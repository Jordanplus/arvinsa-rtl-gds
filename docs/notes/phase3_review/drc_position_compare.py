"""Position check of the Magic DRC report inside the SRAM outline (Phase 3 independent review).

usage: python3 drc_position_compare.py <sram-alone drc.magic.rpt> <soc_top drc.magic.rpt>
e.g. runs/sram_drc_baseline/out/reports/drc.magic.rpt  runs/soc_top/65-magic-drc/reports/drc.magic.rpt
Every soc_top violation box must equal, lie inside, or touch a box of the same rule in the SRAM-alone
report shifted to the sram0 origin (301.76, 364.48). Not part of make phase3 (see docs/notes/phase3_review/README.md).
"""
import sys
BASE, RUN = sys.argv[1], sys.argv[2]
import re, collections
num = re.compile(r"^ (-?[\d.]+)um (-?[\d.]+)um (-?[\d.]+)um (-?[\d.]+)um$")
def stream(path):
    rule=None
    with open(path, encoding="utf8", errors="replace") as f:
        next(f,None)
        for line in f:
            line=line.rstrip("\n")
            m=num.match(line)
            if m: yield rule, tuple(round(float(v)*1000) for v in m.groups())
            elif line.startswith("[INFO]"): pass
            elif line and not line.startswith("-"): rule=line
ox,oy=301760,364480
G=2000
def key(b): return (b[0]<<60)|(b[1]<<40)|(b[2]<<20)|b[3]
alone_exact=collections.defaultdict(set); grid=collections.defaultdict(list)
for r,b in stream(BASE):
    t=(b[0]+ox,b[1]+oy,b[2]+ox,b[3]+oy)
    alone_exact[r].add(key(t))
miss=[]
for r,b in stream(RUN):
    if key(b) not in alone_exact.get(r,()): miss.append((r,b))
del alone_exact
cells=set()
for r,b in miss:
    for gx in range(b[0]//G-1,b[2]//G+2):
        for gy in range(b[1]//G-1,b[3]//G+2): cells.add((gx,gy))
for r,b in stream(BASE):
    t=(b[0]+ox,b[1]+oy,b[2]+ox,b[3]+oy)
    for gx in range(t[0]//G,t[2]//G+1):
        for gy in range(t[1]//G,t[3]//G+1):
            if (gx,gy) in cells: grid[(gx,gy,r)].append(t)
def cand(r,b):
    s=[]
    for gx in range(b[0]//G,b[2]//G+1):
        for gy in range(b[1]//G,b[3]//G+1): s+=grid.get((gx,gy,r),[])
    return s
contained=overlap=none=0; nonesamp=collections.Counter(); ex=[]
for r,b in miss:
    c=cand(r,b)
    if any(b[0]>=B[0] and b[1]>=B[1] and b[2]<=B[2] and b[3]<=B[3] for B in c): contained+=1
    elif any(not (b[2]<=B[0] or B[2]<=b[0] or b[3]<=B[1] or B[3]<=b[1]) or (b[2]>=B[0] and B[2]>=b[0] and b[3]>=B[1] and B[3]>=b[1]) for B in c): overlap+=1
    else:
        none+=1; nonesamp[r]+=1
        if len(ex)<10: ex.append((r,[v/1000 for v in b]))
print('missing',len(miss),'contained in an alone box',contained,'touching/overlapping an alone box',overlap,'no alone box nearby',none)
print(nonesamp.most_common(10)); print(ex)
