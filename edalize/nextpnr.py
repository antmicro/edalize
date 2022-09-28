# Copyright edalize contributors
# Licensed under the 2-Clause BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-2-Clause

import os.path

from edalize.edatool import Edatool
from edalize.utils import EdaCommands


class Nextpnr(Edatool):
    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            return {
                "description": "a portable FPGA place and route tool",
                "members": [],
                "lists": [
                    {
                        "name": "nextpnr_options",
                        "type": "String",
                        "desc": "Additional options for nextpnr",
                    },
                ],
            }

    def configure_main(self):
        cst_file = ""
        lpf_file = ""
        pcf_file = ""
        xdc_file = ""
        pdc_file = ""
        qsf_file = ""
        netlist = ""
        unused_files = []

        arch = self.flow_config["arch"]
        is_interchange = arch == "fpga_interchange"
        chipdb = self.tool_options.get("chipdb")
        if is_interchange and (chipdb is None):
            raise RuntimeError(
                "Nextpnr-fpga_interchange require chipdb to be specified."
            )
        package = self.tool_options.get("package")

        for f in self.files:
            if f["file_type"] == "CST":
                if cst_file:
                    raise RuntimeError(
                        "Nextpnr only supports one CST file. Found {} and {}".format(
                            cst_file, f["name"]
                        )
                    )
                cst_file = f["name"]
            if f["file_type"] == "LPF":
                if lpf_file:
                    raise RuntimeError(
                        "Nextpnr only supports one LPF file. Found {} and {}".format(
                            pcf_file, f["name"]
                        )
                    )
                lpf_file = f["name"]
            if f["file_type"] == "PDC":
                if pdc_file:
                    raise RuntimeError(
                        "Nextpnr only supports one PDC file. Found {} and {}".format(
                            pdc_file, f["name"]
                        )
                    )
                pdc_file = f["name"]
            if f["file_type"] == "PCF":
                if pcf_file:
                    raise RuntimeError(
                        "Nextpnr only supports one PCF file. Found {} and {}".format(
                            pcf_file, f["name"]
                        )
                    )
                pcf_file = f["name"]
            elif f["file_type"] == "XDC":
                if xdc_file:
                    raise RuntimeError(
                        "Nextpnr only supports one XDC file. Found {} and {}".format(
                            xdc_file, f["name"]
                        )
                    )
                xdc_file = f["name"]
            if f["file_type"] == "QSF":
                if qsf_file:
                    raise RuntimeError(
                        "Nextpnr only supports one QSF file. Found {} and {}".format(
                            qsf_file, f["name"]
                        )
                    )
                qsf_file = f["name"]
            elif f["file_type"] == "jsonNetlist":
                if netlist:
                    raise RuntimeError(
                        "Nextpnr only supports one netlist. Found {} and {}".format(
                            netlist, f["name"]
                        )
                    )
                netlist = f["name"]
                if is_interchange:
                    raise RuntimeError(
                        "Nextpnr-fpga_interchange requires fpga-interchange logical netlist instead of JSON, found{}".format(
                            f["name"]
                        )
                    )
                netlist = f["name"]
            elif f["file_type"] == "fpgaInterchangeNetlist":
                if netlist:
                    raise RuntimeError(
                        "Nextpnr only supports one netlist. Found {} and {}".format(
                            netlist, f["name"]
                        )
                    )
                if not is_interchange:
                    raise RuntimeError(
                        "Non-interchange variants of Nextpnr require JSON netlist, found{}".format(
                            f["name"]
                        )
                    )
            else:
                unused_files.append(f)

        self.edam["files"] = unused_files
        of = [
            {"name": self.name + ".asc", "file_type": "iceboxAscii"},
        ]
        self.edam["files"] += of

        # Write Makefile
        commands = EdaCommands()

        arch_options = []
        if arch == "ecp5":
            targets = self.name + ".config"
            constraints = ["--lpf", lpf_file] if lpf_file else []
            output = ["--textcfg", targets]
        elif arch == "mistral":
            device = self.tool_options.get("device")
            if not device:
                raise RuntimeError(
                    "Missing required option 'device' for nextpnr-mistral"
                )
            arch_options += ["--device", device]
            targets = self.name + ".rbf"
            constraints = ["--qsf", qsf_file] if qsf_file else []
            output = ["--rbf", targets]
        elif arch == "nexus":
            device = self.tool_options.get("device")
            if not device:
                raise RuntimeError("Missing required option 'device' for nextpnr-nexus")
            arch_options += ["--device", device]
            targets = self.name + ".fasm"
            constraints = ["--pdc", pdc_file] if pdc_file else []
            output = ["--fasm", targets]
        elif arch == "gowin":
            device = self.tool_options.get("device")
            if not device:
                raise RuntimeError("Missing required option 'device' for nextpnr-gowin")
            arch_options += ["--device", device]
            targets = self.name + ".pack"
            constraints = ["--cst", cst_file] if cst_file else []
            output = ["--write", targets]
        elif arch == "fpga_interchange":
            targets = self.name + ".phys"
            constraints = ["--xdc", xdc_file]
            output = ["--phys", targets]
        else:
            targets = self.name + ".asc"
            constraints = ["--pcf", pcf_file] if pcf_file else []
            output = ["--asc", targets]

        depends = netlist
        command = ["nextpnr-" + arch, "-l", "next.log"]
        command += arch_options + self.tool_options.get("nextpnr_options", [])
        command += constraints
        if is_interchange:
            command += ["--netlist", depends, "--chipdb", chipdb]
        else:
            command += ["--json", depends]
        if package is not None:
            command += ["--package", package]
        command += output

        # CLI target
        commands.add(command, [targets], [depends])

        # GUI target
        commands.add(command + ["--gui"], ["build-gui"], [depends])
        self.commands = commands.commands

        commands.set_default_target(targets)
        commands.write(os.path.join(self.work_root, "Makefile"))
