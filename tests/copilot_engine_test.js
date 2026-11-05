const assert=require('node:assert/strict');
const {RULE,assess}=require('../docs/copilot_engine.js');
const {imageHeader,imageDimensions,verifiedRecord}=require('../docs/copilot.js');
const now=Date.parse('2026-11-04T23:00:00Z');
function fixture(direction=1){
  const bars=Array.from({length:100},(_,i)=>({session:new Date(Date.UTC(2026,10,4-99+i)).toISOString().slice(0,10),close:200+direction*i,high:202+direction*i,low:198+direction*i,volume:1000}));
  return {schema_version:1,rule:RULE,symbol:'AAPL',timeframe:'1d',observed_at:'2026-11-04T22:00:00Z',valid_until:'2026-11-05T21:00:00Z',source_timestamp:'2026-11-04T21:00:00Z',source_session:bars.at(-1).session,quality:'VERIFIED',reason:'Synthetic test fixture only; no market verification claim',evidence:'validated-provider-snapshot',bundle_sha256:'a'.repeat(64),bars};
}
assert.equal(assess(fixture(),now).state,'BUY');assert.equal(assess(fixture(-1),now).state,'SELL');assert.equal(assess(fixture(0),now).state,'WAIT');
for(const mutate of [x=>x.quality='UNVERIFIED',x=>x.quality='BLOCKED',x=>x.evidence='synthetic',x=>x.bars=[],x=>x.bars[10].volume=null,x=>x.bars[10].close=NaN,x=>x.bars[11].session=x.bars[10].session,x=>x.bundle_sha256=null,x=>x.observed_at='2026-11-06T00:00:00Z',x=>x.valid_until='2026-11-04T22:30:00Z',x=>x.source_session='wrong',x=>x.timeframe='5m',x=>x.symbol='UNKNOWN']){
 const input=fixture();mutate(input);assert.equal(assess(input,now).state,'WAIT');
}
assert.equal(assess(null,now).state,'WAIT');
const changed=fixture();changed.bars.at(-1).close=changed.bars.at(-1).high;assert.deepEqual(assess(changed,now).indicators,assess(fixture(),now).indicators,'last context bar must not leak into prior-bar setup');
imageHeader(Uint8Array.from([137,80,78,71,13,10,26,10]),'image/png',100);
const bomb=new Uint8Array(24);new DataView(bomb.buffer).setUint32(16,65535);new DataView(bomb.buffer).setUint32(20,65535);assert.throws(()=>imageDimensions(bomb,'image/png'));
for(const [bytes,type,size] of [[[], 'image/svg+xml',100],[[137,80,78,71,13,10,26,10],'image/jpeg',100],[[],'image/png',6000000]])assert.throws(()=>imageHeader(Uint8Array.from(bytes),type,size));
(async()=>{await assert.rejects(()=>verifiedRecord({schema_version:1,path:'../private.png',sha256:'a'.repeat(64)},new ArrayBuffer(0)));console.log('PASS: BUY/SELL/WAIT, quality/stale/future/malformed gates, prior-bar invariance, upload signatures/limits and path rejection');})();
module.exports={fixture,now};
