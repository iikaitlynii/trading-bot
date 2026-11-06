"use strict";
// Move existing nodes, preserving IDs, event listeners, data and warning text.
(() => {
  const main = document.querySelector('main');
  const original = [...main.children];
  const views = {};
  for (const [id, title, description] of [
    ['overview', '', ''], ['markets', 'Markets', 'Explore saved prices and chart research.'],
    ['strategy-lab', 'Strategy Lab', 'Test ideas and review historical evidence.'],
    ['health-view', 'Account Health', 'Review data quality, reports, and simulated records.'],
    ['copilot-view', 'AI Copilot', 'Explore evidence before a simulated decision.'],
    ['settings', 'Settings', 'This dashboard is read-only. No brokerage account is connected.']
  ]) {
    const view = document.createElement('div');
    view.id = id; view.className = 'editorial-view'; view.tabIndex = -1;
    if (title) {
      const h = document.createElement('h1'); h.textContent = title;
      const p = document.createElement('p'); p.textContent = description;
      view.append(h, p);
    }
    main.append(view); views[id] = view;
  }
  const welcome = document.createElement('section');
  welcome.className = 'welcome';
  welcome.innerHTML = '<p>WELCOME BACK</p><h1>Kaitlyn</h1><p>YOUR SPACE TO LEARN &amp; EXPLORE</p><span class="welcome-seal" aria-hidden="true">KR</span>';
  views.overview.append(welcome);
  for (const node of original) {
    let view = 'strategy-lab';
    if (node.matches('.intro, #portfolio-context, #error, [aria-label="Portfolio metrics"], footer')) view = 'overview';
    else if (node.matches('.main')) {
      const chart = node.querySelector('#chart').closest('section');
      views.overview.append(chart); chart.classList.add('equity-card');
      views['health-view'].append(...node.children); node.remove(); continue;
    } else if (node.id === 'ai-copilot') view = 'copilot-view';
    else if (node.id === 'account-health' || node.matches('[aria-label="Profit breakdown"], #performance-reports, #weekly-report') || node.querySelector('#quality-status, #trades')) view = 'health-view';
    else if (node.matches('#chart-research, #chart-intelligence, #volume-profile') || node.querySelector('#crypto-research')) view = 'markets';
    views[view].append(node);
  }
  const features = document.createElement('div'); features.className = 'feature-cards';
  for (const [href, icon, title, text] of [
    ['markets', '◇', 'Markets', 'Charts, prices, and saved research.'],
    ['ai-copilot', '✧', 'AI Copilot', 'Simple analysis. Evidence first.'],
    ['account-health', '♡', 'Account Health', 'Data status and system updates.']
  ]) {
    const a = document.createElement('a'); a.href = '#' + href; a.className = 'feature-card';
    a.innerHTML = `<span class="feature-icon" aria-hidden="true">${icon}</span><h2>${title}</h2><p>${text}</p><span class="feature-arrow" aria-hidden="true">›</span>`;
    features.append(a);
  }
  views.overview.append(features);
  const footer = views.overview.querySelector('footer'); if (footer) views.overview.append(footer);
  function route() {
    const id = decodeURIComponent(location.hash.slice(1)) || 'overview';
    const target = document.getElementById(id);
    const active = target?.closest('.editorial-view') || views.overview;
    for (const view of Object.values(views)) view.hidden = id !== 'all' && view !== active;
    if (target && location.hash && id !== 'all') target.focus({preventScroll:true});
    const navId = {'health-view':'account-health','copilot-view':'ai-copilot'}[active.id] || active.id;
    document.querySelectorAll('.sidebar a').forEach(a => {
      if (a.hash === '#' + navId) a.setAttribute('aria-current','page');
      else a.removeAttribute('aria-current');
    });
  }
  window.addEventListener('hashchange', route); route();
})();
