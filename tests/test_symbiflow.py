import os
import pytest

from edalize_common import make_edalize_test, tests_dir


@pytest.mark.parametrize("pnr_tool", ["vtr", "nextpnr"])
def test_symbiflow(make_edalize_test, pnr_tool):
    tool_options = {
        "part": "xc7a35tcsg324-1",
        "package": "csg324-1",
        "vendor": "xilinx",
        "pnr": pnr_tool,
        "additional_vpr_options": "--fake_option 1000"
    }
    if pnr_tool == "nextpnr":
        tool_options["yosys_additional_tcl_file"] = "test_symbiflow/additional.tcl"
    files = [{"name": "top.xdc", "file_type": "xdc"}]

    if pnr_tool == "nextpnr":
        files.append({"name": "chipdb.db", "file_type": "bba"})

    name = "test_symbiflow_0"

    tf = make_edalize_test("symbiflow",
                           param_types=[],
                           files=files,
                           tool_options=tool_options,
                           ref_dir=pnr_tool,)
    tf.backend.configure()
    config_file_list = [
        "Makefile",
    ]

    if pnr_tool == "nextpnr":
        config_file_list.append(name + ".mk")
        config_file_list.append(name + ".tcl")
        config_file_list.append(name + "-nextpnr.mk")

    tf.compare_files(config_file_list)
