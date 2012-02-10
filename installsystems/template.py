# -*- python -*-
# -*- coding: utf-8 -*-
# Started 12/05/2011 by Seblu <seblu@seblu.net>

description = u"""[image]
name = %(name)s
version = %(version)s
description = %(description)s
author = %(author)s
is_min_version = %(is_min_version)s
"""

changelog = u"""[1]
- Initial version
"""

build = u"""# -*- python -*-
# -*- coding: utf-8 -*-

# global rebuild object allow you to force rebuild of payloads
# to force rebuild of payload nammed rootfs add it to the rebuild list
# rebuild list is empty by default
#rebuild += ["rootfs"]

# vim:set ts=2 sw=2 noet:
"""


parser = """# -*- python -*-
# -*- coding: utf-8 -*-

# global image object is a reference to current image
# global parser object is your installsystems subparser (argparse)

import os
import argparse
from installsystems.printer import arrow

class TargetAction(argparse.Action):
  def __call__(self, parser, namespace, values, option_string=None):
    if not os.path.isdir(values):
      raise Exception("Invalid target directory %s" % values)
    namespace.target = values

parser.add_argument("-n", "--hostname", dest="hostname", type=str, required=True)
parser.add_argument("target", type=str, action=TargetAction,
  help="target installation directory")

# vim:set ts=2 sw=2 noet:
"""

setup = u"""# -*- python -*-
# -*- coding: utf-8 -*-

# global image object is a reference to current image
# namespace object is the persistant, it can be used to store data accross scripts

from installsystems.printer import arrow

arrow("hostname: %s" % namespace.hostname)

# uncomment to extract payload named root in namespace.target directory
#image.payload["rootfs"].extract(namespace.target)

# vim:set ts=2 sw=2 noet:
"""

createdb = u"""
CREATE TABLE image (md5 TEXT NOT NULL PRIMARY KEY,
                    name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    date INTEGER NOT NULL,
                    author TEXT,
                    description TEXT,
                    size INTEGER NOT NULL,
                    UNIQUE(name, version));

CREATE TABLE payload (md5 TEXT NOT NULL,
                     image_md5 TEXT NOT NULL REFERENCES image(md5),
                     name TEXT NOT NULL,
                     isdir INTEGER NOT NULL,
                     size INTEGER NOT NULL,
                     PRIMARY KEY(md5, image_md5));
"""
