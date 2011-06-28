#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Started 30/05/2011 by Seblu <seblu@seblu.net>

'''
InstallSystems Configuration files class
'''

import os
from ConfigParser import RawConfigParser
from installsystems.printer import *
from installsystems.repository import RepositoryConfig


class ConfigFile(object):
    '''
    Configuration File base class
    '''

    def __init__(self, filename):
        '''
        filename can be name in config path
        '''
        #try to get filename in  default config dir
        if "/" not in filename:
            path = self._config_path(filename)
            if path is not None:
                self.path = path
        elif os.path.exists(filename):
            self.path = filename
        else:
            self.path = None
            debug("No config file found: %s" % filename)
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
            if (os.path.exists(cf) and os.path.isfile(cf) and os.access(cf, os.R_OK)):
                return cf
        return None

    def _cache_paths(self, name):
        '''
        List all candidates to cache directories. Alive or not
        '''
        dirs = [] # ["/var/tmp", "/tmp"]
        # we have a different behaviour if we are root
        dirs.insert(0, "/var/cache" if os.getuid() == 0 else os.path.expanduser("~/.cache"))
        return map(lambda x: os.path.join(x, name), dirs)

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


class MainConfigFile(ConfigFile):
    '''
    Program configuration file
    '''

    def reload(self):
        '''
        Load/Reload config file
        '''
        self._config = {}
        # loading config file if exists
        if self.path is None:
            return
        debug("Loading config file: %s" % self.path)
        try:
            cp = RawConfigParser()
            cp.read(self.path)
            # main configuration
            name = os.path.splitext(os.path.basename(self.path))[0]
            if cp.has_section(name):
                self._config = dict(cp.items(name))
        except Exception as e:
            raise Exception("Unable load file %s: %s" % (self.path, e))

    def merge(self, namespace):
        '''
        Merge current loaded option with a namespace from argparse
        '''
        for option, value in self._config.items():
            if not hasattr(namespace, option):
                setattr(namespace, option, value)
            elif getattr(namespace, option) == None:
                setattr(namespace, option, value)

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
        # loading config file if exists
        if self.path is not None:
            debug("Loading config file: %s" % self.path)
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
                raise Exception("Unable load file %s: %s" % (self.path, e))
        else:
            debug("No config file found")

    @property
    def repos(self):
        '''
        Get a list of repository available
        '''
        # deep copy
        return list(self._repos)
