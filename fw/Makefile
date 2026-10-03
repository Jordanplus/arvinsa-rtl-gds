# fw/Makefile - SoC firmware and boot ROM build (docs/spec/soc_spec.md §6).
# GNU make 3.81 compatible: no .ONESHELL/.SHELLFLAGS/$(file)/undefine, no pipes in recipes.
#
#   make -C fw all            all tests + boot ROM image + build/size_report.txt
#   make -C fw <test>         one test: build/<test>.elf .bin .hex .lst (+ size check)
#   make -C fw bootrom        regenerate rtl/bootrom/bootrom.v from the boot ROM image
#   make -C fw check-bootrom  regenerate into build/ and compare with rtl/bootrom/bootrom.v
#   make -C fw clean
SHELL := /bin/bash
.DELETE_ON_ERROR:
.SUFFIXES:

ROOT        := ..
B           := build
PY          ?= python3
CROSS       ?= riscv64-elf-
CC          := $(CROSS)gcc
OBJCOPY     := $(CROSS)objcopy
OBJDUMP     := $(CROSS)objdump
NM          := $(CROSS)nm
SIZE        := $(CROSS)size

MEMMAP      := $(ROOT)/rtl/include/memmap.vh
PICO_FW     := $(ROOT)/third_party/picorv32/firmware
BOOTROM_V   := $(ROOT)/rtl/bootrom/bootrom.v
GEN_BOOTROM := $(ROOT)/rtl/bootrom/gen_bootrom.py

# SoC tests (spec §6.1). Libraries: libgcc only (no newlib).
CFLAGS  := -march=rv32imc -mabi=ilp32 -Os -ffreestanding -nostdlib -nostartfiles \
           -g -Wall -Wextra -Werror -ffunction-sections -fdata-sections \
           -MMD -MP -Icommon -I$(B) -I$(PICO_FW)
# The whole image lives in one RWX SRAM region by design, so the RWX-segment warning is off.
LDFLAGS := -march=rv32imc -mabi=ilp32 -ffreestanding -nostdlib -nostartfiles -Wl,--gc-sections \
           -Wl,--no-warn-rwx-segments

# Boot ROM (spec §6.5): plain RV32I, no compressed instructions, no libraries.
BOOT_ASFLAGS := -march=rv32i -mabi=ilp32 -ffreestanding -nostdlib -nostartfiles \
                -g -MMD -MP -Icommon -I$(B)
BOOT_LDFLAGS := -march=rv32i -mabi=ilp32 -ffreestanding -nostdlib -nostartfiles -Wl,--no-warn-rwx-segments

# Every test of spec §6.4 that loads an SRAM image, plus the directed tests
# regs and unmapped (dv/tests.toml). bootrom_march loads nothing (it runs the
# boot ROM only), so its target builds the boot ROM image instead.
TESTS := hello memtest irq muldiv uart_echo neg_fw_hang neg_fw_illegal \
         boot_uart_hello boot_host_hello regs unmapped
# Tests that reuse another test's sources (same image, own output names).
SRC_boot_uart_hello := hello
SRC_boot_host_hello := hello
# Extra size limit (linker symbol) per test; all tests are also held to _stack_limit.
LIMIT_SYM_memtest := _sram_half

COMMON_OBJS := $(B)/obj/common/start.o $(B)/obj/common/fwlib.o
BOOTROM_OBJ := $(B)/obj/bootrom/bootrom.o

# Build-flag record. Every generated linker script, object, ELF and size
# check depends on it and on this Makefile, so a changed flag, toolchain
# version, per-test size limit or recipe rebuilds everything an incremental
# 'make' would otherwise reuse. The recipe always runs (FORCE) but replaces
# the file only when its content changes, so an unchanged build stays a no-op.
FLAGS_STAMP := $(B)/build_flags.txt
CC_VERSION  := $(shell $(CC) -dumpfullversion -dumpversion 2>/dev/null)
REBUILD_ON  := $(FLAGS_STAMP) Makefile

test_dir = tests/$(if $(SRC_$(1)),$(SRC_$(1)),$(1))

.PHONY: all bootrom bootrom-image check-bootrom bootrom_march clean FORCE $(TESTS)

all: $(TESTS) $(B)/size_report.txt bootrom-image

# ---------------------------------------------------------------- build-flag record
FORCE:

$(FLAGS_STAMP): FORCE
	@mkdir -p $(B)
	@printf '%s\n' 'CC=$(CC) $(CC_VERSION)' 'CFLAGS=$(CFLAGS)' 'LDFLAGS=$(LDFLAGS)' \
	    'BOOT_ASFLAGS=$(BOOT_ASFLAGS)' 'BOOT_LDFLAGS=$(BOOT_LDFLAGS)' \
	    'OBJCOPY=$(OBJCOPY) OBJDUMP=$(OBJDUMP) NM=$(NM) SIZE=$(SIZE) PY=$(PY)' \
	    'LIMITS=$(foreach t,$(TESTS),$(t):$(if $(LIMIT_SYM_$(t)),$(LIMIT_SYM_$(t)),_stack_limit))' > $@.tmp
	@if cmp -s $@.tmp $@; then rm -f $@.tmp; else mv -f $@.tmp $@; echo "fw: build flags changed, rebuilding ($@)"; fi

# ---------------------------------------------------------------- generated headers
$(B)/soc.h: $(MEMMAP) scripts/gen_soc_h.py
	@mkdir -p $(B)
	$(PY) scripts/gen_soc_h.py --in $(MEMMAP) --out $@

$(B)/link.ld: common/link.ld common/fw_layout.h $(B)/soc.h $(REBUILD_ON)
	$(CC) -E -P -undef -x c -Icommon -I$(B) $< -o $@

$(B)/bootrom.ld: bootrom/bootrom.ld $(B)/soc.h $(REBUILD_ON)
	$(CC) -E -P -undef -x c -Icommon -I$(B) $< -o $@

# ---------------------------------------------------------------- objects
$(B)/obj/common/%.o: common/%.c $(B)/soc.h $(REBUILD_ON)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -c $< -o $@

$(B)/obj/common/%.o: common/%.S $(B)/soc.h $(REBUILD_ON)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -c $< -o $@

$(BOOTROM_OBJ): bootrom/bootrom.S $(B)/soc.h $(REBUILD_ON)
	@mkdir -p $(@D)
	$(CC) $(BOOT_ASFLAGS) -c $< -o $@

# ---------------------------------------------------------------- per-test rules
define TEST_RULES
$(1)_OBJS := $$(patsubst $$(call test_dir,$(1))/%.c,$(B)/obj/$(1)/%.o,$$(wildcard $$(call test_dir,$(1))/*.c))

$(B)/obj/$(1)/%.o: $$(call test_dir,$(1))/%.c $(B)/soc.h $(REBUILD_ON)
	@mkdir -p $$(@D)
	$$(CC) $$(CFLAGS) -c $$< -o $$@

$(B)/$(1).elf: $(COMMON_OBJS) $$($(1)_OBJS) $(B)/link.ld $(REBUILD_ON)
	$$(CC) $$(LDFLAGS) -T $(B)/link.ld -Wl,-Map=$(B)/$(1).map -o $$@ $(COMMON_OBJS) $$($(1)_OBJS) -lgcc

$(1): $(B)/$(1).elf $(B)/$(1).bin $(B)/$(1).hex $(B)/$(1).lst $(B)/$(1).size
endef
$(foreach t,$(TESTS),$(eval $(call TEST_RULES,$(t))))

# ---------------------------------------------------------------- image formats
$(B)/%.bin: $(B)/%.elf
	$(OBJCOPY) -O binary $< $@

$(B)/%.hex: $(B)/%.bin scripts/bin2hex.py
	$(PY) scripts/bin2hex.py $< $@

$(B)/%.lst: $(B)/%.elf
	$(OBJDUMP) -h -d -S $< > $@

# Size checker (spec §6.2): fails the build when _free_start is over the limit.
$(B)/%.size: $(B)/%.elf scripts/size_check.py $(REBUILD_ON)
	$(PY) scripts/size_check.py --nm $(NM) --size $(SIZE) --elf $< --name $* \
	    --limit-sym $(if $(LIMIT_SYM_$*),$(LIMIT_SYM_$*),_stack_limit) --out $@

$(B)/size_report.txt: $(foreach t,$(TESTS),$(B)/$(t).size) scripts/size_check.py
	$(PY) scripts/size_check.py --report $@ $(filter %.size,$^)

# ---------------------------------------------------------------- boot ROM
$(B)/bootrom.elf: $(BOOTROM_OBJ) $(B)/bootrom.ld $(REBUILD_ON)
	$(CC) $(BOOT_LDFLAGS) -T $(B)/bootrom.ld -Wl,-Map=$(B)/bootrom.map -o $@ $(BOOTROM_OBJ)

bootrom-image: $(B)/bootrom.elf $(B)/bootrom.bin $(B)/bootrom.hex $(B)/bootrom.lst

bootrom_march: bootrom-image

bootrom: bootrom-image
	$(PY) $(GEN_BOOTROM) --hex $(B)/bootrom.hex --out $(BOOTROM_V)

check-bootrom: bootrom-image
	$(PY) $(GEN_BOOTROM) --hex $(B)/bootrom.hex --out $(B)/bootrom_check.v
	@if cmp -s $(B)/bootrom_check.v $(BOOTROM_V); then \
	    echo "check-bootrom: PASS: $(BOOTROM_V) matches the boot ROM image"; \
	else \
	    echo "check-bootrom: FAIL: $(BOOTROM_V) is stale or edited; run 'make -C fw bootrom'" >&2; \
	    exit 1; \
	fi

clean:
	rm -rf $(B)

-include $(wildcard $(B)/obj/*/*.d)
