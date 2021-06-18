import logging
import os.path
import subprocess

from edalize.edatool import Edatool

logger = logging.getLogger(__name__)

class Surelog(Edatool):

    argtypes = ['vlogdefine', 'vlogparam']

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            return {'description' : "Surelog",
                    'members' : [
                        {'name' : 'arch',
                         'type' : 'String',
                         'desc' : 'Target architecture. Legal values are *xilinx*, *ice40* and *ecp5*'},
                        {'name' : 'surelog_as_subtool',
                         'type' : 'bool',
                         'desc' : 'Determines if surelog is run as a part of bigger toolchain, or as a standalone tool'},
                        {'name' : 'makefile_name',
                         'type' : 'String',
                         'desc' : 'Generated makefile name, defaults to $name.mk'},
                        {'name' : 'library_files',
                         'type' : 'String',
                         'desc' : 'List of the library files for Surelog'},
                        ],
                    'lists' : [
                        {'name' : 'surelog_options',
                         'type' : 'String',
                         'desc' : 'List of the Surelog parameters'},
                        ]}

    def configure_main(self):
        incdirs = []
        file_table = []
        unused_files = []
        for f in self.files:
            src = ""
            if f.get('file_type', '').startswith('verilogSource'):
                src = f['name']
            elif f.get('file_type', '').startswith('systemVerilogSource'):
                src = '-sv ' + f['name']

            if src != "":
                if not self._add_include_dir(f, incdirs):
                    file_table.append(src)
            else:
                unused_files.append(f)
        
        self.edam['files'] = unused_files
        of = [
            {'name' : self.toplevel+'.uhdm', 'file_type' : 'uhdm'},
        ]
        self.edam['files'] += of

        surelog_options = self.tool_options.get('surelog_options', [])

        arch = self.tool_options.get('arch', None)

        library_files = self.tool_options.get('library_files', None)

        pattern = len(self.vlogparam.keys()) * " -P%s=%%s"
        verilog_params_command = pattern % tuple(self.vlogparam.keys()) % tuple(self.vlogparam.values())

        verilog_defines_command = "+define" if self.vlogdefine.items() else ""
        pattern = len(self.vlogdefine.keys()) * "+%s=%%s"
        verilog_defines_command += pattern % tuple(self.vlogdefine.keys()) % tuple(self.vlogdefine.values())

        pattern = len(incdirs) * " -I%s"
        include_files_command = pattern % tuple(incdirs)

        yosys_conf_out = subprocess.run(['yosys-config', '--datdir'],
                        capture_output=True)
        yosys_conf_path = yosys_conf_out.stdout.decode('ascii').strip()
        library_command = []
        if library_files:
            library_files = library_files.split(",")
            pattern = len(library_files) * " -v %s"
            library_command = pattern % tuple(library_files)
        else:
            if arch in ['ecp5', 'ice40']:
                library_command = ['-v', yosys_conf_path+'/'+arch+'/cells_bb.v']
            else:
                library_command = ['-v', yosys_conf_path+'/'+arch+'/cells_xtra_surelog.v', '-v', yosys_conf_path+'/'+arch+'/cells_sim.v']
        
        commands = self.EdaCommands()
        depends = ''
        target = self.toplevel+'_build'
        command = ['surelog', ' '.join(surelog_options), '-parse', library_command,
                verilog_defines_command, verilog_params_command,
                include_files_command, ' '.join(file_table)]
        commands.add(command, [target], [depends])
        default_target = self.toplevel+'.uhdm'

        depends = self.toplevel+'_build'
        target = default_target
        command = ['cp', 'slpp_all/surelog.uhdm', self.toplevel+'.uhdm']
        commands.add(command, [target], [depends])

        commands.set_default_target(default_target)

        if self.tool_options.get('surelog_as_subtool'):
            self.commands = commands.commands

            commands.write(os.path.join(self.work_root, "surelog.mk"))
        else:
            commands.write(os.path.join(self.work_root, 'Makefile'))
