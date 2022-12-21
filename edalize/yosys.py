# Copyright edalize contributors
# Licensed under the 2-Clause BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-2-Clause

import logging
import os.path

from edalize.edatool import Edatool
from edalize.utils import EdaCommands

logger = logging.getLogger(__name__)


class Yosys(Edatool):

    argtypes = ["vlogdefine", "vlogparam"]

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            return {
                "description": "Open source synthesis tool targeting many different FPGAs",
                "members": [
                    {
                        "name": "arch",
                        "type": "String",
                        "desc": "Target architecture. Legal values are *xilinx*, *ice40* and *ecp5*",
                    },
                    {
                        "name": "output_format",
                        "type": "String",
                        "desc": "Output file format. Legal values are *json*, *edif*, *blif*, *verilog*",
                    },
                    {
                        "name": "output_name",
                        "type": "String",
                        "desc": "Output file name. [Optional]",
                    },
                    {
                        "name": "yosys_as_subtool",
                        "type": "bool",
                        "desc": "Determines if Yosys is run as a part of bigger toolchain, or as a standalone tool",
                    },
                    {
                        "name": "makefile_name",
                        "type": "String",
                        "desc": "Generated makefile name, defaults to $name.mk",
                    },
                    {
                        "name": "yosys_template",
                        "type": "String",
                        "desc": "TCL template file to use instead of default template",
                    },
                ],
                "lists": [
                    {
                        "name": "yosys_synth_options",
                        "type": "String",
                        "desc": "Additional options for the synth command",
                    },
                ],
            }

    def _configure_readsystemverilog(self):
        """returns a list of Yosys commands to process Verilog and SystemVerilog sources"""
        unused_files = []
        file_table = []
        includes = set()
        for f in self.edam["files"]:
            # check if Verilog or SystemVerilog
            if "file_type" not in f:
                continue
            if "is_include_file" in f:
                includes.add(os.path.dirname(f["name"]))
            if f["file_type"].find("erilogSource") > 0:
                file_table.append(f["name"])
            else:
                unused_files.append(f)

        # we assume that every directory that contains sources can also contain include files
        #   as the include files are not always properly marked in the core files.
        includes |= {os.path.dirname(f) for f in file_table}
        file_table = [f for f in file_table if not f.endswith(".svh")]
        self.edam["files"] = unused_files[:]

        # Read all files in one command.
        # Prepend with flags for includes
        include_str = ""
        if includes:
            include_str = "-I" + " -I".join(set(includes)) + " "

        read_command = ""
        if file_table:
            read_command = "read_systemverilog " + include_str + " ".join(file_table)

        return read_command

    def gen_script_nosynth(self, read_command, plugins):
        """Generates a TCL script for Yosys to parse SystemVerilog files without synthesis"""
        commands = EdaCommands()
        targets = []

        # TODO use verilog_defines
        verilog_defines = []
        for key, value in self.vlogdefine.items():
            verilog_defines.append("{{{key} {value}}}".format(key=key, value=value))

        # TODO use verilog_params
        verilog_params = []
        for key, value in self.vlogparam.items():
            if type(value) is str:
                value = '{"' + value + '"}'
            verilog_params.append(f"-P{key}={self._param_value_str(value)}")
        rtlil = self.toplevel + ".rtlil"

        template_vars = {
            "file_table": read_command,
            "top": self.toplevel,
            "name": self.name,
            "plugins": "plugin -i %s \n" * len(plugins) % tuple(plugins),
            "write_command": "write_rtlil " + rtlil,
        }
        tcl_script = "yosys_nosynth.tcl"
        self.render_template("yosys_nosynth.tcl.j2", tcl_script, template_vars)
        commands.add(
            ["yosys", "-l", "yosys.log", "-p", f"'tcl {tcl_script}'"],
            [rtlil],
            [],
            [tcl_script],
        )
        targets.append(rtlil)
        commands.add([], ["rtlil"], [], targets)
        commands.set_default_target("rtlil")
        commands.write(os.path.join(self.work_root, "Makefile"))
        self.commands = commands.commands

    def gen_script(self, file_table, incdirs, plugins, commands):
        arch = self.tool_options.get("arch", None)
        if not arch:
            logger.error("ERROR: arch is not defined.")
        # todo simplify
        yosys_template = self.tool_options.get("yosys_template")
        template = yosys_template or "edalize_yosys_template.tcl"

        output_format = self.tool_options.get("output_format", "blif")
        default_target = self.tool_options.get(
            "output_name", f"{self.name}.{output_format}"
        )

        self.edam["files"].append(
            {
                "name": default_target,
                "file_type": "jsonNetlist"
                if output_format == "json"
                else output_format,
            }
        )

        verilog_defines = []
        for key, value in self.vlogdefine.items():
            verilog_defines.append("{{{key} {value}}}".format(key=key, value=value))

        verilog_params = []
        for key, value in self.vlogparam.items():
            if type(value) is str:
                value = '{"' + value + '"}'
            _s = r"chparam -set {} {} {}"
            verilog_params.append(
                _s.format(key, self._param_value_str(value), self.toplevel)
            )

        template_vars = {
            "verilog_defines": "{" + " ".join(verilog_defines) + "}",
            "verilog_params": "\n".join(verilog_params),
            "file_table": "\n".join(file_table),
            "incdirs": " ".join(["-I" + d for d in incdirs]),
            "top": self.toplevel,
            "synth_command": "synth_" + arch,
            "synth_options": " ".join(self.tool_options.get("yosys_synth_options", "")),
            "write_command": "write_" + output_format,
            "output_name": default_target,
            "output_opts": "-pvector bra " if arch == "xilinx" else "",
            "yosys_template": template,
            "name": self.name,
            "plugins": "plugin -i %s \n" * len(plugins) % tuple(plugins),
        }

        self.render_template(
            "edalize_yosys_procs.tcl.j2", "edalize_yosys_procs.tcl", template_vars
        )

        if not yosys_template:
            self.render_template(
                "yosys-script-tcl.j2", "edalize_yosys_template.tcl", template_vars
            )

        commands.add(
            ["yosys", "-l", "yosys.log", "-p", f"'tcl {template}'"],
            [default_target],
            [template] + additional_deps,
        )
        if self.tool_options.get("yosys_as_subtool"):
            self.commands = commands.commands
        else:
            commands.set_default_target(f"{self.name}.{output_format}")
            commands.write(os.path.join(self.work_root, "Makefile"))

    def configure_main(self):
        # write Yosys tcl script file

        plugins = ["systemverilog"]

        self.edam["files"] = [] if not "files" in self.edam else self.edam["files"]

        read_command = self._configure_readsystemverilog()

        self.gen_script_nosynth(read_command, plugins)
