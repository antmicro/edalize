# Copyright edalize contributors
# Licensed under the 2-Clause BSD License, see LICENSE for details.
# SPDX-License-Identifier: BSD-2-Clause

import os.path

from edalize.edatool import Edatool
from edalize.nextpnr import Nextpnr
from edalize.yosys import Yosys

class Trellis(Edatool):

    argtypes = ['vlogdefine', 'vlogparam']

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            yosys_help = Yosys.get_doc(api_ver)
            trellis_help = {
                    'lists' : [
                        {'name' : 'nextpnr_options',
                         'type' : 'String',
                         'desc' : 'Additional options for nextpnr'},
                        {'name' : 'yosys_synth_options',
                         'type' : 'String',
                         'desc' : 'Additional options for the synth_ecp5 command'},
                        {'name' : 'yosys_read_options',
                         'type' : 'String',
                         'desc' : 'Addtional options for the read_* command (e.g. read_verlog or read_uhdm)'},
                        {'name' : 'frontend_options',
                         'type' : 'String',
                         'desc' : 'Additional options for the Yosys frontend'},
                        ]}

            Edatool._extend_options(options, Yosys)
            Edatool._extend_options(options, Nextpnr)

            return {'description' : "Project Trellis enables a fully open-source flow for ECP5 FPGAs using Yosys for Verilog synthesis and nextpnr for place and route",
                    'members' : options['members'],
                    'lists'   : options['lists']}

    def configure_main(self):
        # Write yosys script file
        (src_files, incdirs)  = self._get_fileset_files()
        yosys_synth_options   = self.tool_options.get('yosys_synth_options', [])
        yosys_read_options    = self.tool_options.get('yosys_read_options', [])
        yosys_synth_options   = ["-nomux"] + yosys_synth_options
        frontend_options      = self.tool_options.get('frontend_options', [])
        yosys_edam = {
                'files'         : self.files,
                'name'          : self.name,
                'toplevel'      : self.toplevel,
                'parameters'    : self.parameters,
                'tool_options'  : {'yosys' : {
                                        'arch' : 'ecp5',
                                        'yosys_synth_options' : yosys_synth_options,
                                        'yosys_read_options' : yosys_read_options,
                                        'yosys_as_subtool' : True,
                                        'frontend_options' : frontend_options,
                                        }
                                }
                }

        # Write Makefile
        commands = self.EdaCommands()
        commands.commands = yosys.commands

        commands.commands += nextpnr.commands

        #Image generation
        depends = self.name+'.config'
        targets = self.name+'.bit'
        command = ['ecppack', '--svf', self.name+'.svf', depends, targets]
        commands.add(command, [targets], [depends])

        commands.set_default_target(self.name+'.bit')
        commands.write(os.path.join(self.work_root, 'Makefile'))
