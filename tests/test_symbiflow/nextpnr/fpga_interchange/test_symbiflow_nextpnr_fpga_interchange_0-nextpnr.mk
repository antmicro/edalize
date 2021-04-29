#Auto generated by Edalize

TARGET   := test_symbiflow_nextpnr_fpga_interchange_0

all: $(TARGET).fasm

test_symbiflow_nextpnr_fpga_interchange_0.json: test_symbiflow_nextpnr_fpga_interchange_0.mk
	$(EDALIZE_LAUNCHER) $(MAKE) -f $<

test_symbiflow_nextpnr_fpga_interchange_0.netlist: test_symbiflow_nextpnr_fpga_interchange_0.json
	$(EDALIZE_LAUNCHER) python -m fpga_interchange.yosys_json --schema_dir /home/runner/work/edalize/edalize/tests/mock_commands --device xc7a35t.device --top top_module test_symbiflow_nextpnr_fpga_interchange_0.json test_symbiflow_nextpnr_fpga_interchange_0.netlist

test_symbiflow_nextpnr_fpga_interchange_0.phys: test_symbiflow_nextpnr_fpga_interchange_0.netlist
	$(EDALIZE_LAUNCHER) nextpnr-fpga_interchange --chipdb chipdb.bin --package csg324 --xdc top.xdc --netlist test_symbiflow_nextpnr_fpga_interchange_0.netlist --write test_symbiflow_nextpnr_fpga_interchange_0.routed.json --phys test_symbiflow_nextpnr_fpga_interchange_0.phys --fake_option 1000

test_symbiflow_nextpnr_fpga_interchange_0.fasm: test_symbiflow_nextpnr_fpga_interchange_0.phys
	$(EDALIZE_LAUNCHER) python -m fpga_interchange.fasm_generator --schema_dir /home/runner/work/edalize/edalize/tests/mock_commands --family xc7 xc7a35t.device test_symbiflow_nextpnr_fpga_interchange_0.netlist test_symbiflow_nextpnr_fpga_interchange_0.phys test_symbiflow_nextpnr_fpga_interchange_0.fasm

clean:
	$(EDALIZE_LAUNCHER) rm -f $(TARGET).json $(TARGET).routed.json $(TARGET).netlist $(TARGET).phys $(TARGET).fasm