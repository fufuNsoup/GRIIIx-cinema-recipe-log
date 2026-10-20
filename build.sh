#!/usr/bin/env bash
# Build the GR IIIx 1.60 mod (stage 11) from your own copies of Ricoh's update files.
#
#   ./build.sh path/to/fwdc243b.bin path/to/fwdc248b.bin [OUT_DIR]
#
# fwdc243b.bin = GR IIIx 1.60 (also GR IIIx Urban Edition / HDF), fwdc248b.bin = GR IV 1.11 (only read, for the
# Cinema look data). Both are free downloads from Ricoh. Every stage is checked against expected-hashes.txt; the
# build stops at the first difference. Output: OUT_DIR/FWDC243B.BIN plus the GR-Log LUTs in OUT_DIR/luts.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
[ $# -ge 2 ] || { sed -n 2,8p "$0"; exit 1; }
GR3X_BIN=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
GR4_BIN=$(cd "$(dirname "$2")" && pwd)/$(basename "$2")
OUT=$(mkdir -p "${3:-$HERE/out}" && cd "${3:-$HERE/out}" && pwd)
WORK=$OUT/work; mkdir -p "$WORK" "$OUT/stages" "$OUT/luts"
TP=$HERE/third_party
PY=${PY:-python3}

LOOK_EDITOR_URL=https://github.com/judgem00/gr3-look-editor.git
LOOK_EDITOR_REV=be5190fe7db52298eab5265d9f0bf30bc7fdf99f
FILM_MODS_URL=https://github.com/idontknownihil/gr3-film-mods.git
FILM_MODS_REV=04d5d5dd6e85d80089c6200bd0f0de5fff2d658f

sha() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
expect() {  # expect NAME FILE
    local want got; want=$(awk -v n="$1" '$1 == n {print $2}' "$HERE/expected-hashes.txt"); got=$(sha "$2")
    if [ "$want" != "$got" ]; then echo "!! $1: SHA-256 $got, expected $want - stopping" >&2; exit 1; fi
    echo "ok $1 ${got:0:8}"
}
step() { echo; echo "== $*"; }

step "inputs"
expect stock-gr3x-1.60 "$GR3X_BIN"
expect stock-gr4-1.11 "$GR4_BIN"

step "upstream projects (pinned commits + our IIIx patches)"
mkdir -p "$TP"
fetch() {  # fetch DIR URL REV PATCH
    if [ ! -d "$TP/$1/.git" ]; then git clone -q "$2" "$TP/$1"; fi
    git -C "$TP/$1" checkout -q -f "$3"
    git -C "$TP/$1" clean -qfd -e work/ma_probe5/gr4_std_ma.json -e target/
    git -C "$TP/$1" apply "$HERE/patches/$4"
    echo "$1 @ ${3:0:7} + $4"
}
fetch gr3-look-editor "$LOOK_EDITOR_URL" "$LOOK_EDITOR_REV" gr3-look-editor-iiix.patch
fetch gr3-film-mods "$FILM_MODS_URL" "$FILM_MODS_REV" gr3-film-mods-iiix.patch
git -C "$TP/gr3-film-mods" submodule update -q --init third_party/gr-custom-tool

export GR3X_FILMMODS=$TP/gr3-film-mods GR3X_STOCK=$GR3X_BIN GR3X_WORK=$WORK GR3X_STOCK_IMAGE=$WORK/stock.img
export LLVM_BIN=${LLVM_BIN:-$(dirname "$(command -v llvm-mc || echo /usr/bin/llvm-mc)")/}
LE=$TP/gr3-look-editor
PACK="$PY $LE/fw-pack.py pack $GR3X_BIN"
pack() { $PACK "$WORK/$1.img" -o "$OUT/stages/$1.BIN" >/dev/null; expect "$1" "$OUT/stages/$1.BIN"; }

step "look editor examples (Rust)"
(cd "$LE/core" && cargo build -q --release --examples)
EX=$LE/core/target/release/examples

step "GR IV Cinema data (stays in $WORK/gr4, never commit it)"
$PY "$HERE/tools/extract_gr4.py" "$GR4_BIN" "$WORK/gr4"

step "stage 1: video M bundle (judgem00)"
"$EX/iiix_image" "$GR3X_BIN" "$WORK/stock.img"
"$EX/iiix_image" "$GR3X_BIN" "$WORK/stage1.img" --video >/dev/null
pack stage1

step "stage 2: Cinema (Yellow) / Cinema (Green) (gr3-film-mods v16 builder, IIIx port)"
(cd "$TP/gr3-film-mods" && $PY make_slots16.py "$OUT/stages/stage2.BIN" \
    "cinema_yellow@18=$WORK/gr4/fits/cinema_yellow.json" "cinema_green@19=$WORK/gr4/fits/cinema_green.json" \
    > "$WORK/stage2.log")
expect stage2 "$OUT/stages/stage2.BIN"

step "stage 3: 1 + 2"
"$EX/iiix_image" "$OUT/stages/stage2.BIN" "$WORK/stage3.img" --video >/dev/null
pack stage3

step "stage 4: Clarity/Shading gate on Cinema, grain on Negative Film"
$PY "$HERE/tools/make_stage4.py" "$WORK/stage3.img" "$WORK/stage4.img" >/dev/null; pack stage4
step "stage 5: grain on Cinema"
$PY "$HERE/tools/make_stage5.py" "$WORK/stage4.img" "$WORK/stage5.img" >/dev/null; pack stage5
step "stage 8: GR IV Color Tone on the Toning slider"
$PY "$HERE/tools/make_stage8.py" "$WORK/stage5.img" "$WORK/stage8.img" "$WORK/gr4/colortone_variants.json" >/dev/null
pack stage8

step "stage 9: GR-Log on Vivid (judgem00's GR-Log, v1 curve)"
"$EX/grlog_iiix" "$GR3X_BIN" "$WORK/grlog1" Vivid
$PY "$HERE/tools/make_stage9.py" "$WORK/stage8.img" "$WORK/grlog1/image-grlog.bin" "$WORK/stage9.img" >/dev/null
pack stage9
step "stage 10a: bitrate 24p 42 / 30p 52.5 / 60p 52.5 Mbit/s"
$PY "$HERE/tools/make_stage10.py" "$WORK/stage9.img" "$WORK/stage10a.img" 52500 52500; pack stage10a
step "stage 11: GR-Log v2 curve"
GRLOG_LO=-5.5 "$EX/grlog_iiix" "$GR3X_BIN" "$WORK/grlog2" Vivid
$PY "$HERE/tools/make_stage11.py" "$WORK/stage10a.img" "$WORK/grlog2/image-grlog.bin" "$WORK/stage11.img"
pack stage11
$PY "$LE/fw-pack.py" check "$OUT/stages/stage11.BIN" | tail -1
cp "$OUT/stages/stage11.BIN" "$OUT/FWDC243B.BIN"

step "GR-Log v2 LUTs for DaVinci Resolve (personal use: computed from Ricoh's tone curve)"
GRLOG_LO=-5.5 "$EX/grlog_luts_img" "$WORK/stock.img" "$WORK/luts"
for f in "$WORK"/luts/GR-Log_to_*.cube; do
    sed '1s/^TITLE "GR-Log /TITLE "GR-Log v2 /' "$f" > "$OUT/luts/$(basename "$f" | sed 's/^GR-Log_/GR-Log-v2_/')"
done
GRLOG_LO=-5.5 "$EX/grlog_dump" "$WORK/stock.img" "$OUT/luts/grlog2_model.json"

if [ "${VERIFY:-0}" = 1 ]; then
    step "emulation checks (slow)"
    mkdir -p "$TP/gr3-film-mods/work/fw"   # the verifier emulates the stock IIIx RTOS section
    $PY - "$WORK/stock.img" "$TP/gr3-film-mods/work/fw/rtos.bin" <<'EOF'
import sys, os
sys.path.insert(0, os.environ['GR3X_FILMMODS']); import codec_path  # noqa: F401
from gr4_editor.codec.frames import section_rows
d = open(sys.argv[1], 'rb').read(); r = {x['name']: x for x in section_rows(d)}['RTOS']
open(sys.argv[2], 'wb').write(d[r['start'] + 16:r['start'] + 16 + r['payload_bytes']])
EOF
    (cd "$TP/gr3-film-mods" && $PY verify_slots16.py "$GR3X_BIN" "$OUT/stages/stage2.BIN" \
        "cinema_yellow@18=$WORK/gr4/fits/cinema_yellow.json" "cinema_green@19=$WORK/gr4/fits/cinema_green.json" | tail -1)
    $PY "$HERE/tools/verify_stage4.py" "$WORK/stage4.img" | tail -1
    $PY "$HERE/tools/verify_stage5.py" "$WORK/stage5.img" | tail -1
    $PY "$HERE/tools/verify_stage8.py" "$WORK/stage8.img" "$WORK/gr4/colortone_variants.json" | tail -1
    $PY "$HERE/tools/verify_stage9.py" "$WORK/stage9.img" "$WORK/grlog1/image-grlog.bin" | tail -1
fi

echo
echo "Done: $OUT/FWDC243B.BIN (stage 11, SHA-256 $(sha "$OUT/FWDC243B.BIN"))"
echo "Read docs/FLASHING.md before you copy it to a card."
