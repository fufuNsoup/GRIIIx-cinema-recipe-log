"""Extract the GR IV Cinema (Yellow) / Cinema (Green) data the GR IIIx build needs, from YOUR OWN copy of Ricoh's
GR IV 1.11 update file (fwdc248b.bin). Nothing extracted here is ever committed: it is Ricoh data.

Writes into OUT_DIR:
  gr4_rtos.bin                      the GR IV RTOS section (decoded with gr-custom-tool's codec)
  fits/cinema_{yellow,green}.json   gr3-film-mods v16 film fits: look matrix, exact R/G/B curves, GR IV hue sectors
  colortone_variants.json           Color Tone 1 / 3 R and B curves as 33-knot tables (stage 8, Toning slider)
  cinema_ref_{key}.npy              the curves at Color Tone 1/2/3 (used by verify_stage8.py)
  gr4_ma_sets.json, gr4_std_ma.json GR IV MultiAxial (hue-sector) sets; gr4_std_ma.json is also copied to
                                    <gr3-film-mods>/work/ma_probe5/, where make_slots16.py reads it

Method (all upstream, from idontknownihil/gr3-film-mods work/films_v14/gr4/): the GR IV's own ImageTuning code is run
in Unicorn (emux.Tuning) and the curve composite at 0x5391E340 is captured; the look matrix is the GR IV Cinema
matrix relative to GR IV Standard, applied on top of the GR III Standard look matrix (cinema_fit.py); the hue sectors
are GR IV sets 18/19 level 0, quantised to steps of 4/1024 (rows sum to 1024).

Usage: extract_gr4.py FWDC248B.BIN OUT_DIR       (env GR3X_FILMMODS = patched gr3-film-mods checkout)
"""
import sys, os, json, hashlib, shutil
import numpy as np

GR4_SHA = 'a2f664dfca034059eb0fd6e18ab08684c326b4a034d85c164dad7e1ec9b5655f'   # GR IV 1.11 fwdc248b.bin
FM = os.environ['GR3X_FILMMODS']
src, out = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(out, 'fits'), exist_ok=True)

data = open(src, 'rb').read()
if hashlib.sha256(data).hexdigest() != GR4_SHA:
    raise SystemExit(f'{src}: not Ricoh GR IV 1.11 fwdc248b.bin (SHA-256 {GR4_SHA[:8]}…)')

# 1. decode the container, cut the RTOS section (as gr3-film-mods' dec.py + verify_slots: payload after a 16-B header)
rtos_path = os.path.join(out, 'gr4_rtos.bin')
if not os.path.exists(rtos_path):
    sys.path.insert(0, FM); import codec_path  # noqa: F401  (gr-custom-tool on sys.path)
    from gr4_editor.codec.container import inspect_container
    from gr4_editor.codec.frames import decode_payload, section_rows
    info = inspect_container(data)
    dec, _ = decode_payload(data[128:info['payload_end']], info['decoded_size'])
    r = {x['name']: x for x in section_rows(dec)}['RTOS']
    open(rtos_path, 'wb').write(dec[r['start'] + 16:r['start'] + 16 + r['payload_bytes']])
    del dec
os.environ['GR_RTOS_DIR'] = os.path.abspath(out) + os.sep

sys.path.insert(0, os.path.join(FM, 'work', 'films_v14', 'gr4'))
from g4curves import curves, g      # noqa: E402  (emulates the GR IV)

# 2. look matrices and curves (gr3-film-mods cinema_fit.py, without its GR III base-gamma diagnostic)
STD_LOOK = np.array([8116, 743, -667, 15, 8598, -421, -244, 542, 7894]).reshape(3, 3) / 8192
L4 = lambda rec: np.array(g.h(g.w(rec + 4), 9), float).reshape(3, 3) / 8192
L4std = L4(g.w(0x55053780 + 4 * 11))
TONES = (('cinema_yellow', 18), ('cinema_green', 19))
fits, refs = {}, {}
for key, tone in TONES:
    M = L4(g.w(0x55053780 + 4 * tone)) @ np.linalg.inv(L4std) @ STD_LOOK
    c = curves(tone, 1)
    assert c['mix'] == (1, 2), c['mix']
    fits[key] = dict(matrix=M.tolist(), post_q512=[[512, 0, 0], [0, 512, 0], [0, 0, 512]], mid_index=7.8,
                     source=f'GR IV fwdc248b tone {tone}, Color Tone 1 (default), MultiAxial not ported',
                     presets=[dict(spec=f'gr4:{tone}', curves=[x.tolist() for x in c['curves']])])
    refs[key] = np.array([curves(tone, 1, ct)['curves'] for ct in (0, 1, 2)])
    assert (refs[key][1] == np.array(c['curves'])).all()
    print(key, 'matrix row sums', M.sum(1).round(4))

# 3. MultiAxial sets (tools/extract_gr4_hue.py logic, self-checked against gr3-film-mods FINDINGS §29)
SETS = {11: 0x54049DE8, 17: 0x5404A6A8, 18: 0x5404B800, 19: 0x5404C6D4}
TABLE = 0x55053504
import struct  # noqa: E402
def read_set(at):
    p = [g.w(at + 4 * i) for i in range(6)]
    return dict(bounds=list(g.H(p[0], 16)), selectors=list(g.rd(p[1], 20)), control=list(g.H(p[4], 21)),
                ycc=list(g.h(p[5], 9)), matrices=list(struct.unpack('<540i', g.rd(g.w(p[2] + 0x10), 540 * 4))))
sets = {}
for tone, at in SETS.items():
    assert g.w(TABLE + 4 * tone) == at, 'per-slot table does not point at the documented set'
    s = read_set(at)
    assert s['bounds'] == [1298, 750, 0, 0, 1448, 843, 0, 0, 1298, 750, 0, 0, 1205, 843, 0, 0]
    assert s['selectors'] == [0, 1, 2, 2, 2, 3, 4, 5, 5, 5, 6, 7, 8, 8, 8, 9, 10, 11, 11, 11]
    assert s['control'] == [32, 328, 328, 328, 293, 800, 1600, 2400, 3200, 32, 1024, 1024, 1024, 1024, 0, 0, 0, 0, 0,
                            640, 1280]
    assert s['ycc'] == [77, 150, 29, -43, -85, 128, 128, -107, -21]
    sets[str(tone)] = s
std = {k: sets['11'][k] for k in ('bounds', 'selectors', 'control', 'ycc')}
json.dump(std, open(os.path.join(out, 'gr4_std_ma.json'), 'w'))
json.dump(sets, open(os.path.join(out, 'gr4_ma_sets.json'), 'w'))
os.makedirs(os.path.join(FM, 'work', 'ma_probe5'), exist_ok=True)
shutil.copy(os.path.join(out, 'gr4_std_ma.json'), os.path.join(FM, 'work', 'ma_probe5', 'gr4_std_ma.json'))

# 4. v16 fits: + hue sectors (level 0, step-4 quantised, diagonal = 1024 - row's off-diagonals)
for key, tone in TONES:
    m = np.array(sets[str(tone)]['matrices']).reshape(12, 5, 3, 3)[:, 0].astype(float)
    q = np.round(m / 4) * 4
    for i in range(3):
        q[:, i, i] = 0
        q[:, i, i] = 1024 - q[:, i].sum(1)
    err = int(np.abs(q - m).max())
    f = dict(fits[key])
    f['source'] += f'; hue sectors: GR IV set tone {tone} level 0, step-4 quantised (max |err| {err}/1024)'
    f['hue_q10'] = q.astype(int).tolist()
    f['hue_gr4_levels'] = True
    json.dump(f, open(os.path.join(out, 'fits', f'{key}.json'), 'w'))

# 5. Color Tone variants for stage 8: Color Tone 1 (weak) / 3 (strong), R and B (G is the same at every Color Tone)
sys.path.insert(0, FM)
from film_cave import knots_of, expand   # noqa: E402
V = {}
for key, _ in TONES:
    r = refs[key]
    assert all((r[i][1] == r[1][1]).all() for i in range(3)), 'G differs between Color Tones'
    np.save(os.path.join(out, f'cinema_ref_{key}.npy'), r)
    for vi, v in ((0, 'weak'), (2, 'strong')):
        for ch, cn in ((0, 'R'), (2, 'B')):
            kn = knots_of(r[vi][ch])
            V[f'{key}_{v}_{cn}'] = dict(knots=[int(x) for x in kn], err=float(np.abs(expand(kn) - r[vi][ch]).max()))
json.dump(dict(out=V, default_ptrs={}), open(os.path.join(out, 'colortone_variants.json'), 'w'), indent=1)
print('GR IV data extracted to', out)
