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
Install Systems Printer module
'''

from installsystems.exception import ISException

from locale import getpreferredencoding
from os import linesep, _exit
from re import sub
from sys import stdout, stderr, exc_info
from traceback import print_exc
from warnings import filterwarnings

VERBOSITY = 1 # 0: quiet, 1: normal, 2: debug
NOCOLOR = False

COLOR = {
    # regular
    "black": "\033[30m",
    "B": "\033[30m",
    "red": "\033[31m",
    "r": "\033[31m",
    "green": "\033[32m",
    "g": "\033[32m",
    "yellow": "\033[33m",
    "y": "\033[33m",
    "blue": "\033[34m",
    "b": "\033[34m",
    "purple": "\033[35m",
    "p": "\033[35m",
    "cyan": "\033[36m",
    "c": "\033[36m",
    "white": "\033[37m",
    "w": "\033[37m",
    # others
    "under": "\033[4m",
    "u": "\033[4m",
    "light": "\033[1m",
    "l": "\033[1m",
    "reset": "\033[m",
    "R": "\033[m",
    }

# arrow_level is between 1 and 3
# is the level of indentation of arrow
_ARROW_LEVEL = 1

def out(message="", fd=stdout, endl=linesep, flush=True):
    '''
    Print message colorised in fd ended by endl
    '''
    if message is None:
        return
    # color subsitution
    color_pattern = "#(%s)#" % "|".join(COLOR)
    if not fd.isatty() or NOCOLOR:
        f = lambda obj: ""
    else:
        f = lambda obj: COLOR[obj.group(1)]
    message = sub(color_pattern, f, message)
    # convert unicode into str before write
    # this can cause issue on python 2.6
    if type(message) == unicode:
        message = message.encode(getpreferredencoding(), "replace")
    # printing
    fd.write("%s%s" % (message, endl))
    if flush:
        fd.flush()

def err(message, fd=stderr, endl=linesep):
    '''
    Print a message on stderr
    '''
    out(message, fd, endl)

def fatal(message, quit=True, fd=stderr, endl=linesep):
    out(u"#light##red#Fatal:#reset# #red#%s#reset#" % message, fd, endl)
    if exc_info()[0] is not None and VERBOSITY > 1:
        raise
    if quit:
        _exit(21)

def error(message=None, exception=None, quit=True, fd=stderr, endl=linesep):
    # create error message
    pmesg = u""
    if message is not None:
        pmesg += unicode(message)
    if exception is not None:
        if pmesg == "":
            pmesg += unicode(exception)
        else:
            pmesg += u": %s" % unicode(exception)
    # print error message
    if pmesg != "":
        out(u"#light##red#Error:#reset# #red#%s#reset#" % pmesg, fd, endl)
    # print traceback in debug mode
    if VERBOSITY > 1 and isinstance(exception, ISException):
        exception.print_tb(fd)
    elif VERBOSITY > 1:
        out("#l##B#", fd=fd, endl="")
        print_exc(file=fd)
        out("#R#", fd=fd, endl="")
    if quit:
        exit(42)

def warn(message, fd=stderr, endl=linesep):
    out(u"#light##yellow#Warning:#reset# #yellow#%s#reset#" % message, fd, endl)

def info(message, fd=stderr, endl=linesep):
    if VERBOSITY > 0:
        out(u"#light#Info:#reset# %s" % message, fd, endl)

def debug(message, fd=stderr, endl=linesep):
    '''
    Print debug information
    '''
    if VERBOSITY > 1:
        out(u"#light##black#%s#reset#" % message, fd, endl)

def arrowlevel(inc=None, level=None):
    '''
    Modify the current arrow level
    '''
    global _ARROW_LEVEL
    old_level = _ARROW_LEVEL
    if level is not None:
        _ARROW_LEVEL = max(1, min(4, level))
    if inc is not None:
        _ARROW_LEVEL = max(1, min(4, _ARROW_LEVEL + inc))
    return old_level

def arrow(message, inclevel=None, level=None, fd=stdout, endl=linesep):
    '''
    Print a message prefixed by an arrow
    Arrows have indentation levels
    '''
    if VERBOSITY == 0:
        return
    # define new level
    old_level = arrowlevel(inc=inclevel, level=level)
    if _ARROW_LEVEL == 1:
        out(u"#light##red#=>#reset# %s" % message, fd=fd, endl=endl)
    elif _ARROW_LEVEL == 2:
        out(u" #light##yellow#=>#reset# %s" % message, fd=fd, endl=endl)
    elif _ARROW_LEVEL == 3:
        out(u"  #light##blue#=>#reset# %s" % message, fd=fd, endl=endl)
    elif _ARROW_LEVEL == 4:
        out(u"   #light##green#=>#reset# %s" % message, fd=fd, endl=endl)
    # restore old on one shot level
    arrowlevel(level = old_level)

def ask(message, fd=stdout, endl=""):
    '''
    Ask a question on stdin
    '''
    out(message, fd=fd, endl=endl, flush=True)
    return raw_input()

def confirm(message=None, ans=None, fd=stdout, endl=""):
    '''
    Ask a question on stdin
    '''
    if ans is None:
        ans = "yes"
    if message is None:
        message = u"#u##l##w#Are you sure?#R# (%s) " % ans
    return ask(message, fd, endl) == ans

def setmode(verbosity=None, nocolor=None):
    '''
    Set printer mode
    This is done to allow write access to global variables
    '''
    global VERBOSITY, NOCOLOR
    if verbosity is not None:
        # no warning if we are not in debug mode
        if verbosity < 2:
            filterwarnings("ignore")
        VERBOSITY = verbosity
    if nocolor is not None:
        NOCOLOR = nocolor
