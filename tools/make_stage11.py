"""Stage 11 for GR IIIx 1.60: GR-Log v2 on Vivid (stage 10a + new curve).
GR-Log v2 = judgem00's grlog with lo = -5.5 EV and span = top_ev - lo (top_ev = +3.46, the 12-bit tone input end), so the
camera's real top lands at the top of the code range (Y ~252 instead of ~239) and each stop gets ~28 codes instead of
~26 (camera test 2026-10-18: video clips exactly at the curve's top; toe data down to ~-6 EV). Only the 512-byte curve at
0x53002100 changes; colour set, ColorMatrix entry and the fill's Vivid case are stage 9's.
Usage: make_stage11.py stage10a_image grlog_v2_export_image out_image
"""
import sys, struct
import os
import numpy as np
B = 0x52FEF790
CURVE = 0x53002100
img = bytearray(open(sys.argv[1], 'rb').read()); g = open(sys.argv[2], 'rb').read()
stock = open(os.environ['GR3X_STOCK_IMAGE'], 'rb').read()
ptr = struct.unpack_from('<I', g, 0x53003D80 + 12 - B)[0]
ptrs = struct.unpack_from('<3I', g, 0x53003D80 + 12 - B)
new = [g[p - B:p - B + 512] for p in ptrs]; assert new[0] == new[1] == new[2]
c = np.frombuffer(new[0], '<u2')
assert np.all(np.diff(c.astype(int)) >= 0) and c[-1] <= 16383
# colour set / CM entry of this export identical to the ones already in the image (stage 9)
assert g[0x53003EA8 - B:0x53003EA8 - B + 0x68] == bytes(img[0x53003EA8 - B:0x53003EA8 - B + 0x68])
assert g[0x54094304 - B:0x54094308 - B] == bytes(img[0x54094304 - B:0x54094308 - B])
old = bytes(img[CURVE - B:CURVE - B + 512]); assert old != new[0] and any(old)
img[CURVE - B:CURVE - B + 512] = new[0]
open(sys.argv[3], 'wb').write(img)
print('curve replaced: top', c[-1], 'zeros', int((c == 0).sum()))
