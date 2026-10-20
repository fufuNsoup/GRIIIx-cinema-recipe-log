"""Verify stage 5 (Cinema grain) against the stage-4 image by emulation."""
import sys, struct, random
import os
import numpy as np
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UcError
from unicorn import arm_const as A
B = 0x52FEF790
S4 = open(os.path.join(os.environ['GR3X_WORK'], 'stage4.img'), 'rb').read()
S5 = open(sys.argv[1], 'rb').read()
ok = True
def check(c, msg):
    global ok; ok &= bool(c); print(('OK   ' if c else 'FAIL ') + msg)

LO, HI = 0x53000000, 0x54100000
def machine(img):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(LO, HI - LO); u.mem_write(LO, img[LO - B:HI - B])
    for base in (0x10000000, 0x20000000, 0x30000000, 0x40000000): u.mem_map(base, 0x10000)
    u.mem_map(0x7F000000, 0x100000)  # stack
    return u
def call(u, fn, regs, stops, sp=0x7F0F0000):
    for r, v in regs.items(): u.reg_write(getattr(A, 'UC_ARM_REG_' + r.upper()), v)
    u.reg_write(A.UC_ARM_REG_SP, sp); u.reg_write(A.UC_ARM_REG_LR, 0x40000000)
    hit = {}
    def hook(uc, addr, size, _):
        if addr in stops: hit['at'] = addr; uc.emu_stop()
    h = u.hook_add(1 << 2, hook)  # UC_HOOK_CODE
    try:
        u.emu_start(fn, 0x40000000, count=5000)
    finally:
        u.hook_del(h)
    return hit.get('at'), u.reg_read(A.UC_ARM_REG_R0)

m4, m5 = machine(S4), machine(S5)

# 1. "is active" checks: copy vs Ricoh's original
CHECKS = [(0x5326AE28, 0x5325A850, (0x5326AE70, 0x532795B8)),
          (0x5326B284, 0x5325ABE8, (0x5326B2D0, 0x532796A8)),
          (0x5326B6E4, 0x5325AF80, (0x5326B730, 0x53279798))]
def site_target(img, s):
    x = struct.unpack('<I', img[s - B:s - B + 4])[0]
    off = x & 0xFFFFFF; off = off - 0x1000000 if off & 0x800000 else off
    return s + 8 + 4 * off
for k, (orig, tail, sites) in enumerate(CHECKS):
    copy = site_target(S5, sites[0])
    check(all(site_target(S5, s) == copy for s in sites) and all(site_target(S4, s) == orig for s in sites),
          f'bank {k}: both callers (setter + apply-all) now call the copy {copy:#x} (were {orig:#x})')
    check(S5[orig - B:orig - B + 0x30] == S4[orig - B:orig - B + 0x30], f'bank {k}: Ricoh original check untouched')
    bad, cine = [], True
    for mode in (0, 1):
        for sset in (0, 1, 2, 3):
            for tone in range(256):
                st = bytearray(0x400); st[0x44] = mode; st[0x1c0] = sset
                for j in range(3): st[0x1c2 + 2 * j] = random.choice([11, 13, 22])
                st[0x1c2 + 2 * k] = tone
                for m in (m4, m5):
                    m.mem_write(0x10000000, b'\0' * 8); m.mem_write(0x10000004, struct.pack('<I', 0x20000000))
                    m.mem_write(0x20000000, bytes(st))
                a, r0 = call(m4, orig, {'r0': 0x10000000}, {tail})
                b, r1 = call(m5, copy, {'r0': 0x10000000}, {tail})
                ra, rb = (a == tail), (b == tail)
                if tone in (25, 26):
                    st2 = bytearray(st); st2[0x1c2 + 2 * k] = 22
                    m4.mem_write(0x20000000, bytes(st2)); a2, _ = call(m4, orig, {'r0': 0x10000000}, {tail})
                    if rb != (a2 == tail): cine = False
                elif ra != rb or (not ra and r0 != r1):
                    bad.append((mode, sset, tone))
    check(not bad, f'bank {k}: copy == original for every look except 25/26 (2 modes x 4 banks x 256 looks) {bad[:3]}')
    check(cine, f'bank {k}: Cinema 25/26 answer exactly as Negative Film 22 would')

# 2. tone maps
for site, reg in ((0x532C17A4, 'r0'), (0x532C9758, 'r1')):
    fn = site_target(S5, site); res = {}
    for t in range(256):
        call(m5, fn, {reg: t, 'r5': 0xDEAD}, set()); res[t] = m5.reg_read(A.UC_ARM_REG_R5)
    check(all(res[t] == (22 if t in (25, 26) else t) for t in range(256)),
          f'tone map at {site:#x}: 25/26 -> 22, every other look unchanged (as the original mov r5,{reg})')

# 3. pipeline pass-through, whole function, stage 4 vs stage 5
PT = 0x536DB7DC
diffs, cine_ok = [], True
random.seed(1)
for tone in list(range(0, 32)) + [255]:
    for trial in range(6):
        si = bytearray(random.getrandbits(8) for _ in range(0x900)); si[0x77c] = tone
        res = []
        for m in (m4, m5):
            m.mem_write(0x30000000, b'\0' * 0x400)             # r1 object: +0x2ac = 0, +0x2d0 = SI
            m.mem_write(0x30000000 + 0x2d0, struct.pack('<I', 0x20000000))
            m.mem_write(0x20000000, bytes(si))
            m.mem_write(0x10000000, b'\xEE' * 0x400)           # ctx
            call(m, PT, {'r0': 0x10000000, 'r1': 0x30000000}, set())
            res.append((bytes(m.mem_read(0x10000000 + 0x1e0, 0x40)), bytes(m.mem_read(0x20000000 + 0x77c, 0x30))))
        (c4, s4), (c5, s5) = res
        if tone in (25, 26):
            g = si[0x795]
            exp_c = bytearray(c4); exp_c[0x18:0x1a] = struct.pack('<H', g)
            exp_s = bytearray(s4); exp_s[0x795 - 0x77c] = g
            if c5 != bytes(exp_c) or s5 != bytes(exp_s): cine_ok = False
        elif (c4, s4) != (c5, s5):
            diffs.append(tone)
check(not diffs, f'pipeline step: identical output for every look except 25/26 (looks 0-31, 255 x 6 random states) {sorted(set(diffs))}')
check(cine_ok, 'pipeline step: Cinema 25/26 now pass the grain value (ctx+0x1F8 and SI+0x795) and nothing else changes')

# 4. menu lists
T = 0x53B3488C
def lst(img, s, i):
    e = T + (12 * s + i) * 8 - B; p, n = struct.unpack('<IH', img[e:e + 6])
    it = img[p - B:p - B + 2 * n]; return [(it[2 * q], it[2 * q + 1]) for q in range(n)]
for s in range(3):
    check(all(lst(S5, s, i) == lst(S4, s, i) + [(0, 15)] for i in (8, 9)), f'bank {s}: Cinema lists 8/9 = stage 4 + Grain (shooting only)')
    check(all(lst(S5, s, i) == lst(S4, s, i) for i in range(12) if i not in (8, 9)), f'bank {s}: the other 10 lists unchanged (incl. Negative Film with Grain)')
check(max(len(lst(S5, s, i)) for s in range(3) for i in range(12)) <= 12, 'list lengths <= 12')

# 5. nothing else changed
x = np.frombuffer(S4, np.uint8); y = np.frombuffer(S5, np.uint8); d = np.nonzero(x != y)[0] + B
allowed = [(0x53DC2E58, 0x53DC3198)] + [(s, s + 4) for _, _, ss in CHECKS for s in ss] + \
          [(0x532C17A4, 0x532C17A8), (0x532C9758, 0x532C975C), (0x536DBB58, 0x536DBB5C)] + \
          [(T + (12 * s + i) * 8, T + (12 * s + i) * 8 + 6) for s in range(3) for i in (8, 9)]
stray = [hex(v) for v in d if not any(lo <= v < hi for lo, hi in allowed)]
check(not stray, f'{len(d)} bytes changed vs stage 4, all in the free area, 9 call sites and 6 list entries {stray[:5]}')
print('ALL OK' if ok else 'PROBLEMS')
