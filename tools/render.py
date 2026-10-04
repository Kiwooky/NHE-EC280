#!/usr/bin/env python3
"""Render the pedal face's screenshot and thumbnail from the built bundle.

Run `make` first, then:  python3 tools/render.py
Writes bundle/nhe-ec280.lv2/modgui/screenshot-ec280.png and thumbnail-ec280.png
(rebuild afterwards to copy them into bin/). Shows the default settings:
E1 and R1 down, Echo, 300 ms, Tail on, effect on. Needs playwright (Chromium)
and pillow.
"""
import re, os, asyncio
from playwright.async_api import async_playwright
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, 'bin', 'nhe-ec280.lv2', 'modgui')
OUT = os.path.join(ROOT, 'bundle', 'nhe-ec280.lv2', 'modgui')

html = open(R + '/icon-ec280.html').read()
css = open(R + '/stylesheet-ec280.css').read()
html = re.sub(r'\{\{#effect.*?\{\{/effect[^}]*\}\}', '', html, flags=re.S)
html = html.replace('{{{cns}}}', '').replace('{{{ns}}}', '')
css = css.replace('{{{cns}}}', '').replace('{{{ns}}}', '').replace('/resources/', 'file://' + R + '/')

def knob(v):
    return '-%dpx 0' % (round(v / 10 * 64) * 56)

state = {'return_level': 6, 'duration': 4, 'speed': 5, 'volume': 5, 'chorus': 2}
extra = ''.join('.ec280 .ec-%s{background-position:%s}' % (k, knob(v)) for k, v in state.items())
extra += '.ec280 .ec-onoff{background-position:-40px 0}'
page = '<html><head><style>body{margin:0;background:transparent}%s%s</style></head><body>%s</body></html>' % (css, extra, html)
page = page.replace('class="ec-switch ec-tails"', 'class="ec-switch ec-tails lit"')
page = page.replace('class="ec-bank ec-E1"', 'class="ec-bank ec-E1 down"').replace('class="ec-bank ec-R1"', 'class="ec-bank ec-R1 down"')
tmp = os.path.join(ROOT, 'build', 'face.html')
os.makedirs(os.path.dirname(tmp), exist_ok=True)
open(tmp, 'w').write(page)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 650, 'height': 400})
        await pg.goto('file://' + tmp)
        await pg.wait_for_timeout(300)
        await pg.screenshot(path=os.path.join(ROOT, 'build', 'screenshot_full.png'), omit_background=True)
        await b.close()

asyncio.run(main())
im = Image.open(os.path.join(ROOT, 'build', 'screenshot_full.png')).convert('RGBA')
im.quantize(256, method=Image.Quantize.FASTOCTREE).save(OUT + '/screenshot-ec280.png', optimize=True)
t = im.copy(); t.thumbnail((256, 64), Image.LANCZOS); t.save(OUT + '/thumbnail-ec280.png', optimize=True)
print('screenshot and thumbnail written to', OUT)
