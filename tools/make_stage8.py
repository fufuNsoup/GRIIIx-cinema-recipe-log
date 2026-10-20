"""Stage 8 for GR IIIx 1.60 (stage 7 + Toning store/read fix + Cinema Green on the Retro -4..+4 slider): Cinema Color Tone (GR IV) on the Toning slider, on top of the stage-5 image.

The GR IV's Cinema looks have a Color Tone setting (1..3) that blends the R and B tone curves toward G; our port is
fixed at Color Tone 2. On the GR IIIx the Cinema looks inherit Bleach Bypass's / Retro's Toning slider, whose value
sits in the shooting state at SI+0x786 (Cinema Yellow, via Bleach) / SI+0x787 (Cinema Green, via Retro) but is never
used for them. Stock code treats Toning values 2 / 3 as the two toned variants (Bleach record slots 22 / 23).

Mapping (ascending): Toning off ('--') -> GR IV Color Tone 1 (lightest), 2 (blue) -> Color Tone 2 = the
existing, bit-identical curves, 3 (red) -> Color Tone 3 (strongest).

* data : weak / strong R and B curves of both looks (extracted from the GR IV 1.11 by emulation) as 33-knot u16
         tables (66 B each) in the free part of curve region 0 (0x53EFB1A4..), the range the builder's knot expander
         already unpacks into the getter's scratch buffer (max error 0.36 %). G is identical for every Color Tone.
* table: [film][variant][R, G, B] curve pointers (variant 0 = the builder's existing pointers).
* code : the ctx fill's `b <curve fill>` (0x536DD454) -> new fill: identical to the builder's, but picks the pointer
         row by the Toning byte; r7 holds the shooting state there (loaded at 0x536DD28C, never reassigned).
Usage: make_stage8.py in_image out_image variants.json
"""
import sys, struct, os, json
sys.path.insert(0, os.environ['GR3X_FILMMODS']); os.environ.setdefault('LLVM_BIN', '/usr/bin/')
import armasm
B = 0x52FEF790
img = bytearray(open(sys.argv[1], 'rb').read())
V = json.load(open(sys.argv[3]))['out']
def rd(va, n): return bytes(img[va - B:va - B + n])
def wr(va, d): img[va - B:va - B + len(d)] = d
def w32(va): return struct.unpack('<I', rd(va, 4))[0]
def bra(at, to, link=False): return struct.pack('<I', (0xEB if link else 0xEA) << 24 | (((to - at - 8) >> 2) & 0xFFFFFF))

FILL_AT, OLD_FILL, NO_CURVES, RET_WORD = 0x536DD454, 0x536EF658, 0x536DD458, 0xE89DAFF8
LIB6, STOCK6, OLD_PTRS = 0x5503761C, 0x53EFB15C, 0x53EFB144
REG0_LO, REG0_HI = 0x53EFB0E4, 0x53EFB6E4
KNOT_AT = 0x53EFB2C0                      # region 0 after every builder allocation (last builder byte 0x53EFB280)
CODE0, CODE_END = 0x53DC2FA8, 0x53DC3198  # zeros after stage 5 in the freed MultiAxial table area

# sanity: the old fill stub is the builder's and references these addresses
assert rd(FILL_AT, 4) == bra(FILL_AT, OLD_FILL), 'ctx fill does not branch to the builder curve fill'
old = rd(OLD_FILL, 0x50)
def movw(rd_, v): return struct.pack('<I', 0xE3000000 | ((v & 0xF000) << 4) | (rd_ << 12) | (v & 0xFFF))
assert movw(0, LIB6 & 0xFFFF) in old and movw(2, STOCK6 & 0xFFFF) in old and movw(4, OLD_PTRS & 0xFFFF) in old, 'builder fill differs'
assert REG0_LO <= STOCK6 < REG0_HI and REG0_LO <= OLD_PTRS < REG0_HI
assert rd(CODE0 - 4, CODE_END - CODE0 + 4) == bytes(CODE_END - CODE0 + 4), 'code area not free'

# 1. knot tables
at = KNOT_AT
kp = {}
for film in ('cinema_yellow', 'cinema_green'):
    for var in ('weak', 'strong'):
        for ch in ('R', 'B'):
            kn = V[f'{film}_{var}_{ch}']['knots']; assert len(kn) == 33
            kp[(film, var, ch)] = at
            wr(at, struct.pack('<33H', *kn)); at += 66
assert at <= REG0_HI
# 2. pointer table [film][variant][R,G,B]
rows = []
for k, film in enumerate(('cinema_yellow', 'cinema_green')):
    R0, G0, B0 = struct.unpack('<3I', rd(OLD_PTRS + 12 * k, 12))
    rows += [R0, G0, B0]
    for var in ('weak', 'strong'):
        rows += [kp[(film, var, 'R')], G0, kp[(film, var, 'B')]]
ptab = CODE0
wr(ptab, struct.pack('<18I', *rows))
# 3. new fill
fill = ptab + 72
src = f'''
    movw r0, #{LIB6 & 0xFFFF:#x}
    movt r0, #{LIB6 >> 16:#x}
    movw r2, #{STOCK6 & 0xFFFF:#x}
    movt r2, #{STOCK6 >> 16:#x}
    ldm r2, {{r4, r5, r8, r9, r10, r12}}
    stm r0, {{r4, r5, r8, r9, r10, r12}}
    sub r2, r1, #0x19
    cmp r2, #2
    bhs abs({NO_CURVES:#x})
    add r4, r7, r2
    ldrb r4, [r4, #0x786]
    cmp r2, #0
    subne r4, r4, #1
    lsrne r4, r4, #1
    sub r4, r4, #2
    cmp r4, #1
    lslls r4, r4, #1
    movhi r4, #1
    add r2, r2, r2, lsl #1
    add r2, r2, r4
    add r2, r2, r2, lsl #1
    movw r4, #{ptab & 0xFFFF:#x}
    movt r4, #{ptab >> 16:#x}
    add r4, r4, r2, lsl #2
    ldm r4, {{r5, r8, r9}}
    add r0, r0, #12
    stm r0, {{r5, r8, r9}}
    add r3, r3, #0x38000
    mov r2, #4
    strb r2, [r3, #0xa98]
    .word {RET_WORD:#x}'''
code = b''.join(struct.pack('<I', x) for x in armasm.assemble(src, fill))
assert fill + len(code) <= CODE_END
wr(fill, code)
wr(FILL_AT, bra(FILL_AT, fill))

# 4. Toning setters / getters: accept the Cinema tones (stock compares the tone against Bleach 0x12 / Retro 0x13 only,
#    so for Cinema the value was never stored or read back - the menu showed a stale value and bounced)
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
FUNCS = [(0x532c056c, 0x532c0700, 0x12, 0x19), (0x532c0700, 0x532c0894, 0x13, 0x1a),
         (0x532c6b94, 0x532c6e38, 0x12, 0x19), (0x532c6e38, 0x532c70e4, 0x13, 0x1a)]
hat = (fill + len(code) + 15) & ~15
helpers = {}
SITES = []
for lo, hi, proxy, film in FUNCS:
    for i in md.disasm(rd(lo, hi - lo), lo):
        if i.mnemonic == 'cmp' and i.op_str.endswith(f'#{proxy:#x}'):
            reg = i.op_str.split(',')[0]
            nxt = list(md.disasm(rd(i.address + 4, 4), i.address + 4))[0]
            assert nxt.mnemonic in ('beq', 'bne'), (hex(i.address), nxt.mnemonic)
            key = (reg, proxy, film)
            if key not in helpers:
                h = armasm.assemble(f"cmp {reg}, #{film:#x}\n cmpne {reg}, #{proxy:#x}\n bx lr", hat)
                wr(hat, b''.join(struct.pack('<I', x) for x in h)); helpers[key] = hat; hat += 4 * len(h)
            SITES.append(i.address)
            wr(i.address, bra(i.address, helpers[key], link=True))
assert len(SITES) == 24 and hat <= CODE_END, (len(SITES), hex(hat))
print('toning sites', len(SITES), 'helpers', {k: hex(v) for k, v in helpers.items()}, 'end', hex(hat))
open(sys.argv[2], 'wb').write(img)
print('knots', hex(KNOT_AT), '..', hex(at), '| table', hex(ptab), '| fill', hex(fill), len(code), 'B')
