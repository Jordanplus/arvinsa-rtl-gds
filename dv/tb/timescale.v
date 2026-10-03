// timescale.v - compiled first so that every later file without its own
// `timescale directive inherits 1ns/1ps (docs/spec/soc_spec.md section 1).
// The Verilator build also passes --timescale 1ns/1ps (dv/scripts/dvlib.py).
`timescale 1ns/1ps
