"""archvyrt archlinux provisioner module"""

# stdlib
import logging
import os
# archvyrt
import archvyrt.tools as tools
from .base import LinuxProvisioner

LOG = logging.getLogger(__name__)


class ArchlinuxProvisioner(LinuxProvisioner):
    """
    ArchLinux Provisioner
    """

    def _install(self):
        """
        ArchLinux base installation
        """
        LOG.info('Do ArchLinux installation')
        self.run(
            tools.PACSTRAP,
            self.target,
            'base'
        )

    def _network_config(self):
        """
        Domain network configuration
        """
        LOG.info('Setup guest networking')

        # get provisioned interfaces
        interfaces = self.domain.xml.find('devices').findall('interface')

        addresses = []
        udev_lines = []
        for interface, network in zip(interfaces, self.domain.networks):
            # update interface xml with provisioned interface
            # this also includes pci slots and mac-addresses
            network.xml = interface
            if network.ipv4_address:
                addresses.append(network.ipv4_address.ip)
            if network.ipv6_address:
                addresses.append(network.ipv6_address.ip)
            if network.mac:
                udev_lines.append(
                    'SUBSYSTEM=="net", ACTION=="add", '
                    'ATTR{address}=="%s", NAME="%s"' % (network.mac,
                                                        network.name)
                )
            self.writetargetfile(
                '/etc/netctl/%s' % network.name,
                network.netctl
            )
            self.runchroot(
                'netctl',
                'enable',
                network.name
            )

        self.writetargetfile(
            '/etc/udev/rules.d/10-network.rules',
            udev_lines
        )
        self.writetargetfile('/etc/hostname', [self.domain.hostname, ])

        host_entries = [
            '127.0.0.1 localhost.localdomain localhost',
            '::1 localhost.localdomain localhost'
        ]
        if addresses:
            for address in addresses:
                host_entries.append(
                    '%s %s %s' % (
                        address,
                        self.domain.fqdn,
                        self.domain.hostname
                    )
                )
        self.writetargetfile('/etc/hosts', host_entries)

    def _locale_config(self):
        """
        Domain locale/language settings
        """
        LOG.info('Setup locale/language settings')
        self.writetargetfile('/etc/locale.gen', [
            'en_US.UTF-8 UTF-8',
            'de_CH.UTF-8 UTF-8',
        ])
        self.writetargetfile('/etc/locale.conf', [
            'LANG="en_US.UTF-8"',
            'LC_CTYPE="en_US.UTF-8"',
            'LC_COLLATE=C',
            'LC_MESSAGES="en_US.UTF-8"',
            'LC_MONETARY="de_CH.UTF-8"',
            'LC_NUMERIC="de_CH.UTF-8"',
            'LC_PAPER="de_CH.UTF-8"',
            'LC_TIME="de_CH.UTF-8"',
        ])
        self.writetargetfile('/etc/vconsole.conf', [
            'KEYMAP=sg',
            'FONT=lat9w-16',
            'FONT_MAP=8859-1_to_uni',
        ])
        self.runchroot(
            'ln',
            '-sf',
            '/usr/share/zoneinfo/Europe/Zurich',
            '/etc/localtime',
        )
        self.runchroot(
            'locale-gen',
        )

    def _boot_config(self):
        """
        Domain bootloader, initrd configuration
        """
        LOG.info('Setup boot configuration')
        self.writetargetfile('/etc/mkinitcpio.conf', [
            'MODULES="virtio virtio_blk virtio_pci virtio_net"',
            'BINARIES=""',
            'FILES=""',
            'HOOKS="base udev autodetect modconf block mdadm_udev lvm2 '
            'filesystems keyboard fsck"',
        ])
        self.runchroot(
            'mkinitcpio',
            '-p',
            'linux'
        )
        self.runchroot(
            'pacman',
            '-Syy',
            '--noconfirm',
            'grub'
        )
        self.runchroot(
            'grub-install',
            '--target=i386-pc',
            '/dev/nbd0'
        )
        self.runchroot(
            'grub-mkconfig',
            '-o',
            '/boot/grub/grub.cfg'
        )
        # With nbd devices, grub-mkconfig does not use the UUID/LABEL
        # So change it in the resulting file
        self.run(
            tools.SED,
            '-i',
            '-e',
            's/vmlinuz-linux root=[^ ]*/vmlinuz-linux root=UUID=%s/' %
            self._uuid['ext4']['/'],
            '%s/boot/grub/grub.cfg' % self.target
        )

    def _access_config(self):
        """
        Domain access configuration such as sudo/ssh and local users
        """
        LOG.info('Setup ssh/local user access')
        self.runchroot(
            'pacman',
            '-Syy',
            '--noconfirm',
            'openssh'
        )
        self.runchroot(
            'systemctl',
            'enable',
            'sshd.service'
        )
        self.runchroot(
            'systemctl',
            'enable',
            'getty@ttyS0.service'
        )
        if self.domain.password:
            self.runchroot(
                'usermod',
                '-p',
                self.domain.password,
                'root'
            )
        if self.domain.sshkeys:
            authorized_keys = []
            for key, value in self.domain.sshkeys.items():
                authorized_keys.append(
                    "%s %s %s" % (value['type'], value['key'], key)
                )
            os.mkdir('%s/root/.ssh' % self.target)
            self.writetargetfile(
                '/root/.ssh/authorized_keys',
                authorized_keys
            )
