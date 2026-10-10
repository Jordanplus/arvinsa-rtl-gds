"""ngspice building blocks for the SPICE characterization of the OpenRAM sky130 SRAM (ADR-0010).

Used by char/characterize.py and char/neg_char.py; skill openram-macro-characterization.

Model of the macro that the stimulus relies on (measured in the Phase 3.5 probe runs):
  - port 0 inputs (csb0 web0 addr0 din0 wmask0) are sampled at the clk0 rising edge;
  - a read puts the data on dout0 after the falling edge; dout0 is pulled to 0 about 1 ns after
    every rising edge with csb0=0, so read data is checked just before the next rising edge
    (where the SoC's rdata register captures it);
  - port 1 is idle as in the SoC (csb1=1, addr1=0) and clk1 is clk0 (ADR-0018 decision 9): port 1's
    control logic latches csb1 into a DFF on the clk1 rising edge and wl_en1 = (NOT clk1) AND cs, with no
    reset. With clk1 held at 0 the DFF never latches, cs keeps its power-up (here: DC operating point)
    value, and with cs=1 a port-1 wordline stays on and port-0 writes to that row can fail.
Rows: addr0[8:2]; data bit b of word addr0[1:0] = w sits in column 4b + w (column_mux_array:
XXMUX<4b+w> connects bl_<4b+w> to bl_out_<b> with sel_<w>). The trimmed netlists keep rows 0 and 127
(so only the addresses in USABLE hold data; every read must use them) and the columns of data bits
0 and 31 (MEAS_BITS), whose bitlines therefore carry all 128 cells as in the real array. Timing is
measured on those two bits only; the other 30 bits have 2-cell bitlines and are only checked for
the right value.
"""
import os
import re
import shutil
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PDK_ROOT = os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel"))
NGSPICE_DIR = os.path.join(PDK_ROOT, "sky130A", "libs.tech", "ngspice")
# SRAM_CHAR_MACRO selects another macro of the same organisation (Phase 6: the OpenRAM self-generated one,
# ip/sram/openram/read_check.py); the default is the PDK macro characterized in Phase 3.5.
MACRO = os.environ.get("SRAM_CHAR_MACRO", "sky130_sram_2kbyte_1rw1r_32x512_8")
PDK_NETLIST = os.path.join(PDK_ROOT, "sky130A", "libs.ref", "sky130_sram_macros", "spice", MACRO + ".spice")
# SRAM_CHAR_NETLIST: the schematic netlist of a self-generated macro (Phase 6: ip/sram/<macro>/openram/<macro>.sp);
# the default is the PDK netlist.
NETLIST = os.environ.get("SRAM_CHAR_NETLIST", PDK_NETLIST)
# OpenRAM with the 2022 PDK writes the latch PMOS under its old name; the flow PDK renamed it and its legacy
# alias subckt fails in ngspice with "unknown subckt" (ADR-0018 decision 5). The PDK netlist has none.
PFET_OLD, PFET_NEW = "sky130_fd_pr__special_pfet_pass", "sky130_fd_pr__special_pfet_latch"
# SRAM_CHAR_WORDS_PER_ROW: 4 for the PDK macro; 1 for the Phase 6 variant without a column mux (512 rows x 32).
WORD_BITS, ADDR_BITS, WMASK_BITS, WORDS = 32, 9, 4, 512
WORDS_PER_ROW = int(os.environ.get("SRAM_CHAR_WORDS_PER_ROW", "4"))
ROWS, COLS = WORDS // WORDS_PER_ROW, WORD_BITS * WORDS_PER_ROW
MEAS_BITS = (0, WORD_BITS - 1)
SEQ_ADDRS = (0, 3, 508, 511)      # the addresses characterize.py's sequences use: their rows are kept
KEEP_ROWS = tuple(sorted({a // WORDS_PER_ROW for a in SEQ_ADDRS}))
KEEP_COLS = tuple(WORDS_PER_ROW * b + w for b in MEAS_BITS for w in range(WORDS_PER_ROW))
USABLE = tuple(r * WORDS_PER_ROW + w for r in KEEP_ROWS for w in range(WORDS_PER_ROW))
ONES = (1 << WORD_BITS) - 1
GROUPS = ("csb", "web", "addr", "din", "wmask")
BITCELL = "sky130_fd_bd_sram__openram_dp_cell"

# PVT name (LibreLane corner suffix) -> (ngspice model section, supply V, temperature C)
PVTS = {
    "tt_025C_1v80": ("tt", 1.80, 25.0),
    "ss_100C_1v60": ("ss", 1.60, 100.0),
    "ff_n40C_1v95": ("ff", 1.95, -40.0),
    "ss_n40C_1v60": ("ss", 1.60, -40.0),
    "ff_100C_1v95": ("ff", 1.95, 100.0),
}


# ---------------------------------------------------------------- netlist trimming

def bit_cols(bits):
    """Columns of data bits `bits` (column 4b + w for word w, see the module docstring)."""
    return tuple(WORDS_PER_ROW * b + w for b in bits for w in range(WORDS_PER_ROW))


def _kept(r, c, cols=KEEP_COLS):
    return r in KEEP_ROWS or c in cols


def trim_schematic(src, dst, bits=MEAS_BITS):
    """OpenRAM schematic netlist: comment out bitcells Xbit_r<r>_c<c> of the bitcell array subckt outside the
    kept rows/columns. The subckt is `bitcell_array` in the PDK macro and `<MACRO>_bitcell_array` in a macro
    generated with uniquify (Phase 6), whose instances also continue on `+` lines (all of them are commented
    out with the instance). PFET_OLD is renamed to PFET_NEW everywhere. bits: the data bits whose columns keep
    all their bitcells (default MEAS_BITS; power.py passes every bit: the untrimmed netlist, only renamed).
    Returns (kept, dropped)."""
    cols = bit_cols(bits)
    head = re.compile(rf"\.SUBCKT (bitcell_array|{MACRO}_bitcell_array)\s")
    out, inside, kept, dropped, drop_cont = [], False, 0, 0, False
    for line in open(src, encoding="utf-8"):
        line = line.replace(PFET_OLD, PFET_NEW)
        if line.startswith("+") and drop_cont:
            out.append("*TRIM " + line)
            continue
        drop_cont = False
        if head.match(line):
            inside = True
        elif inside and line.startswith(".ENDS"):
            inside = False
        m = re.match(r"Xbit_r(\d+)_c(\d+)\s", line) if inside else None
        if m:
            if _kept(int(m.group(1)), int(m.group(2)), cols):
                kept += 1
            else:
                dropped += 1
                line = "*TRIM " + line
                drop_cont = True
        out.append(line)
    _check_trim(src, kept, dropped, cols)
    open(dst, "w", encoding="utf-8").writelines(out)
    return kept, dropped


def trim_extracted(src, dst):
    """Magic-extracted netlist: drop the bitcell instances of <MACRO>_bitcell_array outside the kept
    rows/columns. Row and column come from the instance's wl_0_<r> and bl_0_<c> nets; the wire
    capacitances of the array stay. Returns (kept, dropped).

    Magic exports the storage nodes of every bitcell up to the top cell, where they are plain nets
    (<bank>/.../<cell>/a_16_183#) with capacitors to the substrate net <...>/VSUBS, and that substrate
    net connects to no device. In the top cell both are renamed to vssd1: a dropped cell's storage
    nodes would otherwise float (singular matrix), and so would the substrate, which on silicon is
    tied to ground through the substrate taps. Their capacitances become loads to ground."""
    lines = open(src, encoding="utf-8").read().split("\n")
    stmts, cur = [], None          # join continuation lines, remember the original line span
    for i, line in enumerate(lines):
        if line.startswith("+") and cur is not None:
            cur[1] = i
            cur[2] += " " + line[1:]
            continue
        cur = [i, i, line]
        stmts.append(cur)
    drop, inside, kept, dropped = set(), False, 0, 0
    head = f".subckt {MACRO}_bitcell_array "
    for first, last, text in stmts:
        low = text.lower()
        if low.startswith(head):
            inside = True
        elif inside and low.startswith(".ends"):
            inside = False
        elif inside and text.startswith("X") and text.split()[-1] == BITCELL:
            wl = re.search(r"\bwl_0_(\d+)\b", text)
            bl = re.search(r"\bbl_0_(\d+)\b", text)
            if not (wl and bl):
                raise SystemExit(f"trim_extracted: FAIL - bitcell without wl_0_/bl_0_ nets: {text[:120]}")
            if _kept(int(wl.group(1)), int(bl.group(1))):
                kept += 1
            else:
                dropped += 1
                drop.update(range(first, last + 1))
    _check_trim(src, kept, dropped)
    gone = set()
    for first, last, text in stmts:
        if first in drop:
            gone.add(text.split()[0][1:])                      # instance name without the X
    top = f".subckt {MACRO} "
    tie = re.compile(r"\S*/(?:(" + BITCELL + r"_\d+)/\S+|VSUBS)(?=\s|$)")
    inside, renamed = False, 0
    for first, last, text in stmts:
        low = text.lower()
        if low.startswith(top):
            inside = True
            continue
        if inside and low.startswith(".ends"):
            break
        if not inside:
            continue
        for i in range(first, last + 1):
            def sub(m):
                nonlocal renamed
                if m.group(1) is None or m.group(1) in gone:
                    renamed += 1
                    return "vssd1"
                return m.group(0)
            lines[i] = tie.sub(sub, lines[i])
    if renamed == 0:
        raise SystemExit("trim_extracted: FAIL - no substrate or dropped-cell net renamed in the top cell")
    with open(dst, "w", encoding="utf-8") as f:
        for i, line in enumerate(lines):
            f.write(("*TRIM " + line if i in drop else line) + ("\n" if i < len(lines) - 1 else ""))
    return kept, dropped


def _check_trim(src, kept, dropped, cols=KEEP_COLS):
    want_kept = len(KEEP_ROWS) * COLS + len(cols) * ROWS - len(KEEP_ROWS) * len(cols)
    if kept != want_kept or kept + dropped != ROWS * COLS:
        raise SystemExit(f"trim: FAIL - {src}: kept {kept}, dropped {dropped}; expected kept {want_kept} "
                         f"of {ROWS * COLS} bitcells")


def subckt_ports(netlist):
    """Port list of the macro's .subckt line (continuation lines joined, any case)."""
    text = open(netlist, encoding="utf-8").read()
    m = re.search(rf"^\.subckt\s+{MACRO}\s+(.*?)\n(?!\+)", text, re.I | re.M | re.S)
    if not m:
        raise SystemExit(f"sramchar: FAIL - no .subckt {MACRO} in {netlist}")
    return [t for t in m.group(1).replace("\n+", " ").split() if t != "+"]  # a port list may start on a + line


BITCELL = "sky130_fd_bd_sram__openram_dp_cell"


def bitcell_paths(netlist, want=ROWS * COLS):
    """ngspice instance paths (lower case, from the deck's Xsram) of every BITCELL below the macro subckt
    (commented-out ones of a trimmed netlist do not count); FAILs unless there are `want` of them (ROWS x COLS
    for the untrimmed netlist; trim_schematic's kept count for a trimmed one)."""
    subs, cur = {}, None
    for line in re.sub(r"\n\+", " ", open(netlist, encoding="utf-8").read()).splitlines():
        tok = line.split()
        if not tok:
            continue
        head = tok[0].lower()
        if head == ".subckt":
            cur = subs.setdefault(tok[1], [])
        elif head == ".ends":
            cur = None
        elif cur is not None and head.startswith("x"):
            cur.append((head, [t for t in tok[1:] if "=" not in t][-1]))

    def walk(sub, path):
        for inst, model in subs.get(sub, ()):
            if model == BITCELL:
                yield f"{path}.{inst}"
            elif model in subs:
                yield from walk(model, f"{path}.{inst}")
    paths = list(walk(MACRO, "xsram"))
    if len(paths) != want:
        raise SystemExit(f"sramchar: FAIL - {netlist}: {len(paths)} {BITCELL} instances below {MACRO}, "
                         f"expected {want}")
    return paths


def bitcell_ic(netlist, vdd, want=ROWS * COLS):
    """.ic lines that hold every bitcell at Q = 0, Q_bar = vdd during the operating point. Without them the
    operating point leaves each latch the sequence never writes balanced (Q = Q_bar near vdd / 2, both inverters
    conducting); at ss -40C such latches took 75 ns to fall to one side and the step landed in the leakage
    window (power.py, ADR-0018 decision 13). A real latch resolves at power-up."""
    return "\n".join(f".ic v({p}.q)=0 v({p}.q_bar)={vdd}" for p in bitcell_paths(netlist, want))


def subckt_text(netlist, name):
    """The .subckt ... .ends block of `name` in netlist (any case)."""
    m = re.search(rf"^\.subckt\s+{name}\s.*?^\.ends\b.*?$", open(netlist, encoding="utf-8").read(), re.I | re.M | re.S)
    if not m:
        raise SystemExit(f"sramchar: FAIL - no .subckt {name} in {netlist}")
    return m.group(0)


# ---------------------------------------------------------------- stimulus

class Seq:
    """Cycle-by-cycle port 0 stimulus, its expected read data, and the ngspice deck for it.

    Times are ns. Cycle k has its rising edge at rise[k] (50 % of the clock ramp), its falling
    edge after high[k], the next rising edge after low[k]. The value of each input group for
    cycle k is applied in the middle of the longer phase of cycle k-1 (all port 0 inputs go
    through registers clocked by the rising edge, so any time well away from both edges works;
    taking the longer phase keeps a short phase in the pulse width searches from also testing
    setup or hold) unless moved with move(); a setup search moves cycle k's value to rise[k] - s,
    a hold search moves cycle k+1's value to rise[k] + h.
    """

    def __init__(self, pvt, period=40.0, clk_slew=0.2, in_slew=0.2, load_ff=10.0):
        self.pvt, self.corner, self.vdd, self.temp = pvt, *PVTS[pvt]
        self.period, self.clk_slew, self.in_slew, self.load_ff = period, clk_slew, in_slew, load_ff
        self.cycles, self.moves, self.checks = [], {}, []

    def cycle(self, csb, web, addr, din=0, wmask=(1 << WMASK_BITS) - 1, high=None, low=None):
        self.cycles.append(dict(csb=csb, web=web, addr=addr, din=din, wmask=wmask,
                                high=self.period / 2 if high is None else high,
                                low=self.period / 2 if low is None else low))
        return len(self.cycles) - 1

    def write(self, addr, din, wmask=(1 << WMASK_BITS) - 1, **kw):
        return self.cycle(0, 0, addr, din, wmask, **kw)

    def read(self, addr, expect, label="", **kw):
        if addr not in USABLE:
            raise ValueError(f"read of address {addr}, which the trimmed netlist does not hold")
        prev = self.cycles[-1] if self.cycles else None
        k = self.cycle(0, 1, addr, prev["din"] if prev else 0, prev["wmask"] if prev else 0xF, **kw)
        self.checks.append((k, expect, label))
        return k

    def nop(self, web=1, addr=0, din=0, wmask=(1 << WMASK_BITS) - 1, **kw):
        return self.cycle(1, web, addr, din, wmask, **kw)

    def move(self, k, group, t):
        assert group in GROUPS
        self.moves[(k, group)] = t

    def rise_of(self, k):
        return self.edges()[0][k]

    # timing
    def edges(self):
        ramp = self.clk_slew / 0.8
        t, rise, fall = 2.0 + ramp, [], []
        for c in self.cycles:
            rise.append(t)
            fall.append(t + c["high"])
            t += c["high"] + c["low"]
        rise.append(t)    # the rising edge after the last cycle
        return rise, fall

    def _value(self, c, group, bit):
        v = c[group]
        return (v >> bit) & 1 if group in ("addr", "din", "wmask") else v

    def _pwl(self, group, bit, rise, fall):
        ramp = self.in_slew / 0.8
        vals = [self._value(c, group, bit) for c in self.cycles]
        pts = [(0.0, vals[0])]
        for k in range(1, len(vals)):
            if vals[k] == vals[k - 1]:
                continue
            c = self.cycles[k - 1]
            mid = rise[k - 1] + c["high"] / 2 if c["high"] >= c["low"] else fall[k - 1] + c["low"] / 2
            t = self.moves.get((k, group), mid)
            if t - ramp / 2 <= pts[-1][0]:
                raise ValueError(f"{group}[{bit}] transitions overlap at cycle {k} (t={t:.3f})")
            pts += [(t - ramp / 2, vals[k - 1]), (t + ramp / 2, vals[k])]
        return "PWL(" + " ".join(f"{t:.4f}n {v * self.vdd:.4f}" for t, v in pts) + ")"

    def deck(self, netlist, tstep="100p", tmax=None, extra="", uic=False, probes=(), clk_stop=None,
             clk_park=None, csb1=1, save_only=False):
        """uic: skip the DC operating point (all nodes start at 0 V, the first writes set the state).
        The Magic-extracted netlist needs it: its bitcell latches leave the operating point singular.
        probes: more vectors for wave.txt, e.g. "i(vvdd)" (power.py). clk_stop: {"clk0"|"clk1": t} - that
        clock has no edge after t ns and stays low (t must fall in a low phase). clk_park: {"clk0"|"clk1": k}
        - that clock rises at cycle k and stays high (power.py's leakage deck). csb1: 0 selects port 1
        (it then reads addr1 = 0 at every clk1 edge). save_only: keep only the written vectors (`save`); without
        it ngspice keeps every node of every time point, which for the untrimmed netlist grew to about 5 GB per
        run and made 5 parallel runs swap (power.py). Without probes, clk_stop, clk_park, csb1 and save_only the
        deck is the same as before they existed (cached simulations stay valid)."""
        rise, fall = self.edges()
        ramp = self.clk_slew / 0.8
        clk = [(0.0, 0)]
        for r, f in zip(rise, fall):
            clk += [(r - ramp / 2, 0), (r + ramp / 2, 1), (f - ramp / 2, 1), (f + ramp / 2, 0)]
        clks = {}
        for name in ("clk0", "clk1"):
            stop, park = (clk_stop or {}).get(name), (clk_park or {}).get(name)
            if stop is not None and park is not None:
                raise ValueError(f"{name}: clk_stop and clk_park both given")
            if park is not None and not 0 <= park < len(fall):
                raise ValueError(f"{name} park at cycle {park}: the sequence has {len(fall)} cycles")
            pts = clk if stop is None else [p for p in clk if p[0] <= stop]
            nxt = clk[len(pts)][1] if len(pts) < len(clk) else 0
            if stop is not None and (pts[-1][1] != 0 or nxt != 0):    # both neighbours low: inside a low phase
                raise ValueError(f"{name} stop at {stop} ns is not in a low phase")
            if park is not None:
                pts = clk[:3 + 4 * park]                              # up to the end of cycle park's rising ramp
            clks[name] = "PWL(" + " ".join(f"{t:.4f}n {v * self.vdd:.4f}" for t, v in pts) + ")"
        tend = rise[-1] + 0.5
        L = [f"* {MACRO} {self.pvt} characterization deck (ip/sram/char/sramchar.py)",
             f'.lib "{os.path.join(NGSPICE_DIR, "sky130.lib.spice")}" {self.corner}',
             f'.include "{netlist}"',
             f".temp {self.temp}",
             f"Vvdd vccd1 0 {self.vdd}", "Vvss vssd1 0 0",
             "Vclk0 clk0 0 " + clks["clk0"],
             "Vclk1 clk1 0 " + clks["clk1"],
             f"Vcsb1 csb1 0 {self.vdd if csb1 else 0}"]
        L += [f"Va1_{i} addr1[{i}] 0 0" for i in range(ADDR_BITS)]
        L.append(f"Vcsb0 csb0 0 {self._pwl('csb', 0, rise, fall)}")
        L.append(f"Vweb0 web0 0 {self._pwl('web', 0, rise, fall)}")
        L += [f"Va0_{i} addr0[{i}] 0 {self._pwl('addr', i, rise, fall)}" for i in range(ADDR_BITS)]
        L += [f"Vd{i} din0[{i}] 0 {self._pwl('din', i, rise, fall)}" for i in range(WORD_BITS)]
        L += [f"Vwm{i} wmask0[{i}] 0 {self._pwl('wmask', i, rise, fall)}" for i in range(WMASK_BITS)]
        L.append("Xsram " + " ".join(subckt_ports(netlist)) + f" {MACRO}")
        L += [f"Cl{i} dout0[{i}] 0 {self.load_ff}f" for i in range(WORD_BITS)]
        L += [f"Edo{i} do{i} 0 dout0[{i}] 0 1" for i in range(WORD_BITS)]   # bus names break wrdata
        L.append(extra)
        L.append(".options method=gear reltol=1e-3")
        L.append(f".tran {tstep} {tend:.4f}n" + (f" 0 {tmax or tstep} uic" if uic else f" 0 {tmax}" if tmax else ""))
        vecs = ["v(clk0)"] + [f"v(do{i})" for i in range(WORD_BITS)] + list(probes)
        save = ("save " + " ".join(re.sub(r"^i\((.+)\)$", r"\1#branch", v) for v in vecs) + "\n") if save_only else ""
        L.append(".control\nset wr_singlescale\nset wr_vecnames\noption numdgt=9\n" + save + "run")
        L.append("wrdata wave.txt " + " ".join(vecs))
        L.append(".endc\n.end")
        return "\n".join(L) + "\n"


# ---------------------------------------------------------------- running ngspice

def spiceinit(workdir):
    """The PDK's ngspice init (ngbehavior=hsa, KLU), single-threaded because jobs run in parallel."""
    text = open(os.path.join(NGSPICE_DIR, "spinit"), encoding="utf-8").read()
    text = re.sub(r"set num_threads=\d+", "set num_threads=1", text)
    open(os.path.join(workdir, ".spiceinit"), "w", encoding="utf-8").write(text)


def run(deck_text, workdir, timeout=7200):
    """Run one deck in workdir. Returns the waveform as {column: [floats]} or raises RuntimeError."""
    os.makedirs(workdir, exist_ok=True)
    spiceinit(workdir)
    wave = os.path.join(workdir, "wave.txt")
    if os.path.exists(wave):
        os.remove(wave)
    open(os.path.join(workdir, "deck.sp"), "w", encoding="utf-8").write(deck_text)
    with open(os.path.join(workdir, "ngspice.log"), "w") as log:
        try:
            rc = subprocess.run(["ngspice", "-b", "deck.sp"], cwd=workdir, stdout=log, stderr=subprocess.STDOUT,
                                timeout=timeout).returncode
        except subprocess.TimeoutExpired:      # the callers report RuntimeError as a FAIL line
            raise RuntimeError(f"ngspice timed out after {timeout} s: {workdir}") from None
    errs = log_errors(workdir)
    if rc != 0 or errs or not os.path.isfile(wave):
        raise RuntimeError(f"ngspice rc={rc}, {len(errs)} error line(s) {errs[:2]}, wave "
                           f"{'present' if os.path.isfile(wave) else 'missing'}: {workdir}")
    w = read_wave(wave)
    end = tran_end(deck_text)
    if not w["time"] or w["time"][-1] < end - 1e-3:
        raise RuntimeError(f"ngspice wave ends at {w['time'][-1] if w['time'] else 0:.3f} ns, before the .tran end {end:.3f} ns: {workdir}")
    return w


def log_errors(workdir):
    """Error lines of <workdir>/ngspice.log (all lines if the log is missing)."""
    p = os.path.join(workdir, "ngspice.log")
    if not os.path.isfile(p):
        return ["ngspice.log missing"]
    text = open(p, errors="replace").read()
    return [l for l in text.replace("\r", "\n").split("\n")
            if re.search(r"\berror\b|simulation interrupted|timestep too small|singular", l, re.I)]


def tran_end(deck_text):
    """Stop time (ns) of the deck's .tran line."""
    m = re.search(r"^\.tran\s+\S+\s+([\d.]+)n", deck_text, re.M)
    if not m:
        raise RuntimeError("deck has no .tran <step> <stop>n line")
    return float(m.group(1))


def cached_wave(workdir, deck_text):
    """The waveform of an earlier run of this exact deck in workdir, or None. Reused only when that
    run left a clean ngspice.log and a waveform reaching the .tran stop time: a run that failed
    part way can leave a partial wave.txt next to the same deck.sp (Phase 3.5 review)."""
    wave, deck = os.path.join(workdir, "wave.txt"), os.path.join(workdir, "deck.sp")
    if not (os.path.isfile(wave) and os.path.isfile(deck) and open(deck).read() == deck_text) or log_errors(workdir):
        return None
    w = read_wave(wave)
    return w if w["time"] and w["time"][-1] >= tran_end(deck_text) - 1e-3 else None


def read_wave(path):
    with open(path) as f:
        head = f.readline().split()
        cols = [[] for _ in head]
        for line in f:
            parts = line.split()
            if len(parts) != len(head):
                continue
            for i, p in enumerate(parts):
                cols[i].append(float(p))
    names = ["time"] + [re.sub(r"^v\((.*)\)$", r"\1", h) for h in head[1:]]
    w = dict(zip(names, cols))
    w["time"] = [t * 1e9 for t in w["time"]]   # ns
    return w


# ---------------------------------------------------------------- waveform measurements

def value_at(w, sig, t):
    ts, vs = w["time"], w[sig]
    lo, hi = 0, len(ts) - 1
    if t <= ts[0]:
        return vs[0]
    if t >= ts[-1]:
        return vs[-1]
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ts[mid] <= t:
            lo = mid
        else:
            hi = mid
    f = (t - ts[lo]) / (ts[hi] - ts[lo]) if ts[hi] > ts[lo] else 0.0
    return vs[lo] + f * (vs[hi] - vs[lo])


def crossing(w, sig, level, t0, t1, rising):
    """First time in (t0, t1] where sig crosses level in the given direction, or None."""
    ts, vs = w["time"], w[sig]
    for i in range(1, len(ts)):
        if ts[i] <= t0:
            continue
        if ts[i - 1] > t1:
            break
        a, b = vs[i - 1], vs[i]
        if (rising and a < level <= b) or (not rising and a > level >= b):
            t = ts[i - 1] + (level - a) / (b - a) * (ts[i] - ts[i - 1])
            if t0 < t <= t1:
                return t
    return None


def check_reads(seq, w, sample_before=0.05):
    """[(cycle, label, problem)] for every read whose dout0 differs from the expected word just
    before the next rising edge (1 must be >= 0.8 VDD, 0 <= 0.2 VDD)."""
    rise, _ = seq.edges()
    covers(seq, w, sample_before)
    bad = []
    for k, expect, label in seq.checks:
        t = rise[k + 1] - sample_before
        wrong = []
        for b in range(WORD_BITS):
            v = value_at(w, f"do{b}", t)
            if not ((v >= 0.8 * seq.vdd) if (expect >> b) & 1 else (v <= 0.2 * seq.vdd)):
                wrong.append(f"{b}:{v:.2f}V")
        if wrong:
            bad.append((k, label, f"expected 0x{expect:08x}, wrong bits {' '.join(wrong[:6])}"
                                  f"{' ...' if len(wrong) > 6 else ''}"))
    return bad


def covers(seq, w, sample_before=0.05):
    """Raise unless the waveform reaches the last read check: value_at() past the end of a short
    waveform returns its last sample, so a truncated wave.txt would pass every later check."""
    rise, _ = seq.edges()
    need = max((rise[k + 1] - sample_before for k, _, _ in seq.checks), default=0.0)
    if not w["time"] or w["time"][-1] < need:
        raise RuntimeError(f"waveform ends at {w['time'][-1] if w['time'] else 0:.3f} ns, before the read check at {need:.3f} ns")


VALID_HI, VALID_LO, DEPART = 0.8, 0.2, 0.1   # fractions of VDD


def last_entry(w, sig, t0, t1, level, above):
    """Time in [t0, t1] at which sig last entered the band (>= level if above, else <= level),
    interpolated between samples; None if it is in the band over the whole interval."""
    ts, vs = w["time"], w[sig]
    inside = (lambda x: x >= level) if above else (lambda x: x <= level)
    last = None
    for i in range(1, len(ts)):
        if ts[i] < t0:
            continue
        if ts[i - 1] > t1:
            break
        if not inside(vs[i - 1]) and inside(vs[i]):
            last = ts[i - 1] + (level - vs[i - 1]) / (vs[i] - vs[i - 1]) * (ts[i] - ts[i - 1])
    return last


def read_timing(seq, w, sample_before=0.05):
    """Timing of dout0 bits MEAS_BITS for each read cycle k (ns):
      settle  falling edge -> the bit last enters its valid band (>= 0.8 VDD for 1, <= 0.2 VDD for 0)
              before the check point; negative when it was already valid before the falling edge
      d50     falling edge -> 50 % crossing, for bits that rise to 1 after the falling edge
      tran    10-90 % transition of those rises
      depart  rising edge of cycle k -> the bit first moves 0.1 VDD away from the value the read in
              cycle k-1 left on it (only when cycle k-1 was a read); this is how long the data
              of the previous read stays usable after the edge, i.e. the hold side
    The settle and depart thresholds are stricter than the 50 % of the .lib, on purpose."""
    rise, fall = seq.edges()
    covers(seq, w, sample_before)
    v = seq.vdd
    reads = {k: e for k, e, _ in seq.checks}
    out = []
    for k, expect, label in seq.checks:
        t_s = rise[k + 1] - sample_before
        r = dict(cycle=k, label=label, settle=[], d50=[], tran=[], depart=[])
        for b in MEAS_BITS:
            sig, one = f"do{b}", (expect >> b) & 1
            t_in = last_entry(w, sig, rise[k], t_s, (VALID_HI if one else VALID_LO) * v, bool(one))
            r["settle"].append((rise[k] if t_in is None else t_in) - fall[k])
            if one and value_at(w, sig, fall[k]) < 0.5 * v:
                t50 = crossing(w, sig, 0.5 * v, fall[k], t_s, True)
                t10 = crossing(w, sig, 0.1 * v, fall[k] - 0.5, t_s, True)
                t90 = crossing(w, sig, 0.9 * v, fall[k], t_s, True)
                if None in (t50, t10, t90):
                    raise RuntimeError(f"cycle {k} ({label}): do{b} does not rise cleanly after the falling edge")
                r["d50"].append(t50 - fall[k])
                r["tran"].append(t90 - t10)
        if k - 1 in reads:
            for b in MEAS_BITS:
                lvl = v if (reads[k - 1] >> b) & 1 else 0.0
                t = None
                ts, vs = w["time"], w[f"do{b}"]
                for i in range(1, len(ts)):
                    if ts[i] < rise[k] - 1.0:
                        continue
                    if ts[i] > t_s:
                        break
                    if abs(vs[i] - lvl) > DEPART * v:
                        a0, a1 = abs(vs[i - 1] - lvl), abs(vs[i] - lvl)
                        f = (DEPART * v - a0) / (a1 - a0) if a1 > a0 else 0.0
                        t = ts[i - 1] + max(0.0, min(1.0, f)) * (ts[i] - ts[i - 1])
                        break
                if t is not None:
                    r["depart"].append(t - rise[k])
        out.append(r)
    return out


def pdk_version():
    """The open_pdks commit of the PDK the models come from (ciel keeps it under versions/<hash>/)."""
    m = re.search(r"/versions/([0-9a-f]{40})/", os.path.realpath(NGSPICE_DIR))
    return m.group(1) if m else "unknown"


def ngspice_version():
    p = subprocess.run(["ngspice", "--version"], capture_output=True, text=True)
    m = re.search(r"ngspice-(\S+)", p.stdout + p.stderr)
    return m.group(1) if m else "unknown"


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_ngspice():
    if shutil.which("ngspice") is None:
        raise SystemExit("sramchar: FAIL - ngspice not found (toolchain.md: Homebrew ngspice)")
