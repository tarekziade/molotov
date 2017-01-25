from setuptools import setup, find_packages
from molotov import __version__
import sys

install_requires = ['aiohttp', 'statsd', 'urwid', 'humanize',
                    'redis']
description = ''

for file_ in ('README', ):
    with open('%s.rst' % file_) as f:
        description += f.read() + '\n\n'


classifiers = ["Programming Language :: Python",
               "License :: OSI Approved :: Apache Software License",
               "Development Status :: 1 - Planning"]


setup(name='molotov',
      version=__version__,
      url='https://github.com/loads/molotov',
      packages=find_packages(),
      long_description=description,
      description=("AsyncIO Loads client"),
      author="Tarek Ziade",
      author_email="tarek@ziade.org",
      include_package_data=True,
      zip_safe=False,
      classifiers=classifiers,
      install_requires=install_requires,
      entry_points="""
      [console_scripts]
      molotov = molotov.run:main
      moloslave = molotov.slave:main
      """)
