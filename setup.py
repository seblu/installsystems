# -*- python -*-
# -*- coding: utf-8 -*-
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
    license='GPL2',
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
