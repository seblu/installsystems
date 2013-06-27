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
Image Changelog module
'''

from installsystems.exception import ISError
from installsystems.printer import out
from installsystems.tools import strvercmp
from os import linesep
from re import match

class Changelog(dict):
    '''
    Object representing a changelog in memory
    '''
    def __init__(self, data):
        self.verbatim = u""
        self.load(data)

    def load(self, data):
        '''
        Load a changelog file
        '''
        # ensure data are correct UTF-8
        if isinstance(data, str):
            try:
                data = unicode(data, "UTF-8")
            except UnicodeDecodeError:
                raise ISError("Invalid character encoding in changelog")
        version = None
        lines = data.split("\n")
        for line in lines:
            # ignore empty lines
            if len(line.strip()) == 0:
                continue
            # ignore comments
            if line.lstrip().startswith("#"):
                continue
            # try to match a new version
            m = match("\[(\d+(?:\.\d+)*)(?:([~+]).*)?\]", line.lstrip())
            if m is not None:
                version = m.group(1)
                self[version] = []
                continue
            # if line are out of a version => invalid format
            if version is None:
                raise ISError("Invalid format: Line outside version")
            # add line to version changelog
            self[version] += [line]
        # save original
        self.verbatim = data

    def show(self, version=None):
        '''
        Show changelog for a given version
        '''
        assert(isinstance(version, unicode))
        # if no version take the hightest
        if version is None:
            version = max(self, strvercmp)
        # display asked version
        if version in self:
            out(linesep.join(self[version]))

    def show_all(self):
        '''
        Show changelog for all versions
        '''
        for ver in sorted(self, strvercmp,  reverse=True):
            out(u'-- #purple#version:#reset# %s' % ver)
            out(linesep.join(self[ver]))
