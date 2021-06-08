import logging
import os.path

from edalize.edatool import Edatool

logger = logging.getLogger(__name__)

class Sv2v(Edatool):

    argtypes = ['vlogdefine', 'vlogparam']

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            return {'description' : "Sv2v",
                    'members' : [
                        {'name' : 'sv2v_as_subtool',
                         'type' : 'bool',
                         'desc' : 'Determines if sv2v is run as a part of bigger toolchain, or as a standalone tool'},
                        {'name' : 'makefile_name',
                         'type' : 'String',
                         'desc' : 'Generated makefile name, defaults to $name.mk'},
                        ],
                    'lists' : [
                        {'name' : 'sv2v_options',
                         'type' : 'String',
                         'desc' : 'List of the sv2v parameters'},
                        ]}

    def configure_main(self):
        incdirs = []
        file_table = []
        unused_files = []

        for f in self.files:
            src = ""
            if f.get('file_type', '').startswith('systemVerilogSource'):
                src = f['name']

            if src:
                if not self._add_include_dir(f, incdirs):
                    file_table.append(src)
            else:
                unused_files.append(f)

        self.edam['files'] = unused_files
        of = [
            {'name' : name+'.v', 'file_type' : 'verilogSource'} for name in file_table
        ]
        self.edam['files'] += of

        pattern = len(self.vlogdefine.keys()) * "-D%s=%%s "
        verilog_defines_command = pattern % tuple(self.vlogdefine.keys()) % tuple(self.vlogdefine.values())

        sv2v_options = self.tool_options.get('sv2v_options', [])

        sv2v_options = ' '.join(sv2v_options) + " " + verilog_defines_command
        incdirs = ' '.join(['--incdir='+d for d in incdirs])
        sv_sources = ' '.join(file_table)

        commands = self.EdaCommands()
        commands.set_default_target(self.name)
        depends = []
        targets = [self.name]
        command = ['sv2s' , sv2v_options, incdirs, sv_sources]
        commands.add(command, [depends], [targets])

        if self.tool_options.get('sv2v_as_subtool'):
            self.commands = commands.commands

            commands.write(os.path.join(self.work_root, "sv2v.mk"))
        else:
            commands.write(os.path.join(self.work_root, 'Makefile'))
