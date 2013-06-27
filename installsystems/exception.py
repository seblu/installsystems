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
InstallSystems Exceptions
'''

from traceback import print_tb, print_exc, format_exception_only
from sys import exc_info, stderr

class ISException(Exception):
    '''
    Base exception class
    '''

    def __init__(self, message=u"", exception=None):
        Exception.__init__(self)
        self.message = unicode(message)
        self.exception = None if exception is None else exc_info()

    def __str__(self):
        '''
        Return a description of exception
        '''
        if self.exception is not None:
            return u"%s: %s" % (self.message, self.exception[1])
        else:
            return self.message

    def print_sub_tb(self, fd=stderr):
        '''
        Print stored exception traceback and exception message
        '''
        # no exception, do nothing
        if self.exception is None:
            return
        # print traceback and exception separatly to avoid recursive print of
        # "Traceback (most recent call last)" from traceback.print_exception
        print_tb(self.exception[2], file=fd)
        fd.write("".join(format_exception_only(self.exception[0],
                                               self.exception[1])))
        # recursively call traceback print on ISException error
        if isinstance(self.exception[1], ISException):
            self.exception[1].print_sub_tb()

    def print_tb(self, fd=stderr):
        '''
        Print traceback from embeded exception or current one
        '''
        from installsystems.printer import out
        # coloring
        out("#l##B#", fd=fd, endl="")
        print_exc(file=fd)
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

    def __init__(self, message=u"", exception=None):
        ISError.__init__(self, u"Invalid source image: " + message, exception)
