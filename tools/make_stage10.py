"""Stage 10 for GR IIIx 1.60: higher video bitrate, on top of stage 9.
Bitrate target 0x5366A3D4 (kbit/s, mode 0 = Full HD): fps<=30 -> K30*fps/30 (movw at 0x5366A3E8, stock 21000, the
'bitrate' patch made it 42000); fps>30 -> K60*fps/60 (movwhi at 0x5366A3E0, stock 42000). Peak = 1.5 x target
(0x5366A478). No clamp in MovieService or the H.264 setup (0x5365B2F8 passes +0x24/+0x20 straight through).
Usage: make_stage10.py in_image out_image K30 K60
"""
import sys, struct
B = 0x52FEF790
img = bytearray(open(sys.argv[1], 'rb').read())
k30, k60 = int(sys.argv[3]), int(sys.argv[4])
assert 0 < k30 <= 0xFFFF and 0 < k60 <= 0xFFFF
def movw(cond, rd, v): return 0x03000000 | cond << 28 | (v >> 12) << 16 | rd << 12 | (v & 0xFFF)
def w32(va): return struct.unpack_from('<I', img, va - B)[0]
assert w32(0x5366A3E8) == movw(0xE, 3, 42000), 'stage-9 30p constant not found'
assert w32(0x5366A3E0) == movw(0x8, 3, 42000), 'stock 60p constant not found'
struct.pack_into('<I', img, 0x5366A3E8 - B, movw(0xE, 3, k30))
struct.pack_into('<I', img, 0x5366A3E0 - B, movw(0x8, 3, k60))
open(sys.argv[2], 'wb').write(img)
for fps in (24, 30, 60):
    t = k30 * fps // 30 if fps <= 30 else k60 * fps // 60
    print(f'{fps}p: {t/1000:.1f} Mbit/s average, {1.5*t/1000:.1f} peak')
