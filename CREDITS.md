# Credits and licences

## Projects this is built from

| Project | Author | Licence | What we use | How it gets here |
|---|---|---|---|---|
| [gr3-look-editor](https://github.com/judgem00/gr3-look-editor) | judgem00 | MIT | Video M patch bundle (`manual mlive7 dials osd bitrate`), GR-Log (`core/src/grlog.rs`), container codec and packer (`fw-pack.py`, `core/src/grfw.rs`), the look-editor library | Cloned by `build.sh` at `be5190f`. `patches/gr3-look-editor-iiix.patch` adds four examples (`iiix_image`, `grlog_iiix`, `grlog_luts_img`, `grlog_dump`) |
| [gr3-film-mods](https://github.com/idontknownihil/gr3-film-mods) | idontknownihil | MIT | v16 film-slot builder (`make_slots14/15/16.py`, `film_cave.py`, `gr3patch.py`, `armasm.py`, `make_icons.py`), verifier `verify_slots16.py`, GR IV reader/emulator and Cinema method (`work/films_v14/gr4/`), FINDINGS | Cloned by `build.sh` at `04d5d5d`. `patches/gr3-film-mods-iiix.patch` ports it to the GR IIIx 1.60 file |
| [gr-custom-tool](https://github.com/DoYitNow/gr-custom-tool) | DoYitNow | GPL-2.0 | Firmware container codec (`gr4_editor`) | gr3-film-mods' git submodule, fetched at build time. Nothing from it is copied into this repository |
| [gr3x-fw-hack](https://github.com/hhornbacher/gr3x-fw-hack) | hhornbacher | (none stated) | The original GR III/IIIx firmware exploration that the video patches build on | Reference only |

Both MIT projects keep their copyright notices: `Copyright (c) 2026 judgem00` and `Copyright (c) 2026 idontknownihil`.
The patches in `patches/` are modifications of their files and are under the same MIT terms.

## The IIIx port of the film builder (`patches/gr3-film-mods-iiix.patch`)

* The input is GR IIIx 1.60 `fwdc243b.bin` (SHA-256 `708e79f3…b431c7`) instead of GR III 2.10. The addresses are the
  same, because the two builds differ only in their model identity.
* Menu icons get new ids 0x2A0/0x2A1, with pixels carved from the GR III certification-marks page (0x1E), which a
  GR IIIx never shows. Upstream reuses the HDF and IIIx resources, which a IIIx and an HDF still need.
* The icon font is configurable (`GR3X_FONT`, default DejaVu Sans Condensed Bold).

## Related projects (not used in the build)

* [GR3-LUTSmith](https://github.com/lemonadesaltbagel/GR3-LUTSmith) (lemonadesaltbagel): `.cube` LUT → Image
  Control for the GR III / IIIx.
* [grkit](https://github.com/ahonn/grkit) (ahonn, MIT): an SD-card-loaded runtime with film looks and framing
  guides. It expects stock firmware and refuses to install on these builds, by design.
* [GR-DLC](https://github.com/Mrjie7205/GR-DLC) (Mrjie7205): film slots, custom ratios and shutdown images.

## Third-party LUTs

`lut-tools/impulz_for_gr_v2.py` reorganizes and converts a VisionColor **ImpulZ** collection you already own. No
ImpulZ files are included here, and the LUTs it generates are derived from your licensed copy, so keep them for your
own use. ImpulZ is a product of VisionColor. The tool reads Resolve's `BMDFilm to Linear.cube` from your own
DaVinci Resolve installation, which isn't included either.

## Ricoh

Ricoh, GR, GR IIIx and GR IV are trademarks of Ricoh Imaging. This project isn't affiliated with Ricoh. It ships
no Ricoh firmware, no code or data extracted from it, and no LUTs computed from it.
