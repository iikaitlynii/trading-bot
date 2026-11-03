"""Offline browser acceptance with controlled missing/corrupt research reports."""
import json
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1280,'height':1000})
    mode='valid'
    def route(request):
        url=request.request.url
        if url.startswith('https://dashboard.test/'):
            name=urlparse(url).path.lstrip('/') or 'index.html'
            local=ROOT/'docs'/name
            if name=='volume-profile/report.json' and mode!='valid':
                report=json.loads(local.read_text());report['profiles'][0]['bins'][0]['volume']=-1
                request.fulfill(status=503 if mode=='missing' else 200,body=json.dumps(report),content_type='application/json')
            else:
                request.fulfill(status=200 if local.is_file() else 404,body=local.read_bytes() if local.is_file() else b'Unavailable',content_type='text/javascript' if name.endswith('.js') else 'text/css' if name.endswith('.css') else 'application/json' if name.endswith('.json') else 'text/html')
        else:request.abort()
    page.route('**/*',route)
    page.goto('https://dashboard.test/')
    expect(page.locator('#vp-status')).to_contain_text('APPROXIMATE')
    expect(page.locator('#vp-chart .vp-row')).to_have_count(24)
    expect(page.locator('#vp-metrics')).to_contain_text('LVN (approx.)')
    expect(page.locator('#discovery-status')).to_contain_text('NOT RUN')
    for symbol in ('MSFT','NVDA','AMZN','AAPL'):
        page.select_option('#vp-symbol',symbol)
        for window in ('20','60','120'):
            page.select_option('#vp-window',window)
            for bins in ('12','24','48'):
                page.select_option('#vp-bins',bins)
                expect(page.locator('#vp-chart .vp-row')).to_have_count(int(bins))
    page.select_option('#vp-window','60');page.select_option('#vp-bins','24')
    for width in (320,375,768,1280):
        page.set_viewport_size({'width':width,'height':1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
    page.locator('#volume-profile').scroll_into_view_if_needed()
    page.locator('#volume-profile').screenshot(path=str(ROOT/'work/volume-profile-desktop.png'))
    page.set_viewport_size({'width':375,'height':1000});page.locator('#volume-profile').scroll_into_view_if_needed()
    page.locator('#volume-profile').screenshot(path=str(ROOT/'work/volume-profile-mobile.png'))
    mode='corrupt';page.reload();page.select_option('#vp-window','20');page.select_option('#vp-bins','12')
    expect(page.locator('#vp-status')).to_contain_text('FAILED');expect(page.locator('#vp-chart .vp-row')).to_have_count(0)
    mode='missing';page.reload();expect(page.locator('#vp-status')).to_contain_text('FAILED')
    expect(page.locator('#vp-metrics')).to_be_empty()
    browser.close()
print('PASS: 36 profile selections, approximate labels, Discovery NOT RUN status preserved, 4 responsive widths, corrupt/missing reports clear metrics and chart')
