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

# vim:set ts=2 sw=2 noet:
"""

setup = """# -*- python -*-
# -*- coding: utf-8 -*-

print "hostname: %s" % args.hostname

# vim:set ts=2 sw=2 noet:
"""
