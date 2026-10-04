# Dynacord EC 280: circuit notes (from the service schematic)

**Source:** Niels's copy of the Dynacord service schematic, sheets 2-1605 b (preamp, filters, chorus, speed) and 2-1606 b (BBD line, clock, button matrix), dated 5.10.77. The schematic is not included in this repository.

**Status:** a reading of a 150 dpi scan. The confidence of each item is marked.

---

## 1. Architecture in one line

Input → Volume preamp → sum with Duration feedback (IC601) → 4-pole anti-alias filter → **8× TDA 1022 BBD** in four buffered pairs → four taps → **Echo / Hall resistor matrix** → Return and Duration buses → 4-pole reconstruction filter → Output / Delay out.

## 2. Delay line and taps (confident)

- Eight 512-stage TDA 1022s in series = 4,096 stages. Each chip pair has its own transistor buffer and trims, and a tap after it: **taps at ¼, ½, ¾ and 1** of the total delay.
- Delay = stages ÷ (2 × clock). About 300 ms at the longest gives a clock near 6.8 kHz, so bandwidth tops out around 3.4 kHz.
- **Plugin:** a 16-chip line (8,192 stages) always runs; Range moves the taps from pairs 1-2-3-4 to 2-4-6-8. Per-pair losses are one-pole low-passes (12 kHz, tuned by ear).

## 3. Clock (topology confident, range a guess)

- OTA-based VCO (CA3080) with a CMOS flip-flop (MC14027) making the two-phase clock.
- **Speed** (R661, 100k log) sets the control voltage via IC500; IC600 with R790 270k ∥ C629 0.1 µ smooths it: **27 ms glide**.
- The clock range isn't readable; the plugin uses 40–300 ms (Vintage), log taper.

## 4. Chorus (confident)

- **T602** (BC414B, marked with a red dot) is a reverse-biased junction used as a **noise source**.
- IC600 stage 1: R623 1M ∥ C608 0.1 µ low-pass at about **1.6 Hz**; D603–D605 softly clamp the swing.
- IC600 stage 2: R631/R610 3k3, C616 100 µ, R638 500k trim: shapes the low end around **0.5 Hz**.
- The Chorus pot (R650 100k) sums this into the Speed control amp, so it adds to the clock in Hz. Max depth is not readable; the plugin uses ±1 kHz.

## 5. Button matrix (Echo good, Hall partly a guess)

- **S602 Echo/Hall** is a two-pole changeover: one pole feeds the Return pot from the Echo or Hall wet bus, the other feeds the Duration pot from the Echo or Hall feedback bus.
- **Echo (S601):** wet = tap 4 through 330k, always. Each E button adds its tap to feedback through 130k (+ a shared 10k). E1 = tap 4 … E4 = tap 1. Confirmed by ear on the drolo demo video: E4 alone gives a long first echo, then fast flutter.
- **Hall (S600):** each two-pole button adds a spread of taps to wet and one tap to feedback (series pairs, kΩ):

| Button | Wet | Feedback | Confidence |
| --- | --- | --- | --- |
| H1 | T1 403, T2 452, T3 506, T4 566 | T4 140 | Good |
| H2 | T1 452, T2 570, T3 719, T4 902 | T4 190 | Good |
| H3 | T1 360, T2 360 | T2 140 | Which tap feeds back is unsure |
| H4 | T1 360, T2 360, T3 360 | T1 140 | Which tap feeds back is unsure |

- Buses are passive: V = Σ(Gᵢ·tapᵢ) ÷ (ΣGᵢ + G_load), with G_load ≈ 1/47k (a guess).

## 6. Filters and levels (values partly hard to read)

- Input: two Sallen-Key stages (T616, T631), about 4.0 kHz (47k/47k, 1n5/470p) and 3.3 kHz (18k/18k, 1n5/4n7), Q ≈ 0.9.
- Output: the matching chain on the Return side (R681–R706, T613–T619); modelled as the same two stages.
- Taps run at about 350 mV nominal.
- Outputs: **Output** (mixed) and **Delay out** through R605 68k (wet).
- Footswitch jack: "Chorus Off" and "Reverb/Echo Off" contacts.
