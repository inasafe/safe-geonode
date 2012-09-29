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
    long_description=read('README'),
    author='Ariel Núñez',
    author_email='ingenieroariel@gmail.com',
    url='http://github.com/safe/safe-geonode/',
    platforms=['any'],
    license='GPLv3',
    zip_safe=False,
    install_requires=[
        'python-safe>=0.5.8',       # pip install python-safe
        'GeoNode',                  # sudo apt-get install geonode
        'django-leaflet>=0.2.0',    # pip install django-leaflet
        'pygments',                 # pip install pygments
    ],
    packages = ['safe_geonode',],
    package_data = {'safe_geonode': ['safe_geonode/templates/*', 'safe_geonode/locale']},
    scripts = [],
    classifiers = [
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GPL License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP :: WSGI',
        'Topic :: Scientific/Engineering :: GIS',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules',
   ],
)
