#Auto generated by Edalize

TARGET   := test_symbiflow_0

all: $(TARGET).fasm

test_symbiflow_0.json: test_symbiflow_0.mk
	$(MAKE) -f $<

test_symbiflow_0.fasm: test_symbiflow_0.json
	nextpnr-xilinx --chipdb chipdb.db --xdc top.xdc --json test_symbiflow_0.json --write test_symbiflow_0.routed.json --fasm test_symbiflow_0.fasm --log nextpnr.log

clean:
	rm -f $(TARGET).fasm $(TARGET).routed.json
