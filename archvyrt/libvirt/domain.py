import logging
import xml.etree.ElementTree as ElementTree
import xml.dom.minidom

LOG = logging.getLogger('archvyrt')


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

    @property
    def xml(self):
        return self._xml

    @xml.setter
    def xml(self, value):
        self._xml = ElementTree.fromstring(value)

