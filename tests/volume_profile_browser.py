"""Offline browser acceptance with controlled missing/corrupt research reports."""
import json
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect
from browser_runtime import launch_chromium

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'work').mkdir(exist_ok=True)
saved=json.loads((ROOT/'docs/volume-profile/report.json').read_text())
with sync_playwright() as p:
    browser=launch_chromium(p)
    page=browser.new_page(viewport={'width':1280,'height':1000})
    mode='valid'
    def route(request):
        url=request.request.url
        if url.startswith('https://dashboard.test/'):
            name=urlparse(url).path.lstrip('/') or 'index.html'
            local=ROOT/'docs'/name
            if name=='volume-profile/report.json' and mode!='valid':
                report=json.loads(local.read_text())
                if mode=='corrupt': report['profiles'][0]['bins'][0]['volume']=-1
                elif mode=='nodes': report['profiles'][0]['hvn']=[None]
                elif mode=='empty':
                    for b in report['profiles'][0]['bins']: b['volume']=0
                elif mode=='label':
                    for item in report['profiles']: item['evidence']='EXACT trade-level volume'
                request.fulfill(status=503 if mode=='missing' else 200,body=json.dumps(report),content_type='application/json')
            else:
                request.fulfill(status=200 if local.is_file() else 404,body=local.read_bytes() if local.is_file() else b'Unavailable',content_type='text/javascript' if name.endswith('.js') else 'text/css' if name.endswith('.css') else 'application/json' if name.endswith('.json') else 'text/html')
        else:request.abort()
    page.route('**/*',route)
    page.goto('https://dashboard.test/#volume-profile')
    expect(page.locator('#vp-status')).to_contain_text('APPROXIMATE')
    expect(page.locator('#vp-chart .vp-row')).to_have_count(24)
    expect(page.locator('#vp-metrics')).to_contain_text('LVN (approx.)')
    expect(page.locator('#discovery-status')).to_contain_text('NOT RUN')
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    assert page.evaluate("new Set([...document.querySelectorAll('[id]')].map(e=>e.id)).size === document.querySelectorAll('[id]').length"), 'Duplicate dashboard IDs'
    for width in (320,375,768,1280):
        page.set_viewport_size({'width':width,'height':1000})
        for symbol in ('MSFT','NVDA','AMZN','AAPL'):
            page.select_option('#vp-symbol',symbol)
            for window in ('20','60','120'):
                page.select_option('#vp-window',window)
                for bins in ('12','24','48'):
                    page.select_option('#vp-bins',bins)
                    expected=next(x for x in saved['profiles'] if (x['symbol'],x['window'],x['bin_count'])==(symbol,int(window),int(bins)))
                    expect(page.locator('#vp-chart .vp-row')).to_have_count(int(bins))
                    expect(page.locator('#vp-status')).to_contain_text('HISTORICAL · APPROXIMATE · UNVALIDATED')
                    expect(page.locator('#vp-status')).to_contain_text(expected['start']+' through '+expected['end'])
                    expect(page.locator('#vp-metrics')).to_contain_text('POC (approx.): '+format(expected['poc'],'.2f'))
                    assert all('≈' in x for x in page.locator('#vp-chart .vp-row').all_text_contents())
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(width,symbol,window,bins)
    page.select_option('#vp-window','60');page.select_option('#vp-bins','24')
    page.set_viewport_size({'width':1280,'height':1000})
    page.locator('#volume-profile').scroll_into_view_if_needed()
    page.locator('#volume-profile').screenshot(path=str(ROOT/'work/volume-profile-desktop.png'))
    page.set_viewport_size({'width':375,'height':1000});page.locator('#volume-profile').scroll_into_view_if_needed()
    page.locator('#volume-profile').screenshot(path=str(ROOT/'work/volume-profile-mobile.png'))
    mode='label';page.reload()
    expect(page.locator('#vp-status')).to_contain_text('APPROXIMATE')
    expect(page.locator('#vp-status')).not_to_contain_text('EXACT')
    for mode in ('corrupt','nodes','empty','missing'):
        page.reload();page.select_option('#vp-window','20');page.select_option('#vp-bins','12')
        expect(page.locator('#vp-status')).to_contain_text('FAILED')
        expect(page.locator('#vp-chart .vp-row')).to_have_count(0)
        expect(page.locator('#vp-metrics')).to_be_empty()
        expect(page.locator('#vp-provenance')).to_be_empty()
    assert not errors,errors
    browser.close()
print('PASS: 144 profile/viewport combinations, saved values and fixed approximation labels, unique IDs, Discovery NOT RUN preserved; malformed/missing reports clear all output; no JS errors')
