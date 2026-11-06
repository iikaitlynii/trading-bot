"""Offline v2 disclosure/rendering and deterministic responsive screenshots."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright, expect
from browser_runtime import launch_chromium

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from simulation_v2.model import new_account, advance, valuation
from simulation_v2.report import build
OUT=ROOT/'work/simulation-v2-browser';OUT.mkdir(parents=True,exist_ok=True)
a=new_account('stock',['<img src=x onerror=alert(1)>'],'1000','2026-11-02T22:00:00Z')
symbol=a['symbols'][0]
a=advance(a,session='2026-11-02',observed_at='2026-11-02T22:00:00Z',retrieved_at='2026-11-02T22:00:00Z',prices={symbol:'100'},signals={symbol:'BULLISH'},input_hash='a'*64)
payload=build();payload['accounts'][0].update(availability='SAVED_SIMULATION',reason='Synthetic browser fixture only.',generation='a'*64,last_session=a['last_session'],assumptions=a['assumptions'],accounting=valuation(a,{symbol:'100'}),positions=a['positions'],pending_orders=a['orders'],fills=a['fills'])
with sync_playwright() as p:
    browser=launch_chromium(p);page=browser.new_page(device_scale_factor=1);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    mode='valid'
    def route(r):
        url=r.request.url
        if url.startswith('https://dashboard.test/'):
            name=url.split('https://dashboard.test/',1)[1].split('?',1)[0].split('#',1)[0] or 'index.html'
            if name=='simulation-v2/status.json':
                r.fulfill(status=404 if mode=='missing' else 200,body='invalid' if mode=='invalid' else json.dumps(payload),content_type='application/json');return
            path=ROOT/'docs'/name;r.fulfill(status=200 if path.is_file() else 404,body=path.read_bytes() if path.is_file() else b'{}');return
        r.fulfill(status=200,body='{}',content_type='application/json')
    page.route('**/*',route)
    for width in [375,1280]:
        page.set_viewport_size({'width':width,'height':900});page.goto('https://dashboard.test/#simulation-v2')
        target=page.locator('#simulation-v2');expect(target).to_contain_text('Pending simulated orders: 1')
        expect(target).to_contain_text('not verified market costs');expect(target).to_contain_text('Cash: 1000')
        expect(target).to_contain_text('SIM_BUY <img');assert target.locator('img').count()==0
        assert page.locator('.health-badge.active').count()==0
        target.scroll_into_view_if_needed();page.evaluate('document.fonts.ready')
        first=OUT/f'v2-{width}.png';second=OUT/f'v2-{width}-repeat.png'
        target.screenshot(path=str(first),animations='disabled');target.screenshot(path=str(second),animations='disabled')
        assert ImageChops.difference(Image.open(first).convert('RGB'),Image.open(second).convert('RGB')).getbbox() is None
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    for mode in ['missing','invalid']:
        page.goto('https://dashboard.test/?mode='+mode+'#simulation-v2');expect(page.locator('#simulation-v2')).to_contain_text('V2 accounting unavailable')
        assert page.locator('#simulation-v2').get_by_text('Cash: 0',exact=True).count()==0
    assert not errors,errors
    browser.close()
print('V2 Chromium: pending orders, assumptions, accounting, safe text, missing evidence and responsive repeat screenshots passed.')
