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
Repository stuff
'''

from installsystems.tools import islocal

class Repository1(object):
    '''
    Repository class
    '''

    def __init__(self, config):
        self.config = config
        self.local = islocal(config.path)
        if not self.config.offline:
            try:
                self.db = Database(config.dbpath)
            except:
                debug(u"Unable to load database %s" % config.dbpath)
                self.config.offline = True
        if self.config.offline:
            debug(u"Repository %s is offline" % config.name)

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
            raise ISError(u"Repository %s is offline" % config.name)
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
            raise ISError(u"Repository creation must be local")
        # create base directories
        arrow("Creating base directories")
        arrowlevel(1)
        # creating local directory
        try:
            if os.path.exists(config.path):
                arrow(u"%s already exists" % config.path)
            else:
                istools.mkdir(config.path, config.uid, config.gid, config.dmod)
                arrow(u"%s directory created" % config.path)
        except Exception as e:
            raise ISError(u"Unable to create directory %s" % config.path, e)
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
            raise ISError(u"Repository addition must be local")
        try:
            arrow("Updating last file")
            last_path = os.path.join(self.config.path, self.config.lastname)
            open(last_path, "w").write("%s\n" % int(time.time()))
            istools.chrights(last_path, self.config.uid, self.config.gid, self.config.fmod)
        except Exception as e:
            raise ISError(u"Update last file failed", e)

    def last(self, name):
        '''
        Return last version of name in repo or None if not found
        '''
        r = self.db.ask("SELECT version FROM image WHERE name = ?", (name,)).fetchall()
        # no row => no way
        if r is None:
            return None
        f = lambda x,y: x[0] if istools.compare_versions(x[0], y[0]) > 0 else y[0]
        # return last
        return reduce(f, r)

    def add(self, image, delete=False):
        '''
        Add a packaged image to repository
        if delete is true, remove original files
        '''
        # check local repository
        if not self.local:
            raise ISError(u"Repository addition must be local")
        # cannot add already existant image
        if self.has(image.name, image.version):
            raise ISError(u"Image already in database, delete first!")
        # adding file to repository
        arrow("Copying images and payload")
        for obj in [ image ] + image.payload.values():
            dest = os.path.join(self.config.path, obj.md5)
            basesrc = os.path.basename(obj.path)
            if os.path.exists(dest):
                arrow(u"Skipping %s: already exists" % basesrc, 1)
            else:
                arrow(u"Adding %s (%s)" % (basesrc, obj.md5), 1)
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
            raise ISError(u"Repository must be local")
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
            raise ISError(u"Repository must be local")
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
                raise ISError(u"Aborted!")
            # start cleaning
            arrow("Cleaning")
            for f in dirtyfiles:
                p = os.path.join(self.config.path, f)
                arrow(u"Removing %s" % p, 1)
                try:
                    if os.path.isdir(p):
                        os.rmdir(p)
                    else:
                        os.unlink(p)
                except:
                    warn(u"Removing %s failed" % p)
        else:
            arrow("Nothing to clean")

    def delete(self, name, version, payloads=True):
        '''
        Delete an image from repository
        '''
        # check local repository
        if not self.local:
            raise ISError(u"Repository deletion must be local")
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
        Return a dict of information on images
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

    def payloads(self):
        '''
        Return a dict of information on payloads
        '''
        db_payloads = self.db.ask("SELECT payload.md5,payload.size,payload.isdir,image.name,image.version,payload.name FROM payload inner join image on payload.image_md5 = image.md5").fetchall()
        res = {}
        for payload in db_payloads:
            md5 = payload[0]
            # create entry if not exists
            if md5 not in res:
                res[md5] = {"size": payload[1], "isdir": payload[2], "images": {}}
            # add image to list
            imgpath = u"%s/%s:%s" % (self.config.name, payload[3], payload[4])
            res[md5]["images"][imgpath] = {"repo": self.config.name,
                                           "imgname": payload[3],
                                           "imgver": payload[4],
                                           "payname": payload[5]}
        return res

    def search(self, pattern):
        '''
        Search pattern in a repository
        '''
        images = self.db.ask("SELECT name, version, author, description\
                              FROM image\
                              WHERE name LIKE ? OR\
                              description LIKE ? OR\
                              author LIKE ?",
                             tuple( [u"%%%s%%" % pattern ] * 3)
                             ).fetchall()
        for name, version, author, description in images:
            arrow(u"%s v%s" % (name, version), 1)
            out(u"   #yellow#Author:#reset# %s" % author)
            out(u"   #yellow#Description:#reset# %s" % description)

    def _remove_file(self, filename):
        '''
        Remove a filename from pool. Check if it's not needed by db before
        '''
        # check existance in table image
        have = False
        for table in ("image", "payload"):
            have = have or  self.db.ask(u"SELECT md5 FROM %s WHERE md5 = ? LIMIT 1" % table,
                                        (filename,)).fetchone() is not None
        # if no reference, delete!
        if not have:
            arrow(u"%s, deleted" % filename)
            os.unlink(os.path.join(self.config.path, filename))
        else:
            arrow(u"%s, skipped" % filename)

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
            if version is None:
                raise ISError(u"Unable to find image %s in %s" % (name,
                                                                      self.config.name))
        # get file md5 from db
        r = self.db.ask("select md5 from image where name = ? and version = ? limit 1",
                        (name, version)).fetchone()
        if r is None:
            raise ISError(u"Unable to find image %s v%s in %s" % (name, version,
                                                                      self.config.name))
        path = os.path.join(self.config.path, r[0])
        # getting the file
        arrow(u"Loading image %s v%s from repository %s" % (name,
                                                            version,
                                                            self.config.name))
        memfile = cStringIO.StringIO()
        try:
            fo = PipeFile(path, "r")
            fo.consume(memfile)
            fo.close()
        except Exception as e:
            raise ISError(u"Loading image %s v%s failed" % (name, version), e)
        memfile.seek(0)
        pkg = PackageImage(path, fileobj=memfile, md5name=True)
        if pkg.md5 != r[0]:
            raise ISError(u"Image MD5 verification failure")
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
            raise ISError(u"No such image %s version %s" % (name, version))
        b = self.db.ask("SELECT md5 FROM payload WHERE image_md5 = ?",
                        (a[0],)).fetchall()
        return [ a[0] ] + [ x[0] for x in b ]


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
            conn.executescript(istemplate.createdb)
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
            r = self.ask("SELECT value FROM misc WHERE key = 'version'").fetchone()
            if r is None:
                raise TypeError()
            self.version = float(r[0])
        except:
            self.version = 1.0
        # we only support database v1
        if self.version >= 2.0:
            debug(u"Invalid database format: %s" % self.version)
            raise ISError("Invalid database format")
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
