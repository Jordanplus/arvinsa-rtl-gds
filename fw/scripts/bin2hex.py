#!/usr/bin/env python3
"""Flat binary -> $readmemh hex (docs/spec/soc_spec.md §6.1).

One 32-bit word per line, first line = word 0 of the image, bytes assembled
little-endian. A trailing partial word is zero-padded.
"""
import argparse
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bin")
    ap.add_argument("hex")
    args = ap.parse_args()
    data = Path(args.bin).read_bytes()
    if not data:
        print("bin2hex: ERROR: %s is empty" % args.bin, file=sys.stderr)
        return 1
    data += b"\0" * (-len(data) % 4)
    words = [int.from_bytes(data[i:i + 4], "little") for i in range(0, len(data), 4)]
    out = Path(args.hex)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text("".join("%08x\n" % w for w in words))
    tmp.replace(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
