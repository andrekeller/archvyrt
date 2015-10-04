import logging
import os

from archvyrt.provisioner.base.linux import LinuxProvisioner

LOG = logging.getLogger('archvyrt')


class UbuntuProvisioner(LinuxProvisioner):
    """
    Ubuntu Provisioner
    """

    def runchroot(self, cmds, output=False, failhard=True, **kwargs):
        """
        Runs a command in the guest
        """
        run_env = kwargs.pop('env', None)
        if not run_env:
            run_env = os.environ.copy()
        run_env['PATH'] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        chroot_cmds = [
            '/usr/bin/arch-chroot',
            self.target,
        ]
        return self.run(chroot_cmds + cmds, output, failhard, env=run_env, **kwargs)

    def _install(self):
        """
        Ubuntu base installation
        """
        LOG.info('Do Ubuntu installation')
        self.run([
            '/usr/bin/debootstrap',
            'trusty',
            self.target,
            'http://de.archive.ubuntu.com/ubuntu/'
        ])

    def _network_config(self):
        """
        Domain network configuration
        """
        LOG.info('Setup guest networking')

        # get provisioned interfaces
        interfaces = self.domain.et.find('devices').findall('interface')

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
        Domain fstab, bootloader, initrd configuration
        """
        LOG.info('Setup boot configuration')
        swap_lines = []
        ext4_lines = []
        for key, value in self._uuid.items():
            fsckcount = 0
            if key == 'swap':
                for uuid in value:
                    swap_lines.append("UUID=%s none swap defaults 0 0" % uuid)
            elif key == 'ext4':
                for mountpoint, uuid in sorted(value.items()):
                    fsckcount += 1
                    ext4_lines.append(
                        "UUID=%s %s ext4 rw,relatime,data=ordered 0 %d" % (
                            uuid, mountpoint, fsckcount
                        )
                    )

        self.writetargetfile('/etc/fstab', ext4_lines + swap_lines, 'a')
        apt_env = os.environ.copy()
        apt_env['DEBIAN_FRONTEND'] = "noninteractive"
        self.runchroot([
            'apt-get',
            '-qy',
            'install',
            'grub-pc',
            'linux-image-virtual'
        ], env=apt_env)
        self.runchroot([
            'grub-install',
            '--target=i386-pc',
            '/dev/nbd0'
        ])
        self.runchroot([
            'update-grub',
        ])
        # With nbd devices, grub-mkconfig does not use the UUID/LABEL
        # So change it in the resulting file
        self.run([
            '/usr/bin/sed',
            '-i',
            '-e',
            's/vmlinuz-\(.*\) root=[^ ]*/vmlinuz-\\1 root=UUID=%s/' %
            self._uuid['ext4']['/'],
            '%s/boot/grub/grub.cfg' % self.target
        ])

    def _access_config(self):
        """
        Domain access configuration such as sudo/ssh and local users
        """
        LOG.info('Setup ssh/local user access')
        apt_env = os.environ.copy()
        apt_env['DEBIAN_FRONTEND'] = "noninteractive"
        self.runchroot([
            'apt-get',
            '-qy',
            'install',
            'ssh'
        ], env=apt_env)
        self.runchroot([
            'service',
            'ssh',
            'stop'
        ])
        self.writetargetfile(
            '/etc/init/ttyS0.conf',
            [
                '# libvirt console',
                '',
                'start on runlevel [23] and not-container',
                '',
                'stop on runlevel [!23]',
                '',
                'respawn',
                'exec /sbin/getty -8 38400 ttyS0',
            ]
        )
        if self.domain.password:
            self.runchroot([
                'usermod',
                '-p',
                self.domain.password,
                'root'
            ])
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
