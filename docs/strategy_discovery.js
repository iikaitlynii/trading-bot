/* Dashboard-only saved weekly research. No discovery, evaluation or notifications in browser. */
(function (root) {
  'use strict';
  const SCOPE = 'SYNTHETIC FIXTURES ONLY — no actual video discoveries or historical evidence';
  const isoWeek = value => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw Error('Invalid week');
    const d = new Date(value + 'T00:00:00Z');
    if (!Number.isFinite(+d) || d.toISOString().slice(0, 10) !== value || d.getUTCDay() !== 1) throw Error('Week must start Monday UTC');
    return d;
  };
  function validateIndex(index) {
    if (index.schema_version !== 1 || !Array.isArray(index.reports)) throw Error('Unsupported archive');
    const seen = new Set(); let previous = '9999-99-99';
    for (const entry of index.reports) {
      isoWeek(entry.week_start);
      if (entry.path !== entry.week_start + '.json' || !/^[a-f0-9]{64}$/.test(entry.sha256) || seen.has(entry.week_start) || previous <= entry.week_start) throw Error('Unsafe, duplicate or unordered archive entry');
      seen.add(entry.week_start); previous = entry.week_start;
    }
    return index;
  }
  function validateReport(r, selected, now = new Date()) {
    const start = isoWeek(selected), end = new Date(+start + 7 * 86400000);
    if (r.schema_version !== 1 || r.simulation_only !== true || r.scope !== SCOPE || r.historical_state !== 'UNVALIDATED' || r.week_start !== selected || r.week_end !== new Date(+end - 86400000).toISOString().slice(0, 10)) throw Error('Unsupported evidence classification');
    const generated = new Date(r.generated_at_utc);
    if (!r.generated_at_utc.endsWith('Z') || !Number.isFinite(+generated) || generated < end || generated > now) throw Error('Invalid generation time');
    if (!Array.isArray(r.sources) || !Array.isArray(r.candidates) || r.sources.length !== r.candidates.length || !r.counts) throw Error('Missing evidence');
    const sources = new Set();
    for (const s of r.sources) {
      const reviewed = new Date(s.reviewed_at), acquired = new Date(s.source.retrieved_at);
      if (s.source.synthetic !== true || s.source.permission?.basis !== 'author-created fixture' || !s.source.permission.reference || !s.reviewer || !Number.isFinite(+reviewed) || !Number.isFinite(+acquired) || reviewed < start || reviewed >= end || acquired > reviewed || sources.has(s.source_sha256) || !/^[a-f0-9]{64}$/.test(s.source_sha256)) throw Error('Unsupported or duplicated source activity');
      sources.add(s.source_sha256);
    }
    const candidateSources = new Set();
    let simulations = 0, ambiguous = 0;
    for (const c of r.candidates) {
      const sourceHash = c.candidate.source_sha256;
      if (!sources.has(sourceHash) || candidateSources.has(sourceHash) || !Array.isArray(c.candidate.uncertainties) || !c.candidate.evidence || !c.quality || !Number.isFinite(c.quality.score) || c.quality.score < 0 || c.quality.score > 100) throw Error('Invalid candidate evidence');
      candidateSources.add(sourceHash);
      if (c.candidate.uncertainties.length) ambiguous++;
      if (c.result !== null) {
        if (c.simulation_state !== 'UNVALIDATED' || c.result.evidence !== 'illustrative synthetic simulation' || c.result.candidate_sha256 !== c.candidate_sha256 || c.result.robustness?.historical_evidence !== false || !c.result.periods?.evaluation?.candidate || !Number.isFinite(c.result.periods.evaluation.candidate.return_pct) || !Number.isFinite(c.result.periods.evaluation.candidate.max_drawdown_pct) || c.candidate.uncertainties.length) throw Error('Unsupported simulation claims');
        simulations++;
      } else if (c.simulation_state !== 'NOT RUN') throw Error('Missing simulation must be NOT RUN');
    }
    if (r.counts.sources_reviewed !== r.sources.length || r.counts.candidates !== r.candidates.length || r.counts.simulations !== simulations || r.counts.ambiguous !== ambiguous || r.activity_state !== (r.sources.length ? 'RECORDED FIXTURE REVIEWS' : 'EMPTY') || r.simulation_state !== (simulations ? 'UNVALIDATED' : 'NOT RUN')) throw Error('Counts or states contradict evidence');
    return r;
  }
  function mount(document, fetcher, crypto, now = () => new Date()) {
    const get = id => document.getElementById('discovery-' + id);
    if (!get('status')) return;
    const create = (tag, text) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = String(text); return el; };
    let generation = 0, entries = [];
    const reset = message => {
      get('status').textContent = message;
      get('summary').textContent = 'Sources reviewed: unavailable · Candidates: unavailable · Ambiguities: unavailable';
      get('simulation').textContent = 'Simulation: NOT RUN · Historical evidence: UNVALIDATED';
      for (const id of ['sources', 'candidates', 'results']) get(id).replaceChildren();
    };
    function render(r) {
      get('status').textContent = r.activity_state + ' · ' + r.week_start + ' through ' + r.week_end + ' (UTC) · generated ' + r.generated_at_utc;
      get('summary').textContent = `Recorded synthetic source reviews: ${r.counts.sources_reviewed} · Candidate extractions: ${r.counts.candidates} · Ambiguous: ${r.counts.ambiguous} · Simulations: ${r.counts.simulations}. No actual video discoveries.`;
      get('simulation').textContent = 'Simulation: ' + r.simulation_state + ' · Historical evidence: UNVALIDATED';
      for (const source of r.sources) {
        const item = create('li');
        item.append(create('strong', source.source.title), create('p', 'Synthetic fixture · Reviewed ' + source.reviewed_at + ' · ' + source.reviewer), create('p', source.source.video_url), create('p', 'Permission: ' + source.source.permission.reference), create('p', 'Source SHA-256: ' + source.source_sha256));
        get('sources').append(item);
      }
      for (const record of r.candidates) {
        const c = record.candidate, details = create('details'), summary = create('summary', c.source.title + ' · ' + record.quality.grade + ' · Research quality ' + record.quality.score + '/100');
        details.append(summary, create('p', 'Candidate SHA-256: ' + record.candidate_sha256), create('p', 'Human-review gate: ' + c.status + '. Synthetic demo attestations do not constitute human acceptance.'), create('p', c.uncertainties.length ? 'Ambiguities: ' + c.uncertainties.join(' · ') : 'No parser ambiguities; independent human review remains required.'));
        const quotes = create('ul');
        for (const [field, evidence] of Object.entries(c.evidence)) for (const quote of evidence) quotes.append(create('li', field + ' [' + quote.start + '–' + quote.end + 's]: ' + quote.quote + ' · ' + quote.url));
        details.append(quotes); get('candidates').append(details);
        if (record.result) {
          const r = record.result, values = r.periods.evaluation.candidate, tr = create('tr');
          for (const v of [c.source.title, 'UNVALIDATED · synthetic only', values.return_pct.toFixed(4) + '%', Math.abs(values.max_drawdown_pct).toFixed(4) + '%', record.quality.score + '/100']) tr.append(create('td', v));
          get('results').append(tr);
          const baseline = create('details'); baseline.append(create('summary', 'Simulation comparisons and limitations: ' + c.source.title));
          // Preserve original baseline keys and signs; explain engine differences.
          baseline.append(create('pre', JSON.stringify(r.periods.evaluation.baselines, null, 2)));
          for (const note of r.limitations) baseline.append(create('p', note));
          get('candidates').append(baseline);
        }
      }
      if (!r.sources.length) get('sources').append(create('li', 'EMPTY — no recorded source reviews in this report.'));
      if (!r.candidates.length) get('candidates').append(create('p', 'EMPTY — no candidate evidence.'));
      if (!r.counts.simulations) { const tr = create('tr'), td = create('td', 'NOT RUN — no simulation results. Historical evidence remains UNVALIDATED.'); td.colSpan = 5; tr.append(td); get('results').append(tr); }
    }
    async function selectWeek() {
      const token = ++generation;
      reset('NOT RUN — loading selected archived report; evidence unavailable until verified.');
      const entry = entries.find(e => e.week_start === get('archive').value);
      if (!entry) { reset('NOT RUN — no weekly report selected. Archive: EMPTY.'); return; }
      try {
        const response = await fetcher('strategy-discovery/' + entry.path, {cache: 'no-store'});
        if (!response.ok) throw Error('HTTP ' + response.status);
        const raw = await response.text();
        const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(raw)))].map(b => b.toString(16).padStart(2, '0')).join('');
        if (hash !== entry.sha256) throw Error('Report hash mismatch');
        const r = validateReport(JSON.parse(raw), entry.week_start, now());
        if (token === generation) render(r);
      } catch (error) {
        if (token === generation) reset('NOT RUN — saved evidence unavailable or invalid: ' + error.message + '. No results inferred.');
      }
    }
    get('archive').addEventListener('change', selectWeek);
    const ready = (async () => {
      reset('NOT RUN — no verified weekly report loaded.');
      try {
        const response = await fetcher('strategy-discovery/index.json', {cache: 'no-store'});
        if (!response.ok) throw Error('HTTP ' + response.status);
        entries = validateIndex(await response.json()).reports;
        get('archive').replaceChildren();
        if (!entries.length) {
          get('archive').append(create('option', 'EMPTY — no archived weekly reports')); get('archive').disabled = true;
          reset('NOT RUN — weekly research has no published report. Archive: EMPTY.');
          return;
        }
        get('archive').disabled = false;
        for (const entry of entries) { const option = create('option', 'Week of ' + entry.week_start + ' (UTC)'); option.value = entry.week_start; get('archive').append(option); }
        get('archive').value = entries[0].week_start;
        await selectWeek();
      } catch (error) { get('archive').disabled = true; reset('NOT RUN — archive unavailable or invalid: ' + error.message + '. No weekly activity inferred.'); }
    })();
    return {ready, selectWeek};
  }
  const api = {validateIndex, validateReport, mount};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else if (root.document) mount(root.document, root.fetch.bind(root), root.crypto);
})(typeof globalThis !== 'undefined' ? globalThis : this);
