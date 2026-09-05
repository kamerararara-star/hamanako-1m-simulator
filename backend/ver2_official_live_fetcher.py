#!/usr/bin/env python3
"""Official BOAT RACE Hamanako live-data fetcher.

Low-load, one-race-at-a-time design. No bulk crawling and no video downloading.
If a page cannot be fetched or parsed, the result remains incomplete rather than
being guessed.
"""
from __future__ import annotations
import re, json, argparse
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

def parse_roster(html):
    soup=BeautifulSoup(html,'html.parser')
    boats=[]
    for row in soup.find_all('tr'):
        cells=row.find_all(['th','td'])
        if not cells: continue
        texts=[c.get_text(' ',strip=True) for c in cells]
        first=texts[0] if texts else ''
        mboat=re.match(r'^\s*([1-6])(?:\D|$)', first)
        if not mboat:
            # Some official table variants put the lane number in a classed cell.
            mboat=None
            for txt in texts[:3]:
                q=re.match(r'^\s*([1-6])(?:\D|$)',txt)
                if q: mboat=q; break
        if not mboat: continue
        boat_no=int(mboat.group(1))
        alltext=' '.join(texts)
        cls=None
        class_idx=-1
        for i,txt in enumerate(texts):
            mc=re.search(r'\b([ABC][123])\b',txt)
            if mc:
                cls=mc.group(1); class_idx=i; break
        name=None
        # Prefer a cell containing Japanese characters near the class/registration fields.
        jp=re.compile(r'[一-龥々ぁ-んァ-ヶー]{2,}')
        candidates=[]
        for i,txt in enumerate(texts):
            if i == 0: continue
            if re.search(r'\b\d{4}\b',txt) or re.search(r'\b[ABC][123]\b',txt): continue
            for token in re.split(r'\s+',txt):
                token=token.strip()
                if jp.fullmatch(token): candidates.append((abs(i-class_idx) if class_idx>=0 else i, i, token))
        if candidates:
            candidates.sort(key=lambda z:(z[0],z[1]))
            name=candidates[0][2]
        if not name:
            # Fallback to the historical compact-text parser.
            m=re.search(r'(?:\d{4}\s*/\s*)?([ABC][123])\s+(.+?)(?=\s+\d{2,3}\.\dkg|\s+\d{2,3}\.\d|$)',alltext)
            if m:
                if cls is None: cls=m.group(1)
                name=m.group(2).strip().split()[0]
        wt=None
        mw=re.search(r'(\d{2,3}\.\d)kg',alltext)
        if mw: wt=float(mw.group(1))
        reg=None
        for txt in texts:
            mm=re.search(r'(?<!\d)(\d{4})(?!\d)',txt)
            if mm: reg=int(mm.group(1)); break
        motor_no=None
        mmotor=re.search(r'(?:モーター\s*)?(\d{1,2})\s+(?:\d{1,3}\.\d)%',alltext)
        if mmotor: motor_no=int(mmotor.group(1))
        boats.append({'boat_no':boat_no,'racer_name':name,'racer_class':cls,'registration_no':reg,'motor_no':motor_no,'weight':wt,'raw_cells':texts})
    uniq={b['boat_no']:b for b in boats}
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
            before=parse_before(fetch(urls['beforeinfo']));
            by={x['boat_no']:x for x in before}
            for b in result['boats']: b.update({k:v for k,v in by.get(b['boat_no'],{}).items() if k!='boat_no'})
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
