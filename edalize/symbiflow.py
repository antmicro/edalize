import logging
import os.path
import platform
import re
import subprocess

from edalize.edatool import Edatool
from edalize.yosys import Yosys
from importlib import import_module

logger = logging.getLogger(__name__)

""" Symbiflow backtend

A core (usually the system core) can add the following files:

- Standard design sources (Verilog only)

- Constraints: unmanaged constraints with file_type SDC, pin_constraints with file_type PCF and placement constraints with file_type xdc

"""

class Symbiflow(Edatool):

    argtypes = ['vlogdefine', 'vlogparam', 'generic']
    archs = ['xilinx', 'fpga_interchange']
    families = ['xc7']

    @classmethod
    def get_doc(cls, api_ver):
        if api_ver == 0:
            symbiflow_help = {
                    'members' : [
                        {'name' : 'package',
                         'type' : 'String',
                         'desc' : 'FPGA chip package (e.g. clg400-1)'},
                        {'name' : 'part',
                         'type' : 'String',
                         'desc' : 'FPGA part type (e.g. xc7a50t)'},
                        {'name' : 'builddir',
                         'type' : 'String',
                         'desc' : 'directory where all the intermediate files will be stored (default "build")'},
                        {'name' : 'vendor',
                         'type' : 'String',
                         'desc' : 'Target architecture. Currently only "xilinx" is supported'},
                        {'name' : 'pnr',
                         'type' : 'String',
                         'desc' : 'Place and Route tool. Currently only "vpr" and "nextpnr" are supported'},
                        {'name' : 'options',
                         'type' : 'String',
                         'desc' : 'Tool options. If not used, default options for the tool will be used'},
                        {'name' : 'fasm2bels',
                         'type' : 'Boolean',
                         'desc' : 'Value to state whether fasm2bels is to be used.'},
                        {'name' : 'dbroot',
                         'type' : 'String',
                         'desc' : 'Path to the database root (needed by fasm2bels).'},
                        {'name' : 'clocks',
                         'type' : 'dict',
                         'desc' : 'Clocks to be added for having tools correctly handling timing based routing.'},
                        {'name' : 'seed',
                         'type' : 'String',
                         'desc' : 'Seed assigned to the PnR tool.'},
                        {'name' : 'environment_script',
                         'type' : 'String',
                         'desc' : 'Optional bash script that will be sourced before each build step.'},
                    ]}

            symbiflow_members = symbiflow_help['members']

            return {'description' : "The Symbilow backend executes Yosys sythesis tool and VPR place and route. It can target multiple different FPGA vendors",
                    'members': symbiflow_members}

    def get_version(self):
        return "1.0"

    def configure_nextpnr(self):
        (src_files, incdirs) = self._get_fileset_files(force_slash=True)

        yosys_synth_options = self.tool_options.get('yosys_synth_options', '')
        yosys_additional_commands = self.tool_options.get('yosys_additional_commands', '')
        nextpnr_impl_options = self.tool_options.get('options', '')
        arch = self.tool_options.get('arch')

        assert arch in getattr(self, 'archs'), 'Missing or invalid "arch" parameter: {} in "tool_options"'.format(arch)

        package = self.tool_options.get('package', None)
        assert package is not None, 'Missing required "package" parameter'

        schema_dir = self.tool_options.get('schema_dir', None)
        assert schema_dir is not None or arch is not 'fpga_interchange', 'Missing required "schema_dir" parameter for "fpga_interchange" arch'

        part = self.tool_options.get('part', None)

        assert part is not None, 'Missing required "part" parameter'

        target_family = None
        for family in getattr(self, 'families'):
            if family in part:
                target_family = family
                break

        assert target_family is not None or arch is not "fpga_interchange", "Couldn't find family for part: {}. Available families: {}".format(part, ", ".join(getattr(self, 'families')))

        nextpnr_edam = {
                'files'         : self.files,
                'name'          : self.name,
                'toplevel'      : self.toplevel,
                'tool_options'  : {'nextpnr' : {
                                        'arch' : arch,
                                        'yosys_synth_options' : yosys_synth_options,
                                        'yosys_additional_commands' : yosys_additional_commands,
                                        'nextpnr_impl_options' : nextpnr_impl_options,
                                        'nextpnr_as_subtool' : True,
                                        'package' : package,
                                        'family' : target_family,
                                        'schema_dir' : schema_dir,
                                        }

                                }
                }

        nextpnr = getattr(import_module("edalize.nextpnr"), 'Nextpnr')(nextpnr_edam, self.work_root)
        nextpnr.configure(self.args)

        builddir = self.tool_options.get('builddir', 'build')

        partname = part + package

        if 'xc7a' in part:
            bitstream_device = 'artix7'
        if 'xc7z' in part:
            bitstream_device = 'zynq7'
        if 'xc7k' in part:
            bitstream_device = 'kintex7'

        placement_constraints = None
        pins_constraints = None
        rr_graph = None
        vpr_grid = None
        vpr_capnp_schema = None
        for f in src_files:
            if f.file_type in ['PCF']:
                pins_constraints = f.name
            if f.file_type in ['xdc']:
                placement_constraints = f.name
            if f.file_type in ['RRGraph']:
                rr_graph = f.name
            if f.file_type in ['VPRGrid']:
                vpr_grid = f.name
            if f.file_type in ['capnp']:
                vpr_capnp_schema = f.name

        fasm2bels = self.tool_options.get('fasm2bels', False)
        dbroot = self.tool_options.get('dbroot', None)
        clocks = self.tool_options.get('clocks', None)

        if fasm2bels:
            if any(v is None for v in [rr_graph, vpr_grid, dbroot]):
                logger.error("When using fasm2bels, rr_graph, vpr_grid and database root must be provided")

            tcl_params = {
                'top': self.name,
                'part': partname,
                'xdc': placement_constraints,
                'clocks': clocks,
            }

            self.render_template('symbiflow-fasm2bels-tcl.j2',
                                 'fasm2bels.tcl',
                                 tcl_params)

            self.render_template('vivado-sh.j2',
                                 'vivado.sh',
                                 dict())

        vendor = self.tool_options.get('vendor', None)


        # Optional script that will be sourced right before executing each build step in Makefile
        # This script can for example setup enviroment variables or conda enviroment.
        # This file needs to be a bash file
        environment_script = self.tool_options.get('environment_script', None)

        makefile_params = {
                'top' : self.name,
                'partname' : partname,
                'bitstream_device' : bitstream_device,
                'builddir' : builddir,
                'fasm2bels': fasm2bels,
                'rr_graph': rr_graph,
                'vpr_grid': vpr_grid,
                'vpr_capnp_schema': vpr_capnp_schema,
                'dbroot': dbroot,
                'environment_script': environment_script,
            }

        self.render_template('symbiflow-nextpnr-{}-makefile.j2'.format(arch),
                             'Makefile',
                             makefile_params)

    def configure_vpr(self):
        (src_files, incdirs) = self._get_fileset_files(force_slash=True)

        has_vhdl     = 'vhdlSource'      in [x.file_type for x in src_files]
        has_vhdl2008 = 'vhdlSource-2008' in [x.file_type for x in src_files]

        assert (not has_vhdl and not has_vhdl2008), 'VHDL files are not supported in Yosys'
        file_list = []
        timing_constraints = []
        pins_constraints = []
        placement_constraints = []
        user_files = []

        vpr_grid = None
        rr_graph = None
        vpr_capnp_schema = None

        for f in src_files:
            if f.file_type in ['verilogSource']:
                file_list.append(f.name)
            if f.file_type in ['SDC']:
                timing_constraints.append(f.name)
            if f.file_type in ['PCF']:
                pins_constraints.append(f.name)
            if f.file_type in ['xdc']:
                placement_constraints.append(f.name)
            if f.file_type in ['user']:
                user_files.append(f.name)
            if f.file_type in ['RRGraph']:
                rr_graph = f.name
            if f.file_type in ['VPRGrid']:
                vpr_grid = f.name
            if f.file_type in ['capnp']:
                vpr_capnp_schema = f.name

        builddir = self.tool_options.get('builddir', 'build')

        # copy user files to builddir
        for f in user_files:
            shutil.copy(f, self.work_root + "/" + builddir)

        part = self.tool_options.get('part', None)
        package = self.tool_options.get('package', None)
        vendor = self.tool_options.get('vendor', None)

        assert part is not None, 'Missing required "part" parameter'
        assert package is not None, 'Missing required "package" parameter'

        if vendor == 'xilinx':
            if 'xc7a' in part:
                bitstream_device = 'artix7'
            if 'xc7z' in part:
                bitstream_device = 'zynq7'
            if 'xc7k' in part:
                bitstream_device = 'kintex7'

            partname = part + package

            # a35t are in fact a50t
            # leave partname with 35 so we access correct DB
            if part == 'xc7a35t':
                part = 'xc7a50t'
            device_suffix = 'test'
            toolchain_prefix = 'symbiflow_'
        elif vendor == 'quicklogic':
            partname = package
            device_suffix = 'wlcsp'
            bitstream_device = part + "_" + device_suffix
            # Newest Quicklogic toolchain release do not have any toolchain_prefix
            # if if will change in the future this variable should be adjusted.
            toolchain_prefix = ''

        options = self.tool_options.get('options', None)

        fasm2bels = self.tool_options.get('fasm2bels', False)
        dbroot = self.tool_options.get('dbroot', None)
        clocks = self.tool_options.get('clocks', None)

        if fasm2bels:
            if any(v is None for v in [rr_graph, vpr_grid, dbroot]):
                logger.error("When using fasm2bels, rr_graph, vpr_grid and database root must be provided")

            tcl_params = {
                'top': self.toplevel,
                'part': partname,
                'xdc': ' '.join(placement_constraints),
                'clocks': clocks,
            }

            self.render_template('symbiflow-fasm2bels-tcl.j2',
                                 'fasm2bels.tcl',
                                 tcl_params)

            self.render_template('vivado-sh.j2',
                                 'vivado.sh',
                                 dict())

        seed = self.tool_options.get('seed', None)


        # Optional script that will be sourced right before executing each build step in Makefile
        # This script can for example setup enviroment variables or conda enviroment.
        # This file needs to be a bash file
        environment_script = self.tool_options.get('environment_script', None)

        makefile_params = {
            'top': self.toplevel,
            'sources': ' '.join(file_list),
            'partname': partname,
            'part': part,
            'bitstream_device': bitstream_device,
            'sdc': ' '.join(timing_constraints),
            'pcf': ' '.join(pins_constraints),
            'xdc': ' '.join(placement_constraints),
            'builddir': builddir,
            'options': options,
            'fasm2bels': fasm2bels,
            'rr_graph': rr_graph,
            'vpr_grid': vpr_grid,
            'vpr_capnp_schema': vpr_capnp_schema,
            'dbroot': dbroot,
            'seed': seed,
            'device_suffix': device_suffix,
            'toolchain_prefix': toolchain_prefix,
            'environment_script': environment_script,
        }

        self.render_template('symbiflow-vpr-makefile.j2',
                             'Makefile',
                             makefile_params)

    def configure_main(self):
        if self.tool_options.get('pnr') == 'nextpnr':
            self.configure_nextpnr()
        else:
            self.configure_vpr()


    def run_main(self):
        logger.info("Programming")
