import logging
import os

from archvyrt.provisioner import Base

LOG = logging.getLogger('archvyrt')


class ArchlinuxProvisioner(Base):
    """
    ArchLinux Provisioner
    """

    def __init__(self, domain, target="/provision", proxy=None):
        """
        Initializes and runs the provisioner.
        """
        super().__init__(domain)
        self._proxy = proxy
        self._target = target
        self._uuid = {}
        self._cleanup = []

        self._prepare_disks()
        self._install()
        self._network_config()
        self._locale_config()
        self._boot_config()
        self._access_config()

    @property
    def proxy(self):
        """
        Proxy server used by this provisioner
        """
        return self._proxy

    @property
    def target(self):
        """
        Temporary provisioning target, where the domains disks are mounted
        """
        return self._target

    def run(self, cmds, output=False, failhard=True, **kwargs):
        """
        Runs a command, ensures proper environment
        """
        run_env = kwargs.pop('env', None)
        if not run_env:
            run_env = os.environ.copy()
            if self.proxy:
                run_env['http_proxy'] = 'http://%s' % self.proxy
                run_env['ftp_proxy'] = 'http://%s' % self.proxy
        return self._runcmd(cmds, output, failhard, **kwargs)

    def runchroot(self, cmds, output=False, failhard=True, **kwargs):
        """
        Runs a command in the guest
        """
        chroot_cmds = [
            '/usr/bin/arch-chroot',
            self.target,
        ]
        return self.run(chroot_cmds + cmds, output, failhard, **kwargs)

    def writetargetfile(self, filename, lines, mode='w'):
        """
        Writes a file in the guest
        """
        targetfilename = "%s%s" % (self.target, filename)
        self.writefile(targetfilename, lines, mode)

    def cleanup(self):
        """
        Cleanup actions, such as unmounting and disconnecting disks
        """
        for cmd in reversed(self._cleanup):
            self.run(cmd)

    def _prepare_disks(self):
        """
        Format and mount disks
        """
        LOG.info('Prepare disks')
        for disk in self.domain.disks:
            dev = '/dev/nbd%s' % disk.number
            cur_part = 0
            # "mount" qcow2 image file as block device
            self.run([
                '/usr/bin/qemu-nbd',
                '-n',
                '-c',
                dev,
                disk.path,
            ])
            self._cleanup.append([
                '/usr/bin/qemu-nbd',
                '-d',
                dev,
            ])
            # create empty partition table
            self.run([
                '/usr/bin/sgdisk',
                '-o',
                dev,
            ])
            # On first disk, we create a bios boot partition
            if disk.number == '0':
                cur_part += 1
                self.run([
                    '/usr/bin/sgdisk',
                    '-n', '%d:2048:4095' % cur_part,
                    '-t', '%d:ef02' % cur_part,
                    dev
                ])
                endsector = self.run([
                    '/usr/bin/sgdisk',
                    '-E',
                    dev
                ], output=True).strip()
                cur_part += 1
                self.run([
                    '/usr/bin/sgdisk',
                    '-n', '%d:4096:%s' % (cur_part, endsector),
                    dev
                ])
            else:
                # create single partition
                cur_part += 1
                self.run([
                    '/usr/bin/sgdisk',
                    '-n', '%d' % cur_part,
                    dev
                ])
            if disk.fstype == 'ext4':
                # format ext4
                self.run([
                    '/usr/bin/mkfs.ext4',
                    '%sp%d' % (dev, cur_part)
                ])
                mountpoint = '/provision/%s' % disk.mountpoint.lstrip('/')
                if disk.mountpoint == '/':
                    # set a filesystem label to aid grub configuration
                    self.run([
                        '/usr/bin/tune2fs',
                        '-L',
                        'ROOTFS',
                        '%sp%d' % (dev, cur_part),
                        ])
                else:
                    # create mountpoint
                    os.makedirs(mountpoint)
                self.run([
                    '/usr/bin/mount',
                    '%sp%d' % (dev, cur_part),
                    mountpoint,
                    ])
                self._cleanup.append([
                    '/usr/bin/umount',
                    mountpoint,
                ])
                uuid = self.run([
                    '/usr/bin/blkid',
                    '-s',
                    'UUID',
                    '-o',
                    'value',
                    '%sp%d' % (dev, cur_part),
                    ], output=True).strip()
                self._uuid.setdefault('ext4', {})[disk.mountpoint] = uuid
            elif disk.fstype == 'swap':
                # set partition type to linux swap
                self.run([
                    '/usr/bin/sgdisk',
                    '-t',
                    '%d:8200' % cur_part,
                    dev
                ])
                # format swap space
                self.run([
                    '/usr/bin/mkswap',
                    '-f',
                    '%sp%d' % (dev, cur_part)
                ])
                self.run([
                    '/usr/bin/swapon',
                    '%sp%d' % (dev, cur_part)
                ])
                self._cleanup.append([
                    '/usr/bin/swapoff',
                    '%sp%d' % (dev, cur_part)
                ])
                uuid = self.run([
                    '/usr/bin/blkid',
                    '-s',
                    'UUID',
                    '-o',
                    'value',
                    '%sp%d' % (dev, cur_part),
                    ], output=True).strip()
                self._uuid.setdefault('swap', []).append(uuid)
            else:
                raise RuntimeError('Unsupported fstype %s', disk.fstype)

    def _install(self):
        """
        ArchLinux base installation
        """
        LOG.info('Do ArchLinux installation')
        self.run([
            '/usr/bin/pacstrap',
            self.target,
            'base'
        ])

    def _network_config(self):
        """
        Domain network configuration
        """
        LOG.info('Setup guest networking')

        # get provisioned interfaces
        interfaces = self.domain.et.find('devices').findall('interface')

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
            self.runchroot([
                'netctl',
                'enable',
                network.name
            ])

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
        self.runchroot([
            'ln',
            '-sf',
            '/usr/share/zoneinfo/Europe/Zurich',
            '/etc/localtime',
        ])
        self.runchroot([
            'locale-gen',
        ])

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
        self.writetargetfile('/etc/mkinitcpio.conf', [
            'MODULES="virtio virtio_blk virtio_pci virtio_net"',
            'BINARIES=""',
            'FILES=""',
            'HOOKS="base udev autodetect modconf block mdadm_udev lvm2 '
            'filesystems keyboard fsck"',
        ])
        self.runchroot([
            'mkinitcpio',
            '-p',
            'linux'
        ])
        self.runchroot([
            'pacman',
            '-Syy',
            '--noconfirm',
            'grub'
        ])
        self.runchroot([
            'grub-install',
            '--target=i386-pc',
            '/dev/nbd0'
        ])
        self.runchroot([
            'grub-mkconfig',
            '-o',
            '/boot/grub/grub.cfg'
        ])
        # With nbd devices, grub-mkconfig does not use the UUID/LABEL
        # So change it in the resulting file
        self.run([
            '/usr/bin/sed',
            '-i',
            '-e',
            's/vmlinuz-linux root=[^ ]*/vmlinuz-linux root=UUID=%s/' %
            self._uuid['ext4']['/'],
            '%s/boot/grub/grub.cfg' % self.target
        ])

    def _access_config(self):
        """
        Domain access configuration such as sudo/ssh and local users
        """
        LOG.info('Setup ssh/local user access')
        self.runchroot([
            'pacman',
            '-Syy',
            '--noconfirm',
            'openssh'
        ])
        self.runchroot([
            'systemctl',
            'enable',
            'sshd.service'
        ])
        self.runchroot([
            'systemctl',
            'enable',
            'getty@ttyS0.service'
        ])
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

