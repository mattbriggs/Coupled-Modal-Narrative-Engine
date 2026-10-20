"""Generate the workbench's small, dependency-free PNG application icon."""

import struct
import zlib
from pathlib import Path


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


size = 128
rows = []
for y in range(size):
    row = bytearray([0])
    for x in range(size):
        color = (24, 32, 42, 255)
        if 20 <= x <= 106 and 23 <= y <= 102:
            color = (39, 69, 72, 255)
        if 31 <= x <= 95 and 30 <= y <= 49:
            color = (92, 218, 189, 255)
        if 38 <= x <= 102 and 55 <= y <= 74:
            color = (52, 174, 158, 255)
        if 26 <= x <= 90 and 80 <= y <= 99:
            color = (21, 124, 117, 255)
        row.extend(color)
    rows.append(bytes(row))
png = b"\x89PNG\r\n\x1a\n"
png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
png += chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
png += chunk(b"IEND", b"")
Path("app/src-tauri/icons/icon.png").write_bytes(png)
