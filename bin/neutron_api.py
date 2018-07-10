# here callback controller pxe ip api 

import urllib2
import json
import os 

from oslo_config import cfg
from oslo_utils import uuidutils

from conf.load_conf import CONF
from conf.load_conf import logging

LOG = logging.getLogger(__name__)

keystone_usrname = CONF.keystone_usrname
keystone_password = CONF.keystone_password
keystone_ip = CONF.keystone_ip
keystone_port = CONF.keystone_port

neutron_ip = CONF.neutron_ip
neutron_port = CONF.neutron_port

pxe_node_ip = CONF.pxe_node_ip

def get_keystone_token():
    headers = {'content-type':'application/json'}
    body = {
            "auth":{
                "identity":{
                        "methods": [
                            "password"
                        ],
                        "password":{
                            "user":{
                                "domain":{
                                    "name":"default"
                                },
                                "name":keystone_usrname,
                                "password":keystone_password
                            }
                        }
                },
                "scope": {
                    "project": {
                        "domain": {
                            "id": "default"
                        },
                        "name": "service"
                    }
                }
            }
    }

    url = "http://%s:%s/v3/auth/tokens" % (keystone_ip, keystone_port)
    request = urllib2.Request(url, headers = headers, data = json.dumps(body))
    request.get_method = lambda : "POST"

    LOG.info("Details of get_keystone_token:\nrequest_url: %s \nheader: %s\nbody: %s" % (url, json.dumps(headers), json.dumps(body)))
    try:  
        response = urllib2.urlopen(request) 
        response_json = json.loads(response.read())
        LOG.info("Response of calling get_keystone_token:\n%s" % json.dumps(response_json))  
    except urllib2.URLError as e: 
        LOG.exception("Error in calling get_keystone_token.")
        response_json = json.loads(e.read())
        LOG.info("Response of calling get_keystone_token:\n%s" % json.dumps(response_json))
        return "ERROR" 
    else:
        LOG.info("SUCCESS to call get_keystone_token")  
        resp ={}
        resp['headers'] = response.headers
        token_id =  resp['headers']["X-Subject-Token"]
        return token_id

def get_subnet_dhcp_range(subnet_id, token_id):
    headers = {'content-type':'application/json',
               'accept':'application/json',
               'X-Auth-Token':token_id
               }
    subnet_url = "/v2.0/subnets/" + subnet_id
    url = "http://%s:%s%s" % (neutron_ip, neutron_port, subnet_url)
    request = urllib2.Request(url, headers = headers, data = None)
    request.get_method = lambda : "GET"

    LOG.info("Details of get_subnet_dhcp_range:\nrequest_url: %s \nheader: %s" % (url, json.dumps(headers)))
    try:  
        response = urllib2.urlopen(request)
        response_json = json.loads(response.read())
        LOG.info("Response of calling get_subnet_dhcp_range:\n%s" % json.dumps(response_json)) 
    except urllib2.URLError as e: 
        LOG.exception("Error in calling get_subnet_dhcp_range.")
        response_json = json.loads(e.read())
        LOG.info("Response of calling get_subnet_dhcp_range:\n%s" % json.dumps(response_json)) 
        return "ERROR"
    else:
        LOG.info("SUCCESS to call get_subnet_dhcp_range")   
        response = urllib2.urlopen(request)
        CONF.dnsmasq_gateway_addr = response_json["subnet"]["gateway_ip"]
        if response_json["subnet"]["dhcp_allocation_pools"] == []:
            CONF.dnsmasq_dns_addr = CONF.dnsmasq_gateway_addr
        else:
            CONF.dnsmasq_dns_addr = response_json["subnet"]["dhcp_allocation_pools"][0]["start"]

        dhcp_range_start = response_json["subnet"]["allocation_pools"][0]["start"]
        dhcp_range_end = response_json["subnet"]["allocation_pools"][0]["end"]
        dhcp_range = "%s,%s,48h" % (dhcp_range_start, dhcp_range_end)
        CONF.dhcp_range = dhcp_range

        dhcp_netmask_str = response_json["subnet"]["cidr"]
        dhcp_netmask_str_split = dhcp_netmask_str.split("/")
        CONF.dhcp_netmask = dhcp_netmask_str_split[1]
        LOG.info('get_subnet_dhcp_range is: %s' % CONF.dhcp_range)
        return "SUCCESS"

def get_pxe_ip(network_id, tenant_id, subnet_id):
    token_id = get_keystone_token()
    if token_id is "ERROR":
        return None, None, None

    request_id = uuidutils.generate_uuid()
    headers = {'content-type':'application/json',
               'accept':'application/json',
               'x-bce-resource-id': request_id,
               #'x-bce-resource-id': 'a163de20-1ffa-4476-902f-cf6b8d2251c2',
               'x-auth-token': token_id
               } 
    body = {"port":{"binding:host_id":pxe_node_ip, 
                    #"binding:host_id":"10.107.225.1",
                    "admin_state_up":True,
                    "network_id":network_id,
                    #"network_id":"7462bba7-901e-405b-8bb9-c73c1b383968",
                    "tenant_id": tenant_id,
                    #"tenant_id":"1bd360e1027147a2af24ac360905a964",
                    "device_owner": "bare_metal",
                    "binding:vif_details":{"interface_name":"bbc-pxe-server","type":"untagged","interface_id":1},
                    "fixed_ips": [{"subnet_id": subnet_id}]
                    #"fixed_ips":[{"subnet_id":"211ef57e-e4bd-4add-ab50-671d5e0cf2c8"}]
                    }
            }

    url = "http://%s:%s/v2.0/ports.json" % (neutron_ip, neutron_port)
    request = urllib2.Request(url, headers = headers, data = json.dumps(body))
    request.get_method = lambda : "POST"
    
    LOG.info("Details of get_pxe_ip:\nrequest: %s \nheaders: %s\nbody: %s" % (url, json.dumps(headers), json.dumps(body)))
    try:
        response = urllib2.urlopen(request)
        response_json = json.loads(response.read())
        LOG.info("Response of calling get_pxe_ip:\n%s" % json.dumps(response_json))  
    except urllib2.URLError as e: 
        LOG.exception("Error in calling get_pxe_ip.")
        response_json = json.loads(e.read())
        LOG.info("Response of calling get_pxe_ip:\n%s" % json.dumps(response_json))
        return None, None, None
    else:  
        # here can only read response only one time  
        # print response.read()
        LOG.info("SUCCESS to call get_pxe_ip") 
        mac = response_json["port"]["mac_address"]
        ip = response_json["port"]["fixed_ips"][0]["ip_address"]
        port_id = response_json["port"]["id"]

        subnet_id = response_json["port"]["fixed_ips"][0]['subnet_id']
        get_subnet_dhcp_range_res = get_subnet_dhcp_range(subnet_id, token_id)
        if get_subnet_dhcp_range_res is "ERROR":
            return None, None, None
        else:
            return mac, ip, port_id


'''
subnet_id = "211ef57e-e4bd-4add-ab50-671d5e0cf2c8"
network_id = "7462bba7-901e-405b-8bb9-c73c1b383968"
tenant_id = "1bd360e1027147a2af24ac360905a964"
get_pxe_ip(network_id, tenant_id, subnet_id)
'''

'''
def get_pxe_ip(network_id, subnet_id, tenant_id):
    return "FA:16:3E:DA:F4:94 ", "192.168.18.65", "4512be1d-cf57-411a-a789-faeda2719c7d"
'''

