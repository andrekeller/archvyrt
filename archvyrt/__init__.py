#!/usr/bin/python3

"""
Libvirt provisioning for ArchLinux host system.
"""

import argparse
import json
import logging
import os

from archvyrt.domain import Domain
from archvyrt.provisioner import ArchlinuxProvisioner
from archvyrt.provisioner import PlainProvisioner
from archvyrt.provisioner import UbuntuProvisioner
from archvyrt.version import __version__

LOG = logging.getLogger(__name__)


def main():
    """
    main function.

    parse command line arguments, create VM and run the appropriate
    provisioner
    """

    parser = argparse.ArgumentParser(
        description="LibVirt VM provisioner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        prog='archvyrt',
    )
    parser.add_argument(
        '--log-level',
        dest='loglevel',
        default='info',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        help='Output log verbosity level'
    )
    parser.add_argument(
        '--mountpoint',
        default='/provision',
        help='Temporary mountpoint for provisioning'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s ' + __version__
    )
    parser.add_argument(
        'vmdefinition',
        help='Path to VM definition file'
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.getLevelName(args.loglevel.upper()),
                        format='%(asctime)s - %(levelname)s - %(message)s')

    with open(args.vmdefinition) as jsonfile:
        domain = Domain(json.load(jsonfile))

    if domain.guesttype == 'archlinux':
        os.mkdir(args.mountpoint)
        provisioner = ArchlinuxProvisioner(domain)
        provisioner.cleanup()
        domain.autostart(True)
        LOG.info('Enabled %s autostart', domain.fqdn)
        domain.start()
        LOG.info('Started domain %s', domain.fqdn)
        os.rmdir(args.mountpoint)
    elif domain.guesttype == 'ubuntu':
        os.mkdir(args.mountpoint)
        provisioner = UbuntuProvisioner(domain)
        provisioner.cleanup()
        domain.autostart(True)
        LOG.info('Enabled %s autostart', domain.fqdn)
        domain.start()
        LOG.info('Started domain %s', domain.fqdn)
        os.rmdir(args.mountpoint)
    elif domain.guesttype == 'plain':
        provisioner = PlainProvisioner(domain)
        provisioner.cleanup()
        domain.autostart(True)
        LOG.info('Enabled %s autostart', domain.fqdn)
    else:
        raise RuntimeError('Unsupported guest type: %s' % domain.guesttype)

    LOG.info('Provisioning of %s (%s) completed', domain.fqdn, domain.guesttype)
