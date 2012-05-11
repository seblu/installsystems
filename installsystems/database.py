# -*- python -*-
# -*- coding: utf-8 -*-
# Started 24/05/2011 by Seblu <seblu@seblu.net>

'''
Database stuff
'''

import os
import sqlite3
import installsystems.tools as istools
import installsystems.template as istemplate
from installsystems.tarball import Tarball
from installsystems.printer import *

class Database(object):
    '''
    Abstract repo database stuff
    It needs to be local cause of sqlite3 which need to open a file
    '''

    @classmethod
    def create(cls, path):
        arrow("Creating repository database")
        # check locality
        if not istools.isfile(path):
            raise Exception("Database creation must be local")
        path = os.path.abspath(path)
        if os.path.exists(path):
            raise Exception("Database already exists. Remove it before")
        try:
            conn = sqlite3.connect(path, isolation_level=None)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(istemplate.createdb)
            conn.commit()
            conn.close()
        except Exception as e:
            raise Exception(u"Create database failed: %s" % e)
        return cls(path)

    def __init__(self, path):
        # check locality
        if not istools.isfile(path):
            raise Exception("Database must be local")
        self.path = os.path.abspath(path)
        if not os.path.exists(self.path):
            raise Exception("Database not exists")
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
            raise Exception("Invalid database format")
        # we make a query to be sure format is valid
        try:
            self.ask("SELECT * FROM image")
        except:
            debug(u"Invalid database format: %s" % self.version)
            raise Exception("Invalid database format")

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
