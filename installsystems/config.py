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
InstallSystems configuration files module
'''

from argparse import Namespace
from configobj import ConfigObj, flatten_errors
from installsystems.exception import ISWarning, ISError
from installsystems.printer import warn, debug
from installsystems.repository.config import RepositoryConfig
from os import access, mkdir, getuid, R_OK, W_OK, X_OK
from os.path import join, expanduser, isfile, basename, abspath, exists, isdir
from sys import argv
from validate import Validator

class ConfigFile(object):
    '''
    Configuration File base class
    '''

    def __init__(self, filename):
        '''
        Filename can be full path to config file or a name in config directory
        '''
        # try to get filename in default config dir
        if isfile(filename):
            self.path = abspath(filename)
        else:
            self.path = self._config_path(filename)
        # loading config file if exists
        if self.path is None:
            raise ISWarning("No config file to load")
        self.config = ConfigObj(self.path, configspec=self.configspec,
                                encoding="utf8", file_error=True)
        self.validate()

    def validate(self):
        '''
        Validate the configuration file according to the configuration specification
        If some values doesn't respect specification, she's ignored and a warning is issued.
        '''
        res = self.config.validate(Validator(), preserve_errors=True)
        # If everything is fine, the validation return True
        # Else, it returns a list of (section, optname, error)
        if res is not True:
            for section, optname, error in flatten_errors(self.config, res):
                # If error is False, this mean no value as been supplied,
                # so we use the default value
                # Else, the check has failed
                if error:
                    warn("%s: %s Skipped" % (optname, error))
                    # remove wrong value to avoid merging it with argparse value
                    del self.config[section[0]][optname]

    @staticmethod
    def _config_path(name):
        '''
        Return path of the best config file
        '''
        for cfp in [join(expanduser(u"~/.config/installsystems/%s.conf" %name)),
         u"/etc/installsystems/%s.conf" % name ]:
            if (isfile(cfp) and access(cfp, R_OK)):
                return cfp
        return None

    @property
    def configspec(self):
        '''Return configobj spec'''
        raise NotImplementedError()


class MainConfigFile(ConfigFile):
    '''
    Program configuration class
    '''

    def __init__(self, filename, prefix=basename(argv[0])):
        self.prefix = prefix
        try:
            super(MainConfigFile, self).__init__(filename)
            debug(u"Loading main config file: %s" % self.path)
        except ISWarning:
            debug("No main config file to load")
        except Exception as exc:
            raise ISError(u"Unable load main config file %s" % self.path, exc)

    def _cache_paths(self):
        '''
        List all candidates to cache directories. Alive or not
        '''
        dirs = [expanduser("~/.cache"), "/var/tmp", "/tmp"]
        # we have an additional directory if we are root
        if getuid() == 0:
            dirs.insert(0, "/var/cache")
        return [ join(x, self.prefix) for x in dirs ]

    def _cache_path(self):
        '''
        Return path of the best cache directory
        '''
        # find a good directory
        for directory in self._cache_paths():
            if (exists(directory)
                and isdir(directory)
                and access(directory, R_OK|W_OK|X_OK)):
                return directory
        return None

    @property
    def cache(self):
        '''
        Find a cache directory
        '''
        if self._cache_path() is None:
            for directory in self._cache_paths():
                try:
                    mkdir(directory)
                    break
                except Exception as exc:
                    debug(u"Unable to create %s: %s" % (directory, exc))
        return self._cache_path()

    def parse(self, namespace=None):
        '''
        Parse current loaded option within a namespace
        '''
        if namespace is None:
            namespace = Namespace()
        if self.path:
            for option, value in self.config[self.prefix].items():
                setattr(namespace, option, value)
        return namespace

    @property
    def configspec(self):
        '''Return configobj spec'''
        return (MAIN_CONFIG_SPEC % self.cache).splitlines()


class RepoConfigFile(ConfigFile):
    '''
    Repository Configuration class
    '''

    def __init__(self, filename):
        # seting default config
        self._config = {}
        self._repos = []

        try:
            super(RepoConfigFile, self).__init__(filename)
            debug(u"Loading repository config file: %s" % self.path)
            self._parse()
        except ISWarning:
            debug("No repository config file to load")

    def _parse(self):
        '''
        Parse repositories from config
        '''
        try:
            # each section is a repository
            for rep in self.config.sections:
                # check if its a repo section
                if "path" not in self.config[rep]:
                    continue
                # get all options in repo
                self._repos.append(
                    RepositoryConfig(rep, **dict(self.config[rep].items()))
                )
        except Exception as exc:
            raise ISError(u"Unable to load repository file %s" % self.path, exc)

    @property
    def repos(self):
        '''
        Get a list of repository available
        '''
        # deep copy
        return list(self._repos)

    @property
    def configspec(self):
        '''Return configobj spec'''
        return REPO_CONFIG_SPEC.splitlines()


# This must not be an unicode string, because configobj don't decode configspec
# with the provided encoding
MAIN_CONFIG_SPEC = '''\
[installsystems]
verbosity = integer(0, 2)
repo_config = string
repo_search = string
repo_filter = string
repo_timeout = integer
cache = string(default=%s)
timeout = integer
no_cache = boolean
no_check = boolean
no-sync = boolean
no_color = boolean
nice = integer
ionice_class = option("none", "rt", "be", "idle")
ionice_level = integer
'''

# This must not be an unicode string, because configobj don't decode configspec
# with the provided encoding
REPO_CONFIG_SPEC = '''\
[__many__]
    path = string
    fmod = string
    dmod = string
    uid = string
    gid = string
    offline = boolean
    lastpath = string
    dbpath = string
'''
