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
Image stuff
'''

import codecs
import configobj
import cStringIO
import difflib
import imp
import fnmatch
import json
import locale
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import validate
import installsystems
import installsystems.template as istemplate
import installsystems.tools as istools
from installsystems.exception import *
from installsystems.printer import *
from installsystems.tools import PipeFile
from installsystems.tarball import Tarball


# This must not be an unicode string, because configobj don't decode configspec
# with the provided encoding
DESCRIPTION_CONFIG_SPEC = '''\
[image]
name = IS_name
version = IS_version
description = string
author = string
is_min_version = IS_min_version

[compressor]
__many__ = force_list
'''


class Image(object):
    '''
    Abstract class of images
    '''

    extension = ".isimage"
    default_compressor = "gzip"

    @staticmethod
    def check_image_name(buf):
        '''
        Check if @buf is a valid image name
        '''
        if re.match("^[-_\w]+$", buf) is None:
            raise ISError(u"Invalid image name %s" % buf)
        # return the image name, because this function is used by ConfigObj
        # validate to ensure the image name is correct
        return buf

    @staticmethod
    def check_image_version(buf):
        '''
        Check if @buf is a valid image version
        '''
        if re.match("^\d+(\.\d+)*(([~+]).*)?$", buf) is None:
            raise ISError(u"Invalid image version %s" % buf)
        # return the image version, because this function is used by ConfigObj
        # validate to ensure the image version is correct
        return buf

    @staticmethod
    def check_min_version(version):
        '''
        Check InstallSystems min version
        '''
        if istools.compare_versions(installsystems.version, version) < 0:
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
        return istools.compare_versions(v1, v2)

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
        module = imp.new_module(name)
        # compile module code
        try:
            bytecode = compile(code, filename.encode(locale.getpreferredencoding()), "exec")
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
            module_name = os.path.splitext(fn.split('-', 1)[1])[0]
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
        cwd = os.getcwd()
        for fp, fn, fc in select_scripts():
            # check input unicode stuff
            assert(isinstance(fp, unicode))
            assert(isinstance(fn, unicode))
            assert(isinstance(fc, str))
            arrow(fn, 1)
            # backup arrow level
            old_level = arrowlevel(2)
            # chdir in exec_directory
            os.chdir(exec_directory)
            # compile source code
            try:
                bytecode = compile(fc, fn.encode(locale.getpreferredencoding()), "exec")
            except Exception as e:
                raise ISError(u"Unable to compile script %s" % fp, e)
            # add current image
            global_dict["image"] = self
            # execute source code
            self.secure_exec_bytecode(bytecode, fp, global_dict)
            arrowlevel(level=old_level)
        os.chdir(cwd)

    def secure_exec_bytecode(self, bytecode, path, global_dict):
        '''
        Execute bytecode in a clean modules' environment, without altering
        Installsystems' sys.modules
        '''
        # system modules dict
        sysmodules = sys.modules
        sysmodules_backup = sysmodules.copy()
        # autoload modules
        global_dict.update(self.modules)
        try:
            # replace system modules by image loaded
            # we must use the same directory and not copy it (probably C reference)
            sysmodules.clear()
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


class SourceImage(Image):
    '''
    Image source manipulation class
    '''

    # format should be a float  X.Y but for compatibility reason it's a string
    # before version 6, it's strict string comparaison
    format = "2.0"


    @classmethod
    def create(cls, path, force=False):
        '''
        Create an empty source image
        '''
        # check local repository
        if not istools.isfile(path):
            raise NotImplementedError("SourceImage must be local")
        # main path
        build_path = os.path.join(path, "build")
        parser_path = os.path.join(path, "parser")
        setup_path = os.path.join(path, "setup")
        payload_path = os.path.join(path, "payload")
        lib_path = os.path.join(path, "lib")
        # create base directories
        arrow("Creating base directories")
        try:
            for d in (path, build_path, parser_path, setup_path, payload_path,
                      lib_path):
                if not os.path.exists(d) or not os.path.isdir(d):
                    os.mkdir(d)
        except Exception as e:
            raise ISError(u"Unable to create directory: %s" % d, e)
        # create example files
        arrow("Creating examples")
        arrowlevel(1)
        # create dict of file to create
        examples = {}
        # create description example from template
        examples["description"] = {"path": "description",
                                   "content": istemplate.description % {
                "name": "",
                "version": "1",
                "description": "",
                "author": "",
                "is_min_version": installsystems.version,
                "compressor": "gzip = *\nnone = *.gz, *.bz2, *.xz"}}
        # create changelog example from template
        examples["changelog"] = {"path": "changelog", "content": istemplate.changelog}
        # create build example from template
        examples["build"] = {"path": "build/01-build.py", "content": istemplate.build}
        # create parser example from template
        examples["parser"] = {"path": "parser/01-parser.py", "content": istemplate.parser}
        # create setup example from template
        examples["setup"] = {"path": "setup/01-setup.py", "content": istemplate.setup}
        for name in examples:
            try:
                arrow(u"Creating %s example" % name)
                expath = os.path.join(path, examples[name]["path"])
                if not force and os.path.exists(expath):
                    warn(u"%s already exists. Skipping!" % expath)
                    continue
                open(expath, "w").write(examples[name]["content"])
            except Exception as e:
                raise ISError(u"Unable to create example file", e)
        try:
            # setting executable rights on files in setup and parser
            arrow("Setting executable rights on scripts")
            umask = os.umask(0)
            os.umask(umask)
            for dpath in (build_path, parser_path, setup_path):
                for f in os.listdir(dpath):
                    istools.chrights(os.path.join(dpath, f), mode=0777 & ~umask)
        except Exception as e:
            raise ISError(u"Unable to set rights on %s" % pf, e)
        arrowlevel(-1)

    def __init__(self, path):
        '''
        Initialize source image
        '''
        Image.__init__(self)
        # check local repository
        if not istools.isfile(path):
            raise NotImplementedError("SourceImage must be local")
        self.base_path = os.path.abspath(path)
        for pathtype in ("build", "parser", "setup", "payload", "lib"):
            setattr(self, u"%s_path" % pathtype, os.path.join(self.base_path, pathtype))
        self.check_source_image()
        self.description = self.parse_description()
        self.changelog = self.parse_changelog()
        self.modules = {}
        # script tarball path
        self.image_name = u"%s-%s%s" % (self.description["name"],
                                        self.description["version"],
                                        self.extension)

    def check_source_image(self):
        '''
        Check if we are a valid SourceImage directories
        A vaild SourceImage contains at least a description and a setup directory.
        Payload directory is mandatory is build scripts are present
        '''
        # Ensure setup_path exists
        if not os.path.exists(self.setup_path):
            raise InvalidSourceImage(u"setup directory is missing.")
        # Ensure description exists
        if not os.path.exists(os.path.join(self.base_path, u"description")):
            raise InvalidSourceImage(u"no description file.")
        # Ensure payload directory exists if there is build directory
        if not os.path.exists(self.payload_path) and os.path.exists(self.build_path):
            raise InvalidSourceImage(u"payload directory is mandatory with a build directory.")
        # Ensure directories are directories and accessible
        for d in (self.base_path, self.build_path, self.parser_path,
                  self.setup_path, self.payload_path, self.lib_path):
            if os.path.exists(d):
                if not os.path.isdir(d):
                    raise InvalidSourceImage(u"%s is not a directory." % d)
                if not os.access(d, os.R_OK|os.X_OK):
                    raise InvalidSourceImage(u"unable to access to %s." % d)

    def build(self, force=False, force_payload=False, check=True, script=True):
        '''
        Create packaged image
        '''
        # check if free to create script tarball
        if os.path.exists(self.image_name) and force == False:
            raise ISError("Tarball already exists. Remove it before")
        # register start time
        t0 = time.time()
        # check python scripts
        if check:
            for d in (self.build_path, self.parser_path, self.setup_path,
                      self.lib_path):
                if os.path.exists(d):
                    self.check_scripts(d)
        # load modules
        self.load_modules(lambda: self.select_scripts(self.lib_path))
        # remove list
        rl = set()
        # run build script
        if script and os.path.exists(self.build_path):
            rl |= set(self.run_build())
        if force_payload:
            rl |= set(self.select_payloads())
        # remove payloads
        self.remove_payloads(rl)
        # create payload files
        self.create_payloads()
        # generate a json description
        jdesc = self.generate_json_description()
        # creating scripts tarball
        self.create_image(jdesc)
        # compute building time
        return int(time.time() - t0)

    def create_image(self, jdescription):
        '''
        Create a script tarball in current directory
        '''
        # create tarball
        arrow("Creating image tarball")
        arrowlevel(1)
        arrow(u"Name %s" % self.image_name)
        try:
            try:
                tarball = Tarball.open(self.image_name, mode="w:gz", dereference=True)
            except Exception as e:
                raise ISError(u"Unable to create tarball %s" % self.image_name, e)
            # add description.json
            arrow("Add description.json")
            tarball.add_str("description.json", jdescription, tarfile.REGTYPE, 0644)
            # add changelog
            if self.changelog is not None:
                arrow("Add changelog")
                tarball.add_str("changelog", self.changelog.verbatim, tarfile.REGTYPE, 0644)
            # add format
            arrow("Add format")
            tarball.add_str("format", self.format, tarfile.REGTYPE, 0644)
            # add setup scripts
            self.add_scripts(tarball, self.setup_path)
            # add optional scripts
            for d in (self.build_path, self.parser_path, self.lib_path):
                if os.path.exists(d):
                    self.add_scripts(tarball, d)
            # closing tarball file
            tarball.close()
        except (SystemExit, KeyboardInterrupt):
            if os.path.exists(self.image_name):
                os.unlink(self.image_name)
        arrowlevel(-1)

    def describe_payload(self, name):
        '''
        Return information about a payload
        '''
        ans = {}
        ans["source_path"] = os.path.join(self.payload_path, name)
        ans["dest_path"] = u"%s-%s%s" % (self.description["name"],
                                         name,
                                         Payload.extension)
        ans["link_path"] = u"%s-%s-%s%s" % (self.description["name"],
                                            self.description["version"],
                                            name,
                                            Payload.extension)
        source_stat = os.stat(ans["source_path"])
        ans["isdir"] = stat.S_ISDIR(source_stat.st_mode)
        ans["uid"] = source_stat.st_uid
        ans["gid"] = source_stat.st_gid
        ans["mode"] = stat.S_IMODE(source_stat.st_mode)
        ans["mtime"] = source_stat.st_mtime
        ans["compressor"] = self.compressor(name)
        return ans

    def select_payloads(self):
        '''
        Return a generator on image payloads
        '''
        if not os.path.isdir(self.payload_path):
            raise StopIteration()
        for payname in os.listdir(self.payload_path):
            yield payname

    def remove_payloads(self, paylist):
        '''
        Remove payload list if exists
        '''
        arrow("Removing payloads")
        for pay in paylist:
            arrow(pay, 1)
            desc = self.describe_payload(pay)
            for f in (desc["dest_path"], desc["link_path"]):
                if os.path.lexists(f):
                    os.unlink(f)

    def create_payloads(self):
        '''
        Create all missing data payloads in current directory
        Doesn't compute md5 during creation because tarball can
        be created manually
        Also create symlink to versionned payload
        '''
        arrow("Creating payloads")
        for payload_name in self.select_payloads():
            paydesc = self.describe_payload(payload_name)
            if os.path.exists(paydesc["link_path"]):
                continue
            arrow(payload_name, 1)
            try:
                # create non versionned payload file
                if not os.path.exists(paydesc["dest_path"]):
                    if paydesc["isdir"]:
                        self.create_payload_tarball(paydesc["dest_path"],
                                                    paydesc["source_path"],
                                                    paydesc["compressor"])
                    else:
                        self.create_payload_file(paydesc["dest_path"],
                                                 paydesc["source_path"],
                                                 paydesc["compressor"])
                # create versionned payload file
                if os.path.lexists(paydesc["link_path"]):
                    os.unlink(paydesc["link_path"])
                os.symlink(paydesc["dest_path"], paydesc["link_path"])
            except Exception as e:
                raise ISError(u"Unable to create payload %s" % payload_name, e)

    def create_payload_tarball(self, tar_path, data_path, compressor):
        '''
        Create a payload tarball
        '''
        try:
            # get compressor argv (first to escape file creation if not found)
            a_comp = istools.get_compressor_path(compressor, compress=True)
            a_tar = ["tar", "--create", "--numeric-owner", "--directory",
                     data_path, "."]
            # create destination file
            f_dst = PipeFile(tar_path, "w", progressbar=True)
            # run tar process
            p_tar = subprocess.Popen(a_tar, shell=False, close_fds=True,
                                     stdout=subprocess.PIPE)
            # run compressor process
            p_comp = subprocess.Popen(a_comp, shell=False, close_fds=True,
                                      stdin=p_tar.stdout, stdout=subprocess.PIPE)
            # write data from compressor to tar_path
            f_dst.consume(p_comp.stdout)
            # close all fd
            p_tar.stdout.close()
            p_comp.stdout.close()
            f_dst.close()
            # check tar return 0
            if p_tar.wait() != 0:
                raise ISError("Tar return is not zero")
            # check compressor return 0
            if p_comp.wait() != 0:
                raise ISError(u"Compressor %s return is not zero" % a_comp[0])
        except (SystemExit, KeyboardInterrupt):
            if os.path.exists(tar_path):
                os.unlink(tar_path)
            raise

    def create_payload_file(self, dest, source, compressor):
        '''
        Create a payload file
        '''
        try:
            # get compressor argv (first to escape file creation if not found)
            a_comp = istools.get_compressor_path(compressor, compress=True)
            # open source file
            f_src = open(source, "r")
            # create destination file
            f_dst = PipeFile(dest, "w", progressbar=True)
            # run compressor
            p_comp = subprocess.Popen(a_comp, shell=False, close_fds=True,
                                      stdin=f_src, stdout=subprocess.PIPE)
            # close source file fd
            f_src.close()
            # write data from compressor to dest file
            f_dst.consume(p_comp.stdout)
            # close compressor stdin and destination file
            p_comp.stdout.close()
            f_dst.close()
            # check compressor return 0
            if p_comp.wait() != 0:
                raise ISError(u"Compressor %s return is not zero" % a_comp[0])
        except (SystemExit, KeyboardInterrupt):
            if os.path.exists(dest):
                os.unlink(dest)
            raise

    def select_scripts(self, directory):
        '''
        Generator of tuples (fp,fn,fc) of scripts witch are allocatable
        in a real directory
        '''
        # ensure directory is unicode to have fn and fp in unicode
        if not isinstance(directory, unicode):
            directory = unicode(directory, locale.getpreferredencoding())
        if not os.path.exists(directory):
            return
        for fn in sorted(os.listdir(directory)):
            fp = os.path.join(directory, fn)
            # check name
            if not re.match("^\d+-.*\.py$", fn):
                continue
            # check execution bit
            if not os.access(fp, os.X_OK):
                continue
            # get module content
            try:
                fc = open(fp, "r").read()
            except Exception as e:
                raise ISError(u"Unable to read script %s" % n_scripts, e)
            # yield complet file path, file name and file content
            yield (fp, fn, fc)

    def add_scripts(self, tarball, directory):
        '''
        Add scripts inside a directory into a tarball
        '''
        basedirectory = os.path.basename(directory)
        arrow(u"Add %s scripts" % basedirectory)
        arrowlevel(1)
        # adding base directory
        ti = tarball.gettarinfo(directory, arcname=basedirectory)
        ti.mode = 0755
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = ""
        tarball.addfile(ti)
        # adding each file
        for fp, fn, fc in self.select_scripts(directory):
            # check input unicode stuff
            assert(isinstance(fp, unicode))
            assert(isinstance(fn, unicode))
            assert(isinstance(fc, str))
            # add file into tarball
            tarball.add_str(os.path.join(basedirectory, fn),
                            fc,
                            tarfile.REGTYPE,
                            0755,
                            int(os.stat(fp).st_mtime))
            arrow(u"%s added" % fn)
        arrowlevel(-1)

    def check_scripts(self, directory):
        '''
        Check if scripts inside a directory can be compiled
        '''
        basedirectory = os.path.basename(directory)
        arrow(u"Checking %s scripts" % basedirectory)
        arrowlevel(1)
        # checking each file
        for fp, fn, fc in self.select_scripts(directory):
            # check input unicode stuff
            assert(isinstance(fp, unicode))
            assert(isinstance(fn, unicode))
            assert(isinstance(fc, str))
            arrow(fn)
            try:
                compile(fc, fn.encode(locale.getpreferredencoding()), "exec")
            except SyntaxError as e:
                raise ISError(exception=e)
        arrowlevel(-1)

    def run_build(self):
        '''
        Run build scripts
        '''
        rebuild_list = []
        self.run_scripts(os.path.basename(self.build_path),
                         lambda: self.select_scripts(self.build_path),
                         self.payload_path,
                         {"rebuild": rebuild_list})
        return rebuild_list

    def generate_json_description(self):
        '''
        Generate a JSON description file
        '''
        arrow("Generating JSON description")
        arrowlevel(1)
        # copy description
        desc = self.description.copy()
        # only store compressor patterns
        desc["compressor"] = desc["compressor"]["patterns"]
        # timestamp image
        arrow("Timestamping")
        desc["date"] = int(time.time())
        # watermark
        desc["is_build_version"] = installsystems.version
        # append payload infos
        arrow("Checksumming payloads")
        desc["payload"] = {}
        for payload_name in self.select_payloads():
            arrow(payload_name, 1)
            # getting payload info
            payload_desc = self.describe_payload(payload_name)
            # compute md5 and size
            fileobj = PipeFile(payload_desc["link_path"], "r")
            fileobj.consume()
            fileobj.close()
            # create payload entry
            desc["payload"][payload_name] = {
                "md5": fileobj.md5,
                "size": fileobj.size,
                "isdir": payload_desc["isdir"],
                "uid": payload_desc["uid"],
                "gid": payload_desc["gid"],
                "mode": payload_desc["mode"],
                "mtime": payload_desc["mtime"],
                "compressor": payload_desc["compressor"]
                }
        arrowlevel(-1)
        # check md5 are uniq
        md5s = [v["md5"] for v in desc["payload"].values()]
        if len(md5s) != len(set(md5s)):
            raise ISError("Two payloads cannot have the same md5")
        # serialize
        return json.dumps(desc)

    def parse_description(self):
        '''
        Raise an exception is description file is invalid and return vars to include
        '''
        arrow("Parsing description")
        d = dict()
        try:
            descpath = os.path.join(self.base_path, "description")
            cp = configobj.ConfigObj(descpath,
                                     configspec=DESCRIPTION_CONFIG_SPEC.splitlines(),
                                     encoding="utf8", file_error=True)
            res = cp.validate(validate.Validator({"IS_name": Image.check_image_name,
                                                  "IS_version": Image.check_image_version,
                                                  "IS_min_version": Image.check_min_version}), preserve_errors=True)
            # If everything is fine, the validation return True
            # Else, it returns a list of (section, optname, error)
            if res is not True:
                for section, optname, error in configobj.flatten_errors(cp, res):
                    # If error is False, this mean no value as been supplied,
                    # so we use the default value
                    # Else, the check has failed
                    if error:
                        installsystems.printer.error('Wrong description file, %s %s: %s' % (section, optname, error))
            for n in ("name","version", "description", "author", "is_min_version"):
                d[n] = cp["image"][n]
            d["compressor"] = {}
            # set payload compressor
            d["compressor"]["patterns"] = cp["compressor"].items()
            if not d["compressor"]["patterns"]:
                d["compressor"]["patterns"] = [(Image.default_compressor, "*")]
            for compressor, patterns in cp["compressor"].items():
                # is a valid compressor?
                istools.get_compressor_path(compressor)
                for pattern in patterns:
                    for payname in fnmatch.filter(self.select_payloads(), pattern):
                        d["compressor"][payname] = compressor
        except Exception as e:
            raise ISError(u"Bad description", e)
        return d

    def parse_changelog(self):
        '''
        Create a changelog object from a file
        '''
        # try to find a changelog file
        try:
            path = os.path.join(self.base_path, "changelog")
            fo = codecs.open(path, "r", "utf8")
        except IOError:
            return None
        # we have it, we need to check everything is ok
        arrow("Parsing changelog")
        try:
            cl = Changelog(fo.read())
        except Exception as e:
            raise ISError(u"Bad changelog", e)
        return cl

    def compressor(self, payname):
        '''
        Return payload compressor
        '''
        try:
            return self.description["compressor"][payname]
        except KeyError:
            # set default compressor if no compressor is specified
            return Image.default_compressor


class PackageImage(Image):
    '''
    Packaged image manipulation class
    '''

    @classmethod
    def diff(cls, pkg1, pkg2):
        '''
        Diff two packaged images
        '''
        arrow(u"Difference from images #y#%s v%s#R# to #r#%s v%s#R#:" % (pkg1.name,
                                                                         pkg1.version,
                                                                         pkg2.name,
                                                                         pkg2.version))
        # extract images for diff scripts files
        fromfiles = set(pkg1._tarball.getnames(re_pattern="(parser|setup)/.*"))
        tofiles = set(pkg2._tarball.getnames(re_pattern="(parser|setup)/.*"))
        for f in fromfiles | tofiles:
            # preparing from info
            if f in fromfiles:
                fromfile = os.path.join(pkg1.filename, f)
                fromdata = pkg1._tarball.extractfile(f).readlines()
            else:
                fromfile = "/dev/null"
                fromdata = ""
            # preparing to info
            if f in tofiles:
                tofile = os.path.join(pkg2.filename, f)
                todata = pkg2._tarball.extractfile(f).readlines()
            else:
                tofile = "/dev/null"
                todata = ""
            # generate diff
            for line in difflib.unified_diff(fromdata, todata,
                                             fromfile=fromfile, tofile=tofile):
                # coloring diff
                if line.startswith("+"):
                   out(u"#g#%s#R#" % line, endl="")
                elif line.startswith("-"):
                   out(u"#r#%s#R#" % line, endl="")
                elif line.startswith("@@"):
                   out(u"#c#%s#R#" % line, endl="")
                else:
                   out(line, endl="")

    def __init__(self, path, fileobj=None, md5name=False):
        '''
        Initialize a package image

        fileobj must be a seekable fileobj
        '''
        Image.__init__(self)
        self.path = istools.abspath(path)
        self.base_path = os.path.dirname(self.path)
        # tarball are named by md5 and not by real name
        self.md5name = md5name
        try:
            if fileobj is None:
                fileobj = PipeFile(self.path, "r")
            else:
                fileobj = PipeFile(mode="r", fileobj=fileobj)
            memfile = cStringIO.StringIO()
            fileobj.consume(memfile)
            # close source
            fileobj.close()
            # get downloaded size and md5
            self.size = fileobj.read_size
            self.md5 = fileobj.md5
            memfile.seek(0)
            self._tarball = Tarball.open(fileobj=memfile, mode='r:gz')
        except Exception as e:
            raise ISError(u"Unable to open image %s" % path, e)
        self._metadata = self.read_metadata()
        # print info
        arrow(u"Image %s v%s loaded" % (self.name, self.version))
        arrow(u"Author: %s" % self.author, 1)
        arrow(u"Date: %s" % istools.time_rfc2822(self.date), 1)
        # build payloads info
        self.payload = {}
        for pname, pval in self._metadata["payload"].items():
            pfilename = u"%s-%s%s" % (self.filename[:-len(Image.extension)],
                                      pname, Payload.extension)
            if self.md5name:
                ppath = os.path.join(self.base_path,
                                     self._metadata["payload"][pname]["md5"])
            else:
                ppath = os.path.join(self.base_path, pfilename)
            self.payload[pname] = Payload(pname, pfilename, ppath, **pval)

    def __getattr__(self, name):
        '''
        Give direct access to description field
        '''
        if name in self._metadata:
            return self._metadata[name]
        raise AttributeError

    @property
    def filename(self):
        '''
        Return image filename
        '''
        return u"%s-%s%s" % (self.name, self.version, self.extension)

    def read_metadata(self):
        '''
        Parse tarball and return metadata dict
        '''
        desc = {}
        # check format
        img_format = self._tarball.get_utf8("format")
        try:
            if float(img_format) >= math.floor(float(SourceImage.format)) + 1.0:
                raise Exception()
        except:
            raise ISError(u"Invalid image format %s" % img_format)
        desc["format"] = img_format
        # check description
        try:
            img_desc = self._tarball.get_utf8("description.json")
            desc.update(json.loads(img_desc))
            self.check_image_name(desc["name"])
            self.check_image_version(desc["version"])
            if "compressor" not in desc:
                desc["compressor"] = "gzip = *"
            else:
                # format compressor pattern string
                compressor_str = ""
                for compressor, patterns in desc["compressor"]:
                    # if pattern is not empty
                    if patterns != ['']:
                        compressor_str += "%s = %s\n" % (compressor, ", ".join(patterns))
                # remove extra endline
                desc["compressor"] = compressor_str[:-1]
            # add is_min_version if not present
            if "is_min_version" not in desc:
                desc["is_min_version"] = 0
            # check installsystems min version
            if self.compare_versions(installsystems.version, desc["is_min_version"]) < 0:
                raise ISError("Minimum Installsystems version not satisfied "
                              "(%s)" % desc["is_min_version"])
        except Exception as e:
            raise ISError(u"Invalid description", e)
        # try to load changelog
        try:
            img_changelog = self._tarball.get_utf8("changelog")
            desc["changelog"] = Changelog(img_changelog)
        except KeyError:
            desc["changelog"] = Changelog("")
        except Exception as e:
            warn(u"Invalid changelog: %s" % e)
        return desc

    def show(self, o_payloads=False, o_files=False, o_changelog=False, o_json=False):
        '''
        Display image content
        '''
        if o_json:
            out(json.dumps(self._metadata))
        else:
            out(u'#light##yellow#Name:#reset# %s' % self.name)
            out(u'#light##yellow#Version:#reset# %s' % self.version)
            out(u'#yellow#Date:#reset# %s' % istools.time_rfc2822(self.date))
            out(u'#yellow#Description:#reset# %s' % self.description)
            out(u'#yellow#Author:#reset# %s' % self.author)
            # field is_build_version is new in version 5. I can be absent.
            try: out(u'#yellow#IS build version:#reset# %s' % self.is_build_version)
            except AttributeError: pass
            # field is_min_version is new in version 5. I can be absent.
            try: out(u'#yellow#IS minimum version:#reset# %s' % self.is_min_version)
            except AttributeError: pass
            out(u'#yellow#Format:#reset# %s' % self.format)
            out(u'#yellow#MD5:#reset# %s' % self.md5)
            out(u'#yellow#Payload count:#reset# %s' % len(self.payload))
            # display payloads
            if o_payloads:
                payloads = self.payload
                for payload_name in payloads:
                    payload = payloads[payload_name]
                    out(u'#light##yellow#Payload:#reset# %s' % payload_name)
                    out(u'  #yellow#Date:#reset# %s' % istools.time_rfc2822(payload.mtime))
                    out(u'  #yellow#Size:#reset# %s' % (istools.human_size(payload.size)))
                    out(u'  #yellow#MD5:#reset# %s' % payload.md5)
            # display image content
            if o_files:
                out('#light##yellow#Files:#reset#')
                self._tarball.list(True)
            # display changelog
            if o_changelog:
                out('#light##yellow#Changelog:#reset#')
                self.changelog.show(self.version)

    def check(self, message="Check MD5"):
        '''
        Check md5 and size of tarballs are correct
        Download tarball from path and compare the loaded md5 and remote
        '''
        arrow(message)
        arrowlevel(1)
        # check image
        fo = PipeFile(self.path, "r")
        fo.consume()
        fo.close()
        if self.size != fo.read_size:
            raise ISError(u"Invalid size of image %s" % self.name)
        if self.md5 != fo.md5:
            raise ISError(u"Invalid MD5 of image %s" % self.name)
        # check payloads
        for pay_name, pay_obj in self.payload.items():
            arrow(pay_name)
            pay_obj.check()
        arrowlevel(-1)

    def cat(self, filename):
        '''
        Display filename in the tarball
        '''
        filelist = self._tarball.getnames(glob_pattern=filename, dir=False)
        if len(filelist) == 0:
            warn(u"No file matching %s" % filename)
        for filename in filelist:
            arrow(filename)
            out(self._tarball.get_utf8(filename))

    def download(self, directory, force=False, image=True, payload=False):
        '''
        Download image in directory
        Doesn't use in memory image because we cannot access it
        This is done to don't parasitize self._tarfile access to memfile
        '''
        # check if destination exists
        directory = os.path.abspath(directory)
        if image:
            dest = os.path.join(directory, self.filename)
            if not force and os.path.exists(dest):
                raise ISError(u"Image destination already exists: %s" % dest)
            # some display
            arrow(u"Downloading image in %s" % directory)
            debug(u"Downloading %s from %s" % (self.filename, self.path))
            # open source
            fs = PipeFile(self.path, progressbar=True)
            # check if announced file size is good
            if fs.size is not None and self.size != fs.size:
                raise ISError(u"Downloading image %s failed: Invalid announced size" % self.name)
            # open destination
            fd = open(self.filename, "wb")
            fs.consume(fd)
            fs.close()
            fd.close()
            if self.size != fs.consumed_size:
                raise ISError(u"Download image %s failed: Invalid size" % self.name)
            if self.md5 != fs.md5:
                raise ISError(u"Download image %s failed: Invalid MD5" % self.name)
        if payload:
            for payname in self.payload:
                arrow(u"Downloading payload %s in %s" % (payname, directory))
                self.payload[payname].info
                self.payload[payname].download(directory, force=force)

    def extract(self, directory, force=False, payload=False, gendescription=False):
        '''
        Extract content of the image inside a repository
        '''
        # check validity of dest
        if os.path.exists(directory):
            if not os.path.isdir(directory):
                raise ISError(u"Destination %s is not a directory" % directory)
            if not force and len(os.listdir(directory)) > 0:
                raise ISError(u"Directory %s is not empty (need force)" % directory)
        else:
            istools.mkdir(directory)
        # extract content
        arrow(u"Extracting image in %s" % directory)
        self._tarball.extractall(directory)
        # generate description file from description.json
        if gendescription:
            arrow(u"Generating description file in %s" % directory)
            with open(os.path.join(directory, "description"), "w") as f:
                f.write((istemplate.description % self._metadata).encode("UTF-8"))
        # launch payload extraction
        if payload:
            for payname in self.payload:
                # here we need to decode payname which is in unicode to escape
                # tarfile to encode filename of file inside tarball inside unicode
                dest = os.path.join(directory, "payload", payname.encode("UTF-8"))
                arrow(u"Extracting payload %s in %s" % (payname, dest))
                self.payload[payname].extract(dest, force=force)

    def run(self, parser, extparser, load_modules=True, run_parser=True,
            run_setup=True):
        '''
        Run images scripts

        parser is the whole command line parser
        extparser is the parser extensible by parser scripts

        if load_modules is true load image modules
        if run_parser is true run parser scripts
        if run_setup is true run setup scripts
        '''
        # register start time
        t0 = time.time()
        # load image modules
        if load_modules:
            self.load_modules(lambda: self.select_scripts("lib"))
        # run parser scripts to extend extparser
        # those scripts should only extend the parser or produce error
        if run_parser:
            self.run_scripts("parser",
                             lambda: self.select_scripts("parser"),
                             "/",
                             {"parser": extparser})
        # call parser (again), with full options
        arrow("Parsing command line")
        # encode command line arguments to utf-8
        args = istools.argv()[1:]
        # catch exception in custom argparse action
        try:
            args = parser.parse_args(args=args)
        except Exception as e:
            raise ISError("Argument parser", e)
        # run setup scripts
        if run_setup:
            self.run_scripts("setup",
                             lambda: self.select_scripts("setup"),
                             "/",
                             {"namespace": args})
        # return the building time
        return int(time.time() - t0)

    def select_scripts(self, directory):
        '''
        Generator of tuples (fp,fn,fc) of scripts witch are allocatable
        in a tarball directory
        '''
        for fp in sorted(self._tarball.getnames(re_pattern="%s/.*\.py" % directory)):
            fn = os.path.basename(fp)
            # extract source code
            try:
                fc = self._tarball.get_str(fp)
            except Exception as e:
                raise ISError(u"Unable to extract script %s" % fp, e)
            # yield complet file path, file name and file content
            yield (fp, fn, fc)


class Payload(object):
    '''
    Payload class represents a payload object
    '''
    extension = ".isdata"
    legit_attr = ("isdir", "md5", "size", "uid", "gid", "mode", "mtime", "compressor")

    def __init__(self, name, filename, path, **kwargs):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "filename", filename)
        object.__setattr__(self, "path", path)
        # register legit param
        for attr in self.legit_attr:
            setattr(self, attr, None)
        # set all named param
        for kwarg in kwargs:
            # do not use hasattr which use getattr and so call md5 checksum...
            if kwarg in self.legit_attr:
                setattr(self, kwarg, kwargs[kwarg])

    def __getattr__(self, name):
        # get all value with an understance as if there is no underscore
        if hasattr(self, u"_%s" % name):
            return getattr(self, u"_%s" % name)
        raise AttributeError

    def __setattr__(self, name, value):
        # set all value which exists have no underscore, but where underscore exists
        if name in self.legit_attr:
            object.__setattr__(self, u"_%s" % name, value)
        else:
            object.__setattr__(self, name, value)

    def checksummize(self):
        '''
        Fill missing md5/size about payload
        '''
        fileobj = PipeFile(self.path, "r")
        fileobj.consume()
        fileobj.close()
        if self._size is None:
            self._size = fileobj.read_size
        if self._md5 is None:
            self._md5 = fileobj.md5

    @property
    def md5(self):
        '''
        Return md5 of payload
        '''
        if self._md5 is None:
            self.checksummize()
        return self._md5

    @property
    def size(self):
        '''
        Return size of payload
        '''
        if self._size is None:
            self.checksummize()
        return self._size

    @property
    def uid(self):
        '''
        Return uid of owner of orginal payload
        '''
        return self._uid if self._uid is not None else 0

    @property
    def gid(self):
        '''
        Return gid of owner of orginal payload
        '''
        return self._gid if self._gid is not None else 0

    @property
    def mode(self):
        '''
        Return mode of orginal payload
        '''
        if self._mode is not None:
            return self._mode
        else:
            umask = os.umask(0)
            os.umask(umask)
            return 0666 & ~umask

    @property
    def mtime(self):
        '''
        Return last modification time of orginal payload
        '''
        return self._mtime if self._mtime is not None else time.time()

    @property
    def compressor(self):
        '''
        Return payload compress format
        '''
        return self._compressor if self._compressor is not None else Image.default_compressor

    @property
    def info(self):
        '''
        Return a dict of info about current payload
        Auto calculated info like name and filename must not be here
        '''
        return {"md5": self.md5,
                "size": self.size,
                "isdir": self.isdir,
                "uid": self.uid,
                "gid": self.gid,
                "mode": self.mode,
                "mtime": self.mtime}

    def check(self):
        '''
        Check that path correspond to current md5 and size
        '''
        if self._size is None or self._md5 is None:
            debug("Check is called on payload with nothing to check")
            return True
        fileobj = PipeFile(self.path, "r")
        fileobj.consume()
        fileobj.close()
        if self._size != fileobj.read_size:
            raise ISError(u"Invalid size of payload %s" % self.name)
        if self._md5 != fileobj.md5:
            raise ISError(u"Invalid MD5 of payload %s" % self._md5)

    def download(self, dest, force=False):
        '''
        Download payload in directory
        '''
        # if dest is a directory try to create file inside
        if os.path.isdir(dest):
            dest = os.path.join(dest, self.filename)
        # try to create leading directories
        elif not os.path.exists(os.path.dirname(dest)):
            istools.mkdir(os.path.dirname(dest))
        # check validity of dest
        if os.path.exists(dest):
            if os.path.isdir(dest):
                raise ISError(u"Destination %s is a directory" % dest)
            if not force:
                raise ISError(u"File %s already exists" % dest)
        # open remote file
        debug(u"Downloading payload %s from %s" % (self.filename, self.path))
        fs = PipeFile(self.path, progressbar=True)
        # check if announced file size is good
        if fs.size is not None and self.size != fs.size:
            raise ISError(u"Downloading payload %s failed: Invalid announced size" %
                            self.name)
        fd = open(dest, "wb")
        fs.consume(fd)
        # closing fo
        fs.close()
        fd.close()
        # checking download size
        if self.size != fs.read_size:
            raise ISError(u"Downloading payload %s failed: Invalid size" % self.name)
        if self.md5 != fs.md5:
            raise ISError(u"Downloading payload %s failed: Invalid MD5" % self.name)

    def extract(self, dest, force=False, filelist=None):
        '''
        Extract payload into dest
        filelist is a filter of file in tarball
        force will overwrite existing file if exists
        '''
        try:
            if self.isdir:
                self.extract_tar(dest, force=force, filelist=filelist)
            else:
                self.extract_file(dest, force=force)
        except Exception as e:
            raise ISError(u"Extracting payload %s failed" % self.name, e)

    def extract_tar(self, dest, force=False, filelist=None):
        '''
        Extract a payload which is a tarball.
        This is used mainly to extract payload from a directory
        '''
        # check validity of dest
        if os.path.exists(dest):
            if not os.path.isdir(dest):
                raise ISError(u"Destination %s is not a directory" % dest)
            if not force and len(os.listdir(dest)) > 0:
                raise ISError(u"Directory %s is not empty (need force)" % dest)
        else:
            istools.mkdir(dest)
        # try to open payload file
        try:
            fo = PipeFile(self.path, progressbar=True)
        except Exception as e:
            raise ISError(u"Unable to open %s" % self.path)
        # check if announced file size is good
        if fo.size is not None and self.size != fo.size:
            raise ISError(u"Invalid announced size on %s" % self.path)
        # get compressor argv (first to escape file creation if not found)
        a_comp = istools.get_compressor_path(self.compressor, compress=False)
        a_tar = ["tar", "--extract", "--numeric-owner", "--ignore-zeros",
                 "--preserve-permissions", "--directory", dest]
        # add optionnal selected filename for decompression
        if filelist is not None:
            a_tar += filelist
        p_tar = subprocess.Popen(a_tar, shell=False, close_fds=True,
                                 stdin=subprocess.PIPE)
        p_comp = subprocess.Popen(a_comp, shell=False, close_fds=True,
                                  stdin=subprocess.PIPE, stdout=p_tar.stdin)
        # close tar fd
        p_tar.stdin.close()
        # push data into compressor
        fo.consume(p_comp.stdin)
        # close source fd
        fo.close()
        # checking downloaded size
        if self.size != fo.read_size:
            raise ISError("Invalid size")
        # checking downloaded md5
        if self.md5 != fo.md5:
            raise ISError("Invalid MD5")
        # close compressor pipe
        p_comp.stdin.close()
        # check compressor return 0
        if p_comp.wait() != 0:
            raise ISError(u"Compressor %s return is not zero" % a_comp[0])
        # check tar return 0
        if p_tar.wait() != 0:
            raise ISError("Tar return is not zero")

    def extract_file(self, dest, force=False):
        '''
        Copy a payload directly to a file
        Check md5 on the fly
        '''
        # if dest is a directory try to create file inside
        if os.path.isdir(dest):
            dest = os.path.join(dest, self.name)
        # try to create leading directories
        elif not os.path.exists(os.path.dirname(dest)):
            istools.mkdir(os.path.dirname(dest))
        # check validity of dest
        if os.path.exists(dest):
            if os.path.isdir(dest):
                raise ISError(u"Destination %s is a directory" % dest)
            if not force:
                raise ISError(u"File %s already exists" % dest)
        # get compressor argv (first to escape file creation if not found)
        a_comp = istools.get_compressor_path(self.compressor, compress=False)
        # try to open payload file (source)
        try:
            f_src = PipeFile(self.path, "r", progressbar=True)
        except Exception as e:
            raise ISError(u"Unable to open payload file %s" % self.path, e)
        # check if announced file size is good
        if f_src.size is not None and self.size != f_src.size:
            raise ISError(u"Invalid announced size on %s" % self.path)
        # opening destination
        try:
            f_dst = open(dest, "wb")
        except Exception as e:
            raise ISError(u"Unable to open destination file %s" % dest, e)
        # run compressor process
        p_comp = subprocess.Popen(a_comp, shell=False, close_fds=True,
                                  stdin=subprocess.PIPE, stdout=f_dst)
        # close destination file
        f_dst.close()
        # push data into compressor
        f_src.consume(p_comp.stdin)
        # closing source fo
        f_src.close()
        # checking download size
        if self.size != f_src.read_size:
            raise ISError("Invalid size")
        # checking downloaded md5
        if self.md5 != f_src.md5:
            raise ISError("Invalid MD5")
        # close compressor pipe
        p_comp.stdin.close()
        # check compressor return 0
        if p_comp.wait() != 0:
            raise ISError(u"Compressor %s return is not zero" % a_comp[0])
        # settings file orginal rights
        istools.chrights(dest, self.uid, self.gid, self.mode, self.mtime)


class Changelog(dict):
    '''
    Object representing a changelog in memory
    '''
    def __init__(self, data):
        self.verbatim = u""
        self.load(data)

    def load(self, data):
        '''
        Load a changelog file
        '''
        # ensure data are correct UTF-8
        if isinstance(data, str):
            try:
                data = unicode(data, "UTF-8")
            except UnicodeDecodeError:
                raise ISError("Invalid character encoding in changelog")
        version = None
        lines = data.split("\n")
        for line in lines:
            # ignore empty lines
            if len(line.strip()) == 0:
                continue
            # ignore comments
            if line.lstrip().startswith("#"):
                continue
            # try to match a new version
            m = re.match("\[(\d+(?:\.\d+)*)(?:([~+]).*)?\]", line.lstrip())
            if m is not None:
                version = m.group(1)
                self[version] = []
                continue
            # if line are out of a version => invalid format
            if version is None:
                raise ISError("Invalid format: Line outside version")
            # add line to version changelog
            self[version] += [line]
        # save original
        self.verbatim = data

    def show(self, version=None):
        '''
        Show changelog for a given version
        '''
        assert(isinstance(version, unicode))
        # if no version take the hightest
        if version is None:
            version = max(self, istools.strvercmp)
        # display asked version
        if version in self:
            out(os.linesep.join(self[version]))

    def show_all(self):
        '''
        Show changelog for all versions
        '''
        for ver in sorted(self, istools.strvercmp,  reverse=True):
            out(u'-- #purple#version:#reset# %s' % ver)
            out(os.linesep.join(self[ver]))
