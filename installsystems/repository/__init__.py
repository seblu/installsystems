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
InstallSystems repository package
'''

__all__ = [
    "is_name",
    "check_name",
    "split_path",
    "split_list",
    "diff",
]

from installsystems.exception import ISError
from installsystems.printer import arrow, out
from re import match, split

def is_name(name):
    '''Check if name is a valid repository name'''
    return match("^[-_\w]+$", name) is not None

def check_name(name):
    '''
    Raise exception is repository name is invalid
    '''
    if not is_name(name):
        raise ISError(u"Invalid repository name %s" % name)
    return name

def split_path(path):
    '''
    Split an image path (repo/image:version)
    in a tuple (repo, image, version)
    '''
    x = match(u"^(?:([^/:]+)/)?([^/:]+)?(?::v?([^/:]+)?)?$", path)
    if x is None:
        raise ISError(u"invalid image path: %s" % path)
    return x.group(1, 2, 3)

def split_list(repolist, filter=None):
    '''
    Return a list of repository from a comma/spaces separated names of repo
    '''
    if filter is None:
        filter = is_name
    return [r for r in  split("[ ,\n\t\v]+", repolist) if filter(r)]

@staticmethod
def diff(repo1, repo2):
    '''
    Compute a diff between two repositories
    '''
    arrow(u"Diff between repositories #y#%s#R# and #g#%s#R#" % (repo1.config.name,
                                                                repo2.config.name))
    # Get info from databases
    i_dict1 = dict((b[0], b[1:]) for b in repo1.db.ask(
        "SELECT md5, name, version FROM image").fetchall())
    i_set1 = set(i_dict1.keys())
    i_dict2 = dict((b[0], b[1:]) for b in repo2.db.ask(
        "SELECT md5, name, version FROM image").fetchall())
    i_set2 = set(i_dict2.keys())
    p_dict1 = dict((b[0], b[1:]) for b in  repo1.db.ask(
        "SELECT md5, name FROM payload").fetchall())
    p_set1 = set(p_dict1.keys())
    p_dict2 = dict((b[0], b[1:]) for b in repo2.db.ask(
        "SELECT md5, name FROM payload").fetchall())
    p_set2 = set(p_dict2.keys())
    # computing diff
    i_only1 = i_set1 - i_set2
    i_only2 = i_set2 - i_set1
    p_only1 = p_set1 - p_set2
    p_only2 = p_set2 - p_set1
    # printing functions
    pimg = lambda r,c,m,d,: out("#%s#Image only in repository %s: %s v%s (%s)#R#" %
                                (c, r.config.name, d[m][0], d[m][1], m))
    ppay = lambda r,c,m,d,: out("#%s#Payload only in repository %s: %s (%s)#R#" %
                                (c, r.config.name, d[m][0], m))
    # printing image diff
    for md5 in i_only1: pimg(repo1, "y", md5, i_dict1)
    for md5 in p_only1: ppay(repo1, "y", md5, p_dict1)
    for md5 in i_only2: pimg(repo2, "g", md5, i_dict2)
    for md5 in p_only2: ppay(repo2, "g", md5, p_dict2)
