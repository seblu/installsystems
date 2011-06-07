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

image.extractdata("rootfs", args.target)

# vim:set ts=2 sw=2 noet:
"""
