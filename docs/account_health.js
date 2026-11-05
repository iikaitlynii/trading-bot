/* Simulation health is independent of returns and of workflow success. */
(function (root) {
  'use strict';
  const ids = ['stock', 'crypto', 'forward'];
  const labels = ['STOCK', 'CRYPTO', 'FORWARD RESEARCH'];
  const github = 'https://github.com/iikaitlynii/trading-bot/';
  function expected(now, id) {
    if (id === 'crypto') return new Date(now - 86400000).toISOString().slice(0, 10);
    const closes = root.AccountHealthCalendar || (typeof require === 'function' ? require('./account_health_calendar.js') : []);
    if (!closes.length || now < Date.parse(closes[0]) || now >= Date.parse('2028-01-01T00:00:00Z')) return null;
    const completed = closes.filter(close => Date.parse(close) <= now);
    return completed.length ? completed[completed.length - 1].slice(0, 10) : null;
  }
  function checked(payload, id, now = Date.now()) {
    const fallback = {id, label: labels[ids.indexOf(id)], status: 'BLOCKED', reason_codes: ['HEALTH_EVIDENCE_UNAVAILABLE'], explanations: ['Health evidence is missing, invalid or expired. Saved valuations do not establish fresh data.'], evidence: [], data_fresh: false};
    if (!payload || payload.schema_version !== 1 || payload.simulation_only !== true || !Array.isArray(payload.accounts)) return fallback;
    const matches = payload.accounts.filter(a => a && a.id === id);
    if (matches.length !== 1) return fallback;
    const a = matches[0], stamp = Date.parse(a.checked_at), expires = Date.parse(a.expires_at);
    const session = expected(now, id);
    if (!['ACTIVE', 'PAUSED', 'BLOCKED'].includes(a.status) || !Number.isFinite(stamp) || stamp > now ||
        !Number.isFinite(expires) || expires <= now || expires <= stamp || expires - stamp > 26 * 3600000 ||
        !session || session !== a.expected_session || !Array.isArray(a.reason_codes) || !a.reason_codes.length ||
        !a.reason_codes.every(x => typeof x === 'string') || !Array.isArray(a.explanations) || !a.explanations.length ||
        !a.explanations.every(x => typeof x === 'string') || !Array.isArray(a.evidence)) return {...fallback, checked_at: a.checked_at};
    if (a.status !== 'BLOCKED' && (id === 'forward' || a.data_fresh !== true ||
        a.last_verified_data_session !== session || a.last_recorded_valuation !== session ||
        !a.workflow || a.workflow.status !== 'SUCCESS' || !Number.isInteger(a.workflow.run_id) ||
        a.workflow.url !== github + 'actions/runs/' + a.workflow.run_id ||
        !a.evidence.includes(github + 'blob/main/monitoring/account_receipts/' + id + '.json') ||
        (a.status === 'ACTIVE' && (a.last_successful_account_advancement !== session || !a.reason_codes.includes('ACCOUNT_PUBLISHED'))) ||
        (a.status === 'PAUSED' && !a.reason_codes.includes('ALREADY_PROCESSED')))) return fallback;
    return {...a, label: fallback.label};
  }
  function safeLink(url) { return typeof url === 'string' && url.startsWith(github) && !/[\s<>]/.test(url); }
  function time(value) {
    if (!value || !Number.isFinite(Date.parse(value))) return 'Unknown';
    return new Intl.DateTimeFormat('en-US', {dateStyle: 'medium', timeStyle: 'long', timeZone: 'America/Chicago'}).format(new Date(value));
  }
  function render(payload) {
    const host = document.getElementById('account-health-rows');
    if (!host) return;
    host.replaceChildren();
    for (const id of ids) {
      const a = checked(payload, id), card = document.createElement('article');
      card.className = 'health-account'; card.dataset.account = id;
      const title = document.createElement('h3'); title.textContent = a.label;
      const badge = document.createElement('strong'); badge.className = 'health-badge ' + a.status.toLowerCase();
      badge.textContent = a.status; badge.setAttribute('aria-label', a.label + ' health: ' + a.status);
      card.append(title, badge);
      const dl = document.createElement('dl');
      for (const [label, value] of [
        ['Expected completed session', a.expected_session || 'Unknown'],
        ['Last verified data session', a.last_verified_data_session || 'Unknown'],
        ['Last successful account advancement', a.last_successful_account_advancement || 'Unconfirmed'],
        ['Saved valuation label', a.last_recorded_valuation || 'Unknown'],
        ['Data freshness', a.data_fresh ? 'Fresh accepted data; account status checked separately' : 'Historical or unverified; not fresh data'],
        ['Last checked (Chicago)', time(a.checked_at)]]) {
        const dt = document.createElement('dt'), dd = document.createElement('dd'); dt.textContent = label; dd.textContent = value; dl.append(dt, dd);
      }
      card.append(dl);
      for (const explanation of a.explanations) { const p = document.createElement('p'); p.textContent = explanation; card.append(p); }
      const codes = document.createElement('p'); codes.className = 'small'; codes.textContent = 'Reason codes: ' + a.reason_codes.join(', '); card.append(codes);
      if (Array.isArray(a.accounts)) for (const child of a.accounts.filter(x => x && typeof x.id === 'string')) {
        const p = document.createElement('p'); p.className = 'small'; p.textContent = child.id + ': BLOCKED · saved label ' + (child.last_recorded_valuation || 'Unknown'); card.append(p);
      }
      const links = [...a.evidence];
      if (a.workflow && safeLink(a.workflow.url)) links.push(a.workflow.url);
      for (const url of links.filter(safeLink)) { const link = document.createElement('a'); link.href = url; link.textContent = url.includes('/actions/runs/') ? 'Actions run evidence' : url.split('/').slice(-2).join('/'); card.append(link); }
      host.append(card);
    }
  }
  root.AccountHealth = {checked, expected, safeLink};
  if (typeof module !== 'undefined') module.exports = root.AccountHealth;
  if (typeof document !== 'undefined') {
    let payload = null;
    render(payload);
    fetch('account-health/status.json', {cache: 'no-store'}).then(r => { if (!r.ok) throw Error('Health artifact unavailable'); return r.json(); }).then(p => {payload = p; render(payload);}).catch(() => render(null));
    setInterval(() => render(payload), 60000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) render(payload); });
  }
})(typeof window !== 'undefined' ? window : globalThis);
