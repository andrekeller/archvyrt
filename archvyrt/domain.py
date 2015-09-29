import libvirt
import logging
import xml.etree.ElementTree as ElementTree

from archvyrt.libvirt.domain import LibvirtDomain
from archvyrt.libvirt.disk import LibvirtDisk
from archvyrt.libvirt.network import LibvirtNetwork

LOG = logging.getLogger('archvyrt')


class Domain:
    """
    High-level domain object
    """

    def __init__(self, domain_info, libvirt_url=None):
        """
        Initialize libvirt domain

        :param domain_info - JSON definition of domain
        :param libvirt_url - URL for libvirt connection
        """
        self._conn = libvirt.open(libvirt_url)
        self._domain_info = domain_info
        self._domain = LibvirtDomain(self.fqdn)
        self._domain.memory = int(self.memory)
        self._domain.vcpu = int(self.vcpu)
        self._disks = []
        self._init_disks()
        self._networks = []
        self._init_networks()
        self._conn.defineXML(self.xml)
        self._domain.xml = self._conn.lookupByName(self.fqdn).XMLDesc()
        LOG.info('New domain %s', self.fqdn)
        LOG.debug(
            'Define new domain %s: %s',
            self.fqdn,
            self.xml.replace('\n', ' ').replace('\r', '')
        )

    def __del__(self):
        """
        Make sure to cleanup connection when object is destroyed
        """
        try:
            self.close()
        except libvirt.libvirtError:
            pass

    def close(self):
        """
        Close libvirt connection, if established
        """
        if self._conn:
            try:
                self._conn.close()
            except libvirt.libvirtError:
                pass

    def _init_disks(self):
        """
        Initialize disks

        will create libvirt disks and attach them to the domain
        """
        for alias, details in sorted(self._domain_info['disks'].items()):
            disk_name = '%s-%s' % (self.hostname, alias)
            self._disks.append(
                LibvirtDisk(
                    self._conn,
                    disk_name,
                    alias,
                    **details
                )
            )
        for disk in self._disks:
            self._domain.add_device(disk.xml)
            LOG.debug('Add disk %s to domain %s', disk.name, self.fqdn)

    def _init_networks(self):
        """
        Initialize networks
        """
        for alias, details in sorted(self._domain_info['networks'].items()):
            self._networks.append(
                LibvirtNetwork(
                    alias,
                    **details
                )
            )

        for network in self._networks:
            self._domain.add_device(network.xml)
            LOG.debug('Add network %s to domain %s', network.name, self.fqdn)

    def start(self):
        """
        Start domain

        Warning: Will not check if the domain is provisioned yet...
        """
        domain = self._conn.lookupByName(self.fqdn)
        domain.create()

    def stop(self):
        """
        Stop domain
        """
        domain = self._conn.lookupByName(self.fqdn)
        domain.destroy()

    def autostart(self, autostart):
        """
        Set autostart option of domain

        :param autostart - True/False
        """
        domain = self._conn.lookupByName(self.fqdn)
        domain.setAutostart(autostart)

    @property
    def sshkeys(self):
        """
        sshkeys (from JSON representation)
        """
        if self._domain_info.get('access', {}):
            return self._domain_info.get('access').get('ssh-keys', {})

    @property
    def password(self):
        """
        password (encrypted, salted hash from JSON representation)
        """
        if self._domain_info.get('access', {}):
            return self._domain_info.get('access').get('password', None)

    @property
    def guesttype(self):
        """
        Type of domain (archlinux, plain, ...)
        """
        return self._domain_info.get('guesttype')

    @property
    def disks(self):
        """
        Disks attached to this domain
        """
        return self._disks

    @property
    def networks(self):
        """
        Networks attached to this domain
        """
        return self._networks

    @property
    def fqdn(self):
        """
        FQDN of this domain
        """
        return self._domain_info.get('fqdn')

    @property
    def hostname(self):
        """
        hostname of this domain
        """
        return self._domain_info.get('hostname')

    @property
    def memory(self):
        """
        Memory (in MB) of this domain
        """
        return self._domain_info.get('memory')

    @property
    def vcpu(self):
        """
        Number of virtual cpus for this domain
        """
        return self._domain_info.get('vcpu')

    @property
    def xml(self):
        """
        XML representaion of this domain
        """
        return str(self._domain)

    @property
    def et(self):
        """
        ElementTree representaion of this domain
        """
        return self._domain.xml
