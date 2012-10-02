#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

from distutils.core import setup
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
    packages = ['safe_geonode',],
    package_data = {'safe_geonode': ['safe_geonode/templates/*', 'safe_geonode/locale']},
    scripts = [],
    classifiers = [
   ],
)
