# Copyright edalize contributors
# Licensed under the 2-Clause BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-2-Clause

import logging
import os.path

from edalize.edatool import Edatool
from edalize.utils import EdaCommands
from edalize.surelog import Surelog
from edalize.sv2v import Sv2v

logger = logging.getLogger(__name__)


class Yosys(Edatool):

    argtypes = ["vlogdefine", "vlogparam"]

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            options = {
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
                        'name' : 'yosys_read_options',
                        'type' : 'String',
                        'desc' : 'Addtional options for the read_* command (e.g. read_verlog or read_uhdm)'
                    },
                    {
                        "name": "yosys_synth_options",
                        "type": "String",
                        "desc": "Additional options for the synth command",
                    },
                ],
            }

            Edatool._extend_options(options, Surelog)
            Edatool._extend_options(options, Sv2v)

            return options

    def _configure_readsystemverilog(self):
        '''returns a list of Yosys commands to process Verilog and SystemVerilog sources'''
        unused_files = []
        file_table = []
        for f in self.edam['files']:
            # check if Verilog or SystemVerilog
            if 'file_type' not in f:
                continue
            if f['file_type'].find('erilogSource') > 0:
                file_table.append('read_systemverilog -defer {' + f['name'] + '}')
            else:
                unused_files.append(f)
        if file_table:
            file_table.append('read_systemverilog -link')
        self.edam['files'] = unused_files[:]
        return file_table

    def gen_script(self, file_table, incdirs, plugins, commands):
        arch = self.tool_options.get('arch', None)
        if not arch:
            logger.error("ERROR: arch is not defined.")
        #todo simplify
        yosys_template = self.tool_options.get('yosys_template')
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
            'plugins': "plugin -i %s \n"*len(plugins) % tuple(plugins)
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

        yosys_synth_options = self.tool_options.get('yosys_synth_options', [])

        commands = EdaCommands()
        additional_deps = []
        plugins = []

        self.edam['files'] = [] if not 'files' in self.edam else self.edam['files']
        file_table = []

        if True: #TODO
            self.generate_separate_tests()
            return

        if "frontend=surelog" in yosys_synth_options:
            arch = self.tool_options.get('arch', None)
            if not arch:
                logger.error("ERROR: arch is not defined.")

            self.edam['tool_options'].update({'surelog' : {
                    'arch' : arch,
                    'surelog_options' : self.tool_options.get('surelog_options', []),
                    'library_files' : self.tool_options.get('library_files', []),
                    'surelog_as_subtool' : True,
                    }
                })
            yosys_synth_options.remove("frontend=surelog")
            surelog = Surelog(self.edam, self.work_root)
            surelog.configure()
            self.vlogparam.clear() # vlogparams are handled by Surelog
            self.vlogdefine.clear() # vlogdefines are handled by Surelog
            commands.commands += surelog.commands
            additional_deps = [self.toplevel + '.uhdm']
            self.edam['files'] = surelog.edam['files']
            plugins += ['uhdm']
        elif "frontend=sv2v" in yosys_synth_options:
            self.edam['tool_options'].update({'sv2v' : {
                        'sv2v_options' : self.tool_options.get('sv2v_options', []),
                        'sv2v_as_subtool' : True
                        }
                    })
            yosys_synth_options.remove("frontend=sv2v")
            sv2v = Sv2v(self.edam, self.work_root)
            sv2v.configure()
            self.edam['files'] = sv2v.edam['files']
            commands.commands += sv2v.commands
            additional_deps = [self.name+".sv2v"]
        else:
            file_table = self._configure_readsystemverilog()
            plugins += ['systemverilog']

        incdirs = []
        unused_files = []
        yosys_read_options = " ".join(self.tool_options.get('yosys_read_options', []))

        for f in self.edam['files']:
            cmd = ""
            if f["file_type"].startswith("verilogSource"):
                cmd = "read_verilog"
            elif f["file_type"].startswith("systemVerilogSource"):
                cmd = "read_verilog -sv"
            elif f["file_type"] == "tclSource":
                cmd = "source"
            elif f["file_type"] == "uhdm":
                cmd = "read_uhdm"

            if cmd and not self._add_include_dir(f, incdirs):
                file_table.append(cmd + yosys_read_options + " {" + f["name"] + "}")
            else:
                unused_files.append(f)
                print(f"Skipping file without file_type: {f}")

        self.edam["files"] = unused_files
        self.gen_script(file_table, incdirs, plugins, commands)

    def generate_separate_tests(self):
        default_target = self.tool_options.get(
            "output_name", f"{self.name}.{output_format}"
        )

        # iterate over Verilog or SystemVerilog sources
        filelist = (f for f in self.edam['files'] if 'file_type' in f and f['file_type'].find('erilogSource') > 0)
        for f in filelist:
            fname = f['name']

            verilog_defines = []
            for key, value in self.vlogdefine.items():
                verilog_defines.append("{{{key} {value}}}".format(key=key, value=value))

            verilog_params = []
            for key, value in self.vlogparam.items():
                if type(value) is str:
                    value = '{"' + value + '"}'
                verilog_params.append(
                    r"chparam -set {} {} {}".format(key, self._param_value_str(value), self.toplevel)
                )
            file_table = ['read_systemverilog -defer {' + f['name'] + '}']
            # TODO add include dirs?
            arch = self.tool_options.get('arch', None)
            if not arch:
                logger.error("ERROR: arch is not defined.")
            plugins = ['systemverilog']

            template_vars = {
                "verilog_defines": "{" + " ".join(verilog_defines) + "}",
                "verilog_params": "\n".join(verilog_params),
                "file_table": "\n".join(file_table),
                "incdirs": "",
                "top": self.toplevel,
                "name": self.name,
                'plugins': "plugin -i %s \n"*len(plugins) % tuple(plugins)
            }
            tcl_script = f['name'] + '.tcl'
            self.render_template(
                "yosys_separate_tests.tcl.j2", tcl_script, template_vars
            )
            commands.add(
                ["yosys", "-l", "yosys.log", "-p", f"'tcl {tcl_script}'"],
                [default_target],
                [tcl_script],
        )
        commands.set_default_target(f"{self.name}")
        commands.write(os.path.join(self.work_root, "Makefile"))
