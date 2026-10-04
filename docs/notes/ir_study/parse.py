import re, glob, os, sys
W = sys.argv[1]
walls = {}
for l in open(f"{W}/runs/wall_times.txt"):
    m = re.match(r"(\S+) rc=(\d+) wall=(\d+)s", l)
    if m: walls[m[1]] = (m[2], m[3])
rows = []
for d in sorted(glob.glob(f"{W}/runs/*/")):
    name = os.path.basename(d.rstrip("/"))
    log = os.path.join(d, "openroad-irdropreport.log")
    if not os.path.exists(log): continue
    s = open(log).read()
    res = {}
    for blk in re.findall(r"\+ analyze_power_grid -net (\S+)(.*?)####################################", s, re.S):
        net, body = blk
        g = lambda k: (re.search(k + r"\s*:\s*([\d.e+-]+)", body) or [None, None])[1]
        an = re.findall(r"Nodes in all nodes: (\d+)", body); mx = re.findall(r"Nodes in matrix: (\d+)", body)
        nsrc = int(mx[0]) - int(an[0]) if an and mx else None
        lr = dict(re.findall(r"  (met[15]): ([\d.e+-]+) Ohm per square", body))
        res[net] = dict(corner=(re.search(r"Corner\s*:\s*(\S+)", body) or [0, "?"])[1], P=g("Total power"), V=g("Supply voltage"),
                        worst=g("Worstcase IR drop"), avg=g("Average IR drop"), nsrc=nsrc, lr=lr,
                        mode=("vsrc" if "Reading location of sources" in body else
                              (re.search(r"PSM-007[123]\] (.*?)\n", body)[1] if re.search(r"PSM-007[123]\]", body) else "bterms(pins)")))
    rp = re.search(r"^Total\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)", s, re.M)
    sram = re.search(r"([\d.e+-]+)\s+sram0", s)
    w = walls.get(name, ("?", "?"))
    if not res: continue
    vc, vs = res.get("vccd1", {}), res.get("vssd1", {})
    f = lambda x: f"{float(x)*1e3:.3f}" if x else "n/a"
    print(f"{name:24s} corner={vc.get('corner')} V={vc.get('V')} P={vc.get('P')}W rp_total={rp[4] if rp else 'n/a'} sram0={sram[1] if sram else 'n/a'} "
          f"| vccd1 worst={f(vc.get('worst'))}mV avg={f(vc.get('avg'))}mV nsrc={vc.get('nsrc')} | vssd1 worst={f(vs.get('worst'))}mV avg={f(vs.get('avg'))}mV nsrc={vs.get('nsrc')} "
          f"| R/sq met1={vc.get('lr',{}).get('met1')} met5={vc.get('lr',{}).get('met5')} | src={vc.get('mode')} | rc={w[0]} wall={w[1]}s")
