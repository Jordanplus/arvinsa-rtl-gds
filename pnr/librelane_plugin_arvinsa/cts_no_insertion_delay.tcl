# Script of Arvinsa.CTSNoInsertionDelay (__init__.py, ADR-0016): LibreLane's own cts.tcl, unchanged,
# with OpenROAD's clock_tree_synthesis wrapped so that every call also passes -no_insertion_delay.
# clock_tree_synthesis sets the insertion-delay option on every call (cts::set_insertion_delay true
# unless the flag is given), so the flag must be on the call itself. check_soc.py cts_macro_latency
# checks the line below in the step log and that the final netlist has no delaybuf_* instance.
rename clock_tree_synthesis arvinsa_clock_tree_synthesis
proc clock_tree_synthesis {args} {
    puts "\[INFO\] arvinsa: clock_tree_synthesis -no_insertion_delay (no macro latency balancing, ADR-0016)"
    arvinsa_clock_tree_synthesis {*}$args -no_insertion_delay
}
source $::env(SCRIPTS_DIR)/openroad/cts.tcl
