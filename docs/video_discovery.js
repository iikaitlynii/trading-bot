/* Inspect local queue artifacts only. Never accepts or executes a strategy. */
(function(root){
  'use strict';
  function validate(q) {
    if(q.schema_version!==1||q.simulation_only!==true||q.evidence!=='public metadata / strategy unvalidated'||!Array.isArray(q.records)||!Array.isArray(q.candidates)||!q.envelope||!Array.isArray(q.envelope.response?.items)||q.records.length!==q.envelope.response.items.length)throw Error('Unsupported metadata queue');
    const seen=new Set();
    for(const r of q.records){
      if(!/^[A-Za-z0-9_-]{11}$/.test(r.video_id)||seen.has(r.video_id)||r.video_url!=='https://www.youtube.com/watch?v='+r.video_id||typeof r.title!=='string'||!['blocked','needs_transcript_permission'].includes(r.state)||!Number.isFinite(Date.parse(r.retrieved_at))||!r.permission||!r.original||!['response_sha256','envelope_sha256'].every(k=>/^[a-f0-9]{64}$/.test(r[k])))throw Error('Invalid metadata record');
      const p=r.permission, env=q.envelope;
      const allowed=['youtube-data-api-v3','permissioned-metadata-export'].includes(r.provider) && ['authorized API response','licensed metadata export','creator permission'].includes(p.basis) && p.status==='active' && p.scope==='metadata' && typeof p.reference==='string' && p.reference.trim() &&
        (r.provider!=='youtube-data-api-v3'||(['search.list','videos.list'].includes(r.interface)&&p.basis==='authorized API response'));
      const original=env.response.items.find(item=>(typeof item.id==='string'?item.id:item.id?.videoId)===r.video_id);
      if(!original || JSON.stringify(original)!==JSON.stringify(r.original) || JSON.stringify(p)!==JSON.stringify(env.permission) || r.provider!==env.provider || r.retrieved_at!==env.retrieved_at ||
         (r.state!=='blocked'&&(!allowed||!r.original.snippet?.title?.trim()||!r.original.snippet?.channelId?.trim()||!['public',undefined].includes(r.original.status?.privacyStatus))))throw Error('Contradictory metadata/permission record');
      seen.add(r.video_id);
    }
    return q;
  }
  function mount(document){
    const file=document.getElementById('vd-file');if(!file)return;
    const status=document.getElementById('vd-status'), records=document.getElementById('vd-records');
    const el=(tag,text)=>{const e=document.createElement(tag);e.textContent=String(text);return e;};
    let generation=0;
    file.addEventListener('change',async()=>{
      const token=++generation,f=file.files[0];records.replaceChildren();status.textContent='MISSING — inspecting unvalidated local artifact';if(!f)return;
      try{
        if(f.size>2000000)throw Error('Maximum file size 2 MB');
        const q=validate(JSON.parse(await f.text()));if(token!==generation)return;
        status.textContent=`UNVALIDATED LOCAL EXPORT · ${q.records.length} metadata records · ${q.candidates.length} candidate artifacts · ${q.pagination}. Live discovery: BLOCKED. No strategy accepted.`;
        for(const r of q.records){
          const details=el('details','');details.append(el('summary',r.title+' · '+(r.state==='blocked'?'BLOCKED':'NEEDS PERMISSION / HUMAN REVIEW')));
          const link=el('a','Original video source');link.href=r.video_url;link.rel='noopener noreferrer';details.append(link);
          details.append(el('p',`Provider ${r.provider} · ${r.interface || 'export'} · retrieved ${r.retrieved_at} · published ${r.published_at || 'MISSING'} · query ${r.query}`),el('p',`Metadata permission assertion: ${r.permission.basis || 'MISSING'} · ${r.permission.status || 'MISSING'} · ${r.permission.reference || 'MISSING'}`),el('p',`Response SHA-256 ${r.response_sha256} · envelope SHA-256 ${r.envelope_sha256}`),el('p',r.reason));
          for(const c of q.candidates.filter(c=>c.source?.video_url===r.video_url)){
            details.append(el('p','NEEDS HUMAN REVIEW — local artifact is not authenticated acceptance. Historical evaluation BLOCKED.'),el('pre',JSON.stringify({status:c.status,uncertainties:c.uncertainties,evidence:c.evidence,permission:c.source.permission},null,2)));
          }
          records.append(details);
        }
        if(!q.records.length)records.append(el('p','EMPTY — supplied export contains no metadata; no extraction performed.'));
      }catch(e){if(token!==generation)return;records.replaceChildren();status.textContent='BLOCKED — '+e.message+'; no sources accepted';}
    });
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={validate,mount};else mount(root.document);
})(typeof globalThis!=='undefined'?globalThis:this);
