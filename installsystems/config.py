# -*- python -*-
# -*- coding: utf-8 -*-
# Started 30/05/2011 by Seblu <seblu@seblu.net>

'''
InstallSystems Configuration files class
'''

import os
import sys
from argparse import Namespace
from ConfigParser import RawConfigParser
from installsystems.printer import *
from installsystems.repository import RepositoryConfig


class ConfigFile(object):
    '''
    Configuration File base class
    '''

    def __init__(self, filename):
        '''
        filename can be full path to config file or a name in config directory
        '''
        #try to get filename in default config dir
        if os.path.isfile(filename):
            self.path = os.path.abspath(filename)
        else:
            self.path = self._config_path(filename)
        self.reload()

    def reload():
        '''
        Reload configuration from file
        '''
        raise NotImplementedError

    def _config_path(self, name):
        '''
        Return path of the best config file
        '''
        for cf in [ os.path.join(os.path.expanduser("~/.config/installsystems/%s.conf" % name)),
                    "/etc/installsystems/%s.conf" % name ]:
            if (os.path.isfile(cf) and os.access(cf, os.R_OK)):
                return cf
        return None


class MainConfigFile(ConfigFile):
    '''
    Program configuration file
    '''

    valid_options = {
        "verbosity": [0,1,2],
        "no_cache": bool,
        "no_color": bool,
        "timeout": int,
        "cache": str,
        "repo_search": str,
        "repo_filter": str,
        "repo_config": str,
        "repo_timeout": int,
        "nice": int,
        "ionice_class": ["none", "rt", "be", "idle"],
        "ionice_level": int
        }
    def __init__(self, filename, prefix=os.path.basename(sys.argv[0])):
        self.prefix = prefix
        ConfigFile.__init__(self, filename)

    def reload(self):
        '''
        Load/Reload config file
        '''
        self._config = {}
        # loading default options
        self._config["cache"] = self.cache
        # loading config file if exists
        if self.path is None:
            debug("No main config file to load")
            return
        debug("Loading main config file: %s" % self.path)
        try:
            cp = RawConfigParser()
            cp.read(self.path)
            # main configuration
            if cp.has_section(self.prefix):
                self._config.update(cp.items(self.prefix))
        except Exception as e:
            raise Exception("Unable load main config file %s: %s" % (self.path, e))

    def parse(self, namespace=None):
        '''
        Parse current loaded option within a namespace
        '''
        if namespace is None:
            namespace = Namespace()
        for option, value in self._config.items():
            # check option is valid
            if option not in self.valid_options.keys():
                warn("Invalid option %s in %s, skipped" % (option, self.path))
                continue
            # we expect a string like
            if not isinstance(option, basestring):
                raise TypeError("Invalid config parser option %s type" % option)
            # smartly cast option's value
            if self.valid_options[option] is bool:
                value = value.strip().lower() not in ("false", "no", "0", "")
            # in case of valid option is a list, we take the type of the first
            # argument of the list to convert value into it
            # as a consequence, all element of a list must be of the same type!
            # empty list are forbidden !
            elif isinstance(self.valid_options[option], list):
                ctype = type(self.valid_options[option][0])
                try:
                    value = ctype(value)
                except ValueError:
                    warn("Invalid option %s type (must be %s), skipped" %
                         (option, ctype))
                    continue
                if value not in self.valid_options[option]:
                    warn("Invalid value %s in option %s (must be in %s), skipped" %
                         (value, option, self.valid_options[option]))
                    continue
            else:
                try:
                    value = self.valid_options[option](value)
                except ValueError:
                    warn("Invalid option %s type (must be %s), skipped" %
                         (option, self.valid_options[option]))
                    continue
            setattr(namespace, option, value)
        return namespace

    def _cache_paths(self):
        '''
        List all candidates to cache directories. Alive or not
        '''
        dirs = [os.path.expanduser("~/.cache"), "/var/tmp", "/tmp"]
        # we have an additional directry if we are root
        if os.getuid() == 0:
            dirs.insert(0, "/var/cache")
        return map(lambda x: os.path.join(x, self.prefix), dirs)

    def _cache_path(self):
        '''
        Return path of the best cache directory
        '''
        # find a good directory
        for di in self._cache_paths():
            if (os.path.exists(di)
                and os.path.isdir(di)
                and os.access(di, os.R_OK|os.W_OK|os.X_OK)):
                return di
        return None

    @property
    def cache(self):
        '''
        Find a cache directory
        '''
        if "cache" in self._config:
            return self._config["cache"]
        if self._cache_path() is None:
            for di in self._cache_paths():
                try:
                    os.mkdir(di)
                    break
                except Exception as e:
                    debug("Unable to create %s: %s" % (di, e))
        return self._cache_path()


class RepoConfigFile(ConfigFile):
    '''
    Repository Configuration class
    '''

    def reload(self):
        '''
        Load/Reload config file
        '''
        # seting default config
        self._config = {}
        self._repos = []
        # if no file nothing to load
        if self.path is None:
            return
        # loading config file if exists
        debug("Loading repository config file: %s" % self.path)
        try:
            cp = RawConfigParser()
            cp.read(self.path)
            # each section is a repository
            for rep in cp.sections():
                # check if its a repo section
                if "path" not in cp.options(rep):
                    continue
                # get all options in repo
                self._repos.append(RepositoryConfig(rep, **dict(cp.items(rep))))
        except Exception as e:
            raise Exception("Unable to load repository file %s: %s" % (self.path, e))

    @property
    def repos(self):
        '''
        Get a list of repository available
        '''
        # deep copy
        return list(self._repos)
