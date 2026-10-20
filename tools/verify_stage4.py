"""Verify stage 4: run the effect-stage gate 0x535131C0 (stock vs patched) in Unicorn for every tone 0..255 and
Shading/Clarity/Grain/HDR-field combinations; check the Negative Film lists and that nothing else changed."""
import sys, struct, itertools
import os
import numpy as np
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn import arm_const as A
B = 0x52FEF790
stock = open(os.path.join(os.environ['GR3X_WORK'], 'stage3.img'), 'rb').read()
pat = open(sys.argv[1], 'rb').read()
FN, FN_END = 0x535131C0, 0x53513284
ok = True
def check(c, msg):
    global ok; ok &= bool(c); print(('OK   ' if c else 'FAIL ') + msg)

def runner(img):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    base = FN & ~0xFFF
    u.mem_map(base, 0x2000); u.mem_write(base, img[base - B:base - B + 0x2000])
    u.mem_map(0x10000000, 0x10000)   # SI
    u.mem_map(0x20000000, 0x1000)    # plan
    u.mem_map(0x30000000, 0x1000)    # lr target
    def run(tone, sh, cl, gr, hdr):
        si = bytearray(0x1000); si[0x77c] = tone; si[0x793] = sh; si[0x794] = cl; si[0x795] = gr; si[0x796] = hdr
        u.mem_write(0x10000000, bytes(si)); u.mem_write(0x20000000, b'\xAA' * 0x40)
        u.reg_write(A.UC_ARM_REG_R0, 0x20000000); u.reg_write(A.UC_ARM_REG_R1, 0x10000000)
        u.reg_write(A.UC_ARM_REG_LR, 0x30000000)
        u.emu_start(FN, 0x30000000, count=200)
        return u.mem_read(0x20000024, 1)[0]
    return run

rs, rp = runner(stock), runner(pat)
combos = list(itertools.product([4, 0, 2], [4, 0, 3], [0, 1, 3], [0, 1]))   # shading, clarity, grain, hdr
diff, same_stock, cine_mono = [], True, True
for tone in range(256):
    for c in combos:
        a, b = rs(tone, *c), rp(tone, *c)
        if tone in (25, 26):
            if b != rs(13, *c): cine_mono = False
        elif a != b:
            diff.append((tone, c, a, b))
check(not diff, f'gate: every non-Cinema tone 0..255 x {len(combos)} setting combos identical to stock ({len(diff)} diffs)')
check(cine_mono, 'gate: Cinema tones 25/26 now follow the Monotone rule (Clarity / Shading / Grain apply)')
check(all(rs(t, *c) == 0 for t in (25, 26) for c in combos), 'gate: Cinema tones were never enabled before (confirms the bug)')
check(rp(25, 4, 0, 0, 0) == 1 and rp(25, 4, 4, 0, 0) == 0 and rp(26, 2, 4, 0, 0) == 1,
      'gate: Cinema with Clarity set -> on, all neutral -> off, Shading set -> on')
check(all(rp(22, 4, 4, g, 0) == (1 if g else 0) for g in (0, 1, 2, 3)), 'gate: Negative Film with only Grain set -> on (as stock)')

# lists
T = 0x53B3488C
def lst(img, s, i):
    p, n = struct.unpack('<IH', img[T + (12 * s + i) * 8 - B:T + (12 * s + i) * 8 - B + 6])
    it = img[p - B:p - B + 2 * n]; return [(it[2 * k], it[2 * k + 1]) for k in range(n)]
for s in range(3):
    a, b = lst(stock, s, 6), lst(pat, s, 6)
    check(b == a + [(0, 15)], f'Negative Film list set {s}: stock + Grain (shooting only) -> {len(b)} items')
    others = all(lst(stock, s, i) == lst(pat, s, i) for i in range(12) if i != 6)
    check(others, f'set {s}: the other 11 Image Control lists unchanged')
mono_max = max(len(lst(stock, s, i)) for s in range(3) for i in range(12))
check(max(len(lst(pat, s, 6)) for s in range(3)) <= mono_max, f'list lengths within the stock maximum ({mono_max})')

# nothing else changed
x = np.frombuffer(stock, np.uint8); y = np.frombuffer(pat, np.uint8); d = np.nonzero(x != y)[0] + B
allowed = [(0x535131EC, 0x53513218), (0x53DC2E2C, 0x53DC2E2C + 44)] + \
          [(T + (12 * s + 6) * 8, T + (12 * s + 6) * 8 + 6) for s in range(3)]
stray = [hex(v) for v in d if not any(lo <= v < hi for lo, hi in allowed)]
check(not stray, f'{len(d)} bytes changed, all inside the gate tail, the new lists and the 3 table entries {stray[:5]}')
print('ALL OK' if ok else 'PROBLEMS')
