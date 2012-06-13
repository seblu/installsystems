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

import StringIO
import sys
import traceback
import installsystems

class ISException(Exception):
    '''
    Base exception class
    '''
    def __init__(self, message="", exception=None):
        self.message = unicode(message)
        self.exception = exception
        if exception:
            self.exc_info = sys.exc_info()

    def __str__(self):
        if self.exception:
            return u"%s: %s" % (self.message, self.exception)
        else:
            return self.message

    def print_tb(self, fd=sys.stderr):
        '''
        Print traceback from embeded exception or current one
        '''
        from installsystems.printer import out
        # coloring
        out("#l##B#", fd=fd, endl="")
        # print original exception traceback
        if self.exception is not None:
            traceback.print_exception(self.exc_info[0], self.exc_info[1],
                                      self.exc_info[2], file=fd)
        # print current exception traceback
        else:
            exc_info = sys.exc_info()
            traceback.print_exception(exc_info[0], exc_info[1], exc_info[2],
                                      file=fd)
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

