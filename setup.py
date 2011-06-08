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
    author='Sebastien Luttringer',
    author_email='sebastien.luttringer@smartjog.com',
    license='GPL2', 
    packages=[ 'installsystems'],
    scripts=['bin/isrepo', 'bin/isinstall', 'bin/isimage'],
    classifiers=[
        'Operating System :: Unix',
        'Programming Language :: Python',
        ],
    )
