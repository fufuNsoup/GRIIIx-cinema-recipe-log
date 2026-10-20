# GR-Log LUTs

`build.sh` writes these into `out/luts/`, computed from your own firmware file:

| File | Turns GR-Log v2 into |
|---|---|
| `GR-Log-v2_to_Rec709_33/65.cube` | Rec.709 with a soft highlight roll-off. The normal starting point. |
| `GR-Log-v2_to_Standard_33/65.cube` | What the camera's Standard look would have recorded. Useful as a check. |
| `grlog2_model.json` | The exact decoder (code → linear) and Standard's matrix, the input for the tools below. |

They're computed from Ricoh's tone curve, so they're for your own use; don't redistribute them.

In Resolve: node 1 for exposure and white balance on the flat log image, then the LUT as the last node.

## Film-emulation LUTs (`lut-tools/`)

* `grlog_film_luts.py MODEL.json OUTDIR [film.cube …]` writes a `GR-Log → Cineon` LUT, and for each Cineon-input film
  LUT you pass, a combined `GR-Log → film` LUT (33³/65³, tetrahedral interpolation).
* `impulz_for_gr_v2.py MODEL.json "BMDFilm to Linear.cube" IMPULZ_ROOT OUT FRAME.png` organizes a VisionColor ImpulZ
  Ultimate collection you own and builds a GR-Log version of every look. The chain is the LOG Generic LUT ∘ BMD Film
  (Gen 1) encode, using Resolve's own curve from `…/LUT/VFX IO/BMDFilm to Linear.cube` ∘ GR-Log decode. Each look then
  sits at the brightness and contrast it has on original Pocket footage. Suffixes: **FC** Film Contrast, **FPE** Kodak
  2383 print, **VS** VisionSpace (low contrast), **CIN** Cineon negative only (put a print LUT after it). The script
  expects the folder layout of the Ultimate pack (`01 … LOG Generic`, `04 … BMPCC`, `31 … Cineon Conversions`).
  The output is derived from your licensed files and is for your own use.

GR-Log v1 footage (stage 9/10a) needs a model made with the v1 encoding: run the `grlog_dump` example without
`GRLOG_LO`.
