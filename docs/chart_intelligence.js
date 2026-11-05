/* Independent teaching calculations. No orders, portfolio writes or performance claims. */
(function(root) {
  'use strict';
  function validate(data) {
    if (!data || data.schema_version !== 1 || !['synthetic','historical-unvalidated'].includes(data.evidence) ||
        typeof data.symbol !== 'string' || !data.symbol.trim() || !data.provenance ||
        !['source','retrieved_at','adjustment','session_convention'].every(k => typeof data.provenance[k] === 'string' && data.provenance[k].trim()) ||
        !Number.isFinite(Date.parse(data.provenance.retrieved_at)) || !Array.isArray(data.bars) || data.bars.length > 5000) throw Error('Unsupported OHLCV evidence envelope');
    let previous = '';
    for (const b of data.bars) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(b.session) || !Number.isFinite(Date.parse(b.session)) || new Date(b.session).toISOString().slice(0,10) !== b.session || b.session <= previous ||
          !['open','high','low','close'].every(k => typeof b[k] === 'number' && Number.isFinite(b[k]) && b[k] > 0 && b[k] <= 1e12) ||
          b.low > Math.min(b.open,b.close) || b.high < Math.max(b.open,b.close) ||
          !(b.volume === null || (typeof b.volume === 'number' && Number.isFinite(b.volume) && b.volume >= 0 && b.volume <= 1e18))) throw Error('Invalid, duplicate or unordered OHLCV bar; no filling allowed');
      previous = b.session;
    }
    return data;
  }
  const mean = a => a.reduce((s,v)=>s+v,0)/a.length;
  function indicators(bars) {
    return bars.map((b,i) => {
      const closes = n => bars.slice(i-n+1,i+1).map(x=>x.close);
      const sma = n => i+1 >= n ? mean(closes(n)) : null;
      let rsi = null, atr = null, bandLow = null, bandHigh = null;
      if (i >= 14) {
        const changes = bars.slice(i-13,i+1).map((v,j)=>v.close-bars[i-14+j].close);
        const gains = mean(changes.map(v=>Math.max(v,0))), losses = mean(changes.map(v=>Math.max(-v,0)));
        rsi = gains === 0 && losses === 0 ? 50 : losses === 0 ? 100 : 100-100/(1+gains/losses);
        atr = mean(bars.slice(i-13,i+1).map((v,j)=>Math.max(v.high-v.low,Math.abs(v.high-bars[i-14+j].close),Math.abs(v.low-bars[i-14+j].close))));
      }
      if (i >= 19) {
        const avg = sma(20), sd = Math.sqrt(mean(closes(20).map(v=>(v-avg)**2)));
        bandLow = avg-2*sd; bandHigh = avg+2*sd;
      }
      return {sma20:sma(20),sma50:sma(50),rsi14:rsi,atr14:atr,bandLow,bandHigh};
    });
  }
  function confluence(bars, values = indicators(bars)) {
    // Signal uses only the previous completed input bar; the final bar is display context.
    const i = bars.length-2, v = values[i], b = bars[i];
    if (!v || !b) return {signal:'UNAVAILABLE',asof:null,evidence:[{name:'History',state:'missing',reason:'At least two completed bars required'}],agreement:0,disagreement:0,missing:1};
    const trend = v.sma50 === null ? 'missing' : v.sma20 > v.sma50 ? 'bullish' : v.sma20 < v.sma50 ? 'bearish' : 'neutral';
    const momentum = v.rsi14 === null ? 'missing' : v.rsi14 > 55 ? 'bullish' : v.rsi14 < 45 ? 'bearish' : 'neutral';
    const evidence = [
      {name:'Trend',state:trend,reason:'SMA20 above/below SMA50; equal is neutral'},
      {name:'Momentum',state:momentum,reason:'Simple-window RSI14 above 55 / below 45; otherwise neutral'},
      {name:'Volatility',state:v.atr14 === null ? 'missing' : 'context',reason:v.atr14 === null ? 'Needs 15 bars including previous close' : `ATR14 ${(100*v.atr14/b.close).toFixed(2)}% of close; risk context, no direction vote`},
      {name:'Volume',state:bars.slice(Math.max(0,i-19),i+1).length < 20 || bars.slice(i-19,i+1).some(x=>x.volume===null) ? 'missing':'context',reason:'20 observed volumes required; activity alone has no direction vote'}
    ];
    const bulls = evidence.filter(e=>e.state==='bullish').length, bears = evidence.filter(e=>e.state==='bearish').length;
    const missing = evidence.filter(e=>e.state==='missing').length;
    return {signal:missing ? 'UNAVAILABLE' : bulls===2 ? 'SIMULATED LONG SETUP' : bears===2 ? 'SIMULATED DEFENSIVE SETUP' : 'WAIT / MIXED EVIDENCE',asof:b.session,evidence,
      agreement:Math.max(bulls,bears),disagreement:Math.min(bulls,bears),missing};
  }
  function fixture() {
    const bars = Array.from({length:100},(_,i)=>{
      const open=100+i*.17+Math.sin(i*.4)*3, close=open+Math.cos(i*.7);
      return {session:new Date(Date.UTC(2026,0,1+i)).toISOString().slice(0,10),open,close,high:Math.max(open,close)+1.2,low:Math.min(open,close)-1.1,volume:10000+i*37};
    });
    return {schema_version:1,symbol:'TEACHING FIXTURE',evidence:'synthetic',provenance:{source:'Deterministic artificial OHLCV; no market data',retrieved_at:'2026-04-11T00:00:00Z',adjustment:'none — artificial prices',session_convention:'artificial consecutive UTC days'},bars};
  }
  function mount(document) {
    const get=id=>document.getElementById('ci-'+id);
    if (!get('chart')) return;
    let data=fixture();
    const node=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;return e;};
    const svgNode=(tag,attrs)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs)) e.setAttribute(k,String(v));return e;};
    function render() {
      const values=indicators(data.bars), c=confluence(data.bars,values), count=Number(get('window').value), start=Math.max(0,data.bars.length-count), bars=data.bars.slice(start), svg=get('chart');
      get('status').textContent=`${data.symbol} · ${data.evidence.toUpperCase()} · UNVALIDATED · ${data.bars.length} supplied bars. Historical verification: unavailable. ${data.provenance.source}`;
      get('provenance').textContent=`Retrieved ${data.provenance.retrieved_at} · ${data.provenance.adjustment} · ${data.provenance.session_convention}. Gaps/calendar completeness and provider authenticity are not verified by this viewer.`;
      get('signal').textContent=`${c.signal} · formed ${c.asof || 'unavailable'} from previous supplied bar · agreement ${c.agreement}/2 directional votes · disagreement ${c.disagreement} · missing ${c.missing}`;
      get('evidence').replaceChildren(...c.evidence.map(e=>node('li',`${e.name}: ${e.state.toUpperCase()} — ${e.reason}`)));
      const last=values.at(-1), fmt=v=>v===null?'MISSING':v.toFixed(2);
      get('values').textContent=last ? `Latest displayed bar: SMA20 ${fmt(last.sma20)} · SMA50 ${fmt(last.sma50)} · RSI14 ${fmt(last.rsi14)} · ATR14 ${fmt(last.atr14)} · 20-bar ±2σ bands ${fmt(last.bandLow)}–${fmt(last.bandHigh)}` : 'MISSING — no bars';
      svg.replaceChildren(svgNode('title',{}));svg.firstChild.textContent='Educational candlesticks, SMA20 in gold, SMA50 in blue, volume below';
      if(!bars.length) {get('status').textContent+=' · MISSING — no OHLCV bars';return;}
      const overlays=values.slice(start).flatMap(v=>[v.sma20,v.sma50]).filter(v=>v!==null);
      const lo=Math.min(...bars.map(b=>b.low),...overlays),hi=Math.max(...bars.map(b=>b.high),...overlays),range=hi-lo||1;
      const x=i=>45+(i+.5)*630/bars.length,y=v=>245-(v-lo)/range*210, maxVol=Math.max(1,...bars.map(b=>b.volume||0)),width=Math.max(1,630/bars.length*.65);
      for(let j=0;j<4;j++){const value=lo+range*j/3;const label=svgNode('text',{x:2,y:y(value),fill:'#e8d5df','font-size':10});label.textContent=value.toFixed(1);svg.append(label);}
      bars.forEach((b,i)=>{
        const color=b.close>=b.open?'#a7dfc6':'#f1a0b5';
        svg.append(svgNode('line',{x1:x(i),x2:x(i),y1:y(b.high),y2:y(b.low),stroke:color}),svgNode('rect',{x:x(i)-width/2,y:Math.min(y(b.open),y(b.close)),width,height:Math.max(1,Math.abs(y(b.open)-y(b.close))),fill:color}));
        if(b.volume!==null) svg.append(svgNode('rect',{x:x(i)-width/2,y:325-55*b.volume/maxVol,width,height:55*b.volume/maxVol,fill:color}));
      });
      for(const [key,color] of [['sma20','#f0cc73'],['sma50','#9bc7ff']]) {
        const points=values.slice(start).map((v,i)=>v[key]===null?null:`${x(i)},${y(v[key])}`).filter(Boolean);
        if(points.length) svg.append(svgNode('polyline',{points:points.join(' '),fill:'none',stroke:color,'stroke-width':2}));
      }
      const dates=svgNode('text',{x:45,y:350,fill:'#e8d5df','font-size':12}); dates.textContent=`${bars[0].session} through ${bars.at(-1).session} · volume (units supplied) below`;svg.append(dates);
      get('table').replaceChildren(...bars.slice(-10).map(b=>{const tr=document.createElement('tr');for(const v of [b.session,b.open.toFixed(2),b.high.toFixed(2),b.low.toFixed(2),b.close.toFixed(2),b.volume===null?'MISSING':b.volume])tr.append(node('td',v));return tr;}));
    }
    get('window').addEventListener('change',render);
    get('demo').addEventListener('click',()=>{++generation;data=fixture();get('file').value='';render();});
    let generation=0;
    get('file').addEventListener('change',async()=>{
      const token=++generation,file=get('file').files[0];if(!file)return;
      try {if(file.size>2000000)throw Error('Maximum file size 2 MB');const parsed=validate(JSON.parse(await file.text()));if(token!==generation)return;data=parsed;render();}
      catch(e){if(token!==generation)return;data={...fixture(),bars:[]};render();get('status').textContent='BLOCKED — '+e.message+'; no signal inferred';}
    });
    render();
  }
  const api={validate,indicators,confluence,fixture,mount};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else mount(root.document);
})(typeof globalThis!=='undefined'?globalThis:this);
