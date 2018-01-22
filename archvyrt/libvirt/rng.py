"""archvyrt libvirt rng module"""

# stdlib
import xml.etree.ElementTree as ElementTree
# archvyrt
from .xml import LibvirtXml


class LibvirtRng(LibvirtXml):
    """
    Libvirt Rng Device
    """

    def __init__(self, rng_bytes=2048):
        super().__init__()

        self._xml = ElementTree.Element('rng')
        self._xml.attrib['model'] = 'virtio'
        rate = ElementTree.Element('rate')
        rate.attrib['bytes'] = str(rng_bytes)
        rate.attrib['period'] = '1000'
        self._xml.append(rate)
        backend = ElementTree.Element('backend')
        backend.attrib['model'] = 'random'
        backend.text = '/dev/random'
        self._xml.append(backend)
