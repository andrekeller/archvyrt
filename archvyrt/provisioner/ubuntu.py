"""archvyrt ubuntu provisioner module"""

# stdlib
import logging
import os
# archvyrt
import archvyrt.tools as tools
from .base import LinuxProvisioner

LOG = logging.getLogger(__name__)


class UbuntuProvisioner(LinuxProvisioner):
    """
    Ubuntu Provisioner
    """

    def _install(self):
        """
        Ubuntu base installation
        """
        LOG.info('Do Ubuntu installation')
        self.run(
            tools.DEBOOTSTRAP,
            'xenial',
            self.target,
            'http://ch.archive.ubuntu.com/ubuntu/'
        )

    def _network_config(self):
        """
        Domain network configuration
        """
        LOG.info('Setup guest networking')

        # get provisioned interfaces
        interfaces = self.domain.xml.find('devices').findall('interface')

        dns_servers = []
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
                '/etc/network/interfaces.d/%s' % network.name,
                network.interfaces
            )
            if network.dns:
                for server in network.dns:
                    dns_servers.append('nameserver %s' % str(server))

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
        if dns_servers:
            self.writetargetfile(
                '/etc/resolvconf/resolv.conf.d/original',
                dns_servers
            )
            self.writetargetfile(
                '/etc/resolvconf/resolv.conf.d/tail',
                dns_servers
            )

    def _locale_config(self):
        """
        Domain locale/language settings
        """
        pass

    def _boot_config(self):
        """
        Domain bootloader, initrd configuration
        """
        LOG.info('Setup boot configuration')
        apt_env = {'DEBIAN_FRONTEND': "noninteractive"}
        self.runchroot(
            'apt-get',
            '-qy',
            'install',
            'grub-pc',
            'linux-image-virtual',
            add_env=apt_env
        )
        self.runchroot(
            'grub-install',
            '--target=i386-pc',
            '/dev/nbd0'
        )
        # Enable serial console
        self.runchroot(
            'systemctl',
            'enable',
            'getty@ttyS0.service'
        )
        # Remove quiet and splash option
        self.runchroot(
            'sed',
            '-i',
            # pylint: disable=anomalous-backslash-in-string
            's/^\(GRUB_CMDLINE_LINUX_DEFAULT=\).*/\\1""/',
            '/etc/default/grub'
        )
        self.runchroot(
            'update-grub',
        )
        # With nbd devices, grub-mkconfig does not use the UUID/LABEL
        # So change it in the resulting file
        self.run(
            tools.SED,
            '-i',
            '-e',
            # pylint: disable=anomalous-backslash-in-string
            's/vmlinuz-\(.*\) root=[^ ]*/vmlinuz-\\1 root=UUID=%s/' %
            self._uuid['ext4']['/'],
            '%s/boot/grub/grub.cfg' % self.target
        )

    def _access_config(self):
        """
        Domain access configuration such as sudo/ssh and local users
        """
        LOG.info('Setup ssh/local user access')
        self.writetargetfile('/usr/sbin/policy-rc.d', ['exit 101'])
        self.chmodtargetfile('/usr/sbin/policy-rc.d', 0o555)
        apt_env = {'DEBIAN_FRONTEND': "noninteractive"}
        self.runchroot(
            'apt-get',
            '-qy',
            'install',
            'ssh',
            add_env=apt_env
        )
        self.deletetargetfile('/usr/sbin/policy-rc.d')
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
