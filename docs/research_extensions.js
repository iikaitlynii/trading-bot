"use strict";
// Educational local-only tools. No brokerage credentials or orders.
(()=>{
const el=id=>document.getElementById(id);
const usd=n=>new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:2}).format(n);
const val=(id,def=0)=>{const n=Number(el(id)?.value);return Number.isFinite(n)&&n>=0?n:def};
const keys=["wealth-saved","wealth-monthly","wealth-income","wealth-expenses"];
try{for(const id of keys){const s=localStorage.getItem("paperlab-"+id);if(s!==null&&el(id))el(id).value=s}}catch(e){}
function wealth(){const saved=val("wealth-saved"),monthly=val("wealth-monthly"),income=val("wealth-income"),expenses=val("wealth-expenses");const remaining=Math.max(0,100000-saved);const required=remaining/60;el("wealth-progress").textContent=(100*saved/100000).toFixed(2)+"%";el("wealth-projection").textContent=usd(saved+60*monthly);el("wealth-gap").textContent=usd(Math.max(0,required-monthly));el("wealth-cashflow").textContent=usd(income-expenses-monthly);el("wealth-note").textContent="To reach $100,000 in 60 months without market returns, save about "+usd(required)+" monthly. Negative cash flow means the plan needs adjustment. This is a planning scenario, not a prediction.";const milestones=el("wealth-milestones");if(milestones){milestones.replaceChildren();for(let y=1;y<=5;y++){const amount=saved+12*y*monthly;const tr=document.createElement("tr");for(const v of ["Year "+y,usd(amount),(amount/100000*100).toFixed(1)+"%"]){const td=document.createElement("td");td.textContent=v;tr.appendChild(td)}milestones.appendChild(tr)}}for(const id of keys)try{localStorage.setItem("paperlab-"+id,el(id).value)}catch(e){}}
for(const id of keys)el(id)?.addEventListener("input",wealth);el("wealth-reset")?.addEventListener("click",()=>{for(const [id,value] of [["wealth-saved","184.86"],["wealth-monthly","100"],["wealth-income","0"],["wealth-expenses","0"]])el(id).value=value;wealth()});wealth();
function etf(){const initial=val("etf-initial"),monthly=val("etf-monthly"),years=Math.max(1,Math.min(40,val("etf-years",5))),rate=Math.max(-20,Math.min(20,Number(el("etf-rate").value)||0))/1200,n=Math.round(years*12);const factor=Math.pow(1+rate,n);const future=initial*factor+(rate===0?monthly*n:monthly*(factor-1)/rate);el("etf-projection").textContent="Hypothetical balance: "+usd(future)+" | Contributions: "+usd(initial+monthly*n)+" | Gain/loss: "+usd(future-initial-monthly*n)}
for(const id of ["etf-initial","etf-monthly","etf-years","etf-rate"])el(id)?.addEventListener("input",etf);etf();
async function screen(){try{const rows=await read("crypto_paper/latest_signals.csv");const body=el("meme-screen-rows");body.replaceChildren();for(const r of rows){const good=[r.close,r.ma20,r.ma50,r.ma100].every(x=>x!==""&&Number.isFinite(Number(x))&&Number(x)>0);const above=good&&Number(r.ma20)>Number(r.ma50);const long=good&&Number(r.close)>Number(r.ma100);const warning=!good?"Missing price or averages":r.signal==="DEFENSIVE"?"Defensive signal; verify liquidity and token risks":"Liquidity, ownership and contract risks unverified";const tr=document.createElement("tr");for(const v of [r.ticker,good?(above?"Above":"Below"):"Unavailable",good?(long?"Above":"Below"):"Unavailable",warning]){const td=document.createElement("td");td.textContent=v;tr.appendChild(td)}body.appendChild(tr)}el("meme-screen-status").textContent=rows.length+" saved assets reviewed; screening does not identify new launches or establish safety."}catch(e){el("meme-screen-status").textContent="Research snapshot unavailable."}}screen();
async function forwardTable(){const body=el("meme-forward-rows");if(!body)return;try{const rows=await read("crypto_paper/forward_signals.csv");body.replaceChildren();for(const r of rows.slice(-30).reverse()){const change=r.next_return_pct!==""&&Number.isFinite(Number(r.next_return_pct))?(Number(r.next_return_pct)>=0?"+":"")+Number(r.next_return_pct).toFixed(2)+"%":"Pending";const tr=document.createElement("tr");for(const v of [r.observed_date||"—",r.ticker||"—",r.signal||"—",r.next_date||"Pending",change]){const td=document.createElement("td");td.textContent=v;tr.appendChild(td)}body.appendChild(tr)}if(!rows.length){const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=5;td.textContent="No observations recorded yet";tr.appendChild(td);body.appendChild(tr)}}catch(e){body.textContent="Forward data not yet available"}}forwardTable();
async function discoveryTable(){const body=el("token-discovery-rows"),status=el("token-discovery-status");if(!body)return;try{const rows=await read("crypto_paper/discovered_tokens.csv");body.replaceChildren();const usd=n=>n!==""&&Number.isFinite(Number(n))?new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(Number(n)):"Unknown";for(const r of rows.slice(0,30)){const tr=document.createElement("tr");for(const v of [r.symbol||"Unknown",r.pair_age_hours!==""?r.pair_age_hours+"h":"Unknown",usd(r.liquidity_usd),usd(r.volume_24h_usd),(r.research_flags||"Unverified").replaceAll("|",", ")]){const td=document.createElement("td");td.textContent=v;tr.appendChild(td)}body.appendChild(tr)}status.textContent=rows.length?rows.length+" public profiles observed; latest snapshot "+rows[0].observed_utc:"No Solana profiles returned in latest snapshot."}catch(e){status.textContent="No snapshot yet. Run the Token Discovery Research workflow in GitHub Actions or wait for the daily schedule."}}discoveryTable();

let etfHistory=[];
function drawEtf(){const svg=el("etf-history-chart");if(!svg)return;const fund=el("etf-chart-fund").value,rows=etfHistory.filter(r=>r.fund===fund&&Number.isFinite(Number(r.indexed_value))).sort((a,b)=>a.month.localeCompare(b.month));svg.replaceChildren();const ns="http://www.w3.org/2000/svg";const node=(tag,attrs,text)=>{const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;svg.appendChild(e);return e};if(rows.length<2){el("etf-chart-status").textContent="Historical data not yet available for "+fund+". Run ETF Historical Research in GitHub Actions.";return}const values=rows.map(r=>Number(r.indexed_value)),min=Math.min(...values),max=Math.max(...values),pad=Math.max(5,(max-min)*.12),lo=min-pad,hi=max+pad,x=i=>55+i*630/(rows.length-1),y=v=>225-(v-lo)*185/(hi-lo);for(let k=0;k<5;k++){const value=lo+(hi-lo)*k/4;node("line",{x1:55,y1:y(value),x2:685,y2:y(value),stroke:"#34405a","stroke-width":1});node("text",{x:8,y:y(value)+4,fill:"#91a0b9","font-size":12},value.toFixed(0))}node("polyline",{points:values.map((v,i)=>x(i)+","+y(v)).join(" "),fill:"none",stroke:"#68c9eb","stroke-width":3,"stroke-linejoin":"round","stroke-linecap":"round"});node("text",{x:55,y:250,fill:"#91a0b9","font-size":12},rows[0].month);node("text",{x:625,y:250,fill:"#91a0b9","font-size":12},rows[rows.length-1].month);el("etf-chart-status").textContent=fund+": "+rows.length+" monthly observations | normalized start 100 | latest "+values[values.length-1].toFixed(1)+" | price/adjustment basis varies by data availability."}
async function loadEtfHistory(){try{etfHistory=await read("research/etf_history.csv");drawEtf()}catch(e){el("etf-chart-status").textContent="Waiting for first ETF Historical Research workflow run."}}el("etf-chart-fund")?.addEventListener("change",drawEtf);loadEtfHistory();

function quarterlyLab(){const body=el("qt-rows");if(!body)return;const ids=["qt-start","qt-q1","qt-q2","qt-q3","qt-q4"],values=ids.map(id=>Number(el(id).value));body.replaceChildren();if(values.some(v=>!Number.isFinite(v)||v<=0)){el("qt-summary").textContent="Enter positive prices for all five values.";return}const labels=["Accumulation (hypothesis)","Manipulation / deviation (hypothesis)","Distribution / directional move (hypothesis)","Continuation or reversal (hypothesis)"];for(let i=1;i<=4;i++){const pct=(values[i]/values[i-1]-1)*100,tr=document.createElement("tr");for(const v of ["Q"+i,labels[i-1],(pct>=0?"+":"")+pct.toFixed(2)+"%"]){const td=document.createElement("td");td.textContent=v;tr.appendChild(td)}body.appendChild(tr)}const total=(values[4]/values[0]-1)*100;el("qt-summary").textContent="Hypothetical "+el("qt-timeframe").value+" cycle: "+(total>=0?"+":"")+total.toFixed(2)+"% from start to finish. Four blocks are displayed regardless of the actual price path; this does not validate the theory."}for(const id of ["qt-timeframe","qt-start","qt-q1","qt-q2","qt-q3","qt-q4"])el(id)?.addEventListener("input",quarterlyLab);quarterlyLab();

// Stock research: descriptive interpretation of the existing saved snapshot.
async function interpretStock(){const root=el("indicator-interpretations");if(!root)return;root.replaceChildren();let rows;try{rows=await read("paper/chart_analysis.csv")}catch(e){root.textContent="Saved stock analysis is not available yet.";return}const ticker=el("ticker-select")?.value||"AAPL",r=rows.find(x=>x.ticker===ticker);if(!r){root.textContent="No saved analysis for "+ticker;return}const num=k=>r[k]!==""&&r[k]!=null&&Number.isFinite(Number(r[k]))?Number(r[k]):null;const entries=[];const rsi=num("rsi14");entries.push(["RSI (14)",rsi===null?"Unavailable in this snapshot.":rsi<30?"RSI "+rsi.toFixed(1)+": below the conventional 30 threshold; a downtrend can persist.":rsi>70?"RSI "+rsi.toFixed(1)+": above the conventional 70 threshold; strength can persist.":"RSI "+rsi.toFixed(1)+": between conventional 30 and 70 thresholds."]);const macd=num("macd");entries.push(["MACD",macd===null?"Unavailable. MACD alone is not a crossover signal.":"MACD "+macd.toFixed(3)+": "+(macd>0?"positive":macd<0?"negative":"near zero")+"; without a signal-line value, no crossover can be established."]);const close=num("close"),sup=num("support_20d"),res=num("resistance_20d");entries.push(["20-session range",close===null||sup===null||res===null?"Price or range values unavailable.":"Last analyzed close "+close.toFixed(2)+"; support "+sup.toFixed(2)+", resistance "+res.toFixed(2)+". "+(close<sup?"Below the recorded support level.":close>res?"Above the recorded resistance level.":"Within the recorded range.")+" These historical boundaries are not guaranteed."]);const vol=num("volume_vs_20d");entries.push(["Volume",vol===null?"Volume comparison unavailable.":"Volume was "+vol.toFixed(2)+"× the 20-session average ("+(vol>1.5?"unusually elevated":vol<.7?"relatively subdued":"near its typical range")+")."]);entries.push(["Trend label",r.trend?"Saved trend classification: "+r.trend+". Momentum label: "+(r.momentum||"unavailable")+". These are descriptive model labels, not verified outcomes.":"Trend classification unavailable."]);for(const [title,description] of entries){const box=document.createElement("div");box.className="stat";const label=document.createElement("strong");label.textContent=title;const detail=document.createElement("span");detail.className="small muted";detail.style.maxWidth="72%";detail.style.textAlign="right";detail.textContent=description;box.append(label,detail);root.appendChild(box)}}
el("ticker-select")?.addEventListener("change",interpretStock);interpretStock();

let stockHistory=[];
function drawStockHistory(){const svg=el("stock-history-chart");if(!svg)return;svg.replaceChildren();const ticker=el("stock-history-ticker").value;const rows=stockHistory.filter(r=>r.ticker===ticker&&Number(r.close)>0).sort((a,b)=>a.date.localeCompare(b.date));if(rows.length<60){el("stock-history-status").textContent="No sufficient daily history for "+ticker+". Run Stock Historical Research in GitHub Actions.";for(const id of ["stock-test-return","stock-test-hold","stock-test-drawdown","stock-test-trades"])el(id).textContent="—";return}const closes=rows.map(r=>Number(r.close));const sma=(i,n)=>i+1<n?null:closes.slice(i+1-n,i+1).reduce((a,b)=>a+b,0)/n;const a20=closes.map((_,i)=>sma(i,20)),a50=closes.map((_,i)=>sma(i,50));const all=[...closes,...a20.filter(Number.isFinite),...a50.filter(Number.isFinite)],lo=Math.min(...all)*.97,hi=Math.max(...all)*1.03;const X=i=>55+i*670/(rows.length-1),Y=v=>235-(v-lo)*190/(hi-lo),ns="http://www.w3.org/2000/svg";function node(tag,attrs,content){const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);if(content!==undefined)e.textContent=content;svg.appendChild(e)}for(let k=0;k<5;k++){const v=lo+(hi-lo)*k/4;node("line",{x1:55,y1:Y(v),x2:725,y2:Y(v),stroke:"#334155"});node("text",{x:5,y:Y(v)+4,fill:"#94a3b8","font-size":11},v.toFixed(0))}function line(vals,color){node("polyline",{points:vals.map((v,i)=>v===null?"":X(i)+","+Y(v)).filter(Boolean).join(" "),stroke:color,fill:"none","stroke-width":2})}line(closes,"#e8eefc");line(a20,"#67d8b6");line(a50,"#f0b76b");node("text",{x:55,y:261,fill:"#a4b4d0","font-size":12},rows[0].date);node("text",{x:630,y:261,fill:"#a4b4d0","font-size":12},rows[rows.length-1].date);let equity=1,peak=1,maxDD=0,transitions=0,previous=0;for(let i=51;i<closes.length;i++){const position=a20[i-2]>a50[i-2]?1:0;if(position!==previous)transitions++;previous=position;equity*=1+position*(closes[i]/closes[i-1]-1);peak=Math.max(peak,equity);maxDD=Math.max(maxDD,1-equity/peak)}const base=closes[50],hold=closes[closes.length-1]/base-1;el("stock-test-return").textContent=((equity-1)*100).toFixed(1)+"%";el("stock-test-hold").textContent=(hold*100).toFixed(1)+"%";el("stock-test-drawdown").textContent=(maxDD*100).toFixed(1)+"%";el("stock-test-trades").textContent=String(transitions);el("stock-history-status").textContent=ticker+": "+rows.length+" sessions, "+rows[0].date+" to "+rows[rows.length-1].date+" | White: close, green: SMA20, orange: SMA50. No fees, dividends, or slippage."}
async function loadStockHistory(){try{stockHistory=await read("research/stock_history.csv");drawStockHistory()}catch(e){el("stock-history-status").textContent="Waiting for stock history workflow to create its first snapshot."}}el("stock-history-ticker")?.addEventListener("change",drawStockHistory);loadStockHistory();

let cryptoRisk=[];
function renderCryptoRisk(){const body=el("crypto-risk-rows");if(!body)return;body.replaceChildren();const minimum=Number(el("crypto-min-liquidity").value),filtered=cryptoRisk.filter(r=>r.liquidity_usd!==""&&Number.isFinite(Number(r.liquidity_usd))&&Number(r.liquidity_usd)>=minimum);for(const r of filtered.slice(0,40)){const liq=Number(r.liquidity_usd),vol=r.volume_24h_usd!==""?Number(r.volume_24h_usd):NaN,change=r.price_change_24h_pct!==""?Number(r.price_change_24h_pct):NaN;const ratio=Number.isFinite(vol)&&liq>0?(vol/liq).toFixed(2)+"×":"Unknown";const tr=document.createElement("tr");for(const value of [r.symbol||"Unnamed",usd(liq),Number.isFinite(change)?change.toFixed(1)+"%":"Unknown",ratio,(r.research_flags||"Unverified").replaceAll("|",", ")]){const td=document.createElement("td");td.textContent=value;tr.appendChild(td)}body.appendChild(tr)}const missing=cryptoRisk.filter(r=>r.liquidity_usd===""||!Number.isFinite(Number(r.liquidity_usd))).length;el("crypto-risk-status").textContent=filtered.length+" of "+cryptoRisk.length+" observations with reported liquidity meet this filter; "+missing+" have missing liquidity and are excluded. Data as of "+(cryptoRisk[0]?.observed_utc||"unknown")+". Not a token recommendation."}
async function loadCryptoRisk(){try{cryptoRisk=await read("crypto_paper/discovered_tokens.csv");renderCryptoRisk()}catch(e){el("crypto-risk-status").textContent="Crypto snapshot unavailable."}}el("crypto-min-liquidity")?.addEventListener("change",renderCryptoRisk);loadCryptoRisk();


let screenerData=[];
function renderScreener(){
 const body=el("screener-rows"),status=el("screener-status");if(!body||!status)return;
 body.replaceChildren();
 const trend=el("screener-trend").value,minScore=Number(el("screener-score").value),rsiMode=el("screener-rsi").value;
 const num=x=>x===undefined||x===null||String(x).trim()===""?NaN:Number(x);
 const rows=screenerData.filter(r=>{
  const t=String(r.trend||"").toLowerCase(),score=num(r.evidence_score),rsi=num(r.rsi14);
  if(trend==="bull"&&!/(up|bull|positive)/.test(t))return false;
  if(trend==="bear"&&!/(down|bear|negative)/.test(t))return false;
  if(minScore&&(!Number.isFinite(score)||score<minScore))return false;
  if(rsiMode!=="all"&&(!Number.isFinite(rsi)||(rsiMode==="low"&&rsi>=30)||(rsiMode==="mid"&&(rsi<30||rsi>70))||(rsiMode==="high"&&rsi<=70)))return false;
  return true;
 }).sort((a,b)=>(num(b.evidence_score)||0)-(num(a.evidence_score)||0));
 for(const r of rows){
  const tr=document.createElement("tr");
  const cells=[r.ticker||"—",r.date||"—",Number.isFinite(num(r.close))?usd(num(r.close)):"—",r.trend||"—",Number.isFinite(num(r.rsi14))?num(r.rsi14).toFixed(1):"—",Number.isFinite(num(r.volume_vs_20d))?num(r.volume_vs_20d).toFixed(2)+"×":"—",Number.isFinite(num(r.evidence_score))?num(r.evidence_score).toFixed(0)+"/100":"—"];
  for(const value of cells){const td=document.createElement("td");td.textContent=value;tr.appendChild(td)}
  body.appendChild(tr);
 }
 if(!rows.length){const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=7;td.textContent="No saved observations match these filters.";tr.appendChild(td);body.appendChild(tr)}
 const dates=screenerData.map(r=>r.date).filter(Boolean).sort();
 status.textContent=rows.length+" of "+screenerData.length+" saved observations match. Latest recorded session: "+(dates.at(-1)||"unknown")+". Not live market data.";
}
async function loadScreener(){try{const rows=await read("paper/chart_analysis.csv");const latest=new Map();for(const r of rows){if(!r.ticker)continue;const old=latest.get(r.ticker);if(!old||String(r.date||"")>String(old.date||""))latest.set(r.ticker,r)}screenerData=[...latest.values()];renderScreener()}catch(e){const s=el("screener-status");if(s)s.textContent="Saved stock analysis is currently unavailable."}}
for(const id of ["screener-trend","screener-score","screener-rsi"])el(id)?.addEventListener("change",renderScreener);
loadScreener();


let markerHistory=[];
function renderPaperMarkers(){
 const ticker=el("paper-marker-ticker")?.value,svg=el("paper-marker-chart"),body=el("paper-marker-rows"),status=el("paper-marker-status");if(!svg||!body||!status)return;
 svg.replaceChildren();body.replaceChildren();
 const rows=markerHistory.filter(r=>r.ticker===ticker).sort((a,b)=>a.date.localeCompare(b.date));
 if(rows.length<55){status.textContent="Not enough historical observations for this simulation.";return}
 const closes=rows.map(r=>Number(r.close)),avg=(i,n)=>{if(i<n-1)return NaN;let sum=0;for(let j=i-n+1;j<=i;j++)sum+=closes[j];return sum/n};
 const sma20=closes.map((_,i)=>avg(i,20)),sma50=closes.map((_,i)=>avg(i,50));
 const trades=[];let previous=false;
 for(let i=51;i<rows.length;i++){const holding=sma20[i-2]>sma50[i-2];if(holding!==previous){trades.push({i,action:holding?"BUY":"SELL",date:rows[i].date,close:closes[i]});previous=holding}}
 const W=760,H=260,pad=32,min=Math.min(...closes),max=Math.max(...closes),range=Math.max(max-min,0.01),x=i=>pad+(W-2*pad)*i/(rows.length-1),y=v=>H-pad-(H-2*pad)*(v-min)/range;
 const ns="http://www.w3.org/2000/svg",node=(tag,attrs)=>{const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));svg.appendChild(n);return n};
 node("polyline",{points:closes.map((v,i)=>x(i).toFixed(1)+","+y(v).toFixed(1)).join(" "),fill:"none",stroke:"#dce7ff","stroke-width":1.7});
 for(const t of trades){const buy=t.action==="BUY",color=buy?"#48d6a1":"#ff9b75",cy=y(t.close);node("line",{x1:x(t.i),y1:cy+(buy?10:-10),x2:x(t.i),y2:cy+(buy?23:-23),stroke:color,"stroke-width":2});node("circle",{cx:x(t.i),cy,r:5,fill:color});const title=document.createElementNS(ns,"title");title.textContent=t.date+" simulated "+t.action+" at "+usd(t.close);svg.lastChild.appendChild(title)}
 const shown=trades.slice(-30).reverse();for(const t of shown){const tr=document.createElement("tr");for(const value of [t.date,ticker,t.action,usd(t.close)]){const td=document.createElement("td");td.textContent=value;tr.appendChild(td)}body.appendChild(tr)}
 if(!trades.length){const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=4;td.textContent="No position changes in this sample.";tr.appendChild(td);body.appendChild(tr)}
 status.textContent=ticker+": "+rows.length+" historical sessions; "+trades.length+" simulated transitions. Green dots = BUY, orange dots = SELL. Showing the latest "+shown.length+" log entries. These are model signals, not broker executions.";
}
async function loadPaperMarkers(){try{markerHistory=await read("research/stock_history.csv");renderPaperMarkers()}catch(e){const s=el("paper-marker-status");if(s)s.textContent="Historical paper marker data unavailable."}}
el("paper-marker-ticker")?.addEventListener("change",renderPaperMarkers);loadPaperMarkers();


let activitySignals=[],activityJournal=[],watchRows=[];
const activityNumber=x=>x===undefined||x===null||String(x).trim()===""?NaN:Number(x);
const activityCell=(tr,v)=>{const td=document.createElement("td");td.textContent=String(v??"—");tr.appendChild(td)};
function activityTable(id,rows){const body=el(id);if(!body)return;body.replaceChildren();for(const values of rows){const tr=document.createElement("tr");for(const v of values)activityCell(tr,v);body.appendChild(tr)}if(!rows.length){const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=id==="activity-journal-rows"?5:4;td.textContent="No recorded entries.";tr.appendChild(td);body.appendChild(tr)}}
function renderActivity(){
 const signals=[...activitySignals].sort((a,b)=>String(b.date_utc).localeCompare(String(a.date_utc)));
 const newest=signals[0]?.date_utc||"—";el("activity-date").textContent=newest;el("activity-freshness").textContent="Latest saved session (not real time)";
 activityTable("activity-signal-rows",signals.map(r=>[r.ticker,r.signal,Number.isFinite(activityNumber(r.close))?usd(Number(r.close)):"—",r.date_utc]));
 el("activity-signal-status").textContent=signals.length+" latest saved observations. A signal is not a trade.";
 const journal=[...activityJournal].sort((a,b)=>String(b.date_utc).localeCompare(String(a.date_utc)));
 activityTable("activity-journal-rows",journal.slice(0,30).map(r=>[r.date_utc,r.ticker,r.action,Number.isFinite(activityNumber(r.price))?usd(Number(r.price)):"—",Number.isFinite(activityNumber(r.shares))?Number(r.shares).toFixed(3):"—"]));
 el("activity-count").textContent=String(journal.length);
 el("activity-journal-status").textContent="Showing "+Math.min(journal.length,30)+" of "+journal.length+" recorded simulated orders. No real broker connection.";
 const lots=new Map();let winners=0,completed=0,realized=0,unmatched=0;
 for(const r of [...activityJournal].sort((a,b)=>String(a.date_utc).localeCompare(String(b.date_utc)))){
  const p=activityNumber(r.price),q=activityNumber(r.shares),ticker=r.ticker;if(!ticker||!Number.isFinite(p)||!Number.isFinite(q)||q<=0||p<=0)continue;
  if(r.action==="SIM_BUY"){if(!lots.has(ticker))lots.set(ticker,[]);lots.get(ticker).push({p,q})}
  if(r.action==="SIM_SELL"){let remaining=q;const queue=lots.get(ticker)||[];while(remaining>1e-8&&queue.length){const lot=queue[0],used=Math.min(remaining,lot.q),pnl=(p-lot.p)*used;realized+=pnl;completed++;if(pnl>0)winners++;lot.q-=used;remaining-=used;if(lot.q<1e-8)queue.shift()}if(remaining>1e-8)unmatched++}
 }
 el("activity-winrate").textContent=completed?(100*winners/completed).toFixed(1)+"%":"—";
 el("activity-average").textContent=completed?usd(realized/completed):"—";
 if(unmatched)el("activity-journal-status").textContent+=" "+unmatched+" unmatched sells; analytics may be incomplete.";
}
function renderWatch(){
 const body=el("watch-alert-rows"),status=el("watch-alert-status");if(!body||!status)return;
 body.replaceChildren();const score=Number(el("watch-score").value),trend=el("watch-trend").value,maxRsi=Number(el("watch-rsi").value);
 const latest=new Map();for(const r of watchRows){const old=latest.get(r.ticker);if(r.ticker&&(!old||String(r.market_session||r.date||"")>String(old.market_session||old.date||"")))latest.set(r.ticker,r)}
 const matching=[...latest.values()].filter(r=>{const s=activityNumber(r.evidence_score),rsi=activityNumber(r.rsi14);return Number.isFinite(s)&&s>=score&&Number.isFinite(rsi)&&rsi<=maxRsi&&(trend==="ALL"||String(r.trend||"").toUpperCase()===trend)});
 for(const r of matching){const tr=document.createElement("tr");for(const v of [r.ticker,r.trend,Number(r.rsi14).toFixed(1),Number(r.evidence_score).toFixed(0)+"/100",r.market_session||r.date||"—"])activityCell(tr,v);body.appendChild(tr)}
 if(!matching.length){const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=5;td.textContent="No saved stocks currently match your research filters.";tr.appendChild(td);body.appendChild(tr)}
 const dates=[...latest.values()].map(r=>r.market_session||r.date).filter(Boolean).sort();status.textContent=matching.length+" of "+latest.size+" stocks match based on the saved session "+(dates.at(-1)||"unknown")+". These are on-page research alerts, not notifications or buy instructions.";
}
async function loadActivity(){
 const tasks=await Promise.allSettled([read("paper/latest_signals.csv"),read("paper/journal.csv"),read("paper/chart_analysis.csv")]);
 if(tasks[0].status==="fulfilled")activitySignals=tasks[0].value;else el("activity-signal-status").textContent="Signals unavailable.";
 if(tasks[1].status==="fulfilled")activityJournal=tasks[1].value;else el("activity-journal-status").textContent="Paper journal unavailable.";
 if(tasks[2].status==="fulfilled")watchRows=tasks[2].value;else el("watch-alert-status").textContent="Indicator research unavailable.";
 if(tasks[0].status==="fulfilled"&&tasks[1].status==="fulfilled")renderActivity();
 if(tasks[2].status==="fulfilled")renderWatch();
}
for(const id of ["watch-score","watch-trend","watch-rsi"])el(id)?.addEventListener("change",renderWatch);
el("activity-refresh")?.addEventListener("click",loadActivity);
loadActivity();


function updateTradingViewSymbol(){
 const ticker=el("tradingview-ticker")?.value,frame=el("tradingview-frame");if(!ticker||!frame)return;
 const url=new URL(frame.getAttribute("src"),location.href);url.searchParams.set("symbol",ticker);frame.src=url.toString();
 const paper=el("paper-marker-ticker");if(paper){paper.value=ticker.split(":").at(-1);renderPaperMarkers()}
}
el("tradingview-ticker")?.addEventListener("change",updateTradingViewSymbol);


async function cryptoHealth(){
 const get=id=>el(id),findings=[],rows=get("crypto-health-trade-rows");if(!rows)return;
 try{
  const [perf,journal,signals]=await Promise.all([read("crypto_paper/performance.csv"),read("crypto_paper/journal.csv"),read("crypto_paper/latest_signals.csv")]);
  const values=perf.map(r=>Number(r.paper_value)).filter(n=>Number.isFinite(n)&&n>0),first=values[0],last=values.at(-1);
  get("crypto-health-return").textContent=first&&last?((last/first-1)*100).toFixed(2)+"%":"—";
  let peak=0,dd=0;for(const v of values){peak=Math.max(peak,v);if(peak>0)dd=Math.max(dd,100*(peak-v)/peak)}
  get("crypto-health-dd").textContent=dd.toFixed(2)+"%";
  get("crypto-health-asof").textContent="Last saved portfolio session: "+(perf.at(-1)?.date_utc||"unknown")+". Historical snapshots, not live prices.";
  const flags=signals.filter(r=>r.signal==="NO_DATA"||!Number.isFinite(Number(r.close))||Number(r.close)<=0);
  get("crypto-health-flags").textContent=String(flags.length);
  if(flags.length)findings.push("Missing or invalid latest prices: "+flags.map(r=>r.ticker).join(", ")+". Inspect data availability; do not treat missing data as a sell signal.");
  const queues=new Map(),closed=[];let unmatched=0;
  for(const r of journal){const ticker=r.ticker,price=Number(r.price),qty=Number(r.units);if(!ticker||!Number.isFinite(price)||price<=0||!Number.isFinite(qty)||qty<=0)continue;
   if(r.action==="SIM_BUY"){if(!queues.has(ticker))queues.set(ticker,[]);queues.get(ticker).push({price,qty,date:r.date_utc})}
   else if(r.action==="SIM_SELL"){let left=qty;const q=queues.get(ticker)||[];while(left>1e-7&&q.length){const lot=q[0],taken=Math.min(left,lot.qty);closed.push({ticker,entry:lot.date,exit:r.date_utc,ret:100*(price/lot.price-1),reason:r.reason||"—",pnl:(price-lot.price)*taken});lot.qty-=taken;left-=taken;if(lot.qty<1e-7)q.shift()}if(left>1e-7)unmatched++}
  }
  get("crypto-health-trades").textContent=String(closed.length);rows.replaceChildren();
  for(const r of closed.slice(-20).reverse()){const tr=document.createElement("tr");for(const v of [r.ticker,r.entry,r.exit,r.ret.toFixed(2)+"%",r.reason]){const td=document.createElement("td");td.textContent=v;tr.appendChild(td)}rows.appendChild(tr)}
  if(!closed.length){const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=5;td.textContent="No matched completed trades.";tr.appendChild(td);rows.appendChild(tr)}
  const losers=closed.filter(r=>r.pnl<0),wins=closed.filter(r=>r.pnl>0);
  if(closed.length)findings.push(wins.length+" profitable and "+losers.length+" losing matched paper trades; win rate "+(100*wins.length/closed.length).toFixed(1)+"%. This small sample cannot establish predictive performance.");
  if(losers.length)findings.push("Largest recorded losing close: "+[...losers].sort((a,b)=>a.pnl-b.pnl)[0].ticker+" ("+usd([...losers].sort((a,b)=>a.pnl-b.pnl)[0].pnl)+"). Review entry and exit timing against market conditions.");
  if(journal.some(r=>String(r.reason).includes("missing_signal")))findings.push("Some exits are labeled defensive_or_missing_signal: the journal cannot distinguish market weakness from missing data. Separate these reasons in future logging.");
  if(unmatched)findings.push(unmatched+" unmatched sell records. Review journal completeness.");
  if(dd>2)findings.push("Recorded drawdown exceeds 2%. Compare against a cash baseline and a buy-and-hold benchmark before concluding whether the strategy helps.");
  findings.push("Research checks to prioritize: transaction fees and slippage, no-look-ahead backtesting, out-of-sample validation, and price-data quality. No rule changes were made to the trading engine.");
  const host=get("crypto-health-findings");host.replaceChildren();const ul=document.createElement("ul");for(const message of findings){const li=document.createElement("li");li.textContent=message;ul.appendChild(li)}host.appendChild(ul);
 }catch(e){get("crypto-health-findings").textContent="Unable to load crypto diagnostic snapshots: "+e.message}
}
cryptoHealth();


let weeklySummary="";
async function loadWeeklyReport(){
 const get=id=>el(id),currency=n=>(n<0?"−":"+")+usd(Math.abs(n));
 try{
 const [performance,journal]=await Promise.all([read("paper/performance.csv"),read("paper/journal.csv")]);
 const rows=performance.filter(r=>Number.isFinite(Number(r.paper_value))&&Number(r.paper_value)>0&&/^\d{4}-\d{2}-\d{2}$/.test(r.date_utc)).sort((a,b)=>a.date_utc.localeCompare(b.date_utc));
 if(!rows.length)throw Error("No valid portfolio history.");
 const starting=10000,weekKey=date=>{const d=new Date(date+"T00:00:00Z");d.setUTCDate(d.getUTCDate()-(d.getUTCDay()+6)%7);return d.toISOString().slice(0,10)};
 const weeks=new Map();for(const r of rows){const key=weekKey(r.date_utc);if(!weeks.has(key))weeks.set(key,{key,sessions:0,last:starting});const w=weeks.get(key);w.sessions++;w.last=Number(r.paper_value)}
 let previous=starting;for(const w of weeks.values()){w.change=w.last-previous;previous=w.last;w.realized=0}
 const lots=new Map();let realized=0,unmatched=0;
 for(const r of [...journal].sort((a,b)=>String(a.date_utc).localeCompare(String(b.date_utc)))){
 const qty=Number(r.shares),price=Number(r.price);if(!r.ticker||!Number.isFinite(qty)||qty<=0||!Number.isFinite(price)||price<=0)continue;
 if(r.action==="SIM_BUY"){if(!lots.has(r.ticker))lots.set(r.ticker,[]);lots.get(r.ticker).push({qty,price})}
 if(r.action==="SIM_SELL"){let remaining=qty;const queue=lots.get(r.ticker)||[];while(remaining>1e-8&&queue.length){const lot=queue[0],used=Math.min(lot.qty,remaining),profit=(price-lot.price)*used;realized+=profit;const w=weeks.get(weekKey(r.date_utc));if(w)w.realized+=profit;lot.qty-=used;remaining-=used;if(lot.qty<1e-8)queue.shift()}if(remaining>1e-8)unmatched++}
 }
 const series=[...weeks.values()],total=rows.at(-1).paper_value-starting,average=total/series.length,positive=series.filter(w=>w.change>0).length;
 get("weekly-average").textContent=currency(average);get("weekly-period").textContent="Across "+series.length+" recorded calendar weeks";
 get("weekly-total").textContent=currency(total);get("weekly-total-pct").textContent=(total/starting*100).toFixed(2)+"% from $10,000 simulated starting capital";
 get("weekly-positive").textContent=positive+" / "+series.length;
 get("weekly-realized").textContent=currency(realized);
 const body=get("weekly-rows"),bars=get("weekly-bars");body.replaceChildren();bars.replaceChildren();
 const max=Math.max(1,...series.map(w=>Math.abs(w.change)));
 for(const w of [...series].reverse()){
 const tr=document.createElement("tr");for(const value of [w.key,w.sessions,currency(w.change),currency(w.realized),usd(w.last)]){const td=document.createElement("td");td.textContent=String(value);tr.appendChild(td)}body.appendChild(tr);
 const line=document.createElement("div");line.style.cssText="display:grid;grid-template-columns:86px minmax(0,1fr) 90px;gap:10px;align-items:center;font-size:12px";
 const label=document.createElement("span");label.textContent=w.key.slice(5);const track=document.createElement("div");track.style.cssText="background:#261822;border-radius:7px;overflow:hidden;height:14px";const fill=document.createElement("div");fill.style.cssText="height:100%;border-radius:7px;background:"+(w.change>=0?"#d9a1bc":"#a45c76")+";width:"+Math.max(1,100*Math.abs(w.change)/max).toFixed(2)+"%";track.appendChild(fill);const amount=document.createElement("span");amount.textContent=currency(w.change);amount.style.textAlign="right";line.append(label,track,amount);bars.appendChild(line)
 }
 const first=rows[0].date_utc,last=rows.at(-1).date_utc;
 get("weekly-notes").textContent="Recorded sessions: "+first+" to "+last+". Weeks with missing sessions are not filled in. Portfolio changes include unrealized P/L and may not equal closed-trade profits. Realized P/L excludes fees, slippage, and taxes."+(unmatched?" "+unmatched+" unmatched sell record(s); realized total may be incomplete.":"");
 weeklySummary="Kaitlyn's Trading — simulated stock results ("+first+" to "+last+"): Starting portfolio $10,000; latest "+usd(Number(rows.at(-1).paper_value))+"; total "+currency(total)+" ("+(total/starting*100).toFixed(2)+"%); average recorded calendar week "+currency(average)+" over "+series.length+" weeks; "+positive+" profitable weeks; realized completed-sale P/L "+currency(realized)+" before costs. Paper trading only; weekly portfolio changes include unrealized P/L and are not guaranteed income.";
 }catch(e){get("weekly-notes").textContent="Weekly report unavailable: "+e.message}
}
getWeeklyCopy();
function getWeeklyCopy(){el("weekly-copy")?.addEventListener("click",async()=>{const status=el("weekly-copy-status");if(!weeklySummary){status.textContent="Report not ready.";return}try{await navigator.clipboard.writeText(weeklySummary);status.textContent="Summary copied."}catch(e){status.textContent="Copy unavailable in this browser."}})}
loadWeeklyReport();


async function benchmarkResearch(){
 const host=el("benchmark-rows");if(!host)return;
 try{
 const [data,missing]=await Promise.all([read("strategy_comparison_results.csv"),read("strategy_comparison_missing.csv")]);
 const valid=data.filter(r=>Number.isFinite(Number(r.buy_hold_return_pct))&&Number.isFinite(Number(r.trend_return_pct)));
 el("benchmark-count").textContent=String(valid.length);
 const beats=valid.filter(r=>Number(r.trend_return_pct)>Number(r.buy_hold_return_pct)).length;
 el("benchmark-beats").textContent=beats+" / "+valid.length;
 el("benchmark-date").textContent=valid.reduce((a,r)=>r.as_of>a?r.as_of:a,"")||"—";
 host.replaceChildren();
 for(const r of valid){const tr=document.createElement("tr");const diff=Number(r.trend_return_pct)-Number(r.buy_hold_return_pct);for(const value of [r.asset,Number(r.buy_hold_return_pct).toFixed(2)+"%",Number(r.trend_return_pct).toFixed(2)+"%",Number(r.momentum_return_pct).toFixed(2)+"%",(diff>=0?"+":"")+diff.toFixed(2)+" pp",Number(r.trend_max_drawdown_pct).toFixed(2)+"%"]){const td=document.createElement("td");td.textContent=value;tr.appendChild(td)}host.appendChild(tr)}
 const unavailable=missing.filter(r=>r.asset);
 el("benchmark-notes").textContent="Source: saved strategy_comparison_results.csv. Hypothetical per-asset tests, not the actual paper bot; signals are delayed one session, with estimated fees and slippage. These results do not establish out-of-sample profitability."+(unavailable.length?" Unavailable assets: "+unavailable.map(r=>r.asset).join(", ")+".":"");
 }catch(e){el("benchmark-notes").textContent="Benchmark comparison unavailable: "+e.message}
}
benchmarkResearch();

})();
