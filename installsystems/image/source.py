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
Source image module
'''


from configobj import ConfigObj, flatten_errors
from installsystems import VERSION
from installsystems.exception import ISError, InvalidSourceImage
from installsystems.image.changelog import Changelog
from installsystems.image.image import Image
from installsystems.image.payload import Payload
from installsystems.image.tarball import Tarball, REGTYPE
from installsystems.printer import arrow, arrowlevel, warn, error
from installsystems.tools import PipeFile, islocal, get_compressor_path, chrights
from json import dumps
from locale import getpreferredencoding
from os import stat, listdir, mkdir, umask, access, unlink, symlink, R_OK, X_OK
from os.path import join, exists, isdir, abspath, lexists, basename
from re import match
from stat import S_ISDIR, S_IMODE
from subprocess import Popen, PIPE
from time import time
from validate import Validator

# use module prefix because function is named open
import codecs
# use module prefix because function is named filter
import fnmatch


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
        if not islocal(path):
            raise NotImplementedError("SourceImage must be local")
        # main path
        build_path = join(path, "build")
        parser_path = join(path, "parser")
        setup_path = join(path, "setup")
        payload_path = join(path, "payload")
        lib_path = join(path, "lib")
        # create base directories
        arrow("Creating base directories")
        try:
            for d in (path, build_path, parser_path, setup_path, payload_path,
                      lib_path):
                if not exists(d) or not isdir(d):
                    mkdir(d)
        except Exception as e:
            raise ISError(u"Unable to create directory: %s" % d, e)
        # create example files
        arrow("Creating examples")
        arrowlevel(1)
        # create dict of file to create
        examples = {}
        # create description example from template
        examples["description"] = {
            "path": "description",
            "content": DESCRIPTION_TPL % {
                "name": "",
                "version": "1",
                "description": "",
                "author": "",
                "is_min_version": VERSION,
                "compressor": "gzip = *\nnone = *.gz, *.bz2, *.xz"}
        }
        # create changelog example from template
        examples["changelog"] = {"path": "changelog", "content": CHANGELOG_TPL}
        # create build example from template
        examples["build"] = {"path": "build/01-build.py", "content": BUILD_TPL}
        # create parser example from template
        examples["parser"] = {"path": "parser/01-parser.py", "content": PARSER_TPL}
        # create setup example from template
        examples["setup"] = {"path": "setup/01-setup.py", "content": SETUP_TPL}
        for name in examples:
            try:
                arrow(u"Creating %s example" % name)
                expath = join(path, examples[name]["path"])
                if not force and exists(expath):
                    warn(u"%s already exists. Skipping!" % expath)
                    continue
                open(expath, "w").write(examples[name]["content"])
            except Exception as e:
                raise ISError(u"Unable to create example file", e)
        try:
            # setting executable rights on files in setup and parser
            arrow("Setting executable rights on scripts")
            oldmask = umask(0)
            umask(oldmask)
            for dpath in (build_path, parser_path, setup_path):
                for f in listdir(dpath):
                    chrights(join(dpath, f), mode=0777 & ~oldmask)
        except Exception as e:
            raise ISError(u"Unable to set rights", e)
        arrowlevel(-1)

    def __init__(self, path):
        '''
        Initialize source image
        '''
        Image.__init__(self)
        # check local repository
        if not islocal(path):
            raise NotImplementedError("SourceImage must be local")
        self.base_path = abspath(path)
        for pathtype in ("build", "parser", "setup", "payload", "lib"):
            setattr(self, u"%s_path" % pathtype, join(self.base_path, pathtype))
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
        if not exists(self.setup_path):
            raise InvalidSourceImage(u"setup directory is missing.")
        # Ensure description exists
        if not exists(join(self.base_path, u"description")):
            raise InvalidSourceImage(u"no description file.")
        # Ensure payload directory exists if there is build directory
        if not exists(self.payload_path) and exists(self.build_path):
            raise InvalidSourceImage(u"payload directory is mandatory with a build directory.")
        # Ensure directories are directories and accessible
        for d in (self.base_path, self.build_path, self.parser_path,
                  self.setup_path, self.payload_path, self.lib_path):
            if exists(d):
                if not isdir(d):
                    raise InvalidSourceImage(u"%s is not a directory." % d)
                if not access(d, R_OK|X_OK):
                    raise InvalidSourceImage(u"unable to access to %s." % d)

    def build(self, force=False, force_payload=False, check=True, script=True):
        '''
        Create packaged image
        '''
        # check if free to create script tarball
        if exists(self.image_name):
            if force:
                unlink(self.image_name)
            else:
                raise ISError("Tarball already exists. Remove it before")
        # register start time
        t0 = time()
        # check python scripts
        if check:
            for d in (self.build_path, self.parser_path, self.setup_path,
                      self.lib_path):
                if exists(d):
                    self.check_scripts(d)
        # load modules
        self.load_modules(lambda: self.select_scripts(self.lib_path))
        # remove list
        rl = set()
        # run build script
        if script and exists(self.build_path):
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
        return int(time() - t0)

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
            tarball.add_str("description.json", jdescription, REGTYPE, 0644)
            # add changelog
            if self.changelog is not None:
                arrow("Add changelog")
                tarball.add_str("changelog", self.changelog.verbatim, REGTYPE, 0644)
            # add format
            arrow("Add format")
            tarball.add_str("format", self.format, REGTYPE, 0644)
            # add setup scripts
            self.add_scripts(tarball, self.setup_path)
            # add optional scripts
            for d in (self.build_path, self.parser_path, self.lib_path):
                if exists(d):
                    self.add_scripts(tarball, d)
            # closing tarball file
            tarball.close()
        except (SystemExit, KeyboardInterrupt):
            if exists(self.image_name):
                unlink(self.image_name)
        arrowlevel(-1)

    def describe_payload(self, name):
        '''
        Return information about a payload
        '''
        ans = {}
        ans["source_path"] = join(self.payload_path, name)
        ans["dest_path"] = u"%s-%s%s" % (self.description["name"],
                                         name,
                                         Payload.extension)
        ans["link_path"] = u"%s-%s-%s%s" % (self.description["name"],
                                            self.description["version"],
                                            name,
                                            Payload.extension)
        source_stat = stat(ans["source_path"])
        ans["isdir"] = S_ISDIR(source_stat.st_mode)
        ans["uid"] = source_stat.st_uid
        ans["gid"] = source_stat.st_gid
        ans["mode"] = S_IMODE(source_stat.st_mode)
        ans["mtime"] = source_stat.st_mtime
        ans["compressor"] = self.compressor(name)
        return ans

    def select_payloads(self):
        '''
        Return a generator on image payloads
        '''
        if not isdir(self.payload_path):
            raise StopIteration()
        for payname in listdir(self.payload_path):
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
                if lexists(f):
                    unlink(f)

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
            if exists(paydesc["link_path"]):
                continue
            arrow(payload_name, 1)
            try:
                # create non versionned payload file
                if not exists(paydesc["dest_path"]):
                    if paydesc["isdir"]:
                        self.create_payload_tarball(paydesc["dest_path"],
                                                    paydesc["source_path"],
                                                    paydesc["compressor"])
                    else:
                        self.create_payload_file(paydesc["dest_path"],
                                                 paydesc["source_path"],
                                                 paydesc["compressor"])
                # create versionned payload file
                if lexists(paydesc["link_path"]):
                    unlink(paydesc["link_path"])
                symlink(paydesc["dest_path"], paydesc["link_path"])
            except Exception as e:
                # cleaning file in case of error
                if exists(paydesc["dest_path"]):
                    unlink(paydesc["dest_path"])
                if lexists(paydesc["link_path"]):
                    unlink(paydesc["link_path"])
                raise ISError(u"Unable to create payload %s" % payload_name, e)

    def create_payload_tarball(self, tar_path, data_path, compressor):
        '''
        Create a payload tarball
        '''
        try:
            # get compressor argv (first to escape file creation if not found)
            a_comp = get_compressor_path(compressor, compress=True)
            a_tar = ["tar", "--create", "--numeric-owner", "--directory",
                     data_path, "."]
            # create destination file
            f_dst = PipeFile(tar_path, "w", progressbar=True)
            # run tar process
            p_tar = Popen(a_tar, shell=False, close_fds=True,
                          stdout=PIPE)
            # run compressor process
            p_comp = Popen(a_comp, shell=False, close_fds=True,
                           stdin=p_tar.stdout, stdout=PIPE)
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
            if exists(tar_path):
                unlink(tar_path)
            raise

    def create_payload_file(self, dest, source, compressor):
        '''
        Create a payload file
        '''
        try:
            # get compressor argv (first to escape file creation if not found)
            a_comp = get_compressor_path(compressor, compress=True)
            # open source file
            f_src = open(source, "r")
            # create destination file
            f_dst = PipeFile(dest, "w", progressbar=True)
            # run compressor
            p_comp = Popen(a_comp, shell=False, close_fds=True,
                           stdin=f_src, stdout=PIPE)
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
            if exists(dest):
                unlink(dest)
            raise

    def select_scripts(self, directory):
        '''
        Generator of tuples (fp,fn,fc) of scripts witch are allocatable
        in a real directory
        '''
        # ensure directory is unicode to have fn and fp in unicode
        if not isinstance(directory, unicode):
            directory = unicode(directory, getpreferredencoding())
        if not exists(directory):
            return
        for fn in sorted(listdir(directory)):
            fp = join(directory, fn)
            # check name
            if not match("^\d+-.*\.py$", fn):
                continue
            # check execution bit
            if not access(fp, X_OK):
                continue
            # get module content
            try:
                fc = open(fp, "r").read()
            except Exception as e:
                raise ISError(u"Unable to read script %s" % fp, e)
            # yield complet file path, file name and file content
            yield (fp, fn, fc)

    def add_scripts(self, tarball, directory):
        '''
        Add scripts inside a directory into a tarball
        '''
        basedirectory = basename(directory)
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
            tarball.add_str(join(basedirectory, fn),
                            fc,
                            REGTYPE,
                            0755,
                            int(stat(fp).st_mtime))
            arrow(u"%s added" % fn)
        arrowlevel(-1)

    def check_scripts(self, directory):
        '''
        Check if scripts inside a directory can be compiled
        '''
        basedirectory = basename(directory)
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
                compile(fc, fn.encode(getpreferredencoding()), "exec")
            except SyntaxError as e:
                raise ISError(exception=e)
        arrowlevel(-1)

    def run_build(self):
        '''
        Run build scripts
        '''
        rebuild_list = []
        self.run_scripts(basename(self.build_path),
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
        desc["date"] = int(time())
        # watermark
        desc["is_build_version"] = VERSION
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
        return dumps(desc)

    def parse_description(self):
        '''
        Raise an exception is description file is invalid and return vars to include
        '''
        arrow("Parsing description")
        d = dict()
        try:
            descpath = join(self.base_path, "description")
            cp = ConfigObj(descpath,
                                     configspec=DESCRIPTION_CONFIG_SPEC.splitlines(),
                                     encoding="utf8", file_error=True)
            res = cp.validate(Validator({"IS_name": Image.check_name,
                                         "IS_version": Image.check_version,
                                         "IS_min_version": Image.check_min_version}),
                              preserve_errors=True)
            # If everything is fine, the validation return True
            # Else, it returns a list of (section, optname, error)
            if res is not True:
                for section, optname, err in flatten_errors(cp, res):
                    # If error, the check has failed
                    if err:
                        error(u"Wrong description file, %s %s: %s" % (section, optname, err))
                    # Else, no value has been supplied and there is no default value
                    else:
                        error(u"No option '%s' in section '%s'" % (optname, section[0]))
            for n in ("name", "version", "description", "author", "is_min_version"):
                d[n] = cp["image"][n]
            d["compressor"] = {}
            # set payload compressor
            d["compressor"]["patterns"] = cp["compressor"].items()
            if not d["compressor"]["patterns"]:
                d["compressor"]["patterns"] = [(Image.default_compressor, "*")]
            for compressor, patterns in cp["compressor"].items():
                # is a valid compressor?
                get_compressor_path(compressor)
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
            path = join(self.base_path, "changelog")
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


DESCRIPTION_TPL = u"""[image]
name = %(name)s
version = %(version)s
description = %(description)s
author = %(author)s
is_min_version = %(is_min_version)s

[compressor]
%(compressor)s
"""

CHANGELOG_TPL = u"""[1]
- Initial version
"""

BUILD_TPL = u"""# -*- python -*-
# -*- coding: utf-8 -*-

# global rebuild object allow you to force rebuild of payloads
# to force rebuild of payload nammed rootfs add it to the rebuild list
# rebuild list is empty by default
#rebuild += ["rootfs"]

# vim:set ts=4 sw=4 et:
"""

PARSER_TPL = u"""# -*- python -*-
# -*- coding: utf-8 -*-

# global image object is a reference to current image
# global parser object is your installsystems subparser (argparse)

# you can use exit() to break the execution of the script

import os
import argparse
from installsystems.printer import arrow

class TargetAction(argparse.Action):
  def __call__(self, parser, namespace, values, option_string=None):
    if not os.path.isdir(values):
      raise Exception(u"Invalid target directory %s" % values)
    namespace.target = values

parser.add_argument("-n", "--hostname", dest="hostname", type=str, required=True)
parser.add_argument("target", type=str, action=TargetAction,
  help="target installation directory")

# vim:set ts=4 sw=4 et:
"""

SETUP_TPL = u"""# -*- python -*-
# -*- coding: utf-8 -*-

# global image object is a reference to current image
# namespace object is the persistant, it can be used to store data accross scripts

# you can use exit() to break the execution of the script

from installsystems.printer import arrow

arrow(u"hostname: %s" % namespace.hostname)

# uncomment to extract payload named root in namespace.target directory
#image.payload["rootfs"].extract(namespace.target)

# vim:set ts=4 sw=4 et:
"""

# This must not be an unicode string, because configobj don't decode configspec
# with the provided encoding
DESCRIPTION_CONFIG_SPEC = """\
[image]
name = IS_name
version = IS_version
description = string(default='')
author = string(default='')
is_min_version = IS_min_version(default=0)

[compressor]
__many__ = force_list
"""
