#!/usr/bin/env python3
"""Boot ROM image ($readmemh hex) -> rtl/bootrom/bootrom.v (docs/spec/soc_spec.md §4.6).

The output is a combinational case-ROM with the fixed interface
    module bootrom (input wire [6:0] addr, output reg [31:0] rdata);
Unused words return 32'h0000_006F (jal x0, 0). The output is deterministic:
the same hex always produces a byte-identical file (no dates, no host paths).
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

ROM_WORDS = 128          # addr[6:0], spec §4.6 / SOC_ROM_WORDS
DEFAULT_WORD = 0x0000006F
_HEXLINE = re.compile(r"^[0-9a-fA-F]{1,8}$")


def read_hex(path):
    words = []
    for lineno, raw in enumerate(Path(path).read_text().splitlines(), 1):
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        if line.startswith("@") or not _HEXLINE.match(line):
            raise ValueError("%s:%d: expected one 32-bit hex word per line, got %r" % (path, lineno, raw))
        words.append(int(line, 16))
    if not words:
        raise ValueError("%s: empty image" % path)
    if len(words) > ROM_WORDS:
        raise ValueError("%s: %d words exceed the %d-word boot ROM" % (path, len(words), ROM_WORDS))
    return words


def fmt32(v):
    return "32'h%04X_%04X" % (v >> 16, v & 0xFFFF)


def render(words, source):
    digest = hashlib.sha256(b"".join(w.to_bytes(4, "little") for w in words)).hexdigest()
    out = [
        "// -----------------------------------------------------------------------------",
        "// bootrom.v - GENERATED FILE, DO NOT EDIT.",
        "// Generator : rtl/bootrom/gen_bootrom.py",
        "// Source    : %s (%d of %d words used)" % (source, len(words), ROM_WORDS),
        "// Image hash: sha256 %s (little-endian bytes)" % digest,
        "// Regenerate: make -C fw bootrom      Staleness check: make -C fw check-bootrom",
        "// Interface : docs/spec/soc_spec.md section 4.6. Combinational case-ROM; the bus",
        "//             registers rdata. Unused words return 32'h0000_006F (jal x0, 0).",
        "// -----------------------------------------------------------------------------",
        "module bootrom (",
        "    input  wire [6:0]  addr,    // word address = mem_addr[8:2]",
        "    output reg  [31:0] rdata",
        ");",
        "    always @(*) begin",
        "        case (addr)",
    ]
    for i, w in enumerate(words):
        if w != DEFAULT_WORD:
            out.append("            7'd%-3d: rdata = %s;" % (i, fmt32(w)))
    out += [
        "            default: rdata = %s;" % fmt32(DEFAULT_WORD),
        "        endcase",
        "    end",
        "endmodule",
        "",
    ]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hex", required=True, help="boot ROM image, one 32-bit word per line")
    ap.add_argument("--out", required=True, help="output Verilog file")
    ap.add_argument("--source", default="fw/bootrom/bootrom.S", help="source named in the header")
    args = ap.parse_args()
    try:
        words = read_hex(args.hex)
    except (OSError, ValueError) as exc:
        print("gen_bootrom: ERROR: %s" % exc, file=sys.stderr)
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(render(words, args.source))
    tmp.replace(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
