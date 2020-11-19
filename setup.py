import sys
from setuptools import setup, find_packages

if sys.version_info < (3, 6):
    raise ValueError("Requires Python 3.6 or superior")

from molotov import __version__  # NOQA

install_requires = ["aiohttp", "aiomeasures", "aiodogstatsd", "multiprocessing_on_dill"]

description = ""

for file_ in ("README", "CHANGELOG"):
    with open("%s.rst" % file_) as f:
        description += f.read() + "\n\n"


classifiers = [
    "Programming Language :: Python",
    "License :: OSI Approved :: Apache Software License",
    "Development Status :: 5 - Production/Stable",
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
]


setup(
    name="molotov",
    version=__version__,
    url="https://molotov.readthedocs.io",
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
      """,
)
