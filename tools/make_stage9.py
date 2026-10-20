"""Stage 9 for GR IIIx 1.60: GR-Log (judgem00's gr3-look-editor) on Vivid, on top of stage 8.

The look editor's GR-Log export on stock (core/examples/grlog_iiix.rs, target Vivid) changes:
  * a private ColorMatrix set for Vivid with Standard's matrix (0x53003EA8..+0x68) and Vivid's entry in the
    ColorMatrix table (0x54094304) -> copied unchanged (every pointer in the set leads to data identical in stage 8);
  * a curve selector at 0x536DD450 + three identical 256 x u16 curves in Cross Process / curve region 0 storage
    -> NOT copied: that site and storage are the film-mods builder's in our build. Instead the one GR-Log curve
    goes into zero padding 0x53002100 (outside region 0, so the builder's knot expander passes it through) and the
    stage-8 curve fill gets a Vivid case: R = G = B = the GR-Log curve, variant 4 (as the editor's selector does).
Usage: make_stage9.py stage8_image grlog_image out_image
"""
import sys, struct, os
sys.path.insert(0, os.environ['GR3X_FILMMODS']); os.environ.setdefault('LLVM_BIN', '/usr/bin/')
import armasm
B = 0x52FEF790
img = bytearray(open(sys.argv[1], 'rb').read())
g = open(sys.argv[2], 'rb').read()
stock = open(os.environ['GR3X_STOCK_IMAGE'], 'rb').read()
def rd(va, n, src=None): s = img if src is None else src; return bytes(s[va - B:va - B + n])
def wr(va, d): img[va - B:va - B + len(d)] = d
def bra(at, to): return struct.pack('<I', 0xEA << 24 | (((to - at - 8) >> 2) & 0xFFFFFF))
def bcond(cond, at, to): return struct.pack('<I', cond << 28 | 0x0A000000 | (((to - at - 8) >> 2) & 0xFFFFFF))

VIVID = 12
SET, SET_END, CM_VIVID = 0x53003EA8, 0x53003EA8 + 0x68, 0x54094304
CURVE = 0x53002100
FILL_BHS, NO_CURVES, RET_WORD = 0x53DC3010, 0x536DD458, 0xE89DAFF8
TAIL, CODE_END = 0x53DC30A0, 0x53DC3198

# 0. the GR-Log export differs from stock only where expected
exp = [(0x53003D00, 0x53003F10), (0x536DD450, 0x536DD454), (0x53EFB0E4, 0x53EFCA00), (CM_VIVID, CM_VIVID + 4),
       (0x568E3280, 0x568E3284)]
import numpy as np
d = np.nonzero(np.frombuffer(g, np.uint8) != np.frombuffer(stock, np.uint8))[0] + B
assert all(any(lo <= v < hi for lo, hi in exp) for v in d), 'unexpected change in the GR-Log export'
# the curve: the editor wrote the same curve three times; take it from the selector table entry of Vivid
ptrs = struct.unpack('<3I', rd(0x53003D80 + 12 * (VIVID - 11), 12, g))
curves = [rd(p, 512, g) for p in ptrs]
assert curves[0] == curves[1] == curves[2]
c = struct.unpack('<256H', curves[0])
assert all(a <= b for a, b in zip(c, c[1:])) and c[-1] <= 16383, 'curve not rising / out of range'

# 1. private colour set + Vivid's ColorMatrix entry
assert rd(SET, SET_END - SET) == bytes(SET_END - SET), 'set area not free'
words = struct.unpack('<21I', rd(SET, 84, g))
def fo(va): return va - 0x55000000 + 0x5407B540 - B if 0x55000000 <= va < 0x5503A080 else va - B   # .data VMA -> file
for k, w in enumerate(words):
    if w and not (SET <= w < SET_END):
        o = fo(w)
        assert img[o:o + 0x40] == stock[o:o + 0x40] == g[o:o + 0x40], f'set word {k} -> {w:#x} differs in stage 8'
assert words[1] == SET + 0x54
wr(SET, rd(SET, SET_END - SET, g))
assert rd(CM_VIVID, 4) == rd(CM_VIVID, 4, stock)
wr(CM_VIVID, rd(CM_VIVID, 4, g))

# 2. the curve in padding
assert rd(CURVE, 512) == bytes(512) and not (0x53EFB0E4 <= CURVE < 0x53EFB0E4 + 0x600)
wr(CURVE, curves[0])

# 3. Vivid case in the curve fill: the fill's 'bhs NO_CURVES' (not Cinema) -> tail
assert rd(FILL_BHS, 4) == bcond(0x2, FILL_BHS, NO_CURVES), 'stage-8 fill differs'
assert rd(TAIL, CODE_END - TAIL) == bytes(CODE_END - TAIL)
src = f'''
    cmp r1, #{VIVID}
    bne abs({NO_CURVES:#x})
    movw r5, #{CURVE & 0xFFFF:#x}
    movt r5, #{CURVE >> 16:#x}
    mov r8, r5
    mov r9, r5
    add r0, r0, #12
    stm r0, {{r5, r8, r9}}
    add r3, r3, #0x38000
    mov r2, #4
    strb r2, [r3, #0xa98]
    .word {RET_WORD:#x}'''
code = b''.join(struct.pack('<I', x) for x in armasm.assemble(src, TAIL))
assert TAIL + len(code) <= CODE_END
wr(TAIL, code)
wr(FILL_BHS, bcond(0x2, FILL_BHS, TAIL))
open(sys.argv[3], 'wb').write(img)
print(f'set {SET:#x} | curve {CURVE:#x} (codes {c[0]}..{c[-1]}) | Vivid tail {TAIL:#x} {len(code)} B')
