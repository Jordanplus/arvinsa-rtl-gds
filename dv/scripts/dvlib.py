"""Shared library for the DV scripts (run_sim.py, regress.py, neg.py).

Contract: docs/spec/soc_spec.md section 7 (DV), section 6.5 (UART loader frame).
Python >= 3.11, standard library only. Every path is resolved against the repo
root, so the scripts work from any current directory.

Main entry points:
    parse_memmap(path)            `define constants of rtl/include/memmap.vh
    load_tests(path)              dv/tests.toml, validated
    load_bugs(path, tests)        dv/bugs.toml, validated
    crc32(data)                   IEEE 802.3 CRC32 (same as zlib.crc32)
    uart_loader_frame(image, kind) boot ROM UART loader frame (spec 6.5 step 4)
    elf_symbols(path)             symbol table of a firmware ELF (sram_cov, reset_on_store)
    tool_identity(sim)            simulator / C++ compiler versions (build cache key)
    build(sim, defines, ...)      cached compile under runs/sim_build/
    run_test(...)                 one simulation + verdict -> result.json
"""

import fcntl
import functools
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
import tomllib
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------- contract names
SIMS = ("icarus", "verilator")
LOADS = ("backdoor", "host", "uart", "none")
CHECKERS = (
    "test_ctrl", "signature", "trap", "timeout", "uart_monitor", "uart_golden",
    "gpio_seq", "bus_assert", "x_check", "log_scan", "sim_error",
    # Added by the Phase 1 testbench qualification fixes (dv/README.md):
    "sram_port", "irq_line", "uart_div", "coverage",
)
# Checkers implemented in the testbench (they print "[CHK:<name>] FAIL ...").
TB_CHECKERS = ("test_ctrl", "trap", "timeout", "uart_monitor", "bus_assert", "x_check",
               "sram_port", "irq_line", "uart_div")

# ---------------------------------------------------------------- repo files
MEMMAP = "rtl/include/memmap.vh"
RTL_F = "rtl/rtl.f"
DV_F = "dv/tb/dv.f"
TIMESCALE_V = "dv/tb/timescale.v"
VLT_WAIVERS = "dv/tb/sim_waivers.vlt"
SRAM_MODEL = "ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/sim/sky130_sram_2kbyte_1rw1r_32x512_8.v"
TESTS_TOML = "dv/tests.toml"
BUGS_TOML = "dv/bugs.toml"
WHITELIST = "dv/log_whitelist.txt"
FW_DIR = "fw/build"
SIM_BUILD = "runs/sim_build"
BOOTROM_V = "rtl/bootrom/bootrom.v"
TOP = "tb_soc"

# Spec 6.5 step 4: 1 <= N <= 448 words (0x700 bytes: SRAM below the stack reserve).
LOADER_MAX_WORDS = 448
# tests.toml loader_frame values (load = "uart" only):
#   valid         N, image, checksum (default)
#   max_words     image zero-padded to LOADER_MAX_WORDS words (upper bound of N)
#   bad_checksum  valid frame with checksum + 1 (boot ROM must reject it)
#   n_zero        N = 0 and a checksum byte 0, no image (boot ROM must reject it)
#   n_too_big     only the 2-byte header N = LOADER_MAX_WORDS + 1 (must be
#                 rejected right after the header; a boot ROM that waits for
#                 the image times out)
LOADER_FRAMES = ("valid", "max_words", "bad_checksum", "n_zero", "n_too_big")
# Keys every complete tb_result.txt carries (tb_soc.v finish_sim). fail.<name>
# for each testbench checker is checked separately (x_check: Icarus only).
TB_RESULT_KEYS = ("end_reason", "done_count", "done", "done_cycle", "sig", "sig_at_done", "cycles",
                  "cpu_start_cycle", "uart_bytes", "unmapped", "uart_wr", "uart_wr_stalled",
                  "uart_wr_stall_cycles", "sram_port_accesses", "mid_resets", "simulator", "finished")
# tests.toml sram_cov rule keys (coverage checker): from/to (byte address or ELF
# symbol of the test image, to exclusive), exact counts rd/wr/fetch, lower
# bounds min_rd/min_wr, and wstrb = write strobes every word must see.
SRAM_COV_KEYS = {"from", "to", "rd", "wr", "fetch", "min_rd", "min_wr", "wstrb"}
SRAM_COV_COUNTS = ("rd", "wr", "fetch", "min_rd", "min_wr")
# Cycles between CPU release and the first byte on uart_rx: two UART frames, so
# the boot ROM / firmware has written DIV and reached its receive loop.
UART_IN_DELAY = 400

CHK_LINE_RE = re.compile(r"^\[CHK:([A-Za-z0-9_]+)\] FAIL (.*)$")
# log_scan keywords (spec 7.2 log_scan row, project-plan.md 7.1 item 8).
LOG_SCAN_RE = re.compile(
    r"\berror\b|\bfatal\b|\bwarning\b|writing and reading|unable to find",
    re.IGNORECASE,
)
NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


class DvError(Exception):
    """Configuration or input error that prevents a run."""


def rel(path):
    """Repo-relative string for a path (absolute string if outside the repo)."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        return str(p)


def repo_path(path):
    p = Path(path)
    return p if p.is_absolute() else REPO / p


def default_jobs():
    return max(1, (os.cpu_count() or 1) - 2)


# ---------------------------------------------------------------- memmap.vh
_DEFINE_RE = re.compile(
    r"^\s*`define\s+([A-Za-z_][A-Za-z0-9_]*)\s+"
    r"(?:(\d+)'[hH]([0-9a-fA-F_]+)|(\d[0-9_]*))\s*(?://.*)?$"
)


def parse_memmap(path=MEMMAP):
    """Return {name: int} for every `define with a numeric value.

    Rule (memmap.vh header): `define NAME <width>'h<hex> or `define NAME
    <decimal>; underscores are separators. Other lines are ignored.
    """
    values = {}
    for lineno, line in enumerate(repo_path(path).read_text().splitlines(), 1):
        m = _DEFINE_RE.match(line)
        if not m:
            continue
        name = m.group(1)
        if m.group(3) is not None:
            width = int(m.group(2))
            value = int(m.group(3).replace("_", ""), 16)
            if value >= (1 << width):
                raise DvError("%s:%d: %s value 0x%x does not fit in %d bits"
                              % (path, lineno, name, value, width))
        else:
            value = int(m.group(4).replace("_", ""), 10)
        if name in values:
            raise DvError("%s:%d: %s defined twice" % (path, lineno, name))
        values[name] = value
    return values


# ---------------------------------------------------------------- TOML config
_TEST_FIELDS = {
    "name", "load", "boot_mode", "max_cycles", "expect_uart", "sig_rule",
    "expect_gpio", "uart_in", "smoke", "negative_only", "fw",
    "min_cycles", "loader_frame", "expect_unmapped",
    "sram_cov", "min_uart_stalls", "reset_on_store",
}
_TEST_REQUIRED = ("name", "load", "boot_mode", "max_cycles", "sig_rule")
_BUG_FIELDS = {"id", "define", "test", "sim", "expect_checkers", "expect_regex"}
_BUG_OPTIONAL = {"exclusive", "expect_gpio", "fw", "bootrom"}


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def parse_sig_rule(rule):
    """Return ("uart_crc32", None) | ("const", value) | ("none", None)."""
    if rule == "uart_crc32":
        return ("uart_crc32", None)
    if rule == "none":
        return ("none", None)
    m = re.match(r"^const:(0[xX][0-9a-fA-F_]+|[0-9]+)$", rule)
    if m:
        value = int(m.group(1).replace("_", ""), 0)
        if value >> 32:
            raise DvError("sig_rule %r: constant wider than 32 bits" % rule)
        return ("const", value)
    raise DvError("sig_rule %r: expected uart_crc32, const:0x<hex> or none" % rule)


def _addr_or_symbol(v):
    """tests.toml address field: a word-aligned SRAM byte address or an ELF symbol name."""
    if isinstance(v, str):
        return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", v))
    return _is_int(v) and 0 <= v <= 0x800 and v % 4 == 0


def _check_sram_cov(where, t):
    rules = t["sram_cov"]
    if not isinstance(rules, list) or not rules:
        raise DvError("%s: sram_cov must be a non-empty list of rule tables" % where)
    for i, r in enumerate(rules, 1):
        w = "%s: sram_cov rule %d" % (where, i)
        if not isinstance(r, dict):
            raise DvError("%s: must be a table" % w)
        unknown = set(r) - SRAM_COV_KEYS
        if unknown:
            raise DvError("%s: unknown keys %s (allowed: %s)" % (w, sorted(unknown), sorted(SRAM_COV_KEYS)))
        for k in ("from", "to"):
            if k not in r or not _addr_or_symbol(r[k]):
                raise DvError("%s: %s must be a word-aligned SRAM byte address or a symbol name" % (w, k))
            if isinstance(r[k], str) and t["load"] not in ("backdoor", "host", "uart"):
                raise DvError("%s: a symbol in %s needs a test that loads an image" % (w, k))
        if not any(k in r for k in SRAM_COV_COUNTS + ("wstrb",)):
            raise DvError("%s: no count rule (one of %s, wstrb)" % (w, ", ".join(SRAM_COV_COUNTS)))
        for k in SRAM_COV_COUNTS:
            if k in r and (not _is_int(r[k]) or r[k] < 0):
                raise DvError("%s: %s must be a non-negative integer" % (w, k))
        if "wstrb" in r:
            g = r["wstrb"]
            if not isinstance(g, list) or not g or not all(_is_int(v) and 1 <= v <= 15 for v in g):
                raise DvError("%s: wstrb must be a non-empty list of write strobes 1..15" % w)


def load_tests(path=TESTS_TOML):
    """Load and validate dv/tests.toml. Returns {name: test dict} in file order."""
    p = repo_path(path)
    with open(p, "rb") as f:
        data = tomllib.load(f)
    extra = set(data) - {"test"}
    if extra:
        raise DvError("%s: unknown top-level keys %s" % (rel(p), sorted(extra)))
    tests = {}
    for i, t in enumerate(data.get("test", [])):
        where = "%s: [[test]] #%d" % (rel(p), i + 1)
        unknown = set(t) - _TEST_FIELDS
        if unknown:
            raise DvError("%s: unknown fields %s" % (where, sorted(unknown)))
        for k in _TEST_REQUIRED:
            if k not in t:
                raise DvError("%s: missing field %r" % (where, k))
        name = t["name"]
        if not isinstance(name, str) or not NAME_RE.match(name):
            raise DvError("%s: bad name %r" % (where, name))
        where = "%s: test %s" % (rel(p), name)
        if name in tests:
            raise DvError("%s: duplicate test name" % where)
        if t["load"] not in LOADS:
            raise DvError("%s: load %r not in %s" % (where, t["load"], LOADS))
        if not _is_int(t["boot_mode"]) or not 0 <= t["boot_mode"] <= 3:
            raise DvError("%s: boot_mode must be 0..3" % where)
        if not _is_int(t["max_cycles"]) or t["max_cycles"] <= 0:
            raise DvError("%s: max_cycles must be a positive integer" % where)
        if not isinstance(t["sig_rule"], str):
            raise DvError("%s: sig_rule must be a string" % where)
        parse_sig_rule(t["sig_rule"])
        if "expect_uart" in t and not isinstance(t["expect_uart"], str):
            raise DvError("%s: expect_uart must be a string" % where)
        if "expect_gpio" in t:
            g = t["expect_gpio"]
            if not isinstance(g, list) or not all(_is_int(v) and 0 <= v <= 0xFF for v in g):
                raise DvError("%s: expect_gpio must be a list of 8-bit integers" % where)
        if not isinstance(t.get("uart_in", ""), str):
            raise DvError("%s: uart_in must be a string" % where)
        for k in ("smoke", "negative_only"):
            if not isinstance(t.get(k, False), bool):
                raise DvError("%s: %s must be true or false" % (where, k))
        if "fw" in t and (not isinstance(t["fw"], str) or not NAME_RE.match(t["fw"])):
            raise DvError("%s: bad fw %r" % (where, t.get("fw")))
        if "min_cycles" in t and (not _is_int(t["min_cycles"]) or not 0 < t["min_cycles"] < t["max_cycles"]):
            raise DvError("%s: min_cycles must be an integer with 0 < min_cycles < max_cycles" % where)
        if "loader_frame" in t:
            if t["load"] != "uart":
                raise DvError("%s: loader_frame needs load = \"uart\"" % where)
            if t["loader_frame"] not in LOADER_FRAMES:
                raise DvError("%s: loader_frame %r not in %s" % (where, t["loader_frame"], LOADER_FRAMES))
        if "expect_unmapped" in t and (not _is_int(t["expect_unmapped"]) or t["expect_unmapped"] < 1):
            raise DvError("%s: expect_unmapped must be a positive integer" % where)
        if "sram_cov" in t:
            _check_sram_cov(where, t)
        if "min_uart_stalls" in t and (not _is_int(t["min_uart_stalls"]) or t["min_uart_stalls"] < 1):
            raise DvError("%s: min_uart_stalls must be a positive integer" % where)
        if "reset_on_store" in t:
            if not _addr_or_symbol(t["reset_on_store"]):
                raise DvError("%s: reset_on_store must be a word-aligned SRAM byte address or a symbol name" % where)
            if isinstance(t["reset_on_store"], str) and t["load"] not in ("backdoor", "host", "uart"):
                raise DvError("%s: a reset_on_store symbol needs a test that loads an image" % where)
        if not t.get("negative_only", False):
            # A positive test must compare every output (Q-F7): a run that only
            # writes DONE = PASS must not be enough.
            missing = [k for k in ("expect_uart", "expect_gpio") if k not in t]
            if missing:
                raise DvError("%s: a positive test (negative_only = false) needs %s"
                              % (where, " and ".join(missing)))
            if t["sig_rule"] == "none":
                raise DvError("%s: a positive test (negative_only = false) needs a sig_rule other than none"
                              % where)
        tt = dict(t)
        tt.setdefault("uart_in", "")
        tt.setdefault("smoke", False)
        tt.setdefault("negative_only", False)
        tt.setdefault("fw", name)
        tt.setdefault("loader_frame", "valid")
        tests[name] = tt
    if not tests:
        raise DvError("%s: no [[test]] entries" % rel(p))
    return tests


def load_bugs(path=BUGS_TOML, tests=None):
    """Load and validate dv/bugs.toml. Returns {id: bug dict} in file order."""
    p = repo_path(path)
    with open(p, "rb") as f:
        data = tomllib.load(f)
    extra = set(data) - {"bug"}
    if extra:
        raise DvError("%s: unknown top-level keys %s" % (rel(p), sorted(extra)))
    bugs = {}
    for i, b in enumerate(data.get("bug", [])):
        where = "%s: [[bug]] #%d" % (rel(p), i + 1)
        unknown = set(b) - _BUG_FIELDS - _BUG_OPTIONAL
        if unknown:
            raise DvError("%s: unknown fields %s" % (where, sorted(unknown)))
        missing = _BUG_FIELDS - set(b)
        if missing:
            raise DvError("%s: missing fields %s" % (where, sorted(missing)))
        bid = b["id"]
        if not isinstance(bid, str) or not NAME_RE.match(bid):
            raise DvError("%s: bad id %r" % (where, bid))
        where = "%s: bug %s" % (rel(p), bid)
        if bid in bugs:
            raise DvError("%s: duplicate id" % where)
        if not isinstance(b["define"], str) or (b["define"] and not NAME_RE.match(b["define"])):
            raise DvError("%s: bad define %r" % (where, b["define"]))
        if tests is not None and b["test"] not in tests:
            raise DvError("%s: unknown test %r" % (where, b["test"]))
        if b["sim"] not in SIMS:
            raise DvError("%s: sim %r not in %s" % (where, b["sim"], SIMS))
        ec = b["expect_checkers"]
        if not isinstance(ec, list) or not ec or not all(c in CHECKERS for c in ec):
            raise DvError("%s: expect_checkers must be a non-empty list of %s" % (where, CHECKERS))
        if b["sim"] != "icarus" and "x_check" in ec and len(ec) == 1:
            raise DvError("%s: x_check exists only on icarus" % where)
        if not isinstance(b["expect_regex"], str):
            raise DvError("%s: expect_regex must be a string" % where)
        try:
            re.compile(b["expect_regex"])
        except re.error as e:
            raise DvError("%s: expect_regex does not compile: %s" % (where, e))
        if not isinstance(b.get("exclusive", False), bool):
            raise DvError("%s: exclusive must be true or false" % where)
        if "expect_gpio" in b:
            g = b["expect_gpio"]
            if not isinstance(g, list) or not all(_is_int(v) and 0 <= v <= 0xFF for v in g):
                raise DvError("%s: expect_gpio must be a list of 8-bit integers" % where)
        # Firmware / boot ROM bug variants (fw/README.md): fw names a variant
        # image fw/build/<fw>.*, bootrom a variant ROM fw/build/bootrom__<bootrom>.v
        # that replaces rtl/bootrom/bootrom.v for this run only.
        for k in ("fw", "bootrom"):
            if k in b and (not isinstance(b[k], str) or not NAME_RE.match(b[k])):
                raise DvError("%s: bad %s %r" % (where, k, b[k]))
        if b["define"] and ("fw" in b or "bootrom" in b):
            raise DvError("%s: an entry injects either an RTL define or a fw/bootrom variant, not both" % where)
        bb = dict(b)
        bb.setdefault("exclusive", False)
        bugs[bid] = bb
    if not bugs:
        raise DvError("%s: no [[bug]] entries" % rel(p))
    return bugs


def load_whitelist(path=WHITELIST):
    """Regexes from dv/log_whitelist.txt ('#' comment lines and blank lines skipped)."""
    p = repo_path(path)
    pats = []
    if not p.exists():
        return pats
    for lineno, line in enumerate(p.read_text().splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        try:
            pats.append(re.compile(s))
        except re.error as e:
            raise DvError("%s:%d: bad regex: %s" % (rel(p), lineno, e))
    return pats


# ---------------------------------------------------------------- data helpers
def crc32(data):
    """IEEE 802.3 CRC32, identical to zlib.crc32 (spec 6.3)."""
    return zlib.crc32(bytes(data)) & 0xFFFFFFFF


def uart_loader_frame(image, kind="valid"):
    """Boot ROM UART loader frame (spec 6.5 step 4).

    N (2 bytes, little-endian, word count) + N*4 image bytes (zero-padded to a
    whole word) + 1 checksum byte (sum of the N*4 image bytes mod 256).
    kind (LOADER_FRAMES) selects a deliberately malformed frame for the
    negative tests of the boot ROM error handling; n_zero and n_too_big
    ignore image.
    """
    if kind not in LOADER_FRAMES:
        raise DvError("unknown loader frame kind %r (expected one of %s)" % (kind, LOADER_FRAMES))
    if kind == "n_zero":
        return (0).to_bytes(2, "little") + bytes([0])
    if kind == "n_too_big":
        return (LOADER_MAX_WORDS + 1).to_bytes(2, "little")
    img = bytes(image)
    img += b"\0" * (-len(img) % 4)
    if kind == "max_words":
        img += b"\0" * (LOADER_MAX_WORDS * 4 - len(img))
    n = len(img) // 4
    if not 1 <= n <= LOADER_MAX_WORDS:
        raise DvError("UART loader image has %d words; spec 6.5 allows 1..%d"
                      % (n, LOADER_MAX_WORDS))
    checksum = sum(img) & 0xFF
    if kind == "bad_checksum":
        checksum = (checksum + 1) & 0xFF
    return n.to_bytes(2, "little") + img + bytes([checksum])


def elf_symbols(path):
    """{name: value} from the symbol table of a 32-bit little-endian ELF
    (riscv64-elf-gcc -mabi=ilp32 output). A name defined twice with different
    values maps to None (ambiguous)."""
    data = Path(path).read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        raise DvError("%s: not a 32-bit little-endian ELF file" % rel(path))
    try:
        e_shoff = struct.unpack_from("<I", data, 0x20)[0]
        e_shentsize, e_shnum = struct.unpack_from("<HH", data, 0x2E)
        secs = [struct.unpack_from("<10I", data, e_shoff + i * e_shentsize) for i in range(e_shnum)]
        syms = {}
        for sh in secs:
            if sh[1] != 2:          # SHT_SYMTAB
                continue
            str_off = secs[sh[6]][4]
            for j in range(sh[5] // 16):
                st_name, st_value = struct.unpack_from("<II", data, sh[4] + 16 * j)
                if not st_name:
                    continue
                start = str_off + st_name
                name = data[start:data.index(b"\0", start)].decode("ascii", "replace")
                if name in syms and syms[name] != st_value:
                    syms[name] = None
                else:
                    syms[name] = st_value
    except (struct.error, ValueError, IndexError) as e:
        raise DvError("%s: malformed ELF file: %s" % (rel(path), e))
    return syms


def resolve_addr(value, elf, what):
    """tests.toml address field -> int (symbol names are looked up in elf)."""
    if not isinstance(value, str):
        return value
    if elf is None or not Path(elf).is_file():
        raise DvError("%s: symbol %s needs the firmware ELF %s (build it with 'make fw')"
                      % (what, value, rel(elf) if elf else "(none)"))
    syms = elf_symbols(elf)
    if syms.get(value) is None:
        raise DvError("%s: symbol %s %s in %s" % (what, value,
                      "is ambiguous" if value in syms else "not found", rel(elf)))
    return syms[value]


def read_sram_cov(path, words):
    """tb_soc sram_cov.txt -> list (index = word) of (data_reads, fetches, writes, wstrb_mask)."""
    rows = [None] * words
    for lineno, line in enumerate(Path(path).read_text(errors="replace").splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        f = s.split()
        try:
            addr, rd, fetch, wr, mask = int(f[0], 16), int(f[1]), int(f[2]), int(f[3]), int(f[4], 16)
        except (IndexError, ValueError):
            raise DvError("%s:%d: malformed line %r" % (rel(path), lineno, s))
        if addr % 4 or not 0 <= addr // 4 < words or rows[addr // 4] is not None:
            raise DvError("%s:%d: bad or repeated address 0x%x" % (rel(path), lineno, addr))
        rows[addr // 4] = (rd, fetch, wr, mask)
    if any(r is None for r in rows):
        raise DvError("%s: %d of %d words missing" % (rel(path), rows.count(None), words))
    return rows


def check_sram_cov(rules, rows, elf):
    """Evaluate tests.toml sram_cov rules. Returns a list of FAIL messages."""
    fails = []
    for i, r in enumerate(rules, 1):
        lo = resolve_addr(r["from"], elf, "sram_cov rule %d from" % i)
        hi = resolve_addr(r["to"], elf, "sram_cov rule %d to" % i)
        if lo % 4 or hi % 4 or not 0 <= lo < hi <= 4 * len(rows):
            fails.append("SRAM coverage rule %d: empty or bad range [0x%x, 0x%x)" % (i, lo, hi))
            continue
        bad = []
        for w in range(lo // 4, hi // 4):
            rd, fetch, wr, mask = rows[w]
            why = []
            for key, got, exact in (("rd", rd, True), ("wr", wr, True), ("fetch", fetch, True),
                                    ("min_rd", rd, False), ("min_wr", wr, False)):
                if key in r and ((got != r[key]) if exact else (got < r[key])):
                    why.append("%s %d (expected %s%d)" % (
                        {"rd": "data reads", "wr": "writes", "fetch": "fetches",
                         "min_rd": "data reads", "min_wr": "writes"}[key],
                        got, "" if exact else ">= ", r[key]))
            missing = [v for v in r.get("wstrb", []) if not mask >> v & 1]
            if missing:
                why.append("write strobes %s never seen" % ",".join("%x" % v for v in missing))
            if why:
                bad.append("0x%03x: %s" % (4 * w, ", ".join(why)))
        if bad:
            fails.append("SRAM coverage rule %d [0x%03x, 0x%03x): %d of %d words off; %s%s"
                         % (i, lo, hi, len(bad), (hi - lo) // 4, "; ".join(bad[:3]),
                            "; ..." if len(bad) > 3 else ""))
    return fails


def variant_rtl_f(rtl_f, bootrom_v):
    """Filelist = rtl_f with rtl/bootrom/bootrom.v replaced by bootrom_v (a boot
    ROM bug variant from fw/build). Written under runs/sim_build/filelists/."""
    src = repo_path(rtl_f)
    lines = src.read_text().splitlines()
    hits = [i for i, l in enumerate(lines) if l.strip() == BOOTROM_V]
    if len(hits) != 1:
        raise DvError("%s: expected exactly one %s line to replace" % (rel(src), BOOTROM_V))
    lines[hits[0]] = rel(bootrom_v)
    out = REPO / SIM_BUILD / "filelists" / ("rtl__%s.f" % Path(bootrom_v).stem)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    if not out.exists() or out.read_text() != text:
        tmp = out.with_name(out.name + ".%d.%d.tmp" % (os.getpid(), threading.get_ident()))
        tmp.write_text(text)
        tmp.replace(out)
    return rel(out)


def hex_word_count(path):
    """Number of 32-bit words in a $readmemh image written by fw/scripts/bin2hex.py."""
    n = 0
    for lineno, line in enumerate(Path(path).read_text().splitlines(), 1):
        s = line.split("//")[0].strip()
        if not s:
            continue
        if not re.match(r"^[0-9a-fA-F_]{1,8}$", s):
            raise DvError("%s:%d: not a one-word-per-line hex image: %r" % (rel(path), lineno, s))
        n += 1
    return n


def read_filelist(path):
    """Parse a .f file (spec 1): one path or +incdir+<dir> per line, no comments.

    Returns (incdirs, files) as absolute Paths.
    """
    p = repo_path(path)
    incdirs, files = [], []
    for lineno, line in enumerate(p.read_text().splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        if s.startswith("+incdir+"):
            incdirs.append(repo_path(s[len("+incdir+"):]).resolve())
        elif s.startswith("+") or s.startswith("-"):
            raise DvError("%s:%d: unsupported filelist option %r" % (rel(p), lineno, s))
        else:
            files.append(repo_path(s).resolve())
    return incdirs, files


# ---------------------------------------------------------------- compile (cached)
class BuildResult:
    def __init__(self, sim, ok, build_dir, exe, log, cmd, cached, message=""):
        self.sim = sim
        self.ok = ok
        self.build_dir = build_dir
        self.exe = exe
        self.log = log
        self.cmd = cmd
        self.cached = cached
        self.message = message


def _sources(rtl_f):
    """Simulation sources (spec 7): timescale.v + rtl.f + SRAM sim model + dv.f."""
    incdirs, files = [], [repo_path(TIMESCALE_V).resolve()]
    i1, f1 = read_filelist(rtl_f)
    i2, f2 = read_filelist(DV_F)
    for d in i1 + i2:
        if d not in incdirs:
            incdirs.append(d)
    files += f1 + [repo_path(SRAM_MODEL).resolve()] + f2
    return incdirs, files


def _first_line(cmd):
    """First non-empty output line of a version command, or a marker when it cannot run."""
    try:
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "unavailable (%s: %s)" % (" ".join(cmd), e)
    for line in cp.stdout.decode(errors="replace").splitlines():
        if line.strip():
            return line.strip()
    return "no output (%s, exit code %d)" % (" ".join(cmd), cp.returncode)


def _which(tool):
    w = shutil.which(tool)
    return os.path.realpath(w) if w else "not found in PATH"


@functools.lru_cache(maxsize=None)
def tool_identity(sim):
    """Identity of every tool that builds or runs a simulation of `sim`:
    resolved path and first version line. Part of the build cache key, so an
    upgraded simulator or C++ compiler forces a rebuild (REPRO-02), and
    recorded in result.json. Cached per process."""
    if sim == "icarus":
        tools = (("iverilog", ["iverilog", "-V"]), ("vvp", ["vvp", "-V"]))
    else:
        # Verilator --binary compiles and links the model with the C++ compiler
        # named in its verilated.mk (CXX = c++, found through PATH).
        tools = (("verilator", ["verilator", "--version"]), ("c++", ["c++", "--version"]))
    return tuple((name, _which(name), _first_line(cmd)) for name, cmd in tools)


def build_tag(sim, defines, rtl_f, trace):
    tag = "+".join(sorted(defines)) if defines else "default"
    if rel(repo_path(rtl_f)) != RTL_F:
        tag += "-rtlf" + hashlib.sha256(rel(repo_path(rtl_f)).encode()).hexdigest()[:8]
    if trace and sim == "verilator":
        tag += "-trace"
    return tag


def build(sim, defines=(), rtl_f=RTL_F, trace=False, extra_files=(), extra_flags=(), variant=None):
    """Compile tb_soc for one (simulator, defines) pair, reusing a cached build.

    extra_files / extra_flags / variant: used by the gate-level lockstep build
    (dv/gl_soc/run_gl_soc.py): extra source files after the RTL and SRAM model,
    extra compiler flags (e.g. -DUNIT_DELAY=#1), and a name appended to the
    build directory. Both are part of the cache key like every other input.

    The cache key is a SHA-256 over the compile command, the identity of the
    simulator and C++ compiler (tool_identity: resolved path + version line),
    and the content of every source file and every file in the include
    directories, so any edit or tool change forces a rebuild. A file lock
    serializes concurrent builds of the same configuration.
    """
    if sim not in SIMS:
        raise DvError("unknown simulator %r" % sim)
    defines = sorted(set(defines))
    for d in defines:
        if not NAME_RE.match(d):
            raise DvError("bad define %r" % d)
    tag = build_tag(sim, defines, rtl_f, trace)
    if variant:
        if not NAME_RE.match(variant):
            raise DvError("bad build variant %r" % variant)
        tag += "-" + variant
    bdir = REPO / SIM_BUILD / sim / tag
    bdir.mkdir(parents=True, exist_ok=True)
    log = bdir / "compile.log"
    try:
        incdirs, files = _sources(rtl_f)
        files += [Path(f).resolve() for f in extra_files]
    except (OSError, DvError) as e:
        return BuildResult(sim, False, bdir, None, log, [], False, "filelist error: %s" % e)
    missing = [f for f in files if not f.is_file()]
    if missing:
        log.write_text("".join("missing source file: %s\n" % rel(f) for f in missing))
        return BuildResult(sim, False, bdir, None, log, [], False,
                           "missing source file(s): %s" % ", ".join(rel(f) for f in missing))

    flist = bdir / "files.f"
    flist_text = "".join("+incdir+%s\n" % d for d in incdirs) + "".join("%s\n" % f for f in files)
    dflags = ["-D%s" % d for d in defines] + list(extra_flags)
    if sim == "icarus":
        exe = bdir / "tb_soc.vvp"
        cmd = ["iverilog", "-g2012", "-Wimplicit", "-Wportbind", "-Wselect-range",
               "-s", TOP, "-o", str(exe)] + dflags + ["-c", str(flist)]
    else:
        exe = bdir / "obj" / "Vtb_soc"
        cmd = ["verilator", "--binary", "--timing", "-Wno-fatal", "--top-module", TOP,
               "--timescale", "1ns/1ps", "--Mdir", str(bdir / "obj"), "-o", "Vtb_soc",
               "-j", str(default_jobs())] + dflags
        if trace:
            cmd.append("--trace")
        cmd += [str(repo_path(VLT_WAIVERS).resolve()), "-f", str(flist)]

    h = hashlib.sha256()
    h.update("\0".join(cmd).encode())
    for name, path, version in tool_identity(sim):
        h.update(("tool\0%s\0%s\0%s\0" % (name, path, version)).encode())
    h.update(flist_text.encode())
    hashed = list(files)
    if sim == "verilator":
        hashed.append(repo_path(VLT_WAIVERS).resolve())
    for d in incdirs:
        if d.is_dir():
            hashed += sorted(x for x in d.iterdir()
                             if x.is_file() and x.suffix in (".v", ".vh", ".sv", ".svh"))
    for f in hashed:
        h.update(str(f).encode() + b"\0")
        h.update(f.read_bytes())
    digest = h.hexdigest()
    stamp = bdir / "stamp.sha256"

    with open(bdir.parent / (tag + ".lock"), "w") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        if stamp.exists() and stamp.read_text().strip() == digest and exe.exists() and log.exists():
            return BuildResult(sim, True, bdir, exe, log, cmd, True)
        if stamp.exists():
            stamp.unlink()
        if sim == "verilator" and (bdir / "obj").exists():
            shutil.rmtree(bdir / "obj")
        if exe.exists():
            exe.unlink()
        flist.write_text(flist_text)
        t0 = time.time()
        with open(log, "w") as lf:
            lf.write("# cwd: %s\n# cmd: %s\n" % (REPO, " ".join(cmd)))
            for name, path, version in tool_identity(sim):
                lf.write("# tool: %s = %s (%s)\n" % (name, version, path))
            lf.flush()
            try:
                rc = subprocess.run(cmd, cwd=str(REPO), stdout=lf, stderr=subprocess.STDOUT,
                                    timeout=1800).returncode
            except FileNotFoundError as e:
                lf.write("cannot run %s: %s\n" % (cmd[0], e))
                rc = 127
            except subprocess.TimeoutExpired:
                lf.write("compile wall-clock timeout (1800 s)\n")
                rc = 124
            lf.write("# exit code %d after %.1f s\n" % (rc, time.time() - t0))
        if rc != 0 or not exe.exists():
            return BuildResult(sim, False, bdir, None, log, cmd, False,
                               "compile failed (exit code %d), see %s" % (rc, rel(log)))
        stamp.write_text(digest + "\n")
        return BuildResult(sim, True, bdir, exe, log, cmd, False)


def compile_log_lines(log):
    """Tool output lines of a compile log, without our own '#' header/footer lines
    and without the C++ compiler command lines of a Verilator build."""
    out = []
    for line in Path(log).read_text(errors="replace").splitlines():
        if (line.startswith("# cwd: ") or line.startswith("# cmd: ") or line.startswith("# tool: ")
                or line.startswith("# exit code ")):
            continue
        s = line.lstrip()
        # Verilator's generated make runs the C++ compiler with long flag lists
        # (for example -Wno-...); those command echoes are not diagnostics.
        if re.match(r"^(ccache\s+)?(\S*/)?(c\+\+|g\+\+|clang\+\+|cc|gcc|clang|ar|ranlib|make|echo|rm|python3?)(\s|$)", s):
            continue
        if s.startswith("make[") or s.startswith("make:"):
            continue
        out.append(line)
    return out


# ---------------------------------------------------------------- one run
def _new_result(test, sim, bug):
    return {
        "test": test, "sim": sim, "bug": bug, "status": "FAIL",
        "failing_checkers": [], "messages": [],
        "cycles": None, "uart_text": "", "sig": None, "done": None, "log": None,
    }


class _Verdict:
    def __init__(self, result):
        self.r = result

    def fail(self, name, msg):
        if name not in self.r["failing_checkers"]:
            self.r["failing_checkers"].append(name)
        self.r["messages"].append("[CHK:%s] FAIL %s" % (name, msg))

    def has(self, name):
        return name in self.r["failing_checkers"]


def _parse_tb_result(path):
    vals = {}
    for line in Path(path).read_text(errors="replace").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals


def _int_or_none(s):
    try:
        return int(s, 0)
    except (TypeError, ValueError):
        return None


def default_timeout(max_cycles):
    """Wall-clock limit in seconds for one simulation run."""
    return int(120 + max_cycles / 4000)


def run_test(test_name, sim, bug_id=None, out_root="runs/sim", trace=False, vcd=False,
             rtl_f=RTL_F, tests_toml=TESTS_TOML, bugs_toml=BUGS_TOML, fw_dir=FW_DIR,
             extra_plusargs=(), max_cycles=None, timeout=None, build_result=None,
             quiet=False):
    """Run one test on one simulator and write <out>/<sim>/<test>[__<bug>]/result.json.

    Returns the result dict. status is "PASS" only with explicit evidence
    (spec 7.4): DONE = PASS magic written exactly once, no checker FAIL, clean
    log scan, normal end of simulation. Anything missing gives FAIL.
    """
    result = _new_result(test_name, sim, bug_id)
    v = _Verdict(result)
    t_start = time.time()
    run_dir = repo_path(out_root) / sim / (test_name + ("__" + bug_id if bug_id else ""))

    def finish():
        result["status"] = "FAIL" if result["failing_checkers"] else "PASS"
        result["wall_time_s"] = round(time.time() - t_start, 2)
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        except OSError as e:
            print("run_sim: cannot write result.json: %s" % e, file=sys.stderr)
            result["status"] = "FAIL"
        result["result_json"] = rel(run_dir / "result.json")
        if not quiet:
            print_summary(result)
        return result

    # ---- configuration ----
    if (sim not in SIMS or not NAME_RE.match(test_name or "")
            or (bug_id is not None and not NAME_RE.match(bug_id))):
        run_dir = repo_path(out_root) / "invalid"
        v.fail("sim_error", "bad simulator, test or bug name: sim=%r test=%r bug=%r (simulators: %s)"
               % (sim, test_name, bug_id, "|".join(SIMS)))
        return finish()
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    result["run_dir"] = rel(run_dir)
    try:
        tests = load_tests(tests_toml)
        if test_name not in tests:
            raise DvError("unknown test %r (not in %s)" % (test_name, rel(repo_path(tests_toml))))
        t = dict(tests[test_name])
        defines = []
        if bug_id is not None:
            bugs = load_bugs(bugs_toml, tests)
            if bug_id not in bugs:
                raise DvError("unknown bug %r (not in %s)" % (bug_id, rel(repo_path(bugs_toml))))
            bug = bugs[bug_id]
            if bug["define"]:
                defines.append(bug["define"])
            # Firmware / boot ROM bug variants (fw/README.md): another image, or
            # another boot ROM in place of rtl/bootrom/bootrom.v, for this run only.
            if "fw" in bug:
                t["fw"] = bug["fw"]
                result["fw_variant"] = bug["fw"]
            if "bootrom" in bug:
                rom_v = repo_path(fw_dir) / ("bootrom__%s.v" % bug["bootrom"])
                if not rom_v.is_file():
                    raise DvError("boot ROM variant %s not found (build it with 'make fw')" % rel(rom_v))
                rtl_f = variant_rtl_f(rtl_f, rom_v)
                result["bootrom_variant"] = rel(rom_v)
        memmap = parse_memmap(MEMMAP)
        for k in ("SOC_SRAM_WORDS", "SOC_TEST_PASS_MAGIC"):
            if k not in memmap:
                raise DvError("%s does not define %s" % (MEMMAP, k))
        whitelist = load_whitelist(WHITELIST)
    except (OSError, tomllib.TOMLDecodeError, DvError) as e:
        v.fail("sim_error", "configuration error: %s" % e)
        return finish()
    result["defines"] = defines
    result["expected"] = {k: t[k] for k in ("load", "boot_mode", "sig_rule", "expect_uart", "expect_gpio", "uart_in",
                                            "min_cycles", "loader_frame", "expect_unmapped", "sram_cov",
                                            "min_uart_stalls", "reset_on_store") if k in t}
    ncycles = int(max_cycles) if max_cycles else t["max_cycles"]

    # ---- inputs: firmware image, UART RX stream ----
    plus = ["+out_dir=%s" % run_dir, "+boot_mode=%d" % t["boot_mode"], "+load=%s" % t["load"],
            "+max_cycles=%d" % ncycles]
    fwd = repo_path(fw_dir)
    uart_in = b""
    # ELF of the loaded image: symbol lookup for sram_cov and reset_on_store.
    elf = fwd / (t["fw"] + ".elf") if t["load"] in ("backdoor", "host", "uart") else None
    try:
        if t["load"] in ("backdoor", "host"):
            hexf = fwd / (t["fw"] + ".hex")
            if not hexf.is_file():
                raise DvError("firmware image %s not found (build it with 'make fw')" % rel(hexf))
            words = hex_word_count(hexf)
            if not 1 <= words <= memmap["SOC_SRAM_WORDS"]:
                raise DvError("%s has %d words; SRAM holds %d" % (rel(hexf), words, memmap["SOC_SRAM_WORDS"]))
            plus += ["+fw=%s" % hexf.resolve(), "+fw_words=%d" % words]
            result["fw_image"] = rel(hexf)
        elif t["load"] == "uart":
            if t["loader_frame"] in ("n_zero", "n_too_big"):
                # Header-only frames: no image is sent.
                uart_in += uart_loader_frame(b"", t["loader_frame"])
            else:
                binf = fwd / (t["fw"] + ".bin")
                if not binf.is_file():
                    raise DvError("firmware image %s not found (build it with 'make fw')" % rel(binf))
                uart_in += uart_loader_frame(binf.read_bytes(), t["loader_frame"])
                result["fw_image"] = rel(binf)
        uart_in += t["uart_in"].encode("utf-8")
        if "reset_on_store" in t:
            addr = resolve_addr(t["reset_on_store"], elf, "reset_on_store")
            plus.append("+reset_on_store=%08x" % addr)
            result["reset_on_store_addr"] = "0x%08x" % addr
    except (OSError, DvError) as e:
        v.fail("sim_error", str(e))
        return finish()
    if uart_in:
        uin = run_dir / "uart_in.hex"
        uin.write_text("".join("%02x\n" % b for b in uart_in))
        plus += ["+uart_in=%s" % uin, "+uart_in_len=%d" % len(uart_in),
                 "+uart_in_delay=%d" % UART_IN_DELAY]
    if "expect_unmapped" in t:
        # bus_assert counts unmapped data accesses instead of failing them; the
        # count is compared with expect_unmapped below.
        plus.append("+allow_unmapped")
    if trace:
        plus.append("+trace")
    if vcd:
        plus.append("+vcd")
    plus += ["+%s" % p.lstrip("+") for p in extra_plusargs]

    # ---- compile (cached) ----
    b = build_result
    if b is None:
        try:
            b = build(sim, defines, rtl_f=rtl_f, trace=vcd)
        except (OSError, DvError) as e:
            v.fail("sim_error", "compile setup failed: %s" % e)
            return finish()
    clog = run_dir / "compile.log"
    if b.log is not None and Path(b.log).exists():
        shutil.copyfile(b.log, clog)
        result["compile_log"] = rel(clog)
    result["build_dir"] = rel(b.build_dir)
    try:
        result["tools"] = ["%s %s (%s)" % (n, ver, path) for n, path, ver in tool_identity(sim)]
    except Exception as e:  # noqa: BLE001 - informational only
        result["tools"] = ["unavailable: %s" % e]
    if not b.ok:
        v.fail("sim_error", b.message or "compile failed")
        if clog.exists():
            for line in compile_log_lines(clog):
                if LOG_SCAN_RE.search(line):
                    result["messages"].append("compile: " + line.strip())
                    if len(result["messages"]) > 10:
                        break
        return finish()

    # ---- simulate ----
    if sim == "icarus":
        cmd = ["vvp", "-n", str(b.exe)] + plus
    else:
        cmd = [str(b.exe)] + plus
    simlog = run_dir / "sim.log"
    result["log"] = rel(simlog)
    limit = int(timeout) if timeout else default_timeout(ncycles)
    rc = None
    with open(simlog, "w") as lf:
        try:
            rc = subprocess.run(cmd, cwd=str(run_dir), stdout=lf, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, timeout=limit).returncode
        except subprocess.TimeoutExpired:
            rc = None
        except OSError as e:
            lf.write("cannot run simulator: %s\n" % e)
            rc = 127
    result["sim_exit_code"] = rc
    (run_dir / "sim_cmd.txt").write_text(" ".join(cmd) + "\n")
    if rc is None:
        v.fail("sim_error", "wall-clock timeout: simulation killed after %d s" % limit)
    elif rc != 0:
        v.fail("sim_error", "simulator exit code %d" % rc)

    # ---- testbench checkers ----
    log_lines = simlog.read_text(errors="replace").splitlines()
    for line in log_lines:
        m = CHK_LINE_RE.match(line.strip())
        if m:
            v.fail(m.group(1), m.group(2))

    tbr_path = run_dir / "tb_result.txt"
    tbr = _parse_tb_result(tbr_path) if tbr_path.exists() else {}
    finished = tbr.get("finished") == "1"
    if not finished:
        v.fail("sim_error", "%s missing or incomplete: simulation did not reach the end" % rel(tbr_path))
    end_reason = tbr.get("end_reason")
    done_count = _int_or_none(tbr.get("done_count"))
    done = _int_or_none(tbr.get("done")) if tbr.get("done") not in (None, "none") else None
    sig = _int_or_none(tbr.get("sig"))
    sig_at_done = _int_or_none(tbr.get("sig_at_done"))
    result["cycles"] = _int_or_none(tbr.get("cycles"))
    result["done"] = None if done is None else "0x%08x" % done
    result["sig"] = None if sig is None else "0x%08x" % sig
    result["sig_at_done"] = None if sig_at_done is None else "0x%08x" % sig_at_done
    result["done_count"] = done_count
    result["end_reason"] = end_reason
    pass_magic = memmap["SOC_TEST_PASS_MAGIC"]

    if finished:
        # A complete tb_result.txt carries every key the testbench writes; a
        # missing key is never read as 0 (Q-F8).
        missing = [k for k in TB_RESULT_KEYS if k not in tbr]
        if missing:
            v.fail("sim_error", "tb_result.txt is missing %s" % ", ".join(missing))
        if tbr.get("simulator") != sim:
            v.fail("sim_error", "tb_result.txt says simulator=%s, but this run is %s"
                   % (tbr.get("simulator"), sim))
        # Counters must agree with the printed messages (defensive cross-check).
        for name in TB_CHECKERS + ("sim_error",):
            key = "fail." + name
            if name == "x_check" and sim != "icarus":
                if key in tbr:
                    v.fail("sim_error", "tb_result.txt has %s on %s (x_check is Icarus only)" % (key, sim))
                continue
            if key not in tbr:
                if name == "x_check":
                    v.fail("sim_error", "tb_result.txt has no fail.x_check on icarus (x_check not compiled?)")
                else:
                    v.fail("sim_error", "tb_result.txt has no %s" % key)
                continue
            n = _int_or_none(tbr[key])
            if n is None:
                v.fail("sim_error", "tb_result.txt: %s is not a number" % key)
            elif n > 0 and not v.has(name):
                v.fail(name, "testbench counted %d failure(s) but printed no message" % n)
        for k in ("uart_wr", "uart_wr_stalled", "uart_wr_stall_cycles", "sram_port_accesses", "mid_resets"):
            result[k] = _int_or_none(tbr.get(k))
        if "reset_on_store" in t and end_reason != "abort" and result["mid_resets"] != 1:
            v.fail("coverage", "the testbench applied %s mid-run reset(s), expected 1: the CPU never presented "
                   "a store to %s (tests.toml reset_on_store)" % (tbr.get("mid_resets"), result.get("reset_on_store_addr")))
        unmapped = _int_or_none(tbr.get("unmapped"))
        result["unmapped"] = unmapped
        if "expect_unmapped" in t and unmapped != t["expect_unmapped"]:
            v.fail("bus_assert", "%s unmapped data access(es), expected exactly %d (tests.toml expect_unmapped)"
                   % (tbr.get("unmapped"), t["expect_unmapped"]))
        if done is None:
            if end_reason == "timeout" and not v.has("timeout"):
                v.fail("timeout", "no DONE write before max_cycles")
            elif end_reason == "trap" and not v.has("trap"):
                v.fail("trap", "trap ended the run before DONE")
            elif end_reason not in ("timeout", "trap", "abort"):
                v.fail("sim_error", "simulation ended without DONE (end_reason=%s)" % end_reason)
        else:
            if done != pass_magic and not v.has("test_ctrl"):
                v.fail("test_ctrl", "DONE=0x%08x is not the PASS magic 0x%08x" % (done, pass_magic))
            if done_count != 1 and not v.has("test_ctrl"):
                v.fail("test_ctrl", "DONE written %s times" % done_count)
            done_cycle = _int_or_none(tbr.get("done_cycle"))
            result["done_cycle"] = done_cycle
            if done == pass_magic and "min_cycles" in t and (done_cycle is None or done_cycle < t["min_cycles"]):
                # Lower bound on the test length (Q-F1): a firmware whose test
                # body was skipped or shrunk still prints the same PASS text.
                v.fail("test_ctrl", "DONE written at cycle %s, before min_cycles=%d: the test ran shorter "
                       "than its measured length (test body skipped or shrunk?)" % (done_cycle, t["min_cycles"]))

    # ---- run_sim.py checkers: uart_golden, signature, gpio_seq ----
    uart_path = run_dir / "uart.txt"
    uart = uart_path.read_bytes() if uart_path.exists() else b""
    result["uart_text"] = uart.decode("latin-1")
    # An aborted run (testbench setup error, already reported as sim_error) never
    # ran the firmware, so its outputs are not compared.
    if finished and end_reason != "abort":
        if not uart_path.exists():
            v.fail("sim_error", "uart.txt missing")
        elif _int_or_none(tbr.get("uart_bytes")) != len(uart):
            v.fail("sim_error", "uart.txt has %d bytes but the testbench decoded %s"
                   % (len(uart), tbr.get("uart_bytes")))
        if "expect_uart" in t:
            exp = t["expect_uart"].encode("utf-8")
            if uart != exp:
                v.fail("uart_golden", "UART text %r (%d bytes), expected %r (%d bytes)"
                       % (uart.decode("latin-1"), len(uart), t["expect_uart"], len(exp)))
        kind, const = parse_sig_rule(t["sig_rule"])
        if kind != "none":
            want = crc32(uart) if kind == "uart_crc32" else const
            what = "CRC32 of the decoded UART bytes" if kind == "uart_crc32" else t["sig_rule"]
            if done is not None:
                # Spec 6.3: test_pass() writes SIG, then DONE. The value that
                # counts is SIG in the cycle of the DONE strobe (review m4).
                if sig_at_done is None:
                    v.fail("signature", "SIG at the DONE write missing from tb_result.txt")
                elif sig_at_done != want:
                    v.fail("signature", "SIG=0x%08x at the DONE write (cycle %s), expected 0x%08x (%s); "
                           "spec 6.3: SIG is written before DONE (SIG at the end of the run: %s)"
                           % (sig_at_done, tbr.get("done_cycle"), want, what, result["sig"]))
            elif sig is None:
                v.fail("signature", "SIG value missing from tb_result.txt")
            elif sig != want:
                v.fail("signature", "SIG=0x%08x, expected 0x%08x (%s)" % (sig, want, what))
        gpio_path = run_dir / "gpio.txt"
        gpio = []
        gpio_bad = []
        if gpio_path.exists():
            for line in gpio_path.read_text(errors="replace").split():
                g = _int_or_none("0x" + line)
                if g is None:
                    gpio_bad.append(line)
                gpio.append(g if g is not None else line)
        else:
            v.fail("sim_error", "gpio.txt missing")
        result["gpio"] = ["0x%02x" % g if isinstance(g, int) else g for g in gpio]
        if "expect_gpio" in t:
            exp = t["expect_gpio"]
            if gpio_bad or gpio != exp:
                v.fail("gpio_seq", "gpio_out sequence [%s], expected [%s]"
                       % (", ".join(result["gpio"]), ", ".join("0x%02x" % g for g in exp)))

        # ---- coverage: the test exercised what tests.toml says it must ----
        if "min_uart_stalls" in t:
            n = result.get("uart_wr_stalled")
            if n is None or n < t["min_uart_stalls"]:
                v.fail("coverage", "%s of %s UART DATA writes were held by the transmitter-busy stall, expected at "
                       "least %d (tests.toml min_uart_stalls; spec 4.2: no mem_ready while reg_dat_wait=1)"
                       % (n, result.get("uart_wr"), t["min_uart_stalls"]))
        if "sram_cov" in t:
            try:
                rows = read_sram_cov(run_dir / "sram_cov.txt", memmap["SOC_SRAM_WORDS"])
                for msg in check_sram_cov(t["sram_cov"], rows, elf):
                    v.fail("coverage", msg)
            except (OSError, DvError) as e:
                v.fail("sim_error", "sram_cov: %s" % e)

    # ---- log_scan ----
    hits = []
    sources = [("compile", compile_log_lines(clog) if clog.exists() else []), ("sim", log_lines)]
    for src, lines in sources:
        for line in lines:
            s = line.strip()
            if CHK_LINE_RE.match(s):
                continue
            if LOG_SCAN_RE.search(s) and not any(w.search(s) for w in whitelist):
                hits.append("%s log: %s" % (src, s))
    for h in hits[:20]:
        v.fail("log_scan", h)
    if len(hits) > 20:
        v.fail("log_scan", "%d more log lines suppressed" % (len(hits) - 20))

    # ---- explicit PASS evidence (spec 7.4) ----
    if not result["failing_checkers"]:
        evidence = (rc == 0 and finished and end_reason == "done" and done == pass_magic
                    and done_count == 1)
        if not evidence:
            v.fail("sim_error", "no explicit PASS evidence (exit=%s finished=%s end_reason=%s done=%s done_count=%s)"
                   % (rc, finished, end_reason, result["done"], done_count))
    return finish()


def print_summary(result):
    tag = result["test"] + ("__" + result["bug"] if result.get("bug") else "")
    extra = "cycles=%s" % result.get("cycles")
    if result["status"] == "PASS":
        print("run_sim: PASS %s %s (%s) -> %s" % (tag, result["sim"], extra, result.get("result_json")))
    else:
        print("run_sim: FAIL %s %s (%s) failing checkers: %s -> %s"
              % (tag, result["sim"], extra, ", ".join(result["failing_checkers"]), result.get("result_json")))
        for m in result["messages"][:8]:
            print("    " + m)
        if len(result["messages"]) > 8:
            print("    ... %d more messages in result.json" % (len(result["messages"]) - 8))


def safe_run_test(test_name, sim, **kw):
    """run_test for the parallel drivers: an unexpected internal error becomes a
    FAIL result (sim_error) instead of aborting the whole regression."""
    try:
        return run_test(test_name, sim, **kw)
    except Exception as e:  # noqa: BLE001 - reported, never swallowed as PASS
        r = _new_result(test_name, sim, kw.get("bug_id"))
        _Verdict(r).fail("sim_error", "internal error in dvlib.run_test: %s: %s" % (type(e).__name__, e))
        r["wall_time_s"] = 0
        r["result_json"] = None
        if not kw.get("quiet"):
            print_summary(r)
        return r


class Parser:
    """argparse wrapper whose usage errors exit with code 1 (spec 7.4: non-PASS -> 1)."""

    @staticmethod
    def make(**kw):
        import argparse

        class _P(argparse.ArgumentParser):
            def error(self, message):
                self.print_usage(sys.stderr)
                print("%s: error: %s" % (self.prog, message), file=sys.stderr)
                sys.exit(1)

        return _P(**kw)
