# -*- python -*-
# -*- coding: utf-8 -*-
# Started 10/05/2011 by Seblu <seblu@seblu.net>

'''
Install Systems Printer module
'''

import sys
import os
import installsystems

color = {
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
    for c in color:
        if fd.isatty():
            message = message.replace("#%s#" % c, color[c])
        else:
            message = message.replace("#%s#" % c, "")
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
    out("#light##red#Fatal:#reset# #red#%s#reset#" % message, fd, endl)
    if sys.exc_info()[0] is not None and installsystems.debug:
        raise
    if quit:
        os._exit(21)

def error(message, quit=True, fd=sys.stderr, endl=os.linesep):
    out("#light##red#Error:#reset# #red#%s#reset#" % message, fd, endl)
    if sys.exc_info()[0] is not None and installsystems.debug:
        raise
    if quit:
        exit(42)

def warn(message, fd=sys.stderr, endl=os.linesep):
    out("#light##yellow#Warning:#reset# #yellow#%s#reset#" % message, fd, endl)

def info(message, fd=sys.stderr, endl=os.linesep):
    if not installsystems.quiet:
        out("#light#Info%s:#reset# %s" % message, fd, endl)

def debug(message, fd=sys.stderr, endl=os.linesep):
    if installsystems.debug:
        out("#light##black#%s#reset#" % message, fd, endl)

def arrowlevel(inc=None, level=None):
    global _arrow_level
    old_level = _arrow_level
    if level is not None:
        _arrow_level = max(1, min(4, level))
    if inc is not None:
        _arrow_level = max(1, min(4, _arrow_level + inc))
    return old_level

def arrow(message, inclevel=None, level=None, fd=sys.stdout, endl=os.linesep):
    if installsystems.quiet:
        return
    # define new level
    old_level = arrowlevel(inc=inclevel, level=level)
    if _arrow_level == 1:
        out("#light##red#=>#reset# %s" % message)
    elif _arrow_level == 2:
        out(" #light##yellow#=>#reset# %s" % message)
    elif _arrow_level == 3:
        out("  #light##blue#=>#reset# %s" % message)
    elif _arrow_level == 4:
        out("   #light##green#=>#reset# %s" % message)
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
        message = "#u##l##w#Are you sure?#R# (%s) " % ans
    return ask(message, fd, endl) == ans
