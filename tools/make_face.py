#!/usr/bin/env python3
"""Build the pedal face's images from the designer's source art (2x retina).

    python3 tools/make_face.py

Reads assets/source/*-v2 (1300 x 800 face, sprites at 2x) and writes the
strips into bundle/nhe-ec280.lv2/modgui/. The face is shown at 650 x 400, so
every image is drawn at half size with CSS background-size.

Positions below were fitted at 2x by template matching each sprite against
assets/source/EC-280-mockup-v2.jpg (lowest pixel error). A sprite whose fitted
position is odd at 2x is padded by one transparent pixel, so every element
sits on a whole pixel at 1x.

Knob: the static body stays put and the knurl + pointer layer rotates over it,
65 frames across 272 deg. The sweep was measured from the printed scale: its
ticks sit at 1, 3, 5, 7, 9, about 27.2 deg per unit, 5 straight up.
Needs pillow.
"""
import os, json
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'assets', 'source')
OUT = os.path.join(ROOT, 'bundle', 'nhe-ec280.lv2', 'modgui')
FRAMES, SWEEP = 65, 272.0

def load(name):
    return Image.open(os.path.join(SRC, name)).convert('RGBA')

def strip(frames, pad=(0, 0)):
    """Frames side by side on one even-sized canvas; pad = (x, y) offset of the art."""
    w, h = frames[0].size
    cw, ch = w + pad[0], h + pad[1]
    cw += cw % 2; ch += ch % 2
    s = Image.new('RGBA', (cw * len(frames), ch), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        s.alpha_composite(f, (i * cw + pad[0], pad[1]))
    return s, (cw // 2, ch // 2)          # 1x frame size

def save_png(im, name, colours=None):
    if colours:
        im = im.quantize(colours, method=Image.Quantize.FASTOCTREE)
    im.save(os.path.join(OUT, name), optimize=True)

def main():
    os.makedirs(OUT, exist_ok=True)
    layout = {}

    # background (2x JPEG)
    Image.open(os.path.join(SRC, 'EC-280-Face-v2.jpg')).convert('RGB').save(
        os.path.join(OUT, 'background.jpg'), quality=88)

    # knob: rotate the knurl/pointer layer over the static body
    body, knurl = load('Knob-static-body.png'), load('Knob-knurdle-pointer.png')
    c = (body.width / 2, body.height / 2)
    frames = []
    for i in range(FRAMES):
        a = -SWEEP / 2 + SWEEP * i / (FRAMES - 1)          # degrees clockwise from 12 o'clock
        f = body.copy()
        f.alpha_composite(knurl.rotate(-a, resample=Image.BICUBIC, center=c))
        frames.append(f)
    s, size = strip(frames)
    save_png(s, 'knob.png', 256)
    layout['knob'] = size

    # 2-frame strips: [value 0 / up | value 1 / down]
    # two momentary push buttons; their fitted positions differ in odd/even rows, so two pads
    s, layout['button1'] = strip([load('Button1-OFF-v2.png'), load('Button1-ONpressed-v2.png')], (1, 1))
    save_png(s, 'button1.png')            # On/Off
    s, layout['button1t'] = strip([load('Button1-OFF-v2.png'), load('Button1-ONpressed-v2.png')], (1, 0))
    save_png(s, 'button1t.png')           # Tails
    s, layout['button2'] = strip([load('Button2-OFF-v2.png'), load('Button2-ON-v2.png')])
    save_png(s, 'button2.png')
    s, layout['led'] = strip([load('ButtonLED1-OFF-v2.png'), load('ButtonLED1-ON-v2.png')], (0, 1))
    save_png(s, 'led.png')
    s, layout['range'] = strip([load('Range-300-v2.png'), load('Range-600-v2.png')], (1, 0))
    save_png(s, 'range.png')
    s, layout['toggle'] = strip([load('Toggle-ECHO-v2.png'), load('Toggle-REVERB-v2.png')], (1, 0))
    save_png(s, 'toggle.png')
    for old in ('button.png',):
        p = os.path.join(OUT, old)
        if os.path.exists(p):
            os.remove(p)
    print(json.dumps(layout))

if __name__ == '__main__':
    main()
