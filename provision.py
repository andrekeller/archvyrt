#!/usr/bin/python3

"""
Libvirt provisioning for ArchLinux host system.
"""

# Copyright (c) 2015, Andre Keller <ak@0x2a.io>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import argparse
import ipaddress
import json
import libvirt
import logging
import os
import re
import subprocess
import xml.etree.ElementTree as ElementTree
import xml.dom.minidom

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class LibvirtDisk:
    """
    LibVirt Disk device object.
    """

    def __init__(self, conn, name, alias, **kwargs):
        """
        Initialie a libvirt disk.

        This will create a Qcow2 image file and its libvirt XML representation.

        :param conn - Libvirt connection (already established)
        :param name - Name of the virtual disk
        :param alias - Short name of the virtual disk
        :param kwargs - Additional properties of the disk:
                         pool - Storage pool name
                         fstype - Type of filesystem
                         target - Target device in guest (vda, vdb, ...)
                         mountpoint - Where to mount the disk in the guest
                         capacity - Disk capacity in GB
        """

        self._alias = alias
        self._name = name
        self._properties = kwargs

        lv_pool = conn.storagePoolLookupByName(self.pool)
        lv_pool.createXML(
            self._volume_xml(),
            libvirt.VIR_STORAGE_VOL_CREATE_PREALLOC_METADATA
        )
        lv_volume = lv_pool.storageVolLookupByName(self.name)
        self._path = lv_volume.path()

        self._xml = ElementTree.Element('disk')
        self._xml.attrib['type'] = 'file'
        self._xml.attrib['device'] = 'disk'
        driver_element = ElementTree.Element('driver')
        driver_element.attrib['name'] = 'qemu'
        driver_element.attrib['type'] = 'qcow2'
        self._xml.append(driver_element)
        target_element = ElementTree.Element('target')
        target_element.attrib['dev'] = self.target
        target_element.attrib['bus'] = 'virtio'
        self._xml.append(target_element)
        source_element = ElementTree.Element('source')
        source_element.attrib['file'] = self.path
        self._xml.append(source_element)
        alias_element = ElementTree.Element('alias')
        alias_element.attrib['name'] = 'virtio-%s' % self.alias
        self._xml.append(alias_element)

        LOG.debug("Define virtual disk %s (%s bytes)", self.name, self.capacity)

    def _volume_xml(self):
        """
        Generate Libvirt Volume XML, to create the actual Qcow2 image
        """
        volume_xml = ElementTree.Element('volume')
        name_element = ElementTree.Element('name')
        name_element.text = self.name
        volume_xml.append(name_element)
        capacity_element = ElementTree.Element('capacity')
        capacity_element.text = self.capacity
        volume_xml.append(capacity_element)
        allocation_element = ElementTree.Element('allocation')
        allocation_element.text = self.capacity
        volume_xml.append(allocation_element)
        target_element = ElementTree.Element('target')
        format_element = ElementTree.Element('format')
        format_element.attrib['type'] = 'qcow2'
        target_element.append(format_element)
        volume_xml.append(target_element)
        return self.__format_xml(volume_xml)

    @staticmethod
    def __format_xml(et_xml):
        """
        Return a pretty formatted XML

        :param et_xml - ElementTree XML object
        """
        reparsed = xml.dom.minidom.parseString(
            ElementTree.tostring(et_xml, encoding='unicode')
        )
        return reparsed.toprettyxml(indent="  ").strip()

    def __str__(self):
        """
        Return a pretty formatted XML representation of this disk
        """
        return self.__format_xml(self._xml)

    @property
    def mountpoint(self):
        """
        Where to mount this disk in the guest
        """
        return self._properties.get('mountpoint')

    @property
    def fstype(self):
        """
        Filesystemi this disk (ext4, swap...) will hold
        """
        return self._properties.get('fstype')

    @property
    def alias(self):
        """
        Short name for this disk
        """
        return self._alias

    @property
    def number(self):
        """
        Disk number, assumes alias is numbered (f.e. disk0, disk1, etc.)
        """
        return re.match(r'^.*?([0-9]+)$', self._alias).groups()[0]

    @property
    def capacity(self):
        """
        Disk capacity in bytes
        """
        return str(int(self._properties.get('capacity')) * 1073741824)

    @property
    def name(self):
        """
        Full disk name, including qcow2 suffix
        """
        return '%s.qcow2' % self._name

    @property
    def path(self):
        """
        Path to backing volume file of this disk
        """
        return self._path

    @property
    def pool(self):
        """
        Name of this disks storage pool
        """
        return self._properties.get('pool')

    @property
    def target(self):
        """
        Target (guest) device name for this disk (vda, vdb, vdc...)
        """
        return self._properties.get('target')

    @property
    def xml(self):
        """
        ElementTree XML object of this disk
        """
        return self._xml


class LibvirtNetwork:
    """
    Libvirt Network device object
    """

    def __init__(self, name, **kwargs):
        """
        Build XML representation

        :param name - Short name of this network device (eth0, eth1, ...)
        """
        try:
            self._ipv4 = kwargs.get('ipv4')
        except KeyError:
            self._ipv4 = None
        try:
            self._ipv6 = kwargs.get('ipv6')
        except KeyError:
            self._ipv6 = None

        self._name = name
        self._vlan = kwargs.get('vlan')
        self._bridge = kwargs.get('bridge')
        self._xml = ElementTree.Element('interface')
        self._xml.attrib['type'] = 'bridge'
        source_element = ElementTree.Element('source')
        source_element.attrib['bridge'] = self._bridge
        self._xml.append(source_element)
        if self.vlan:
            vlan_element = ElementTree.Element('vlan')
            tag_element = ElementTree.Element('tag')
            tag_element.attrib['id'] = str(self.vlan)
            vlan_element.append(tag_element)
            self._xml.append(vlan_element)
        virtualport_element = ElementTree.Element('virtualport')
        virtualport_element.attrib['type'] = 'openvswitch'
        self._xml.append(virtualport_element)
        model_element = ElementTree.Element('model')
        model_element.attrib['type'] = 'virtio'
        self._xml.append(model_element)
        alias_element = ElementTree.Element('alias')
        alias_element.attrib['name'] = 'virtio-%s' % name
        self._xml.append(alias_element)

    def __str__(self):
        """
        Return a pretty formatted XML
        """
        reparsed = xml.dom.minidom.parseString(
            ElementTree.tostring(self._xml, encoding='unicode')
        )
        return reparsed.toprettyxml(indent="  ").strip()

    @property
    def name(self):
        """
        Name of this network device (eth0, eth1, ...)
        """
        return self._name

    @property
    def netctl(self):
        """
        Netctl configuration representation of this network device

        (returns a list, each element representing a line)
        """
        config = list()
        config.append('Description=%s Network' % self.name)
        config.append('Interface=%s' % self.name)
        config.append('Connection=ethernet')
        if self.ipv4_address:
            config.append('IP=static')
            config.append("Address=('%s')" % self.ipv4_address.with_prefixlen)
            if self.ipv4_gateway:
                config.append("Gateway='%s'" % str(self.ipv4_gateway))
        else:
            config.append('IP=no')

        if self.ipv6_address:
            config.append('IP6=static')
            config.append("Address6=('%s')" % self.ipv6_address.with_prefixlen)
            if self.ipv6_gateway:
                config.append("Gateway6='%s'" % str(self.ipv6_gateway))
        else:
            config.append('IP6=no')

        if self.dns:
            dns = []
            for server in self.dns:
                dns.append("'%s'" % str(server))
            config.append('DNS=(%s)' % " ".join(dns))
        return config

    @property
    def dns(self):
        """
        DNS servers configured for this network (returns a list)
        """
        dns = []
        for server in self._ipv4.get('dns', []):
            dns.append(ipaddress.ip_address(server))
        for server in self._ipv6.get('dns', []):
            dns.append(ipaddress.ip_address(server))
        return dns

    @property
    def ipv4_address(self):
        """
        IPv4 address for this interface
        """
        try:
            return ipaddress.ip_interface(self._ipv4['address'])
        except (KeyError, ValueError):
            return None

    @property
    def ipv4_gateway(self):
        """
        IPv4 default gateway for this interface
        """
        try:
            return ipaddress.ip_address(self._ipv4['gateway'])
        except (KeyError, ValueError):
            return None

    @property
    def ipv6_address(self):
        """
        IPv6 address for this interface
        """
        try:
            return ipaddress.ip_interface(self._ipv6['address'])
        except (KeyError, ValueError):
            return None

    @property
    def ipv6_gateway(self):
        """
        IPv6 default gateway for this interface
        """
        try:
            return ipaddress.ip_address(self._ipv6['gateway'])
        except (KeyError, ValueError):
            return None

    @property
    def bridge(self):
        """
        Bridge, this interface will be a member of
        """
        return self._bridge

    @property
    def vlan(self):
        """
        VLAN tag used on the bridge of this interface
        """
        return self._vlan

    @property
    def xml(self):
        """
        XML representation of this network device
        """
        return self._xml


class LibvirtDomain:
    """
    Libvirt Domain object
    """

    def __init__(self, name):
        """
        Initialize domain, including default hardware and behaviour

        :param name - FQDN of domain
        """
        self._xml = ElementTree.Element('domain')
        self._xml.attrib['type'] = 'kvm'
        self.name = name
        self._set_default_behaviour()
        self._set_default_hardware()

    def __str__(self):
        """
        Pretty formatted XML representation of this domain
        """
        reparsed = xml.dom.minidom.parseString(
            ElementTree.tostring(self._xml, encoding='unicode')
        )
        return reparsed.toprettyxml(indent="  ").strip()

    def _set_default_behaviour(self):
        """
        Setup behaviour on start, stop and reboot.
        """
        poweroff_element = ElementTree.Element('on_poweroff')
        poweroff_element.text = 'destroy'
        self._xml.append(poweroff_element)
        reboot_element = ElementTree.Element('on_reboot')
        reboot_element.text = 'restart'
        self._xml.append(reboot_element)
        crash_element = ElementTree.Element('on_crash')
        crash_element.text = 'destroy'
        self._xml.append(crash_element)

    def _set_default_hardware(self):
        """
        Setup default hardware, such as clock, display, memory etc.
        """
        self._set_clock()
        self._set_features()
        self._set_memory_backing()
        self._set_os()
        self._set_resource_partition()
        self._set_devices()

    def _set_clock(self):
        """
        Setup clock device
        """
        clock_element = ElementTree.Element('clock')
        clock_element.attrib['offset'] = 'utc'
        self._xml.append(clock_element)

    def _set_devices(self):
        """
        Setup default devices, such as emulator, console and input devices
        """
        devices_element = ElementTree.Element('devices')
        emulator_element = ElementTree.Element('emulator')
        emulator_element.text = '/usr/bin/qemu-system-x86_64'
        devices_element.append(emulator_element)
        devices_element.append(self.__prepare_serial_devices())
        devices_element.append(self.__prepare_console_devices())
        keyboard_element = ElementTree.Element('input')
        keyboard_element.attrib['type'] = 'keyboard'
        keyboard_element.attrib['bus'] = 'ps2'
        devices_element.append(keyboard_element)
        mouse_element = ElementTree.Element('input')
        mouse_element.attrib['type'] = 'mouse'
        mouse_element.attrib['bus'] = 'ps2'
        devices_element.append(mouse_element)
        devices_element.append(self.__prepare_graphics_devices())
        devices_element.append(self.__prepare_video_devices())
        devices_element.append(self.__prepare_memballoon_devices())
        self._xml.append(devices_element)

    @staticmethod
    def __prepare_console_devices():
        """
        Prepare console devices
        """
        console_element = ElementTree.Element('console')
        console_element.attrib['type'] = 'pty'
        console_element.attrib['tty'] = '/dev/pts/10'
        source_element = ElementTree.Element('source')
        source_element.attrib['path'] = '/dev/pts/10'
        console_element.append(source_element)
        target_element = ElementTree.Element('target')
        target_element.attrib['type'] = 'serial'
        target_element.attrib['port'] = str(0)
        console_element.append(target_element)
        alias_element = ElementTree.Element('alias')
        alias_element.attrib['name'] = 'serial0'
        console_element.append(alias_element)
        return console_element

    @staticmethod
    def __prepare_graphics_devices():
        """
        Prepare graphic devices.

        Sets up graphics and spice server for graphical console in libvirt
        """
        graphics_element = ElementTree.Element('graphics')
        graphics_element.attrib['type'] = 'spice'
        graphics_element.attrib['port'] = '5900'
        graphics_element.attrib['autoport'] = 'yes'
        graphics_element.attrib['listen'] = '127.0.0.1'
        listen_element = ElementTree.Element('listen')
        listen_element.attrib['type'] = 'address'
        listen_element.attrib['address'] = '127.0.0.1'
        graphics_element.append(listen_element)
        return graphics_element

    @staticmethod
    def __prepare_memballoon_devices():
        """
        Setup memory balloning device
        """
        memballoon_element = ElementTree.Element('memballoon')
        memballoon_element.attrib['model'] = 'virtio'
        alias_element = ElementTree.Element('alias')
        alias_element.attrib['name'] = 'balloon0'
        memballoon_element.append(alias_element)
        return memballoon_element

    @staticmethod
    def __prepare_serial_devices():
        """
        Setup serial devices
        """
        serial_element = ElementTree.Element('serial')
        serial_element.attrib['type'] = 'pty'
        source_element = ElementTree.Element('source')
        source_element.attrib['path'] = '/dev/pts/10'
        serial_element.append(source_element)
        target_element = ElementTree.Element('target')
        target_element.attrib['port'] = str(0)
        serial_element.append(target_element)
        alias_element = ElementTree.Element('alias')
        alias_element.attrib['name'] = 'serial0'
        serial_element.append(alias_element)
        return serial_element

    @staticmethod
    def __prepare_video_devices():
        """
        Setup virtualized graphic card
        """
        video_element = ElementTree.Element('video')
        model_element = ElementTree.Element('model')
        model_element.attrib['type'] = 'cirrus'
        model_element.attrib['vram'] = '16384'
        model_element.attrib['heads'] = '1'
        video_element.append(model_element)
        alias_element = ElementTree.Element('alias')
        alias_element.attrib['name'] = 'video0'
        video_element.append(alias_element)
        return video_element

    def _set_features(self):
        """
        Setup machine features such as ACPI and PAE
        """
        features_element = ElementTree.Element('features')
        acpi_element = ElementTree.Element('acpi')
        apic_element = ElementTree.Element('apic')
        pae_element = ElementTree.Element('pae')
        features_element.append(acpi_element)
        features_element.append(apic_element)
        features_element.append(pae_element)
        self._xml.append(features_element)

    def _set_memory_backing(self):
        """
        Setup hugepages memory backend, for improved performance
        """
        memorybacking_element = ElementTree.Element('memoryBacking')
        hugepages_element = ElementTree.Element('hugepages')
        memorybacking_element.append(hugepages_element)
        self._xml.append(memorybacking_element)

    def _set_os(self, arch='x86_64'):
        """
        Set OS/architecture specific configuration
        """
        os_element = ElementTree.Element('os')
        type_element = ElementTree.Element('type')
        type_element.attrib['arch'] = arch
        type_element.attrib['machine'] = 'pc-i440fx-2.3'
        type_element.text = 'hvm'
        os_element.append(type_element)
        boot_element = ElementTree.Element('boot')
        boot_element.attrib['dev'] = 'hd'
        os_element.append(boot_element)
        self._xml.append(os_element)

    def _set_resource_partition(self):
        """
        Setup default resource partitioning
        """
        resource_element = ElementTree.Element('resource')
        partition_element = ElementTree.Element('partition')
        partition_element.text = '/machine'
        resource_element.append(partition_element)
        self._xml.append(resource_element)

    def add_device(self, device_xml):
        """
        Add additional device to this libvirt domain.

        :param device_xml - XML of device to add
        """
        devices_node = self._xml.find('devices')
        devices_node.append(device_xml)

    @property
    def vcpu(self):
        """
        Number of virtual CPUs
        """
        return self._xml.find('vcpu').text

    @vcpu.setter
    def vcpu(self, value):
        """
        Number of virtual CPUs
        """
        vcpu_element = self._xml.find('vcpu')
        if isinstance(vcpu_element, ElementTree.Element):
            vcpu_element.text = str(value)
        else:
            vcpu_element = ElementTree.Element('vcpu')
            vcpu_element.attrib['placement'] = 'static'
            vcpu_element.text = str(value)
            self._xml.append(vcpu_element)

    @property
    def memory(self):
        """
        Memory in MegaBytes
        """
        return self._xml.find('memory').text

    @memory.setter
    def memory(self, value):
        """
        Memory in MegaBytes
        """
        memory_element = self._xml.find('memory')
        if isinstance(memory_element, ElementTree.Element):
            memory_element.text = str(int(value) * 1024)
        else:
            memory_element = ElementTree.Element('memory')
            memory_element.attrib['unit'] = 'KiB'
            memory_element.text = str(int(value) * 1024)
            self._xml.append(memory_element)
        cmemory_element = self._xml.find('currentMemory')
        if isinstance(cmemory_element, ElementTree.Element):
            cmemory_element.text = str(int(value) * 1024)
        else:
            cmemory_element = ElementTree.Element('currentMemory')
            cmemory_element.attrib['unit'] = 'KiB'
            cmemory_element.text = str(int(value) * 1024)
            self._xml.append(cmemory_element)

    @property
    def name(self):
        """
        Name of libvirt domain
        """
        return self._xml.find('name').text

    @name.setter
    def name(self, value):
        """
        Name of libvirt domain
        """
        name_element = self._xml.find('name')
        if isinstance(name_element, ElementTree.Element):
            name_element.text = value
        else:
            name_element = ElementTree.Element('name')
            name_element.text = value
            self._xml.append(name_element)


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
            self._conn.close()

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


class Provision:
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
    def _runcmd(cmds, output=False, failhard=True, **kwargs):
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
            if not rval == 0:
                if failhard:
                    raise RuntimeError('Command %s failed' % " ".join(cmds))
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
        pass


class ArchProvision(Provision):
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
                    os.mkdir(mountpoint)
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
        addresses = []
        for network in self.domain.networks:
            if network.ipv4_address:
                addresses.append(network.ipv4_address.ip)
            if network.ipv6_address:
                addresses.append(network.ipv6_address.ip)
            self.writetargetfile(
                '/etc/netctl/%s' % network.name,
                network.netctl
            )
            self.runchroot([
                'netctl',
                'enable',
                network.name
            ])

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
                        "UUID=%s %s ext4 rw,relatime,data=ordered 0 %d" %(
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
            '/dev/nbd0'
        ])
        self.runchroot([
            'grub-mkconfig',
            '-o',
            '/boot/grub/grub.cfg'
        ])
        #With nbd devices, grub-mkconfig does not use the UUID/LABEL
        #So change it in the resulting file
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
        provisioner = ArchProvision(domain, proxy=proxy)
        provisioner.cleanup()
        domain.autostart(True)
        domain.start()
        os.rmdir(args.mountpoint)
    elif domain.guesttype == 'plain':
        provisioner = Provision
        domain.autostart(True)
    else:
        raise RuntimeError('Unsupported guest type: %s' % domain.guesttype)

    domain.close()

if __name__ == '__main__':
    main()
