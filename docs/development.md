# Development

How Electronic Echo 280 is built, tested and changed. The same process applies to every New Horizon plugin.

## Toolchain

```sh
apt-get install g++ g++-arm-linux-gnueabihf g++-aarch64-linux-gnu qemu-user lilv-utils
pip install numpy scipy pillow playwright rdflib
gcc -O2 -Idpf/distrho/src -Idpf/distrho/src/lv2 tools/lv2host.c -o tools/lv2host -ldl
git clone --depth 1 https://github.com/mod-audio/mod-ui.git /tmp/mod-ui    # for the face test
```

## The loop for every change

1. **Decide the behaviour first.** Faithful to the original by default; any deliberate difference goes in the CHANGELOG.
2. **Edit the sources** (`plugins/`, `bundle/`). The LV2 metadata is hand-written: keep port order, ranges and the URI in step with `DistrhoPluginInfo.h` and `initParameter()`.
3. **Build three ways:** native (`make`), Duo (`CC=arm-linux-gnueabihf-gcc CXX=arm-linux-gnueabihf-g++ CXXFLAGS="-mcpu=cortex-a7 -mfpu=neon-vfpv4 -mfloat-abi=hard" make`), Duo X / Dwarf (`CC=aarch64-linux-gnu-gcc CXX=aarch64-linux-gnu-g++ make`). Warnings are bugs.
4. **Check the metadata:** build DPF's generator from the submodule (`make -C dpf/utils/lv2-ttl-generator`), run `dpf/utils/lv2_ttl_generator` on the built plugin and compare it port by port with `bundle/nhe-ec280.lv2/nhe-ec280.ttl`. Then `LV2_PATH=bin lv2info https://github.com/Kiwooky/NHE-EC280`.
5. **Run the audio suite:** `python3 tools/ectest.py` natively, then the ARM builds under qemu:
   `EC_SO=<arm .so> EC_HOST="qemu-arm -L /usr/arm-linux-gnueabihf <arm lv2host>" python3 tools/ectest.py`
   (put `presets.ttl` next to the `.so` so the preset checks run). It checks tap timing per range at 44.1/48/96 kHz, the E4 flutter spacing, levels, darkness at slow clock, feedback decay and self-oscillation, torture runs, range flips, bypass (clicks, dry at unity, tails), every factory preset and silence. **Every reported bug gets a test that fails first.**
   ARM builds fuse multiply-adds (`-ffp-contract=fast`), so after a while a clock tick lands a sample differently from x86: compare ARM with native by level envelope, not sample by sample.
6. **Face changes:** `make && MODUI=/tmp/mod-ui python3 tools/facetest.py` runs the template and `script-ec280.js` in mod-ui's own `html/js/modgui.js` with mouse (including a small wobble) and touch. Then `python3 tools/render.py && make` to refresh the screenshot and thumbnail. The knob filmstrip comes from `tools/knob_filmstrip.py` with a **276°** sweep to match the printed scale.
7. **Bump the version** in `getVersion()` and the TTL together (`d_version(1,0,N)` ↔ `lv2:minorVersion 2 ; lv2:microVersion N`). MOD caches plugin data per version: an unchanged version shows stale faces.
8. **Commit, update `NHE_EC280_VERSION`** in the package file to the new commit, build on builder.mod.audio and check on hardware: face, sound, footswitches, bypass, CPU meter (worst case: Speed at 10).

## Rules learned the hard way

- **DPF needs `opts:options` and `urid:map`** declared as required features.
- **Parameters arrive with the first `run()`**, not before `activate()`: snap the clock and smoothers to their targets on the first run.
- **One-pole smoothers stall just short of target in float**: land them at the end of each block, or "unity" isn't.
- **Don't trust mod-ui's default film widget for click-to-toggle.** It ignores a click if the mouse moves a couple of pixels, and a 1-step drag can't wrap back to 0. Here every switch and button is driven by the face script; elsewhere use `mod-widget="switch"`.
- **The face script** (`modgui:javascript`) is one anonymous `function (event, funcs)`. `funcs.set_port_value()` sets controls but gets no change event back, so the script redraws its own lamps. If it throws, mod-ui silently disables it.
- **Factory presets never store `lv2_enabled`**, or picking one un-bypasses the plugin.
- **Once public, ports are frozen.** Never remove, reorder or rename ports, and never change the URI: saved pedalboards depend on them.
