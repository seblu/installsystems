# -*- python -*-
# -*- coding: utf-8 -*-

# Installsystems - Python installation framework
# Copyright © 2011-2012 Smartjog S.A
# Copyright © 2011-2012 Sébastien Luttringer
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

'''
InstallSystems Exceptions
'''

import traceback
import sys

class ISException(Exception):
    '''
    Base exception class
    '''

    def __init__(self, message=u"", exception=None):
        self.message = unicode(message)
        self.exception = None if exception is None else sys.exc_info()

    def __str__(self):
        '''
        Return a description of exception
        '''
        if self.exception is not None:
            return u"%s: %s" % (self.message, self.exception[1])
        else:
            return self.message

    def print_sub_tb(self, fd=sys.stderr):
        '''
        Print stored exception traceback and exception message
        '''
        # no exception, do nothing
        if self.exception is None:
            return
        # print traceback and exception separatly to avoid recursive print of
        # "Traceback (most recent call last)" from traceback.print_exception
        traceback.print_tb(self.exception[2], file=fd)
        fd.write("".join(traceback.format_exception_only(self.exception[0], self.exception[1])))
        # recursively call traceback print on ISException error
        if isinstance(self.exception[1], ISException):
            self.exception[1].print_sub_tb()

    def print_tb(self, fd=sys.stderr):
        '''
        Print traceback from embeded exception or current one
        '''
        from installsystems.printer import out
        # coloring
        out("#l##B#", fd=fd, endl="")
        traceback.print_exc(file=fd)
        self.print_sub_tb(fd)
        # reset color
        out("#R#", fd=fd, endl="")


class ISError(ISException):
    '''
    Installsystems error; this exception will stop execution
    '''


class ISWarning(ISException):
    '''
    Installsystems warning; this exception do not stop execution
    '''


class InvalidSourceImage(ISError):
    '''
    Invalid source image errors
    '''

    def __init(self, message=u"", exception=None):
        ISException(self, u"Invalid source image: " + message, exception)
