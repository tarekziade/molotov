from setuptools import setup, find_packages
from ailoads import __version__
import sys

install_requires = ['requests']

if sys.version_info < (2, 7):
    install_requires += ['argparse']

description = ''

for file_ in ('README', ):
    with open('%s.rst' % file_) as f:
        description += f.read() + '\n\n'


classifiers = ["Programming Language :: Python",
               "License :: OSI Approved :: Apache Software License",
               "Development Status :: 1 - Planning"]


setup(name='ailoads',
      version=__version__,
      url='https://github.com/tarekziade/ailoads',
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
      ailoads = ailoads.run:main
      """)
