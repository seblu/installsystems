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
import installsystems.template as istemplate
import installsystems.tools as istools
from installsystems.printer import *
from installsystems.tarball import Tarball

class Image(object):
    '''Abstract class of images'''

    extension = ".isimage"
    extension_data = ".isdata"
    format = "1"

    @staticmethod
    def check_image_name(buf):
        '''Check if @name is a valid image name'''
        return re.match("\w+", buf) is not None

    @staticmethod
    def check_image_version(buf):
        '''Check if @name is a valid image version'''
        return re.match("\d+", buf) is not None

class SourceImage(Image):
    '''Image source manipulation class'''

    @classmethod
    def create(cls, path, verbose=True):
        '''Create an empty source image'''
        # check local repository
        if istools.pathtype(path) != "file":
            raise NotImplementedError("SourceImage must be local")
        # main path
        parser_path = os.path.join(path, "parser")
        setup_path = os.path.join(path, "setup")
        data_path = os.path.join(path, "data")
        # create base directories
        arrow("Creating base directories", 1, verbose)
        try:
            for d in (path, parser_path, setup_path, data_path):
                if not os.path.exists(d) or not os.path.isdir(d):
                    os.mkdir(d)
        except Exception as e:
            raise Exception("Unable to create directory: %s: %s" % (d, e))
        # create example files
        arrow("Creating examples", 1, verbose)
        try:
            # create description example from template
            arrow("Creating description example", 2, verbose)
            open(os.path.join(path, "description"), "w").write(istemplate.description)
            # create parser example from template
            arrow("Creating parser script example", 2, verbose)
            open(os.path.join(parser_path, "01-parser.py"), "w").write(istemplate.parser)
            # create setup example from template
            arrow("Creating setup script example", 2, verbose)
            open(os.path.join(setup_path, "01-setup.py"), "w").write(istemplate.setup)
        except Exception as e:
            raise Exception("Unable to example file: %s" % e)
        try:
            # setting rights on files in setup and parser
            arrow("Setting executable rights on scripts", 2, verbose)
            umask = os.umask(0)
            os.umask(umask)
            for dpath in (parser_path, setup_path):
                for f in os.listdir(dpath):
                    pf = os.path.join(dpath, f)
                    os.chmod(pf, 0777 & ~umask)
        except Exception as e:
            raise Exception("Unable to set rights on %s: %s" % (pf, e))
        return cls(path, verbose)

    def __init__(self, path, verbose=True):
        # check local repository
        if istools.pathtype(path) != "file":
            raise NotImplementedError("SourceImage must be local")
        Image.__init__(self)
        self.base_path = path
        self.parser_path = os.path.join(path, "parser")
        self.setup_path = os.path.join(path, "setup")
        self.data_path = os.path.join(path, "data")
        self.verbose = verbose
        self.validate_source_image()
        self.description = self.parse_description()

    def validate_source_image(self):
        '''Check if we are a valid SourceImage'''
        for d in (self.base_path, self.parser_path, self.setup_path, self.data_path):
            if not os.path.exists(d):
                raise Exception("Missing directory: %s" % d)
            if not os.path.isdir(d):
                raise Exception("Not a directory: %s" % d)
            if not os.access(d, os.R_OK|os.X_OK):
                raise Exception("Unable to access to %s" % d)

    def build(self, overwrite=False):
        '''Create packaged image'''
        # compute script tarball paths
        tarpath = os.path.join(self.base_path,
                               "%s-%s%s" % (self.description["name"],
                                            self.description["version"],
                                            self.extension))
        # check if free to create script tarball
        if os.path.exists(tarpath) and overwrite == False:
            raise Exception("Tarball already exists. Remove it before")
        #  Create data tarballs
        self.create_data_tarballs()
        # generate description.json
        jdesc = self.generate_json_description()
        # creating scripts tarball
        arrow("Creating scripts tarball", 1, self.verbose)
        arrow("Name %s" % os.path.relpath(tarpath), 2, self.verbose)
        try:
            tarball = Tarball.open(tarpath, mode="w:gz", dereference=True)
        except Exception as e:
            raise Exception("Unable to create tarball %s: %s" % (tarpath, e))
        # add .description.json
        arrow("Add .description.json", 2, self.verbose)
        tarball.add_str("description.json", jdesc, tarfile.REGTYPE, 0444)
        # add .format
        arrow("Add .format", 2, self.verbose)
        tarball.add_str("format", self.format, tarfile.REGTYPE, 0444)
        # add parser scripts
        arrow("Add parser scripts", 2, self.verbose)
        tarball.add(self.parser_path, arcname="parser",
                    recursive=True, filter=self.tar_scripts_filter)
        # add setup scripts
        arrow("Add setup scripts", 2, self.verbose)
        tarball.add(self.setup_path, arcname="setup",
                    recursive=True, filter=self.tar_scripts_filter)
        # closing tarball file
        tarball.close()

    @property
    def data_tarballs(self):
        '''List all data tarballs in data directory'''
        databalls = dict()
        for dname in os.listdir(self.data_path):
            filename = "%s-%s-%s%s" % (self.description["name"],
                                       self.description["version"],
                                       dname,
                                       self.extension_data)
            databalls[dname] = filename
        return databalls

    def create_data_tarballs(self):
        '''
        Create all data tarballs in data directory
        Doen't compute md5 during creation because tarball can
        be created manually
        '''
        arrow("Creating data tarballs", 1, self.verbose)
        # build list of data tarball candidate
        candidates = self.data_tarballs
        if len(candidates) == 0:
            arrow("No data tarball", 2, self.verbose)
            return
        # create tarballs
        for (dn, df) in candidates.items():
            source_path = os.path.join(self.data_path, dn)
            dest_path = os.path.join(self.base_path, df)
            if os.path.exists(dest_path):
                arrow("Tarball %s already exists." % df, 2, self.verbose)
            else:
                arrow("Creating tarball %s" % df, 2, self.verbose)
                self.create_data_tarball(dest_path, source_path)

    def create_data_tarball(self, tar_path, data_path):
        '''Create a data tarball'''
        # compute dname to set as a base directory
        dname = os.path.basename(data_path)
        # not derefence for directory. Verbatim copy.
        ddref = False if os.path.isdir(data_path) else True
        try:
            # Tarballing
            tarball = Tarball.open(tar_path, "w:gz", dereference=ddref)
            tarball.add(data_path, arcname="/", recursive=True)
            tarball.close()
        except Exception as e:
            raise Exception("Unable to create data tarball %s: %s" % (tar_path, e))

    def tar_scripts_filter(self, tinfo):
        '''Filter files which can be included in scripts tarball'''
        if not tinfo.name in ("parser", "setup") and os.path.splitext(tinfo.name)[1] != ".py":
            return None
        tinfo.mode = 0755
        tinfo.uid = tinfo.gid = 0
        tinfo.uname = tinfo.gname = "root"
        return tinfo

    def generate_json_description(self):
        '''Generate a JSON description file'''
        arrow("Generating JSON description", 1, self.verbose)
        # copy description
        desc = self.description.copy()
        # timestamp image
        arrow("Timestamping", 2, self.verbose)
        desc["date"] = int(time.time())
        # append data tarballs info
        desc["data"] = dict()
        for (dn, df) in self.data_tarballs.items():
            arrow("Compute MD5 of %s" % df, 2, self.verbose)
            tb_path = os.path.join(self.base_path, df)
            desc["data"][dn] = { "size": os.path.getsize(tb_path),
                                 "md5": istools.md5sum(tb_path) }
        # serialize
        return json.dumps(desc)

    def parse_description(self):
        '''Raise an exception is description file is invalid and return vars to include'''
        arrow("Parsing description", 1, self.verbose)
        d = dict()
        try:
            descpath = os.path.join(self.base_path, "description")
            cp = ConfigParser.RawConfigParser()
            cp.read(descpath)
            for n in ("name","version", "description", "author"):
                d[n] = cp.get("image", n)
        except Exception as e:
            raise Exception("Invalid description: %s" % e)
        return d


class PackageImage(Image):
    '''Packaged image manipulation class'''

    def __init__(self, path, verbose=True):
        Image.__init__(self)
        self.path = istools.abspath(path)
        self.base_path = os.path.dirname(self.path)
        self.verbose = verbose
        # load image in memory
        arrow("Loading tarball in memory", 1, verbose)
        self.file = cStringIO.StringIO()
        fo = istools.uopen(self.path)
        shutil.copyfileobj(fo, self.file)
        fo.close()
        # set tarball fo
        self.file.seek(0)
        self.tarball = Tarball.open(fileobj=self.file, mode='r:gz')
        self.parse()
        self._md5 = None

    @property
    def md5(self):
        '''Return md5sum of the current tarball'''
        if self._md5 is None:
            self._md5 = istools.md5sum(self.path)
        return self._md5

    @property
    def id(self):
        '''Return image versionned name / id'''
        return "%s-%s" % (self.description["name"], self.description["version"])

    @property
    def name(self):
        '''Return image name'''
        return self.description["name"]

    @property
    def version(self):
        '''Return image version'''
        return self.description["version"]

    @property
    def filename(self):
        '''Return image filename'''
        return "%s%s" % (self.id, self.extension)

    @property
    def datas(self):
        '''Create a dict of data tarballs'''
        d = dict()
        for dt in self.description["data"]:
            d[dt] = dict(self.description["data"][dt])
            d[dt]["filename"] = "%s-%s%s" % (self.id, dt, self.extension_data)
            d[dt]["path"] = os.path.join(self.base_path, d[dt]["filename"])
        return d

    def parse(self):
        '''Parse tarball and extract metadata'''
        # extract metadata
        arrow("Read tarball metadata", 1, self.verbose)
        img_format = self.tarball.get_str("format")
        img_desc = self.tarball.get_str("description.json")
        # check format
        arrow("Read format", 2, self.verbose)
        if img_format != self.format:
            raise Exception("Invalid tarball image format")
        # check description
        arrow("Read description", 2, self.verbose)
        try:
            self.description = json.loads(img_desc)
        except Exception as e:
            raise Exception("Invalid description: %s" % e1)

    def check_md5(self):
        '''Check if md5 of data tarballs are correct'''
        arrow("Check MD5", 1, self.verbose)
        databalls = self.description["data"]
        for databall in databalls:
            md5_path = os.path.join(self.base_path, databall)
            arrow(os.path.relpath(md5_path), 2, self.verbose)
            md5_meta = databalls[databall]["md5"]
            md5_file = istools.md5sum(md5_path)
            if md5_meta != md5_file:
                raise Exception("Invalid md5: %s" % databall)

    def run_parser(self, gl):
        '''Run parser scripts'''
        self._run_scripts(gl, "parser")

    def run_setup(self, gl):
        '''Run setup scripts'''
        gl["image"] = self
        self._run_scripts(gl, "setup")

    def _run_scripts(self, gl, directory):
        '''Run scripts in a tarball directory'''
        arrow("Run %s" % directory, 1, self.verbose)
        # get list of parser scripts
        l_scripts = self.tarball.getnames("%s/.*\.py" % directory)
        # order matter!
        l_scripts.sort()
        # run scripts
        for n_scripts in l_scripts:
            arrow(os.path.basename(n_scripts), 2, self.verbose)
            try:
                s_scripts = self.tarball.get_str(n_scripts)
            except Exception as e:
                raise Exception("Extracting script %s fail: %s" %
                                (os.path.basename(n_scripts), e))
            try:
                exec(s_scripts, gl, dict())
            except Exception as e:
                raise
                raise Exception("Execution script %s fail: %s" %
                                (os.path.basename(n_scripts), e))

    def extractdata(self, dataname, target, filelist=None):
        '''Extract a data tarball into target'''
        # check if dataname exists
        if dataname not in self.description["data"].keys():
            raise Exception("No such data")
        # tarball info
        tinfo = self.description["data"][dataname]
        # build data tar paths
        paths = [ os.path.join(self.base_path, tinfo["md5"]),
                  os.path.join(self.base_path, "%s-%s%s" % (self.id,
                                                            dataname,
                                                            self.extension_data)) ]
        # try to open path
        fo = None
        for path in paths:
            try:
                fo = istools.uopen(path)
                break
            except Exception:
                pass
        # error if no file is openned
        if fo is None:
            raise Exception("Unable to open data tarball")
        try:
            # create tar object
            t = Tarball.open(fileobj=fo, mode="r|gz")
        except Exception as e:
            raise Exception("Invalid data tarball: %s" % e)
        # filter on file to extact
        if filelist is not None:
            members = []
            for fi in filelist:
                members += t.gettarinfo(name)
        else:
            members = None
        try:
            t.extractall(target, members)
        except Exception as e:
            raise Exception("Extracting failed: %s" % e)
