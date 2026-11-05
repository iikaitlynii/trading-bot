"""Offline Chromium + reviewed screenshot baselines. --update refreshes baselines.

Synthetic fixtures exercise UI states, never claim verified historical outcomes.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect
from PIL import Image, ImageChops

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/copilot-browser';OUT.mkdir(parents=True,exist_ok=True)
BASE=ROOT/'tests/copilot_visual';BASE.mkdir(exist_ok=True)
NOW='2026-11-04T23:00:00Z'
script="const f=require('./tests/copilot_engine_test.js');process.stdout.write('FIXTURE:'+JSON.stringify(f.fixture()));"
text=subprocess.check_output(['node','-e',script],cwd=ROOT,text=True)
fixture=json.JSONDecoder().raw_decode(text.split('FIXTURE:')[1])[0]
mode='BUY'
network=[]


def record():
    x=json.loads(json.dumps(fixture))
    if mode=='SELL':
        for i,b in enumerate(x['bars']):b.update(close=200-i,high=202-i,low=198-i)
    if mode=='WAIT':x.update(quality='BLOCKED',reason='Synthetic missing-evidence test')
    if mode=='STALE':x['valid_until']='2026-11-04T22:30:00Z'
    return json.dumps({'schema_version':1,'observed_at':x['observed_at'],'observations':[{**x,'symbol':s} for s in ['AAPL','MSFT','NVDA','AMZN']]},sort_keys=True).encode()


with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1280,'height':900},device_scale_factor=1)
    page.clock.install(time=datetime(2026,11,4,23,tzinfo=timezone.utc))
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def route(r):
        network.append((r.request.method,r.request.url))
        url=r.request.url
        if url.startswith('https://dashboard.test/'):
            name=urlparse(url).path.lstrip('/') or 'index.html'
            data=record();sha=hashlib.sha256(data).hexdigest()
            if name=='copilot/latest.json':
                if mode=='MISSING':r.fulfill(status=404,body='Unavailable');return
                r.fulfill(json={'schema_version':1,'path':'observations/'+sha+'.json','sha256':sha});return
            if name.startswith('copilot/observations/'):
                r.fulfill(body=data if mode!='TAMPER' else data+b' ',content_type='application/json');return
            local=ROOT/'docs'/name
            r.fulfill(status=200 if local.is_file() else 404,body=local.read_bytes() if local.is_file() else b'Not found',content_type='text/javascript' if name.endswith('.js') else 'text/css' if name.endswith('.css') else 'application/json' if name.endswith('.json') else 'text/html');return
        if url.startswith('https://raw.githubusercontent.com/') and '/main/' in url:
            path=ROOT/url.split('/main/',1)[1]
            r.fulfill(status=200 if path.is_file() else 404,body=path.read_bytes() if path.is_file() else b'Not found');return
        r.fulfill(status=404,body='Offline test')
    page.route('**/*',route)
    for width in [375,1280]:
        page.set_viewport_size({'width':width,'height':900})
        for state in ['BUY','SELL','WAIT']:
            mode=state;page.goto(f'https://dashboard.test/?case={state}-{width}#ai-copilot')
            expect(page.locator('#cp-signal')).to_have_attribute('data-state',state)
            expect(page.locator('#cp-profile')).to_contain_text('APPROXIMATE')
            page.locator('#ai-copilot').scroll_into_view_if_needed()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            for control in page.locator('#ai-copilot select,#ai-copilot input,#ai-copilot textarea,#ai-copilot button').all():
                assert control.bounding_box()['height']>=44
            page.locator('#cp-symbol').focus();expect(page.locator('#cp-symbol')).to_be_focused()
            page.locator('#cp-symbol').blur()
            page.evaluate('document.fonts.ready')
            target=OUT/f'{state.lower()}-{width}.png'
            page.locator('#ai-copilot').screenshot(path=str(target),animations='disabled')
            baseline=BASE/target.name
            if '--update' in sys.argv:baseline.write_bytes(target.read_bytes())
            assert baseline.exists(),f'Missing baseline: {baseline}; review and use --update'
            a,b=Image.open(target).convert('RGB'),Image.open(baseline).convert('RGB')
            assert a.size==b.size,f'Visual dimensions changed: {target.name}'
            diff=ImageChops.difference(a,b)
            # Small renderer anti-alias variation allowed; layout/color changes fail.
            changed=sum(max(pixel)>25 for pixel in diff.getdata())
            assert changed/(a.width*a.height)<0.001,f'Visual regression {target.name}: {changed} pixels'
    for state in ['STALE','MISSING','TAMPER']:
        mode=state;page.reload();expect(page.locator('#cp-signal')).to_have_attribute('data-state','WAIT')
    mode='BUY';page.reload();expect(page.locator('#cp-signal')).to_have_attribute('data-state','BUY')
    page.clock.fast_forward(24*60*60*1000)
    expect(page.locator('#cp-signal')).to_have_attribute('data-state','WAIT')
    page.clock.set_fixed_time(datetime(2026,11,4,23,tzinfo=timezone.utc));page.reload()
    expect(page.locator('#cp-signal')).to_have_attribute('data-state','BUY')
    # A synthetic local image contains no real private screenshot.
    baseline_storage=page.evaluate('JSON.stringify(localStorage)')
    image=OUT/'test-chart.png';Image.new('RGB',(640,360),'#242424').save(image)
    page.locator('#cp-image').set_input_files(str(image))
    expect(page.locator('#cp-image-status')).to_contain_text('Private local preview')
    expect(page.locator('#cp-signal')).to_have_attribute('data-state','WAIT')
    page.locator('#cp-labels').fill('<img src=x onerror=alert(1)> uncertain labels')
    assert page.locator('#cp-labels img').count()==0
    assert not [r for r in network if r[0] not in ('GET','HEAD')],network
    assert page.evaluate('JSON.stringify(localStorage)')==baseline_storage
    page.locator('#cp-return').click()
    expect(page.locator('#cp-preview')).to_be_hidden();expect(page.locator('#cp-labels')).to_have_value('')
    expect(page.locator('#cp-signal')).to_have_attribute('data-state','BUY')
    for payload in [dict(name='bad.svg',mimeType='image/svg+xml',buffer=b'<svg onload="alert(1)"/>'),dict(name='fake.png',mimeType='image/png',buffer=b'not an image')]:
        page.locator('#cp-image').set_input_files(payload)
        expect(page.locator('#cp-image-status')).to_contain_text('REJECTED')
        expect(page.locator('#cp-signal')).to_have_attribute('data-state','WAIT')
    tiny=OUT/'tiny.png';Image.new('RGB',(10,10)).save(tiny)
    page.locator('#cp-image').set_input_files(str(tiny));expect(page.locator('#cp-image-status')).to_contain_text('REJECTED')
    assert not errors,errors
    browser.close()
print('PASS: six screenshot baselines; mobile reflow/touch/keyboard; BUY/SELL/WAIT; expiry/missing/tamper; local-only uploads, invalid formats, clearing and injection safety')
