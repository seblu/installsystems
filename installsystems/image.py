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
import tarfile
import json
import hashlib
import StringIO
import ConfigParser
import subprocess
import installsystems.printer as p
import installsystems.template

image_extension = ".img.tar.bz2"
image_format = "1"

class Image(object):
    '''Abstract class of images'''

    def __init__(self, pbzip2=True):
        self.pbzip2_path = self.path_search("pbzip2") if pbzip2 else None

    def path_search(self, name, path=None):
        '''Search in PATH for a binary'''
        path = path or os.environ["PATH"]
        for d in path.split(os.pathsep):
            if os.path.exists(os.path.join(d, name)):
                return os.path.join(os.path.abspath(d), name)
        return None

    def md5_checksum(self, path):
        '''Compute md5 of a file'''
        m = hashlib.md5()
        m.update(open(path, "r").read())
        return m.hexdigest()

class SourceImage(Image):
    '''Image source manipulation class'''

    def __init__(self, path, verbose=True, create=False, pbzip2=True):
        Image.__init__(self, pbzip2)
        self.base_path = path
        self.parser_path = os.path.join(path, "parser")
        self.setup_path = os.path.join(path, "setup")
        self.data_path = os.path.join(path, "data")
        self.verbose = verbose
        if create:
            self.create()
        self.description = self.parse_description()

    def create(self):
        '''Create an empty source image'''
        # create base directories
        if self.verbose: p.arrow("Creating base directories")
        try:
            for d in (self.base_path, self.parser_path, self.setup_path, self.data_path):
                os.mkdir(d)
        except Exception as e:
            raise Exception("Unable to create directory %s: %s" % (d, e))
        # create example files
        if self.verbose: p.arrow("Creating examples")
        try:
            # create description example from template
            if self.verbose: p.arrow2("Creating description example")
            open(os.path.join(self.base_path, "description"), "w").write(
                installsystems.template.description)
            # create parser example from template
            if self.verbose: p.arrow2("Creating parser script example")
            open(os.path.join(self.parser_path, "01-parser.py"), "w").write(
                installsystems.template.parser)
            # create setup example from template
            if self.verbose: p.arrow2("Creating setup script example")
            open(os.path.join(self.setup_path, "01-setup.py"), "w").write(
                installsystems.template.setup)
        except Exception as e:
            raise Exception("Unable to example file: %s" % e)
        try:
            # setting rights on files in setup and parser
            if self.verbose: p.arrow2("Setting executable rights on scripts")
            umask = os.umask(0)
            os.umask(umask)
            for path in (self.parser_path, self.setup_path):
                for f in os.listdir(path):
                    pf = os.path.join(path, f)
                    os.chmod(pf, 0777 & ~umask)
        except Exception as e:
            raise Exception("Unable to set rights on %s: %s" % (pf, e))

    def build(self):
        '''Create packaged image'''
        t0 = time.time()
        # compute script tarball paths
        tarpath = os.path.join(self.base_path,
                               "%s-%s%s" % (self.description["name"],
                                            self.description["version"],
                                            image_extension))
        # check if free to create script tarball
        if os.path.exists(tarpath):
            raise Exception("Tarbal already exists. Remove it before")
        # printing pbzip2 status
        if self.verbose:
            if self.pbzip2_path:
                p.arrow("Parallel bzip2 enabled (%s)" % self.pbzip2_path)
            else:
                p.arrow("Parallel bzip disabled")
        #  Create data tarballs
        data_d = self.create_data_tarballs()
        # generate .description.json
        jdesc = self.generate_json_description()
        # creating scripts tarball
        if self.verbose: p.arrow("Creating scripts tarball")
        if self.verbose: p.arrow2("Name %s" % os.path.relpath(tarpath))
        try:
            tarball = tarfile.open(tarpath, mode="w:bz2", dereference=True)
        except Exception as e:
            raise Exception("Unable to create tarball %s: %s" % (tarpath, e))
        # add .description.json
        if self.verbose: p.arrow2("Add .description.json")
        self.tar_add_str(tarball, tarfile.REGTYPE, 0444, ".description.json", jdesc)
        # add .format
        if self.verbose: p.arrow2("Add .format")
        self.tar_add_str(tarball, tarfile.REGTYPE, 0444, ".format", image_format)
        # add parser scripts
        if self.verbose: p.arrow2("Add parser scripts")
        tarball.add(self.parser_path, arcname="parser",
                    recursive=True, filter=self.tar_scripts_filter)
        # add setup scripts
        if self.verbose: p.arrow2("Add setup scripts")
        tarball.add(self.setup_path, arcname="setup",
                    recursive=True, filter=self.tar_scripts_filter)
        # closing tarball file
        tarball.close()
        # compute building time
        t1 = time.time()
        dt = int(t1 - t0)
        if self.verbose: p.arrow("Build time: %s" % datetime.timedelta(seconds=dt))

    def data_tarballs(self):
        '''List all data tarballs in data directory'''
        databalls = dict()
        for dname in os.listdir(self.data_path):
            filename = "%s-%s-%s%s" % (self.description["name"],
                                       self.description["version"],
                                       dname,
                                       image_extension)
            databalls[filename] = os.path.abspath(os.path.join(self.data_path, dname))
        return databalls

    def create_data_tarballs(self):
        '''Create all data tarballs in data directory'''
        if self.verbose: p.arrow("Creating data tarballs")
        # build list of data tarball candidate
        candidates = self.data_tarballs()
        if len(candidates) == 0:
            if self.verbose: p.arrow2("No data tarball")
            return
        # create tarballs
        for candidate in candidates:
            path = os.path.join(self.base_path, candidate)
            if os.path.exists(path):
                if self.verbose: p.arrow2("Tarball %s already exists." % candidate)
            else:
                if self.verbose: p.arrow2("Creating tarball %s" % candidate)
                self.create_data_tarball(path, candidates[candidate])

    def create_data_tarball(self, tar_path, data_path):
        '''Create a data tarball'''
        dname = os.path.basename(data_path)
        try:
            # opening file
            if self.pbzip2_path:
                tb = open(tar_path, mode="w")
                p = subprocess.Popen(self.pbzip2_path, shell=False, close_fds=True,
                                     stdin=subprocess.PIPE, stdout=tb.fileno())
                tarball = tarfile.open(mode="w|", dereference=True, fileobj=p.stdin)
            else:
                tarball = tarfile.open(tar_path, "w:bz2", dereference=True)
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

    def tar_add_str(self, tarball, ftype, mode, name, content):
        '''Add a string in memory as a file in tarball'''
        ti = tarfile.TarInfo(name)
        ti.type = ftype
        ti.mode = mode
        ti.mtime = int(time.time())
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = "root"
        ti.size = len(content) if content is not None else 0
        tarball.addfile(ti, StringIO.StringIO(content))

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
        if self.verbose: p.arrow("Generating JSON description")
        # copy description
        desc = self.description.copy()
        # timestamp image
        if self.verbose: p.arrow2("Timestamping")
        desc["date"] = int(time.time())
        # append data tarballs info
        desc["data"] = dict()
        for dt in self.data_tarballs():
            if self.verbose: p.arrow2("Compute MD5 of %s" % dt)
            path = os.path.join(self.base_path, dt)
            desc["data"][dt] = { "size": os.path.getsize(path),
                                 "md5": self.md5_checksum(path) }
        # create file
        filedesc = StringIO.StringIO()
        # serialize
        return json.dumps(desc)

    def parse_description(self):
        '''Raise an exception is description file is invalid and return vars to include'''
        if self.verbose: p.arrow("Parsing description")
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

    def __init__(self, path):
        Image.__init__(self)
        self.path = path

class DataImage(Image):
    '''Data image manipulation class'''

    def __init__(self, path):
        Image.__init__(self)
        self.path = path
