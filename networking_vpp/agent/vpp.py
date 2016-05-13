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


import vpp_papi


def mac_to_bytes(mac):
    return ''.join(chr(int(x, base=16)) for x in mac.split(':'))


def fix_string(s):
    return s.rstrip("\0").decode(encoding='ascii')


def _vpp_cb(*args, **kwargs):
    # sw_interface_set_flags comes back when you delete interfaces
    # print 'callback:', args, kwargs
    pass


def _check_retval(t):
    if t.retval != 0:
        print ('FAIL? retval here is %s' % t.retval)
        raise Exception('failed in backend')


# Sometimes a callback fires unexpectedly.  We need to catch them
# because vpp_papi will traceback otherwise
vpp_papi.register_event_callback(_vpp_cb)


class VPPInterface(object):

    def get_interfaces(self):
        t = vpp_papi.sw_interface_dump(0, b'ignored')

        for interface in t:
            if interface.vlmsgid == vpp_papi.VL_API_SW_INTERFACE_DETAILS:
                yield (fix_string(interface.interfacename, interface))

    def get_interface(self, name):
        for f in self.get_interfaces():
            ifname = fix_string(f.interfacename)
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

        return t.swifindex  # will be -1 on failure (e.g. 'already exists')

    def delete_tap(self, idx):
        vpp_papi.tap_delete(idx)

        # Err, I just got a sw_interface_set_flags here, not a delete tap?
        # _check_retval(t)

    #############################

    def create_vhostuser(self, ifpath, mac):
        t = vpp_papi.create_vhost_user_if(True,  # is a server,
                                          ifpath,
                                          False,  # Who knows what renumber is?
                                          0,  # custom_dev_instance
                                          True,  # use custom MAC
                                          mac_to_bytes(mac)
                                          )

        _check_retval(t)

        return t.swifindex

    def delete_vhostuser(self, idx):
        t = vpp_papi.delete_vhost_user_if(idx)

        _check_retval(t)

    ########################################

    def __init__(self):
        self.r = vpp_papi.connect("test_papi")
        self._bd_next = 5678  # bridge domain number

    def disconnect(self):
        vpp_papi.disconnect()

    def create_bridge_domain(self):

        t = vpp_papi.bridge_domain_add_del(
            self._bd_next,  # the ID of this domain
            True,  # enable bcast and mcast flooding
            True,  # enable unknown ucast flooding
            True,  # enable forwarding on all interfaces
            True,  # enable learning on all interfaces
            False,  # enable ARP termination in the BD
            True  # is an add
        )

        _check_retval(t)

        self._bd_next += 1
        return self._bd_next - 1

    def create_vlan_subif(self, if_id, vlan_tag):
        t = vpp_papi.create_vlan_subif(
            if_id,
            vlan_tag)

        _check_retval(t)

        return t.swifindex

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