"""
archvyrt setup module.
"""

from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

setup(
    name='archvyrt',
    version='0.2.1',
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
        'Programming Language :: Python :: 3.4',
    ],

    packages=find_packages(),
    install_requires=[
        'libvirt-python'
    ],

    entry_points={
        'console_scripts': [
            'archvyrt = archvyrt:main',
        ],
    },

)
