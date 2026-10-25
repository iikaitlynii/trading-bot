"""Optional Chromium smoke checks: python tests/dashboard_browser.py.

Requires Playwright and Chromium; no external market services are contacted.
"""
from pathlib import Path
from threading import Thread
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import csv
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
(ROOT / 'work').mkdir(exist_ok=True)
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT / 'docs')))
Thread(target=server.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{server.server_port}/'
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
    page = browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror', lambda e: errors.append(str(e)))
    def fixtures(route):
        name = route.request.url.split('/main/', 1)[1]
        path = ROOT / name
        route.fulfill(status=200 if path.is_file() else 404, body=path.read_bytes() if path.is_file() else b'Not found', content_type='text/csv')
    page.route('https://raw.githubusercontent.com/**', fixtures)
    page.route('https://s.tradingview.com/**', lambda route: route.fulfill(body='<p>External chart omitted in offline verification.</p>', content_type='text/html'))
    page.goto(url)
    expect(page.locator('#status')).to_have_text('Loaded')
    assert page.locator('main h2').count() == 20
    for kind, folder in [('crypto','crypto_paper'),('stocks','paper')]:
        page.locator('#'+kind).click()
        expect(page.locator('#status')).to_have_text('Loaded')
        expect(page.locator('#'+kind)).to_have_attribute('aria-pressed','true')
        expect(page.locator('#portfolio-context')).to_have_text(kind.title()+' · simulated portfolio')
        with (ROOT/folder/'performance.csv').open() as f: last=list(csv.DictReader(f))[-1]
        expect(page.locator('#value')).to_have_text('${:,.2f}'.format(float(last['paper_value'])))
    page.goto(url)
    page.keyboard.press('Tab')
    expect(page.locator('.skip-link')).to_be_focused()
    page.keyboard.press('Enter')
    expect(page.locator('#dashboard')).to_be_focused()
    for link in page.locator('.sidebar a').all():
        link.focus(); page.keyboard.press('Enter')
        target = link.get_attribute('href')
        expect(page.locator(target)).to_be_focused()
        expect(link).to_have_attribute('aria-current','location')
    page.go_back()
    expect(page.locator('.sidebar a[href="#weekly-report"]')).to_have_attribute('aria-current','location')
    for width in [320,375,480,640,768,1024,1440]:
        page.set_viewport_size({'width':width,'height':900})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Page overflow at {width}'
        for control in page.locator('.sidebar a, button, select, input').all():
            if control.is_visible(): assert control.bounding_box()['height'] >= 44, f'Small target at {width}'
    page.set_viewport_size({'width':320,'height':900})
    table = page.locator('.table-wrap').first
    table.focus(); page.keyboard.press('ArrowRight')
    page.wait_for_timeout(200)
    assert table.evaluate('(el)=>el.scrollLeft')>0
    assert page.locator('thead th:not([scope="col"])').count()==0
    page.locator('#ticker-select').select_option('MSFT')
    expect(page.locator('#analysis-trend')).not_to_have_text('—')
    page.locator('#qt-q4').fill('110')
    expect(page.locator('#qt-summary')).to_contain_text('+10.00%')
    expect(page.locator('#weekly-rows tr').first).to_be_attached()
    page.locator('#watch-score').select_option('80')
    page.locator('#crypto-min-liquidity').select_option(index=1)
    assert not errors, errors
    page.set_viewport_size({'width':1440,'height':1000})
    page.goto(url); expect(page.locator('#status')).to_have_text('Loaded')
    page.screenshot(path=str(ROOT/'work/desktop.png'))
    page.set_viewport_size({'width':375,'height':900})
    page.screenshot(path=str(ROOT/'work/mobile.png'))
    print('PASS: saved Stocks/Crypto values, all panels, keyboard links/skip/back, table scrolling, 7 viewport widths, 44px controls, research and report smoke checks; no JavaScript errors')
    page.route('https://raw.githubusercontent.com/**/paper/performance.csv', lambda route: route.fulfill(status=503, body='Unavailable'))
    page.reload()
    expect(page.locator('#error')).to_be_visible()
    expect(page.locator('#status')).to_have_text('Unavailable')
    page.locator('.sidebar a[href="#weekly-report"]').click()
    expect(page.locator('#weekly-report')).to_be_focused()
    print('PASS: Reports navigation remains usable when portfolio data fails')
    # Verify native links remain available without scripts or network data.
    context=browser.new_context(java_script_enabled=False, viewport={'width':320,'height':900})
    offline=context.new_page(); offline.route('https://**',lambda r:r.abort()); offline.goto(url)
    offline.locator('.sidebar a[href="#weekly-report"]').click()
    assert offline.url.endswith('#weekly-report')
    print('PASS: no-JavaScript Reports navigation')
    browser.close()
server.shutdown()
