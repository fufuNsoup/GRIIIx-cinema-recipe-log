"""Stage 4 for GR IIIx 1.60, on top of the stage-2 Cinema image (and optionally the video patches).

1. Effect-stage gate (film-mods FINDINGS §47, the v29 fix, re-done in place): the processing-plan gate
   0x535131C0 gives tones 25/26 (Cinema Yellow/Green) the Monotone rule 0x53513240, so their Clarity and
   Shading sliders (and Grain, if ever set) are applied. Rewrites 11 instructions of the same function's tail,
   no code cave. Every stock tone keeps its stock result (checked by emulation in verify_stage4.py).
2. Grain on Negative Film (tone 22, Image Control list index 6): Negative Film already has a Grain field,
   setter, default, apply-all, pass-through and gate (FINDINGS §45/§47); only its parameter list lacks the
   Grain item (id 15). New lists = stock list + (visibility 0, id 15) in free zeros left by the stage-2 build
   (the stock MultiAxial 10-bit table area freed by make_slots16, verified zero); the three table entries
   [set 0..2][6] are repointed. Visibility 0 = shooting screen only (as the Monotone modes), not RAW development.

Usage: make_stage4.py in_image out_image
"""
import sys, struct, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fwre import BIAS
import subprocess, tempfile, os

def asm(lines, base):
    sys.path.insert(0, os.environ['GR3X_FILMMODS'])
    os.environ.setdefault('LLVM_BIN', '/usr/bin/')
    import armasm
    return armasm.assemble('\n'.join(lines), base)

img = bytearray(open(sys.argv[1], 'rb').read())
def rd(va, n): o = va - BIAS; return bytes(img[o:o + n])
def wr(va, data): o = va - BIAS; img[o:o + len(data)] = data
def put(va, stock, new):
    assert rd(va, len(stock)) == stock, f'{va:#x}: found {rd(va, len(stock)).hex()} expected {stock.hex()}'
    assert len(stock) == len(new)
    wr(va, new)

# ---- 1. gate -------------------------------------------------------------------------------------------
GATE = 0x535131EC
STOCK_GATE = bytes.fromhex(
    '112043e2' '020052e3' '0700009a' '140053e3' '1c00000a' '150053e3' '0300000a' '160053e3' '0b00000a'
    '0030a0e3' '070000ea')
new = asm([
    'cmp r3, #0x14',
    'beq abs(0x53513274)',          # HDR Tone (20): its own rule, as stock
    'sub r2, r3, #0x11',
    'cmp r2, #4',
    'bls abs(0x53513218)',          # 17..21 (20 already taken): Standard rule, as stock
    'sub r2, r3, #0x19',
    'cmp r3, #0x16',
    'cmpne r2, #1',
    'bls abs(0x53513240)',          # 22 (Negative Film, as stock) and 25/26 (Cinema): Monotone rule
    'mov r3, #0',
    'b abs(0x53513238)',            # anything else: 0, as stock
], GATE)
new = b''.join(struct.pack('<I', w) for w in new)
put(GATE, STOCK_GATE, new)

# ---- 2. Negative Film grain item ----------------------------------------------------------------------
TABLE, NEG_INDEX, GRAIN = 0x53B3488C, 6, (0, 15)
FREE, FREE_LEN = 0x53DC2E2C, 876
assert rd(FREE, FREE_LEN) == bytes(FREE_LEN), 'free area not zero'
at = (FREE + 3) & ~3
made = {}
for s in range(3):
    e = TABLE + (12 * s + NEG_INDEX) * 8
    p, n = struct.unpack('<IH', rd(e, 6))
    items = rd(p, 2 * n)
    assert all(items[2 * k + 1] != 15 for k in range(n)), 'Negative Film already lists Grain'
    if p not in made:
        made[p] = (at, n + 1)
        wr(at, items + bytes(GRAIN))
        at = (at + 2 * (n + 1) + 3) & ~3
    np_, nn = made[p]
    put(e, struct.pack('<IH', p, n), struct.pack('<IH', np_, nn))
assert at <= FREE + FREE_LEN
open(sys.argv[2], 'wb').write(img)
print('gate patched at', hex(GATE), '| Negative Film lists:', {hex(k): (hex(v[0]), v[1]) for k, v in made.items()},
      '| free area used', at - FREE, 'of', FREE_LEN)
