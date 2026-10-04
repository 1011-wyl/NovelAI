from pathlib import Path
import struct
import zlib


def png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


width = height = 16
raw = b"".join(b"\x00" + bytes([0x31, 0x5F, 0x46, 255] * width) for _ in range(height))
ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
png = (
    b"\x89PNG\r\n\x1a\n"
    + png_chunk(b"IHDR", ihdr)
    + png_chunk(b"IDAT", zlib.compress(raw, 9))
    + png_chunk(b"IEND", b"")
)
ico = struct.pack("<HHH", 0, 1, 1)
ico += struct.pack("<BBBBHHII", width, height, 0, 0, 1, 32, len(png), 22)
ico += png
out = Path(__file__).resolve().parents[1] / "public" / "favicon.ico"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(ico)
print(out, out.stat().st_size)
