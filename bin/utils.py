
import os
import sys
import time
import hashlib
import datetime

from oslo_config import cfg
from conf.load_conf import CONF
from conf.load_conf import logging

from init_api import db
from bin.api_db.objects import pxeServer, remoteClient
from bin.api_db import utils as db_utils

LOG = logging.getLogger(__name__)

neutron_br_tun = CONF.neutron_br_tun
ovs_flow_rule_idle_timeout = CONF.ovs_flow_rule_idle_timeout
ovs_ethertype = "0x0800"
ovs_vxlan_local_ip = CONF.pxe_node_ip

tftp_dir = CONF.tftp_dir
dhcp_hostsfile_path = CONF.dhcp_hostsfile_path
#dhcp_range = CONF.dhcp_range
#dnsmasq_gateway_addr = CONF.dnsmasq_gateway_addr
#dnsmasq_dns_addr = CONF.dnsmasq_dns_addr
dhcp_netmask = CONF.dhcp_netmask

dnsmasq_log_path = CONF.dnsmasq_log_path
ovs_vswitchd_log_path = CONF.ovs_vswitchd_log_path
ovs_dbserver_log_path = CONF.ovs_dbserver_log_path

def check_br_tun():
    cmd = "ovs-vsctl show"
    res = os.popen(cmd).readlines()
    for line in res:
        if neutron_br_tun in line:
            return True
    return False

def add_br_tun():
    cmd = "ovs-vsctl --log-file=%s add-br %s" % (ovs_vswitchd_log_path, neutron_br_tun)
    os.system(cmd)

def check_ns(target):
    cmd = "ip netns show | grep %s" % target
    res = os.popen(cmd).readlines()
    if res is not None:
        for line in res:
            if (target + '\n') == line:
                return True
    return False

def add_pxe_ns(pxe_ns_name, pxe_port_name, pxe_port_mac, pxe_port_ip):
    pxe_port_ip = pxe_port_ip + "/" + dhcp_netmask

    cmd = "ovs-vsctl --log-file=%s add-port %s %s -- set Interface %s type=internal" \
    % (ovs_vswitchd_log_path, neutron_br_tun, pxe_port_name, pxe_port_name)
    os.system(cmd)
    cmd = "ip netns add %s" % pxe_ns_name
    os.system(cmd)
    cmd = "ip link set %s netns %s" % (pxe_port_name, pxe_ns_name)
    os.system(cmd)

    cmd = "ip netns exec %s ip addr add %s dev %s" % (pxe_ns_name, pxe_port_ip, pxe_port_name)
    os.system(cmd)
    cmd = "ip netns exec %s ip link set %s address %s" % (pxe_ns_name, pxe_port_name, pxe_port_mac)
    os.system(cmd)
    cmd = "ip netns exec %s ip link set %s up" % (pxe_ns_name, pxe_port_name)
    os.system(cmd)
    cmd = "ip netns exec %s ip link set lo up" % (pxe_ns_name)
    os.system(cmd)

def del_pxe_ns_port(pxe_ns_name, pxe_port_name):
    cmd = "ip netns delete %s" % pxe_ns_name
    os.system(cmd)

    cmd = "ovs-vsctl --log-file=%s del-port %s %s" % (ovs_vswitchd_log_path, neutron_br_tun, pxe_port_name)
    os.system(cmd)

def check_vtep_ip(ip):
    cmd = "ovs-vsctl show"
    res = os.popen(cmd).readlines()
    key_string = "remote_ip=\"%s\"" % (ip)
    for i in range(0, len(res)):
        # example : '                options: {in_key=flow, local_ip="192.168.16.9", out_key=flow, remote_ip="192.168.16.10"}\n'
        if key_string in res[i]:
            return True
    return False

def add_vxlan_tun(vxlan_port_name, vtep_ip):
    cmd = "ovs-vsctl --log-file=%s add-port %s %s -- set interface %s type=vxlan options:df_default=\'true\'" \
    % (ovs_vswitchd_log_path, neutron_br_tun, vxlan_port_name, vxlan_port_name)
    os.system(cmd)
    cmd = "ovs-vsctl --log-file=%s set interface %s options:in_key=flow" \
    % (ovs_vswitchd_log_path, vxlan_port_name)
    os.system(cmd)
    cmd = "ovs-vsctl --log-file=%s set interface %s options:out_key=flow" \
    % (ovs_vswitchd_log_path, vxlan_port_name)
    os.system(cmd)
    cmd = "ovs-vsctl --log-file=%s set interface %s options:local_ip=%s" \
    % (ovs_vswitchd_log_path, vxlan_port_name, ovs_vxlan_local_ip)
    os.system(cmd)
    cmd = "ovs-vsctl --log-file=%s set interface %s type=vxlan options:remote_ip=%s" \
    % (ovs_vswitchd_log_path, vxlan_port_name, vtep_ip)
    os.system(cmd)

def get_vtap_ip_port_name(ip):
    cmd = "ovs-vsctl show"
    res = os.popen(cmd).readlines()
    key_string = "remote_ip=\"%s\"" % (ip)
    for i in range(0, len(res)):
        # example : '                options: {in_key=flow, local_ip="192.168.16.9", out_key=flow, remote_ip="192.168.16.10"}\n'
        if key_string in res[i]:
            # example : '        Port "vx1"\n'
            port_name_line = res[i - 2]
            line_split = port_name_line.split("Port ")
            port_name_line = line_split[-1].split("\"")
            port_name = port_name_line[1]
            return "%s" % port_name
    return ""

def get_port_num(port_name):
    cmd = "ovs-ofctl show %s | grep '(%s)'" % (neutron_br_tun, port_name)
    res = os.popen(cmd).readlines()
    LOG.info("port name in get_port_num:\n%s" % port_name)
    LOG.info("grep result in get_port_num:\n%s" % res)
    if res != []:
        # grep exmaple [' 3(testDHCP): addr:00:00:00:00:00:00\n']
        res_split = res[0].split("(%s)" % port_name)
        port_num = "%d" % int(res_split[0])
        return "%s" % port_num
    return ""

def add_ovs_flow_rules_multicast(vni, pxe_port_num, vxlan_port_num):
    cmd = "ovs-ofctl dump-flows %s 'table=1,in_port=%s,dl_dst=01:00:00:00:00:00/01:00:00:00:00:00'" \
    % (neutron_br_tun, pxe_port_num)
    res = os.popen(cmd).readlines()
    LOG.info("flow rules in table 1 : %s" % res)
    if len(res) > 1:
        key_line = res[1]
        LOG.info("key_line: %s" % key_line)
        key_words = key_line.split("output:")
        key_words = key_words[1].split("\n")
        vxlan_port_num_set = key_words[0].split(',')
        if vxlan_port_num not in vxlan_port_num_set:
            vxlan_port_num_set.append(vxlan_port_num)
            multicast_vxlan_ports = '.'.join(vxlan_port_num_set)
            LOG.info("multicast_vxlan_ports: %s" % multicast_vxlan_ports)
            cmd = "ovs-ofctl mod-flow %s table=1,dl_dst=01:00:00:00:00:00/01:00:00:00:00:00,in_port=%s,idle_timeout=%s,actions=set_tunnel:%s,output:%s --log-file=%s" \
            % (neutron_br_tun, pxe_port_num, ovs_flow_rule_idle_timeout, vni, multicast_vxlan_ports, ovs_dbserver_log_path)
            LOG.info("mod multicast flow rlues: %s" % cmd)
            os.system(cmd)
    else:
        cmd = "ovs-ofctl add-flow %s table=1,dl_dst=01:00:00:00:00:00/01:00:00:00:00:00,in_port=%s,idle_timeout=%s,actions=set_tunnel:%s,output:%s --log-file=%s" \
        % (neutron_br_tun, pxe_port_num, ovs_flow_rule_idle_timeout, vni, vxlan_port_num, ovs_dbserver_log_path)
        LOG.info("add multicast flow rlues: %s" % cmd)
        os.system(cmd)

def add_ovs_flow_rules(mac, ip, vni, pxe_port_num, vxlan_port_num):
    # table logic follows:
    # table 0 seperate packets to table 1 (pxe->vxlan) and table 3 (vxlan->pxe)
    # table 1 macth flow with dl_dst nw_dst mac, action set_tunnel, outport 
    # table 3 macth flow with in_port tun_id, action set_tunnel, outport  
    cmd = "ovs-ofctl add-flow %s table=0,priority=1,in_port=%s,actions=\'resubmit(,1)\' --log-file=%s" \
    % (neutron_br_tun, pxe_port_num, ovs_dbserver_log_path)
    os.system(cmd)
    cmd = "ovs-ofctl add-flow %s table=0,priority=1,in_port=%s,actions=\'resubmit(,3)\' --log-file=%s" \
    % (neutron_br_tun, vxlan_port_num, ovs_dbserver_log_path)
    os.system(cmd)


    cmd = "ovs-ofctl add-flow %s table=1,priority=0,actions=drop --log-file=%s" \
    % (neutron_br_tun, ovs_dbserver_log_path)
    os.system(cmd)
    add_ovs_flow_rules_multicast(vni, pxe_port_num, vxlan_port_num)
    cmd = "ovs-ofctl add-flow %s table=1,dl_dst=%s,in_port=%s,idle_timeout=%s,actions=set_tunnel:%s,output:%s --log-file=%s" \
    % (neutron_br_tun, mac, pxe_port_num, ovs_flow_rule_idle_timeout, vni, vxlan_port_num, ovs_dbserver_log_path)
    os.system(cmd)
    cmd = "ovs-ofctl add-flow %s table=1,dl_type=%s,nw_dst=%s,in_port=%s,idle_timeout=%s,actions=set_tunnel:%s,output:%s --log-file=%s" \
    % (neutron_br_tun, ovs_ethertype, ip, pxe_port_num, ovs_flow_rule_idle_timeout, vni, vxlan_port_num, ovs_dbserver_log_path)
    os.system(cmd)

    cmd = "ovs-ofctl add-flow %s table=3,priority=0,actions=drop --log-file=%s" % (neutron_br_tun, ovs_dbserver_log_path)
    os.system(cmd)
    cmd = "ovs-ofctl add-flow %s table=3,priority=2,tun_id=%s,dl_src=%s,idle_timeout=%s,actions=output:%s --log-file=%s" \
    % (neutron_br_tun, vni, mac, ovs_flow_rule_idle_timeout, pxe_port_num, ovs_dbserver_log_path)
    os.system(cmd)
    

def is_port_flow_rules_empty(pxe_port_num):
    cmd = "ovs-ofctl dump-flows %s \"table=1,in_port=%s\" --log-file=%s" % (neutron_br_tun, pxe_port_num, ovs_dbserver_log_path)
    res = os.popen(cmd).readlines()
    LOG.info("flow rules in table 1 : %s" % res)
    # lines should only contain the caption and the multicast flow rule
    if len(res) > 2:
        return False
    else:
        return True

def del_ovs_flow_rules(api_res, mac, ip, vni, vtep_ip, subnet_id, pxe_port_num, vxlan_port_num):
    cmd = "ovs-ofctl del-flows %s \"table=1,dl_dst=%s,in_port=%s\" --log-file=%s" % (neutron_br_tun, mac, pxe_port_num, ovs_dbserver_log_path)
    os.system(cmd)
    cmd = "ovs-ofctl del-flows %s \"table=1,nw_dst=%s,in_port=%s\" --log-file=%s" % (neutron_br_tun, ip, pxe_port_num, ovs_dbserver_log_path)
    os.system(cmd)
    cmd = "ovs-ofctl del-flows %s \"table=3,tun_id=%s,dl_src=%s\" --log-file=%s" % (neutron_br_tun, vni, mac, ovs_dbserver_log_path)
    os.system(cmd)

    db_utils.del_db_remote_client(ip)
    api_res[0]['del_ovs_flow_rules'] = 'done' 
    if is_port_flow_rules_empty(pxe_port_num):
        cmd = "ovs-ofctl del-flows %s \"table=1,in_port=%s\" --log-file=%s" % (neutron_br_tun, pxe_port_num, ovs_dbserver_log_path)
        os.system(cmd)
        cmd = "ovs-ofctl del-flows %s \"table=0,in_port=%s\" --log-file=%s" % (neutron_br_tun, pxe_port_num, ovs_dbserver_log_path)
        os.system(cmd)

        pxe_id = subnet_id[:10]
        pxe_ns_name = "pxe_ns_%s" % pxe_id
        pxe_port_name = "pxe_port_%s" % pxe_id
        pxe_port_name = pxe_port_name[:15]
        del_pxe_ns_port(pxe_ns_name, pxe_port_name)
        stop_tftp_dhcp(pxe_ns_name)

        db_utils.del_db_pxe_server(subnet_id)
        api_res[0]['del_namespace'] = 'done' 

    return api_res

def get_dnsmasq_pid(pxe_network_namespace):
    cmd = "ps aux | grep dnsmasq"
    res = os.popen(cmd).readlines()
    dnsmasq_id = pxe_network_namespace + "_id"
    for line in res:
        # 'nobody   16249  0.0  0.0  12900   484 ?        S    10:03   0:00 dnsmasq --port=0 --enable-tftp --tftp-root=/var/lib/tftp --except-interface=pxe_ns_ee33d0d8\n'
        if dnsmasq_id in line:
            line_split = line.split()
            pid = line_split[1]
            return pid
    LOG.exception("Failed to get pid of dnsmasq in pxe namespace %s." % pxe_network_namespace)

def start_tftp_dhcp(pxe_network_namespace, pxe_port_ip):
    cmd = "mkdir %s" % tftp_dir
    os.system(cmd)
    dnsmasq_id = pxe_network_namespace + "_id"
    dhcp_hostsfile_ns_id_path = dhcp_hostsfile_path + "_" + dnsmasq_id
    cmd = "touch %s" % dhcp_hostsfile_ns_id_path
    os.system(cmd)
    pxe_dnsmasq_log_path = dnsmasq_log_path + pxe_network_namespace + ".log"
    cmd = "touch %s" % pxe_dnsmasq_log_path
    os.system(cmd)
    dhcp_listen_address = "%s,127.0.0.1" % pxe_port_ip
    
    # ues --except-interface= as the tftp server id that is started by pxe_network_namespace
    cmd = "ip netns exec %s dnsmasq \
    --port=0\
    --dhcp-hostsfile=%s \
    --listen-address=%s \
    --dhcp-range=%s\
    --enable-tftp\
    --tftp-root=%s\
    --tftp-no-blocksize\
    --log-queries\
    --log-facility=%s\
    --log-dhcp\
    --dhcp-option-force=option:router,%s\
    --dhcp-option-force=option:dns-server,%s\
    --dhcp-option=vendor:PXEClient,6,2b\
    --dhcp-no-override\
    --dhcp-boot=pxelinux.0,pxeserver,%s\
    --dhcp-option-force=66,%s\
    --pxe-service=x86PC,'Boot from network',pxelinux\
    " % (pxe_network_namespace, dhcp_hostsfile_ns_id_path, dhcp_listen_address, CONF.dhcp_range, tftp_dir, pxe_dnsmasq_log_path, CONF.dnsmasq_gateway_addr, CONF.dnsmasq_dns_addr, pxe_port_ip, pxe_port_ip)
    os.system(cmd)

def add_dhcpHost(pxe_network_namespace, mac, ip):
    dnsmasq_pid = get_dnsmasq_pid(pxe_network_namespace)
    dnsmasq_id = pxe_network_namespace + "_id"
    dhcp_hostsfile_ns_id_path = dhcp_hostsfile_path + "_" + dnsmasq_id
    record_buffer = ""
    with open(dhcp_hostsfile_ns_id_path, 'r+') as f:
        mac_exist = False
        for line in f.readlines():
            if ip in line:
                return 
            elif mac in line:
                mac_exist = True
                line = "%s, %s\n" % (mac, ip)
            record_buffer += line 
    
        if mac_exist is False:
            record_buffer += "%s, %s\n" % (mac, ip)
    
    with open(dhcp_hostsfile_ns_id_path, 'w') as f:
        f.writelines(record_buffer)
    
    time.sleep(0.01)
    cmd = "kill -HUP %s" % dnsmasq_pid
    os.system(cmd)

def stop_tftp_dhcp(pxe_network_namespace):
    dnsmasq_pid = get_dnsmasq_pid(pxe_network_namespace)
    cmd = "kill %s" % dnsmasq_pid
    os.system(cmd)

    dnsmasq_id = pxe_network_namespace + "_id"
    dhcp_hostsfile_ns_id_path = dhcp_hostsfile_path + "_" + dnsmasq_id
    cmd = "rm %s" % dhcp_hostsfile_ns_id_path
    os.system(cmd)

def encrypt_string(input):
    input_md5 = hashlib.md5(input)
    # here seems the length of ovs_port_name should be less than 16
    # we assumes 10bits in md5 can avoid the conflict
    sub_string_md5 = input_md5.hexdigest()[12:-12]
    return sub_string_md5

