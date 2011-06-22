# -*- python -*-
# -*- coding: utf-8 -*-
# Started 12/05/2011 by Seblu <seblu@seblu.net>

description = """[image]
name =
version =
description =
author =
"""

parser = """# -*- python -*-
# -*- coding: utf-8 -*-

parser.add_argument("-n", "--hostname", dest="hostname", type=str, required=True)
parser.add_argument("target", type=str,
  help="target installation directory")

# vim:set ts=2 sw=2 noet:
"""

setup = """# -*- python -*-
# -*- coding: utf-8 -*-

print "hostname: %s" % args.hostname

image.payload["rootfs"].extract(args.target)

# vim:set ts=2 sw=2 noet:
"""

createdb = """
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
