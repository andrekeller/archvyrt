use archvyrt
============

basic usage
-----------

to provision a virtual machine, run archvyrt with a vmdefinition json file::

    archvyrt vm.json


vmdefinition format
-------------------

example vmdefinition::

    {
      "hostname": "foobar",
      "fqdn": "foobar.example.org",
      "guesttype": "archlinux",
      "vcpu": "1",
      "memory": "1024",
      "disk": {
        "disk0": {
          "capacity": 20,
          "pool": hdd,
          "fstype": "ext4",
          "target": "vda",
        }
      },
      "networks": {
        "net0": {
          "ipv4": {
            "address": "192.0.2.200/24",
            "gateway": "192.0.2.1",
            "dns": [
              "203.0.113.1"
            ]
          },
          "ipv6": {
            "address": "2001:db8:1234::200/64",
            "gateway": "2001:db8:1234::1"
          },
          "bridge": "ovs0"
        }
      },
      "rng": {},
      "access":
        "ssh-keys":
          "user@example.org": {
            "type": "ssh-rsa",
            "key": "AAAA..."
          },
        }
      }
    }


basic vm parameters
^^^^^^^^^^^^^^^^^^^

hostname
""""""""

top-level key defining the hostname (without domain) of the vm::

    {
      "hostname": "foobar",
      ...


fqdn
""""

top-level key defining the fully-qualified domain name of the vm::

    {
      ...,
      "fqdn": "foobar.example.org",
      ...

used as identifier in libvirt and in the filenames of the virtual disks


guesttype
"""""""""

top-level key defining the provisioner used to create the vm::

    {
      ...,
      "guesttype": "archlinux",
      ...

currently supported types are archlinux and plain

* **archlinux**: Sets up a basic archlinux vm including network and disk config.
* **ubuntu**: Sets up a basic ubuntu LTS (16.04) vm including network and disk config.
* **plain**: Sets up an empty vm to manually install an operating system
  (f.e. using virt-manager)


vcpu
""""

top-level key defining the number of virtual cpu cores assigned to a vm::

    {
        ...,
        "vcpu": "1",
        ...
    
memory
""""""

top-level key defining the amount of ram assigned to a vm::

    {
        ...,
        "memory": "1024",
        ...

disk
""""

top-level object defining disks provisionend and assigned to a vm::

    {
      ...,
      "disk": {
        "disk0": {
          "capacity": 20,
          "pool": "hdd",
          "fstype": "ext4",
          "mountpoint": "/",
          "target": "vda",
        },
        "disk1": {
          "capacity": 2,
          "pool": "hdd",
          "fstype": "swap",
          "target": "vdb"
        }
      },
      ...

multiple disks may be defined as in the example above. use a distinct target,
supported fstypes currently are ``ext4`` and ``swap``.

rng
"""

top-level key defining wether an virtio-rng shall be attached to the vm::

    {
      ...,
      "rng": {
        "bytes": 2048
      },
      ...

This will add a virtio-rng seeded with max 2048 bytes per second from hosts
``/dev/random`` to the vm. The 2048 bytes are the default value, which may be
omitted.

**NOTE** Only add virtio-rng devices if you can ensure that your hosts entropy
pool is properly seeded (i.e. using a hardware rng).

networks
""""""""

top-level object defining network interfaces assigned to a vm::

    {
      ...,
      "networks": {
        "net0": {
          "ipv4": {
            "address": "192.0.2.200/24",
            "gateway": "192.0.2.1",
            "dns": [
              "203.0.113.1"
            ]
          },
          "ipv6": {
            "address": "2001:db8:1234::200/64",
            "gateway": "2001:db8:1234::1"
          },
          "vlan": "201",
          "bridge": "ovs0"
        },
        "net1": {
          "vlan": "202",
          "bridge": "ovs0"
        }
      },
      ...

multiple networks may be defined as in the example above. The only mandatory
key for a network is a ``bridge`` which needs to be an openvswitch bridge. If a
network does not include a ``vlan`` the interface is added to the bridge 
without a vlan tag.

the ``archlinux`` and ``ubuntu`` guesttypes will take into account the
``ipv4``/``ipv6`` keys and will configure network profiles for each defined
network.


access
""""""
top-level object configuring root-access for the ``archlinux`` and ``ubuntu``
guesttypes::

    {
      ...,
      "access": {
        "password": "$6$...",
        "ssh-keys": {
          "key-name": {
            "type": "ssh-rsa",
            "key": "AAA..."
          }
        }
      },
      ...

either or both ``password`` and ``ssh-keys`` may be specified. Multiple keys
are supported as well. ``password`` needs to be a valid crypt hash, compatible
with /etc/shadow format.
