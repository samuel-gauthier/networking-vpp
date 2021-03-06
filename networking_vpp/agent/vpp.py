# Copyright (c) 2016 Cisco Systems, Inc.
# All Rights Reserved
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


import grp
import os
import pwd
import vpp_papi
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


def mac_to_bytes(mac):
    return str(''.join(chr(int(x, base=16)) for x in mac.split(':')))


def fix_string(s):
    return s.rstrip("\0").decode(encoding='ascii')


def _vpp_cb(*args, **kwargs):
    # sw_interface_set_flags comes back when you delete interfaces
    # print 'callback:', args, kwargs
    pass


def _check_retval(t):
    try:
        print("checking return value for object: %s" % str(t))
        if t.retval != 0:
            print ('FAIL? retval here is %s' % t.retval)
    #        raise Exception('failed in backend')
    except AttributeError as e:
        print("Error: %s" % e)


# Sometimes a callback fires unexpectedly.  We need to catch them
# because vpp_papi will traceback otherwise
vpp_papi.register_event_callback(_vpp_cb)


class VPPInterface(object):

    def get_interfaces(self):
        t = vpp_papi.sw_interface_dump(0, b'ignored')

        for interface in t:
            if interface.vl_msg_id == vpp_papi.VL_API_SW_INTERFACE_DETAILS:
                yield (fix_string(interface.interface_name), interface)

    def get_interface(self, name):
        for (ifname, f) in self.get_interfaces():
            if ifname == name:
                return f

    def get_version(self):
        t = vpp_papi.show_version()

        _check_retval(t)

        return fix_string(t.version)

    ########################################

    def create_tap(self, ifname, mac):
        t = vpp_papi.tap_connect(False,  # random MAC
                                 ifname,
                                 mac_to_bytes(mac),
                                 False,  # renumber - who knows, no doc
                                 0)  # customdevinstance - who knows, no doc

        _check_retval(t)

        return t.sw_if_index  # will be -1 on failure (e.g. 'already exists')

    def delete_tap(self, idx):
        vpp_papi.tap_delete(idx)

        # Err, I just got a sw_interface_set_flags here, not a delete tap?
        # _check_retval(t)

    #############################

    def create_vhostuser(self, ifpath, mac):
        print ('Creating %s as a port' % ifpath)
        t = vpp_papi.create_vhost_user_if(True,  # is a server?
                                          str(ifpath),  # unicode not allowed.
                                          False,  # Who knows what renumber is?
                                          0,  # custom_dev_instance
                                          True,  # use custom MAC
                                          mac_to_bytes(mac)
                                          )
        #LOG.debug("Created vhost user interface object: %s" % str(t))
        print("Created vhost user interface object: %s" % str(t))
        _check_retval(t)

        # The permission that qemu runs as (TODO(ijw): should be
        # configurable)
        uid = pwd.getpwnam("libvirt-qemu").pw_uid
        gid = grp.getgrnam("libvirtd").gr_gid
        os.chown(ifpath, uid, gid)
        os.chmod(ifpath, 0o770)

        return t.sw_if_index

    def delete_vhostuser(self, idx):
        #LOG.debug("Deleting VPP interface - index: %s" % idx)
        print("Deleting VPP interface - index: %s" % idx)
        t = vpp_papi.delete_vhost_user_if(idx)

        _check_retval(t)

    ########################################

    def __init__(self):
        self.r = vpp_papi.connect("test_papi")

    def disconnect(self):
        vpp_papi.disconnect()

    def create_bridge_domain(self, id):
        t = vpp_papi.bridge_domain_add_del(
            id,  # the numeric ID of this domain
            True,  # enable bcast and mcast flooding
            True,  # enable unknown ucast flooding
            True,  # enable forwarding on all interfaces
            True,  # enable learning on all interfaces
            False,  # enable ARP termination in the BD
            True  # is an add
        )

        _check_retval(t)

    def create_vlan_subif(self, if_id, vlan_tag):
        print("Creating vlan subinterface with ID:%s and vlan_tag:%s" % (if_id, vlan_tag))
        t = vpp_papi.create_vlan_subif(
            if_id,
            vlan_tag)
        print("Create vlan subinterface response: %s" % str(t))

        _check_retval(t)

        return t.sw_if_index

    def create_srcrep_vxlan_subif(self, vrf_id, src_addr, bcast_addr, vnid):
        t = vpp_papi.vxlan_add_del_tunnel(
            true,  # is_add
            src_addr,
            bcast_addr,
            vrf_id,
            decap_next_index,   # what is this?
            vni)

        _check_retval(t)

        return t.sw_if_index
        
    
    ########################################

    def add_to_bridge(self, bridx, *ifidxes):
        for ifidx in ifidxes:
            t = vpp_papi.sw_interface_set_l2_bridge(
                ifidx, bridx,
                False,                  # BVI (no thanks)
                0,                      # shared horizon group
                True)                   # enable bridge mode
            _check_retval(t)

    def ifup(self, *ifidxes):
        for ifidx in ifidxes:
            vpp_papi.sw_interface_set_flags(
                ifidx,
                1, 1,               # admin and link up
                0)                   # err, I can set the delected flag?
