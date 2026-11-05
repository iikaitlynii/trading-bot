'use strict';
const assert = require('node:assert/strict');
const {checked,expected,safeLink} = require('../docs/account_health.js');
const now = Date.parse('2026-11-03T04:00:00Z');
function fixture(status='ACTIVE') { return {schema_version:1,simulation_only:true,accounts:[{id:'stock',status,checked_at:'2026-11-03T03:00:00Z',expires_at:'2026-11-03T21:00:00Z',expected_session:'2026-11-02',last_verified_data_session:'2026-11-02',last_recorded_valuation:'2026-11-02',last_successful_account_advancement:'2026-11-02',data_fresh:true,reason_codes:[status==='PAUSED'?'ALREADY_PROCESSED':'ACCOUNT_PUBLISHED'],explanations:['Synthetic fixture'],symbols:Object.fromEntries(['AAPL','MSFT','NVDA','AMZN'].map(s=>[s,{status:'VALIDATED',source_session:'2026-11-02',http_status:200}])),publication:{session:'2026-11-02',output_commit:'a'.repeat(40),bundle_sha256:'b'.repeat(64),run_id:42,run_attempt:1,outcome:status==='ACTIVE'?'ADVANCED':'ALREADY_PROCESSED',files:Object.fromEntries(['state.json','performance.csv','journal.csv','latest_signals.csv'].map(s=>['paper/'+s,'c'.repeat(64)]))},workflow:{status:'SUCCESS',run_id:42,run_attempt:1,url:'https://github.com/iikaitlynii/trading-bot/actions/runs/42'},evidence:['https://github.com/iikaitlynii/trading-bot/blob/main/monitoring/account_receipts/stock.json']}]}; }
assert.equal(checked(fixture(),'stock',now).status,'ACTIVE');
assert.equal(checked(fixture('PAUSED'),'stock',now).status,'PAUSED');
for (const patch of [{status:'UNKNOWN'},{symbols:null},{publication:null},{expires_at:'2026-11-03T03:30:00Z'},{expires_at:'2030-01-01'},{checked_at:'2027-01-01'},{reason_codes:[]},{last_recorded_valuation:'2026-10-30'},{data_fresh:false},{workflow:{status:'SUCCESS'}},{evidence:[]},{last_successful_account_advancement:null}]) {
 const p=fixture();Object.assign(p.accounts[0],patch);assert.equal(checked(p,'stock',now).status,'BLOCKED',JSON.stringify(patch));
}
for(const p of [null,{},'invalid',{schema_version:2}, {...fixture(),accounts:[...fixture().accounts,...fixture().accounts]}]) assert.equal(checked(p,'stock',now).status,'BLOCKED');
assert.equal(checked(fixture(),'stock',Date.parse('2026-11-03T21:00:00Z')).status,'BLOCKED');
assert.equal(expected(Date.parse('2026-11-08T12:00:00Z'),'stock'),'2026-11-06');
assert.equal(expected(Date.parse('2026-11-08T12:00:00Z'),'crypto'),'2026-11-07');
assert.equal(expected(Date.parse('2026-11-27T17:59:59Z'),'stock'),'2026-11-25');
assert.equal(expected(Date.parse('2026-11-27T18:00:00Z'),'stock'),'2026-11-27');
assert.equal(expected(Date.parse('2028-01-01T00:00:00Z'),'stock'),null);
assert.equal(safeLink('javascript:alert(1)'),false);
assert.equal(safeLink('https://github.com.evil.test/iikaitlynii/trading-bot/'),false);
console.log('Account health: status, unknown evidence, expiry, calendar and safe links passed.');
