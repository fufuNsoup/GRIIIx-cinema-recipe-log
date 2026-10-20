# How each stage works

Addresses are GR IIIx 1.60 RTOS virtual addresses (decoded image file offset = VA − `0x52FEF790`). The update file is
a frame-compressed container with a checksum and no signature; `fw-pack.py` (judgem00) repacks a modified image.
GR IIIx 1.60 is the same build as GR III 2.10 apart from the model identity (project 0x261 vs 0x24C), so GR III
research applies at the same addresses.

## Stage 1: video M (judgem00)
judgem00's tested bundle `manual mlive7 dials osd bitrate`: 10 patch sites, 98 bytes in the AE engine (M allowed
in movie mode, live AE in M, dials, overlay items, 24/30p bitrate ×2). Applied with `grlook::video::apply`, which
checks every site's stock bytes. See gr3-look-editor `docs/firmware/video.md`.

## Stage 2: Cinema (Yellow / Green)
idontknownihil's v16 builder, run with the GR IV Cinema fits (`make_slots16.py cinema_yellow@18=… cinema_green@19=…`).
The Cinema looks become tones 25 / 26 and replace Bleach Bypass (18) / Retro (19) in the stills, movie and RAW
development lists. Each one gets:
* **Look matrix** = GR IV Cinema matrix × (GR IV Standard)⁻¹ × GR III Standard look matrix.
* **Tone curves**: the GR IV's exact R/G/B curves, captured by running the GR IV's own tuning code in Unicorn
  (curve composite `0x5391E340`), stored as full 256-entry curves.
* **Hue sectors**: the GR IV's MultiAxial sets for tones 18/19 (12 sectors × 5 levels). The GR III's MultiAxial stage
  is inactive by default and is turned on with the GR IV's control values (gr3-film-mods FINDINGS §29–30b).
`tools/extract_gr4.py` reproduces the fits from `fwdc248b.bin` with upstream's emulator.

## Stage 4: effect gate + Negative Film grain
* The processing-plan gate `0x535131C0` decides per tone whether the Shading/Clarity/Grain stage runs. Its tail
  (`0x535131EC…`) is rewritten in place: 20 keeps the HDR rule, 17–21 follow Standard's rule, and 22 (Negative Film)
  and 25/26 (Cinema) follow the Monotone rule, which runs the Shading/Clarity/Grain stage.
* A Grain item is added to Negative Film's menu list. Ricoh's `SetParticle` / `GetDefaultValueParticle` already have
  Negative Film cases.

## Stage 5: grain on Cinema
* Cinema's menu lists get the Grain item. `SetParticle` / `GetDefaultValueParticle` map tones 25/26 → 22 through
  small stubs, because the default path would assert otherwise.
* The image pipeline's pass-through `0x536DB7DC` maps films to Standard's case, which zeroes grain. A stub at
  `0x536DBB58` passes the grain value for tones 25/26 instead.
* All new code sits in zeros freed by the v16 builder's MultiAxial table move (`0x53DC2E58…`).

## Stage 8: GR IV Color Tone on the Toning slider
* On the GR IV, Color Tone only changes how the R and B tone curves blend toward G (the composite's r0/r1). An
  emulation of the full GR IV tuning step confirmed that nothing else depends on it.
* The Color Tone 1 and 3 R/B curves are stored as 33-knot tables (max error 0.36 %), which the builder's knot expander
  unpacks. A new curve fill (the ctx fill branch at `0x536DD454`) picks the curve row from the Toning byte
  (Bleach SI+0x786 → Cinema Yellow, Retro SI+0x787 → Cinema Green).
* **Fix found on camera (stage 7 → 8):** `SetColorToneBleechBypass` / `SetColorToneRetro` and their getters check
  tone == 18 / 19. These 24 `cmp` sites now call helpers that also accept 25 / 26. Without the fix, the value was
  never stored.

## Stage 9: GR-Log on Vivid (judgem00's GR-Log)
* judgem00's GR-Log curve = log encoding ∘ inverse of Standard's tone curve, applied equally to R, G and B, with
  Standard's colour matrix. It is exported on stock with our `grlog_iiix` example (target Vivid).
* The editor installs its curve through the same ctx-fill hook the film builder uses. So only its private colour-matrix
  set (`0x53003EA8`) and Vivid's matrix entry (`0x54094304`) are copied. The 512-byte curve goes into zero padding at
  `0x53002100`, and stage 8's fill gets a Vivid case (`0x53DC30A0`): curve slots 9–11, variant 4.

## Stage 10a: bitrate
The movie bitrate target `0x5366A3D4` (kbit/s) computes fps ≤ 30 → K30·fps/30 (`movw` at `0x5366A3E8`) and fps > 30 →
K60·fps/60 (`movwhi` at `0x5366A3E0`). The peak is 1.5× the target. 10a sets K30 = K60 = 52500. A `movw` can hold at
most 65535 (10b). No clamp was found between this function and the H.264 setup.

## Stage 11: GR-Log v2
Same as stage 9, with the encoding chosen from camera clips: lo = −5.5 EV, span = top − lo = 8.96 EV, where top =
+3.46 EV is the end of the 12-bit tone input. Only the 512-byte curve changes (`GRLOG_LO=-5.5` in the examples).

## Open ideas
* ND filter in video M. Settings-side and AE-flag attempts didn't work, and it needs runtime observation.
* Highlight range in video: video clips at the tone-input end; whether the sensor holds more is unknown.
* Cross Process curves (their storage is used by the Cinema data).
* Separate grain per Cinema look; Cinema as new slots so Bleach Bypass / Retro come back.
