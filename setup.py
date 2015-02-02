#!/usr/bin/env python
# -*- coding: utf-8 -*-

from wcleaner import __version__

from setuptools import setup

setup(
    license='License :: OSI Approved :: MIT License',
    name='wcleaner',
    version=__version__,
    author='ruiqi',
    author_email='liruiqi@wandoujia.com',
    url='http://gitlab.wandoulabs.com/liruiqi/wcleaner',
    description="Wandoujia Cleaner",
    packages=[
        'wcleaner',
    ],

    entry_points={
        'console_scripts': [
            'wcleaner = wcleaner.core:wcleaner',
        ]
    },
    install_requires=[
        'argparse',
        'scandir',
    ],
)
