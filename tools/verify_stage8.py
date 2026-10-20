"""Verify stage 8 (Cinema Color Tone) against the stage-5 image, by emulation."""
import sys, struct, json
import os
import numpy as np
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn import arm_const as A
B = 0x52FEF790
S5 = open(os.path.join(os.environ['GR3X_WORK'], 'stage5.img'), 'rb').read()
S7 = open(sys.argv[1], 'rb').read()
V = json.load(open(sys.argv[2]))['out']
REF = {k: np.load(os.path.join(os.environ['GR3X_WORK'], 'gr4', f'cinema_ref_{k}.npy')) for k in ('cinema_yellow', 'cinema_green')}
OLD_FILL, NEW_FILL, NO_CURVES, FILL_AT = 0x536EF658, 0x53DC2FF0, 0x536DD458, 0x536DD454
LIB6, EXP = 0x5503761C, 0x536EF7C8
ok = True
def check(c, m):
    global ok; ok &= bool(c); print(('OK   ' if c else 'FAIL ') + m)

def machine(img):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x53000000, 0x01100000); u.mem_write(0x53000000, img[0x53000000 - B:0x54100000 - B])
    u.mem_map(0x55000000, 0x100000)
    u.mem_map(0x10000000, 0x100000)   # r3 object (+0x38a98) and SI (r7)
    u.mem_map(0x7F000000, 0x10000)    # stack with a fake epilogue frame
    return u
m5, m7 = machine(S5), machine(S7)

def run_fill(u, fn, tone, ton_y, ton_g):
    u.mem_write(LIB6 - 24, b'\xAB' * 72)
    si = bytearray(0x1000); si[0x786] = ton_y; si[0x787] = ton_g
    u.mem_write(0x10080000, bytes(si))
    u.mem_write(0x10000000 + 0x38a98, b'\x77')
    frame = struct.pack('<11I', *([0] * 9 + [0x7F002000, NO_CURVES]))   # r3..fp, sp, pc: the epilogue 'returns' to NO_CURVES = stop
    u.mem_write(0x7F001000, frame)
    u.reg_write(A.UC_ARM_REG_R1, tone); u.reg_write(A.UC_ARM_REG_R3, 0x10000000)
    u.reg_write(A.UC_ARM_REG_R7, 0x10080000); u.reg_write(A.UC_ARM_REG_SP, 0x7F001000)
    u.emu_start(fn, NO_CURVES, count=200)
    pc = u.reg_read(A.UC_ARM_REG_PC); assert pc == NO_CURVES, hex(pc)
    return pc, bytes(u.mem_read(LIB6 - 24, 72)), bytes(u.mem_read(0x10000000 + 0x38a98, 1))

check(struct.unpack('<I', S7[FILL_AT - B:FILL_AT - B + 4])[0] & 0xFFFFFF != struct.unpack('<I', S5[FILL_AT - B:FILL_AT - B + 4])[0] & 0xFFFFFF,
      'ctx fill now branches to the new curve fill')
bad, var_ok = [], True
ptab = 0x53DC2FA8
rows = struct.unpack('<18I', S7[ptab - B:ptab - B + 72])
for tone in list(range(0, 40)) + [255]:
    for ty in range(0, 6):
        for tg in range(0, 10):
            a = run_fill(m5, OLD_FILL, tone, ty, tg)
            b = run_fill(m7, NEW_FILL, tone, ty, tg)
            film = tone - 25
            if film in (0, 1):
                t = (ty, tg)[film]
                var = {2: 0, 3: 2}.get(t, 1) if film == 0 else {5: 0, 6: 0, 7: 2, 8: 2}.get(t, 1)
                exp_lib = bytearray(a[1]); exp_lib[36:48] = struct.pack('<3I', *rows[9 * film + 3 * var:9 * film + 3 * var + 3])
                if var == 0:
                    if b != a: bad.append((tone, ty, tg))
                elif (b[0], b[1], b[2]) != (a[0], bytes(exp_lib), a[2]):
                    var_ok = False
            elif b != a:
                bad.append((tone, ty, tg))
check(not bad, f'new fill == builder fill for every non-Cinema look and for Cinema with Toning blue (41 looks x 60 Toning pairs) {bad[:3]}')
check(var_ok, 'Cinema Toning selects weak / strong curve pointers (Yellow: --/red; Green: <=0 / +3,+4); G pointer and stock library entries unchanged')

# expander on every variant pointer
u = m7
err_max = 0; exp_ok = True
for k, film in enumerate(('cinema_yellow', 'cinema_green')):
    for vi, var in ((1, 'weak'), (2, 'strong')):
        R, G, Bp = rows[9 * k + 3 * vi:9 * k + 3 * vi + 3]
        for ptr, ch, ref_ct in ((R, 0, 0 if var == 'weak' else 2), (Bp, 2, 0 if var == 'weak' else 2)):
            u.mem_write(0x10000000, struct.pack('<I', ptr))
            u.reg_write(A.UC_ARM_REG_R0, 0x10000000); u.reg_write(A.UC_ARM_REG_R7, 0x10040000)
            u.reg_write(A.UC_ARM_REG_LR, 0x7F00F000)
            u.emu_start(EXP, 0x7F00F000, count=20000)
            out = np.frombuffer(bytes(u.mem_read(0x10040000, 512)), '<u2').astype(int)
            newp = struct.unpack('<I', bytes(u.mem_read(0x10000000, 4)))[0]
            e = np.abs(out - REF[film][ref_ct][ch]).max(); err_max = max(err_max, e)
            exp_ok &= newp == 0x10040000
        u.mem_write(0x10000000, struct.pack('<I', G)); u.reg_write(A.UC_ARM_REG_R0, 0x10000000)
        u.reg_write(A.UC_ARM_REG_LR, 0x7F00F000); u.emu_start(EXP, 0x7F00F000, count=20000)
        exp_ok &= struct.unpack('<I', bytes(u.mem_read(0x10000000, 4)))[0] == G
check(exp_ok, "builder's knot expander unpacks every variant R/B into the scratch buffer; exact G curves pass through")
check(err_max <= 60, f'unpacked variants match the GR IV Color Tone 1 / 3 curves within {err_max}/16383 ({100*err_max/16383:.2f} %)')

x = np.frombuffer(S5, np.uint8); y = np.frombuffer(S7, np.uint8); d = np.nonzero(x != y)[0] + B
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
FUNCS = [(0x532c056c, 0x532c0700, 0x12, 0x19, 'r6'), (0x532c0700, 0x532c0894, 0x13, 0x1a, 'r6'),
         (0x532c6b94, 0x532c6e38, 0x12, 0x19, 'r7'), (0x532c6e38, 0x532c70e4, 0x13, 0x1a, 'r5')]
REG = {'r5': A.UC_ARM_REG_R5, 'r6': A.UC_ARM_REG_R6, 'r7': A.UC_ARM_REG_R7}
sites = []; site_ok = True
for lo, hi, proxy, film, reg in FUNCS:
    for i in md.disasm(S5[lo - B:hi - B], lo):
        if i.mnemonic == 'cmp' and i.op_str == f'{reg}, #{proxy:#x}':
            sites.append(i.address)
            br = list(md.disasm(S5[i.address + 4 - B:i.address + 8 - B], i.address + 4))[0]
            taken = int(br.op_str.lstrip('#'), 16); fall = i.address + 8
            for tone in list(range(0, 40)) + [255]:
                outs = []
                for mach in (m5, m7):
                    mach.reg_write(REG[reg], tone); mach.reg_write(A.UC_ARM_REG_LR, 0)
                    mach.emu_start(i.address, 0, count=5 if mach is m7 else 2)
                    outs.append(mach.reg_read(A.UC_ARM_REG_PC))
                eq_target = taken if br.mnemonic == 'beq' else fall
                ne_target = fall if br.mnemonic == 'beq' else taken
                exp = outs[0] if tone != film else eq_target
                site_ok &= outs[1] == exp and outs[0] == (eq_target if tone == proxy else ne_target)
                site_ok &= m7.reg_read(REG[reg]) == tone
check(len(sites) == 24 and site_ok, f'{len(sites)} Toning setter/getter tone checks: Cinema Yellow passes as Bleach, Cinema Green as Retro, every other tone exactly as stock')
allowed = [(0x53EFB2C0, 0x53EFB4D0), (0x53DC2FA8, 0x53DC30A0), (FILL_AT, FILL_AT + 4)] + [(a, a + 4) for a in sites]
stray = [hex(v) for v in d if not any(lo <= v < hi for lo, hi in allowed)]
check(not stray, f'{len(d)} bytes changed vs stage 5, all in the knot area, the table/fill code and the one branch {stray[:5]}')
print('ALL OK' if ok else 'PROBLEMS')
