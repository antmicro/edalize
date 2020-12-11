import logging
import os.path

from edalize.edatool import Edatool

logger = logging.getLogger(__name__)

class Surelog(Edatool):

    argtypes = ['vlogdefine', 'vlogparam']

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            return {'description' : "Surelog",
                    'lists' : [
                        {'name' : 'library_files',
                         'type' : 'String',
                         'desc' : 'List of the library files for Surelog'},
                        ]}

    def configure_main(self):
        (src_files, incdirs) = self._get_fileset_files()
        file_list = []
        for f in src_files:
            if f.file_type in ['verilogSource']:
                file_list.append(f.name)
            if f.file_type in ['systemVerilogSource']:
                file_list.append(f.name)

        library_files = self.tool_options.get('library_files', [])
        library_command = ""

        for library_file in library_files:
            library_command = library_command + " -v " + library_file

        verilog_params_command = ""
        for key, value in self.vlogparam.items():
            verilog_params_command = verilog_params_command + " -P" + key + '=' + value

        include_files = self.tool_options.get('include_files', [])
        include_files_command = ""

        for include_file in incdirs:
            include_files_command = include_files_command + " -I" + include_file

        template_vars = {
                'top'                       : self.toplevel,
                'name'                      : self.name,
                'sources'                   : ' '.join(file_list),
                'library_command'           : library_command,
                'verilog_params_command'    : verilog_params_command,
                'include_files_command'     : include_files_command,
        }


        self.render_template('surelog-makefile.j2',
                             'surelog.mk',
                             template_vars)
