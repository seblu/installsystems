# -*- python -*-
# -*- coding: utf-8 -*-
# Started 10/05/2011 by Seblu <seblu@seblu.net>

'''
Image stuff
'''

import os
import stat
import datetime
import time
import json
import StringIO
import ConfigParser
import subprocess
import json
import tarfile
import re
import installsystems.template
import installsystems.tools as istools
from installsystems.printer import *
from installsystems.tarball import Tarball

class Image(object):
    '''Abstract class of images'''

    image_extension = ".isimage"
    image_payload = ".isdata"
    image_format = "1"

    @staticmethod
    def check_image_name(buf):
        '''Check if @name is a valid image name'''
        return re.match("\w+", buf) is not None

    @staticmethod
    def check_image_version(buf):
        '''Check if @name is a valid image version'''
        return re.match("\d+", buf) is not None

    def __init__(self, pbzip2=True):
        self.pbzip2_path = self.path_search("pbzip2") if pbzip2 else None

    def path_search(self, name, path=None):
        '''Search in PATH for a binary'''
        path = path or os.environ["PATH"]
        for d in path.split(os.pathsep):
            if os.path.exists(os.path.join(d, name)):
                return os.path.join(os.path.abspath(d), name)
        return None

class SourceImage(Image):
    '''Image source manipulation class'''

    def __init__(self, path, verbose=True, pbzip2=True):
        Image.__init__(self, pbzip2)
        self.base_path = path
        self.parser_path = os.path.join(path, "parser")
        self.setup_path = os.path.join(path, "setup")
        self.data_path = os.path.join(path, "data")
        self.verbose = verbose
        self.description = self.parse_description()

    @classmethod
    def create(cls, path, verbose=True, pbzip2=True):
        '''Create an empty source image'''
        parser_path = os.path.join(path, "parser")
        setup_path = os.path.join(path, "setup")
        data_path = os.path.join(path, "data")
        # create base directories
        arrow("Creating base directories", 1, verbose)
        try:
            for d in (path, parser_path, setup_path, data_path):
                os.mkdir(d)
        except Exception as e:
            raise Exception("Unable to create directory: %s: %s" % (d, e))
        # create example files
        arrow("Creating examples", 1, verbose)
        try:
            # create description example from template
            arrow("Creating description example", 2, verbose)
            open(os.path.join(path, "description"), "w").write(
                installsystems.template.description)
            # create parser example from template
            arrow("Creating parser script example", 2, verbose)
            open(os.path.join(parser_path, "01-parser.py"), "w").write(
                installsystems.template.parser)
            # create setup example from template
            arrow("Creating setup script example", 2, verbose)
            open(os.path.join(setup_path, "01-setup.py"), "w").write(
                installsystems.template.setup)
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
        return cls(path, verbose, pbzip2)

    def build(self):
        '''Create packaged image'''
        t0 = time.time()
        # compute script tarball paths
        tarpath = os.path.join(self.base_path,
                               "%s-%s%s" % (self.description["name"],
                                            self.description["version"],
                                            self.image_extension))
        # check if free to create script tarball
        if os.path.exists(tarpath):
            raise Exception("Tarball already exists. Remove it before")
        # printing pbzip2 status
        if self.pbzip2_path:
            arrow("Parallel bzip2 enabled (%s)" % self.pbzip2_path, 1, self.verbose)
        else:
            arrow("Parallel bzip disabled", 1, self.verbose)
        #  Create data tarballs
        data_d = self.create_data_tarballs()
        # generate description.json
        jdesc = self.generate_json_description()
        # creating scripts tarball
        arrow("Creating scripts tarball", 1, self.verbose)
        arrow("Name %s" % os.path.relpath(tarpath), 2, self.verbose)
        try:
            tarball = Tarball.open(tarpath, mode="w:bz2", dereference=True)
        except Exception as e:
            raise Exception("Unable to create tarball %s: %s" % (tarpath, e))
        # add .description.json
        arrow("Add .description.json", 2, self.verbose)
        tarball.add_str("description.json", jdesc, tarfile.REGTYPE, 0444)
        # add .format
        arrow("Add .format", 2, self.verbose)
        tarball.add_str("format", self.image_format, tarfile.REGTYPE, 0444)
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
        # compute building time
        t1 = time.time()
        dt = int(t1 - t0)
        arrow("Build time: %s" % datetime.timedelta(seconds=dt), 2, self.verbose)

    def data_tarballs(self):
        '''List all data tarballs in data directory'''
        databalls = dict()
        for dname in os.listdir(self.data_path):
            filename = "%s-%s-%s%s" % (self.description["name"],
                                       self.description["version"],
                                       dname,
                                       self.image_payload)
            databalls[filename] = os.path.abspath(os.path.join(self.data_path, dname))
        return databalls

    def create_data_tarballs(self):
        '''Create all data tarballs in data directory'''
        arrow("Creating data tarballs", 1, self.verbose)
        # build list of data tarball candidate
        candidates = self.data_tarballs()
        if len(candidates) == 0:
            arrow("No data tarball", 2, self.verbose)
            return
        # create tarballs
        for candidate in candidates:
            path = os.path.join(self.base_path, candidate)
            if os.path.exists(path):
                arrow("Tarball %s already exists." % candidate, 2, self.verbose)
            else:
                arrow("Creating tarball %s" % candidate, 2, self.verbose)
                self.create_data_tarball(path, candidates[candidate])

    def create_data_tarball(self, tar_path, data_path):
        '''Create a data tarball'''
        dname = os.path.basename(data_path)
        # not derefence for directory. Verbatim copy.
        ddref = False if os.path.isdir(data_path) else True
        try:
            # opening file
            if self.pbzip2_path:
                tb = open(tar_path, mode="w")
                p = subprocess.Popen(self.pbzip2_path, shell=False, close_fds=True,
                                     stdin=subprocess.PIPE, stdout=tb.fileno())
                tarball = Tarball.open(mode="w|", dereference=ddref, fileobj=p.stdin)
            else:
                tarball = Tarball.open(tar_path, "w:bz2", dereference=ddref)
            tarball.add(data_path, arcname=dname, recursive=True)
            # closing tarball file
            tarball.close()
            if self.pbzip2_path:
                # closing pipe, needed to end pbzip2
                p.stdin.close()
                # waiting pbzip to terminate
                r = p.wait()
                # cleaning openfile
                tb.close()
                # status
                if r != 0:
                    raise Exception("Data tarball %s creation return %s" % (tar_path, r))
        except Exception as e:
            raise Exception("Unable to create data tarball %s: %s" % (tar_path, e))

    def tar_scripts_filter(self, tinfo):
        '''Filter files which can be included in scripts tarball'''
        if not tinfo.name in ("parser", "setup") and os.path.splitext(tinfo.name)[1] != ".py":
            return None
        tinfo.mode = 0555
        tinfo.uid = tinfo.gid = 0
        tinfo.uname = tinfo.gname = "root"
        return tinfo

    def generate_json_description(self):
        '''Generate a json description file'''
        arrow("Generating JSON description", 1, self.verbose)
        # copy description
        desc = self.description.copy()
        # timestamp image
        arrow("Timestamping", 2, self.verbose)
        desc["date"] = int(time.time())
        # append data tarballs info
        desc["data"] = dict()
        for dt in self.data_tarballs():
            arrow("Compute MD5 of %s" % dt, 2, self.verbose)
            path = os.path.join(self.base_path, dt)
            desc["data"][dt] = { "size": os.path.getsize(path),
                                 "md5": istools.md5sum(path) }
        # create file
        filedesc = StringIO.StringIO()
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
            raise Exception("description: %s" % e)
        return d

class PackageImage(Image):
    '''Packaged image manipulation class'''

    def __init__(self, path, verbose=True):
        Image.__init__(self)
        self.path = os.path.abspath(path)
        self.base_path = os.path.dirname(self.path)
        self.verbose = verbose
        self.tarball = Tarball.open(self.path, mode='r:bz2')
        self.parse()

    def parse(self):
        '''Parse tarball and extract metadata'''
        # extract metadata
        arrow("Read tarball metadata", 1, self.verbose)
        img_format = self.tarball.get_str("format")
        img_desc = self.tarball.get_str("description.json")
        # check format
        arrow("Read format", 2, self.verbose)
        if img_format != self.image_format:
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
            arrow(databall, 2, self.verbose)
            md5_meta = databalls[databall]["md5"]
            md5_file = istools.md5sum(os.path.join(self.base_path, databall))
            if md5_meta != md5_file:
                raise Exception("Invalid md5: %s" % databall)

    def description(self):
        '''Return metadatas of a tarball'''
        return self.description

    def jdescription(self):
        '''Return json formated metadatas'''
        return json.dumps(self.description)

    def name(self):
        '''Return image name'''
        return "%s-%s" % (self.description["name"], self.description["version"])

    def databalls(self):
        '''Create a dict of image and data tarballs'''
        return [ os.path.join(self.base_path, d)
                 for d in self.description["data"] ]

    def run_parser(self, gl):
        '''Run parser scripts'''
        self.run_scripts(gl, "parser")

    def run_setup(self, gl):
        '''Run setup scripts'''
        self.run_scripts(gl, "setup")

    def run_scripts(self, gl, directory):
        '''Run scripts in a tarball directory'''
        arrow("Run %s" % directory, 1, self.verbose)
        # get list of parser scripts
        l_scripts = self.tarball.getnames("%s/.*\.py" % directory)
        # order matter!
        l_scripts.sort()
        # run scripts
        for n_scripts in l_scripts:
            arrow(os.path.basename(n_scripts), 2, self.verbose)
            s_scripts = self.tarball.get_str(n_scripts)
            exec(s_scripts, gl, dict())
