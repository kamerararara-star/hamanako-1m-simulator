#!/usr/bin/env python3
"""Official BOAT RACE Hamanako live-data fetcher.

Low-load, one-race-at-a-time design. No bulk crawling and no video downloading.
If a page cannot be fetched or parsed, the result remains incomplete rather than
being guessed.
"""
from __future__ import annotations
import re, json, argparse, unicodedata
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import time
from bs4 import BeautifulSoup

BASE='https://www.boatrace.jp/owpc/pc/race'
VENUE='06'

def fetch(url, timeout=20, retries=2):
    headers={
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36',
        'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language':'ja,en-US;q=0.8,en;q=0.6',
        'Referer':'https://www.boatrace.jp/'
    }
    last=None
    for attempt in range(retries+1):
        try:
            req=Request(url,headers=headers)
            with urlopen(req,timeout=timeout) as r:
                body=r.read().decode('utf-8','ignore')
                if len(body)>1000: return body
                raise RuntimeError('official page response was unexpectedly short')
        except Exception as e:
            last=e
            if attempt<retries: time.sleep(0.7*(attempt+1))
    raise last

def cell_texts(html):
    soup=BeautifulSoup(html,'html.parser')
    return [[c.get_text(' ',strip=True) for c in row.find_all(['th','td'])] for row in soup.find_all('tr')]

def _norm(s):
    return unicodedata.normalize('NFKC', str(s or '')).replace('\u3000',' ').strip()

def _extract_roster_row(cells, fallback_boat=None):
    texts=[_norm(c) for c in cells]
    alltext=' '.join(texts)
    boat_no=fallback_boat
    # Official HTML normally puts the frame number in the first cell.  Some
    # variants render it as a full-width digit or wrap it in an image/span.
    for txt in texts[:5]:
        m=re.match(r'^\s*([1-6])(?:\D|$)',txt)
        if m:
            boat_no=int(m.group(1)); break
    if boat_no is None:
        for txt in texts[:5]:
            m=re.search(r'(?:^|\s)([1-6])(?:号艇|枠|コース)(?:\s|$)',txt)
            if m:
                boat_no=int(m.group(1)); break
    if boat_no is None:
        return None

    cls=None; class_idx=-1
    for i,txt in enumerate(texts):
        mc=re.search(r'\b([ABC][123])\b',txt)
        if mc:
            cls=mc.group(1); class_idx=i; break

    name=None
    jp=re.compile(r'[一-龥々ぁ-んァ-ヶー]{2,}')
    candidates=[]
    for i,txt in enumerate(texts):
        if i == 0: continue
        if re.search(r'\b\d{4}\b',txt) or re.search(r'\b[ABC][123]\b',txt): continue
        for token in re.split(r'\s+',txt):
            token=token.strip()
            if jp.fullmatch(token):
                candidates.append((abs(i-class_idx) if class_idx>=0 else i, i, token))
    if candidates:
        candidates.sort(key=lambda z:(z[0],z[1])); name=candidates[0][2]
    if not name:
        m=re.search(r'(?:\d{4}\s*/\s*)?([ABC][123])\s+(.+?)(?=\s+\d{2,3}\.\dkg|\s+\d{2,3}\.\d|$)',alltext)
        if m:
            if cls is None: cls=m.group(1)
            name=m.group(2).strip().split()[0]

    wt=None
    mw=re.search(r'(\d{2,3}\.\d)\s*kg',alltext)
    if mw: wt=float(mw.group(1))
    reg=None
    for txt in texts:
        mm=re.search(r'(?<!\d)(\d{4})(?!\d)',txt)
        if mm: reg=int(mm.group(1)); break
    motor_no=None
    mmotor=re.search(r'(?:モーター\s*)?(\d{1,2})\s+(?:\d{1,3}\.\d)%',alltext)
    if mmotor: motor_no=int(mmotor.group(1))
    return {'boat_no':boat_no,'racer_name':name,'racer_class':cls,
            'registration_no':reg,'motor_no':motor_no,'weight':wt,'raw_cells':texts}

def parse_roster(html):
    soup=BeautifulSoup(html,'html.parser')
    boats=[]
    candidate_rows=[]
    for row in soup.find_all('tr'):
        cells=row.find_all(['th','td'])
        if not cells: continue
        texts=[_norm(c.get_text(' ',strip=True)) for c in cells]
        alltext=' '.join(texts)
        # A racer row has a registration number and class.  Keep these rows as
        # a reliable ordered fallback when the frame-number cell is rendered in
        # a variant form (this is what caused 6号艇 to disappear).
        if re.search(r'(?<!\d)\d{4}(?!\d)',alltext) and re.search(r'\b[ABC][123]\b',alltext):
            candidate_rows.append(cells)
        item=_extract_roster_row(cells)
        if item and item.get('racer_name'):
            boats.append(item)

    uniq={b['boat_no']:b for b in boats if b.get('boat_no') in range(1,7)}
    missing=[b for b in range(1,7) if b not in uniq]
    if missing and len(candidate_rows)>=6:
        # Official racelist order is frame 1..6. Rebuild missing entries from
        # the six racer rows, but preserve any already-parsed richer entries.
        ordered=[]
        for idx,row in enumerate(candidate_rows[:6],start=1):
            item=_extract_roster_row(row, fallback_boat=idx)
            if item: ordered.append(item)
        for item in ordered:
            b=item['boat_no']
            if b not in uniq or not uniq[b].get('racer_name'):
                uniq[b]=item

    return [uniq[k] for k in sorted(uniq)]

def parse_before(html):
    rows=cell_texts(html); out={}
    for cells in rows:
        if not cells: continue
        first=re.sub(r'[^0-9]','',cells[0])
        if first not in {'1','2','3','4','5','6'}: continue
        text=' '.join(cells)
        b=int(first); d=out.setdefault(b,{'boat_no':b,'raw_cells':cells})
        for pat,key in [
            (r'(\d\.\d{2})\s*', 'exhibition_time'),
            (r'展示ST[^0-9]*([-.]?\d+\.\d+)', 'exhibition_st'),
            (r'(?<!\d)([1-6])\s*コース', 'exhibition_course'),
            (r'チルト[^-+0-9]*([-+]?\d+(?:\.\d+)?)','tilt'),
        ]:
            m=re.search(pat,text)
            if m and key not in d:
                try: d[key]=float(m.group(1)) if key!='exhibition_course' else int(m.group(1))
                except ValueError: pass
        # Fallback: collect decimal tokens for later human review.
        d['raw_text']=text
    return [out[k] for k in sorted(out)]


def _parse_st_value(text):
    """Parse official start-exhibition ST tokens such as .09 or F.03."""
    t=str(text).strip().upper().replace(' ', '')
    m=re.search(r'([0-9]*\.[0-9]+)',t)
    if not m:
        return None
    v=float(m.group(1))
    return -v if t.startswith('F') else v

def parse_start_exhibition(html):
    """Parse the official start-exhibition grid.

    BOAT RACE's beforeinfo page renders six .table1_boatImage1 blocks in
    course order. Each block contains the boat number and the ST.  The course
    is the block order (1..6), while the number span is the actual boat number.
    This is important when the start exhibition entry differs from frame order.
    """
    soup=BeautifulSoup(html,'html.parser')
    out=[]
    blocks=soup.select('div.table1_boatImage1')
    for course,block in enumerate(blocks[:6],start=1):
        num=block.select_one('.table1_boatImage1Number')
        tm=block.select_one('.table1_boatImage1Time')
        if not num or not tm:
            continue
        m=re.search(r'([1-6])',num.get_text(' ',strip=True))
        st=_parse_st_value(tm.get_text(' ',strip=True))
        if not m or st is None:
            continue
        out.append({'course':course,'boat_no':int(m.group(1)),'exhibition_st':st})
    return out

def parse_result(html):
    rows=cell_texts(html); out={}
    for cells in rows:
        if not cells: continue
        first=re.sub(r'[^0-9]','',cells[0])
        if first not in {'1','2','3','4','5','6'}: continue
        text=' '.join(cells); b=int(first)
        d=out.setdefault(b,{'boat_no':b,'raw_cells':cells})
        m=re.search(r'着順[^0-9]*([1-6])',text)
        if m: d['finish']=int(m.group(1))
        m=re.search(r'進入[^0-9]*([1-6])',text)
        if m: d['actual_course']=int(m.group(1))
        m=re.search(r'ST[^-+0-9]*([-.]?\d+\.\d+)',text)
        if m: d['actual_st']=float(m.group(1))
        d['raw_text']=text
    return [out[k] for k in sorted(out)]

def parse_motor_ranking(html):
    rows=cell_texts(html); out={}
    for cells in rows:
        text=' '.join(cells)
        mreg=re.search(r'(?<!\d)(\d{4})(?!\d)',text)
        if not mreg: continue
        reg=int(mreg.group(1))
        # Table order: registration, racer, class, motor no, motor 2-rentai, boat no, boat 2-rentai, time.
        mm=re.search(r'\b([1-6]\d?|\d{1,2})\s+(\d{1,3}\.\d)%',text)
        if not mm: continue
        try:
            motor_no=int(mm.group(1)); motor_rate=float(mm.group(2))
        except ValueError:
            continue
        out[reg]={'motor_no':motor_no,'motor_2rentai_rate':motor_rate}
    return out

def build_race(date, race_no, fetch_before=True, fetch_result=False):
    rid=f'{date}_06_{int(race_no):02d}'
    urls={
      'racelist':f'{BASE}/racelist?hd={date}&jcd={VENUE}&rno={race_no}',
      'beforeinfo':f'{BASE}/beforeinfo?hd={date}&jcd={VENUE}&rno={race_no}',
      'result':f'{BASE}/result?hd={date}&jcd={VENUE}&rno={race_no}',
      'rankingmotor':f'{BASE}/rankingmotor?hd={date}&jcd={VENUE}',
    }
    result={'race_id':rid,'race_date':date,'venue':'浜名湖','race_no':int(race_no),
            'source_url':urls['racelist'],'fetched_at':datetime.now(timezone.utc).isoformat(),
            'status':'incomplete','boats':[],'sources':urls,'errors':[]}
    try:
        roster=parse_roster(fetch(urls['racelist']))
        result['boats']=roster
    except Exception as e:
        result['errors'].append({'stage':'racelist','error':str(e)})
    try:
        ranking=parse_motor_ranking(fetch(urls['rankingmotor']))
        for b in result['boats']:
            reg=b.get('registration_no')
            if reg in ranking:
                b.update(ranking[reg])
        result['motor_data_source']=urls['rankingmotor']
        result['motor_field_count']=len(ranking)
    except Exception as e:
        result['errors'].append({'stage':'rankingmotor','error':str(e)})
    if fetch_before:
        try:
            before_html=fetch(urls['beforeinfo'])
            before=parse_before(before_html)
            by={x['boat_no']:x for x in before}
            for b in result['boats']: b.update({k:v for k,v in by.get(b['boat_no'],{}).items() if k!='boat_no'})
            start_ex=parse_start_exhibition(before_html)
            result['start_exhibition']=start_ex
            result['start_exhibition_count']=len(start_ex)
            # Map official start-exhibition ST to the actual boat number.
            # The row order is the course; the embedded number is the boat.
            for x in start_ex:
                for b in result['boats']:
                    if b.get('boat_no') == x['boat_no']:
                        b['exhibition_st']=x['exhibition_st']
                        b['exhibition_course']=x['course']
                        break
        except Exception as e: result['errors'].append({'stage':'beforeinfo','error':str(e)})
    if fetch_result:
        try:
            result['result']=parse_result(fetch(urls['result']))
        except Exception as e: result['errors'].append({'stage':'result','error':str(e)})
    required_names=len(result['boats'])==6 and all(b.get('racer_name') for b in result['boats'])
    required_before=all(b.get('exhibition_time') is not None and b.get('exhibition_st') is not None for b in result['boats']) if result['boats'] else False
    result['status']='ready_for_simulation' if required_names and required_before else ('needs_exhibition' if required_names else 'incomplete')
    return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--date',required=True); ap.add_argument('--race',type=int,required=True); ap.add_argument('--result',action='store_true'); ap.add_argument('--output',required=True)
    a=ap.parse_args(); d=build_race(a.date,a.race,True,a.result); open(a.output,'w',encoding='utf-8').write(json.dumps(d,ensure_ascii=False,indent=2)); print(json.dumps(d,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
