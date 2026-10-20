"""GR-Log -> Cineon (DPX log) conversion LUT, and GR-Log -> <film LUT> combined LUTs for Cineon/DP-input LUTs
(e.g. Impulz '(DP)' LUTs).
Chain (as gr3-look-editor's post_lut 'Film' path): code -> look-linear via the camera's exact decoder
(grlog_dump) -> scene-linear sRGB/Rec.709 primaries (inverse of Standard's look matrix) -> Cineon log
(Kodak: 685 + 300 log10(x*(1-o)+o), o = 10^((95-685)/300), /1023; 18 % grey -> code 468).
Usage: grlog_film_luts.py out/luts/grlog2_model.json OUTDIR [film.cube ...]
"""
import sys, json, os, re
import numpy as np
M = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
dec = np.array(M['decode']); S = np.array(M['standard']).reshape(3, 3); Sinv = np.linalg.inv(S)
OFF = 10 ** ((95 - 685) / 300)

def decode(u):
    return np.interp(u, np.linspace(0, 1, len(dec)), dec)

def cineon(x):
    return (685 + 300 * np.log10(np.maximum(x, 0) * (1 - OFF) + OFF)) / 1023

def to_cineon(rgb):                      # rgb: (...,3) GR-Log codes 0..1
    lin = decode(rgb) @ Sinv.T
    return np.clip(cineon(lin), 0, 1)

def grid(n):
    u = np.linspace(0, 1, n)
    b, g, r = np.meshgrid(u, u, u, indexing='ij')   # R fastest in file order
    return np.stack([r, g, b], -1).reshape(-1, 3)

def read_cube(path):
    size, vals, title = None, [], os.path.basename(path)
    for line in open(path, errors='replace'):
        s = line.strip()
        if not s or s.startswith('#'): continue
        if s.startswith('LUT_3D_SIZE'): size = int(s.split()[1]); continue
        if s.startswith('TITLE'): title = s.split(None, 1)[1].strip('"'); continue
        if re.match(r'^(DOMAIN_|LUT_1D)', s):
            assert not s.startswith('LUT_1D'); assert s.split()[1:] in (['0', '0', '0'], ['1', '1', '1']), s; continue
        p = s.split()
        if len(p) == 3: vals.append([float(v) for v in p])
    a = np.array(vals); assert size and len(a) == size ** 3, (size, len(a))
    return title, a.reshape(size, size, size, 3)     # [b][g][r]

def tetra(lut, x):
    """tetrahedral interpolation of lut[b][g][r] at x (...,3) in 0..1 (rgb)"""
    n = lut.shape[0] - 1
    p = np.clip(x, 0, 1) * n
    i = np.minimum(np.floor(p).astype(int), n - 1); f = p - i
    r, g, b = i[:, 0], i[:, 1], i[:, 2]; fr, fg, fb = f[:, 0], f[:, 1], f[:, 2]
    def L(dr, dg, db): return lut[b + db, g + dg, r + dr]
    c000, c111 = L(0, 0, 0), L(1, 1, 1)
    out = np.zeros_like(x)
    conds = [(fr >= fg) & (fg >= fb), (fr >= fb) & (fb > fg), (fb > fr) & (fr >= fg),
             (fg > fr) & (fr >= fb), (fg >= fb) & (fb > fr), (fb > fg) & (fg > fr)]
    for k, m in enumerate(conds):
        if not m.any(): continue
        a, bb, c = [(fr, fg, fb), (fr, fb, fg), (fb, fr, fg), (fg, fr, fb), (fg, fb, fr), (fb, fg, fr)][k]
        steps = [[(1, 0, 0), (1, 1, 0)], [(1, 0, 0), (1, 0, 1)], [(0, 0, 1), (1, 0, 1)],
                 [(0, 1, 0), (1, 1, 0)], [(0, 1, 0), (0, 1, 1)], [(0, 0, 1), (0, 1, 1)]][k]
        c1, c2 = L(*steps[0]), L(*steps[1])
        w0, w1, w2, w3 = 1 - a, a - bb, bb - c, c
        out[m] = (w0[m, None] * c000[m] + w1[m, None] * c1[m] + w2[m, None] * c2[m] + w3[m, None] * c111[m])
    return out

def write_cube(path, title, comments, n, f):
    v = f(grid(n))
    with open(path, 'w') as fh:
        fh.write(f'TITLE "{title}"\n' + ''.join(f'# {c}\n' for c in comments))
        fh.write(f'LUT_3D_SIZE {n}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
        np.savetxt(fh, np.clip(v, 0, 1), fmt='%.6f')

head = ['input: GR-Log (encoding from the model json, highlight correction off), camera RGB codes 0..1 full range',
        'decoded with the camera\'s exact tone/log chain, Standard\'s look matrix removed (Rec.709 primaries)']
for n in (33, 65):
    write_cube(f'{out}/GR-Log_to_Cineon_{n}.cube', 'GR-Log to Cineon (DPX log)',
               head + ['output: Cineon log (95/685 black/white, 18% grey = 468/1023) - feed any Cineon/DP-input LUT'], n, to_cineon)
for path in sys.argv[3:]:
    title, lut = read_cube(path)
    name = re.sub(r'[^A-Za-z0-9]+', '_', os.path.splitext(os.path.basename(path))[0]).strip('_')
    name = re.sub(r'^([0-9a-f]{8}_)?\d+_', '', name)
    write_cube(f'{out}/GR-Log_{name}_65.cube', f'GR-Log to {title}',
               head + [f'then Cineon log, then {title} (personal use: built from your own copy of this LUT)'], 65,
               lambda x: tetra(lut, to_cineon(x)))
print('grey 0.6 ->', to_cineon(np.array([[0.6] * 3]))[0], 'code0 ->', to_cineon(np.zeros((1, 3)))[0], 'code1 ->', to_cineon(np.ones((1, 3)))[0])
