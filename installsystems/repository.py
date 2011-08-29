# -*- python -*-
# -*- coding: utf-8 -*-
# Started 10/05/2011 by Seblu <seblu@seblu.net>

'''
Repository stuff
'''

import os
import time
import shutil
import pwd
import grp
import tempfile
import fnmatch
import cStringIO
import installsystems
import installsystems.tools as istools
from installsystems.printer import *
from installsystems.tarball import Tarball
from installsystems.image import Image, PackageImage
from installsystems.database import Database

class Repository(object):
    '''
    Repository class
    '''

    def __init__(self, config):
        self.config = config
        if not config.offline:
            try:
                self.db = Database(config.dbpath)
            except:
                self.config.offline = True
        if config.offline:
            debug("Repository %s is offline" % config.name)

    def __getattribute__(self, name):
        '''
        Raise an error if repository is unavailable
        Unavailable can be caused because db is not accessible or
        because repository is not initialized
        '''
        config = object.__getattribute__(self, "config")
        # config and init are always accessible
        if name in ("init", "config"):
            return object.__getattribute__(self, name)
        # if no db (not init or not accessible) raise error
        if config.offline:
            raise Exception("Repository %s is offline" % config.name)
        return object.__getattribute__(self, name)

    def init(self):
        '''
        Initialize an empty base repository
        '''
        config = self.config
        # check local repository
        if not istools.isfile(self.config.path):
            raise Exception("Repository creation must be local")
        # create base directories
        arrow("Creating base directories")
        arrowlevel(1)
        # creating local directory
        try:
            if os.path.exists(config.path):
                arrow("%s already exists" % config.path)
            else:
                istools.mkdir(config.path, config.uid, config.gid, config.dmod)
                arrow("%s directory created" % config.path)
        except Exception as e:
            raise Exception("Unable to create directory %s: %s" % (config.path, e))
        arrowlevel(-1)
        # create database
        d = Database.create(config.dbpath)
        istools.chrights(config.dbpath, uid=config.uid,
                         gid=config.gid, mode=config.fmod)
        # load database
        self.db = Database(config.dbpath)
        # mark repo as not offline
        self.config.offline = False
        # create/update last file
        self.update_last()

    def update_last(self):
        '''
        Update last file to current time
        '''
        # check local repository
        if not istools.isfile(self.config.path):
            raise Exception("Repository addition must be local")
        try:
            arrow("Updating last file")
            last_path = os.path.join(self.config.path, self.config.lastname)
            open(last_path, "w").write("%s\n" % int(time.time()))
            istools.chrights(last_path, self.config.uid, self.config.gid, self.config.fmod)
        except Exception as e:
            raise Exception("Update last file failed: %s" % e)

    def last(self):
        '''
        Return the last value
        '''
        try:
            last_path = os.path.join(config.path, config.lastname)
            return int(open(last_path, "r").read().rstrip())
        except Exception as e:
            raise Exception("Read last file failed: %s" % e)
        return 0

    def add(self, image, delete=False):
        '''
        Add a packaged image to repository
        if delete is true, remove original files
        '''
        # check local repository
        if not istools.isfile(self.config.path):
            raise Exception("Repository addition must be local")
        # cannot add already existant image
        if self.has(image.name, image.version):
            raise Exception("Image already in database, delete first!")
        # checking data tarballs md5 before copy
        image.check("Check image and payload before copy")
        # adding file to repository
        arrow("Copying images and payload")
        for obj in [ image ] + image.payload.values():
            dest = os.path.join(self.config.path, obj.md5)
            basesrc = os.path.basename(obj.path)
            if os.path.exists(dest):
                arrow("Skipping %s: already exists" % basesrc, 1)
            else:
                arrow("Adding %s (%s)" % (basesrc, obj.md5), 1)
                istools.copy(obj.path, dest,
                             self.config.uid, self.config.gid, self.config.fmod)
        # copy is done. create a image inside repo
        r_image = PackageImage(os.path.join(self.config.path, image.md5),
                                 md5name=True)
        # checking must be done with original md5
        r_image.md5 = image.md5
        # checking image and payload after copy
        r_image.check("Check image and payload after copy")
        # add description to db
        arrow("Adding metadata")
        self.db.begin()
        # insert image information
        arrow("Image", 1)
        self.db.ask("INSERT INTO image values (?,?,?,?,?,?,?)",
                    (image.md5,
                     image.name,
                     image.version,
                     image.date,
                     image.author,
                     image.description,
                     image.size,
                     ))
        # insert data informations
        arrow("Payloads", 1)
        for name, obj in image.payload.items():
            self.db.ask("INSERT INTO payload values (?,?,?,?,?)",
                        (obj.md5,
                         image.md5,
                         name,
                         obj.isdir,
                         obj.size,
                         ))
        # on commit
        self.db.commit()
        # update last file
        self.update_last()
        # removing orginal files
        if delete:
            arrow("Removing original files")
            for obj in [ image ] + image.payload.values():
                arrow(os.path.basename(obj.path), 1)
                os.unlink(obj.path)

    def delete(self, name, version):
        '''
        Delete an image from repository
        '''
        # check local repository
        if not istools.isfile(self.config.path):
            raise Exception("Repository deletion must be local")
        # get md5 of files related to images (exception is raised if not exists
        md5s = self.getmd5(name, version)
        # cleaning db (must be done before cleaning)
        arrow("Cleaning database")
        arrow("Remove payloads from database", 1)
        self.db.begin()
        for md5 in md5s[1:]:
            self.db.ask("DELETE FROM payload WHERE md5 = ? AND image_md5 = ?",
                        (md5, md5s[0])).fetchone()
        arrow("Remove image from database", 1)
        self.db.ask("DELETE FROM image WHERE md5 = ?",
                        (md5s[0],)).fetchone()
        self.db.commit()
        # Removing script image
        arrow("Removing files from pool")
        arrowlevel(1)
        for md5 in md5s:
            self._remove_file(md5)
        arrowlevel(-1)
        # update last file
        self.update_last()

    def show(self, verbose=False):
        '''
        List images in repository
        '''
        images = self.db.ask("SELECT md5, name, version, date,\
                author, description, size FROM image ORDER BY name, version").fetchall()

        for (image_md5, image_name, image_version, image_date, image_author,
             image_description, image_size) in images:
            out("#light##yellow#%s #reset#v%s" % (image_name, image_version))
            if verbose:
                out("  #yellow#Date:#reset# %s" % time.ctime(image_date))
                out("  #yellow#Description:#reset# %s" % image_description)
                out("  #yellow#Author:#reset# %s" % image_author)
                out("  #yellow#MD5:#reset# %s" % image_md5)
                payloads = self.db.ask("SELECT md5, name, size FROM payload\
                                    WHERE image_md5 = ?", (image_md5,)).fetchall()
                for payload_md5, payload_name, payload_size in payloads:
                    out("  #light##yellow#Payload:#reset# %s" % payload_name)
                    out("    #yellow#Size:#reset# %s" % (istools.human_size(payload_size)))
                    out("    #yellow#MD5:#reset# %s" % payload_md5)
                out()

    def search(self, pattern):
        '''
        Search pattern in a repository
        '''
        images = self.db.ask("SELECT name, version, author, description\
                              FROM image\
                              WHERE name LIKE ? OR\
                              description LIKE ? OR\
                              author LIKE ?",
                             tuple( ["%%%s%%" % pattern ] * 3)
                             ).fetchall()
        for name, version, author, description in images:
            arrow("%s v%s" % (name, version), 1)
            out("   #yellow#Author:#reset# %s" % author)
            out("   #yellow#Description:#reset# %s" % description)

    def _remove_file(self, filename):
        '''
        Remove a filename from pool. Check if it's not needed by db before
        '''
        # check existance in table image
        have = False
        for table in ("image", "payload"):
            have = have or  self.db.ask("SELECT md5 FROM %s WHERE md5 = ? LIMIT 1" % table,
                                        (filename,)).fetchone() is not None
        # if no reference, delete!
        if not have:
            arrow("%s, deleted" % filename)
            os.unlink(os.path.join(self.config.path, filename))
        else:
            arrow("%s, skipped" % filename)

    def has(self, name, version):
        '''
        Return the existance of a package
        '''
        return self.db.ask("SELECT name,version FROM image WHERE name = ? AND version = ? LIMIT 1", (name,version)).fetchone() is not None

    def get(self, name, version=None):
        '''
        Return an image from a name and version
        '''
        # is no version take the last
        if version is None:
            version = self.last(name)
            if version < 0:
                raise Exception("Unable to find image %s in %s" % (name,
                                                                   self.config.name))
        # get file md5 from db
        r = self.db.ask("select md5 from image where name = ? and version = ? limit 1",
                        (name, version)).fetchone()
        if r is None:
            raise Exception("Unable to find image %s v%s" % (name, version))
        path = os.path.join(self.config.path, r[0])
        # getting the file
        arrow("Loading image %s v%s from repository %s" % (name,
                                                           version,
                                                           self.config.name))
        memfile = cStringIO.StringIO()
        try:
            fo = istools.uopen(path)
            istools.copyfileobj(fo, memfile)
            fo.close()
        except Exception as e:
            raise Exception("Loading image %s v%s failed: %s" % (name, version, e))
        memfile.seek(0)
        pkg = PackageImage(path, fileobj=memfile, md5name=True)
        if pkg.md5 != r[0]:
            raise Exception("Image MD5 verification failure")
        return pkg

    def getmd5(self, name, version):
        '''
        Return an image md5 and payload md5 from name and version. Order matter !
        Image md5 will still be the first
        '''
        # get file md5 from db
        a = self.db.ask("SELECT md5 FROM image WHERE name = ? AND version = ? LIMIT 1",
                        (name,version)).fetchone()
        if a is None:
            raise Exception("No such image %s version %s" % (name, version))
        b = self.db.ask("SELECT md5 FROM payload WHERE image_md5 = ?",
                        (a[0],)).fetchall()
        return [ a[0] ] + [ x[0] for x in b ]

    def last(self, name):
        '''
        Return last version of name in repo or -1 if not found
        '''
        r = self.db.ask("SELECT version FROM image WHERE name = ? ORDER BY version DESC LIMIT 1", (name,)).fetchone()
        # no row => no way
        if r is None:
            return -1
        # return last
        return r[0]


class RepositoryManager(object):
    '''
    Manage multiple repostories

    This call implement a cache and a manager for multiple repositories
    '''

    def __init__(self, cache_path=None, timeout=None, filter=None):
        self.timeout = 3 if timeout is None else timeout
        self.repos = []
        self.tempfiles = []
        self.filter = filter
        if cache_path is None:
            self.cache_path = None
            debug("No repository cache")
        else:
            if not istools.isfile(cache_path):
                raise NotImplementedError("Repository cache must be local")
            self.cache_path =  os.path.abspath(cache_path)
            # must_path is a list of directory which must exists
            # create directory if not exists
            if not os.path.exists(self.cache_path):
                os.mkdir(self.cache_path)
            # ensure directories are avaiblable
            if not os.access(self.cache_path, os.W_OK | os.X_OK):
                raise Exception("%s is not writable or executable" % self.cache_path)
            debug("Repository cache is in %s" % self.cache_path)

    def __del__(self):
        # delete temporary files (used by db)
        for f in self.tempfiles:
            try:
                debug("Removing temporary db file %s" % f)
                os.unlink(f)
            except OSError:
                pass

    def __len__(self):
        '''
        Return the number of repository registered
        '''
        return len(self.repos)


    def __getitem__(self, key):
        '''
        Return a repostiory by its position in list
        '''
        if type(key) == int:
            return self.repos[key]
        elif type(key) == str:
            for repo in self.repos:
                if repo.config.name == key:
                    return repo
            raise Exception("No repository named: %s" % key)
        else:
            raise TypeError

    def __contains__(self, key):
        '''
        Check if a key is a repository name
        '''
        for r in self.repos:
            if r.config.name == key:
                return True
        return False

    def register(self, config):
        '''
        Register a repository from its config
        '''
        # check filter on name
        if self.filter is not None:
            if not fnmatch.fnmatch(config.name, self.filter):
                return
        # if path is local, no needs to create a cache
        if istools.isfile(config.path):
            debug("Registering direct repository %s (%s)" % (config.path, config.name))
            self.repos.append(Repository(config))
        else:
            debug("Registering cached repository %s (%s)" % (config.path, config.name))
            self.repos.append(self._cachify(config))


    def _cachify(self, config):
        '''
        Return a config of a cached repository from an orignal config file
        '''
        # find destination file and load last info
        if config.name is None or self.cache_path is None:
            # this is a forced temporary repository or without name repo
            tempfd, filedest = tempfile.mkstemp()
            os.close(tempfd)
            self.tempfiles.append(filedest)
        else:
            filedest = os.path.join(self.cache_path, config.name)
            # create file if not exists
            if not os.path.exists(filedest):
                open(filedest, "wb")
        # get remote last value
        try:
            rlast = int(istools.uopen(config.lastpath,
                                      timeout=self.timeout).read().strip())
            # get local last value
            llast = int(os.stat(filedest).st_mtime)
            # if repo is out of date, download it
            if rlast != llast:
                arrow("Getting %s" % config.dbpath)
                istools.copy(config.dbpath, filedest,
                             uid=config.uid,
                             gid=config.gid,
                             mode=config.fmod,
                             timeout=self.timeout)
                os.utime(filedest, (rlast, rlast))
            config.dbpath = filedest
        except:
            # if something append bad during caching, we mark repo as offline
            config.offline = True
        return Repository(config)

    @property
    def names(self):
        '''
        Return list of repository names
        '''
        return [ r.config.name for r in self.repos ]

    @property
    def onlines(self):
        '''
        Return list of online repository names
        '''
        return [ r.config.name for r in self.repos if not r.config.offline ]

    @property
    def offlines(self):
        '''
        Return list of offlines repository names
        '''
        return [ r.config.name for r in self.repos if r.config.offline ]

    def get(self, name, version=None, best=False):
        '''
        Crawl repositories to get an image

        best mode search the most recent version accross all repo
        else it search the first match
        '''
        # search last version if needed
        if version is None:
            version = -1
            for repo in self.repos:
                if repo.config.offline: continue
                current = repo.last(name)
                # if not best mode, we found our version
                if not best and current > 0:
                    version = current
                    break
                version = max(version, current)
            # if version < 0, il n'y a pas d'image
            if version < 0:
                raise Exception("Unable to find image %s" % name)
        # search image in repos
        for repo in self.repos:
            if repo.config.offline:  continue
            if repo.has(name, version):
                return repo.get(name, version), repo
        raise Exception("Unable to find image %s v%s" % (name, version))

    def show(self, verbose=False):
        '''
        Show repository inside manager
        '''
        for repo in self.repos:
            repo.config.name
            s = "#light##blue#%s#reset#"% repo.config.name
            if verbose:
                s += " (%s)" % repo.config.path
            if repo.config.offline:
                s +=  " #light##red#[offline]#reset#"
            out(s)

    def search(self, pattern):
        '''
        Search pattern accross all registered repositories
        '''
        for repo in self.repos:
            if repo.config.offline:  continue
            arrow(repo.config.name)
            repo.search(pattern)


class RepositoryConfig(object):
    '''
    Repository configuration container
    '''

    def __init__(self, name, **kwargs):
        # set default value for arguments
        self.name = name
        self.path = ""
        self.offline = False
        self._dbpath = None
        self.dbname = "db"
        self._lastpath = None
        self.lastname = "last"
        self._uid = os.getuid()
        self._gid = os.getgid()
        umask = os.umask(0)
        os.umask(umask)
        self._fmod =  0666 & ~umask
        self._dmod =  0777 & ~umask
        self.update(**kwargs)

    def __str__(self):
        l = []
        for a in ("name", "path", "dbpath", "lastpath", "uid", "gid", "fmod", "dmod"):
            l.append("%s: %s" % (a, getattr(self, a)))
        return os.linesep.join(l)

    def __eq__(self, other):
        return vars(self) == vars(other)

    def __ne__(self, other):
        return not (self == other)

    def __contains__(self, key):
        return key in self.__dict__

    @property
    def lastpath(self):
        '''
        Return the last file complete path
        '''
        if self._lastpath is None:
            return os.path.join(self.path, self.lastname)
        return self._lastpath

    @lastpath.setter
    def lastpath(self, value):
        '''
        Set last path
        '''
        self._lastpath = value

    @property
    def dbpath(self):
        '''
        Return the db complete path
        '''
        if self._dbpath is None:
            return os.path.join(self.path, self.dbname)
        return self._dbpath

    @dbpath.setter
    def dbpath(self, value):
        '''
        Set db path
        '''
        # dbpath must be local, sqlite3 requirment
        if not istools.isfile(value):
            raise ValueError("Database path must be local")
        self._dbpath = os.path.abspath(value)

    @property
    def uid(self):
        '''
        Return owner of repository
        '''
        return self._uid

    @uid.setter
    def uid(self, value):
        '''
        Define user name owning repository
        '''
        if not value.isdigit():
            self._uid = pwd.getpwnam(value).pw_uid
        else:
            self._uid = int(value)

    @property
    def gid(self):
        '''
        Return group of the repository
        '''
        return self._gid

    @gid.setter
    def gid(self, value):
        '''
        Define group owning repository
        '''
        if not value.isdigit():
            self._gid = grp.getgrnam(value).gr_gid
        else:
            self._gid = int(value)

    @property
    def fmod(self):
        '''
        Return new file mode
        '''
        return self._fmod

    @fmod.setter
    def fmod(self, value):
        '''
        Define new file mode
        '''
        if value.isdigit():
            self._fmod = int(value, 8)
        else:
            raise ValueError("File mode must be an integer")

    @property
    def dmod(self):
        '''
        Return new directory mode
        '''
        return self._dmod

    @dmod.setter
    def dmod(self, value):
        '''
        Define new directory mode
        '''
        if value.isdigit():
            self._dmod = int(value, 8)
        else:
            raise ValueError("Directory mode must be an integer")

    def update(self, *args, **kwargs):
        '''
        Update attribute with checking value
        All attribute must already exists
        '''
        # autoset parameter in cmdline
        for k in kwargs:
            if hasattr(self, k):
                try:
                    setattr(self, k, kwargs[k])
                except Exception as e:
                    warn("Unable to set config parameter %s in repository %s: %s" % (k, self.name, e))
            else:
                debug("No such repository parameter: %s" % k)
