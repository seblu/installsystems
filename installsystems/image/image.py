# -*- python -*-
# -*- coding: utf-8 -*-

# This file is part of Installsystems.
#
# Installsystems is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Installsystems is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Installsystems.  If not, see <http://www.gnu.org/licenses/>.


'''
Image abstract module
'''

from imp import new_module
from installsystems import VERSION
from installsystems.exception import ISError
from installsystems.printer import arrow, arrowlevel
from installsystems.tools import compare_versions
from locale import getpreferredencoding
from os import getcwd, chdir
from os.path import splitext
from re import match, split

class Image(object):
    '''
    Abstract class of images
    '''

    extension = ".isimage"
    default_compressor = "gzip"

    def __init__(self):
        self.modules = {}

    def _load_module(self, name, filename, code=None):
        '''
        Create a python module from a string or a filename
        '''
        # unicode safety check
        assert(isinstance(name, unicode))
        assert(isinstance(filename, unicode))
        assert(code is None or isinstance(code, str))
        # load code if not provided
        if code is None:
            code = open(filename, "r").read()
        # create an empty module
        module = new_module(name)
        # compile module code
        try:
            bytecode = compile(code, filename.encode(getpreferredencoding()), "exec")
        except Exception as e:
            raise ISError(u"Unable to compile %s" % filename, e)
        # load module
        try:
            self.secure_exec_bytecode(bytecode, name, module.__dict__)
        except Exception as e:
            raise ISError(u"Unable to load %s" % filename, e)
        return module

    def load_modules(self, select_scripts):
        '''
        Load all modules selected by generator select_scripts

        select_scripts is a generator which return tuples (fp, fn, fc) where:
          fp is unicode file path of the module
          fn is unicode file name of the module (basename)
          fc is unicode file content
        '''
        arrow(u"Load lib scripts")
        old_level = arrowlevel(1)
        self.modules = {}
        for fp, fn, fc in select_scripts():
            # check input unicode stuff
            assert(isinstance(fp, unicode))
            assert(isinstance(fn, unicode))
            assert(isinstance(fc, str))
            arrow(fn)
            module_name = splitext(fn.split('-', 1)[1])[0]
            self.modules[module_name] = self._load_module(module_name, fp, fc)
        arrowlevel(level=old_level)

    def run_scripts(self, scripts_name, select_scripts, exec_directory, global_dict):
        '''
        Execute scripts selected by generator select_scripts

        scripts_name is only for display the first arrow before execution

        select_scripts is a generator which return tuples (fp, fn, fc) where:
          fp is file path of the scripts
          fn is file name of the scripts (basename)
          fc is file content

        exec_directory is the cwd of the running script

        global_dict is the globals environment given to scripts
        '''
        arrow(u"Run %s scripts" % scripts_name)
        # backup current directory and loaded modules
        cwd = getcwd()
        for fp, fn, fc in select_scripts():
            # check input unicode stuff
            assert(isinstance(fp, unicode))
            assert(isinstance(fn, unicode))
            assert(isinstance(fc, str))
            arrow(fn, 1)
            # backup arrow level
            old_level = arrowlevel(2)
            # chdir in exec_directory
            chdir(exec_directory)
            # compile source code
            try:
                bytecode = compile(fc, fn.encode(getpreferredencoding()), "exec")
            except Exception as e:
                raise ISError(u"Unable to compile script %s" % fp, e)
            # add current image
            global_dict["image"] = self
            # execute source code
            self.secure_exec_bytecode(bytecode, fp, global_dict)
            arrowlevel(level=old_level)
        chdir(cwd)

    def secure_exec_bytecode(self, bytecode, path, global_dict):
        '''
        Execute bytecode in a clean modules' environment, without altering
        Installsystems' sys.modules
        '''
        import sys
        import installsystems.printer

        # system modules dict
        sysmodules = sys.modules
        sysmodules_backup = sysmodules.copy()
        # autoload modules
        global_dict.update(self.modules)
        try:
            # replace system modules by image loaded
            # we must use the same directory and not copy it (probably C reference)
            for module in self.modules:
                if module in sysmodules:
                    del sysmodules[str(module)]
            # sys must be in sys.module to allow loading of modules
            sysmodules["sys"] = sys
            sysmodules.update(self.modules)
            # we need installsystems.printer to conserve arrow level
            sysmodules["installsystems.printer"] = installsystems.printer
            exec bytecode in global_dict
        except SystemExit as e:
            # skip a script which call exit(0) or exit()
            if e.code is None or e.code == 0:
                return
            else:
                raise ISError(u"Script %s exits with status" % path, e)
        except Exception as e:
            raise ISError(u"Fail to execute script %s" % path, e)
        finally:
            sysmodules.clear()
            sysmodules.update(sysmodules_backup)

    @staticmethod
    def check_name(buf):
        '''
        Check if @buf is a valid image name
        '''
        if match("^[-_.\w]+$", buf) is None:
            raise ISError(u"Invalid image name %s" % buf)
        # return the image name, because this function is used by ConfigObj
        # validate to ensure the image name is correct
        return buf

    @staticmethod
    def check_version(buf):
        '''
        Check if @buf is a valid image version
        '''
        if match("^\d+(\.\d+)*(([~+]).*)?$", buf) is None:
            raise ISError(u"Invalid image version %s" % buf)
        # return the image version, because this function is used by ConfigObj
        # validate to ensure the image version is correct
        return buf

    @staticmethod
    def check_min_version(version):
        '''
        Check InstallSystems min version
        '''
        if compare_versions(VERSION, version) < 0:
            raise ISError("Minimum Installsystems version not satisfied "
                          "(%s)" % version)
        # return the version, because this function is used by ConfigObj
        # validate to ensure the version is correct
        return version

    @staticmethod
    def compare_versions(v1, v2):
        '''
        For backward compatibility, image class offer a method to compare image versions
        But code is now inside tools
        '''
        return compare_versions(v1, v2)
