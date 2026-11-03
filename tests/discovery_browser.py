"""Offline populated archive browser regression. Generate discovery_fixtures.py first."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
fixtures=json.loads((ROOT/'work/discovery-fixtures.json').read_text())
# Attack-shaped titles must stay inert even in an integrity-valid saved fixture.
fixtures['full']['sources'][0]['source']['title']='<img src=x onerror="window.untrustedExecuted=true">'
fixtures['full']['candidates'][0]['candidate']['source']['title']='<script>window.untrustedExecuted=true</script>'
raws={r['week_start']+'.json':json.dumps(r).encode() for r in fixtures.values()}
entries=[dict(week_start=key[:-5],path=key,sha256=hashlib.sha256(raw).hexdigest()) for key,raw in raws.items()]
index=dict(schema_version=1,reports=sorted(entries,key=lambda e:e['week_start'],reverse=True))
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1280,'height':900})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    broken=False
    def route(request):
        url=request.request.url
        if url.startswith('https://raw.githubusercontent.com/'):
            path=ROOT/url.split('/main/',1)[1]
            request.fulfill(status=200 if path.is_file() else 404,body=path.read_bytes() if path.is_file() else b'Unavailable')
        elif url.startswith('https://s.tradingview.com/'):
            request.fulfill(body='<p>External chart omitted.</p>',content_type='text/html')
        elif url.startswith('https://dashboard.test/'):
            path=urlparse(url).path.lstrip('/') or 'index.html'
            if path=='strategy-discovery/index.json':request.fulfill(body=json.dumps(index),content_type='application/json')
            elif path.startswith('strategy-discovery/'):
                name=path.split('/')[-1]
                request.fulfill(status=503 if broken else 200,body=b'Unavailable' if broken else raws[name],content_type='application/json')
            else:
                local=ROOT/'docs'/path
                request.fulfill(status=200 if local.is_file() else 404,body=local.read_bytes() if local.is_file() else b'Not found',content_type='text/javascript' if path.endswith('.js') else 'text/css' if path.endswith('.css') else 'text/html')
        else:request.abort()
    page.route('**/*',route)
    page.goto('https://dashboard.test/')
    expect(page.locator('#discovery-status')).to_contain_text('RECORDED FIXTURE REVIEWS')
    expect(page.locator('#discovery-summary')).to_contain_text('Ambiguous: 1')
    expect(page.locator('#discovery-simulation')).to_have_text('Simulation: UNVALIDATED · Historical evidence: UNVALIDATED')
    assert page.locator('#discovery-results tr').count()==1
    assert page.locator('#strategy-discovery img,#strategy-discovery script').count()==0
    assert page.evaluate('window.untrustedExecuted') is None
    page.locator('.sidebar a[href="#strategy-discovery"]').click()
    expect(page.locator('#strategy-discovery')).to_be_focused()
    page.locator('#discovery-archive').select_option('2026-10-12')
    expect(page.locator('#discovery-status')).to_contain_text('EMPTY · 2026-10-12')
    expect(page.locator('#discovery-results')).to_contain_text('NOT RUN')
    page.locator('#discovery-archive').select_option('2026-10-19')
    expect(page.locator('#discovery-status')).to_contain_text('RECORDED FIXTURE REVIEWS')
    for width in (320,375,768,1280):
        page.set_viewport_size({'width':width,'height':900})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
    broken=True
    page.locator('#discovery-archive').select_option('2026-10-12')
    expect(page.locator('#discovery-status')).to_contain_text('unavailable or invalid')
    assert page.locator('#discovery-results tr').count()==0
    page.locator('#crypto').click();expect(page.locator('#status')).to_have_text('Loaded')
    expect(page.locator('#report-status')).to_contain_text('Simulated forward paper records')
    assert not errors,errors
    browser.close()
print('PASS: populated/empty archives, switching, failed report clears results, inert source text, disclosure states, responsive layout, navigation and existing portfolio/performance behavior')
