
from oslo_config import cfg

from conf.load_conf import logging
from bin.api_db.objects import pxeServer, remoteClient
from bin.api_db import utils as db_utils
from init_api import app, db
from bin import neutron_api
from bin import utils

LOG = logging.getLogger(__name__)

def add_client_api(mac, ip, vni, vtep_ip, subnet_id, network_id, tenant_id):
    LOG.info("The subnet is %s." % subnet_id)
    api_res = [
        {
            'done': 'undone',
            'create_ns': 'undone',
            'start_dnsmasq': 'undone',
            'configure_ovs': 'undone'
        }
    ]

    if utils.check_br_tun():
        LOG.info("br-tun exists.")
    else:
        LOG.info("Add neutron br-tun in host.")
        utils.add_br_tun()
   
    vxlan_tap_id = utils.encrypt_string(vtep_ip)
    vxlan_port_name = "vx-%s" % vxlan_tap_id
    vxlan_port_name = vxlan_port_name[:15]
    if utils.check_vtep_ip(vtep_ip):
        LOG.info("vxlan tunnel port exists.")
    else:
        # here ovs adds the vxlan is unstable
        get_vxlan_port_times = 3
        for i in range(0, get_vxlan_port_times):
            LOG.info("Create vxlan tunnel port %s." % (vxlan_port_name))
            utils.add_vxlan_tun(vxlan_port_name, vtep_ip)

            vxlan_port_num = utils.get_port_num(vxlan_port_name)
            if vxlan_port_num is "":
                LOG.exception("Failed to get namespace vxlan port number, after trying %d times." % i)
                if i + 1 == get_vxlan_port_times:
                    return api_res
            else:
                break

    pxe_id = subnet_id[:10]
    pxe_ns_name = "pxe_ns_%s" % pxe_id
    pxe_port_name = "pxe_port_%s" % pxe_id
    pxe_port_name = pxe_port_name[:15]
    if utils.check_ns(pxe_ns_name):
        LOG.info("pxe namespace exists.")
    else:
        pxe_port_mac, pxe_port_ip, pxe_port_id = neutron_api.get_pxe_ip(network_id, tenant_id, subnet_id)
        if pxe_port_mac is None or pxe_port_ip is None or pxe_port_id is None:
            LOG.exception("Error in calling neutron_api.")
            return api_res

        get_pxe_port_times = 3
        for i in range(0, get_pxe_port_times):
            LOG.info("Create namespace %s and the br-tun internal port %s." % (pxe_ns_name, pxe_port_name))
            utils.add_pxe_ns(pxe_ns_name, pxe_port_name, pxe_port_mac, pxe_port_ip)

            pxe_port_num = utils.get_port_num(pxe_port_name)
            if pxe_port_num is "":
                LOG.exception("Failed to get namespace port number.")
                if i + 1 == get_pxe_port_times:
                    return api_res
            else:
                api_res[0]['create_ns'] = "done"

                LOG.info("Start a dnsmasq tftp server.")
                utils.start_tftp_dhcp(pxe_ns_name, pxe_port_ip)
                api_res[0]['start_dnsmasq'] = "done"

                pxe_server = pxeServer(subnet_id, pxe_port_ip, pxe_port_id)
                db_utils.add_db_pxe_server(pxe_server)
                break

    vxlan_port_num = utils.get_port_num(vxlan_port_name)
    pxe_port_num = utils.get_port_num(pxe_port_name)
        
    LOG.info("Update the dhcp host file and then dnsmasq.")
    utils.add_dhcpHost(pxe_ns_name, mac, ip)

    LOG.info("Start to install flow rules.")
    utils.add_ovs_flow_rules(mac, ip, vni, pxe_port_num, vxlan_port_num)
    api_res[0]['configure_ovs'] = "done"

    remote_client = remoteClient(ip, mac, vni, vtep_ip, subnet_id, network_id, tenant_id)
    db_utils.add_db_remote_client(remote_client) 

    api_res[0]['done'] = 'done' 
    return api_res

def list_pxe_servers():
    LOG.info("Start to list pxe servers and remote clients.")
    db.create_all(bind = "pxe_server")
    api_res = {}
    all_pxe_servers =  pxeServer.query.all()
    for pxe_server in all_pxe_servers:
        db.create_all(bind = "remote_client")
        all_remote_clients = remoteClient.query.filter_by(subnet_id = pxe_server.subnet_id).order_by(remoteClient.add_time).all()
        clients = []
        for remote_client in all_remote_clients:
            remote_client_info = {
                "ip" : remote_client.ip,
                "mac" : remote_client.mac,
                "vni" : remote_client.vni,
                "vtep" : remote_client.vtep_ip
            }
            clients.append(remote_client_info)

        pxe_server_info = [{
            "subnet_id" : pxe_server.subnet_id,
            "port_id" : pxe_server.port_id,
            "ip" : pxe_server.port_ip,
            "clients": clients,
            "created_at": pxe_server.add_time.strftime('%B %d %Y - %H:%M:%S'),
            "updated_at" : all_remote_clients[0].add_time.strftime('%B %d %Y - %H:%M:%S')
        }]
        pxe_serevr_name = "pxe_server_" + pxe_server.subnet_id
        api_res[pxe_serevr_name] = pxe_server_info
    return api_res

def del_client_api(mac, ip, vni, vtep_ip, subnet_id):
    api_res = [
        {
            'del_ovs_flow_rules' : 'undone',
            'del_namespace' : 'undone',
            'done': 'undone',
        }
    ]

    pxe_id = subnet_id[:10]
    pxe_port_name = "pxe_port_%s" % pxe_id
    pxe_port_name = pxe_port_name[:15]

    vxlan_tap_id = utils.encrypt_string(vtep_ip)
    vxlan_port_name = "vx-%s" % vxlan_tap_id
    vxlan_port_name = vxlan_port_name[:15]

    pxe_port_num = utils.get_port_num(pxe_port_name)
    vxlan_port_num = utils.get_port_num(vxlan_port_name)

    if pxe_port_num is "":
        LOG.info("Pxe port is not existed.")
    elif vxlan_port_num is "":
        LOG.exception("Failed to vxlan port number.")
        return api_res
    elif pxe_port_num is not "" and vxlan_port_num is not "":
        LOG.info("Start to delete flow rules, (and pxe namespace when necessary).")
        api_res = utils.del_ovs_flow_rules(api_res, mac, ip, vni, vtep_ip, subnet_id, pxe_port_num, vxlan_port_num)

    api_res[0]['done'] = 'done' 
    return api_res

def del_db_client_api():
    LOG.info("Start to delete remote clients in db.")
    db.create_all(bind = "pxe_server")
    api_res = {}
    all_pxe_servers =  pxeServer.query.all()
    for pxe_server in all_pxe_servers:
        db.create_all(bind = "remote_client")
        all_remote_clients = remoteClient.query.filter_by(subnet_id = pxe_server.subnet_id).order_by(remoteClient.add_time).all()
        clients = []
        for remote_client in all_remote_clients:
            pxe_id = remote_client.subnet_id[:10]
            pxe_port_name = "pxe_port_%s" % pxe_id
            pxe_port_name = pxe_port_name[:15]

            vxlan_tap_id = utils.encrypt_string(remote_client.vtep_ip)
            vxlan_port_name = "vx-%s" % vxlan_tap_id
            vxlan_port_name = vxlan_port_name[:15]

            pxe_port_num = utils.get_port_num(pxe_port_name)
            vxlan_port_num = utils.get_port_num(vxlan_port_name)

            client_api_res = [
                {
                    'client_ip' : remote_client.ip,
                    'del_ovs_flow_rules' : 'undone',
                    'del_namespace' : 'undone',
                    'done': 'undone',
                }
            ]
            if pxe_port_num is "":
                LOG.info("Pxe port is not existed.")
            elif vxlan_port_num is "":
                LOG.exception("Failed to vxlan port number.")
                return api_res
            elif pxe_port_num is not "" and vxlan_port_num is not "":
                LOG.info("Start to delete flow rules, (and pxe namespace when necessary).")
                client_api_res = utils.del_ovs_flow_rules(client_api_res, remote_client.mac, remote_client.ip, remote_client.vni, remote_client.vtep_ip, remote_client.subnet_id, pxe_port_num, vxlan_port_num)

            client_api_res[0]['done'] = 'done' 
            clients.append(client_api_res[0])
        pxe_serevr_name = "pxe_server_" + pxe_server.subnet_id
        api_res[pxe_serevr_name] = clients
    return api_res






    