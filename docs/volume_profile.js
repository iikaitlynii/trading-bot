/* Offline educational display. Never creates strategy candidates or execution intent. */
(()=>{
'use strict';
const root=document.getElementById('volume-profile');if(!root)return;
const el=id=>document.getElementById('vp-'+id);let report;
function clear(message){el('status').textContent=message;el('metrics').replaceChildren();el('chart').replaceChildren();el('provenance').textContent='';}
function render(){
 clear('Loading selected historical research…');
 try{
 const p=report.profiles.find(p=>p.symbol===el('symbol').value&&p.window===Number(el('window').value)&&p.bin_count===Number(el('bins').value));
 if(!p||p.status!=='AVAILABLE')throw Error(p?.error||'Selected profile unavailable');
 if(p.method!=='uniform_low_high_candle_approximation_v1'||!Array.isArray(p.bins)||p.bins.length!==p.bin_count||!['poc','vah','val','total_volume'].every(k=>Number.isFinite(p[k])&&p[k]>0)||p.bins.some(b=>!['low','high','volume'].every(k=>Number.isFinite(b[k]))||b.volume<0||b.high<=b.low))throw Error('Invalid saved profile');
 if(!['hvn','lvn'].every(k=>Array.isArray(p[k])&&p[k].every(v=>Number.isFinite(v)&&v>0))||!Number.isFinite(p.value_area_achieved)||p.value_area_achieved<=0||p.value_area_achieved>1||p.bins.every(b=>b.volume===0))throw Error('Invalid saved levels or volume');
 const fmt=n=>n.toFixed(2);
 el('status').textContent='HISTORICAL · APPROXIMATE · UNVALIDATED'+' · '+p.start+' through '+p.end+' · '+p.sessions+' completed daily sessions';
 for(const [name,value] of [['POC',fmt(p.poc)],['VAH',fmt(p.vah)],['VAL',fmt(p.val)],['HVN',p.hvn.map(fmt).join(', ')||'None under this definition'],['LVN',p.lvn.map(fmt).join(', ')||'None under this definition']]){
 const line=document.createElement('p');line.textContent=name+' (approx.): '+value;el('metrics').append(line);
 }
 const max=Math.max(...p.bins.map(b=>b.volume));
 for(const b of [...p.bins].reverse()){
 const row=document.createElement('div');row.className='vp-row';
 const label=document.createElement('span');label.textContent=fmt(b.low)+'–'+fmt(b.high);
 const track=document.createElement('div');track.className='vp-track';const bar=document.createElement('div');bar.className='vp-bar';bar.style.width=(b.volume/max*100)+'%';bar.style.background=b.poc?'#f5c76c':b.value_area?'#d48ab2':'#879bb5';track.append(bar);
 const volume=document.createElement('span');volume.textContent='≈ '+Math.round(b.volume).toLocaleString()+(b.poc?' POC':'')+(b.hvn?' HVN':'')+(b.lvn?' LVN':'');row.append(label,track,volume);el('chart').append(row);
 }
 el('provenance').textContent=report.source_basis+' · Source: '+report.source+' · SHA-256: '+report.source_sha256+' · Value area achieved: '+(p.value_area_achieved*100).toFixed(1)+'% (target 70%). Retrieval time unknown; this is a saved historical window, not current market health.';
 }catch(error){clear('FAILED — '+error.message+'; no profile displayed.');}
}
for(const id of ['symbol','window','bins'])el(id).addEventListener('change',()=>{if(report)render()});
fetch('volume-profile/report.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(data=>{if(data.schema_version!==1||!Array.isArray(data.profiles))throw Error('Invalid report schema');report=data;render()}).catch(error=>clear('FAILED — Volume Profile report unavailable or invalid: '+error.message));
})();
