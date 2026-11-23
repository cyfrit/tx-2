RTL := rtl/tx2_instruction_decode.v rtl/tx2_configuration_decode.v \
       rtl/tx2_exchange.v rtl/tx2_alu.v rtl/tx2_sequence_selector.v rtl/tx2_io.v rtl/tx2_core.v \
       rtl/tx2_memory.v rtl/tx2_system.v rtl/tx2_machine.v
MODULES := tx2_instruction_decode tx2_configuration_decode tx2_exchange tx2_alu tx2_sequence_selector tx2_io tx2_core tx2_memory tx2_system tx2_machine
INIT := $(wildcard programs/core-init-*.hex)
TESTS := decode exchange system core_wait boot alu machine io sequence_selector graphics

.PHONY: check test lint synth clean assemble-demo demo boot graphics sketchpad sketchpad-check
check: test lint synth

build:
	mkdir -p build

build/vector-summary.json: tools/generate_rtl_vectors.py programs/configured-copy.hex programs/configured-copy.tx2as | build
	python3 tools/generate_rtl_vectors.py

build/alu-summary.json: tools/generate_alu_vectors.py | build
	python3 tools/generate_alu_vectors.py

build/machine-summary.json: tools/generate_machine_vectors.py tools/generate_alu_vectors.py tools/generate_rtl_vectors.py | build
	python3 tools/generate_machine_vectors.py

build/tb_alu: build/alu-summary.json
build/tb_machine: build/machine-summary.json
build/tb_boot: programs/hello.tape
build/tb_graphics: programs/display-demo.tape

build/tb_%: tb/tb_%.v $(RTL) $(INIT) | build
	iverilog -g2012 -Wall -s tb_$* -o $@ $(RTL) tb/tb_$*.v

build/fixture-validation.json: tools/verify_program_images.py tools/tx2tape.py programs/hello.tx2as programs/hello.hex programs/hello.tape programs/hello.tape.json programs/display-demo.tx2as programs/display-demo.hex programs/display-demo.tape programs/display-demo.tape.json | build
	python3 tools/verify_program_images.py

test: build/fixture-validation.json build/vector-summary.json $(addprefix build/tb_,$(TESTS))
	vvp build/tb_decode
	vvp build/tb_exchange
	vvp build/tb_system
	vvp build/tb_core_wait
	vvp build/tb_boot
	vvp build/tb_alu
	vvp build/tb_machine
	vvp build/tb_io
	vvp build/tb_sequence_selector
	vvp build/tb_graphics
	python3 tools/render_display_demo.py

demo: build/vector-summary.json build/tb_system
	vvp build/tb_system

boot: build/tb_boot
	vvp build/tb_boot

graphics: build/tb_graphics
	vvp build/tb_graphics
	python3 tools/render_display_demo.py

.PHONY: upstream
upstream:
	python3 tools/fetch_upstream.py

sketchpad: upstream
	python3 tools/run_sketchpad.py

sketchpad-check: check sketchpad

.PHONY: wasm site cli browser devices
# Run native peripheral tests and the Sketchpad interaction suite.
devices: cli
	for t in rtlio writers paperplot printanalog magtape; do python3 tools/test_dev_$$t.py || exit 1; done
	python3 tools/test_sketchpad_functions.py

.PHONY: digits digits-check
digits:
	python3 tools/build_digits.py $(if $(TX2_ASSEMBLER),--assembler "$(TX2_ASSEMBLER)")

digits-check: cli
	python3 tools/test_digits.py

wasm:
	python3 tools/build_wasm.py

site: wasm upstream
	python3 tools/build_site.py

cli:
	python3 tools/build_cli.py

browser: site
	python3 tools/serve_web.py

assemble-demo:
	python3 tools/assemble_demo.py

lint: $(addprefix build/,$(addsuffix -lint.log,$(MODULES)))

build/%-lint.log: $(RTL) $(INIT) | build
	verilator --lint-only -Wall --top-module $* $(RTL) > $@ 2>&1

synth: $(addprefix build/,$(addsuffix -yosys.log,$(MODULES))) build/tx2_core-gates.log

build/%-yosys.log: $(RTL) $(INIT) | build
	yosys -Q -T -p 'read_verilog $(RTL); hierarchy -check -top $*; proc; opt; memory_collect; opt; check -assert; stat' > $@ 2>&1

build/tx2_core-gates.log: $(RTL) $(INIT) | build
	yosys -Q -T -p 'read_verilog $(RTL); synth -top tx2_core; check -assert; stat; write_json build/tx2_core-gates.json' > $@ 2>&1

.DELETE_ON_ERROR:

clean:
	rm -rf build
