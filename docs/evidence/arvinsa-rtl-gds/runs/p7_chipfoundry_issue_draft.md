<!-- 草稿：給 chipfoundry/cf-precheck 的 issue。使用者決定要不要送出（ADR-0019 決定 6）。只用 PDK 預建的 SRAM 重現，不含本專案的設計。 -->

**Title:** sky130A `MR_mcon.CON.10` and `MR_licon.SP.6` flag the OpenRAM bitcells of the PDK's own `sky130_sram_*` macros (areaid.ce exemption removed in 08f559e)

### Summary

With the bundled deck `drc_scripts/sky130A_mr.drc` (release `2026.03.30_01.00`, cf-precheck `6c401ed5`), the PDK's prebuilt SRAM macro `sky130_sram_2kbyte_1rw1r_32x512_8` alone fails `klayout_feol` and `klayout_beol`. Every violation is inside the OpenRAM bitcells (`sky130_fd_bd_sram__openram_dp_cell`, `_replica`, `_dummy`) and the replica columns, i.e. inside `areaid.ce` (81/2). So any Caravel project that uses an OpenRAM-based sky130 SRAM, including the PDK macros, cannot pass precheck.

### Repro (PDK macro only)

```
klayout -b -r src/cf_precheck/drc_scripts/sky130A_mr.drc \
  -rd input=$PDK_ROOT/sky130A/libs.ref/sky130_sram_macros/gds/sky130_sram_2kbyte_1rw1r_32x512_8.gds \
  -rd topcell=sky130_sram_2kbyte_1rw1r_32x512_8 -rd report=out.xml -rd thr=8 -rd beol=true
```
(same with `feol=true`; same arguments as `checks/klayout_drc.py`). KLayout 0.30.7; PDK open_pdks `8afc834`.

| check | violations (per cell, KLayout deep mode) | rule | cells |
|---|---|---|---|
| FEOL | 3 | `MR_licon.SP.6` | `sky130_fd_bd_sram__openram_dp_cell`, `_replica`, `_dummy` |
| BEOL | 264 | `MR_mcon.CON.10` | `..._replica_column` (128), `..._replica_column_0` (128), `sky130_fd_bd_sram__openram_dp_cell` (3), `..._replica_bitcell_array` (2), `_replica` (2), `_dummy` (1) |
| offgrid | 0 | | |

### Cause

Commit `08f559e30a` ("sync sky130A precheck deck with master", 2026-05-07) changed

```
-    mconnotace.not(li).output("MR_mcon.CON.10", ...)
+    mcon.not(li).output("MR_mcon.CON.10", ...)
```

so the check no longer excludes `areaid.ce`. The previous deck (open_pdks `sky130A_mr.drc` release `2024.2.11_01.09`, rule `ct.4`) used `mconnotace = mcon.not(areaid_ce)`. `MR_licon.SP.6` (poly licon to psdm 0.11 µm) is new and also hits the bitcell. `$sram_exclude` does not cover either rule.

### Questions

1. Is removing the `areaid.ce` exemption for `MR_mcon.CON.10` intended? The SRAM core cells are drawn to the foundry's SRAM rules inside `areaid.ce`.
2. If it is intended, what is the accepted path for projects with OpenRAM / PDK SRAM macros (waiver, `sram_exclude`, abstracting the macro)?

Related: #108, #51.

### Additional question: latch-up marker in the user area (added 2026-10-15)

Our `user_project_wrapper.gds` is written by KLayout (LibreLane), so it carries no `areaid.lowTapDensity` (81/14). Magic's sky130 tech generates 81/14 over the top cell shrunk by 250 um when it writes GDS, and the standard cells are tapped for the 15 um rule (`FP_TAPCELL_DIST` 13 um). Measured on our wrapper: 0 diffusion farther than 15 um from a same-type tap, but about 7% of the diffusion area outside the SRAM is farther than 6 um. Neither the precheck KLayout deck nor its Magic DRC checks the 6 um rule.

3. Is 81/14 added to the user area when the full chip is assembled for tapeout, or should the user project add it (and over which area, given "at least 50 um from padframe")?
4. Which tap distance does the tapeout check apply to the user area, 6 um or 15 um?
