#!/usr/bin/python3

"""
Libvirt provisioning for ArchLinux host system.
"""

import argparse
import json
import logging
import os

from archvyrt.domain import Domain
from archvyrt.provisioner.archlinux import ArchlinuxProvisioner
from archvyrt.provisioner.plain import PlainProvisioner


LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def main():
    """
    main function.

    parse command line arguments, create VM and run the appropriate
    provisioner
    """

    parser = argparse.ArgumentParser(
        description="LibVirt VM provisioner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--proxy', dest='proxy',
        default='127.0.0.1:3128',
        help='Proxy to use when running provisioning commands'
    )
    parser.add_argument(
        '--no-proxy', dest='use_proxy', action='store_false',
        default=True,
        help='Disable proxy'
    )
    parser.add_argument(
        '--mountpoint', dest='mountpoint',
        default='/provision',
        help='Temporary mountpoint for provisioning'
    )
    parser.add_argument(
        'vmdefinition',
        help='Path to VM definition file'
    )
    args = parser.parse_args()

    with open(args.vmdefinition) as jsonfile:
        domain = Domain(json.load(jsonfile))

    if domain.guesttype == 'archlinux':
        os.mkdir(args.mountpoint)
        if args.use_proxy:
            proxy = args.proxy
        else:
            proxy = None
        provisioner = ArchlinuxProvisioner(domain, proxy=proxy)
        provisioner.cleanup()
        domain.autostart(True)
        domain.start()
        os.rmdir(args.mountpoint)
    elif domain.guesttype == 'plain':
        provisioner = PlainProvisioner(domain)
        provisioner.cleanup()
        domain.autostart(True)
    else:
        raise RuntimeError('Unsupported guest type: %s' % domain.guesttype)

    domain.close()

if __name__ == '__main__':
    main()
