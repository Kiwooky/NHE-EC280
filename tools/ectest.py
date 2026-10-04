#!/usr/bin/env python3
"""Audio tests for Electronic Echo 280 via lv2host.

  python3 tools/ectest.py                     native build in bin/
  EC_SO=<arm .so> EC_HOST="qemu-arm -L /usr/arm-linux-gnueabihf <arm lv2host>" python3 tools/ectest.py
"""
import numpy as np, subprocess, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SO = os.environ.get('EC_SO', os.path.join(ROOT, 'bin', 'nhe-ec280.lv2', 'nhe-ec280_dsp.so'))
HOST = os.environ.get('EC_HOST', os.path.join(HERE, 'lv2host')).split()
ORDER = ['volume', 'speed', 'duration', 'return_level', 'chorus', 'mode', 'echo_taps',
         'hall_taps', 'range', 'tails', 'lv2_enabled']
DEF = dict(volume=5, speed=5, duration=4, return_level=10, chorus=0, mode=0, echo_taps=1,
           hall_taps=1, range=0, tails=1, lv2_enabled=1)
PORT = {s: 3 + i for i, s in enumerate(ORDER)}


def run(x, sr=48000, events=(), **kw):
    p = dict(DEF); p.update(kw)
    with tempfile.TemporaryDirectory() as td:
        fi, fo = os.path.join(td, 'i.raw'), os.path.join(td, 'o.raw')
        x.astype(np.float32).tofile(fi)
        args = HOST + [SO, fi, fo, str(sr), '1', '2'] + [str(p[s]) for s in ORDER]
        args += ['@%d:%d=%g' % (t, PORT[s], v) for (t, s, v) in events]
        subprocess.run(args, check=True)
        y = np.fromfile(fo, dtype=np.float32).reshape(-1, 2)
    return y[:, 0], y[:, 1]


def db(v):
    return 20 * np.log10(np.sqrt(np.mean(np.square(v))) + 1e-12)


def peak_db(v):
    return 20 * np.log10(np.max(np.abs(v)) + 1e-12)


def finite(*a):
    return all(np.all(np.isfinite(v)) for v in a)


fails = []


def check(name, ok, info=''):
    print(('PASS ' if ok else 'FAIL ') + name + ('  ' + info if info else ''))
    if not ok:
        fails.append(name)


def main():
    rng = np.random.default_rng(1)

    # 1. tap timing: wet = tap 4; E4 alone feeds back tap 1 (flutter spacing)
    for sr in (44100, 48000, 96000):
        for rg in (0, 1):
            for sp in (0, 10):
                want = (300 if sp == 0 else 40) * (2 if rg else 1)
                n = int(sr * 1.6); x = np.zeros(n); x[100] = 0.5
                _, w = run(x, sr, speed=sp, range=rg, duration=0)
                e = np.abs(w); on = (np.argmax(e > 0.05 * e.max()) - 100) / sr * 1000
                _, w2 = run(x, sr, speed=sp, range=rg, duration=6, echo_taps=8)
                e = np.abs(w2); first = np.argmax(e > 0.05 * e.max()); q = int(want / 4000 * sr)
                pk1 = first + np.argmax(e[first:first + q // 2])
                pk2 = first + int(q * 0.6) + np.argmax(e[first + int(q * 0.6):first + int(q * 1.6)])
                sp_ms = (pk2 - pk1) / sr * 1000
                tag = '@%d %s speed %d' % (sr, 'extended' if rg else 'vintage', sp)
                check('tap 4 onset ' + tag, abs(on - want) < 1.0, '%.1f ms (want %d)' % (on, want))
                check('E4 flutter spacing ' + tag, abs(sp_ms - want / 4) < max(1.0, want * 0.02),
                      '%.1f ms (want %.1f)' % (sp_ms, want / 4))

    sr = 48000
    # 2. levels
    noise = rng.standard_normal(sr * 3) * 10 ** (-12 / 20)
    m, w = run(noise, sr, duration=0)
    from scipy.signal import butter, lfilter
    b, a = butter(4, 3500 / (sr / 2)); ref = db(lfilter(b, a, noise))
    check('echo wet at unity (band-limited)', abs(db(w[sr:]) - ref) < 1.0, '%.1f dB vs %.1f' % (db(w[sr:]), ref))
    m, w = run(noise, sr, return_level=0)
    check('dry exactly unity at Volume 5', np.max(np.abs(m - noise)) < 1e-6, '%.1e' % np.max(np.abs(m - noise)))
    for h in (1, 15):
        _, w = run(noise, sr, mode=1, hall_taps=h, duration=0)
        check('reverb mask %d level sane' % h, -30 < db(w[sr:]) < -6, '%.1f dB' % db(w[sr:]))

    # 3. bandwidth: dark at slow clock
    m, w = run(noise, sr, duration=0, speed=0)
    f = np.fft.rfftfreq(8192, 1 / sr)
    spec = lambda v: np.mean([np.abs(np.fft.rfft(v[i:i + 8192] * np.hanning(8192))) ** 2
                              for i in range(sr, len(v) - 8192, 4096)], axis=0)
    H = 10 * np.log10(spec(w) / spec(noise)); r0 = np.median(H[(f > 200) & (f < 800)])
    f3 = f[np.argmax((H < r0 - 3) & (f > 500))]
    check('slow clock is dark', 2000 < f3 < 3300, '-3 dB at %.0f Hz' % f3)

    # 4. feedback: decays below the edge, wakes from hiss above it
    x = np.zeros(sr * 20); x[100] = 0.5
    _, w = run(x, sr, duration=7)
    check('Duration 7 decays', db(w[-2 * sr:]) < -70, '%.1f dB' % db(w[-2 * sr:]))
    _, w = run(np.zeros(sr * 20), sr, duration=10)
    check('Duration 10 self-oscillates from hiss, bounded',
          -30 < db(w[-2 * sr:]) and peak_db(w) <= 0.01, '%.1f dB, peak %.1f' % (db(w[-2 * sr:]), peak_db(w)))

    # 5. torture: everything up, speed flip, both modes and ranges
    loud = rng.standard_normal(sr * 6) * 0.9
    for mode in (0, 1):
        for rg in (0, 1):
            m, w = run(loud, sr, volume=10, duration=10, chorus=10, mode=mode, echo_taps=15,
                       hall_taps=15, range=rg, speed=10, events=[(sr * 3, 'speed', 0)])
            check('torture mode %d range %d' % (mode, rg), finite(m, w) and peak_db(w) <= 0.01,
                  'wet peak %.1f dBFS' % peak_db(w))

    # 6. range flip under signal (glitch allowed, must stay finite)
    m, w = run(loud * 0.3, sr, duration=6, echo_taps=5, events=[(sr * 3, 'range', 1)])
    check('range flip under signal', finite(m, w), 'peak %.1f dBFS' % peak_db(w))

    # 7. bypass: no clicks, dry exactly unity, tails on/off
    t = np.arange(sr * 4) / sr; x = 0.3 * np.sin(2 * np.pi * 220 * t)
    for tails in (1, 0):
        for vol in (5, 8):
            m, w = run(x, sr, tails=tails, volume=vol, duration=6, return_level=8,
                       events=[(sr * 2, 'lv2_enabled', 0)])
            step = np.max(np.abs(np.diff(m[sr * 2 - 256:sr * 2 + 2048])))
            own = np.max(np.abs(np.diff(x))) + np.max(np.abs(np.diff(m[:sr * 2])))
            dry = np.max(np.abs(m[sr * 3:] - x[sr * 3:] - w[sr * 3:]))
            tail = np.sqrt(np.mean(w[sr * 3:] ** 2))
            tag = 'tails %d vol %d' % (tails, vol)
            check('bypass no click ' + tag, step < own, '%.4f < %.4f' % (step, own))
            check('bypass dry unity ' + tag, dry < 1e-6, '%.1e' % dry)
            check('bypass tail ' + ('rings ' if tails else 'cleared ') + tag,
                  (tail > 1e-3) if tails else (tail < 1e-6), 'rms %.4f' % tail)

    # 8. factory presets load and run clean
    pfile = os.path.join(os.path.dirname(SO), 'presets.ttl')
    if os.path.exists(pfile):
        import re
        txt = open(pfile).read()
        presets = re.findall(r'rdfs:label "([^"]+)" ;\s*lv2:port\s*(.*?) \.', txt, re.S)
        check('ten factory presets', len(presets) == 10, '%d found' % len(presets))
        x = np.zeros(sr * 8); x[:sr] = rng.standard_normal(sr) * 0.25
        for label, body in presets:
            v = dict(DEF); v.update({k: float(val) for k, val in re.findall(r'"(\w+)" ; pset:value ([-0-9.]+)', body)})
            m, w = run(x, sr, **v)
            check('preset "%s" runs clean' % label, finite(m, w) and peak_db(w) <= 0.01, 'wet peak %.1f dBFS' % peak_db(w))

    # 9. silence stays quiet below the edge (no denormal stall)
    m, w = run(np.zeros(sr * 2), sr, duration=6)
    check('silence stays quiet', peak_db(m) < -60, 'peak %.1f dBFS' % peak_db(m))

    print('\n%d failures' % len(fails), fails)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
