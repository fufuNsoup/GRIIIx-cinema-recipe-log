"""Small static-analysis helper for the GR IIIx 1.60 RTOS image (decoded image, file offset = va - BIAS)."""
import struct, re, numpy as np
import os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

BIAS = 0x52FEF790
IMG = open(os.environ['GR3X_STOCK_IMAGE'], 'rb').read()
W = np.frombuffer(IMG[:len(IMG) // 4 * 4], '<u4')
md = Cs(CS_ARCH_ARM, CS_MODE_ARM); md.detail = False
RTOS_LO, RTOS_HI = 0x53000000, 0x54100000


def rd(va, n): o = va - BIAS; return IMG[o:o + n]
def w32(va): return struct.unpack('<I', rd(va, 4))[0]


def dis(va, n=30):
    return [(i.address, i.mnemonic, i.op_str) for i in md.disasm(rd(va, 4 * n), va)]


def pr(va, n=30):
    for a, m, o in dis(va, n): print(f'  {a:#x}: {m} {o}')


def _word_va(i): return BIAS + 4 * i


def callers(target, kinds=('bl', 'b')):
    """ARM-mode bl/b (any cond) whose target is `target`, searched over the RTOS range."""
    lo = (RTOS_LO - BIAS) // 4; hi = min((RTOS_HI - BIAS) // 4, len(W))
    idx = np.arange(lo, hi)
    w = W[lo:hi]
    isb = (w & 0x0E000000) == 0x0A000000
    cond_ok = (w >> 28) != 0xF
    off = (w & 0x00FFFFFF).astype(np.int64)
    off = np.where(off & 0x800000, off - 0x1000000, off)
    va = BIAS + 4 * idx.astype(np.int64)
    tgt = va + 8 + 4 * off
    sel = isb & cond_ok & (tgt == target)
    out = []
    for i in np.nonzero(sel)[0]:
        link = bool(w[i] & 0x01000000)
        k = 'bl' if link else 'b'
        if k in kinds: out.append((int(va[i]), k))
    return out


def func_start(va, back=4000):
    """walk back to a 'mov ip, sp' / push prologue"""
    for a in range(va, va - 4 * back, -4):
        x = w32(a)
        if x == 0xE1A0C00D:  # mov ip, sp
            return a
        if (x & 0xFFFF0000) == 0xE92D0000 and (w32(a - 4) & 0x0FFFFFFF) in (0x012FFF1E,) :  # push after bx lr
            return a
    return None


def str_refs(s):
    """addresses of a string and words referencing it"""
    hits = [BIAS + m.start() for m in re.finditer(re.escape(s), IMG)]
    out = {}
    for h in hits:
        out[h] = [_word_va(int(i)) for i in np.nonzero(W == h)[0]]
    return out
