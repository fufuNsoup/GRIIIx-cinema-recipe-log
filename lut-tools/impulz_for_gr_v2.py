"""Organize an ImpulZ Ultimate collection (BMPCC + LOG Generic + Cineon Conversions) and build GR-Log versions.

GR-Log version of a look = ImpulZ 'LOG Generic' LUT  o  BMD Film (original Pocket) encode  o  GR-Log decode:
  * GR-Log decode: the camera's exact tone/log chain (grlog_dump), Standard's look matrix removed -> scene-linear,
    Rec.709 primaries.
  * BMD Film encode: Resolve's own 'BMDFilm to Linear' 1D LUT, inverted -> the tone the Pocket records, so each look
    sits at the same brightness/contrast it has on Pocket footage (ImpulZ's BMPCC and LOG Generic LUTs have identical
    neutral response; they differ only in colour handling).
  * Colour: the LOG Generic version, because GR colours are standard Rec.709 (the BMPCC folder adds a boost for the
    Pocket's wide, desaturated colour).
Usage: impulz_for_gr_v2.py out/luts/grlog2_model.json BMDFILM_TO_LINEAR.cube IMPULZ_ROOT OUT_DIR FRAME.png
"""
import sys, os, re, shutil, json
import numpy as np
from PIL import Image, ImageDraw

MODEL, BMD, ROOT, OUT, FRAME = sys.argv[1:6]
M = json.load(open(MODEL)); dec = np.array(M['decode']); Sinv = np.linalg.inv(np.array(M['standard']).reshape(3, 3))
OFF = 10 ** ((95 - 685) / 300)
def decode(u): return np.interp(u, np.linspace(0, 1, len(dec)), dec)
def r1d(p):
    rows = [l.split() for l in open(p) if l.strip() and l.strip()[0] in '0123456789-']
    return np.array([[float(x) for x in r] for r in rows if len(r) == 3])[:, 0]
bmd = r1d(BMD); xb = np.linspace(0, 1, len(bmd)); assert np.all(np.diff(bmd) > 0)
def scene(u): return decode(u) @ Sinv.T
def to_bmdfilm(u): return np.interp(scene(u), bmd, xb)           # clamps to 0..1 at the ends
def to_cineon(u): return np.clip((685 + 300 * np.log10(np.maximum(scene(u), 0) * (1 - OFF) + OFF)) / 1023, 0, 1)

def read_cube(path):
    size, vals = None, []
    for line in open(path, errors='replace'):
        s = line.strip()
        if not s or s.startswith('#') or s.startswith('TITLE'): continue
        if s.startswith('LUT_3D_SIZE'): size = int(s.split()[1]); continue
        if s.startswith('DOMAIN_'): assert s.split()[1:] in (['0', '0', '0'], ['1', '1', '1']), s; continue
        assert not s.startswith('LUT_1D'), path
        p = s.split()
        if len(p) == 3: vals.append([float(v) for v in p])
    a = np.array(vals); assert size and len(a) == size ** 3, (path, size, len(a))
    return a.reshape(size, size, size, 3)

def tetra(lut, x):
    n = lut.shape[0] - 1
    p = np.clip(x, 0, 1) * n; i = np.minimum(np.floor(p).astype(int), n - 1); f = p - i
    r, g, b = i[:, 0], i[:, 1], i[:, 2]; fr, fg, fb = f[:, 0], f[:, 1], f[:, 2]
    def L(dr, dg, db): return lut[b + db, g + dg, r + dr]
    c000, c111 = L(0, 0, 0), L(1, 1, 1); out = np.zeros_like(x)
    cases = [((fr >= fg) & (fg >= fb), (fr, fg, fb), (1, 0, 0), (1, 1, 0)),
             ((fr >= fb) & (fb > fg), (fr, fb, fg), (1, 0, 0), (1, 0, 1)),
             ((fb > fr) & (fr >= fg), (fb, fr, fg), (0, 0, 1), (1, 0, 1)),
             ((fg > fr) & (fr >= fb), (fg, fr, fb), (0, 1, 0), (1, 1, 0)),
             ((fg >= fb) & (fb > fr), (fg, fb, fr), (0, 1, 0), (0, 1, 1)),
             ((fb > fg) & (fg > fr), (fb, fg, fr), (0, 0, 1), (0, 1, 1))]
    for m, (a, bb, c), s1, s2 in cases:
        if m.any():
            out[m] = ((1 - a)[m, None] * c000[m] + (a - bb)[m, None] * L(*s1)[m] + (bb - c)[m, None] * L(*s2)[m]
                      + c[m, None] * c111[m])
    return out

def grid(n):
    u = np.linspace(0, 1, n); b, g, r = np.meshgrid(u, u, u, indexing='ij')
    return np.stack([r, g, b], -1).reshape(-1, 3)

def write_cube(path, title, comments, n, f):
    v = np.clip(f(grid(n)), 0, 1)
    with open(path, 'w') as fh:
        fh.write(f'TITLE "{title}"\n' + ''.join(f'# {c}\n' for c in comments))
        fh.write(f'LUT_3D_SIZE {n}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
        np.savetxt(fh, v, fmt='%.6f')

VARIANT = {'FC': 'FC (Film Contrast)', 'FPE': 'FPE (Film Print 2383)', 'VS': 'VS (VisionSpace low contrast)',
           'CIN': 'CIN (Negative only, Cineon log)'}
def clean(stock): return re.sub(r'\s*21\S*$', ' 21', stock).strip()
def family(stock):
    if 'Vision3' in stock: return '1 Kodak Vision3 cinema film'
    if stock.startswith('Kodak'): return '2 Kodak still film'
    if stock.startswith('Fuji'): return '3 Fuji'
    return '4 Creative (LPP, Lomo)'

GEN = os.path.join(ROOT, '01 ImpulZ -  LOG Generic'); POC = os.path.join(ROOT, '04 ImpulZ -  BMPCC')
CONV = os.path.join(ROOT, '31 ImpulZ - Cineon Conversions')
base = os.path.join(OUT, 'ImpulZ for GR IIIx - GR-Log v2'); shutil.rmtree(base, ignore_errors=True)
A = os.path.join(base, '1 GR-Log ready'); P = os.path.join(base, '2 Print stocks (after a CIN LUT)')
C = os.path.join(base, '3 Conversions (build your own chain)'); O = os.path.join(base, '4 Original Pocket (BMPCC) LUTs')
V = os.path.join(base, 'Previews')
for d in (A, P, C, O, V): os.makedirs(d)

head = ['input: GR-Log v2 (Vivid slot, grlog -5.5 8.96, highlight correction off), full-range codes 0..1',
        'decoded with the camera\'s exact curve, re-encoded with Resolve\'s BMD Film (original Pocket) curve',
        'then the ImpulZ LOG Generic version of this look (Rec.709 colour). Personal use: built from your licensed ImpulZ files.']
looks = {}
files = sorted(f for f in os.listdir(POC) if f.endswith('.cube'))
assert len(files) == 64
for f in files:
    stock, var = f[:-5].rsplit('_', 1); assert var in VARIANT, f
    st = clean(stock); fam = family(st)
    gen = read_cube(os.path.join(GEN, f)); looks[(st, var)] = gen
    for d in (os.path.join(A, fam), os.path.join(O, fam)): os.makedirs(d, exist_ok=True)
    write_cube(os.path.join(A, fam, f'{st} - {VARIANT[var]} - GR-Log v2.cube'), f'GR-Log v2 {st} {var}',
               head, 33, lambda x, g=gen: tetra(g, to_bmdfilm(x)))
    shutil.copy2(os.path.join(POC, f), os.path.join(O, fam, f'{st} - {VARIANT[var]}.cube'))

PRINT = {'Cineon to Kodak 2383 FPE (D50).cube': 'Kodak 2383 print - industry standard (D50).cube',
         'Cineon to Kodak 2393 FPE (D55).cube': 'Kodak 2393 print - rich blacks, more saturation (D55).cube',
         'Cineon to Fuji FPE (D65).cube': 'Fuji print - 35mm positive (D65).cube',
         'Cineon to Film Contrast 01.cube': 'Film Contrast 01 (same as the FC LUTs).cube',
         'Cineon to Film Contrast 02.cube': 'Film Contrast 02.cube',
         'Cineon to VisionSpace.cube': 'VisionSpace low contrast (same as the VS LUTs).cube'}
for src, dst in PRINT.items(): shutil.copy2(os.path.join(CONV, src), os.path.join(P, dst))

conv_head = ['input: GR-Log v2 (Vivid slot, grlog -5.5 8.96, highlight correction off), full-range codes 0..1']
write_cube(os.path.join(C, 'GR-Log v2 to Pocket BMD Film (Rec709 colour).cube'), 'GR-Log v2 to BMD Film', conv_head +
           ['output: Resolve BMD Film (original Pocket) curve, Rec.709 colours - put ImpulZ LOG Generic LUTs after it'], 33, to_bmdfilm)
write_cube(os.path.join(C, 'GR-Log v2 to Cineon.cube'), 'GR-Log v2 to Cineon', conv_head +
           ['output: Cineon log 95-685 - for print LUTs and other Cineon-input LUTs'], 33, to_cineon)

# previews on your own frame grab
im = np.asarray(Image.open(FRAME).convert('RGB')) / 255.0; h, w, _ = im.shape
W = 320; Hh = int(h * W / w)
def thumb(arr, label):
    t = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).resize((W, Hh))
    c = Image.new('RGB', (W, Hh + 22), (18, 18, 18)); c.paste(t, (0, 22)); ImageDraw.Draw(c).text((6, 5), label, fill=(225, 225, 225))
    return c
def sheet(tiles, cols, path):
    rows = (len(tiles) + cols - 1) // cols; s = Image.new('RGB', (cols * (W + 8), rows * (Hh + 30)), (18, 18, 18))
    for k, t in enumerate(tiles): s.paste(t, ((k % cols) * (W + 8), (k // cols) * (Hh + 30)))
    s.save(path)
px = im.reshape(-1, 3)
# the frame grab is a dim night shot: previews are rendered one stop brighter (as a +1 stop exposure lift on the log
# before the LUT would), so the looks can be told apart
enc = np.interp(2.0 * scene(px), bmd, xb)
stocks = sorted({s for s, _ in looks}, key=lambda s: (family(s), s))
for var in ('FC', 'FPE', 'VS'):
    sheet([thumb(tetra(looks[(s, var)], enc).reshape(h, w, 3), s) for s in stocks], 4,
          os.path.join(V, f'All looks - {VARIANT[var]} (+1 stop).png'))
print('done', len(files), 'looks;', base)
