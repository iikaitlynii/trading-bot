'use strict';
const assert=require('node:assert/strict');
const {validate,indicators,confluence,fixture}=require('../docs/chart_intelligence.js');
const video=require('../docs/video_discovery.js');
const f=fixture();validate(f);
const rising=f.bars.map((b,i)=>({...b,open:100+i,close:100+i,high:101+i,low:99+i}));
const values=indicators(rising);
assert.equal(values[49].sma20,139.5);assert.equal(values[49].sma50,124.5);
assert.equal(values[14].rsi14,100);assert.equal(values[14].atr14,2);
assert.equal(values[13].rsi14,null);assert.equal(values[48].sma50,null);
const sd=Math.sqrt(33.25);assert.ok(Math.abs(values[19].bandHigh-(109.5+2*sd))<1e-10);
assert.equal(confluence(rising).signal,'SIMULATED LONG SETUP');
const falling=rising.map((b,i)=>({...b,open:200-i,close:200-i,high:201-i,low:199-i}));
assert.equal(confluence(falling).signal,'SIMULATED DEFENSIVE SETUP');
const flat=rising.map(b=>({...b,open:100,close:100,high:100,low:100}));
assert.equal(indicators(flat)[14].rsi14,50);assert.equal(indicators(flat)[14].atr14,0);
assert.equal(confluence(flat).signal,'WAIT / MIXED EVIDENCE');
assert.equal(confluence(rising.slice(0,15)).signal,'UNAVAILABLE');
const missing=structuredClone(rising);missing[90].volume=null;
assert.equal(confluence(missing).missing,1);assert.equal(confluence(missing).signal,'UNAVAILABLE');
// Mutating the context bar cannot change the setup formed on the previous bar.
const perturbed=structuredClone(rising);perturbed.at(-1).close=100000;
assert.deepEqual(confluence(perturbed),confluence(rising));
for(let end=2;end<100;end++)assert.deepEqual(indicators(rising.slice(0,end)),values.slice(0,end));
const mixed=structuredClone(rising);for(let i=90;i<100;i++)mixed[i].close=180-(i-90)*2;
assert.equal(confluence(mixed).disagreement,1);assert.equal(confluence(mixed).signal,'WAIT / MIXED EVIDENCE');
for(const mutate of [x=>x.bars[0].close=null,x=>x.bars[1].session=x.bars[0].session,x=>x.bars[0].high=1,x=>x.bars[0].volume=-1,x=>x.evidence='verified',x=>x.bars[0].session='2026-02-30',x=>x.bars[0].open=true,x=>x.bars[0].close=1e308]){
 const bad=fixture();mutate(bad);assert.throws(()=>validate(bad));
}
assert.equal(confluence([]).signal,'UNAVAILABLE');
assert.throws(()=>video.validate({schema_version:1,simulation_only:true,records:[],candidates:[]}));
console.log('PASS: hand-calculated SMA/RSI/ATR/bands, warmups, flat/mixed/missing evidence, prefix/lag invariance and invalid OHLCV');
