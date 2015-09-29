import ipaddress
import logging
import xml.etree.ElementTree as ElementTree
import xml.dom.minidom

LOG = logging.getLogger('archvyrt')


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
        config.append('Description="%s network"' % self.name)
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
        try:
            for server in self._ipv4.get('dns', []):
                dns.append(ipaddress.ip_address(server))
            for server in self._ipv6.get('dns', []):
                dns.append(ipaddress.ip_address(server))
        except AttributeError:
            pass
        return dns

    @property
    def ipv4_address(self):
        """
        IPv4 address for this interface
        """
        try:
            return ipaddress.ip_interface(self._ipv4['address'])
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def ipv4_gateway(self):
        """
        IPv4 default gateway for this interface
        """
        try:
            return ipaddress.ip_address(self._ipv4['gateway'])
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def ipv6_address(self):
        """
        IPv6 address for this interface
        """
        try:
            return ipaddress.ip_interface(self._ipv6['address'])
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def ipv6_gateway(self):
        """
        IPv6 default gateway for this interface
        """
        try:
            return ipaddress.ip_address(self._ipv6['gateway'])
        except (KeyError, ValueError, TypeError):
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
    def mac(self):
        """
        MAC address of this interface
        """
        try:
            return self.xml.find('mac').attrib['address']
        except (KeyError, TypeError):
            return None

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
        self._xml = value
