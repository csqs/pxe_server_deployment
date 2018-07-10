
import os
import sys
import json
import random
import hashlib
from random import randrange

from oslo_config import cfg
from oslo_log import log as logging
from conf.load_conf import CONF

from api_db.objects import pxeServer, remoteClient
from init_api import db

LOG = logging.getLogger(__name__)

neutron_br_tun = CONF.neutron_br_tun

def check_br_tun():
    cmd = "ovs-vsctl show"
    res = os.popen(cmd).readlines()
    for line in res:
        if neutron_br_tun in line:
            return "done"
    return "undone"

def check_ns(subnet_id):
    pxe_id = subnet_id[:10]
    pxe_ns_name = "pxe_ns_%s" % pxe_id

    cmd = "ip netns show | grep %s" % pxe_ns_name
    res = os.popen(cmd).readlines()
    if res is not None:
        for line in res:
            if (pxe_ns_name + '\n') == line:
                return "done"
    return "undone"

def check_ns_ip(subnet_id, pxe_port_ip):
    pxe_id = subnet_id[:10]
    pxe_ns_name = "pxe_ns_%s" % pxe_id
    cmd = "ip netns exec %s ifconfig" % pxe_ns_name
    res = os.popen(cmd).readlines()
    for line in res:
        if pxe_port_ip in line:
            return "done"
    return "undone"

def check_pxe_port(subnet_id):
    pxe_id = subnet_id[:10]
    pxe_port_name = "pxe_port_%s" % pxe_id
    pxe_port_name = pxe_port_name[:15]
    cmd = "ovs-vsctl show"
    res = os.popen(cmd).readlines()
    for line in res:
        if pxe_port_name in line:
            return "done"
    return "undone"

def check_vtep_ip(ip):
    cmd = "ovs-vsctl show"
    res = os.popen(cmd).readlines()
    key_string = "remote_ip=\"%s\"" % (ip)
    for i in range(0, len(res)):
        # example : '                options: {in_key=flow, local_ip="192.168.16.9", out_key=flow, remote_ip="192.168.16.10"}\n'
        if key_string in res[i]:
            return "done"
    return "undone"

def get_port_num(port_name):
    cmd = "ovs-ofctl show %s | grep '(%s)'" % (neutron_br_tun, port_name)
    res = os.popen(cmd).readlines()
    # print port_name
    # print res
    if res != []:
        # grep exmaple [' 3(testDHCP): addr:00:00:00:00:00:00\n']
        res_split = res[0].split("(%s)" % port_name)
        port_num = "%d" % int(res_split[0])
        return "%s" % port_num
    return ""

def encrypt_string(input):
    input_md5 = hashlib.md5(input)
    # here seems the length of ovs_port_name should be less than 16
    # we assumes 10bits in md5 can avoid the conflict
    sub_string_md5 = input_md5.hexdigest()[12:-12]
    return sub_string_md5

def check_ovs_flow_rules(mac, ip, vni, vtep_ip, subnet_id):
    pxe_id = subnet_id[:10]
    pxe_port_name = "pxe_port_%s" % pxe_id
    pxe_port_name = pxe_port_name[:15]

    vxlan_tap_id = encrypt_string(vtep_ip)
    vxlan_port_name = "vx-%s" % vxlan_tap_id
    vxlan_port_name = vxlan_port_name[:15]

    pxe_port_num = get_port_num(pxe_port_name)
    vxlan_port_num = get_port_num(vxlan_port_name)

    if pxe_port_num is "" or vxlan_port_num is "":
        return "undone"

    cmd = "ovs-ofctl dump-flows %s \"table=0,in_port=%s\"" % (neutron_br_tun, pxe_port_num)
    res = os.popen(cmd).readlines()
    if len(res) < 1:
        return "undone"

    cmd = "ovs-ofctl dump-flows %s \"table=0,in_port=%s\"" % (neutron_br_tun, vxlan_port_num)
    res = os.popen(cmd).readlines()
    if len(res) < 1:
        return "undone"

    cmd = "ovs-ofctl dump-flows %s \"table=1,dl_dst=%s,in_port=%s\"" % (neutron_br_tun, mac, pxe_port_num)
    res = os.popen(cmd).readlines()
    if len(res) < 1:
        return "undone"

    cmd = "ovs-ofctl dump-flows %s \"table=1,nw_dst=%s,in_port=%s\"" % (neutron_br_tun, ip, pxe_port_num)
    res = os.popen(cmd).readlines()
    if len(res) < 1:
        return "undone"

    cmd = "ovs-ofctl dump-flows %s \"table=3,tun_id=%s,dl_src=%s\"" % (neutron_br_tun, vni, mac)
    res = os.popen(cmd).readlines()
    if len(res) < 1:
        return "undone"

    return "done"

def check_dnsmasq(subnet_id):
    pxe_id = subnet_id[:10]
    pxe_ns_name = "pxe_ns_%s" % pxe_id
    dnsmasq_id = pxe_ns_name + "_id"
    
    cmd = "ps aux | grep dnsmasq"
    res = os.popen(cmd).readlines()
    for line in res:
        if pxe_ns_name in line:
            return "done"
    return "undone"

def gene_rand_num_in_1000():
    num = random.random()
    num = num * 1000
    return int(num)

def gene_rand_mac():
    maclist = []
    for i in range(1, 7):
        rand_str = "".join(random.sample("0123456789abcdef", 2))
        maclist.append(rand_str)
    rand_mac = ":".join(maclist)
    return  rand_mac

def genr_rand_ip():
    iplist = []
    for i in range(1, 5):
        # here the ip range may cause the failure of creating ovs vxlan port
        ip_str = "%d" % randrange(0, 192, 1)
        iplist.append(ip_str)
    rand_ip = ".".join(iplist)
    return  rand_ip

def check_db_conf():
    db.create_all(bind = "pxe_server")
    all_pxe_servers =  pxeServer.query.all()
    check_res = {}
    pxe_server_num = 0
    pxe_server_fail_num = 0
    remote_client_num = 0
    remote_client_fail_num = 0
    for pxe_server in all_pxe_servers:
        clients = []
        all_remote_clients = remoteClient.query.filter_by(subnet_id = pxe_server.subnet_id).order_by(remoteClient.add_time).all()
        for remote_client in all_remote_clients:
            remote_client_conf = {
                "vxlan_port" : check_vtep_ip(remote_client.vtep_ip),
                "ovs_flow_rules" : check_ovs_flow_rules(remote_client.mac, remote_client.ip, remote_client.vni, remote_client.vtep_ip, remote_client.subnet_id)
            }

            remote_client_num = remote_client_num + 1
            if remote_client_conf["vxlan_port"] is "undone" or remote_client_conf["ovs_flow_rules"] is "undone":
                remote_client_fail_num = remote_client_fail_num + 1

            clients.append(remote_client_conf)
        pxe_server_conf = [{
            "pxe_namespace" : check_ns(pxe_server.subnet_id),
            "pxe_namespace_ip" : check_ns_ip(pxe_server.subnet_id, pxe_server.port_ip),
            "pxe_port" : check_pxe_port(pxe_server.subnet_id),
            "dnsmasq" : check_dnsmasq(pxe_server.subnet_id),
            "remote_clients_conf": clients
        }]

        pxe_server_num = pxe_server_num + 1
        if pxe_server_conf[0]["pxe_namespace"] is "undone" \
            or pxe_server_conf[0]["pxe_namespace_ip"] is "undone" \
            or pxe_server_conf[0]["pxe_port"] is "undone" \
            or pxe_server_conf[0]["dnsmasq"] is "undone" : 
                pxe_server_fail_num = pxe_server_fail_num + 1

        pxe_serevr_name = "conf_" + pxe_server.subnet_id
        check_res[pxe_serevr_name] = pxe_server_conf
    
    print json.dumps(check_res, indent=4)
    return pxe_server_num, pxe_server_fail_num, remote_client_num, remote_client_fail_num






    