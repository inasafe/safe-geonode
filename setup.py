#!/usr/bin/env python
# -*- coding: utf-8 -*-
from distutils.core import setup
from distutils.command.install import INSTALL_SCHEMES
import os
import sys

def fullsplit(path, result=None):
    """
    Split a pathname into components (the opposite of os.path.join) in a
    platform-neutral way.
    """
    if result is None:
        result = []
    head, tail = os.path.split(path)
    if head == '':
        return [tail] + result
    if head == path:
        return result
    return fullsplit(head, [tail] + result)

# Tell distutils not to put the data_files in platform-specific installation
# locations. See here for an explanation:
# http://groups.google.com/group/comp.lang.python/browse_thread/thread/35ec7b2fed36eaec/2105ee4d9e8042cb
for scheme in INSTALL_SCHEMES.values():
    scheme['data'] = scheme['purelib']

# Compile the list of packages available, because distutils doesn't have
# an easy way to do this.
packages, data_files = [], []
root_dir = os.path.dirname(__file__)
if root_dir != '':
    os.chdir(root_dir)
geonode_dir = 'geonode'

for dirpath, dirnames, filenames in os.walk(geonode_dir):
    # Ignore dirnames that start with '.'
    for i, dirname in enumerate(dirnames):
        if dirname.startswith('.'): del dirnames[i]
    if '__init__.py' in filenames:
        packages.append('.'.join(fullsplit(dirpath)))
    elif filenames:
        data_files.append([dirpath, [os.path.join(dirpath, f) for f in filenames]])


safe_geonode = __import__('safe_geonode')


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='safe-geonode',
    version=safe_geonode.get_version(),
    description='GeoNode SAFE plugin',
    #long_description=read('README'),
    long_description='safe-geonode',
    author='Ariel Núñez',
    author_email='ingenieroariel@gmail.com',
    url='http://github.com/safe/safe-geonode/',
    platforms=['any'],
    license='GPLv3',
    zip_safe=False,
    install_requires=[
        'python-safe>=0.5',       # pip install python-safe
        'GeoNode',                  # sudo apt-get install geonode
        'django-leaflet>=0.2.0',    # pip install django-leaflet
        'pygments',                 # pip install pygments
    ],
    packages = packages,
    data_files=data_files,
    scripts = [],
    classifiers = [
   ],
)
