"""Verify stage 9 (GR-Log on Vivid) against stage 8, by emulation."""
import sys, struct
import os
import numpy as np
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn import arm_const as A
B = 0x52FEF790
S8 = open(os.path.join(os.environ['GR3X_WORK'], 'stage8.img'), 'rb').read()
S9 = open(sys.argv[1], 'rb').read()
G = open(sys.argv[2], 'rb').read()
FILL, NO_CURVES, LIB6, EXP = 0x53DC2FF0, 0x536DD458, 0x5503761C, 0x536EF7C8
CURVE, SET, CM_VIVID, TAIL = 0x53002100, 0x53003EA8, 0x54094304, 0x53DC30A0
ok = True
def check(c, m):
    global ok; ok &= bool(c); print(('OK   ' if c else 'FAIL ') + m)

def machine(img):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x53000000, 0x01100000); u.mem_write(0x53000000, img[0x53000000 - B:0x54100000 - B])
    u.mem_map(0x55000000, 0x100000); u.mem_map(0x10000000, 0x100000); u.mem_map(0x7F000000, 0x10000)
    return u
m8, m9 = machine(S8), machine(S9)

def run_fill(u, tone, ty, tg):
    u.mem_write(LIB6 - 24, b'\xAB' * 72)
    si = bytearray(0x1000); si[0x786] = ty; si[0x787] = tg
    u.mem_write(0x10080000, bytes(si)); u.mem_write(0x10000000 + 0x38a98, b'\x77')
    u.mem_write(0x7F001000, struct.pack('<11I', *([0] * 9 + [0x7F002000, NO_CURVES])))
    u.reg_write(A.UC_ARM_REG_R1, tone); u.reg_write(A.UC_ARM_REG_R3, 0x10000000)
    u.reg_write(A.UC_ARM_REG_R7, 0x10080000); u.reg_write(A.UC_ARM_REG_SP, 0x7F001000)
    u.emu_start(FILL, NO_CURVES, count=200)
    assert u.reg_read(A.UC_ARM_REG_PC) == NO_CURVES
    return bytes(u.mem_read(LIB6 - 24, 72)), bytes(u.mem_read(0x10000000 + 0x38a98, 1))

bad, viv_ok = [], True
for tone in list(range(0, 40)) + [255]:
    for ty in (1, 2, 3):
        for tg in (0, 4, 6, 8):
            a, b = run_fill(m8, tone, ty, tg), run_fill(m9, tone, ty, tg)
            if tone == 12:
                lib = bytearray(a[0]); lib[36:48] = struct.pack('<3I', CURVE, CURVE, CURVE)
                viv_ok &= b == (bytes(lib), b'\x04')
            elif a != b:
                bad.append((tone, ty, tg))
check(not bad, f'curve fill identical to stage 8 for every look except Vivid (41 looks x 12 Toning pairs) {bad[:3]}')
check(viv_ok, 'Vivid: R, G, B library slots -> the GR-Log curve, variant 4; stock slots 6-8 as before')

# expander passes the GR-Log curve through untouched
u = m9; u.mem_write(0x10000000, struct.pack('<I', CURVE)); u.reg_write(A.UC_ARM_REG_R0, 0x10000000)
u.reg_write(A.UC_ARM_REG_R7, 0x10040000); u.reg_write(A.UC_ARM_REG_LR, 0x7F00F000)
u.emu_start(EXP, 0x7F00F000, count=100)
check(struct.unpack('<I', bytes(u.mem_read(0x10000000, 4)))[0] == CURVE, "builder's knot expander passes the GR-Log curve pointer through")

# data equal to the look editor's own GR-Log export
ptr = struct.unpack_from('<I', G, 0x53003D80 + 12 - B)[0]
check(S9[CURVE - B:CURVE - B + 512] == G[ptr - B:ptr - B + 512], 'GR-Log curve = the look editor\'s curve, byte for byte')
c = np.frombuffer(S9[CURVE - B:CURVE - B + 512], '<u2').astype(int)
check(np.all(np.diff(c) >= 0) and c[-1] <= 16383, f'curve rises monotonically, codes {c[0]}..{c[-1]}')
check(S9[SET - B:SET - B + 0x68] == G[SET - B:SET - B + 0x68] and S9[CM_VIVID - B:CM_VIVID - B + 4] == G[CM_VIVID - B:CM_VIVID - B + 4],
      "Vivid's colour set (Standard's matrix) and ColorMatrix entry = the look editor's export")

x = np.frombuffer(S8, np.uint8); y = np.frombuffer(S9, np.uint8); d = np.nonzero(x != y)[0] + B
allowed = [(CURVE, CURVE + 512), (SET, SET + 0x68), (CM_VIVID, CM_VIVID + 4), (TAIL, TAIL + 48), (0x53DC3010, 0x53DC3014)]
stray = [hex(v) for v in d if not any(lo <= v < hi for lo, hi in allowed)]
check(not stray, f'{len(d)} bytes changed vs stage 8, all in the curve, colour set, table entry, fill tail and one branch {stray[:5]}')
print('ALL OK' if ok else 'PROBLEMS')
