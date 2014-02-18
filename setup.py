#!/usr/bin/python
# Copyright (C) 2012 Alex Nitz, Andrew Miller, Josh Willis
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""
setup.py file for PyCBC package
"""
import os
import fnmatch
import sys
import subprocess
import shutil
from trace import fullmodname
from distutils.core import setup,Command,Extension
from distutils.command.clean import clean as _clean
from distutils.command.install import install as _install
from distutils.command.build import build as _build
from numpy import get_include as np_get_include
from pycbc.setuputils import pkg_config
from distutils.file_util import write_file

# Now use the above function to set up our extension library's needs:

ext_libraries, ext_library_dirs, ext_include_dirs = pkg_config(["lal", "lalsimulation", "lalinspiral"])

# Setup our swig options. We need the first two to match with how the swiglal
# wrappings are compiled, so that our module can talk to theirs.  Then we must
# reassemble the include_dirs to add the "-I" so swig can find things
ext_swig_opts = ['-O','-keyword','-builtin','-outdir','pycbc']
for libpath in ext_include_dirs:
    ext_swig_opts.append('-I'+str(libpath))

# Numpy include must be added separately:

ext_include_dirs += [np_get_include()]

# Define our extension module

lalwrap_module = Extension('_lalwrap',
                           sources=['include/lalwrap.i'],
                           depends=['include/pycbc_laltypes.i'],
                           swig_opts=ext_swig_opts,
                           include_dirs=ext_include_dirs,
                           library_dirs=ext_library_dirs,
			   runtime_library_dirs=ext_library_dirs,
                           libraries=ext_libraries,
                           extra_compile_args=['-std=c99']
                           )

testlalwrap_module = Extension('_testlalwrap',
                               sources=['include/testlalwrap.i'],
                               depends=['include/pycbc_laltypes.i'],
                               swig_opts=ext_swig_opts,
                               include_dirs=ext_include_dirs,
                               library_dirs=ext_library_dirs,
                               runtime_library_dirs=ext_library_dirs,
                               libraries=ext_libraries,
                               extra_compile_args=['-std=c99']
                               )

# Add swig-generated files to the list of things to clean, so they
# get regenerated each time.
class clean(_clean):
    def finalize_options (self):
        _clean.finalize_options(self)
        self.clean_files = ['pycbc/lalwrap.py','pycbc/lalwrap.pyc','include/lalwrap_wrap.c',
                            'pycbc/testlalwrap.py','pycbc/testlalwrap.pyc','include/testlalwrap_wrap.c']

        self.clean_folders = ['docs/_build']
    def run(self):
        _clean.run(self)
        for f in self.clean_files:
            try:
                os.unlink(f)
                print 'removed {0}'.format(f)
            except:
                pass

        for fol in self.clean_folders:
            shutil.rmtree(fol, ignore_errors=True)
            print 'removed {0}'.format(fol)

class install(_install):
    def run(self):

        etcdirectory = os.path.join(self.install_data, 'etc')
        if not os.path.exists(etcdirectory):
            os.makedirs(etcdirectory)

        filename = os.path.join(etcdirectory, 'pycbc-user-env.sh')
        self.execute(write_file,
                     (filename, [self.extra_dirs]),
                     "creating %s" % filename)

        env_file = open(filename, 'w')
        print >> env_file, "# Source this file to access PyCBC"
        print >> env_file, "PATH=" + self.install_scripts + ":$PATH"
        print >> env_file, "PYTHONPATH=" + self.install_libbase + ":$PYTHONPATH"
        env_file.close()
        _install.run(self)


# Override build order, so swig is handled first.
class build(_build):
    # override order of build sub-commands to work around
    # <http://bugs.python.org/issue7562>
    sub_commands = [ ('build_clib', _build.has_c_libraries),
                     ('build_ext', _build.has_ext_modules),
                     ('build_py', _build.has_pure_modules),
                     ('build_scripts', _build.has_scripts) ]

    def run(self):
        _build.run(self)

test_results = []
# Run all of the testing scripts
class TestBase(Command):
    user_options = []
    test_modules = []
    def initialize_options(self):
        self.scheme = None
        self.build_dir = None
    def finalize_options(self):
        #Populate the needed variables
        self.set_undefined_options('build',('build_lib', 'build_dir'))

    def find_test_modules(self,pattern):
       # Find all the unittests that match a given string pattern
        modules= []
        for path, dirs, files in os.walk("test"):
            for filename in fnmatch.filter(files, pattern):
                #add the test directories to the path
                sys.path.append(os.path.join(path))
                #save the module name for importing
                modules.append(fullmodname(filename))
        return modules

    def run(self):
        self.run_command('build')
        # Get the list of cpu test modules
        self.test_modules = self.find_test_modules("test*.py")

        # Run from the build directory
        os.environ['PYTHONPATH'] = self.build_dir + ":" + os.environ['PYTHONPATH']

        test_results.append("\n" + (self.scheme + " tests ").rjust(30))
        for test in self.test_modules:
            test_command = 'python ' + 'test/' + test + '.py -s ' + self.scheme
            a = subprocess.call(test_command,env=os.environ,shell=True)
            if a != 0:
                result_str = str(test).ljust(30) + ": Fail : " + str(a)
            else:
                result_str = str(test).ljust(30) + ": Pass"
            test_results.append(result_str)

        for test in test_results:
            print test

class test(Command):
    def has_cuda(self):
        import pycbc
        return pycbc.HAVE_CUDA
    def has_opencl(self):
        import pycbc
        return pycbc.HAVE_OPENCL

    sub_commands = [('test_cpu',None),('test_cuda',has_cuda),('test_opencl',has_opencl)]
    user_options = []
    description = "run the available tests for all compute schemes (cpu,cuda,opencl)"
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        for cmd_name in self.get_sub_commands():
            self.run_command(cmd_name)

class test_cpu(TestBase):
    description = "run all CPU tests"
    def initialize_options(self):
        TestBase.initialize_options(self)
        self.scheme = 'cpu'

class test_cuda(TestBase):
    description = "run CUDA tests"
    def initialize_options(self):
        TestBase.initialize_options(self)
        self.scheme = 'cuda'

class test_opencl(TestBase):
    description = "run OpenCL tests"
    def initialize_options(self):
        TestBase.initialize_options(self)
        self.scheme = 'opencl'

# write versioning info
def generate_version_info():
    """Get VCS info and write version info to version.py
    """
    from pycbc import _version_helper

    vcs_info = _version_helper.generate_git_version_info()

    with open('pycbc/version.py', 'w') as f:
        f.write("# Generated by setup.py for PyCBC on %s.\n\n"
                % vcs_info.build_date)

        # print general info
        f.write('version = \'%s\'\n' % vcs_info.version)
        f.write('date = \'%s\'\n' % vcs_info.date)
        f.write('release = %s\n' % vcs_info.release)

        # print git info
        f.write('\ngit_hash = \'%s\'\n' % vcs_info.hash)
        f.write('git_branch = \'%s\'\n' % vcs_info.branch)
        f.write('git_tag = \'%s\'\n' % vcs_info.tag)
        f.write('git_author = \'%s\'\n' % vcs_info.author)
        f.write('git_committer = \'%s\'\n' % vcs_info.committer)
        f.write('git_status = \'%s\'\n' % vcs_info.status)
        f.write('git_builder = \'%s\'\n' % vcs_info.builder)
        f.write('git_build_date = \'%s\'\n' % vcs_info.build_date)
        f.write('git_verbose_msg = """Branch: %s\nTag: %s\nId: %s\nBuilder: %s\nBuild date: %s\nRepository status is %s"""' %(vcs_info.branch,vcs_info.tag,vcs_info.hash,vcs_info.author,vcs_info.build_date,vcs_info.status) )
    return vcs_info.version

class build_docs(Command):
    user_options = []
    description = "Build the documentation pages"
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        subprocess.check_call("cd docs; cp conf_std.py conf.py; sphinx-apidoc -o ./ -f -A 'PyCBC dev team' -V '0.1' ../pycbc && make html",
                            stderr=subprocess.STDOUT, shell=True)

class build_docs_test(Command):
    user_options = []
    description = "Build the documentation pages in testing mode"
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        subprocess.check_call("cd docs; cp conf_test.py conf.py; sphinx-apidoc -o ./ -f -A 'PyCBC dev team' -V '0.1' ../pycbc && make html",
                            stderr=subprocess.STDOUT, shell=True)                            
                            
# do the actual work of building the package
VERSION = generate_version_info()

setup (
    name = 'PyCBC',
    version = VERSION,
    description = 'Gravitational wave CBC analysis toolkit',
    author = 'Ligo Virgo Collaboration - PyCBC team',
    url = 'https://sugwg-git.phy.syr.edu/dokuwiki/doku.php?id=pycbc:home',
    cmdclass = { 'test'  : test,
                 'build_docs' : build_docs,
                 'build_docs_test' : build_docs_test,
                 'install' : install,
                 'test_cpu':test_cpu,
                 'test_cuda':test_cuda,
                 'test_opencl':test_opencl,
                 'clean' : clean,
                 'build' : build},
    ext_modules = [lalwrap_module, testlalwrap_module],
    requires = ['lal'],
    scripts = ['bin/pycbc_banksim', 'bin/pycbc_faithsim', 'bin/pycbc_inspiral',
               'bin/pycbc_make_banksim', 'bin/pycbc_split_table',
               'bin/pycbc_legacy_inspiral','bin/pycbc_geom_aligned_2dstack',
               'bin/pycbc_geom_aligned_bank','bin/pycbc_geom_nonspinbank',
               'bin/pycbc_aligned_bank_cat','bin/pycbc_aligned_stoch_bank',
               'bin/pycbc_make_faithsim', 'bin/pycbc_get_ffinal',
               'bin/pycbc_legacy_tmpltbank'],
    packages = ['pycbc','pycbc.fft','pycbc.types','pycbc.filter','pycbc.psd','pycbc.waveform','pycbc.events','pycbc.noise','pycbc.vetoes','pycbc.tmpltbank','pycbc.ahope'],
)
