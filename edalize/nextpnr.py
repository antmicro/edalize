import os.path

from edalize.edatool import Edatool
from edalize.yosys import Yosys
from importlib import import_module

class Nextpnr(Edatool):

    argtypes = []
    archs = ['xilinx', 'fpga_interchange']
    families = ['xc7']

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            yosys_help = Yosys.get_doc(api_ver)
            nextpnr_help = {
                    'members' : [
                        {'name' : 'arch',
                         'type' : 'String',
                         'desc' : 'Target architecture. Legal values are *xilinx*'},
                        {'name' : 'output_format',
                         'type' : 'String',
                         'desc' : 'Output file format. Legal values are *fasm*'},
                        {'name' : 'nextpnr_as_subtool',
                         'type' : 'bool',
                         'desc' : 'Determines if nextpnr is run as a part of bigger toolchain, or as a standalone tool'},
                        ],
                    'lists' : [
                        {'name' : 'nextpnr_impl_options',
                         'type' : 'String',
                         'desc' : 'Additional options for the implementation command'},
                        ]}

            combined_members = nextpnr_help['members']
            combined_lists = nextpnr_help.get('lists', [])
            yosys_members = yosys_help['members']
            yosys_lists = yosys_help['lists']

            combined_members.extend(m for m in yosys_members if m['name'] not in [i['name'] for i in combined_members])
            combined_lists.extend(l for l in yosys_lists if l['name'] not in [i['name'] for i in combined_lists])

            return {'description' : "Open source Place and Route tool targeting many different FPGAs",
                    'members': combined_members,
                    'lists': combined_lists}

    @classmethod
    def validate_args(cls, args):
        nextpnr_help = cls.get_doc(0)
        nextpnr_members = nextpnr_help['members']
        nextpnr_lists = nextpnr_help['lists']

        nextpnr_args = []
        nextpnr_args.append(a['name'] for a in nextpnr_members)
        nextpnr_args.append(a['name'] for a in nextpnr_lists)

        for arg in args:
            if not arg.startswith('-'):
                continue
            argname = arg.strip('-')
            if argname not in nextpnr_args:
                raise Exception(f'Unknown command line option {arg}')

    def check_args(self, unknown):
        part_of_toolchain = self.tool_options.get('nextpnr_as_subtool', False)
        if part_of_toolchain is False:
            super().check_args(unknown)
        else:
            # we assume the calling tool will handle parameter check
            pass


    def configure_main(self):
        (src_files, incdirs) = self._get_fileset_files()

        yosys_synth_options = self.tool_options.get('yosys_synth_options', '')
        yosys_additional_commands = self.tool_options.get('yosys_additional_commands', '')
        yosys_edam = {
                'files'         : self.files,
                'name'          : self.name,
                'toplevel'      : self.toplevel,
                'parameters'    : self.parameters,
                'tool_options'  : {'yosys' : {
                                        'arch' : 'xilinx',
                                        'yosys_synth_options' : yosys_synth_options,
                                        'yosys_additional_commands' : yosys_additional_commands,
                                        'yosys_as_subtool' : True,
                                        }
                                }
                }

        yosys = getattr(import_module("edalize.yosys"), 'Yosys')(yosys_edam, self.work_root)
        yosys.configure(self.args)

        part_of_toolchain = self.tool_options.get('nextpnr_as_subtool', False)

        file_table = []

        output_format = self.tool_options.get('output_format', 'fasm')
        arch = self.tool_options.get('arch')

        assert arch in getattr(self, 'archs'), 'Missing or invalid "arch" parameter in "tool_options"'

        synth_design = None
        chipdb = None
        device = None
        xdc = None

        for f in src_files:
            if f.file_type in ['synthJson']:
                synth_design = f.name
            elif f.file_type in ['bba']:
                chipdb = f.name
            elif f.file_type in ['device']:
                device = f.name
            elif f.file_type in ['xdc']:
                xdc = f.name
            else:
                continue

        assert chipdb and xdc, "Missing required files."
        assert device is not None or arch is not 'fpga_interchange', 'Missing required ".device" file for "fpga_interchange" arch'

        additional_options = self.tool_options.get('nextpnr_impl_options', '')
        package = self.tool_options.get('package', None)

        assert package is not None or arch is not 'fpga_interchange', 'Missing required "package" parameter for "fpga_interchange" arch'

        package = package.split('-')[0] if arch == "fpga_interchange" else None

        family = self.tool_options.get('family', None)

        assert family is not None or arch is not 'fpga_interchange', 'Missing required "family" parameter for "fpga_interchange" arch'
        assert family in getattr(self, 'families') or arch is not 'fpga_interchange', 'Unsupported family: {}'.format(family)

        schema_dir = self.tool_options.get('schema_dir', None)
        assert schema_dir is not None or arch is not 'fpga_interchange', 'Missing required "schema_dir" parameter for "fpga_interchange" arch'

        template_vars = {
                'toplevel'          : self.toplevel,
                'arch'              : arch,
                'chipdb'            : chipdb,
                'device'            : device,
                'constr'            : xdc,
                'default_target'    : output_format,
                'name'              : self.name,
                'package'           : package,
                'family'            : family,
                'schema_dir'        : schema_dir,
                'additional_options': additional_options,
        }

        makefile_name = self.name + '-nextpnr.mk' if part_of_toolchain else 'Makefile'
        self.render_template('nextpnr-{}-makefile.j2'.format(arch),
                             makefile_name,
                             template_vars)

