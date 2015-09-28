import libvirt
import logging
import re
import xml.etree.ElementTree as ElementTree
import xml.dom.minidom

LOG = logging.getLogger('archvyrt')


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
