'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor() { this.children = []; this.listeners = {}; this.hidden = false; this.textContent = ''; }
  replaceChildren() { this.children = []; }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.children.push(child); }
  addEventListener(event, listener) { this.listeners[event] = listener; }
}
const ids = ['stocks', 'crypto', 'report-status', 'report-metrics', 'report-months', 'report-daily', 'report-monthly', 'report-summary'];
const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
const pending = [];
const context = {document: {getElementById: id => elements[id], createElement: () => new Element()},
  fetch: url => new Promise(resolve => pending.push({url, resolve})), Intl, console};
vm.runInNewContext(fs.readFileSync('docs/performance_reports.js', 'utf8'), context);
const tick = () => new Promise(resolve => setImmediate(resolve));
const fixture = account => JSON.parse(fs.readFileSync('reports/' + account + '.json', 'utf8'));
(async () => {
  assert.match(pending[0].url, /stocks.json$/);
  elements.crypto.listeners.click();
  pending[1].resolve({ok: true, json: async () => fixture('crypto')}); await tick();
  assert.match(elements['report-monthly'].href, /crypto_monthly.csv$/);
  assert.equal(elements['report-monthly'].hidden, false);
  assert.equal(elements['report-months'].children.length, fixture('crypto').monthly.length);
  assert.ok(elements['report-metrics'].children.some(e => e.textContent === 'Unavailable'));
  assert.ok(!elements['report-metrics'].children.some(e => /NaN/.test(e.textContent)));
  pending[0].resolve({ok: true, json: async () => fixture('stocks')}); await tick();
  assert.match(elements['report-monthly'].href, /crypto_monthly.csv$/); // stale response ignored
  elements.stocks.listeners.click();
  assert.equal(elements['report-monthly'].hidden, true);
  pending[2].resolve({ok: false, status: 404}); await tick();
  assert.match(elements['report-status'].textContent, /unavailable/);
  assert.equal(elements['report-metrics'].children.length, 0);
  elements.stocks.listeners.click();
  pending[3].resolve({ok: true, json: async () => ({schema_version: 99})}); await tick();
  assert.match(elements['report-status'].textContent, /Unsupported/);
  elements.stocks.listeners.click();
  pending[4].resolve({ok: true, json: async () => fixture('stocks')}); await tick();
  assert.equal(elements['report-months'].children.length, fixture('stocks').monthly.length);
  assert.match(elements['report-status'].textContent, /duplicate/);
  const html = fs.readFileSync('docs/index.html', 'utf8');
  for (const id of ids) assert.ok(html.includes('id="' + id + '"'), id);
  assert.ok(html.includes('src="performance_reports.js"'));
  assert.ok(html.includes('UNCLASSIFIED REMAINING CHANGE'));
  console.log('Dashboard switching, stale response, missing data, downloads and DOM contract passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
