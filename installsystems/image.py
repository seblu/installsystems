# -*- python -*-
# -*- coding: utf-8 -*-
# Started 10/05/2011 by Seblu <seblu@seblu.net>

'''
Image stuff
'''

import os
import stat
import time
import json
import ConfigParser
import subprocess
import tarfile
import re
import cStringIO
import shutil
import gzip
import installsystems.template as istemplate
import installsystems.tools as istools
from installsystems.printer import *
from installsystems.tarball import Tarball


class Image(object):
    '''
    Abstract class of images
    '''

    format = "1"
    extension = ".isimage"

    @staticmethod
    def check_image_name(buf):
        '''
        Check if @name is a valid image name
        '''
        return re.match("\w+", buf) is not None

    @staticmethod
    def check_image_version(buf):
        '''
        Check if @name is a valid image version
        '''
        return re.match("\d+", buf) is not None


class SourceImage(Image):
    '''
    Image source manipulation class
    '''

    @classmethod
    def create(cls, path):
        '''
        Create an empty source image
        '''
        # check local repository
        if istools.pathtype(path) != "file":
            raise NotImplementedError("SourceImage must be local")
        # main path
        parser_path = os.path.join(path, "parser")
        setup_path = os.path.join(path, "setup")
        payload_path = os.path.join(path, "payload")
        # create base directories
        arrow("Creating base directories")
        try:
            for d in (path, parser_path, setup_path, payload_path):
                if not os.path.exists(d) or not os.path.isdir(d):
                    os.mkdir(d)
        except Exception as e:
            raise Exception("Unable to create directory: %s: %s" % (d, e))
        # create example files
        arrow("Creating examples")
        arrowlevel(1)
        try:
            # create description example from template
            arrow("Creating description example")
            open(os.path.join(path, "description"), "w").write(istemplate.description)
            # create parser example from template
            arrow("Creating parser script example")
            open(os.path.join(parser_path, "01-parser.py"), "w").write(istemplate.parser)
            # create setup example from template
            arrow("Creating setup script example")
            open(os.path.join(setup_path, "01-setup.py"), "w").write(istemplate.setup)
        except Exception as e:
            raise Exception("Unable to example file: %s" % e)
        try:
            # setting rights on files in setup and parser
            arrow("Setting executable rights on scripts")
            umask = os.umask(0)
            os.umask(umask)
            for dpath in (parser_path, setup_path):
                for f in os.listdir(dpath):
                    istools.chrights(os.path.join(dpath, f), mode=0777 & ~umask)
        except Exception as e:
            raise Exception("Unable to set rights on %s: %s" % (pf, e))
        arrowlevel(-1)
        return cls(path)

    def __init__(self, path):
        # check local repository
        if istools.pathtype(path) != "file":
            raise NotImplementedError("SourceImage must be local")
        Image.__init__(self)
        self.base_path = path
        self.parser_path = os.path.join(path, "parser")
        self.setup_path = os.path.join(path, "setup")
        self.payload_path = os.path.join(path, "payload")
        self.validate_source_files()
        self.description = self.parse_description()
        # script tarball path
        self.image_name = "%s-%s%s" % (self.description["name"],
                                       self.description["version"],
                                       self.extension)

    def validate_source_files(self):
        '''
        Check if we are a valid SourceImage directories
        '''
        for d in (self.base_path, self.parser_path, self.setup_path, self.payload_path):
            if not os.path.exists(d):
                raise Exception("Missing directory: %s" % d)
            if not os.path.isdir(d):
                raise Exception("Not a directory: %s" % d)
            if not os.access(d, os.R_OK|os.X_OK):
                raise Exception("Unable to access to %s" % d)
        if not os.path.exists(os.path.join(self.base_path, "description")):
            raise Exception("No description file")

    def build(self, force=False, check=True):
        '''
        Create packaged image
        '''
        # check if free to create script tarball
        if os.path.exists(self.image_name) and force == False:
            raise Exception("Tarball already exists. Remove it before")
        # Check python file
        if check:
            self._check_scripts(self.parser_path)
            self._check_scripts(self.setup_path)
        # Create payload files
        payloads = self._create_payloads()
        # generate a JSON description
        jdesc = self.generate_json_description(payloads)
        # creating scripts tarball
        self._create_image(jdesc)

    def _create_image(self, description):
        '''
        Create a script tarball in current directory
        '''
        # create tarball
        arrow("Creating image tarball")
        arrowlevel(1)
        arrow("Name %s" % self.image_name)
        try:
            tarball = Tarball.open(self.image_name, mode="w:gz", dereference=True)
        except Exception as e:
            raise Exception("Unable to create tarball %s: %s" % (self.image_name, e))
        # add .description.json
        arrow("Add description.json")
        tarball.add_str("description.json", description, tarfile.REGTYPE, 0444)
        # add .format
        arrow("Add format")
        tarball.add_str("format", self.format, tarfile.REGTYPE, 0444)
        # add parser scripts
        self._add_scripts(tarball, self.parser_path)
        # add setup scripts
        self._add_scripts(tarball, self.setup_path)
        # closing tarball file
        tarball.close()
        arrowlevel(-1)

    def _create_payloads(self):
        '''
        Create all data payloads in current directory
        Doesn't compute md5 during creation because tarball can
        be created manually
        '''
        arrow("Creating payloads")
        arrowlevel(1)
        # build list of payload files
        candidates = os.listdir(self.payload_path)
        if len(candidates) == 0:
            arrow("No payload")
            arrowlevel(-1)
            return []
        # create payload files
        l_l = []
        for pay in candidates:
            source_path = os.path.join(self.payload_path, pay)
            dest_path = "%s-%s-%s%s" % (self.description["name"],
                                        self.description["version"],
                                        pay,
                                        Payload.extension)
            source_stat = os.stat(source_path)
            isdir = stat.S_ISDIR(source_stat.st_mode)
            if os.path.exists(dest_path):
                arrow("Payload %s already exists" % dest_path)
            else:
                arrow("Creating payload %s" % dest_path)
                if isdir:
                    self._create_payload_tarball(dest_path, source_path)
                else:
                    self._create_payload_file(dest_path, source_path)
            # create payload object
            payobj = Payload(pay, dest_path, isdir=isdir)
            payobj.uid = source_stat.st_uid
            payobj.gid = source_stat.st_gid
            payobj.mode = stat.S_IMODE(source_stat.st_mode)
            payobj.mtime = source_stat.st_mtime
            l_l.append(payobj)
        arrowlevel(-1)
        return l_l

    def _create_payload_tarball(self, tar_path, data_path):
        '''
        Create a payload tarball
        This is needed by payload directory
        '''
        # compute dname to set as a base directory
        dname = os.path.basename(data_path)
        try:
            # Tarballing
            tarball = Tarball.open(tar_path, "w:gz", dereference=False)
            tarball.add(data_path, arcname="/", recursive=True)
            tarball.close()
        except Exception as e:
            raise Exception("Unable to create payload tarball %s: %s" % (tar_path, e))

    def _create_payload_file(self, dest, source):
        '''
        Create a payload file
        Only gzipping it
        '''
        fsource = istools.uopen(source)
        # open file not done in GzipFile, to escape writing of filename
        # in gzip file. This change md5.
        fdest = open(dest, "wb")
        fdest = gzip.GzipFile(filename=os.path.basename(source),
                              fileobj=fdest,
                              mtime=os.stat(source).st_mtime)
        istools.copyfileobj(fsource, fdest)
        fsource.close()
        fdest.close()

    def _add_scripts(self, tarball, directory):
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
        for fi in os.listdir(directory):
            fp = os.path.join(directory, fi)
            # check name
            if not re.match("\d+-.*\.py$", fi):
                debug("%s skipped: invalid name" % fi)
                continue
            # adding file
            ti = tarball.gettarinfo(fp, arcname=os.path.join(basedirectory, fi))
            ti.mode = 0755
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = "root"
            tarball.addfile(ti, open(fp, "rb"))
            arrow("%s added" % fi)
        arrowlevel(-1)

    def _check_scripts(self, directory):
        '''
        Check if scripts inside a directory can be compiled
        '''
        basedirectory = os.path.basename(directory)
        arrow("Checking %s scripts" % basedirectory)
        arrowlevel(1)
        # checking each file
        for fi in os.listdir(directory):
            # check name
            if not re.match("\d+-.*\.py$", fi):
                debug("%s skipped: invalid name" % fi)
                continue
            # compiling file
            fs = open(os.path.join(directory, fi), "rb").read()
            compile(fs, fi, mode="exec")
            arrow(fi)
        arrowlevel(-1)

    def generate_json_description(self, payloads):
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
        # append payload infos
        arrow("Checksumming")
        desc["payload"] = {}
        for payload in payloads:
            desc["payload"][payload.name] = payload.info
        arrowlevel(-1)
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
        except Exception as e:
            raise Exception("Bad description: %s" % e)
        return d


class PackageImage(Image):
    '''
    Packaged image manipulation class
    '''

    def __init__(self, path, md5name=False):
        Image.__init__(self)
        self.path = istools.abspath(path)
        self.base_path = os.path.dirname(self.path)
        # tarball are named by md5 and not by real name
        self.md5name = md5name
        # load image in memory
        arrow("Loading tarball in memory")
        memfile = cStringIO.StringIO()
        fo = istools.uopen(self.path)
        (self.size, self.md5) = istools.copyfileobj(fo, memfile)
        fo.close()
        # set tarball fo
        memfile.seek(0)
        self._tarball = Tarball.open(fileobj=memfile, mode='r:gz')
        self._metadata = self.read_metadata()
        # build payloads
        self.payload = {}
        for pname, pval in self._metadata["payload"].items():
            if self.md5name:
                ppath = os.path.join(self.base_path,
                                     self._metadata["payload"][pname]["md5"])
            else:
                ppath = os.path.join(self.base_path,
                                     "%s-%s%s" % (self.id, pname, Payload.extension))
            self.payload[pname] = Payload(pname, ppath, **pval)

    def __getattr__(self, name):
        '''
        Give direct access to description field
        '''
        if name in self._metadata:
            return self._metadata[name]
        raise AttributeError

    @property
    def id(self):
        '''
        Return image versionned name / id
        '''
        return "%s-%s" % (self.name, self.version)

    @property
    def filename(self):
        '''
        Return image filename
        '''
        return "%s%s" % (self.id, self.extension)

    def read_metadata(self):
        '''
        Parse tarball and return metadata dict
        '''
        # extract metadata
        arrow("Read tarball metadata", 1)
        arrowlevel(1)
        img_format = self._tarball.get_str("format")
        img_desc = self._tarball.get_str("description.json")
        # check format
        arrow("Read format file")
        if img_format != self.format:
            raise Exception("Invalid tarball image format")
        # check description
        arrow("Read image description")
        try:
            desc = json.loads(img_desc)
        except Exception as e:
            raise Exception("Invalid description: %s" % e)
        # FIXME: we should check valid information here
        arrowlevel(-1)
        return desc

    def check(self, message="Check MD5"):
        '''
        Check md5 and size of tarballs are correct
        '''
        arrow(message)
        arrowlevel(1)
        # check image
        if self.md5 != istools.md5sum(self.path):
            raise Exception("Invalid MD5 of image %s" % self.name)
        # check payloads
        for pay_name, pay_obj in self.payload.items():
            arrow(pay_name)
            pay_obj.check()
        arrowlevel(-1)

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
        l_scripts = self._tarball.getnames("%s/.*\.py" % directory)
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
    legit_attr = ('isdir', 'md5', 'size', 'uid', 'gid', 'mode', 'mtime')

    def __init__(self, name, path, **kwargs):
        object.__setattr__(self, "name", name)
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
        fileobj = istools.uopen(self.path)
        size, md5 = istools.copyfileobj(fileobj, None)
        if self._size is None:
            self._size = size
        if self._md5 is None:
            self._md5 = md5

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
    def info(self):
        '''
        return a dict of info about current payload
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
        fileobj = istools.uopen(self.path)
        size, md5 = istools.copyfileobj(fileobj, None)
        if self._size != size:
            raise Exception("Invalid size of payload %s" % self.name)
        if self._md5 != md5:
            raise Exception("Invalid MD5 of payload %s" % self._md5)

    def extract(self, dest, force=False, filelist=None):
        '''
        Extract payload into dest
        filelist is a filter of file in tarball
        force will overwrite existing file if exists
        '''
        if self.isdir:
            self.extract_tar(dest, force=force, filelist=filelist)
        else:
            self.extract_file(dest, force=force)

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
            os.mkdir(dest)
        # try to open payload file
        try:
            fo = istools.uopen(self.path)
        except Exception as e:
            raise Exception("Unable to open payload file %s" % self.path)
        # try to open tarball on payload
        try:
            t = Tarball.open(fileobj=fo, mode="r|gz")
        except Exception as e:
            raise Exception("Invalid payload tarball: %s" % e)
        # filter on file to extact
        members = (None if filelist is None
                   else [ t.gettarinfo(name) for name in filelist ])
        try:
            t.extractall(dest, members)
        except Exception as e:
            raise Exception("Extracting failed: %s" % e)
        # closing fo
        t.close()
        fo.close()

    def extract_file(self, dest, force=False):
        '''
        Copy a payload directly to a file
        Check md5 on the fly
        '''
        # if dest is a directory try to create file inside
        if os.path.isdir(dest):
            dest = os.path.join(dest, self.name)
        # check validity of dest
        if os.path.exists(dest):
            if not os.path.isfile(dest):
                raise Exception("Destination %s is not a file" % dest)
            if not force:
                raise Exception("File %s already exists" % dest)
        # opening destination
        try:
            f_dst = istools.uopen(dest, "wb")
        except Exception as e:
            raise Exception("Unable to open destination file %s" % dest)
        # try to open payload file
        try:
            f_gsrc = istools.uopen(self.path)
            f_src = gzip.GzipFile(fileobj=f_gsrc)
        except Exception as e:
            raise Exception("Unable to open payload file %s" % self.path)
        # launch copy
        size, md5 = istools.copyfileobj(f_src, f_dst)
        # closing fo
        f_dst.close()
        f_gsrc.close()
        f_src.close()
        # settings file orginal rights
        istools.chrights(dest, self.uid, self.gid, self.mode, self.mtime)
