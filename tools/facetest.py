#!/usr/bin/env python3
"""Click-test the pedal face with mod-ui's own widget code in headless Chromium.

  git clone --depth 1 https://github.com/mod-audio/mod-ui.git /tmp/mod-ui
  make && MODUI=/tmp/mod-ui python3 tools/facetest.py

Loads bin/nhe-ec280.lv2's template, stylesheet and script into mod-ui's
html/js/modgui.js (jQuery 1.9.1), builds the port list from the TTL, then
clicks and taps every switch and button bank and checks what reaches the host.
Needs playwright (Chromium) and rdflib.
"""
import os, sys, json
import rdflib
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, 'bin', 'nhe-ec280.lv2')
M = os.path.join(os.environ.get('MODUI', '/tmp/mod-ui'), 'html', 'js')
LIBS = ['lib/jquery-1.9.1.min.js', 'lib/sprintf-0.6.js', 'lib/jquery-ui-1.10.1.custom.min.js',
        'lib/jquery.mousewheel.min.js', 'lib/jquery.ba-resize.min.js', 'lib/mustache.js', 'common.js', 'modgui.js']
LV2 = rdflib.Namespace('http://lv2plug.in/ns/lv2core#')
RDFS = rdflib.Namespace('http://www.w3.org/2000/01/rdf-schema#')

def ports():
    g = rdflib.Graph(); g.parse(os.path.join(B, 'nhe-ec280.ttl'), format='turtle')
    ctl = []
    for p in g.objects(None, LV2.port):
        if (p, rdflib.RDF.type, LV2.ControlPort) not in g:
            continue
        sym = str(g.value(p, LV2.symbol))
        if sym == 'lv2_enabled':
            continue
        ctl.append(dict(index=int(g.value(p, LV2['index'])), symbol=sym, name=str(g.value(p, LV2.name)),
                        ranges=dict(minimum=float(g.value(p, LV2.minimum)), maximum=float(g.value(p, LV2.maximum)),
                                    default=float(g.value(p, LV2.default))),
                        properties=[str(o).split('#')[-1] for o in g.objects(p, LV2.portProperty)],
                        scalePoints=sorted([dict(value=float(g.value(s, rdflib.RDF.value)), label=str(g.value(s, RDFS.label)))
                                            for s in g.objects(p, LV2.scalePoint)], key=lambda d: d['value']),
                        units={}, designation='', rangeSteps=0))
    ctl.sort(key=lambda d: d['index'])
    return dict(control=dict(input=ctl, output=[]), audio=dict(input=[dict(symbol='in', name='In')],
                output=[dict(symbol='out_mix', name='Mix'), dict(symbol='out_echo', name='Echo only')]),
                cv=dict(input=[], output=[]), midi=dict(input=[], output=[]))

def page(tpl, css, js):
    effect = dict(uri='https://github.com/Kiwooky/NHE-EC280', name='Electronic Echo 280', brand='x', label='x',
                  gui=dict(iconTemplate=tpl, javascript='x'), ports=ports(), parameters=[], presets=[])
    scripts = ''.join('<script>%s</script>' % open(os.path.join(M, l)).read() for l in LIBS)
    return """<html><head><style>%s</style><script>var isSDK=true, desktop=null, VERSION='1';</script>%s</head>
<body style="margin:0"><div id="host" style="position:relative;left:20px;top:20px"></div><script>
window.log=[];
var gui=new GUI(%s, {loadDependencies:false, change:function(s,v){log.push(s+'='+v)}, bypassed:false});
var method; eval('method = ' + %s); gui.jsCallback = method;
gui.render(null, function(icon){ jQuery('#host').append(icon); }, true);
</script></body></html>""" % (css, scripts, json.dumps(effect), json.dumps(js))

def main():
    tpl = open(os.path.join(B, 'modgui', 'icon-ec280.html')).read()
    css = open(os.path.join(B, 'modgui', 'stylesheet-ec280.css')).read()
    css = css.replace('{{{cns}}}', '_sdk').replace('{{{ns}}}', '').replace('/resources/', 'file://' + B + '/modgui/')
    js = open(os.path.join(B, 'modgui', 'script-ec280.js')).read()
    tmp = os.path.join(ROOT, 'build', 'facetest.html')
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    open(tmp, 'w').write(page(tpl, css, js))
    fails = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for touch in (False, True):
            ctx = b.new_context(has_touch=touch, viewport={'width': 800, 'height': 500}); pg = ctx.new_page()
            errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.goto('file://' + tmp); pg.wait_for_timeout(800)
            def press(cls, hold=0, wobble=False):
                bb = pg.locator('.' + cls).bounding_box(); x, y = bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2
                if touch:
                    pg.touchscreen.tap(x, y)
                else:
                    pg.mouse.move(x, y); pg.mouse.down()
                    if wobble: pg.mouse.move(x + 2, y - 2)
                    pg.wait_for_timeout(hold or 60); pg.mouse.up()
                pg.wait_for_timeout(200)
            for c, sym, start in (('ec-tails', 'tails', 1), ('ec-range', 'range', 0), ('ec-mode', 'mode', 0)):
                for i in range(3):
                    press(c, wobble=(i == 1))
                want = ['%s=%d' % (sym, v) for v in ((1 - start), start, (1 - start))]
                got = [l for l in pg.evaluate('log') if l.startswith(sym + '=')]
                ok = got == want
                print(('PASS ' if ok else 'FAIL ') + '%s %s three presses -> %s' % ('touch' if touch else 'mouse', sym, got))
                if not ok: fails.append(sym)
            press('ec-E3'); 
            if not touch: press('ec-E1', hold=700)
            got = [l for l in pg.evaluate('log') if l.startswith('echo_taps=')]
            want = ['echo_taps=4'] + ([] if touch else ['echo_taps=5'])
            ok = got == want
            print(('PASS ' if ok else 'FAIL ') + '%s echo bank tap/hold -> %s' % ('touch' if touch else 'mouse', got))
            if not ok: fails.append('bank')
            pg.evaluate("gui.setPortWidgetsValue('range', 1, null, false)"); pg.wait_for_timeout(100)
            ok = pg.evaluate("jQuery('.ec-range').hasClass('lit')") is True
            print(('PASS ' if ok else 'FAIL ') + 'host change lights range')
            if not ok: fails.append('host')
            if errs: print('FAIL page errors', errs); fails.append('errors')
            ctx.close()
        b.close()
    print('\n%d failures' % len(fails))
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
