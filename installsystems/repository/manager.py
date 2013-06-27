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
Repository management module
'''

from installsystems.exception import ISError, ISWarning
from installsystems.printer import out, debug, arrow
from installsystems.repository import split_path
from installsystems.repository.factory import RepositoryFactory
from installsystems.tools import islocal, chrights, PipeFile, compare_versions
from installsystems.tools import time_rfc2822, human_size, strcspn
from json import dumps
from os import mkdir, access, W_OK, X_OK, unlink, stat, linesep, close
from os.path import abspath, exists, lexists, join
from string import hexdigits
from tempfile import mkstemp

# use module prefix because a function is named filter
import fnmatch

class RepositoryManager(object):
    '''
    Manage multiple repositories

    This call implement a cache and a manager for multiple repositories
    Default repository timeout is 3
    '''

    def __init__(self, cache_path=None, timeout=None, filter=None, search=None):
        self.repos = []
        self.tempfiles = []
        self.filter = [] if filter is None else filter
        self.search = [] if search is None else search
        self.timeout = timeout or 3
        debug(u"Repository timeout setted to %ds" % self.timeout)
        if cache_path is None:
            self.cache_path = None
            debug("No repository cache")
        else:
            if not islocal(cache_path):
                raise NotImplementedError("Repository cache must be local")
            self.cache_path =  abspath(cache_path)
            # must_path is a list of directory which must exists
            # create directory if not exists
            if not exists(self.cache_path):
                mkdir(self.cache_path)
            # ensure directories are avaiblable
            if not access(self.cache_path, W_OK | X_OK):
                raise ISError(u"%s is not writable or executable" % self.cache_path)
            debug(u"Repository cache is in %s" % self.cache_path)

    def __del__(self):
        # delete temporary files (used by db)
        for f in self.tempfiles:
            try:
                debug(u"Removing temporary db file %s" % f)
                unlink(f)
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
        if isinstance(key, int):
            return self.repos[key]
        elif isinstance(key, basestring):
            # match name
            for repo in self.repos:
                if repo.config.name == key:
                    return repo
            raise IndexError(u"No repository named: %s" % key)
        else:
            raise TypeError(u"Invalid type %s for %s" % (type(key), key))

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
                debug(u"Filtering repository %s" % config.name)
                return
        # repository is offline
        if config.offline or offline:
            debug(u"Registering offline repository %s (%s)" % (config.path, config.name))
            # we must force offline in cast of argument offline
            config.offline = True
            self.repos.append(RepositoryFactory(config))
        # if path is local, no needs to create a cache
        elif islocal(config.path):
            debug(u"Registering direct repository %s (%s)" % (config.path, config.name))
            self.repos.append(RepositoryFactory(config))
        # path is remote, we need to create a cache
        else:
            debug(u"Registering cached repository %s (%s)" % (config.path, config.name))
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
                raise ISError("sync is disabled")
            elif temp:
                # this is a temporary cached repository
                tempfd, config.dbpath = mkstemp()
                close(tempfd)
                self.tempfiles.append(config.dbpath)
            else:
                config.dbpath = join(self.cache_path, config.name)
            if not nosync:
                # Open remote database
                rdb = PipeFile(original_dbpath, timeout=self.timeout)
                # get remote last modification
                if rdb.mtime is None:
                    # We doesn't have modification time, we use the last file
                    try:
                        rlast = int(PipeFile(config.lastpath, mode='r',
                                             timeout=self.timeout).read().strip())
                    except ISError:
                        rlast = -1
                else:
                    rlast = rdb.mtime
                # get local last value
                if exists(config.dbpath):
                    llast = int(stat(config.dbpath).st_mtime)
                else:
                    llast = -2
                # if repo is out of date, download it
                if rlast != llast:
                    try:
                        arrow(u"Downloading %s" % original_dbpath)
                        rdb.progressbar = True
                        ldb = open(config.dbpath, "wb")
                        rdb.consume(ldb)
                        ldb.close()
                        rdb.close()
                        chrights(config.dbpath,
                                         uid=config.uid,
                                         gid=config.gid,
                                         mode=config.fmod,
                                         mtime=rlast)
                    except:
                        if exists(config.dbpath):
                            unlink(config.dbpath)
                        raise
        except ISError as e :
            # if something append bad during caching, we mark repo as offline
            debug(u"Unable to cache repository %s: %s" % (config.name, e))
            config.offline = True
        return RepositoryFactory(config)

    @property
    def names(self):
        '''
        Return list of repository names
        '''
        return [ r.config.name for r in self.repos ]

    @property
    def uuids(self):
        '''
        Return a dict of repository UUID and associated names
        '''
        d = {}
        for r in self.repos:
            uuid = r.uuid
            if uuid is None:
                continue
            if uuid in d:
                d[uuid].append(r)
            else:
                d[uuid] = [r]
        return d

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

    def select_images(self, patterns):
        '''
        Return a list of available images
        '''
        if len(self.onlines) == 0:
            raise ISError(u"No online repository")
        ans = {}
        for pattern in patterns:
            path, image, version = split_path(pattern)
            if image is None:
                if path is None or version is None:
                    image = "*"
                else:
                    # empty pattern
                    continue
            # building image list
            images = {}
            for reponame in self.onlines:
                for img in self[reponame].images():
                    imgname = u"%s/%s:%s" % (reponame, img["name"], img["version"])
                    images[imgname] = img
            # No path means only in searchable repositories
            if path is None:
                for k, v in images.items():
                    # match name
                    if v["repo"] not in self.search and self[v["repo"]].uuid not in self.search:
                        del images[k]
                path = "*"
            # No version means last version
            if version is None:
                version = "*"
                for repo in set((images[i]["repo"] for i in images)):
                    for img in set((images[i]["name"] for i in images if images[i]["repo"] == repo)):
                        versions = [ images[i]['version']
                                     for i in images if images[i]["repo"] == repo and images[i]["name"] == img ]
                        f = lambda x,y: x if compare_versions(x, y) > 0 else y
                        last = reduce(f, versions)
                        versions.remove(last)
                        for rmv in versions:
                            del images[u"%s/%s:%s" % (repo, img, rmv)]
            # if 'path*' do not match a repo name, it may be an uuid, so add
            # globbing for smart uuid matching
            if not fnmatch.filter(self.onlines, "%s*" % path):
                path = "%s*" % path
            # filter with pattern on path
            filter_pattern = u"%s/%s:%s" % (path, image, version)
            for k, img in images.items():
                if not (fnmatch.fnmatch(k, filter_pattern) or
                        fnmatch.fnmatch("%s/%s" % (self[img["repo"]].uuid, k.split("/")[1]), filter_pattern)):
                    del images[k]
            ans.update(images)
        return ans

    def search_image(self, pattern):
        '''
        Search pattern accross all registered repositories
        '''
        for repo in self.onlines:
            arrow(self[repo].config.name)
            self[repo].search(pattern)

    def show_images(self, patterns, o_json=False, o_long=False, o_md5=False,
                    o_date=False, o_author=False, o_size=False, o_url=False,
                    o_description=False, o_format=False, o_min_version=False):
        '''
        Show images inside manager
        '''
        # get images list
        images = self.select_images(patterns)
        # display result
        if o_json:
            s = dumps(images)
        else:
            l = []
            for imgp in sorted(images.keys()):
                img = images[imgp]
                l.append(u"%s#R#/#l##b#%s#R#:#p#%s#R#" % (
                        img["repo"], img["name"], img["version"]))
                if o_md5 or o_long:
                    l[-1] = l[-1] + u" (#y#%s#R#)" % img["md5"]
                if o_date or o_long:
                    l.append(u"  #l#date:#R# %s" % time_rfc2822(img["date"]))
                if o_author or o_long:
                    l.append(u"  #l#author:#R# %s" % img["author"])
                if o_size or o_long:
                    l.append(u"  #l#size:#R# %s" % human_size(img["size"]))
                if o_url or o_long:
                    l.append(u"  #l#url:#R# %s" % img["url"])
                if o_description or o_long:
                    l.append(u"  #l#description:#R# %s" % img["description"])
                if o_format or o_long:
                    l.append(u"  #l#format:#R# %s" % img["format"])
                if o_min_version or o_long:
                    l.append(u"  #l#is min version:#R# %s" % img["is_min_version"])
            s = linesep.join(l)
        if len(s) > 0:
            out(s)

    def select_payloads(self, patterns):
        '''
        Return a list of available payloads
        '''
        if len(self.onlines) == 0:
            raise ISError(u"No online repository")
        # building payload list
        paylist = {}
        for reponame in self.onlines:
            for md5, info in self[reponame].payloads().items():
                if md5 not in paylist:
                    paylist[md5] = info
                else:
                    paylist[md5]["images"].update(info["images"])
        # check if pattern is md5 startpath
        ans = {}
        for pattern in patterns:
            for md5 in paylist.keys():
                if md5.startswith(pattern):
                    ans[md5] = paylist[md5]
        return ans

    def show_payloads(self, patterns, o_images=False, o_json=False):
        '''
        Show payloads inside manager
        '''
        # get payload list
        payloads = self.select_payloads(patterns)
        # display result
        if o_json:
            s = dumps(payloads)
        else:
            l = []
            for payname in sorted(payloads.keys()):
                pay = payloads[payname]
                l.append(u"#l##y#%s#R#" % payname)
                l.append(u" size: %s" % human_size(pay["size"]))
                l.append(u" directory: %s" % bool(pay["isdir"]))
                l.append(u" image count: %d" % len(pay["images"]))
                l.append(u" names: %s" % ", ".join(set((v["payname"] for v in pay["images"].values()))))
                if o_images:
                    l.append(u" images:")
                    for path, obj in pay["images"].items():
                        l.append(u"   %s#R#/#l##b#%s#R#:#p#%s#R# (%s)" % (
                                obj["repo"], obj["imgname"], obj["imgver"], obj["payname"]))
            s = linesep.join(l)
        if len(s) > 0:
            out(s)

    def select_repositories(self, patterns):
        '''
        Return a list of repository
        '''
        ans = set()
        uuidb = self.uuids
        for pattern in patterns:
            ans |= set(fnmatch.filter(self.names, pattern))
            if strcspn(pattern, hexdigits + "-") == 0:
                for uuid in filter(lambda x: x.startswith(pattern), uuidb.keys()):
                    ans |= set((r.config.name for r in uuidb[uuid]))
        return sorted(ans)

    def purge_repositories(self, patterns):
        '''
        Remove local cached repository files
        '''
        for reponame in self.select_repositories(patterns):
            arrow(u"Purging cache of repository %s" % reponame)
            db = join(self.cache_path, reponame)
            if lexists(db):
                try:
                    unlink(db)
                    arrow("done", 1)
                except:
                    arrow("failed", 1)
            else:
                arrow("nothing to do", 1)

    def show_repositories(self, patterns, local=None, online=None, o_url=False,
                          o_state=False, o_uuid=False, o_json=False, o_version=False):
        '''
        Show repository inside manager
        if :param online: is true, list only online repositories
        if :param online: is false, list only offline repostiories
        if :param online: is None, list both online and offline repostiories.
        if :param local: is true, list only local repositories
        if :param local: is false, list only remote repostiories
        if :param local: is None, list both local and remote repostiories.
        '''
        # build repositories dict
        repos = {}
        for reponame in self.select_repositories(patterns):
            repo = self[reponame]
            if repo.config.offline and online is True:
                continue
            if not repo.config.offline and online is False:
                continue
            if repo.local and local is False:
                continue
            if not repo.local and local is True:
                continue
            repos[reponame] = dict(repo.config.items())
            repos[reponame]["local"] = repo.local
            if not repo.config.offline:
                repos[reponame]["uuid"] = repo.uuid
                repos[reponame]["version"] = repo.version
        # display result
        if o_json:
            s = dumps(repos)
        else:
            l = []
            for name, repo in repos.items():
                ln = ""
                so = "#l##r#Off#R# " if repo["offline"] else "#l##g#On#R#  "
                sl = "#l##y#Local#R#  " if repo["local"] else "#l##c#Remote#R# "
                rc = "#l##r#" if repo["offline"] else "#l##g#"
                if o_state:
                    ln +=  u"%s%s " % (so, sl)
                    rc = "#l##b#"
                ln += u"%s%s#R#"% (rc, name)
                if o_url:
                    ln += u"  (%s)" % repo["path"]
                if not repo["offline"]:
                    if o_version:
                        ln += u"  (#p#v%s#R#)" % repo["version"]
                    if o_uuid and repo["uuid"] is not None:
                        ln += u"  [%s]" % repo["uuid"]
                l.append(ln)
            s = linesep.join(l)
        out(s)

class Database(object):
    '''
    Abstract repo database stuff
    It needs to be local cause of sqlite3 which need to open a file
    '''

    version = 2.0

    @classmethod
    def create(cls, path):
        arrow("Creating repository database")
        # check locality
        if not istools.isfile(path):
            raise ISError("Database creation must be local")
        path = os.path.abspath(path)
        if os.path.exists(path):
            raise ISError("Database already exists. Remove it before")
        try:
            conn = sqlite3.connect(path, isolation_level=None)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(TEMPLATE_EMPTY_DB)
            conn.execute("INSERT INTO repository values (?,?,?)",
                         (str(uuid.uuid4()), Database.version, "",))
            conn.commit()
            conn.close()
        except Exception as e:
            raise ISError(u"Create database failed", e)
        return cls(path)

    def __init__(self, path):
        # check locality
        if not istools.isfile(path):
            raise ISError("Database must be local")
        self.path = os.path.abspath(path)
        if not os.path.exists(self.path):
            raise ISError("Database not exists")
        self.conn = sqlite3.connect(self.path, isolation_level=None)
        self.conn.execute("PRAGMA foreign_keys = ON")
        # get database version
        try:
            r = self.ask("SELECT version FROM repository").fetchone()
            if r is None:
                raise TypeError()
            self.version = float(r[0])
        except:
            self.version = 1.0
        if math.floor(self.version) >= math.floor(Database.version) + 1.0:
            raise ISWarning(u"New database format (%s), please upgrade "
                            "your Installsystems version" % self.version)
        # we make a query to be sure format is valid
        try:
            self.ask("SELECT * FROM image")
        except:
            debug(u"Invalid database format: %s" % self.version)
            raise ISError("Invalid database format")

    def begin(self):
        '''
        Start a db transaction
        '''
        self.conn.execute("BEGIN TRANSACTION")

    def commit(self):
        '''
        Commit current db transaction
        '''
        self.conn.execute("COMMIT TRANSACTION")


    def ask(self, sql, args=()):
        '''
        Ask question to db
        '''
        return self.conn.execute(sql, args)


TEMPLATE_EMPTY_DB = u"""
CREATE TABLE image (md5 TEXT NOT NULL PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    date INTEGER NOT NULL,
                    author TEXT,
                    description TEXT,
                    size INTEGER NOT NULL,
                    is_min_version INTEGER NOT NULL,
                    format INTEGER NOT NULL,
                    UNIQUE(name, version));

CREATE TABLE payload (md5 TEXT NOT NULL,
                      image_md5 TEXT NOT NULL REFERENCES image(md5),
                      name TEXT NOT NULL,
                      isdir INTEGER NOT NULL,
                      size INTEGER NOT NULL,
                      PRIMARY KEY(md5, image_md5));

CREATE TABLE repository (uuid TEXT NOT NULL PRIMARY KEY,
                         version FLOAT NOT NULL,
                         motd TEXT NOT NULL);
"""
