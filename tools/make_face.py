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
65 frames across 272 deg. The two layers aren't drawn concentric (the red cap
sits about 1 px right and down of the knurl ring), so the knurl is rotated
about its own ring centre and moved onto the cap's centre; rotating about the
canvas centre let the knurl creep into the red at some positions. The sweep was measured from the printed scale: its
ticks sit at 1, 3, 5, 7, 9, about 27.2 deg per unit, 5 straight up.
Needs pillow.
"""
import os, json
import numpy as np
from PIL import Image
from scipy import ndimage

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

def circle(xs, ys):
    """Least-squares circle through points: (cx, cy, r)."""
    A = np.c_[2 * xs, 2 * ys, np.ones(len(xs))]
    cx, cy, c = np.linalg.lstsq(A, xs * xs + ys * ys, rcond=None)[0]
    return cx, cy, np.sqrt(c + cx * cx + cy * cy)

def knob_centres(body, knurl):
    """Centre of the body's red cap (circle through its edge) and of the knurl ring
    (circle through the centres of its small lobes; the pointer blob is left out)."""
    b = np.asarray(body).astype(int)
    red = (b[..., 0] > 180) & (b[..., 1] < 120) & (b[..., 3] > 200)
    ys, xs = np.where(red & ~ndimage.binary_erosion(red))
    cap = circle(xs + 0.5, ys + 0.5)[:2]
    lab, n = ndimage.label(np.asarray(knurl)[..., 3] > 128)
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    small = [i + 1 for i, sz in enumerate(sizes) if sz < np.median(sizes) * 2]
    cs = np.array(ndimage.center_of_mass(np.ones_like(lab), lab, small)) + 0.5
    ring = circle(cs[:, 1], cs[:, 0])[:2]
    return cap, ring

def main():
    os.makedirs(OUT, exist_ok=True)
    layout = {}

    # background (2x JPEG)
    Image.open(os.path.join(SRC, 'EC-280-Face-v2.jpg')).convert('RGB').save(
        os.path.join(OUT, 'background.jpg'), quality=88)

    # knob: rotate the knurl/pointer layer over the static body
    body, knurl = load('Knob-static-body.png'), load('Knob-knurdle-pointer.png')
    cap, ring = knob_centres(body, knurl)
    dx, dy = cap[0] - ring[0], cap[1] - ring[1]
    frames = []
    for i in range(FRAMES):
        a = -SWEEP / 2 + SWEEP * i / (FRAMES - 1)          # degrees clockwise from 12 o'clock
        k = knurl.rotate(-a, resample=Image.BICUBIC, center=ring)
        k = k.transform(k.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.BICUBIC)
        f = body.copy()
        f.alpha_composite(k)
        frames.append(f)
    layout['knob_centres'] = {'cap': [round(v, 2) for v in cap], 'ring': [round(v, 2) for v in ring]}
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
