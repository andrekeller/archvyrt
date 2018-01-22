"""archvyrt libvirt device module"""

import xml.etree.ElementTree as ElementTree
import xml.dom.minidom


class LibvirtXml:
    """Libvirt device"""

    def __init__(self):
        self._xml = ElementTree.Element('root')

    @staticmethod
    def format_xml(et_xml):
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
        return self.format_xml(self.xml)

    @property
    def xml(self):
        """
        XML representation of this network device
        """
        return self._xml

    @xml.setter
    def xml(self, value):
        """
        Update XML for interface
        """
        if isinstance(value, str):
            self._xml = ElementTree.fromstring(value)
        elif isinstance(value, ElementTree.Element):
            self._xml = value
        else:
            raise TypeError('Expected str or ElementTree got %s' % type(value))
