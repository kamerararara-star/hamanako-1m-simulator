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
from bs4 import BeautifulSoup

BASE='https://www.boatrace.jp/owpc/pc/race'
VENUE='06'

def fetch(url, timeout=15):
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; Ver2-Hamanako/2.1)'})
    with urlopen(req,timeout=timeout) as r:
        return r.read().decode('utf-8','ignore')

def cell_texts(html):
    soup=BeautifulSoup(html,'html.parser')
    return [[c.get_text(' ',strip=True) for c in row.find_all(['th','td'])] for row in soup.find_all('tr')]

def parse_roster(html):
    rows=cell_texts(html); boats=[]
    for cells in rows:
        if not cells: continue
        first=re.sub(r'[^0-9]','',cells[0])
        if first not in {'1','2','3','4','5','6'}: continue
        alltext=' '.join(cells)
        m=re.search(r'(\d{4})\s*/\s*([ABC][123])\s+(.+?)(?=\s+[^ ]+\s*/|$)',alltext)
        name=None; cls=None
        if m: cls=m.group(2); name=m.group(3).strip()
        else:
            m2=re.search(r'/\s*([ABC][123])\s+(.+)',alltext)
            if m2: cls=m2.group(1); name=m2.group(2).split()[0]
        wt=None
        mw=re.search(r'(\d{2,3}\.\d)kg',alltext)
        if mw: wt=float(mw.group(1))
        boats.append({'boat_no':int(first),'racer_name':name,'racer_class':cls,'weight':wt,'raw_cells':cells})
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

def build_race(date, race_no, fetch_before=True, fetch_result=False):
    rid=f'{date}_06_{int(race_no):02d}'
    urls={
      'racelist':f'{BASE}/racelist?hd={date}&jcd={VENUE}&rno={race_no}',
      'beforeinfo':f'{BASE}/beforeinfo?hd={date}&jcd={VENUE}&rno={race_no}',
      'result':f'{BASE}/result?hd={date}&jcd={VENUE}&rno={race_no}',
    }
    result={'race_id':rid,'race_date':date,'venue':'浜名湖','race_no':int(race_no),
            'source_url':urls['racelist'],'fetched_at':datetime.now(timezone.utc).isoformat(),
            'status':'incomplete','boats':[],'sources':urls,'errors':[]}
    try:
        roster=parse_roster(fetch(urls['racelist']))
        result['boats']=roster
    except Exception as e:
        result['errors'].append({'stage':'racelist','error':str(e)})
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
