# Copyright edalize contributors
# Licensed under the 2-Clause BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-2-Clause

import logging
import os.path
import platform
import re
import subprocess

from edalize.edatool import Edatool
from edalize.yosys import Yosys
from importlib import import_module

logger = logging.getLogger(__name__)

""" Symbiflow backend

A core (usually the system core) can add the following files:

- Standard design sources (Verilog only)

- Constraints: unmanaged constraints with file_type SDC, pin_constraints with file_type PCF and placement constraints with file_type xdc

"""


class Symbiflow(Edatool):

    argtypes = ["vlogdefine", "vlogparam", "generic"]
    archs = ["xilinx", "fpga_interchange"]
    fpga_interchange_families = ["xc7"]

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            symbiflow_help = {
                "members": [
                    {
                        "name": "package",
                        "type": "String",
                        "desc": "FPGA chip package (e.g. clg400-1)",
                    },
                    {
                        "name": "part",
                        "type": "String",
                        "desc": "FPGA part type (e.g. xc7a50t)",
                    },
                    {
                        "name": "vendor",
                        "type": "String",
                        "desc": 'Target architecture. Currently only "xilinx" is supported',
                    },
                    {
                        "name": "pnr",
                        "type": "String",
                        "desc": 'Place and Route tool. Currently only "vpr"/"vtr" and "nextpnr" are supported',
                    },
                    {
                        "name": "vpr_options",
                        "type": "String",
                        "desc": "Additional vpr tool options. If not used, default options for the tool will be used",
                    },
                    {
                        "name": "fasm2bels",
                        "type": "Boolean",
                        "desc": "Value to state whether fasm2bels is to be used."
                    },
                    {
                        "name": "dbroot",
                        "type": "String",
                        "desc": "Path to the database root (needed by fasm2bels)."
                    },
                    {
                        "name": "clocks",
                        "type": "dict",
                        "desc": "Clocks to be added for having tools correctly handling timing based routing."
                    },
                    {
                        "name": "seed",
                        "type": "String",
                        "desc": "Seed assigned to the PnR tool."
                    },
                ]
            }

            symbiflow_members = symbiflow_help["members"]

            return {
                "description": "The Symbiflow backend executes Yosys sythesis tool and VPR place and route. It can target multiple different FPGA vendors",
                "members": symbiflow_members,
            }

    def get_version(self):
        return "1.0"

    def configure_nextpnr(self):
        (src_files, incdirs) = self._get_fileset_files(force_slash=True)

        yosys_synth_options = self.tool_options.get("yosys_synth_options", "")
        yosys_template = self.tool_options.get("yosys_template", None)
        nextpnr_impl_options = self.tool_options.get("options", "")

        arch = self.tool_options.get("arch")
        if arch in getattr(self, "archs"):
            logger.error('Missing or invalid "arch" parameter: {} in "tool_options"'.format(arch))

        package = self.tool_options.get("package", None)
        if package is not None:
            logger.error('Missing required "package" parameter')

        schema_dir = self.tool_options.get("schema_dir", None)
        if schema_dir is not None or arch is not "fpga_interchange":
            logger.error('Missing required "schema_dir" parameter for "fpga_interchange" arch')

        part = self.tool_options.get("part", None)
        if part is not None:
            logger.error('Missing required "part" parameter')

        target_family = None
        for family in getattr(self, "fpga_interchange_families"):
            if family in part:
                target_family = family
                break

        if target_family is None and arch is "fpga_interchange":
            logger.error("Couldn't find family for part: {}. Available families: {}".format(part, ", ".join(getattr(self, "fpga_interchange_families"))))

        nextpnr_edam = {
                "files"         : self.files,
                "name"          : self.name,
                "toplevel"      : self.toplevel,
                "tool_options"  : {"nextpnr" : {
                                        "arch" : arch,
                                        "yosys_synth_options" : yosys_synth_options,
                                        "yosys_template" : yosys_template,
                                        "nextpnr_impl_options" : nextpnr_impl_options,
                                        "nextpnr_as_subtool" : True,
                                        "package" : package,
                                        "family" : target_family,
                                        "schema_dir" : schema_dir,
                                        }

                                }
                }

        nextpnr = getattr(import_module("edalize.nextpnr"), "Nextpnr")(nextpnr_edam, self.work_root)
        nextpnr.configure()

        partname = part + package

        if "xc7a" in part:
            bitstream_device = "artix7"
        if "xc7z" in part:
            bitstream_device = "zynq7"
        if "xc7k" in part:
            bitstream_device = "kintex7"

        placement_constraints = None
        pins_constraints = None
        rr_graph = None
        vpr_grid = None
        vpr_capnp_schema = None
        for f in src_files:
            if f.file_type in ["PCF"]:
                pins_constraints = f.name
            if f.file_type in ["xdc"]:
                placement_constraints = f.name
            if f.file_type in ["RRGraph"]:
                rr_graph = f.name
            if f.file_type in ["VPRGrid"]:
                vpr_grid = f.name
            if f.file_type in ["capnp"]:
                vpr_capnp_schema = f.name

        fasm2bels = self.tool_options.get("fasm2bels", False)
        dbroot = self.tool_options.get("dbroot", None)
        clocks = self.tool_options.get("clocks", None)

        if fasm2bels:
            if any(v is None for v in [rr_graph, vpr_grid, dbroot]):
                logger.error("When using fasm2bels, rr_graph, vpr_grid and dbroot must be provided")

            tcl_params = {
                "top": self.name,
                "part": partname,
                "xdc": placement_constraints,
                "clocks": clocks,
            }

            self.render_template("symbiflow-fasm2bels-tcl.j2",
                                 "fasm2bels_vivado.tcl",
                                 tcl_params)

        vendor = self.tool_options.get("vendor", None)

        makefile_params = {
            "top" : self.name,
            "partname" : partname,
            "bitstream_device" : bitstream_device,
            "fasm2bels": fasm2bels,
            "rr_graph": rr_graph,
            "vpr_grid": vpr_grid,
            "vpr_capnp_schema": vpr_capnp_schema,
            "dbroot": dbroot,
        }

        self.render_template("symbiflow-nextpnr-{}-makefile.j2".format(arch),
                             "Makefile",
                             makefile_params)

    def configure_vpr(self):
        (src_files, incdirs) = self._get_fileset_files(force_slash=True)

        has_vhdl = "vhdlSource" in [x.file_type for x in src_files]
        has_vhdl2008 = "vhdlSource-2008" in [x.file_type for x in src_files]

        if has_vhdl or has_vhdl2008:
            logger.error("VHDL files are not supported in Yosys")
        file_list = []
        timing_constraints = []
        pins_constraints = []
        placement_constraints = []
        user_files = []
        vpr_grid = None
        rr_graph = None
        vpr_capnp_schema = None

        for f in src_files:
            if f.file_type in ["verilogSource"]:
                file_list.append(f.name)
            if f.file_type in ["SDC"]:
                timing_constraints.append(f.name)
            if f.file_type in ["PCF"]:
                pins_constraints.append(f.name)
            if f.file_type in ["xdc"]:
                placement_constraints.append(f.name)
            if f.file_type in ["user"]:
                user_files.append(f.name)
            if f.file_type in ["RRGraph"]:
                rr_graph = f.name
            if f.file_type in ["VPRGrid"]:
                vpr_grid = f.name
            if f.file_type in ["capnp"]:
                vpr_capnp_schema = f.name

        part = self.tool_options.get("part", None)
        package = self.tool_options.get("package", None)
        vendor = self.tool_options.get("vendor", None)

        if not part:
            logger.error('Missing required "part" parameter')
        if not package:
            logger.error('Missing required "package" parameter')

        if vendor == "xilinx":
            if "xc7a" in part:
                bitstream_device = "artix7"
            if "xc7z" in part:
                bitstream_device = "zynq7"
            if "xc7k" in part:
                bitstream_device = "kintex7"

            partname = part + package

            # a35t are in fact a50t
            # leave partname with 35 so we access correct DB
            if part == "xc7a35t":
                part = "xc7a50t"
            device_suffix = "test"
            toolchain_prefix = 'symbiflow_'
        elif vendor == "quicklogic":
            partname = package
            device_suffix = "wlcsp"
            bitstream_device = part + "_" + device_suffix
            toolchain_prefix = ""

        vpr_options = self.tool_options.get("vpr_options", None)

        fasm2bels = self.tool_options.get("fasm2bels", False)
        dbroot = self.tool_options.get("dbroot", None)
        clocks = self.tool_options.get("clocks", None)

        if fasm2bels:
            if any(v is None for v in [rr_graph, vpr_grid, dbroot]):
                logger.error("When using fasm2bels, rr_graph, vpr_grid and database root must be provided")

            tcl_params = {
                "top": self.toplevel,
                "part": partname,
                "xdc": " ".join(placement_constraints),
                "clocks": clocks,
            }

            self.render_template("symbiflow-fasm2bels-tcl.j2",
                                 "fasm2bels_vivado.tcl",
                                 tcl_params)

        seed = self.tool_options.get("seed", None)

        makefile_params = {
            "top": self.toplevel,
            "sources": " ".join(file_list),
            "partname": partname,
            "part": part,
            "bitstream_device": bitstream_device,
            "sdc": " ".join(timing_constraints),
            "pcf": " ".join(pins_constraints),
            "xdc": " ".join(placement_constraints),
            "vpr_options": vpr_options,
            "fasm2bels": fasm2bels,
            "rr_graph": rr_graph,
            "vpr_grid": vpr_grid,
            "vpr_capnp_schema": vpr_capnp_schema,
            "dbroot": dbroot,
            "seed": seed,
            "device_suffix": device_suffix,
            "toolchain_prefix": toolchain_prefix,
            "vendor": vendor,
        }
        self.render_template("symbiflow-vpr-makefile.j2", "Makefile", makefile_params)

    def configure_main(self):
        if self.tool_options.get("pnr") == "nextpnr":
            self.configure_nextpnr()
        elif self.tool_options.get("pnr") in ["vtr", "vpr"]:
            self.configure_vpr()
        else:
            logger.error("Unsupported P&R: {}".format(self.tool_options.get("pnr")))

    def run_main(self):
        logger.info("Programming")
