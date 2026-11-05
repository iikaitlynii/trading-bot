"""Offline Chromium behavior and deterministic responsive screenshot checks."""
from pathlib import Path
from datetime import datetime, timezone
import json
import sys
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright, expect
from browser_runtime import launch_chromium

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/account-health-browser';OUT.mkdir(parents=True,exist_ok=True)
NOW='2026-11-03T04:00:00Z'
BASE='https://github.com/iikaitlynii/trading-bot/'

def fixture():
    rows=[]
    for id,status in [('stock','ACTIVE'),('crypto','PAUSED'),('forward','BLOCKED')]:
        rows.append(dict(id=id,status=status,expected_session='2026-11-02',last_verified_data_session='2026-11-02' if id!='forward' else None,
                         last_recorded_valuation='2026-11-02',last_successful_account_advancement='2026-11-02',
                         checked_at=NOW,expires_at='2026-11-03T21:00:00Z',data_fresh=id!='forward',
                         reason_codes=['ACCOUNT_PUBLISHED' if status=='ACTIVE' else 'ALREADY_PROCESSED' if status=='PAUSED' else 'FORWARD_INPUTS_UNVERIFIED'],
                         explanations=['Synthetic browser fixture; no investment performance claim.'],
                         workflow={'status':'SUCCESS','run_id':42,'url':BASE+'actions/runs/42'},
                         evidence=[BASE+'blob/main/monitoring/account_receipts/'+id+'.json']))
    for r in rows:
        symbols=['AAPL','MSFT','NVDA','AMZN'] if r['id']=='stock' else ['DOGE-USD','SHIB-USD','PEPE-USD','BONK-USD']
        folder='paper' if r['id']=='stock' else 'crypto_paper'
        r['symbols']={s:{'status':'VALIDATED','source_session':'2026-11-02','http_status':200} for s in symbols}
        r['workflow']['run_attempt']=1
        r['publication']={'session':'2026-11-02','output_commit':'a'*40,'bundle_sha256':'b'*64,'run_id':42,'run_attempt':1,'outcome':'ADVANCED' if r['status']=='ACTIVE' else 'ALREADY_PROCESSED','files':{folder+'/'+s:'c'*64 for s in ['state.json','performance.csv','journal.csv','latest_signals.csv']}}
    return dict(schema_version=1,simulation_only=True,accounts=rows)

with sync_playwright() as p:
    browser=launch_chromium(p)
    page=browser.new_page(viewport={'width':1280,'height':900},device_scale_factor=1)
    page.clock.install(time=datetime(2026,11,3,4,tzinfo=timezone.utc))
    payload=fixture(); mode='fixture';errors=[]
    page.on('pageerror',lambda error: errors.append(str(error)))
    def route(r):
        url=r.request.url
        if url.startswith('https://dashboard.test/'):
            name=url.split('https://dashboard.test/',1)[1].split('?',1)[0].split('#',1)[0] or 'index.html'
            if name=='account-health/status.json':
                r.fulfill(status=404 if mode=='missing' else 200,body='invalid' if mode=='invalid' else json.dumps(payload),content_type='application/json');return
            path=ROOT/'docs'/name
            r.fulfill(status=200 if path.is_file() else 404,body=path.read_bytes() if path.is_file() else b'Not found');return
        r.fulfill(status=404,body='External source omitted in offline health test')
    page.route('**/*',route)
    for width in [1280,375]:
        page.set_viewport_size({'width':width,'height':900});page.goto('https://dashboard.test/#account-health')
        expect(page.locator('[data-account="stock"] .health-badge')).to_have_text('ACTIVE')
        expect(page.locator('[data-account="crypto"] .health-badge')).to_have_text('PAUSED')
        expect(page.locator('[data-account="forward"] .health-badge')).to_have_text('BLOCKED')
        expect(page.locator('#account-health')).to_contain_text('America/Chicago')
        expect(page.locator('[data-account="stock"]')).to_contain_text('Nov 2, 2026')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        links=page.locator('#account-health a')
        for link in links.all():assert link.get_attribute('href').startswith(BASE)
        target=page.locator('#account-health');target.scroll_into_view_if_needed();page.evaluate('document.fonts.ready')
        first=OUT/f'health-{width}.png';second=OUT/f'health-{width}-repeat.png'
        target.screenshot(path=str(first),animations='disabled');target.screenshot(path=str(second),animations='disabled')
        a,b=Image.open(first).convert('RGB'),Image.open(second).convert('RGB')
        assert a.size==b.size and ImageChops.difference(a,b).getbbox() is None,'Nondeterministic health screenshot'
        assert a.width<=width and a.height>300
    for mode in ['missing','invalid']:
        page.goto('https://dashboard.test/?mode='+mode+'#account-health');expect(page.locator('.health-badge.blocked')).to_have_count(3)
    mode='unsafe';payload=fixture();payload['accounts'][0]['explanations']=['<img src=x onerror=alert(1)>']
    payload['accounts'][0]['evidence'].append('javascript:alert(1)')
    page.goto('https://dashboard.test/?mode='+mode+'#account-health');expect(page.locator('[data-account="stock"]')).to_contain_text('<img src=x onerror=alert(1)>')
    assert page.locator('#account-health img').count()==0
    assert page.locator('#account-health a[href^="javascript:"]').count()==0
    page.clock.fast_forward(18*3600*1000)
    expect(page.locator('.health-badge.blocked')).to_have_count(3)
    assert not errors,errors
    browser.close()
print('Account health Chromium: statuses, stale open tab, missing/invalid artifacts, safe rendering, responsive layout and repeat screenshots passed.')
