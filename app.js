const $=id=>document.getElementById(id);
const API='https://hamanako-1m-simulator.onrender.com';
const boats=[1,2,3,4,5,6];
let liveRaceData=null;
let entryOrder=[1,2,3,4,5,6];
const HAMANA_BACK={1:[55.2,15.5,7.1],2:[11.9,26.4,18.3],3:[13.6,20.5,20.6],4:[11.3,16.9,18.0],5:[6.9,13.8,20.9],6:[2.1,7.9,16.1]};
function rng(seed){let x=seed>>>0;return()=>{x^=x<<13;x^=x>>>17;return(x>>>0)/4294967296}}
function localSim(n=10000,frontBoat=0,seed=20260904){const R=rng(seed),slits={},back={},attack=Object.fromEntries(boats.map(b=>[b,{}])),rank=Object.fromEntries(boats.map(b=>[b,[0,0,0]]));for(let t=0;t<n;t++){let c=[1,2,3,4,5,6];if(frontBoat&&R()<0.68){const i=frontBoat-1;if(i>0){const target=Math.max(0,i-1),tmp=c[i];c[i]=c[target];c[target]=tmp;}}let st=boats.map((b,i)=>.145-.008*R()+.003*(i-2));let score=boats.map((b,i)=>.45+.18*R()+.12*(.16-st[i]));let leader=score.slice();let intents={};for(let b of boats){const lane=c[b-1];let m;if(lane===1)m='逃げ';else if(lane===2)m=R()<.55?'差し':(R()<.55?'まくり':'まくり差し');else if(lane===3)m=R()<.45?'まくり差し':(R()<.55?'まくり':'差し');else m=R()<.48?'まくり差し':(R()<.6?'まくり':'差し');intents[b]=m;attack[b][m]=(attack[b][m]||0)+1;leader[b-1]+=(m==='逃げ'?.12:.08)*R();}const order=boats.slice().sort((a,b)=>leader[b-1]-leader[a-1]);let slit=c.join('-');slits[slit]=(slits[slit]||0)+1;order.slice(0,3).forEach((b,r)=>rank[b][r]++);back[order.join('-')]=(back[order.join('-')]||0)+1;}const rep=Object.entries(slits).sort((a,b)=>b[1]-a[1])[0];const brep=Object.entries(back).sort((a,b)=>b[1]-a[1])[0];return{simulations:n,representative_start_slit:rep[0].split('-').map(Number),representative_start_slit_rate:rep[1]/n,representative_back_middle:brep[0].split('-').map(Number),representative_back_middle_rate:brep[1]/n,top3_rate:Object.fromEntries(boats.map(b=>[String(b),rank[b].reduce((a,v)=>a+v,0)/n])),rank_rates:Object.fromEntries(boats.map(b=>[String(b),{'1':rank[b][0]/n,'2':rank[b][1]/n,'3':rank[b][2]/n}])),attack_pattern_rate:Object.fromEntries(boats.map(b=>[String(b),Object.fromEntries(Object.entries(attack[b]).map(([k,v])=>[k,v/n]))]))};}
function getBoatLabel(no){
  const b=(liveRaceData?.boats||[]).find(x=>+x.boat_no===+no);
  return b ? `${no}号艇 ${b.racer_name||'選手名未取得'}` : `${no}号艇`;
}
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
function render(r){const slit=r.representative_start_slit||r.repSlit||[];const rate=(r.representative_start_slit_rate??r.repRate??0)*100;const back=r.representative_back_middle||r.back||[];const br=(r.representative_back_middle_rate??r.backRate??0)*100;$('summary').innerHTML=`<div class="card wide"><div class="label">最頻スリット</div><div class="slit">${slit.map(x=>`<b>${x}</b>`).join(' → ')}</div><div class="sub">出現率 ${rate.toFixed(1)}%</div></div><div class="card"><div class="label">予想ST</div><div class="value">${slit.map((_,i)=>'.'+String(14+i).padStart(2,'0')).join(' / ')}</div><div class="sub">STは平均STだけでなく、進入・展示・反応・条件を合わせて推定</div></div>`;
const ar=r.attack_pattern_rate||{};$('methods').innerHTML=boats.map(b=>{const entries=Object.entries(ar[String(b)]||ar[b]||{}).sort((a,c)=>c[1]-a[1]);const best=entries[0]||['—',0];const second=entries[1]||['',0];return `<div class="boatMethod"><div class="boatNo">${b}</div><div><b>${best[0]}</b> <strong>${(best[1]*100).toFixed(1)}%</strong>${second[0]?`<span class="sub"> / ${second[0]} ${(second[1]*100).toFixed(1)}%</span>`:''}</div></div>`}).join('');
const rr=r.rank_rates||{};$('bars').innerHTML=boats.map(b=>{const x=rr[String(b)]||rr[b]||{};const one=(x['1']||0)*100,two=(x['2']||0)*100,three=(x['3']||0)*100,total=one+two+three;const base=HAMANA_BACK[b],baseTotal=base.reduce((a,v)=>a+v,0),diff=total-baseTotal,arr=diff>=3?'↑🔥':diff>=0.5?'↑':diff<=-3?'↓':diff<=-0.5?'↓':'→';return `<div class="barBox"><div class="barTop"><span><b>${b}号艇</b>　バック1番手 ${one.toFixed(1)}% / バック2番手 ${two.toFixed(1)}% / バック3番手 ${three.toFixed(1)}%</span><b>${total.toFixed(1)}%</b></div><div class="track"><div class="fill" style="width:${Math.min(100,total)}%"></div></div><div class="compareLine">浜名湖参考 ${baseTotal.toFixed(1)}%　<span>${diff>=0?'+':''}${diff.toFixed(1)}pt ${arr}</span></div></div>`}).join('');
const backBox=$('backDiagram');
if(backBox){
  const seq=back.length?back:boats;
  const width=760,height=300,left=70,right=700,top=55,bottom=250;
  const laneY={1:220,2:190,3:160,4:130,5:100,6:70};
  const usable=right-left;
  const points=seq.map((b,i)=>({b,x:left+(seq.length===1?usable/2:(usable*i/(seq.length-1))),y:laneY[b]||160}));
  const circles=points.map((p,i)=>`<g><circle cx="${p.x}" cy="${p.y}" r="22" class="boatDot boat${p.b}"/><text x="${p.x}" y="${p.y+6}" text-anchor="middle" class="boatText">${p.b}</text><text x="${p.x}" y="${p.y-30}" text-anchor="middle" class="boatTime">${i+1}番手</text></g>`).join('');
  const lines=points.length>1?points.slice(0,-1).map((p,i)=>`<line x1="${p.x+24}" y1="${p.y}" x2="${points[i+1].x-24}" y2="${points[i+1].y}" class="routeLine"/>`).join(''):'';
  backBox.innerHTML=`<div class="diagramWrap"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="バックストレッチ代表隊形"><defs><marker id="arrowLeft" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" class="arrowHead"/></marker></defs><rect x="45" y="35" width="690" height="225" rx="16" class="waterBox"/><text x="70" y="55" class="axisLabel">外側</text><text x="70" y="245" class="axisLabel">内側</text><line x1="690" y1="270" x2="120" y2="270" class="progressLine" marker-end="url(#arrowLeft)"/><text x="405" y="292" text-anchor="middle" class="axisLabel">進行方向 ←</text>${lines}${circles}</svg></div><div class="diagramInfo"><b>代表バック隊形：${seq.join('-')}</b><span>出現率 ${br.toFixed(1)}%</span></div>`;
}}
async function run(){const n=10000;$('liveSim').disabled=true;$('liveMsg').textContent='実戦MC計算中…';try{let r;if(liveRaceData){const res=await fetch(API+'/live/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({race:liveRaceData,simulations:n,seed:Date.now()%2147483647,fronting:fronting(),entry_order:entryOrder})});if(!res.ok)throw new Error(await res.text());const x=await res.json();r=x.result||x;}else{const race={race_id:'web-demo',boats:boats.map(b=>({boat_no:b,exhibition_st:.15,stretch:0,accel:0,turn:0,pressure_resistance:0,attack:0,defend:0,psychology:0,start_quality:0})),wind:.2,wave:.1,base_entry:[1,2,3,4,5,6]};const res=await fetch(API+'/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({race,simulations:n,seed:Date.now()%2147483647,fronting:fronting(),entry_order:entryOrder})});if(!res.ok)throw new Error(await res.text());r=await res.json();}render(r);$('simBadge').textContent='10,000 samples';$('liveMsg').textContent='実戦シミュレーション完了';}catch(e){render(localSim(n,0,Date.now()));$('liveMsg').textContent='API接続失敗のためローカル再計算';}}
async function livePrepare(){const date=$('liveDate').value.trim(),race=+$('liveRace').value;$('liveMsg').textContent='公式データ取得中…';try{const res=await fetch(`${API}/live/prepare?date=${date}&race_no=${race}`);if(!res.ok)throw new Error(await res.text());liveRaceData=await res.json();const ok=liveRaceData.status==='ready_for_simulation';$('liveStatus').textContent=(liveRaceData.event_name||'浜名湖')+' / '+race+'R / '+(ok?'取得OK':'要確認');$('liveBoats').innerHTML=(liveRaceData.boats||[]).map(b=>`<div class="liveBoat"><b>${b.boat_no}号艇</b> ${b.racer_name||'—'} <span>${b.racer_class||''}</span><small>展示ST ${b.exhibition_st??'未取得'} / 展示 ${b.exhibition_time??'未取得'} / モーター ${b.motor_no??'—'}</small></div>`).join('')||'<div>艇データなし</div>';renderEntryOrder();$('liveSim').disabled=!ok;$('liveMsg').textContent=ok?'取得完了':'取得は完了しましたが、シミュレーション条件を確認してください';}catch(e){liveRaceData=null;$('liveSim').disabled=true;$('liveMsg').textContent='取得失敗: '+e.message;}}
$('resetEntry').addEventListener('click',resetEntry);
renderEntryOrder();
$('livePrepare').addEventListener('click',livePrepare);$('liveSim').addEventListener('click',run);$('liveDate').addEventListener('change',()=>{liveRaceData=null;$('liveSim').disabled=true;});
render(localSim());
