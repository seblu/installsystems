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
Database stuff
'''

import math
import os
import sqlite3
import uuid
import installsystems.tools as istools
from installsystems.exception import *
from installsystems.printer import *

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
