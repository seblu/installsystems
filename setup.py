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

from setuptools import setup
import os
import sys
import installsystems

# Retrieval of version

ldesc = open(os.path.join(os.path.dirname(__file__), 'README')).read()

setup(
    name=installsystems.canonical_name,
    version=installsystems.version,
    description='InstallSystems',
    long_description=ldesc,
    author='Sébastien Luttringer',
    author_email='sebastien.luttringer@smartjog.com',
    license='LGPL3',
    packages=[ 'installsystems' ],
    scripts=[ 'bin/is' ],
    data_files=(
        ('/etc/installsystems/', ('samples/repository.conf',
                                  'samples/installsystems.conf')),
        ('/etc/bash_completion.d/', ('completion/bash/is',)),
        ),
    classifiers=[
        'Operating System :: Unix',
        'Programming Language :: Python',
        ],
    )
