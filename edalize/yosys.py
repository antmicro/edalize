import logging
import os.path

from edalize.edatool import Edatool
from edalize.surelog import Surelog
from importlib import import_module

logger = logging.getLogger(__name__)

class Yosys(Edatool):

    argtypes = ['vlogdefine', 'vlogparam']

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            return {'description' : "Open source synthesis tool targeting many different FPGAs",
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
                        {'name' : 'script_name',
                         'type' : 'String',
                         'desc' : 'Generated tcl script filename, defaults to $name.mk'},
                        ],
                    'lists' : [
                        {'name' : 'yosys_read_options',
                         'type' : 'String',
                         'desc' : 'Addtional options for the read_* command (e.g. read_verlog or read_uhdm)'},
                        {'name' : 'yosys_synth_options',
                         'type' : 'String',
                         'desc' : 'Additional options for the synth command'},
                        {'name' : 'library_files',
                         'type' : 'String',
                         'desc' : 'List of the library files for Surelog'},
                        {'name' : 'surelog_options',
                         'type' : 'String',
                         'desc' : 'Additional options for the Surelog'},
                        ]}

    def configure_main(self):
        # write Yosys tcl script file
        (src_files, incdirs) = self._get_fileset_files()
        part_of_toolchain = self.tool_options.get('yosys_as_subtool', False)

        yosys_read_options = " ".join(self.tool_options.get('yosys_read_options', []))
        file_table = []
        yosys_synth_options = self.tool_options.get('yosys_synth_options', [])
        use_surelog = False
        if "frontend=surelog" in yosys_synth_options:
            use_surelog = True
            yosys_synth_options.remove("frontend=surelog")
        if use_surelog:
            surelog_edam = {
                    'files'         : self.files,
                    'name'          : self.name,
                    'toplevel'      : self.toplevel,
                    'parameters'    : self.parameters,
                    'tool_options'  : {'surelog' : {
                                            'library_files' : self.tool_options.get('library_files', []),
                                            'surelog_options' : self.tool_options.get('surelog_options', []),
                                            }
                                    }
                    }

            surelog = getattr(import_module("edalize.surelog"), 'Surelog')(surelog_edam, self.work_root)
            surelog.configure()
            self.vlogparam.clear() # vlogparams are handled by Surelog
            self.vlogdefine.clear() # vlogdefines are handled by Surelog
            file_table.append('read_uhdm ' + yosys_read_options + ' {' + os.path.abspath(self.work_root + '/' + self.toplevel + '.uhdm') + '}')
        else:
            for f in src_files:
                cmd = ""
                if f.file_type.startswith('verilogSource'):
                    cmd = 'read_verilog'
                elif f.file_type.startswith('systemVerilogSource'):
                    cmd = 'read_verilog -sv'
                elif f.file_type == 'tclSource':
                    cmd = 'source'
                else:
                    continue

                file_table.append(cmd + ' ' + yosys_read_options + ' {' + f.name + '}')

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
        arch = self.tool_options.get('arch', None)

        if not arch:
            logger.error("ERROR: arch is not defined.")

        makefile_name = self.tool_options.get('makefile_name', self.name + '.mk')
        script_name = self. tool_options.get('script_name', self.name + '.tcl')
        template_vars = {
                'verilog_defines'     : "{" + " ".join(verilog_defines) + "}",
                'verilog_params'      : "\n".join(verilog_params),
                'file_table'          : "\n".join(file_table),
                'incdirs'             : ' '.join(['-I'+d for d in incdirs]),
                'top'                 : self.toplevel,
                'synth_command'       : "synth_" + arch,
                'synth_options'       : " ".join(yosys_synth_options),
                'write_command'       : "write_" + output_format,
                'default_target'      : output_format,
                'edif_opts'           : '-pvector bra' if arch=='xilinx' else '',
                'script_name'         : script_name,
                'name'                : self.name,
                'use_surelog'         : use_surelog,
        }

        self.render_template('yosys-script-tcl.j2',
                             script_name,
                             template_vars)

        makefile_name = self.name + '.mk' if part_of_toolchain else 'Makefile'
        self.render_template('yosys-makefile.j2',
                             makefile_name,
                             template_vars)

