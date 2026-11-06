"""Offline redesign regression checks and before/after review screenshots.

Saved CSV values remain the source of truth. No market service is contacted.
"""
from pathlib import Path
import csv
import subprocess
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect
from browser_runtime import launch_chromium

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests/editorial_visual'
OUT.mkdir(exist_ok=True)
before = False
failed = False
with sync_playwright() as p:
    browser = launch_chromium(p)
    page = browser.new_page(viewport={'width':1440,'height':1100}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def route(r):
        u = urlparse(r.request.url)
        if u.hostname == 'dashboard.test':
            name = u.path.lstrip('/') or 'index.html'
            path = ROOT / 'docs' / name
            body = subprocess.check_output(['git','show',f'402a308837bfc7256af6fc4da9f159bfdf30f63b:docs/{name}'],cwd=ROOT) if before and name in ('index.html','dashboard.js','dashboard.css') else path.read_bytes() if path.is_file() else b''
            r.fulfill(status=200 if body else 404, body=body, content_type='text/javascript' if name.endswith('.js') else 'text/css' if name.endswith('.css') else 'application/json' if name.endswith('.json') else 'font/woff2' if name.endswith('.woff2') else 'text/html')
        elif u.hostname == 'raw.githubusercontent.com':
            path = ROOT / u.path.split('/main/',1)[1]
            r.fulfill(status=503 if failed or not path.is_file() else 200, body=path.read_bytes() if path.is_file() else b'Unavailable',content_type='text/csv')
        else:
            r.fulfill(body='<p>External chart omitted in offline review.</p>',content_type='text/html')
    page.route('**/*',route)
    for before in (True,False):
        for width in (1440,375):
            page.set_viewport_size({'width':width,'height':1100})
            page.goto('https://dashboard.test/')
            expect(page.locator('#value')).not_to_have_text('—')
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(OUT/f'{"before" if before else "after"}-{width}.png'),full_page=False)
    for kind, folder in [('crypto','crypto_paper'),('stocks','paper')]:
        page.locator('#'+kind).click()
        with (ROOT/folder/'performance.csv').open() as f: last=list(csv.DictReader(f))[-1]
        expect(page.locator('#value')).to_have_text('${:,.2f}'.format(float(last['paper_value'])))
        expect(page.locator('#asof')).to_contain_text(last['date_utc'])
    expect(page.locator('.feature-card')).to_have_count(3)
    expect(page.locator('#chart')).to_be_visible()
    expect(page.locator('#ai-copilot')).not_to_be_visible()
    for width in (320,375,768,1024,1440):
        page.set_viewport_size({'width':width,'height':1000})
        for target in ('overview','markets','ai-copilot','strategy-lab','account-health','settings'):
            link=page.locator(f'.sidebar a[href="#{target}"]')
            link.focus(); page.keyboard.press('Enter')
            expect(link).to_have_attribute('aria-current','page')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width,target)
            for control in page.locator('button,select,input,.sidebar a').all():
                if control.is_visible(): assert control.bounding_box()['height'] >= 44
    page.goto('https://dashboard.test/#chart-intelligence')
    expect(page.locator('#ci-demo')).to_be_visible()
    page.locator('#ci-window').select_option('30')
    expect(page.locator('#ci-status')).to_contain_text('SYNTHETIC')
    page.goto('https://dashboard.test/#trade-history')
    expect(page.locator('#trades')).to_be_visible()
    page.go_back();expect(page.locator('#ci-demo')).to_be_visible()
    failed=True
    page.reload()
    page.goto('https://dashboard.test/#overview')
    expect(page.locator('#error')).to_be_visible()
    page.locator('.sidebar a[href="#account-health"]').click()
    expect(page.locator('#account-health')).to_be_visible()
    assert not errors, errors
    browser.close()
print('PASS: before/after screenshots; saved Stocks/Crypto values; six views; keyboard/back/deep links; five widths; 44px targets; chart interactions; failed-data navigation.')
