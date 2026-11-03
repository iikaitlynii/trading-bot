'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {webcrypto, createHash} = require('node:crypto');
const {mount, validateIndex, validateReport} = require('../docs/strategy_discovery.js');
const fixtures = JSON.parse(fs.readFileSync('work/discovery-fixtures.json', 'utf8'));
const now = () => new Date('2026-10-29T12:00:00Z');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.listeners = {}; this.textContent = ''; this.disabled = false; this.value = ''; }
  replaceChildren(...items) { this.children = items; }
  append(...items) { this.children.push(...items); }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  set innerHTML(_) { throw Error('Unsafe HTML insertion'); }
}
function harness() {
  const ids = ['status','summary','simulation','archive','sources','candidates','results'];
  const elements = Object.fromEntries(ids.map(id => [id, new Element('div')]));
  const requests = [];
  const document = {getElementById: id => elements[id.replace('discovery-','')], createElement: tag => new Element(tag)};
  const app = mount(document, url => new Promise(resolve => requests.push({url, resolve})), webcrypto, now);
  return {elements, requests, app};
}
const tick = () => new Promise(resolve => setImmediate(resolve));
const raw = r => JSON.stringify(r);
const entry = r => ({week_start:r.week_start,path:r.week_start+'.json',sha256:createHash('sha256').update(raw(r)).digest('hex')});
const index = {schema_version:1,reports:[entry(fixtures.full),entry(fixtures.empty)]};
const response = r => ({ok:true,json:async()=>r,text:async()=>raw(r)});
const allText = e => e.textContent + ' ' + e.children.map(allText).join(' ');
(async () => {
  for (const mutate of [i => i.reports.push(i.reports[0]), i => i.reports[0].path='../other.json', i => i.reports.reverse()]) {
    const i=structuredClone(index);mutate(i);assert.throws(()=>validateIndex(i));
  }
  for (const mutate of [r => r.counts.sources_reviewed=99, r => r.historical_state='VALIDATED',r => r.sources[0].source.synthetic=false,r => r.simulation_state='PROFITABLE',r => r.candidates[0].result.evidence='historical',r => r.generated_at_utc='2099-01-01T00:00:00Z']) {
    const r=structuredClone(fixtures.full);mutate(r);assert.throws(()=>validateReport(r,r.week_start,now()));
  }
  let h=harness();h.requests[0].resolve(response({schema_version:1,reports:[]}));await h.app.ready;
  assert.match(h.elements.status.textContent,/NOT RUN.*Archive: EMPTY/);
  assert.equal(h.elements.archive.disabled,true);
  assert.match(h.elements.simulation.textContent,/NOT RUN.*UNVALIDATED/);
  assert.equal(h.requests.length,1); // Never fetch demo or synthesize a report.

  h=harness();h.requests[0].resolve({ok:false,status:404});await h.app.ready;
  assert.match(h.elements.status.textContent,/archive unavailable/);
  assert.equal(h.elements.results.children.length,0);

  h=harness();h.requests[0].resolve(response(index));await tick();
  assert.equal(h.requests[1].url,'strategy-discovery/2026-10-19.json');
  // Switch before the first report arrives; stale responses must not replace selection.
  h.elements.archive.value='2026-10-12';const selected=h.app.selectWeek();
  h.requests[2].resolve(response(fixtures.empty));await selected;
  h.requests[1].resolve(response(fixtures.full));await h.app.ready;
  assert.match(h.elements.status.textContent,/EMPTY.*2026-10-12/);
  assert.match(h.elements.summary.textContent,/source reviews: 0/);
  assert.match(allText(h.elements.results),/NOT RUN/);

  h.elements.archive.value='2026-10-19';let loading=h.app.selectWeek();
  h.requests[3].resolve(response(fixtures.full));await loading;
  assert.match(h.elements.status.textContent,/RECORDED FIXTURE REVIEWS/);
  assert.match(h.elements.summary.textContent,/Ambiguous: 1/);
  assert.equal(h.elements.results.children.length,1);
  assert.match(allText(h.elements.candidates),/unparsed transcript content/);
  assert.match(allText(h.elements.results),/UNVALIDATED/);
  loading=h.app.selectWeek();h.requests[4].resolve(response({...fixtures.full,counts:{}}));await loading;
  assert.match(h.elements.status.textContent,/hash mismatch/i);
  assert.equal(h.elements.results.children.length,0); // No stale success after error.

  const malicious=structuredClone(fixtures.empty);
  malicious.sources=structuredClone(fixtures.full.sources);malicious.candidates=structuredClone(fixtures.full.candidates);
  malicious.week_start=fixtures.full.week_start;malicious.week_end=fixtures.full.week_end;
  malicious.counts=fixtures.full.counts;malicious.activity_state=fixtures.full.activity_state;malicious.simulation_state=fixtures.full.simulation_state;
  malicious.sources[0].source.title='<img src=x onerror=alert(1)>';
  malicious.candidates[0].candidate.source.title='<script>alert(1)</script>';
  h=harness();h.requests[0].resolve(response({schema_version:1,reports:[entry(malicious)]}));await tick();
  h.requests[1].resolve(response(malicious));await h.app.ready;
  assert.match(allText(h.elements.sources),/<img/); // Inert textContent, never HTML.
  assert.match(allText(h.elements.candidates),/<script>/);
  const html=fs.readFileSync('docs/index.html','utf8');
  for(const id of ['strategy-discovery','discovery-status','discovery-archive','discovery-summary','discovery-simulation','discovery-sources','discovery-candidates','discovery-results']) assert.ok(html.includes('id="'+id+'"'));
  assert.ok(html.includes('src="strategy_discovery.js" defer'));
  console.log('PASS: weekly archive integrity/schema, empty/missing evidence, switching/races, reset on corruption, rankings/ambiguities/results, inert text and dashboard DOM contract');
})().catch(error=>{console.error(error);process.exitCode=1;});
