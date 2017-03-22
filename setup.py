from setuptools import setup, find_packages
from molotov import __version__


install_requires = ['aiohttp', 'urwid', 'humanize']
description = ''

for file_ in ('README', 'CHANGELOG'):
    with open('%s.rst' % file_) as f:
        description += f.read() + '\n\n'


classifiers = ["Programming Language :: Python",
               "License :: OSI Approved :: Apache Software License",
               "Development Status :: 1 - Planning"]


setup(name='molotov',
      version=__version__,
      url='https://github.com/loads/molotov',
      packages=find_packages(),
      long_description=description.strip(),
      description=("Spiffy load testing tool."),
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
      molostart = molotov.quickstart:main
      """)
