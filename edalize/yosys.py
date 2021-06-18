# Copyright edalize contributors
# Licensed under the 2-Clause BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-2-Clause

import logging
import os.path

from edalize.edatool import Edatool
from edalize.surelog import Surelog
from edalize.sv2v import Sv2v
from importlib import import_module

logger = logging.getLogger(__name__)

class Yosys(Edatool):

    argtypes = ['vlogdefine', 'vlogparam']

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            options = {
                    'members' : [
                        {'name' : 'arch',
                         'type' : 'String',
                         'desc' : 'Target architecture. Legal values are *xilinx*, *ice40* and *ecp5*'},
                        {'name' : 'output_format',
                         'type' : 'String',
                         'desc' : 'Output file format. Legal values are *json*, *edif*, *blif*'},
                        {'name' : 'yosys_as_subtool',
                         'type' : 'bool',
                         'desc' : 'Determines if Yosys is run as a part of bigger toolchain, or as a standalone tool'},
                        {'name' : 'makefile_name',
                         'type' : 'String',
                         'desc' : 'Generated makefile name, defaults to $name.mk'},
                        {'name' : 'yosys_template',
                         'type' : 'String',
                         'desc' : 'TCL template file to use instead of default template'},
                        {'name' : 'library_files',
                         'type' : 'String',
                         'desc' : 'List of the library files for Surelog'},
                        ],
                    'lists' : [
                        {'name' : 'yosys_read_options',
                         'type' : 'String',
                         'desc' : 'Addtional options for the read_* command (e.g. read_verlog or read_uhdm)'},
                        {'name' : 'yosys_synth_options',
                         'type' : 'String',
                         'desc' : 'Additional options for the synth command'},
                        ]

                    }
            Edatool._extend_options(options, Surelog)
            Edatool._extend_options(options, Sv2v)

            return {'description' : "Open source synthesis tool targeting many different FPGAs",
                    'members' : options['members'],
                    'lists' : options['lists']}

    def configure_main(self):
        # write Yosys tcl script file

        yosys_template = self.tool_options.get('yosys_template')
        yosys_read_options = " ".join(self.tool_options.get('yosys_read_options', []))

        arch = self.tool_options.get('arch', None)
        if not arch:
            logger.error("ERROR: arch is not defined.")

        self.edam['tool_options'] = \
            {'surelog' : {
                'arch' : arch,
                'surelog_options' : self.tool_options.get('surelog_options', []),
                'library_files' : self.tool_options.get('library_files', []),
                'surelog_as_subtool' : True,
            },
             'sv2v' : {
                'sv2v_options' : self.tool_options.get('surelog_options', []),
                'sv2v_as_subtool' : True,
            },
            }
        yosys_synth_options = self.tool_options.get('yosys_synth_options', [])
        use_surelog = False
        use_sv2v = False

        if "frontend=surelog" in yosys_synth_options:
            use_surelog = True
            yosys_synth_options.remove("frontend=surelog")
        elif "frontend=sv2v" in yosys_synth_options:
            use_sv2v = True
            yosys_synth_options.remove("frontend=sv2v")

        if use_surelog:
            surelog = Surelog(self.edam, self.work_root)
            surelog.configure()
            self.vlogparam.clear() # vlogparams are handled by Surelog
            self.vlogdefine.clear() # vlogdefines are handled by Surelog
        elif use_sv2v:
            sv2v = Sv2v(self.edam, self.work_root)
            sv2v.configure()

        incdirs = []
        file_table = []
        unused_files = []
        sv_files = []
        for f in self.edam['files']:
            cmd = ""
            if f.get('file_type','').startswith('verilogSource'):
                cmd = 'read_verilog '
            elif f.get('file_type','').startswith('systemVerilogSource'):
                cmd = 'read_verilog -sv '
                sv_files += [os.path.splitext(f['name'])[0] + ".v"]
            elif f.get('file_type','') == 'tclSource':
                cmd = 'source '
            elif f.get('file_type','') == 'uhdm':
                cmd = 'read_uhdm '

            if cmd:
                if not self._add_include_dir(f, incdirs):
                    file_table.append(cmd + yosys_read_options + ' {' + f['name'] + '}')
            else:
                unused_files.append(f)

        self.edam['files'] = unused_files
        of = [
            {'name' : self.name+'.blif', 'file_type' : 'blif'},
            {'name' : self.name+'.edif', 'file_type' : 'edif'},
            {'name' : self.name+'.json', 'file_type' : 'jsonNetlist'},
        ]
        self.edam['files'] += of


        verilog_defines = []
        for key, value in self.vlogdefine.items():
            verilog_defines.append('{{{key} {value}}}'.format(key=key, value=value))

        verilog_params = []
        for key, value in self.vlogparam.items():
            if type(value) is str:
                value = "{\"" + value + "\"}"
            _s = r"chparam -set {} {} {}"
            verilog_params.append(_s.format(key,
                self._param_value_str(value),
                self.toplevel))


        output_format = self.tool_options.get('output_format', 'blif')

        template = yosys_template or 'edalize_yosys_template.tcl'
        template_vars = {
                'verilog_defines'     : "{" + " ".join(verilog_defines) + "}",
                'verilog_params'      : "\n".join(verilog_params),
                'file_table'          : "\n".join(file_table),
                'incdirs'             : ' '.join(['-I'+d for d in incdirs]),
                'top'                 : self.toplevel,
                'synth_command'       : "synth_" + arch,
                'synth_options'       : " ".join(self.tool_options.get('yosys_synth_options', '')),
                'write_command'       : "write_" + output_format,
                'default_target'      : output_format,
                'edif_opts'           : '-pvector bra' if arch=='xilinx' else '',
                'yosys_template'      : yosys_template or 'edalize_yosys_template.tcl',
                'name'                : self.name,
                'use_surelog'         : use_surelog,
                'use_sv2v'            : use_sv2v,
        }
        self.render_template('edalize_yosys_procs.tcl.j2',
                             'edalize_yosys_procs.tcl',
                             template_vars)

        if not yosys_template:
            self.render_template('yosys-script-tcl.j2',
                                 'edalize_yosys_template.tcl',
                                 template_vars)

        commands = self.EdaCommands()
        additional_deps = []
        if use_surelog:
            commands.commands += surelog.commands
            additional_deps = self.toplevel + '.uhdm'
        elif use_sv2v:
            commands.commands += sv2v.commands
            additional_deps = sv_files

        commands.add(['yosys', '-l', 'yosys.log', '-p', f'"tcl {template}"'],
                         [f'{self.name}.{output}' for output in ['blif', 'json','edif']],
                         [template, additional_deps])
        if self.tool_options.get('yosys_as_subtool'):
            self.commands = commands.commands
        else:
            commands.set_default_target(f'{self.name}.{output_format}')
            commands.write(os.path.join(self.work_root, 'Makefile'))
