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

import locale
import sys
import os
import re
import installsystems

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
_arrow_level = 1

def out(message="", fd=sys.stdout, endl=os.linesep, flush=True):
    '''
    Print message colorised in fd ended by endl
    '''
    # color subsitution
    color_pattern = "#(%s)#" % "|".join(COLOR)
    if not fd.isatty() or NOCOLOR:
        f = lambda obj: ""
    else:
        f = lambda obj: COLOR[obj.group(1)]
    message = re.sub(color_pattern, f, message)
    # convert unicode into str before write
    # this can cause issue on python 2.6
    if type(message) == unicode:
        message = message.encode(locale.getpreferredencoding(), "replace")
    # printing
    fd.write("%s%s" % (message, endl))
    if flush:
        fd.flush()

def err(message, fd=sys.stderr, endl=os.linesep):
    '''
    Print a message on stderr
    '''
    out(message, fd, endl)

def fatal(message, quit=True, fd=sys.stderr, endl=os.linesep):
    out(u"#light##red#Fatal:#reset# #red#%s#reset#" % message, fd, endl)
    if sys.exc_info()[0] is not None and installsystems.verbosity > 1:
        raise
    if quit:
        os._exit(21)

def error(message, quit=True, fd=sys.stderr, endl=os.linesep):
    out(u"#light##red#Error:#reset# #red#%s#reset#" % message, fd, endl)
    if sys.exc_info()[0] is not None and installsystems.verbosity > 1:
        raise
    if quit:
        exit(42)

def warn(message, fd=sys.stderr, endl=os.linesep):
    out(u"#light##yellow#Warning:#reset# #yellow#%s#reset#" % message, fd, endl)

def info(message, fd=sys.stderr, endl=os.linesep):
    if installsystems.verbosity > 0:
        out(u"#light#Info:#reset# %s" % message, fd, endl)

def debug(message, fd=sys.stderr, endl=os.linesep):
    if installsystems.verbosity > 1:
        out(u"#light##black#%s#reset#" % message, fd, endl)

def arrowlevel(inc=None, level=None):
    global _arrow_level
    old_level = _arrow_level
    if level is not None:
        _arrow_level = max(1, min(4, level))
    if inc is not None:
        _arrow_level = max(1, min(4, _arrow_level + inc))
    return old_level

def arrow(message, inclevel=None, level=None, fd=sys.stdout, endl=os.linesep):
    if installsystems.verbosity == 0:
        return
    # define new level
    old_level = arrowlevel(inc=inclevel, level=level)
    if _arrow_level == 1:
        out(u"#light##red#=>#reset# %s" % message, fd=fd, endl=endl)
    elif _arrow_level == 2:
        out(u" #light##yellow#=>#reset# %s" % message, fd=fd, endl=endl)
    elif _arrow_level == 3:
        out(u"  #light##blue#=>#reset# %s" % message, fd=fd, endl=endl)
    elif _arrow_level == 4:
        out(u"   #light##green#=>#reset# %s" % message, fd=fd, endl=endl)
    # restore old on one shot level
    arrowlevel(level = old_level)

def ask(message, fd=sys.stdout, endl=""):
    '''
    Ask a question on stdin
    '''
    out(message, fd=fd, endl=endl, flush=True)
    return raw_input()

def confirm(message=None, ans=None, fd=sys.stdout, endl=""):
    '''
    Ask a question on stdin
    '''
    if ans is None:
        ans = "yes"
    if message is None:
        message = u"#u##l##w#Are you sure?#R# (%s) " % ans
    return ask(message, fd, endl) == ans
