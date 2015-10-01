installation
============

install libvirt/qemu
--------------------

install libvirt and qemu packages::

    pacman -S qemu libvirt openbsd-netcat
    systemctl enable libvirtd.service
    systemctl start libvirtd.service


configure hugepages
-------------------

configure kernel huge pages, that are later used as memory backend for
libvirt.

See https://wiki.archlinux.org/index.php/KVM#Enabling_huge_pages

the following example will configure ~28.5G hugepages, which seems to be a
good default for a system with 32G RAM::

    # remount huge pages with permissions for KVM (gid=78)
    cat >> /etc/fstab << EOF
    hugetlbfs       /dev/hugepages  hugetlbfs       mode=1770,gid=78        0 0
    EOF
    umount /dev/hugepages
    mount /dev/hugepages

    # 28.5 G if hugepagesize = 2048k (grep Hugepagesize /proc/meminfo)
    echo 14592 > /proc/sys/vm/nr_hugepages
    cat > /etc/sysctl.d/40-hugepages.conf << EOF
    vm.nr_hugepages = 14592
    EOF


configure storage pool
----------------------

setup a storage pool where the vm images can be stored in::

    mkdir /srv/kvm/hdd
    virsh pool-define-as hdd dir --target /srv/kvm/hdd
    virsh pool-start hdd
    virsh pool-autostart hdd


configure openvswitch
---------------------

openvswitch is a virtual switch that makes it easy to later assign different
networks/vlans to the individual virtual machines::

    pacman -S openvswitch
    cat > /etc/netctl/ovs << EOF
    Description="Open vSwitch"
    Interface=ovs0
    Connection=openvswitch
    BindsToInterfaces=(enp2s0)
    IP=static
    Address=('192.0.2.100/24')
    Gateway='192.0.2.1'
    DNS=('203.0.113.1')
    IP6=static
    Address6=('2001:db8:1234::100/64')
    Gateway6='2001:db8:1234::1'
    EOF
    netctl start ovs
    netctl enable ovs
    cat > /tmp/ovsnet.xml << EOF
    <network>
      <name>ovs0</name>
      <forward mode='bridge'/>
      <bridge name='ovs0'/>
      <virtualport type='openvswitch'/>
    </network>
    EOF
    virsh net-define /tmp/ovsnet.xml
    virsh net-start ovs0
    virsh net-autostart ovs0
    rm /tmp/ovsnet.xml


configure nbd
-------------

in order to be able to mount qcow2 files as block devices including partitions,
ndb needs to setup correctly::

    cat > /etc/modprobe.d/nbd.conf << EOF
    options nbd max_part=32
    EOF
    cat > /etc/modules-load.d/nbd.conf << EOF
    nbd
    EOF
    modprobe nbd


install archvyrt
----------------

install the archvyrt package with it's dependencies::

    yaourt -S archvyrt
