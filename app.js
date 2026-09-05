const $ = id => document.getElementById(id);
const API = 'https://hamanako-1m-simulator.onrender.com';
const BOATS = [1,2,3,4,5,6];
const HAMANA_BACK = {
  1:[55.2,15.5,7.1], 2:[11.9,26.4,18.3], 3:[13.6,20.5,20.6],
  4:[11.3,16.9,18.0], 5:[6.9,13.8,20.9], 6:[2.1,7.9,16.1]
};
let raceData = null;
let entryOrder = [...BOATS];

function boat(no){ return (raceData?.boats || []).find(b => +b.boat_no === +no) || {}; }
function label(no){ const b=boat(no); return `${no}号艇 ${b.racer_name || '選手名未取得'}`; }
function ready(data){
  const list=data?.boats || [];
  return list.length===6 && list.every(b => b.racer_name && b.exhibition_time!=null && b.exhibition_st!=null && b.motor_no!=null && b.motor_2rentai_rate!=null && b.motor_3rentai_rate!=null);
}

function renderEntry(){
  $('entryOrder').innerHTML = entryOrder.map((b,i)=>`<label class="entrySlot"><span>${i+1}番手</span><select data-index="${i}">${BOATS.map(x=>`<option value="${x}" ${x===b?'selected':''}>${label(x)}</option>`).join('')}</select></label>`).join('');
  $('entryOrder').querySelectorAll('select').forEach(sel=>sel.addEventListener('change',()=>{
    const i=+sel.dataset.index, v=+sel.value, j=entryOrder.indexOf(v);
    if(j>=0 && j!==i) [entryOrder[i],entryOrder[j]]=[entryOrder[j],entryOrder[i]];
    renderEntry();
    $('liveSim').disabled=true;
    $('liveMsg').textContent='進入想定を変更しました。再度シミュレーションしてください';
  }));
}
function resetEntry(){ entryOrder=[...BOATS]; renderEntry(); if(raceData) $('liveSim').disabled=!ready(raceData); $('liveMsg').textContent='通常進入に戻しました'; }
function fronting(){
  return entryOrder.some((b,i)=>b!==i+1) ? entryOrder.filter((b,i)=>b!==i+1).map(b=>({boat_no:b,strength:70,start_aggression:65,depth:60,give_up:35,target_course:null})) : [];
}

function render(result){
  const slit=result.representative_start_slit||[];
  const slitRate=(result.representative_start_slit_rate||0)*100;
  const back=result.representative_back_middle||[];
  const backRate=(result.representative_back_middle_rate||0)*100;
  const st=result.predicted_st||{};
  $('summary').innerHTML=`<div class="card wide"><div class="label">最頻スリット</div><div class="slit">${slit.map(b=>`<b>${b}</b>`).join(' → ')}</div><div class="sub">出現率 ${slitRate.toFixed(1)}%</div></div><div class="card"><div class="label">予想ST</div><div class="value stGrid">${BOATS.map(b=>`<span><b>${b}号艇</b> ${st[String(b)]!=null?Number(st[String(b)]).toFixed(3):'—'}</span>`).join('')}</div><div class="sub">10,000回MCの平均ST</div></div>`;
  const ar=result.attack_pattern_rate||{};
  const methods=['逃げ','差し','まくり','まくり差し'];
  $('methods').innerHTML=`<div class="methodTable"><div class="methodRow methodHeader"><div class="methodName">決まり手</div>${BOATS.map(b=>`<div class="methodBoat"><span class="boatBadge boat${b}">${b}</span><b>${boat(b).racer_name||'—'}</b><small>${boat(b).racer_class||''}</small></div>`).join('')}</div>${methods.map(m=>`<div class="methodRow"><div class="methodName"><b>${m}</b></div>${BOATS.map(b=>`<div class="methodCell"><span class="miniBoat boat${b}">${b}</span><b>${(((ar[String(b)]||{})[m]||0)*100).toFixed(1)}%</b></div>`).join('')}</div>`).join('')}</div>`;
  const rr=result.rank_rates||{};
  $('bars').innerHTML=BOATS.map(b=>{const x=rr[String(b)]||{};const one=(x['1']||0)*100,two=(x['2']||0)*100,three=(x['3']||0)*100,total=one+two+three,base=HAMANA_BACK[b].reduce((a,v)=>a+v,0),diff=total-base;return `<div class="backRateCard"><div class="backRateHead"><div class="boatIdentity"><span class="boatBadge boat${b}">${b}</span><div><b>${boat(b).racer_name||'—'}</b><small>${boat(b).racer_class||''} / バック中間</small></div></div><strong>${total.toFixed(1)}%</strong></div><div class="rateGrid"><div><span>1番手</span><b>${one.toFixed(1)}%</b></div><div><span>2番手</span><b>${two.toFixed(1)}%</b></div><div><span>3番手</span><b>${three.toFixed(1)}%</b></div></div><div class="compareLine">浜名湖参考 ${base.toFixed(1)}%　<span>${diff>=0?'+':''}${diff.toFixed(1)}pt</span></div></div>`;}).join('');
  const timing=result.back_timing||{}; const tvals=BOATS.map(b=>timing[String(b)]?.mean_sec).filter(v=>typeof v==='number'); const min=Math.min(...tvals), max=Math.max(...tvals); const xFor=b=>{const t=timing[String(b)]?.mean_sec;if(!Number.isFinite(t)||min===max)return 330;return 540-((t-min)/(max-min))*425;};
  const y={1:92,2:126,3:160,4:194,5:228,6:262}; const order=back.length?back:BOATS;
  const points=order.map(b=>{const t=timing[String(b)],x=xFor(b),yy=y[b];return `<g><circle class="boatDot boat${b}" cx="${x.toFixed(1)}" cy="${yy}" r="18"/><text class="boatText" x="${x.toFixed(1)}" y="${yy+6}" text-anchor="middle">${b}</text><text class="boatTime" x="${x.toFixed(1)}" y="${yy-25}" text-anchor="middle">${t?t.mean_sec.toFixed(2)+'s':'—'}</text></g>`;}).join('');
  $('backDiagram').innerHTML=`<div class="diagramWrap"><svg viewBox="0 0 620 330" role="img" aria-label="バックストレッチ展開図"><rect class="waterBox" x="20" y="38" width="580" height="240" rx="14"/><text class="axisLabel" x="590" y="25" text-anchor="end">進行方向 ←</text>${[92,126,160,194,228,262].map(yy=>`<line class="routeLine" x1="55" y1="${yy}" x2="570" y2="${yy}"/>`).join('')}${points}</svg><div class="diagramInfo"><span>代表バック隊形 <b>${order.join(' → ')}</b></span><span>発生率 <b>${backRate.toFixed(1)}%</b></span></div></div>`;
  $('backBadge').textContent=`代表 ${order.join('-')} / ${backRate.toFixed(1)}%`;
}

async function prepare(){
  const date=$('liveDate').value.trim(), race=+$('liveRace').value;
  $('liveMsg').textContent='公式データ取得中…'; $('livePrepare').disabled=true;
  try{
    const res=await fetch(`${API}/live/prepare?date=${date}&race_no=${race}`);
    if(!res.ok) throw new Error(await res.text());
    raceData=await res.json();
    $('liveStatus').textContent=`浜名湖 / ${race}R / ${ready(raceData)?'取得OK':'要確認'}`;
    $('liveBoats').innerHTML=(raceData.boats||[]).map(b=>`<div class="liveBoat"><b>${b.boat_no}号艇</b> ${b.racer_name||'—'} <span>${b.racer_class||''}</span><small>展示ST ${b.exhibition_st??'—'} / 展示 ${b.exhibition_time??'—'} / モーター ${b.motor_no??'—'} / 2連対 ${b.motor_2rentai_rate??'—'}% / 3連対 ${b.motor_3rentai_rate??'—'}%</small></div>`).join('');
    renderEntry(); $('liveSim').disabled=!ready(raceData); $('liveMsg').textContent=ready(raceData)?'取得完了':'6艇の公式データが揃うまでシミュレーションできません';
  }catch(e){ raceData=null; $('liveSim').disabled=true; $('liveMsg').textContent='取得失敗: '+e.message; }
  finally{ $('livePrepare').disabled=false; }
}
async function simulate(){
  if(!ready(raceData)){ $('liveMsg').textContent='公式6艇データが揃っていません'; return; }
  $('liveSim').disabled=true; $('liveMsg').textContent='実戦MC計算中…';
  try{
    const res=await fetch(`${API}/live/simulate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({race:raceData,simulations:10000,seed:Date.now()%2147483647,fronting:fronting(),entry_order:entryOrder})});
    if(!res.ok) throw new Error(await res.text());
    const data=await res.json(); render(data.result||data); $('liveMsg').textContent='実戦シミュレーション完了';
  }catch(e){ $('liveMsg').textContent='シミュレーション失敗: '+e.message; }
  finally{ $('liveSim').disabled=false; }
}

$('livePrepare').addEventListener('click',prepare);
$('liveSim').addEventListener('click',simulate);
$('resetEntry').addEventListener('click',resetEntry);
renderEntry();
