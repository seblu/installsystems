# -*- python -*-
# -*- coding: utf-8 -*-
# Started 10/05/2011 by Seblu <seblu@seblu.net>

'''
Install Systems Printer module
'''

import sys
import os
import signal
import installsystems

color = {
    # regular
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "purple": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    # others
    "under": "\033[4m",
    "light": "\033[1m",
    "reset": "\033[m",
    }

def out(message="", fd=sys.stdout, endl=os.linesep, flush=True):
    '''Print message colorised in fd ended by endl'''
    # color subsitution
    for c in color:
        message = message.replace("#%s#" % c, color[c])
    # printing
    fd.write("%s%s" % (message, endl))
    if flush:
        fd.flush()

def err(message, fd=sys.stderr, endl=os.linesep):
    '''Print a message on stderr'''
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
    out("#light#Info%s:#reset# %s" % message, fd, endl)

def debug(message, fd=sys.stderr, endl=os.linesep):
    if installsystems.debug:
        out("#light##black#%s#reset#" % message, fd, endl)

def arrow(message, level, verbose, fd=sys.stdout, endl=os.linesep):
    if not verbose:
        return
    if level == 1:
        out("#light##red#=>#reset# %s" % message)
    elif level == 2:
        out(" #light##yellow#=>#reset# %s" % message)
    elif level == 3:
        out("  #light##purple#=>#reset# %s" % message)
