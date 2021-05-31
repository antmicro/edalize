# Copyright edalize contributors
# Licensed under the 2-Clause BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-2-Clause

import logging
import multiprocessing
import os
import logging

from edalize.edatool import Edatool

logger = logging.getLogger(__name__)

class Verilator(Edatool):

    argtypes = ['cmdlinearg', 'plusarg', 'vlogdefine', 'vlogparam']

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            return {'description' : "Verilator is the fastest free Verilog HDL simulator, and outperforms most commercial simulators",
                    'members' : [
                        {'name' : 'mode',
                         'type' : 'String',
                         'desc' : 'Select compilation mode. Legal values are *cc* for C++ testbenches, *sc* for SystemC testbenches or *lint-only* to only perform linting on the Verilog code'},
                        {'name' : 'cli_parser',
                         'type' : 'String',
                         'desc' : '**Deprecated: Use run_options instead** : Select whether FuseSoC should handle command-line arguments (*managed*) or if they should be passed directly to the verilated model (*raw*). Default is *managed*'}],
                    'lists' : [
                        {'name' : 'libs',
                         'type' : 'String',
                         'desc' : 'Extra libraries for the verilated model to link against'},
                        {'name' : 'verilator_options',
                         'type' : 'String',
                         'desc' : 'Additional options for verilator'},
                        {'name' : 'make_options',
                         'type' : 'String',
                         'desc' : 'Additional arguments passed to make when compiling the simulation. This is commonly used to set OPT/OPT_FAST/OPT_SLOW.'},
                        {'name' : 'run_options',
                         'type' : 'String',
                         'desc' : 'Additional arguments directly passed to the verilated model'},
                        ]}

    def check_managed_parser(self):
        managed = 'cli_parser' not in self.tool_options or self.tool_options['cli_parser'] == 'managed'
        if not managed:
            logger.warning("The cli_parser argument is deprecated. Use run_options to pass raw arguments to verilated models")

    def configure_main(self):
        self.check_managed_parser()
        if not self.toplevel:
            raise RuntimeError("'" + self.name + "' miss a mandatory parameter 'top_module'")

        self._write_config_files()

    def _write_config_files(self):
        #Future improvement: Separate include directories of c and verilog files
        incdirs = set()
        src_files = []

        (src_files, incdirs) = self._get_fileset_files(force_slash=True)

        self.verilator_file = self.name + '.vc'

        with open(os.path.join(self.work_root,self.verilator_file),'w') as f:
            f.write('--Mdir .\n')
            modes = ['sc', 'cc', 'lint-only']

            #Default to cc mode if not specified
            if not 'mode' in self.tool_options:
                self.tool_options['mode'] = 'cc'

            if self.tool_options['mode'] in modes:
                f.write('--'+self.tool_options['mode']+'\n')
            else:
                _s = "Illegal verilator mode {}. Allowed values are {}"
                raise RuntimeError(_s.format(self.tool_options['mode'],
                                             ', '.join(modes)))
            if 'libs' in self.tool_options:
                for lib in self.tool_options['libs']:
                    f.write('-LDFLAGS {}\n'.format(lib))
            for include_dir in incdirs:
                f.write("+incdir+" + include_dir + '\n')
                f.write("-CFLAGS -I{}\n".format(include_dir))
            vlt_files = []
            vlog_files = []
            opt_c_files = []
            for src_file in src_files:
                if src_file.file_type.startswith("systemVerilogSource") or src_file.file_type.startswith("verilogSource"):
                    vlog_files.append(src_file.name)
                elif src_file.file_type in ['cppSource', 'systemCSource', 'cSource']:
                    opt_c_files.append(src_file.name)
                elif src_file.file_type == 'vlt':
                    vlt_files.append(src_file.name)
                elif src_file.file_type == 'user':
                    pass

            if vlt_files:
                f.write('\n'.join(vlt_files) + '\n')
            f.write('\n'.join(vlog_files) + '\n')
            f.write('--top-module {}\n'.format(self.toplevel))
            f.write('--exe\n')
            f.write('\n'.join(opt_c_files))
            f.write('\n')
            f.write(''.join(['-G{}={}\n'.format(key, self._param_value_str(value, str_quote_style='\\"')) for key, value in self.vlogparam.items()]))
            f.write(''.join(['-D{}={}\n'.format(key, self._param_value_str(value)) for key, value in self.vlogdefine.items()]))

        self.render_template('verilator-makefile.j2',
                             'Makefile')

        if 'verilator_options' in self.tool_options:
            verilator_options = ' '.join(self.tool_options['verilator_options'])
        else:
            verilator_options = ''

        if 'make_options' in self.tool_options:
            make_options = ' '.join(self.tool_options['make_options'])
        else:
            make_options = ''

        self.render_template('verilator-config.j2',
                             'config.mk',
                             {
                                'top_module'        : self.toplevel,
                                'vc_file'           : self.verilator_file,
                                'verilator_options' : verilator_options,
                                'make_options'      : make_options
                             })

    def build_main(self):
        logger.info("Building simulation model")
        if not 'mode' in self.tool_options:
            self.tool_options['mode'] = 'cc'

        # Do parallel builds with <number of cpus> * 2 jobs.
        make_job_count = multiprocessing.cpu_count() * 2
        args = ['-j', str(make_job_count)]

        if self.tool_options['mode'] == 'lint-only':
            args.append('V'+self.toplevel+'.mk')
        _s = os.path.join(self.work_root, 'verilator.{}.log')
        self._run_tool('make', args, quiet=True)

    def run_main(self):
        self.check_managed_parser()
        self.args = []
        for key, value in self.plusarg.items():
            self.args += ['+{}={}'.format(key, self._param_value_str(value))]
        for key, value in self.cmdlinearg.items():
            self.args += ['--{}={}'.format(key, self._param_value_str(value))]

        self.args += self.tool_options.get('run_options', [])

        #Default to cc mode if not specified
        if not 'mode' in self.tool_options:
            self.tool_options['mode'] = 'cc'
        if self.tool_options['mode'] == 'lint-only':
            return
        logger.info("Running simulation")
        self._run_tool('./V' + self.toplevel, self.args)
