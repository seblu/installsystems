# -*- python -*-
# -*- coding: utf-8 -*-
# Started 10/05/2011 by Seblu <seblu@seblu.net>

'''
Repository stuff
'''

import os
import re
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
from installsystems.tools import PipeFile
from installsystems.image import Image, PackageImage
from installsystems.database import Database

class Repository(object):
    '''
    Repository class
    '''

    @staticmethod
    def is_repository_name(name):
        return re.match("^[-_\w]+$", name) is not None

    @staticmethod
    def check_repository_name(name):
        '''
        Raise exception is repository name is invalid
        '''
        if not Repository.is_repository_name(name):
            raise Exception("Invalid repository name %s" % name)
        return name

    @classmethod
    def diff(cls, repo1, repo2):
        '''
        Comptue a diff between two repositories
        '''
        arrow("Diff between repositories #y#%s#R# and #g#%s#R#" % (repo1.config.name,
                                                                   repo2.config.name))
        # Get info from databases
        i_dict1 = dict((b[0], b[1:]) for b in repo1.db.ask(
                "SELECT md5, name, version FROM image").fetchall())
        i_set1 = set(i_dict1.keys())
        i_dict2 = dict((b[0], b[1:]) for b in repo2.db.ask(
                "SELECT md5, name, version FROM image").fetchall())
        i_set2 = set(i_dict2.keys())
        p_dict1 = dict((b[0], b[1:]) for b in  repo1.db.ask(
                "SELECT md5, name FROM payload").fetchall())
        p_set1 = set(p_dict1.keys())
        p_dict2 = dict((b[0], b[1:]) for b in repo2.db.ask(
                "SELECT md5, name FROM payload").fetchall())
        p_set2 = set(p_dict2.keys())
        # computing diff
        i_only1 = i_set1 - i_set2
        i_only2 = i_set2 - i_set1
        p_only1 = p_set1 - p_set2
        p_only2 = p_set2 - p_set1
        # printing functions
        pimg = lambda r,c,m,d,: out("#%s#Image only in repository %s: %s v%s (%s)#R#" %
                                    (c, r.config.name, d[m][0], d[m][1], m))
        ppay = lambda r,c,m,d,: out("#%s#Payload only in repository %s: %s (%s)#R#" %
                                    (c, r.config.name, d[m][0], m))
        # printing image diff
        for md5 in i_only1: pimg(repo1, "y", md5, i_dict1)
        for md5 in p_only1: ppay(repo1, "y", md5, p_dict1)
        for md5 in i_only2: pimg(repo2, "g", md5, i_dict2)
        for md5 in p_only2: ppay(repo2, "g", md5, p_dict2)

    def __init__(self, config):
        self.config = config
        self.local = istools.isfile(self.config.path)
        if not self.config.offline:
            try:
                self.db = Database(config.dbpath)
            except:
                debug("Unable to load database %s" % config.dbpath)
                self.config.offline = True
        if self.config.offline:
            debug("Repository %s is offline" % config.name)

    def __getattribute__(self, name):
        '''
        Raise an error if repository is unavailable
        Unavailable can be caused because db is not accessible or
        because repository is not initialized
        '''
        config = object.__getattribute__(self, "config")
        # config, init, local are always accessible
        if name in ("init", "config", "local"):
            return object.__getattribute__(self, name)
        # if no db (not init or not accessible) raise error
        if config.offline:
            raise Exception("Repository %s is offline" % config.name)
        return object.__getattribute__(self, name)

    @property
    def version(self):
        '''
        Return repository version
        '''
        return self.db.version

    def init(self):
        '''
        Initialize an empty base repository
        '''
        config = self.config
        # check local repository
        if not self.local:
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
        if not self.local:
            raise Exception("Repository addition must be local")
        try:
            arrow("Updating last file")
            last_path = os.path.join(self.config.path, self.config.lastname)
            open(last_path, "w").write("%s\n" % int(time.time()))
            istools.chrights(last_path, self.config.uid, self.config.gid, self.config.fmod)
        except Exception as e:
            raise Exception("Update last file failed: %s" % e)

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

    def add(self, image, delete=False):
        '''
        Add a packaged image to repository
        if delete is true, remove original files
        '''
        # check local repository
        if not self.local:
            raise Exception("Repository addition must be local")
        # cannot add already existant image
        if self.has(image.name, image.version):
            raise Exception("Image already in database, delete first!")
        # adding file to repository
        arrow("Copying images and payload")
        for obj in [ image ] + image.payload.values():
            dest = os.path.join(self.config.path, obj.md5)
            basesrc = os.path.basename(obj.path)
            if os.path.exists(dest):
                arrow("Skipping %s: already exists" % basesrc, 1)
            else:
                arrow("Adding %s (%s)" % (basesrc, obj.md5), 1)
                dfo = open(dest, "wb")
                sfo = PipeFile(obj.path, "r", progressbar=True)
                sfo.consume(dfo)
                sfo.close()
                dfo.close()
                istools.chrights(dest, self.config.uid,
                                 self.config.gid, self.config.fmod)
        # copy is done. create a image inside repo
        r_image = PackageImage(os.path.join(self.config.path, image.md5),
                               md5name=True)
        # checking must be done with original md5
        r_image.md5 = image.md5
        # checking image and payload after copy
        r_image.check("Check image and payload")
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

    def getallmd5(self):
        '''
        Get list of all md5 in DB
        '''
        res = self.db.ask("SELECT md5 FROM image UNION SELECT md5 FROM payload").fetchall()
        return [ md5[0] for md5 in res ]

    def check(self):
        '''
        Check repository for unreferenced and missing files
        '''
        # Check if the repo is local
        if not self.local:
            raise Exception("Repository must be local")
        local_files = set(os.listdir(self.config.path))
        local_files.remove(self.config.dbname)
        local_files.remove(self.config.lastname)
        db_files = set(self.getallmd5())
        # check missing files
        arrow("Checking missing files")
        missing_files = db_files - local_files
        if len(missing_files) > 0:
            out(os.linesep.join(missing_files))
        # check unreferenced files
        arrow("Checking unreferenced files")
        unref_files = local_files - db_files
        if len(unref_files) > 0:
            out(os.linesep.join(unref_files))
        # check corruption of local files
        arrow("Checking corrupted files")
        for f in local_files:
            fo = PipeFile(os.path.join(self.config.path, f))
            fo.consume()
            fo.close()
            if fo.md5 != f:
                out(f)

    def clean(self, force=False):
        '''
        Clean the repository's content
        '''
        # Check if the repo is local
        if not self.local:
            raise Exception("Repository must be local")
        allmd5 = set(self.getallmd5())
        repofiles = set(os.listdir(self.config.path)) - set([self.config.dbname, self.config.lastname])
        dirtyfiles = repofiles - allmd5
        if len(dirtyfiles) > 0:
            # print dirty files
            arrow("Dirty files:")
            for f in dirtyfiles:
                arrow(f, 1)
            # ask confirmation
            if not force and not confirm("Remove dirty files? (yes) "):
                raise Exception("Aborted!")
            # start cleaning
            arrow("Cleaning")
            for f in dirtyfiles:
                p = os.path.join(self.config.path, f)
                arrow("Removing %s" % p, 1)
                try:
                    if os.path.isdir(p):
                        os.rmdir(p)
                    else:
                        os.unlink(p)
                except:
                    warn("Removing %s failed" % p)
        else:
            arrow("Nothing to clean")

    def delete(self, name, version, payloads=True):
        '''
        Delete an image from repository
        '''
        # check local repository
        if not self.local:
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
        # Removing files
        arrow("Removing files from pool")
        # if asked don't remove payloads
        if not payloads:
            md5s = [ md5s[0] ]
        arrowlevel(1)
        for md5 in md5s:
            self._remove_file(md5)
        arrowlevel(-1)
        # update last file
        self.update_last()

    def images(self):
        '''
        Return a dict of informations on images
        '''
        db_images = self.db.ask("SELECT md5, name, version, date,\
                author, description, size FROM image ORDER BY name, version").fetchall()
        images = []
        field = ("md5", "name", "version", "date", "author", "description", "size")
        for info in db_images:
            d = dict(zip(field, info))
            d["repo"] = self.config.name
            d["url"] = os.path.join(self.config.path, d["md5"])
            images.append(d)
        return images

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
            raise Exception("Unable to find image %s v%s in %s" % (name, version,
                                                                   self.config.name))
        path = os.path.join(self.config.path, r[0])
        # getting the file
        arrow("Loading image %s v%s from repository %s" % (name,
                                                           version,
                                                           self.config.name))
        memfile = cStringIO.StringIO()
        try:
            fo = PipeFile(path, "r")
            fo.consume(memfile)
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


class RepositoryManager(object):
    '''
    Manage multiple repostories

    This call implement a cache and a manager for multiple repositories
    '''

    def __init__(self, cache_path=None, timeout=None, filter=None):
        self.timeout = 3 if timeout is None else timeout
        self.repos = []
        self.tempfiles = []
        self.filter = [] if filter is None else filter
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

    def register(self, config, temp=False, nosync=False, offline=False):
        '''
        Register a repository from its config
        temp: repository is stored in a temporary location
        nosync: register repository as online, but no sync is done before
        offline: repository is marked offline
        '''
        # check filter on name
        if len(self.filter) > 0:
            if config.name not in self.filter:
                debug("Filtering repository %s" % config.name)
                return
        # repository is offline
        if config.offline or offline:
            debug("Registering offline repository %s (%s)" % (config.path, config.name))
            # we must force offline in cast of argument offline
            config.offline = True
            self.repos.append(Repository(config))
        # if path is local, no needs to create a cache
        elif istools.isfile(config.path):
            debug("Registering direct repository %s (%s)" % (config.path, config.name))
            self.repos.append(Repository(config))
        # path is remote, we need to create a cache
        else:
            debug("Registering cached repository %s (%s)" % (config.path, config.name))
            self.repos.append(self._cachify(config, temp, nosync))

    def _cachify(self, config, temp=False, nosync=False):
        '''
        Return a config of a cached repository from an orignal config file
        :param config: repository configuration
        :param temp: repository db should be stored in a temporary location
        :param nosync: if a cache exists, don't try to update it
        '''
        # if cache is disable => temp =True
        if self.cache_path is None:
            temp = True
        try:
            original_dbpath = config.dbpath
            if temp and nosync:
                raise IOError("sync is disabled")
            elif temp:
                # this is a temporary cached repository
                tempfd, config.dbpath = tempfile.mkstemp()
                os.close(tempfd)
                self.tempfiles.append(config.dbpath)
            else:
                config.dbpath = os.path.join(self.cache_path, config.name)
            if not nosync:
                # Open remote database
                rdb = PipeFile(original_dbpath, timeout=self.timeout)
                # get remote last modification
                if rdb.mtime is None:
                    # We doesn't have modification time, we use the last file
                    try:
                        rlast = int(PipeFile(config.lastpath, mode='r',
                                             timeout=self.timeout).read().strip())
                    except IOError:
                        rlast = -1
                else:
                    rlast = rdb.mtime
                # get local last value
                if os.path.exists(config.dbpath):
                    llast = int(os.stat(config.dbpath).st_mtime)
                else:
                    llast = -2
                # if repo is out of date, download it
                if rlast != llast:
                    try:
                        arrow("Downloading %s" % original_dbpath)
                        rdb.progressbar = True
                        ldb = open(config.dbpath, "wb")
                        rdb.consume(ldb)
                        ldb.close()
                        rdb.close()
                        istools.chrights(config.dbpath,
                                         uid=config.uid,
                                         gid=config.gid,
                                         mode=config.fmod,
                                         mtime=rlast)
                    except:
                        if os.path.exists(config.dbpath):
                            os.unlink(config.dbpath)
                        raise
        except IOError as e:
            # if something append bad during caching, we mark repo as offline
            debug("Unable to cache repository %s: %s" % (config.name, e))
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

    def images(self, pattern, all_version=True, search=None):
        '''
        Return a list of available images
        '''
        if search is None:
            search = self.onlines
        # building image list
        images = {}
        for reponame in search:
            for img in self[reponame].images():
                imgname = u"%s/%s:%s" % (reponame, img["name"], img["version"])
                images[imgname] = img
        if u"/" in pattern:
            # filter with pattern on path
            for k in images.keys():
                if not fnmatch.fnmatch(k, pattern):
                    del images[k]
        else:
            # filter on image name
            for k, v in images.items():
                if not fnmatch.fnmatch(v["name"], pattern):
                    del images[k]
        # filter multiple versions
        if not all_version:
            for repo in set((images[i]["repo"] for i in images)):
                for img in set((images[i]["name"] for i in images if images[i]["repo"] == repo)):
                    versions = [ images[i]['version']
                                 for i in images if images[i]["repo"] == repo and images[i]["name"] == img ]
                    f = lambda x,y: x if istools.compare_versions(x, y) > 0 else y
                    last = reduce(f, versions)
                    versions.remove(last)
                    for rmv in versions:
                        del images["%s/%s:%s" % (repo, img, rmv)]
        return images

    def get(self, name, version=None, search=None, best=False):
        '''
        Crawl searchable repositories to get an image

        best mode search the most recent version accross all repo
        else it search the first match
        '''
        if search is None:
            search = []
        # search last version if needed
        if version is None:
            version = -1
            for repo in search:
                current = self[repo].last(name)
                # if not best mode, we found our version
                if not best and current > 0:
                    version = current
                    break
                version = max(version, current)
            # if version < 0, il n'y a pas d'image
            if version < 0:
                raise Exception("Unable to find image %s in %s" % (
                        name, search))
        # search image in repos
        for repo in search:
            if self[repo].has(name, version):
                return self[repo].get(name, version), self[repo]
        raise Exception("No image %s v%s in %s" % (
                name, version, search))

    def search(self, pattern):
        '''
        Search pattern accross all registered repositories
        '''
        for repo in self.onlines:
            arrow(repo.config.name)
            repo.search(pattern)

    def purge_cache(self, pattern):
        '''
        Remove local cached repository files
        '''
        for reponame in fnmatch.filter(self.names, pattern):
            arrow("Purging cache of repository %s" % reponame)
            db = os.path.join(self.cache_path, reponame)
            if os.path.exists(db):
                try:
                    os.unlink(db)
                    arrow("done", 1)
                except:
                    arrow("failed", 1)
            else:
                arrow("nothing to do", 1)


class RepositoryConfig(object):
    '''
    Repository configuration container
    '''

    def __init__(self, name, **kwargs):
        # set default value for arguments
        self.name = Repository.check_repository_name(name)
        self.path = ""
        self._offline = False
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
        for a in ("name", "path", "dbpath", "lastpath", "uid", "gid", "fmod", "dmod", "offline"):
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

    @property
    def offline(self):
        '''
        Get the offline state of a repository
        '''
        return self._offline

    @offline.setter
    def offline(self, value):
        if type(value) in (str, unicode):
            value = value.lower() not in ("false", "no", "0")
        elif type(value) is not bool:
            value = bool(value)
        self._offline = value

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
