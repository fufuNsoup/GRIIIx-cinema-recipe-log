# Test results

All on one GR IIIx 1.60 unless noted (October 2026).

## Stills / looks

| Stage | Result |
|---|---|
| 1 | Boots; stills unchanged. |
| 2 | Cinema (Yellow) / Cinema (Green) render correctly in stills and movie, with C-Y / C-G icons. |
| 4 | Clarity and Shading work on both Cinema looks; Grain works on Negative Film. |
| 5 | Grain works on both Cinema looks. Also confirmed on a GR IIIx **Urban Edition** and **Diary Edition**. |
| 7 | ❌ The Toning slider only switched between `--` and blue and had no effect. Stock code checks the tone before storing or reading the Toning value, and those checks rejected the Cinema tones. Fixed in stage 8. |
| 8 | Cinema (Yellow) Toning `--` / blue / red: selectable, the value holds, and the look warms in clear steps. Cinema (Green) −4…+4 not yet reported. |

## Video

| Stage | Result |
|---|---|
| 1 | Video M works: exposure locks with the dial on M. A 30 s 30p clip grew from 74 MB to 164 MB (bitrate doubled). ❌ No shutter/aperture readout. ❌ ND doesn't engage in video M. |
| 6 | ❌ An attempt to set the AE "ND in" flag in video M: the filter still doesn't move. Left out. |
| 9 / 10a | GR-Log + `GR-Log_to_Rec709`: looks right, with much cleaner shadows than Standard. |

### GR-Log measurement clips (stage 10a, 10 clips: exposure bracket −2…+2, highlight correction on/off, pan)

* Files are `yuvj420p`, **full range**, matching what the LUTs assume.
* Log slope confirmed: a wall reads 53 → 79 → 106 for 0 / +1 / +2 stops, about 26–27 codes per stop (25.5 designed).
  At −2 stops it reads code 15, exactly the model's straight toe below −4.5 EV.
* **No scene-adaptive gain in video M.** Matching views before and after the bright part of a pan differ by 0–1
  codes, so one LUT is valid for every scene.
* **Highlight correction has no measurable effect in video M** (same wall level, same clip code).
* Highlights clip at the **top of the GR-Log v1 curve** (code 239 = the end of the camera's 12-bit tone input,
  +3.46 EV), not at the sensor. Codes 240–255 were unused.
* Noise: SD 2–3.5 codes in flat areas. The data is usable but noisy down to about −6 EV.

→ **GR-Log v2 (stage 11):** the curve starts at −5.5 EV instead of −6 and ends at the camera's real top (code ≈ 252
instead of 239). That gives about 28.5 codes per stop instead of 26. Middle grey sits at code ≈ 157. The v1 and v2 LUT
chains agree within 0.15 % (Rec.709) on a grey ramp from −4.5 to +3.3 EV. On camera, GR-Log v2 with a film LUT
(Kodak 50D) gave the expected result.

## Bitrate

| Build | 24p | 30p | 60p |
|---|---|---|---|
| stock | 16.8 (peak 25) | 21 (31.5) | 42 (63) |
| stage 1–9 | 33.6 (50) | 42 (63) | 42 (63) |
| **10a / 11** | **42 (63)** | **52.5 (79)** | **52.5 (79)** |
| 10b (not included, untested) | 52.4 (79) | 65.5 (98) | 65.5 (98) |

Mbit/s average (peak). 65.5 is the most the two 16-bit constants can hold. Short 10a clips record and play back
cleanly. Still to test: long clips (the 4 GB file limit, heat) and slower cards.

## Offline checks (every build)

* Every patch site is checked against Ricoh's stock bytes before writing, so a different firmware stops the build.
* Each stage is packed with `fw-pack.py` and decoded again, and it passes every check the camera's decoder makes.
* `VERIFY=1 ./build.sh …` runs the emulation verifiers. The film builder's verifier checks that every stock look
  renders byte-identical to stock. Stages 4/5/8/9 run the patched functions in Unicorn against the previous stage.
