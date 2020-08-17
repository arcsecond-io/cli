"""
 CLI for arcsecond.io
"""
import ast
import os
import re

from setuptools import find_packages, setup

_version_re = re.compile(r'__version__\s+=\s+(.*)')
with open('arcsecond/__init__.py', 'rb') as f:
    __version__ = str(ast.literal_eval(_version_re.search(f.read().decode('utf-8')).group(1)))

_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='arcsecond',
    version=__version__,
    url='https://github.com/arcsecond-io/cli',
    license='MIT',
    author='Cedric Foellmi',
    author_email='cedric@arcsecond.io',
    description=' CLI for arcsecond.io',
    long_description=long_description,
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'click',
        'requests',
        'requests_toolbelt',
        'pygments',
        'configparser',
        'progress'
    ],
    entry_points={
        'console_scripts': [
            'arcsecond = arcsecond.cli:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Operating System :: MacOS',
        'Operating System :: Unix',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
