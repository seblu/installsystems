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
Repository v1
'''

from installsystems.image.package import PackageImage
from installsystems.printer import arrow, arrowlevel, warn, info
from installsystems.repository.config import RepositoryConfig
from installsystems.repository.database import Database
from installsystems.repository.repository import Repository
from os import listdir, unlink, symlink
from os.path import join, exists
from shutil import move, rmtree
from tempfile import mkdtemp

class Repository1(Repository):

    def _add(self, image):
        '''
        Add description to db
        '''
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
        # insert data information
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

    def images(self):
        '''
        Return a dict of information on images
        '''
        db_images = self.db.ask("SELECT md5, name, version, date, author, \
                           description, size \
                           FROM image ORDER BY name, version").fetchall()

        images = []
        field = ("md5", "name", "version", "date", "author", "description",
                 "size")
        for info in db_images:
            d = dict(zip(field, info))
            d["repo"] = self.config.name
            d["url"] = join(self.config.path, d["md5"])
            d["format"] = 1
            d["is_min_version"] = 9
            images.append(d)
        return images

    @property
    def uuid(self):
        '''
        Repository v1 doesn't support UUID
        '''
        return None

    @property
    def motd(self):
        '''
        Return repository message of the day.
        Repository v1 don't have message of day
        '''
        return None

    def setmotd(self, value=""):
        '''
        Don't set repository message of the day. Not supported by v1.
        '''
        # check local repository
        warn(u"Repository v1 doesn't support motd. Unable to set")

    @property
    def version(self):
        '''
        Return repository version
        '''
        return 1

    def upgrade(self):
        raise NotImplementedError()
        # if self.version == Database.version:
        #     info("Repository already up-to-date (%s)" % self.version)
        #     return
        # else:
        #     arrow("Start repository upgrade")
        #     arrowlevel(1)
        #     # Create dummy repository
        #     tmpdir = mkdtemp()
        #     try:
        #         repoconf = RepositoryConfig("tmp_migrate_repo", path=tmpdir)
        #         dstrepo = Repository(repoconf)
        #         # Symlink content from repository into dummy repo
        #         for file in listdir(self.config.path):
        #             symlink(join(self.config.path, file),
        #                     join(tmpdir, file))
        #         unlink(repoconf.dbpath)
        #         unlink(repoconf.lastpath)
        #         old_verbosity = installsystems.verbosity
        #         arrow("Initialize new database")
        #         # Disable unwanted message during upgrade
        #         installsystems.verbosity = 0
        #         dstrepo.init()
        #         # Restore verbosity
        #         installsystems.verbosity = old_verbosity
        #         md5s = self.db.ask("SELECT md5 FROM image").fetchall()
        #         # Copy images to dummy repository (fill new database)
        #         arrow("Fill database with images")
        #         arrowlevel(1)
        #         installsystems.verbosity = 0
        #         for img in [PackageImage(join(self.config.path, md5[0]),
        #                                  md5name=True) for md5 in md5s]:
        #             installsystems.verbosity = old_verbosity
        #             arrow("%s v%s" % (img.name, img.version))
        #             installsystems.verbosity = 0
        #             dstrepo.add(img)
        #         installsystems.verbosity = old_verbosity
        #         arrowlevel(-1)
        #         arrow("Backup old database")
        #         move(self.config.dbpath,
        #                     join("%s.bak" % self.config.dbpath))
        #         # Replace old db with the new from dummy repository
        #         move(repoconf.dbpath, self.config.dbpath)
        #         self.update_last()
        #         arrowlevel(-1)
        #         arrow("Repository upgrade complete")
        #     finally:
        #         # Remove dummy repository
        #         rmtree(tmpdir)
