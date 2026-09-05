const $=id=>document.getElementById(id);
const API='https://hamanako-1m-simulator.onrender.com';
const UI_VERSION='v13.2';
const boats=[1,2,3,4,5,6];
let liveRaceData=null;
let entryOrder=[1,2,3,4,5,6];
const HAMANA_BACK={1:[55.2,15.5,7.1],2:[11.9,26.4,18.3],3:[13.6,20.5,20.6],4:[11.3,16.9,18.0],5:[6.9,13.8,20.9],6:[2.1,7.9,16.1]};
function getBoatInfo(no){
  const b=(liveRaceData?.boats||[]).find(x=>+x.boat_no===+no)||{};
  const raw=Array.isArray(b.raw_cells)?b.raw_cells.flatMap(x=>String(x).split(/\s+/)).filter(Boolean):[];
  const jp=/^[一-龥々ぁ-んァ-ヶー]{2,}$/;
  const rawName=raw.find(x=>jp.test(x) && !/^[ABC][123]$/.test(x));
  return {
    name:b.racer_name||b.racerName||b.racer||b.name||b.player_name||b.playerName||b.player||rawName||'選手名未取得',
    cls:b.racer_class||b.racerClass||b.class||b.grade||''
  };
}
function getBoatLabel(no){ const x=getBoatInfo(no); return `${no}号艇 ${x.name}`; }
function renderEntryOrder(){
  const box=$('entryOrder'); if(!box)return;
  box.innerHTML=entryOrder.map((b,i)=>`<label class="entrySlot"><span>${i+1}番手</span><select data-entry-index="${i}">${boats.map(x=>`<option value="${x}" ${+x===+b?'selected':''}>${getBoatLabel(x)}</option>`).join('')}</select></label>`).join('');
  box.querySelectorAll('select').forEach(sel=>sel.addEventListener('change',()=>{
    const idx=+sel.dataset.entryIndex, val=+sel.value;
    const other=entryOrder.indexOf(val);
    if(other>=0 && other!==idx){ const tmp=entryOrder[idx]; entryOrder[idx]=entryOrder[other]; entryOrder[other]=tmp; }
    else entryOrder[idx]=val;
    renderEntryOrder(); liveRaceData && ($('liveSim').disabled=true); $('liveMsg').textContent='進入想定を変更しました。もう一度シミュレーションしてください';
  }));
}
function resetEntry(){entryOrder=[1,2,3,4,5,6];renderEntryOrder();$('liveMsg').textContent='通常進入に戻しました';}
function fronting(){
  const changed=entryOrder.some((b,i)=>b!==i+1);
  if(!changed) return [];
  return entryOrder.filter((b,i)=>b!==i+1).map(b=>({boat_no:b,strength:70,start_aggression:65,depth:60,give_up:35,target_course:null}));
}
function render(r){
  const slit=r.representative_start_slit||r.repSlit||[];
  const rate=(r.representative_start_slit_rate??r.repRate??0)*100;
  const back=r.representative_back_middle||r.back||[];
  const br=(r.representative_back_middle_rate??r.backRate??0)*100;
  const names=b=>getBoatLabel(b);
  const st=r.predicted_st||{};
  $('summary').innerHTML=`<div class="card wide"><div class="label">最頻スリット</div><div class="slit">${slit.map(x=>`<b>${x}</b>`).join(' → ')}</div><div class="sub">出現率 ${rate.toFixed(1)}%</div></div><div class="card"><div class="label">予想ST</div><div class="value stGrid">${boats.map(b=>`<span><b>${b}号艇</b> ${st[String(b)]!=null?st[String(b)].toFixed(3):'—'}</span>`).join('')}</div><div class="sub">10,000回のシミュレーションから算出した平均ST（推定）</div></div>`;

  const ar=r.attack_pattern_rate||{};
  const methodOrder=['逃げ','差し','まくり','まくり差し'];
  $('methods').innerHTML=`<div class="methodTable"><div class="methodTitle"><b>1M決まり手パターン</b><span>6艇×4種類を同じ並びで表示（0.0%も表示）</span></div><div class="methodRow methodHeader"><div class="methodName">決まり手</div>${boats.map(b=>{const x=getBoatInfo(b);return `<div class="methodBoat"><span class="boatBadge boat${b}">${b}</span><b>${x.name}</b><small>${x.cls}${(liveRaceData?.boats||[]).find(z=>+z.boat_no===+b)?.course?` / ${(+((liveRaceData.boats||[]).find(z=>+z.boat_no===+b).course))}コース`:''}</small></div>`}).join('')}</div>${methodOrder.map(m=>`<div class="methodRow"><div class="methodName"><b>${m}</b></div>${boats.map(b=>{const v=(ar[String(b)]||ar[b]||{})[m]||0;return `<div class="methodCell"><span class="miniBoat boat${b}">${b}</span><b>${(v*100).toFixed(1)}%</b></div>`}).join('')}</div>`).join('')}</div>`;

  const rr=r.rank_rates||{};
  $('bars').innerHTML=boats.map(b=>{
    const x=rr[String(b)]||rr[b]||{}; const one=(x['1']||0)*100,two=(x['2']||0)*100,three=(x['3']||0)*100,total=one+two+three;
    const base=HAMANA_BACK[b],baseTotal=base.reduce((a,v)=>a+v,0),diff=total-baseTotal,arr=diff>=3?'↑🔥':diff>=0.5?'↑':diff<=-3?'↓':diff<=-0.5?'↓':'→';
    return `<div class="backRateCard"><div class="backRateHead"><div class="boatIdentity"><span class="boatBadge boat${b}">${b}</span><div><b>${getBoatInfo(b).name}</b><small>${getBoatInfo(b).cls} / バック中間</small></div></div><strong>${total.toFixed(1)}%</strong></div><div class="rateGrid"><div><span>1番手</span><b>${one.toFixed(1)}%</b></div><div><span>2番手</span><b>${two.toFixed(1)}%</b></div><div><span>3番手</span><b>${three.toFixed(1)}%</b></div></div><div class="track"><div class="fill" style="width:${Math.min(100,total)}%"></div></div><div class="compareLine">浜名湖参考 ${baseTotal.toFixed(1)}%　<span>${diff>=0?'+':''}${diff.toFixed(1)}pt ${arr}</span></div></div>`;
  }).join('');

  const timing=r.back_timing||{};
  const order=back.length?back:boats;
  const xs=[540,455,370,285,200,115];
  const yMap={1:92,2:126,3:160,4:194,5:228,6:262};
  const tvals=boats.map(b=>timing[String(b)]?.mean_sec).filter(v=>typeof v==='number');
  const minT=tvals.length?Math.min(...tvals):null;
  const maxT=tvals.length?Math.max(...tvals):null;
  const xFor=b=>{
    const t=timing[String(b)]?.mean_sec;
    if(t==null||minT==null||maxT===minT) return 330;
    return 540-((t-minT)/(maxT-minT))*425;
  };
  const points=order.map((b,i)=>{const x=xFor(b), y=yMap[b]??(90+i*34); const tt=timing[String(b)]; const gap=tt?tt.gap_to_leader_sec:0; return `<g><circle class="boatDot boat${b}" cx="${x.toFixed(1)}" cy="${y}" r="18"/><text class="boatText" x="${x.toFixed(1)}" y="${y+6}" text-anchor="middle">${b}</text><text class="boatTime" x="${x.toFixed(1)}" y="${y-25}" text-anchor="middle">${tt?tt.mean_sec.toFixed(2)+'s':'—'}</text><text class="boatGap" x="${x.toFixed(1)}" y="${y+34}" text-anchor="middle">${tt?'+'+gap.toFixed(2)+'s':''}</text></g>`}).join('');
  $('backDiagram').innerHTML=`<div class="backDiagram"><div class="diagramWrap"><svg viewBox="0 0 620 330" role="img" aria-label="バックストレッチ展開図"><rect class="waterBox" x="20" y="38" width="580" height="240" rx="14"/><text class="axisLabel" x="590" y="25" text-anchor="end">進行方向 ←</text><text class="axisLabel" x="30" y="58">外側</text><text class="axisLabel" x="30" y="270">内側</text><line class="progressLine" x1="565" y1="300" x2="70" y2="300"/><path class="arrowHead" d="M70 300 l14 -7 v14 z"/>${[92,126,160,194,228,262].map(y=>`<line class="routeLine" x1="55" y1="${y}" x2="570" y2="${y}"/>`).join('')}${points}</svg><div class="diagramInfo"><span>代表バック隊形 <b>${order.join(' → ')}</b></span><span>発生率 <b>${br.toFixed(1)}%</b></span></div><div class="diagramLegend">※時間はシミュレーション上のバック基準点への推定到達時間。先頭との差を併記。</div></div></div>`;
  $('backBadge').textContent=`代表 ${order.join('-')} / ${br.toFixed(1)}%`;
}
async function run(){const n=10000;if(!liveRaceData){$('liveMsg').textContent='先に公式データを取得してください';return;} $('liveSim').disabled=true;$('liveMsg').textContent='実戦MC計算中…';try{const res=await fetch(API+'/live/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({race:liveRaceData,simulations:n,seed:Date.now()%2147483647,fronting:fronting(),entry_order:entryOrder})});if(!res.ok)throw new Error(await res.text());const x=await res.json();const r=x.result||x;render(r);$('simBadge').textContent='10,000 samples / '+UI_VERSION;$('liveMsg').textContent='実戦シミュレーション完了';}catch(e){$('liveSim').disabled=false;$('liveMsg').textContent='計算失敗: '+(e.message||e)+'。結果は表示していません。';}}
async function livePrepare(){
  const date=$('liveDate').value.trim(),race=+$('liveRace').value;
  $('liveMsg').textContent='公式データ取得中…';
  try{
    const res=await fetch(`${API}/live/prepare?date=${date}&race_no=${race}`);
    if(!res.ok)throw new Error(await res.text());
    liveRaceData=await res.json();
    const list=liveRaceData.boats||[];
    const readyEvidence=list.length===6 && list.every(b=>b.exhibition_time!=null && b.exhibition_st!=null);
    const ok=liveRaceData.status==='ready_for_simulation' || (liveRaceData.status==='needs_exhibition' && readyEvidence) || readyEvidence;
    $('liveStatus').textContent=(liveRaceData.event_name||'浜名湖')+' / '+race+'R / '+(ok?'取得OK':'要確認');
    $('liveBoats').innerHTML=list.map(b=>{
      const info=getBoatInfo(b.boat_no);
      const name=(b.racer_name||info.name||'選手名未取得');
      return `<div class="liveBoat"><b>${b.boat_no}号艇</b> ${name} <span>${b.racer_class||info.cls||''}</span><small>展示ST ${b.exhibition_st??'未取得'} / 展示 ${b.exhibition_time??'未取得'} / モーター ${b.motor_no??'—'}${b.motor_2rentai_rate!=null?` / モーター2連対率 ${Number(b.motor_2rentai_rate).toFixed(1)}%`:''}</small></div>`;
    }).join('')||'<div>艇データなし</div>';
    renderEntryOrder();
    $('liveSim').disabled=!ok;
    $('liveMsg').textContent=ok?'取得完了。③ 実戦10,000回を押せます':'取得は完了しましたが、シミュレーション条件を確認してください';
  }catch(e){
    liveRaceData=null;
    $('liveSim').disabled=true;
    $('liveMsg').textContent='取得失敗: '+e.message;
  }
}
$('resetEntry').addEventListener('click',resetEntry);
const dateInput=$('liveDate'); if(dateInput){ const d=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()).replace(/-/g,''); if(!/^\d{8}$/.test(dateInput.value)||dateInput.value==='20260904') dateInput.value=d; }
renderEntryOrder();
$('simBadge').textContent='公式データ取得待ち / '+UI_VERSION;
$('liveMsg').textContent='日付とRを選び「公式データ取得」を押してください';
$('livePrepare').addEventListener('click',livePrepare);$('liveSim').addEventListener('click',run);$('liveDate').addEventListener('change',()=>{liveRaceData=null;$('liveSim').disabled=true;});
// No local/demo result is rendered. Results appear only after official-data MC succeeds.
