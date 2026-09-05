#!/usr/bin/env python3
"""Official BOAT RACE Hamanako live-data fetcher.

Version: Ver.2 v14.1 tested

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

def norm(s):
    """Normalize full-width/compatibility characters used by the official site."""
    return unicodedata.normalize('NFKC', str(s))

def compact(s):
    return re.sub(r'\s+', '', norm(s))

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
    return [[norm(c.get_text(' ',strip=True)) for c in row.find_all(['th','td'])] for row in soup.find_all('tr')]

def parse_motor_stats_from_text(text):
    """Extract official motor No / 2-rentai / 3-rentai sequence.

    Official racelist rows expose motor data as: motor_no, 2-rentai %,
    3-rentai %, followed by boat No and its rates.
    """
    m=re.search(r"(?<!\d)(\d{1,2})\s+(\d{1,3}\.\d+)\s+(\d{1,3}\.\d+)\s+(\d{1,2})\s+(\d{1,3}\.\d+)\s+(\d{1,3}\.\d+)(?!\d)", text)
    if not m:
        return None
    try:
        motor_no=int(m.group(1)); m2=float(m.group(2)); m3=float(m.group(3))
        if not (1 <= motor_no <= 100 and 0 <= m2 <= 100 and 0 <= m3 <= 100):
            return None
        return motor_no,m2,m3
    except ValueError:
        return None

def parse_roster(html):
    soup=BeautifulSoup(html,'html.parser')
    boats=[]
    jp=re.compile(r'[一-龥々ぁ-んァ-ヶー]{2,}')
    for row in soup.find_all('tr'):
        cells=row.find_all(['th','td'])
        if not cells: continue
        texts=[norm(c.get_text(' ',strip=True)) for c in cells]
        first=texts[0] if texts else ''
        mboat=re.match(r'^\s*([1-6])(?:\D|$)', first)
        if not mboat:
            continue
        boat_no=int(mboat.group(1))
        alltext=' '.join(texts)
        cls=None
        for txt in texts:
            mc=re.search(r'\b([ABC][123])\b',txt)
            if mc:
                cls=mc.group(1); break
        name=None
        # Official racelist exposes the racer name as an <a>. Normalize and
        # remove spacing such as "水口　　由紀" -> "水口由紀".
        for a in row.find_all('a'):
            at=compact(a.get_text(' ',strip=True))
            if jp.fullmatch(at) and len(at)>=2:
                name=at; break
        if not name:
            candidates=[]
            for i,txt in enumerate(texts):
                if i==0 or re.search(r'\b\d{4}\b',txt) or re.search(r'\b[ABC][123]\b',txt):
                    continue
                ct=compact(txt)
                if jp.fullmatch(ct): candidates.append((i,ct))
            if candidates: name=candidates[0][1]
        wt=None
        mw=re.search(r'(\d{2,3}\.\d)kg',alltext)
        if mw: wt=float(mw.group(1))
        reg=None
        for txt in texts:
            mm=re.search(r'(?<!\d)(\d{4})(?!\d)',txt)
            if mm: reg=int(mm.group(1)); break
        motor_no=m2=m3=None
        # Prefer the dedicated motor cell. This avoids false matches in
        # national/local win-rate columns (e.g. 4.45 25.00 40.00).
        mmotor=None
        for txt in texts:
            q=re.search(r'^\s*(\d{1,2})\s+(\d{1,3}\.\d+)\s+(\d{1,3}\.\d+)\s*$',txt)
            if q:
                mmotor=(int(q.group(1)),float(q.group(2)),float(q.group(3)))
                break
        if mmotor:
            motor_no,m2,m3=mmotor
        else:
            mmotor=parse_motor_stats_from_text(alltext)
            if mmotor:
                motor_no,m2,m3=mmotor
        boats.append({'boat_no':boat_no,'racer_name':name,'racer_class':cls,'registration_no':reg,
                      'motor_no':motor_no,'motor_2rentai_rate':m2,'motor_3rentai_rate':m3,
                      'weight':wt,'raw_cells':texts})
    uniq={b['boat_no']:b for b in boats}
    return [uniq[k] for k in sorted(uniq)]

def parse_before(html):
    rows=cell_texts(html); out={}
    for cells in rows:
        if not cells: continue
        first=re.sub(r'[^0-9]','',norm(cells[0]))
        if first not in {'1','2','3','4','5','6'}: continue
        text=' '.join(cells)
        b=int(first); d=out.setdefault(b,{'boat_no':b,'raw_cells':cells})
        for pat,key in [
            (r'(\d\.\d{2})\s*', 'exhibition_time'),
            (r'展示ST\s*([Ff]?\d*\.\d+)', 'exhibition_st'),
            (r'(?<!\d)([1-6])\s*コース', 'exhibition_course'),
            (r'チルト[^-+0-9]*([-+]?\d+(?:\.\d+)?)','tilt'),
        ]:
            m=re.search(pat,text)
            if m and key not in d:
                try:
                    if key=='exhibition_course': d[key]=int(m.group(1))
                    elif key=='exhibition_st': d[key]=_parse_st_value(m.group(1))
                    else: d[key]=float(m.group(1))
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
        m=re.search(r'([1-6])',norm(num.get_text(' ',strip=True)))
        st=_parse_st_value(norm(tm.get_text(' ',strip=True)))
        if not m or st is None:
            continue
        out.append({'course':course,'boat_no':int(m.group(1)),'exhibition_st':st})
    return out

def parse_result(html):
    rows=cell_texts(html); out={}
    for cells in rows:
        if not cells: continue
        first=re.sub(r'[^0-9]','',norm(cells[0]))
        if first not in {'1','2','3','4','5','6'}: continue
        text=' '.join(cells); b=int(first)
        d=out.setdefault(b,{'boat_no':b,'raw_cells':cells})
        m=re.search(r'着順[^0-9]*([1-6])',text)
        if m: d['finish']=int(m.group(1))
        m=re.search(r'進入[^0-9]*([1-6])',text)
        if m: d['actual_course']=int(m.group(1))
        m=re.search(r'ST\s*([Ff]?\d*\.\d+)',text)
        if m: d['actual_st']=float(m.group(1))
        d['raw_text']=text
    return [out[k] for k in sorted(out)]

def extract_motor_3rentai(text, motor_no):
    """Extract 3-rentai immediately following a known official motor number."""
    if motor_no is None:
        return None
    m=re.search(r'(?<!\d)'+re.escape(str(int(motor_no)))+r'\s+([0-9]{1,3}\.[0-9]+)\s+([0-9]{1,3}\.[0-9]+)', str(text))
    if not m:
        return None
    try:
        return float(m.group(2))
    except ValueError:
        return None

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
            raw=' '.join(b.get('raw_cells') or [])
            m3=extract_motor_3rentai(raw,b.get('motor_no'))
            if m3 is not None:
                b['motor_3rentai_rate']=m3
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
    exact_six=sorted(int(b.get('boat_no',0)) for b in result['boats'])==[1,2,3,4,5,6]
    required_names=exact_six and all(b.get('racer_name') for b in result['boats'])
    required_motor=exact_six and all(b.get('motor_no') is not None and b.get('motor_2rentai_rate') is not None and b.get('motor_3rentai_rate') is not None for b in result['boats'])
    required_before=exact_six and all(b.get('exhibition_time') is not None and b.get('exhibition_st') is not None for b in result['boats']) if result['boats'] else False
    result['status']='ready_for_simulation' if required_names and required_motor and required_before else ('needs_exhibition' if required_names and required_motor else 'incomplete')
    return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--date',required=True); ap.add_argument('--race',type=int,required=True); ap.add_argument('--result',action='store_true'); ap.add_argument('--output',required=True)
    a=ap.parse_args(); d=build_race(a.date,a.race,True,a.result); open(a.output,'w',encoding='utf-8').write(json.dumps(d,ensure_ascii=False,indent=2)); print(json.dumps(d,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
