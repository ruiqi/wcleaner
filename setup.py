#!/usr/bin/env python
# -*- coding: utf-8 -*-

from wcleaner import __version__

from setuptools import setup

setup(
    name = 'wcleaner',
    version = __version__,
    description = "Disk Space Cleaner",
    author = 'ruiqi',
    author_email = 'smile.ruiqi@gmail.com',
    url = 'https://github.com/ruiqi/wcleaner',
    download_url = 'https://github.com/ruiqi/wcleaner/archive/v%s.tar.gz' %__version__,
    keywords = ['disk', 'cleaner', 'walk', 'scandir'],
    license = 'License :: OSI Approved :: MIT License',

    packages = [
        'wcleaner',
    ],

    entry_points = {
        'console_scripts': [
            'wcleaner = wcleaner.core:wcleaner',
            'echo_wcleaner_conf = wcleaner.core:echo_wcleaner_conf',
        ]
    },
    install_requires = [
        'argparse',
        'scandir',
    ],
)
