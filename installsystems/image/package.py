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
Package Image module
'''

from cStringIO import StringIO
from difflib import unified_diff
from installsystems import VERSION
from installsystems.exception import ISError
from installsystems.image.changelog import Changelog
from installsystems.image.image import Image
from installsystems.image.payload import Payload
from installsystems.image.source import SourceImage, DESCRIPTION_TPL
from installsystems.image.tarball import Tarball
from installsystems.printer import warn, arrow, arrowlevel, out, debug
from installsystems.tools import mkdir, abspath, time_rfc2822, human_size, argv, PipeFile
from json import loads, dumps
from math import floor
from os import listdir
from os.path import join, basename, exists, isdir, dirname
from time import time

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
                fromfile = join(pkg1.filename, f)
                fromdata = pkg1._tarball.extractfile(f).readlines()
            else:
                fromfile = "/dev/null"
                fromdata = ""
            # preparing to info
            if f in tofiles:
                tofile = join(pkg2.filename, f)
                todata = pkg2._tarball.extractfile(f).readlines()
            else:
                tofile = "/dev/null"
                todata = ""
            # generate diff
            for line in unified_diff(fromdata,
                                     todata,
                                     fromfile=fromfile,
                                     tofile=tofile):
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
        self.path = abspath(path)
        self.base_path = dirname(self.path)
        # tarball are named by md5 and not by real name
        self.md5name = md5name
        try:
            if fileobj is None:
                fileobj = PipeFile(self.path, "r")
            else:
                fileobj = PipeFile(mode="r", fileobj=fileobj)
            memfile = StringIO()
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
        arrow(u"Date: %s" % time_rfc2822(self.date), 1)
        # build payloads info
        self.payload = {}
        for pname, pval in self._metadata["payload"].items():
            pfilename = u"%s-%s%s" % (self.filename[:-len(Image.extension)],
                                      pname, Payload.extension)
            if self.md5name:
                ppath = join(self.base_path,
                                     self._metadata["payload"][pname]["md5"])
            else:
                ppath = join(self.base_path, pfilename)
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
            if float(img_format) >= floor(float(SourceImage.format)) + 1.0:
                raise Exception()
        except:
            raise ISError(u"Invalid image format %s" % img_format)
        desc["format"] = img_format
        # check description
        try:
            img_desc = self._tarball.get_utf8("description.json")
            desc.update(loads(img_desc))
            self.check_name(desc["name"])
            self.check_version(desc["version"])
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
            if self.compare_versions(VERSION, desc["is_min_version"]) < 0:
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
            out(dumps(self._metadata))
        else:
            out(u'#light##yellow#Name:#reset# %s' % self.name)
            out(u'#light##yellow#Version:#reset# %s' % self.version)
            out(u'#yellow#Date:#reset# %s' % time_rfc2822(self.date))
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
                    out(u'  #yellow#Date:#reset# %s' % time_rfc2822(payload.mtime))
                    out(u'  #yellow#Size:#reset# %s' % (human_size(payload.size)))
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
        directory = abspath(directory)
        if image:
            dest = join(directory, self.filename)
            if not force and exists(dest):
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
        if exists(directory):
            if not isdir(directory):
                raise ISError(u"Destination %s is not a directory" % directory)
            if not force and len(listdir(directory)) > 0:
                raise ISError(u"Directory %s is not empty (need force)" % directory)
        else:
            mkdir(directory)
        # extract content
        arrow(u"Extracting image in %s" % directory)
        self._tarball.extractall(directory)
        # generate description file from description.json
        if gendescription:
            arrow(u"Generating description file in %s" % directory)
            with open(join(directory, "description"), "w") as f:
                f.write((DESCRIPTION_TPL % self._metadata).encode("UTF-8"))
        # launch payload extraction
        if payload:
            for payname in self.payload:
                # here we need to decode payname which is in unicode to escape
                # tarfile to encode filename of file inside tarball inside unicode
                dest = join(directory, "payload", payname.encode("UTF-8"))
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
        t0 = time()
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
        args = argv()[1:]
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
        return int(time() - t0)

    def select_scripts(self, directory):
        '''
        Generator of tuples (fp,fn,fc) of scripts witch are allocatable
        in a tarball directory
        '''
        for fp in sorted(self._tarball.getnames(re_pattern="%s/.*\.py" % directory)):
            fn = basename(fp)
            # extract source code
            try:
                fc = self._tarball.get_str(fp)
            except Exception as e:
                raise ISError(u"Unable to extract script %s" % fp, e)
            # yield complet file path, file name and file content
            yield (fp, fn, fc)

