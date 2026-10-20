"""Stage 5 for GR IIIx 1.60: Grain on Cinema (Yellow) / Cinema (Green), on top of the stage-4 image.

The Cinema looks (tones 25/26) share Negative Film's Grain storage (+0xA54 / +0xA68 / +0xA7C, one per settings
bank). Ricoh's own Negative Film grain path is reused end to end:
  * menu      : Grain item (visibility 0 = shooting only) appended to the Cinema lists (Bleach Bypass / Retro
                lists 8 / 9, which the Cinema looks use and no stock look reaches any more), all 3 banks.
  * setter    : SetParticle 0x532C1780 `mov r5,r0` (tone) -> bl map0: tone 25/26 -> 22.
  * default   : GetDefaultValueParticle 0x532C9744 `mov r5,r1` -> bl map1: tone 25/26 -> 22 (else it asserts).
  * checks    : Negative Film's three "is active" checks (0x5326AE28 / 0x5326B284 / 0x5326B6E4) are left in place;
                their six callers (the three setters and apply-all) call new copies that accept tones 22, 25, 26.
  * pipeline  : pass-through Standard case (films are mapped to it) `strh r1,[ip]` (ctx+0x1F8 = 0) at 0x536DBB58
                -> bl pt: tone 25/26 -> r6 = SI+0x795 (grain), else 0; ctx+0x1F8 = r6. The common tail stores r6
                into SI+0x795, so Standard keeps writing 0 and the Cinema looks keep their grain.
  * the effect-stage gate already runs for 25/26 since stage 4.
Usage: make_stage5.py in_image out_image
"""
import sys, struct, os
sys.path.insert(0, os.environ['GR3X_FILMMODS']); os.environ.setdefault('LLVM_BIN', '/usr/bin/')
import armasm
B = 0x52FEF790
img = bytearray(open(sys.argv[1], 'rb').read())
def rd(va, n): return bytes(img[va - B:va - B + n])
def wr(va, d): img[va - B:va - B + len(d)] = d
def put(va, stock, new):
    assert rd(va, len(stock)) == stock, f'{va:#x}: found {rd(va, len(stock)).hex()} expected {stock.hex()}'
    assert len(new) == len(stock); wr(va, new)
def w(x): return struct.pack('<I', x)
def BL(at, to): return w(0xEB000000 | (((to - at - 8) >> 2) & 0xFFFFFF))
def code(at, src):
    return b''.join(w(x) for x in armasm.assemble(src, at))

FREE0, FREE_END = 0x53DC2E58, 0x53DC3198          # after stage 4's 44 bytes, end of the freed 1440 B table
assert rd(FREE0, FREE_END - FREE0) == bytes(FREE_END - FREE0), 'free area not zero'
at = FREE0
def alloc(data):
    global at
    a = at; wr(a, data); at = (at + len(data) + 3) & ~3
    assert at <= FREE_END; return a

# ---- menu lists: Grain on the Cinema lists (8, 9) ------------------------------------------------------------
TABLE = 0x53B3488C
made = {}
for idx in (8, 9):
    for s in range(3):
        e = TABLE + (12 * s + idx) * 8
        p, n = struct.unpack('<IH', rd(e, 6))
        items = rd(p, 2 * n)
        assert all(items[2 * k + 1] != 15 for k in range(n))
        if p not in made:
            made[p] = (alloc(items + bytes([0, 15])), n + 1)
        np_, nn = made[p]
        put(e, struct.pack('<IH', p, n), struct.pack('<IH', np_, nn))

# ---- check copies ------------------------------------------------------------------------------------------
CHECKS = [(0x5326AE28, 0x5325A850, (0x5326AE70, 0x532795B8)),
          (0x5326B284, 0x5325ABE8, (0x5326B2D0, 0x532796A8)),
          (0x5326B6E4, 0x5325AF80, (0x5326B730, 0x53279798))]
chk_at = []
for k, (orig, tail, sites) in enumerate(CHECKS):
    a = at
    c = code(a, f'''
        ldr r3, [r0, #4]
        ldrb r2, [r3, #0x44]
        cmp r2, #0
        bne F
        ldrb r2, [r3, #0x1c0]
        cmp r2, #{k}
        bne F
        ldrb r3, [r3, #{0x1c2 + 2 * k:#x}]
        cmp r3, #0x16
        subne r3, r3, #0x19
        cmpne r3, #1
        bls abs({tail:#x})
        F: mov r0, #0
        bx lr''')
    alloc(c); chk_at.append(a)
    for s in sites:
        put(s, BL(s, orig), BL(s, a))

# ---- tone maps ---------------------------------------------------------------------------------------------
def tmap(src_reg):
    a = at
    alloc(code(a, f'''
        cmp {src_reg}, #0x19
        cmpne {src_reg}, #0x1a
        moveq r5, #0x16
        movne r5, {src_reg}
        bx lr'''))
    return a
map0 = tmap('r0'); put(0x532C17A4, bytes.fromhex('0050a0e1'), BL(0x532C17A4, map0))   # SetParticle: mov r5, r0
map1 = tmap('r1'); put(0x532C9758, bytes.fromhex('0150a0e1'), BL(0x532C9758, map1))   # GetDefault:  mov r5, r1

# ---- pipeline pass-through ---------------------------------------------------------------------------------
pt = at
alloc(code(pt, '''
    ldrb r6, [r3, #0x77c]
    sub r6, r6, #0x19
    cmp r6, #1
    ldrbls r6, [r3, #0x795]
    movhi r6, #0
    strh r6, [ip]
    bx lr'''))
put(0x536DBB58, bytes.fromhex('b010cce1'), BL(0x536DBB58, pt))                            # strh r1, [ip]

open(sys.argv[2], 'wb').write(img)
print('lists', {hex(k): (hex(v[0]), v[1]) for k, v in made.items()})
print('checks', [hex(x) for x in chk_at], 'map0', hex(map0), 'map1', hex(map1), 'pt', hex(pt),
      '| free used', at - FREE0, 'of', FREE_END - FREE0)
