"""archvyrt setup module"""

from pathlib import Path
import re
from setuptools import setup, find_packages


def find_version(source_file):
    """read __version__ from source file"""
    with open(source_file) as version_file:
        version_match = re.search(r"^__version__\s*=\s* ['\"]([^'\"]*)['\"]",
                                  version_file.read(), re.M)
        if version_match:
            return version_match.group(1)
        raise RuntimeError('Unable to find package version')


setup(
    name='archvyrt',
    version=find_version(str(Path('./archvyrt/version.py'))),
    description='libvirt provisioner for archlinux libvirt hosts',
    url='https://github.com/andrekeller/archvyrt',
    author='Andre Keller',
    author_email='ak@0x2a.io',
    license='MIT',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Systems Administration',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
    ],

    packages=find_packages(),
    install_requires=[
        'libvirt-python'
    ],
    python_requires='>=3.4',
    entry_points={
        'console_scripts': [
            'archvyrt = archvyrt:main',
        ],
    },
)
