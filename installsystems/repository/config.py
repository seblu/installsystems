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
Repository configuration module
'''

from grp import getgrnam
from installsystems.printer import warn, debug
from installsystems.repository.repository import Repository
from installsystems.tools import isfile, chrights, mkdir, compare_versions
from os  import getuid, getgid, umask, linesep
from os.path import join, abspath
from pwd import getpwnam

class RepositoryConfig(object):
    '''
    Repository configuration container
    '''

    def __init__(self, name, **kwargs):
        # set default value for arguments
        self._valid_param = ("name", "path", "dbpath", "lastpath",
                             "uid", "gid", "fmod", "dmod", "offline")
        self.name = Repository.check_name(name)
        self.path = ""
        self._offline = False
        self._dbpath = None
        self.dbname = "db"
        self._lastpath = None
        self.lastname = "last"
        self._uid = getuid()
        self._gid = getgid()
        oldmask = umask(0)
        umask(oldmask)
        self._fmod =  0666 & ~oldmask
        self._dmod =  0777 & ~oldmask
        self.update(**kwargs)

    def __str__(self):
        l = []
        for k, v in self.items():
            l.append(u"%s: %s" % (k, v))
        return linesep.join(l)

    def __eq__(self, other):
        return vars(self) == vars(other)

    def __ne__(self, other):
        return not (self == other)

    def __contains__(self, key):
        return key in self.__dict__

    def __getitem__(self, key):
        if key not in self._valid_param:
            raise IndexError(key)
        return getattr(self, key)

    def __iter__(self):
        for p in self._valid_param:
            yield p

    def items(self):
        for p in self:
            yield p, self[p]

    @property
    def lastpath(self):
        '''
        Return the last file complete path
        '''
        if self._lastpath is None:
            return join(self.path, self.lastname)
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
            return join(self.path, self.dbname)
        return self._dbpath

    @dbpath.setter
    def dbpath(self, value):
        '''
        Set db path
        '''
        # dbpath must be local, sqlite3 requirement
        if not isfile(value):
            raise ValueError("Database path must be local")
        self._dbpath = abspath(value)

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
            self._uid = getpwnam(value).pw_uid
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
            self._gid = getgrnam(value).gr_gid
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
                    warn(u"Unable to set config parameter %s in repository %s: %s" %
                         (k, self.name, e))
            else:
                debug(u"No such repository parameter: %s" % k)
