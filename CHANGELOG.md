# Changelog

## 1.0.1 — 2026-10-12

New pedal face artwork at 2x (sharp on retina screens), drawn at the same 650 × 400.

- On/Off and Tails are now momentary push buttons, drawn down only while pressed, each with its own
  LED: On/Off's follows bypass (mod-ui's bypass light), Tails' follows the Tails setting.
- Knob filmstrip rebuilt from the new static body and rotating knurl/pointer layers, 272° to match
  the new printed scale (ticks at 1, 3, 5, 7, 9). The knurl turns about its own ring centre, moved
  onto the red cap's centre, so it never creeps into the red.
- Every sprite position fitted to the new mockup; `tools/make_face.py` rebuilds all face images
  from `assets/source/*-v2`.
- Output jacks centred on the new MIX and 100% WET arrows.
- Face test (`tools/facetest.py`) also checks the momentary buttons and both LEDs.

## 1.0.0 — 2026-10-04

First release under its own identity (URI `https://github.com/Kiwooky/NHE-EC280`,
maker New Horizon Electronics, bundle `nhe-ec280.lv2`). Carries everything from the cookbook
prototype (v1.0.0–1.0.3):

- Virtual bucket-brigade line from the service schematic: 16 chips / 8,192 stages on its own clock,
  four taps after chip pairs, 4-pole filters either side, bucket and output-stage soft clips, BBD hiss.
- Echo / Reverb resistor matrix as passive buses; button banks stored as one bitmask port each.
- Noise-driven chorus (1.6 Hz low-pass, diode clamp, 0.5 Hz high-pass) added to the clock.
- Range: Vintage 300 ms / Extended 600 ms at the same clock; switching glitches like hardware.
- Bypass with Tail option; dry exactly unity when bypassed.
- Pedal face by New Horizon Electronics: 276° knob sweep matched to the printed scale, jacks on the
  MIX / 100% WET arrows, buttons and switches driven by the face script (tap = one, hold = add).
- Ten factory presets by Niels.

Deliberate differences from the original: the 600 ms range, and the Tail option.
