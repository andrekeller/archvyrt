"""archvyrt provisioner base module"""

# stdlib
import logging
import os
import subprocess

# archvyrt
import archvyrt.tools as tools

LOG = logging.getLogger(__name__)


class Provisioner:
    """
    Base provisioner for domain
    """

    def __init__(self, domain):
        """
        Initialize provisioner
        """
        self._domain = domain

    @property
    def domain(self):
        """
        Libvirt domain, this provisioner is attached to
        """
        return self._domain

    @staticmethod
    def _runcmd(cmds, output=False, **kwargs):
        """
        Run a unix command
        """
        # output shall be captured
        if output:
            LOG.debug('Run command: %s', ' '.join(cmds))
            rval = subprocess.check_output(
                cmds,
                stderr=subprocess.STDOUT,
                **kwargs
            ).decode()
        # output does not matter, send it to /dev/null
        else:
            with open(os.devnull, 'w') as devnull:
                LOG.debug('Run command: %s', ' '.join(cmds))
                rval = subprocess.call(
                    cmds,
                    stdout=devnull,
                    stderr=devnull,
                    **kwargs
                )
            if rval != 0:
                raise RuntimeError(
                    'Command %s failed, env: %s' % (' '.join(cmds),
                                                    kwargs.get('env', 'default'))
                )
        return rval

    @staticmethod
    def writefile(filename, lines, mode='w'):
        """
        Write to a file
        """
        LOG.debug('Write file %s', filename)
        with open(filename, mode) as fobj:
            fobj.write('%s\n' % '\n'.join(lines))

    def cleanup(self):
        """
        cleanup actions
        """
        raise NotImplementedError


class LinuxProvisioner(Provisioner):
    """
    Linux Base Provisioner
    """

    def __init__(self, domain, target="/provision"):
        """
        Initializes and runs the provisioner.
        """
        super().__init__(domain)
        self._target = target
        self._uuid = {}
        self._cleanup = []

        self._prepare_disks()
        self._install()
        self._network_config()
        self._locale_config()
        self._fstab_config()
        self._boot_config()
        self._access_config()

    @property
    def target(self):
        """
        Temporary provisioning target, where the domains disks are mounted
        """
        return self._target

    def run(self, *cmds, output=False, **kwargs):
        """
        Runs a command, ensures proper environment
        """
        env = kwargs.pop('env', os.environ.copy())
        return self._runcmd(cmds, output, env=env, **kwargs)

    def runchroot(self, *cmds, output=False, add_env=None, **kwargs):
        """
        Runs a command in the guest
        """
        env = kwargs.pop('env', os.environ.copy())
        env['PATH'] = ":".join(("/usr/local/sbin",
                                "/usr/local/bin",
                                "/usr/sbin",
                                "/usr/bin",
                                "/sbin",
                                "/bin"))
        if add_env is not None:
            env.update(add_env)
        chroot_cmds = (tools.ARCH_CHROOT,
                       self.target) + cmds
        return self.run(*chroot_cmds, output=output, env=env, **kwargs)

    def writetargetfile(self, filename, lines, mode='w'):
        """
        Writes a file in the guest
        """
        targetfilename = "%s%s" % (self.target, filename)
        self.writefile(targetfilename, lines, mode)

    def chmodtargetfile(self, filename, chmod):
        """
        Change permission of file in the guest
        """
        targetfilename = "%s%s" % (self.target, filename)
        os.chmod(targetfilename, chmod)

    def deletetargetfile(self, filename):
        """
        Delete a file in the guest
        """
        targetfilename = "%s%s" % (self.target, filename)
        os.remove(targetfilename)

    def cleanup(self):
        """
        Cleanup actions, such as unmounting and disconnecting disks
        """
        for cmd in reversed(self._cleanup):
            self.run(*cmd)

    def _prepare_disks(self):
        """
        Format and mount disks
        """
        LOG.info('Prepare disks')
        for disk in self.domain.disks:
            dev = '/dev/nbd%s' % disk.number
            cur_part = 0
            # "mount" qcow2 image file as block device
            self.run(
                tools.QEMU_NBD,
                '-n',
                '-c',
                dev,
                disk.path
            )
            self._cleanup.append([
                tools.QEMU_NBD,
                '-d',
                dev,
            ])
            # create empty partition table
            self.run(
                tools.SGDISK,
                '-o',
                dev
            )
            # On first disk, we create a bios boot partition
            if disk.number == '0':
                cur_part += 1
                self.run(
                    tools.SGDISK,
                    '-n', '%d:2048:4095' % cur_part,
                    '-t', '%d:ef02' % cur_part,
                    dev
                )
                endsector = self.run(
                    tools.SGDISK,
                    '-E',
                    dev,
                    output=True).strip()
                cur_part += 1
                self.run(
                    tools.SGDISK,
                    '-n', '%d:4096:%s' % (cur_part, endsector),
                    dev
                )
            else:
                # create single partition
                cur_part += 1
                self.run(
                    tools.SGDISK,
                    '-n', '%d' % cur_part,
                    dev
                )
            if disk.fstype == 'ext4':
                # format ext4
                self.run(
                    tools.MKFS_EXT4,
                    '%sp%d' % (dev, cur_part)
                )
                mountpoint = '/provision/%s' % disk.mountpoint.lstrip('/')
                if disk.mountpoint == '/':
                    # set a filesystem label to aid grub configuration
                    self.run(
                        tools.TUNE2FS,
                        '-L',
                        'ROOTFS',
                        '%sp%d' % (dev, cur_part)
                    )
                else:
                    # create mountpoint
                    os.makedirs(mountpoint)
                self.run(
                    tools.MOUNT,
                    '%sp%d' % (dev, cur_part),
                    mountpoint
                )
                self._cleanup.append([
                    tools.UMOUNT,
                    mountpoint,
                ])
                uuid = self.run(
                    tools.BLKID,
                    '-s',
                    'UUID',
                    '-o',
                    'value',
                    '%sp%d' % (dev, cur_part),
                    output=True
                ).strip()
                self._uuid.setdefault('ext4', {})[disk.mountpoint] = uuid
            elif disk.fstype == 'swap':
                # set partition type to linux swap
                self.run(
                    tools.SGDISK,
                    '-t',
                    '%d:8200' % cur_part,
                    dev
                )
                # format swap space
                self.run(
                    tools.MKSWAP,
                    '-f',
                    '%sp%d' % (dev, cur_part)
                )
                self.run(
                    tools.SWAPON,
                    '%sp%d' % (dev, cur_part)
                )
                self._cleanup.append([
                    tools.SWAPOFF,
                    '%sp%d' % (dev, cur_part)
                ])
                uuid = self.run(
                    tools.BLKID,
                    '-s',
                    'UUID',
                    '-o',
                    'value',
                    '%sp%d' % (dev, cur_part),
                    output=True
                ).strip()
                self._uuid.setdefault('swap', []).append(uuid)
            else:
                raise RuntimeError('Unsupported fstype %s' % disk.fstype)

    def _install(self):
        """
        Linux base installation
        """
        raise NotImplementedError

    def _network_config(self):
        """
        Domain network configuration
        """
        raise NotImplementedError

    def _locale_config(self):
        """
        Domain locale/language settings
        """
        raise NotImplementedError

    def _fstab_config(self):
        """
        Domain fstab configuration
        """
        LOG.info('Write fstab configuration')
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

    def _boot_config(self):
        """
        Domain bootloader, initrd configuration
        """
        raise NotImplementedError

    def _access_config(self):
        """
        Domain access configuration such as sudo/ssh and local users
        """
        raise NotImplementedError
