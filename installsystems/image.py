# -*- python -*-
# -*- coding: utf-8 -*-
# Started 10/05/2011 by Seblu <seblu@seblu.net>

'''
Image stuff
'''

import ConfigParser
import cStringIO
import difflib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import tarfile
import time
import installsystems
import installsystems.template as istemplate
import installsystems.tools as istools
from installsystems.printer import *
from installsystems.tools import PipeFile
from installsystems.tarball import Tarball


class Image(object):
    '''
    Abstract class of images
    '''

    # format should be a float  X.Y but for compatibility reason it's a string
    # before version 6, it's strict string comparaison
    format = "1"
    extension = ".isimage"

    @staticmethod
    def check_image_name(buf):
        '''
        Check if @buf is a valid image name
        '''
        if re.match("^[-_\w]+$", buf) is None:
            raise Exception("Invalid image name %s" % buf)

    @staticmethod
    def check_image_version(buf):
        '''
        Check if @buf is a valid image version
        '''
        if re.match("^\d+$", buf) is None:
            raise Exception("Invalid image version %s" % buf)

    @staticmethod
    def compare_versions(v1, v2):
        '''
        For backward compatibility, image class offer a method to compare image versions
        But code is now inside tools
        '''
        return istools.compare_versions(v1, v2)

class SourceImage(Image):
    '''
    Image source manipulation class
    '''

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
        # create base directories
        arrow("Creating base directories")
        try:
            for d in (path, build_path, parser_path, setup_path, payload_path):
                if not os.path.exists(d) or not os.path.isdir(d):
                    os.mkdir(d)
        except Exception as e:
            raise Exception("Unable to create directory: %s: %s" % (d, e))
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
                "is_min_version": installsystems.version}}
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
                arrow("Creating %s example" % name)
                expath = os.path.join(path, examples[name]["path"])
                if not force and os.path.exists(expath):
                    warn("%s already exists. Skipping!" % expath)
                    continue
                open(expath, "w").write(examples[name]["content"])
            except Exception as e:
                raise Exception("Unable to create example file: %s" % e)
        try:
            # setting executable rights on files in setup and parser
            arrow("Setting executable rights on scripts")
            umask = os.umask(0)
            os.umask(umask)
            for dpath in (build_path, parser_path, setup_path):
                for f in os.listdir(dpath):
                    istools.chrights(os.path.join(dpath, f), mode=0777 & ~umask)
        except Exception as e:
            raise Exception("Unable to set rights on %s: %s" % (pf, e))
        arrowlevel(-1)

    def __init__(self, path):
        # check local repository
        if not istools.isfile(path):
            raise NotImplementedError("SourceImage must be local")
        Image.__init__(self)
        self.base_path = os.path.abspath(path)
        for pathtype in ("build", "parser", "setup", "payload"):
            setattr(self, "%s_path" % pathtype, os.path.join(self.base_path, pathtype))
        self.check_source_image()
        self.description = self.parse_description()
        self.changelog = self.parse_changelog()
        # script tarball path
        self.image_name = "%s-%s%s" % (self.description["name"],
                                       self.description["version"],
                                       self.extension)

    def check_source_image(self):
        '''
        Check if we are a valid SourceImage directories
        '''
        for d in (self.base_path, self.build_path, self.parser_path,
                  self.setup_path, self.payload_path):
            if not os.path.exists(d):
                raise Exception("Invalid source image: directory %s is missing" % d)
            if not os.path.isdir(d):
                raise Exception("Invalid source image: %s is not a directory" % d)
            if not os.access(d, os.R_OK|os.X_OK):
                raise Exception("Invalid source image: unable to access to %s" % d)
        if not os.path.exists(os.path.join(self.base_path, "description")):
            raise Exception("Invalid source image: no description file")

    def build(self, force=False, force_payload=False, check=True, script=True):
        '''
        Create packaged image
        '''
        # check if free to create script tarball
        if os.path.exists(self.image_name) and force == False:
            raise Exception("Tarball already exists. Remove it before")
        # check python scripts
        if check:
            self.check_scripts(self.build_path)
            self.check_scripts(self.parser_path)
            self.check_scripts(self.setup_path)
        # remove list
        rl = set()
        # run build script
        if script:
            rl |= set(self.run_scripts(self.build_path, self.payload_path))
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

    def create_image(self, jdescription):
        '''
        Create a script tarball in current directory
        '''
        # create tarball
        arrow("Creating image tarball")
        arrowlevel(1)
        arrow("Name %s" % self.image_name)
        try:
            try:
                tarball = Tarball.open(self.image_name, mode="w:gz", dereference=True)
            except Exception as e:
                raise Exception("Unable to create tarball %s: %s" % (self.image_name, e))
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
            # add build scripts
            self.add_scripts(tarball, self.build_path)
            # add parser scripts
            self.add_scripts(tarball, self.parser_path)
            # add setup scripts
            self.add_scripts(tarball, self.setup_path)
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
        ans["dest_path"] = "%s-%s%s" % (self.description["name"],
                                        name,
                                        Payload.extension)
        ans["link_path"] = "%s-%s-%s%s" % (self.description["name"],
                                           self.description["version"],
                                           name,
                                           Payload.extension)
        source_stat = os.stat(ans["source_path"])
        ans["isdir"] = stat.S_ISDIR(source_stat.st_mode)
        ans["uid"] = source_stat.st_uid
        ans["gid"] = source_stat.st_gid
        ans["mode"] = stat.S_IMODE(source_stat.st_mode)
        ans["mtime"] = source_stat.st_mtime
        return ans

    def select_payloads(self):
        '''
        Return a generator on image payloads
        '''
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
                                                    paydesc["source_path"])
                    else:
                        self.create_payload_file(paydesc["dest_path"],
                                                 paydesc["source_path"])
                # create versionned payload file
                if os.path.lexists(paydesc["link_path"]):
                    os.unlink(paydesc["link_path"])
                os.symlink(paydesc["dest_path"], paydesc["link_path"])
            except Exception as e:
                raise Exception("Unable to create payload %s: %s" % (payload_name, e))

    def create_payload_tarball(self, tar_path, data_path):
        '''
        Create a payload tarball
        '''
        try:
            # get compressor argv (first to escape file creation if not found)
            a_comp = istools.get_compressor_path(self.compressor, compress=True)
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
                raise Exception("Tar return is not zero")
            # check compressor return 0
            if p_comp.wait() != 0:
                raise Exception("Compressor %s return is not zero" % a_comp[0])
        except (SystemExit, KeyboardInterrupt):
            if os.path.exists(tar_path):
                os.unlink(tar_path)
            raise

    def create_payload_file(self, dest, source):
        '''
        Create a payload file
        '''
        try:
            # get compressor argv (first to escape file creation if not found)
            a_comp = istools.get_compressor_path(self.compressor, compress=True)
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
                raise Exception("Compressor %s return is not zero" % a_comp[0])
        except (SystemExit, KeyboardInterrupt):
            if os.path.exists(dest):
                os.unlink(dest)
            raise

    def add_scripts(self, tarball, directory):
        '''
        Add scripts inside a directory into a tarball
        '''
        basedirectory = os.path.basename(directory)
        arrow("Add %s scripts" % basedirectory)
        arrowlevel(1)
        # adding base directory
        ti = tarball.gettarinfo(directory, arcname=basedirectory)
        ti.mode = 0755
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = "root"
        tarball.addfile(ti)
        # adding each file
        for fp, fn in self.select_scripts(directory):
            ti = tarball.gettarinfo(fp, arcname=os.path.join(basedirectory, fn))
            ti.mode = 0755
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = "root"
            tarball.addfile(ti, open(fp, "rb"))
            arrow("%s added" % fn)
        arrowlevel(-1)

    def check_scripts(self, directory):
        '''
        Check if scripts inside a directory can be compiled
        '''
        basedirectory = os.path.basename(directory)
        arrow("Checking %s scripts" % basedirectory)
        arrowlevel(1)
        # checking each file
        for fp, fn in self.select_scripts(directory):
            # compiling file
            fs = open(fp, "r").read()
            compile(fs, fp, mode="exec")
            arrow(fn)
        arrowlevel(-1)

    def run_scripts(self, script_directory, exec_directory):
        '''
        Execute script inside a directory
        Return a list of payload to force rebuild
        '''
        arrow("Run %s scripts" % os.path.basename(script_directory))
        rebuild_list = []
        cwd = os.getcwd()
        arrowlevel(1)
        for fp, fn in self.select_scripts(script_directory):
            arrow(fn)
            os.chdir(exec_directory)
            old_level = arrowlevel(1)
            # compile source code
            try:
                o_scripts = compile(open(fp, "r").read(), fn, "exec")
            except Exception as e:
                raise Exception("Unable to compile %s fail: %s" %
                                (fn, e))
            # define execution context
            gl = {"rebuild": rebuild_list}
            # execute source code
            try:
                exec o_scripts in gl
            except Exception as e:
                raise Exception("Execution script %s fail: %s" %
                                (fn, e))
            arrowlevel(level=old_level)
        os.chdir(cwd)
        arrowlevel(-1)
        return rebuild_list

    def select_scripts(self, directory):
        '''
        Select script with are allocatable in a directory
        '''
        for fn in sorted(os.listdir(directory)):
            fp = os.path.join(directory, fn)
            # check name
            if not re.match("\d+-.*\.py$", fn):
                continue
            # check execution bit
            if not os.access(fp, os.X_OK):
                continue
            # yield complet filepath and only script name
            yield fp, fn

    def generate_json_description(self):
        '''
        Generate a JSON description file
        '''
        arrow("Generating JSON description")
        arrowlevel(1)
        # copy description
        desc = self.description.copy()
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
                "mtime": payload_desc["mtime"]
                }
        # check md5 are uniq
        md5s = [v["md5"] for v in desc["payload"].values()]
        if len(md5s) != len(set(md5s)):
            raise Exception("Two payloads cannot have the same md5")
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
            cp = ConfigParser.RawConfigParser()
            cp.read(descpath)
            for n in ("name","version", "description", "author"):
                d[n] = cp.get("image", n)
            # get min image version
            if cp.has_option("image", "is_min_version"):
                d["is_min_version"] = cp.get("image", "is_min_version")
            else:
                d["is_min_version"] = 0
            # check image name
            self.check_image_name(d["name"])
            # check image version
            self.check_image_version(d["version"])
            # check installsystems min version
            if self.compare_versions(installsystems.version, d["is_min_version"]) < 0:
                raise Exception("Minimum Installsystems version not satisfied")
        except Exception as e:
            raise Exception("Bad description: %s" % e)
        return d

    def parse_changelog(self):
        '''
        Create a changelog object from a file
        '''
        # try to find a changelog file
        try:
            path = os.path.join(self.base_path, "changelog")
            fo = open(path, "r")
        except IOError:
            return None
        # we have it, we need to check everything is ok
        arrow("Parsing changelog")
        try:
            cl = Changelog(fo.read())
        except Exception as e:
            raise Exception("Bad changelog: %s" % e)
        return cl

    @property
    def compressor(self):
        '''
        Return image compressor
        '''
        # currently only support gzip
        return "gzip"


class PackageImage(Image):
    '''
    Packaged image manipulation class
    '''

    @classmethod
    def diff(cls, pkg1, pkg2):
        '''
        Diff two packaged images
        '''
        arrow("Differnce from images #y#%s v%s#R# to #r#%s v%s#R#:" % (pkg1.name,
                                                                       pkg1.version,
                                                                       pkg2.name,
                                                                       pkg2.version))
        # Extract images for diff scripts files
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
                   out("#g#%s#R#" % line, endl="")
                elif line.startswith("-"):
                   out("#r#%s#R#" % line, endl="")
                elif line.startswith("@@"):
                   out("#c#%s#R#" % line, endl="")
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
            # get donwloaded size and md5
            self.size = fileobj.read_size
            self.md5 = fileobj.md5
            memfile.seek(0)
            self._tarball = Tarball.open(fileobj=memfile, mode='r:gz')
        except Exception as e:
            raise Exception("Unable to open image %s: %s" % (path, e))
        self._metadata = self.read_metadata()
        # print info
        arrow("Image %s v%s loaded" % (self.name, self.version))
        arrow("Author: %s" % self.author, 1)
        arrow("Date: %s" % istools.time_rfc2822(self.date), 1)
        # build payloads info
        self.payload = {}
        for pname, pval in self._metadata["payload"].items():
            pfilename = "%s-%s%s" % (self.filename[:-len(Image.extension)],
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
        return "%s-%s%s" % (self.name, self.version, self.extension)

    def read_metadata(self):
        '''
        Parse tarball and return metadata dict
        '''
        desc = {}
        # check format
        img_format = self._tarball.get_str("format")
        try:
            if float(img_format) >= math.floor(float(self.format)) + 1.0:
                raise Exception()
        except:
            raise Exception("Invalid image format %s" % img_format)
        desc["format"] = img_format
        # check description
        try:
            img_desc = self._tarball.get_str("description.json")
            desc.update(json.loads(img_desc))
            self.check_image_name(desc["name"])
            self.check_image_version(desc["version"])
            # add is_min_version if not present
            if "is_min_version" not in desc:
                desc["is_min_version"] = 0
            # check installsystems min version
            if self.compare_versions(installsystems.version, desc["is_min_version"]) < 0:
                raise Exception("Minimum Installsystems version not satisfied")
        except Exception as e:
            raise Exception("Invalid description: %s" % e)
        # try to load changelog
        try:
            img_changelog = self._tarball.get_str("changelog")
            desc["changelog"] = Changelog(img_changelog)
        except KeyError:
            desc["changelog"] = Changelog("")
        except Exception as e:
            warn("Invalid changelog: %s" % e)
        return desc

    def show(self, o_verbose=False, o_changelog=False, o_json=False):
        '''
        Display image content
        '''
        if o_json:
            out(json.dumps(self._metadata))
        else:
            out('#light##yellow#Name:#reset# %s' % self.name)
            out('#light##yellow#Version:#reset# %s' % self.version)
            out('#yellow#Date:#reset# %s' % istools.time_rfc2822(self.date))
            out('#yellow#Description:#reset# %s' % self.description)
            out('#yellow#Author:#reset# %s' % self.author)
            if o_verbose:
                # field is_build_version is new in version 5. I can be absent.
                try: out('#yellow#IS build version:#reset# %s' % self.is_build_version)
                except AttributeError: pass
                # field is_min_version is new in version 5. I can be absent.
                try: out('#yellow#IS minimum version:#reset# %s' % self.is_min_version)
                except AttributeError: pass
            out('#yellow#MD5:#reset# %s' % self.md5)
            if o_verbose:
                payloads = self.payload
                for payload_name in payloads:
                    payload = payloads[payload_name]
                    out('#light##yellow#Payload:#reset# %s' % payload_name)
                    out('  #yellow#Date:#reset# %s' % istools.time_rfc2822(payload.mtime))
                    out('  #yellow#Size:#reset# %s' % (istools.human_size(payload.size)))
                    out('  #yellow#MD5:#reset# %s' % payload.md5)
            # display image content
            out('#light##yellow#Content:#reset#')
            self._tarball.list(o_verbose)
            # display changelog
            if o_changelog:
                self.changelog.show(int(self.version), o_verbose)

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
            raise Exception("Invalid size of image %s" % self.name)
        if self.md5 != fo.md5:
            raise Exception("Invalid MD5 of image %s" % self.name)
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
            warn("No file matching %s" % filename)
        for filename in filelist:
            arrow(filename)
            out(self._tarball.get_str(filename))

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
                raise Exception("Image destination already exists: %s" % dest)
            # some display
            arrow("Downloading image in %s" % directory)
            debug("Downloading %s from %s" % (self.filename, self.path))
            # open source
            fs = PipeFile(self.path, progressbar=True)
            # check if announced file size is good
            if fs.size is not None and self.size != fs.size:
                raise Exception("Downloading image %s failed: Invalid announced size" % self.name)
            # open destination
            fd = open(self.filename, "wb")
            fs.consume(fd)
            fs.close()
            fd.close()
            if self.size != fs.consumed_size:
                raise Exception("Download image %s failed: Invalid size" % self.name)
            if self.md5 != fs.md5:
                raise Exception("Download image %s failed: Invalid MD5" % self.name)
        if payload:
            for payname in self.payload:
                arrow("Downloading payload %s in %s" % (payname, directory))
                self.payload[payname].info
                self.payload[payname].download(directory, force=force)

    def extract(self, directory, force=False, payload=False, gendescription=False):
        '''
        Extract content of the image inside a repository
        '''
        # check validity of dest
        if os.path.exists(directory):
            if not os.path.isdir(directory):
                raise Exception("Destination %s is not a directory" % directory)
            if not force and len(os.listdir(directory)) > 0:
                raise Exception("Directory %s is not empty (need force)" % directory)
        else:
            istools.mkdir(directory)
        # extract content
        arrow("Extracting image in %s" % directory)
        self._tarball.extractall(directory)
        # generate description file from description.json
        if gendescription:
            arrow("Generating description file in %s" % directory)
            with open(os.path.join(directory, "description"), "w") as f:
                f.write((istemplate.description % self._metadata).encode('utf-8'))
        # launch payload extraction
        if payload:
            for payname in self.payload:
                # here we need to decode payname which is in unicode to escape
                # tarfile to encode filename of file inside tarball inside unicode
                dest = os.path.join(directory, "payload", payname.encode("utf-8"))
                arrow("Extracting payload %s in %s" % (payname, dest))
                self.payload[payname].extract(dest, force=force)

    def run_parser(self, **kwargs):
        '''
        Run parser scripts
        '''
        self._run_scripts("parser", **kwargs)

    def run_setup(self, **kwargs):
        '''
        Run setup scripts
        '''
        self._run_scripts("setup", **kwargs)

    def _run_scripts(self, directory, **kwargs):
        '''
        Run scripts in a tarball directory
        '''
        arrow("Run %s scripts" % directory)
        arrowlevel(1)
        # get list of parser scripts
        l_scripts = self._tarball.getnames(re_pattern="%s/.*\.py" % directory)
        # order matter!
        l_scripts.sort()
        # run scripts
        for n_scripts in l_scripts:
            arrow(os.path.basename(n_scripts))
            old_level = arrowlevel(1)
            # extract source code
            try:
                s_scripts = self._tarball.get_str(n_scripts)
            except Exception as e:
                raise Exception("Extracting script %s fail: %s" %
                                (n_scripts, e))
            # compile source code
            try:
                o_scripts = compile(s_scripts, n_scripts, "exec")
            except Exception as e:
                raise Exception("Unable to compile %s fail: %s" %
                                (n_scripts, e))
            # define execution context
            gl = {}
            for k in kwargs:
                gl[k] = kwargs[k]
            gl["image"] = self
            # execute source code
            try:
                exec o_scripts in gl
            except Exception as e:
                raise Exception("Execution script %s fail: %s" %
                                (n_scripts, e))
            arrowlevel(level=old_level)
        arrowlevel(-1)


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
            # do not use hasattr which user getattr and so call md5 checksum...
            if kwarg in self.legit_attr:
                setattr(self, kwarg, kwargs[kwarg])

    def __getattr__(self, name):
        # get all value with an understance as if there is no underscore
        if hasattr(self, "_%s" % name):
            return getattr(self, "_%s" % name)
        raise AttributeError

    def __setattr__(self, name, value):
        # set all value which exists have no underscore, but where undesrcore exists
        if name in self.legit_attr:
            object.__setattr__(self, "_%s" % name, value)
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
        return self._compressor if self._compressor is not None else "gzip"

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
            raise Exception("Invalid size of payload %s" % self.name)
        if self._md5 != fileobj.md5:
            raise Exception("Invalid MD5 of payload %s" % self._md5)

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
                raise Exception("Destination %s is a directory" % dest)
            if not force:
                raise Exception("File %s already exists" % dest)
        # Open remote file
        debug("Downloading payload %s from %s" % (self.filename, self.path))
        fs = PipeFile(self.path, progressbar=True)
        # check if announced file size is good
        if fs.size is not None and self.size != fs.size:
            raise Exception("Downloading payload %s failed: Invalid announced size" %
                            self.name)
        fd = open(dest, "wb")
        fs.consume(fd)
        # closing fo
        fs.close()
        fd.close()
        # checking download size
        if self.size != fs.read_size:
            raise Exception("Downloading payload %s failed: Invalid size" % self.name)
        if self.md5 != fs.md5:
            raise Exception("Downloading payload %s failed: Invalid MD5" % self.name)

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
            raise Exception("Extracting payload %s failed: %s" % (self.name, e))

    def extract_tar(self, dest, force=False, filelist=None):
        '''
        Extract a payload which is a tarball.
        This is used mainly to extract payload from a directory
        '''
        # check validity of dest
        if os.path.exists(dest):
            if not os.path.isdir(dest):
                raise Exception("Destination %s is not a directory" % dest)
            if not force and len(os.listdir(dest)) > 0:
                raise Exception("Directory %s is not empty (need force)" % dest)
        else:
            istools.mkdir(dest)
        # try to open payload file
        try:
            fo = PipeFile(self.path, progressbar=True)
        except Exception as e:
            raise Exception("Unable to open %s" % self.path)
        # check if announced file size is good
        if fo.size is not None and self.size != fo.size:
            raise Exception("Invalid announced size on %s" % self.path)
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
            raise Exception("Invalid size")
        # checking downloaded md5
        if self.md5 != fo.md5:
            raise Exception("Invalid MD5")
        # close compressor pipe
        p_comp.stdin.close()
        # check compressor return 0
        if p_comp.wait() != 0:
            raise Exception("Compressor %s return is not zero" % a_comp[0])
        # check tar return 0
        if p_tar.wait() != 0:
            raise Exception("Tar return is not zero")

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
                raise Exception("Destination %s is a directory" % dest)
            if not force:
                raise Exception("File %s already exists" % dest)
        # get compressor argv (first to escape file creation if not found)
        a_comp = istools.get_compressor_path(self.compressor, compress=False)
        # try to open payload file (source)
        try:
            f_src = PipeFile(self.path, "r", progressbar=True)
        except Exception as e:
            raise Exception("Unable to open payload file %s: %s" % (self.path, e))
        # check if announced file size is good
        if f_src.size is not None and self.size != f_src.size:
            raise Exception("Invalid announced size on %s" % self.path)
        # opening destination
        try:
            f_dst = open(dest, "wb")
        except Exception as e:
            raise Exception("Unable to open destination file %s: %s" % (dest, e))
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
            raise Exception("Invalid size")
        # checking downloaded md5
        if self.md5 != f_src.md5:
            raise Exception("Invalid MD5")
        # close compressor pipe
        p_comp.stdin.close()
        # check compressor return 0
        if p_comp.wait() != 0:
            raise Exception("Compressor %s return is not zero" % a_comp[0])
        # settings file orginal rights
        istools.chrights(dest, self.uid, self.gid, self.mode, self.mtime)


class Changelog(dict):
    '''
    Object representing a changelog in memory
    '''
    def __init__(self, data):
        self.verbatim = ""
        self.load(data)

    def load(self, data):
        '''
        Load a changelog file
        '''
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
            m = re.match("\[(\d+)\]", line.lstrip())
            if m is not None:
                version = int(m.group(1))
                self[version] = []
                continue
            # if line are out of a version => invalid format
            if version is None:
                raise Exception("Invalid format: Line outside version")
            # add line to version changelog
            self[version] += [line]
        # save original
        self.verbatim = data

    def show(self, version=None, verbose=False):
        '''
        Show changelog for a given version or all
        '''
        out('#light##yellow#Changelog:#reset#')
        # if no version take the hightest
        if version is None:
            version = max(self)
        # display asked version
        if version in self:
            self._show_version(version)
        # display all version in verbose mode
        if verbose:
            for ver in sorted((k for k in self if k < version), reverse=True):
                self._show_version(ver)

    def _show_version(self, version):
        '''
        Display a version content
        '''
        out('  #yellow#Version:#reset# %s' % version)
        for line in self[version]:
            out("    %s" % line)
