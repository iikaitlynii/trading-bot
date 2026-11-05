/* Public observations + private, memory-only screenshot inspection. No upload requests. */
(function(root) {
'use strict';
function imageHeader(bytes, type, size) {
  if(size <= 0 || size > 5*1024*1024) throw Error('Choose an image no larger than 5 MiB');
  const same = a=>a.every((v,i)=>bytes[i]===v);
  const png=same([137,80,78,71,13,10,26,10]), jpeg=same([255,216,255]);
  const webp=same([82,73,70,70]) && [87,69,66,80].every((v,i)=>bytes[i+8]===v);
  if(!((type==='image/png'&&png)||(type==='image/jpeg'&&jpeg)||(type==='image/webp'&&webp))) throw Error('Unsupported image; PNG, JPEG or WebP bytes must match the file type');
}
function imageDimensions(bytes, type) {
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  let width=0,height=0;
  if(type==='image/png' && bytes.length>=24){width=view.getUint32(16);height=view.getUint32(20);}
  if(type==='image/jpeg'){
    let i=2;
    while(i+9<bytes.length){
      if(bytes[i++]!==255)break;
      while(bytes[i]===255)i++;
      const marker=bytes[i++];
      if(marker===217||marker===218)break;
      if(marker===1||(marker>=208&&marker<=215))continue;
      if(i+2>bytes.length)break;
      const length=view.getUint16(i);
      if(length<2||i+length>bytes.length)break;
      if([192,193,194,195,197,198,199,201,202,203,205,206,207].includes(marker)){
        height=view.getUint16(i+3);width=view.getUint16(i+5);break;
      }
      i+=length;
    }
  }
  if(type==='image/webp' && bytes.length>=30){
    const kind=String.fromCharCode(...bytes.slice(12,16));
    if(kind==='VP8X'){
      width=1+bytes[24]+256*bytes[25]+65536*bytes[26];height=1+bytes[27]+256*bytes[28]+65536*bytes[29];
    }else if(kind==='VP8 ' && bytes[23]===157&&bytes[24]===1&&bytes[25]===42){
      width=view.getUint16(26,true)&16383;height=view.getUint16(28,true)&16383;
    }else if(kind==='VP8L'&&bytes[20]===47){
      width=1+bytes[21]+((bytes[22]&63)<<8);height=1+(bytes[22]>>6)+(bytes[23]<<2)+((bytes[24]&15)<<10);
    }
  }
  if(width<320||height<180||width>8192||height>8192||width*height>16000000)throw Error('Ambiguous or unsupported image dimensions; use a readable chart up to 16 megapixels');
  return {width,height};
}
async function verifiedRecord(index, bytes) {
  if(index?.schema_version!==1 || !/^[a-f0-9]{64}$/.test(index.sha256||'') || index.path!==`observations/${index.sha256}.json`) throw Error('Invalid observation index');
  const hash=Array.from(new Uint8Array(await root.crypto.subtle.digest('SHA-256',bytes))).map(b=>b.toString(16).padStart(2,'0')).join('');
  if(hash!==index.sha256) throw Error('Observation integrity check failed');
  const record=JSON.parse(new TextDecoder().decode(bytes));
  if(record.schema_version!==1||!Array.isArray(record.observations)||record.observations.length!==4||new Set(record.observations.map(o=>o.symbol)).size!==4) throw Error('Incomplete observation universe');
  return record;
}
function mount(document) {
  const el=id=>document.getElementById('cp-'+id);if(!el('signal'))return;
  let record=null, screenshot=false, generation=0, preview=null, profile=null;
  function render() {
    const input=record?.observations.find(o=>o.symbol===el('symbol').value);
    const analysis=screenshot ? {...root.CopilotEngine.assess(null),explanation:'Screenshot-only evidence is unverified. Return to verified data for market scenarios.'} : root.CopilotEngine.assess(input);
    el('signal').textContent=analysis.label;el('signal').dataset.state=analysis.state;
    el('explanation').textContent=analysis.explanation;
    el('metadata').textContent=`${el('symbol').value} · 1d · Observed: ${input?.observed_at||'unavailable'} · Source: ${input?.source_session||'unavailable'}`;
    const current=input && Date.parse(input.valid_until)>Date.now() && Date.parse(input.observed_at)<=Date.now();
    el('quality').textContent=screenshot?'UNVERIFIED — private screenshot context':current?`${input.quality} — ${input.reason}`:'STALE / MISSING / INVALID — WAIT';
    el('uncertainty').textContent=analysis.uncertainty;
    el('invalidation').textContent=analysis.invalidation;
    el('conditions').replaceChildren(...analysis.conditions.map(text=>{const li=document.createElement('li');li.textContent=text;return li;}));
    const v=analysis.indicators;
    el('indicators').textContent=v?`Market Intelligence: SMA20 ${v.sma20.toFixed(2)}, SMA50 ${v.sma50.toFixed(2)}, simple-window RSI14 ${v.rsi14.toFixed(2)}, ATR14 ${v.atr14.toFixed(2)}. Volatility is risk context, not a direction vote.`:'Market Intelligence indicators unavailable for this evidence.';
    const p=profile?.profiles?.find(p=>p.symbol===el('symbol').value&&p.window===60&&p.bin_count===24&&p.status==='AVAILABLE');
    el('profile').textContent=p&&['poc','vah','val'].every(k=>Number.isFinite(p[k])&&p[k]>0)&&p.method==='uniform_low_high_candle_approximation_v1' ?
      `Volume Profile (${p.start}–${p.end}): approximate POC ${p.poc.toFixed(2)}, VAH ${p.vah.toFixed(2)}, VAL ${p.val.toFixed(2)}. HISTORICAL · APPROXIMATE · UNVALIDATED. Candle-derived estimates are excluded from signal votes; exact transaction-level volume and current profile confirmation are missing.` : 'Volume Profile unavailable or invalid. Missing profile confirmation is disclosed; no exact volume-at-price is inferred.';
    el('record').textContent=input?`Frozen observation ${record.observed_at}. Outcome: PENDING. Display can become WAIT as data expires; the original record is preserved.`:'No frozen observation loaded. No performance claim.';
    el('scenarios').textContent='Bullish hypothesis: trend and momentum remain positive. Bearish hypothesis: both turn negative. Neutral hypothesis: disagreement or consolidation persists. Missing evidence or failed quality checks means WAIT. These scenarios create no orders.';
  }
  el('symbol').addEventListener('change',render);
  async function refresh(){
    try{
      const response=await fetch('copilot/latest.json',{cache:'no-store'});if(!response.ok)throw Error('Observation index unavailable');const index=await response.json();
      if(index?.schema_version!==1 || !/^[a-f0-9]{64}$/.test(index.sha256||'') || index.path!==`observations/${index.sha256}.json`)throw Error('Invalid observation path');
      const r=await fetch('copilot/'+index.path,{cache:'no-store'});if(!r.ok)throw Error('Frozen observation unavailable');
      const bytes=await r.arrayBuffer();if(bytes.byteLength>2000000)throw Error('Oversized observation');
      record=await verifiedRecord(index,bytes);render();
    }catch(error){record=null;render();el('quality').textContent='BLOCKED — '+error.message;}
  }
  function clearImage(){if(preview)URL.revokeObjectURL(preview);preview=null;el('preview').removeAttribute('src');el('preview').hidden=true;el('labels').value='';}
  el('return').addEventListener('click',()=>{++generation;screenshot=false;clearImage();el('image').value='';el('image-status').textContent='No screenshot retained.';render();});
  el('image').addEventListener('change',async()=>{
    const token=++generation;screenshot=true;clearImage();render();
    const file=el('image').files[0];if(!file){el('image-status').textContent='No image selected. Screenshot mode remains WAIT.';return;}
    el('image-status').textContent='Checking local image…';
    try{
      if(file.size>5*1024*1024)throw Error('Choose an image no larger than 5 MiB');
      const bytes=new Uint8Array(await file.arrayBuffer());
      imageHeader(bytes,file.type,file.size);
      const declared=imageDimensions(bytes,file.type);
      const bitmap=await createImageBitmap(file);
      const width=bitmap.width,height=bitmap.height;bitmap.close();
      if(token!==generation)return;
      if(width!==declared.width||height!==declared.height)throw Error('Decoded image dimensions differ from header');
      preview=URL.createObjectURL(file);el('preview').src=preview;el('preview').hidden=false;
      el('image-status').textContent=`Private local preview: ${width} × ${height}. Readability, chart identity and market values are unverified. Automatic OCR is not configured. Add only labels you can read below; no prices or indicators are inferred.`;
    }catch(error){if(token!==generation)return;clearImage();el('image-status').textContent='REJECTED — '+error.message+'; WAIT.';}
  });
  el('labels').addEventListener('input',()=>{if(!screenshot)el('labels').value='';});
  fetch('volume-profile/report.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(p=>{if(p.schema_version===1&&Array.isArray(p.profiles))profile=p;render();}).catch(()=>{profile=null;render();});
  render();refresh();setInterval(render,15000);setInterval(refresh,60000);
}
const api={imageHeader,imageDimensions,verifiedRecord,mount};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else mount(root.document);
})(typeof globalThis!=='undefined'?globalThis:this);
