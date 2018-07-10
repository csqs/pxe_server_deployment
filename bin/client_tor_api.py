# here callback controller pxe ip api 

import urllib2
import json
import os 

from oslo_config import cfg
from oslo_utils import uuidutils

from conf.load_conf import CONF
from conf.load_conf import logging

LOG = logging.getLogger(__name__)

pxe_node_ip = CONF.pxe_node_ip

icc_ip = CONF.icc_ip
icc_port = CONF.icc_port

mlnx_vtep_name_map = CONF.mlnx_vtep_name_map
h3c_vtep_name_map = CONF.h3c_vtep_name_map 
h3c_vtep_tun_id_map = CONF.h3c_vtep_tun_id_map 
h3c_vtep_ip_map = CONF.h3c_vtep_ip_map 
h3c_model = CONF.h3c_model
pxe_model = CONF.pxe_model
pxe_tun_id = CONF.pxe_tun_id

def client_mlnx_tor_conf(vni, vtep_ip):
    client_tor_name = mlnx_vtep_name_map[vtep_ip]
    request_id = uuidutils.generate_uuid()
    headers = {'content-type' : 'application/json',
               'x-bce-request-id': request_id,
               'Authorization' : 'Basic YmJjOmJiYzEyMw=='
               } 
    body = {"vni_id" : int(vni),
            "src_addr" : vtep_ip,
            "peer_addrs" : [pxe_node_ip]
            }

    icc_bind_tunnel_url = "/device/" + client_tor_name + "/cmd/bind_tunnel/"
    url = "http://%s:%s%s" % (icc_ip, icc_port, icc_bind_tunnel_url)
    url = url.replace("'", "")
    request = urllib2.Request(url, headers = headers, data = json.dumps(body))
    request.get_method = lambda : "POST"
    try:
        LOG.info("request: %s \nheader: %s\nbody: %s" % (url, json.dumps(headers), json.dumps(body)))
        response = urllib2.urlopen(request)
    except urllib2.URLError, e: 
        LOG.exception("Error when calling mlnx bind tunnel.")
        return e.code   
    else:  
        return 'SUCCESS'

def client_h3c_tor_conf(vni, vtep_ip):
    request_id = uuidutils.generate_uuid()
    h3c_vtep_ip = vtep_ip
    h3c_name = h3c_vtep_name_map[vtep_ip]
    h3c_admin_ip = h3c_vtep_ip_map[vtep_ip]
    h3c_tun_id = h3c_vtep_tun_id_map[vtep_ip]
    headers = {'content-type' : 'application/json',
               'x-bce-request-id': request_id,
               'Authorization' : 'Basic YmJjOmJiYzEyMw=='
               } 
    body = {"local_vtep" : {
                "admin_ip" : h3c_admin_ip,
                "ip" : h3c_vtep_ip,
                "id" : int(h3c_tun_id),
                "model" : h3c_model
                },
            "remote_vtep" : {
                "admin_ip" : pxe_node_ip,
                "ip" : pxe_node_ip,
                "id" : pxe_tun_id,
                "model" : pxe_model
               }
            }

    h3c_create_tunnel_url = "/netconf-api/v1/tunnel"
    url = "http://%s:%s%s" % (icc_ip, icc_port, h3c_create_tunnel_url)
    url = url.replace("'", "")
    request = urllib2.Request(url, headers = headers, data = json.dumps(body))
    request.get_method = lambda : "POST"

    LOG.info("Details of h3c create tunnel:\nrequest_url: %s\nheader: %s\nbody: %s" % (url, json.dumps(headers), json.dumps(body)))
    try:
        response = urllib2.urlopen(request)
        response_json = json.loads(response.read())
        LOG.info("Response of calling h3c create tunnel:\n%s" % json.dumps(response_json))
    except urllib2.URLError as e: 
        LOG.exception("Error when calling h3c create tunnel.")
        response_json = json.loads(e.read())
        LOG.info("Response of calling h3c create tunnel:\n%s" % json.dumps(response_json))
        return e.code   
    else:
        LOG.info("SUCCESS to call h3c create tunnel")
        request_id = uuidutils.generate_uuid()
        tunnel_ids = [pxe_tun_id]
        headers = {'content-type' : 'application/json',
                   'x-bce-request-id' : request_id,
                   'Authorization' : 'Basic YmJjOmJiYzEyMw=='
                   }
        body = {
            "vxlan_id" : int(vni),
            "tunnel_ids" : tunnel_ids
        }
        h3c_bind_tunnel_url = "/device/" + h3c_name + "/cmd/bind_tunnel/"
        url = "http://%s:%s%s" % (icc_ip, icc_port, h3c_bind_tunnel_url)
        url = url.replace("'", "")
        request = urllib2.Request(url, headers = headers, data = json.dumps(body))
        request.get_method = lambda : "POST"
        LOG.info("Details of h3c bind tunnel:\nrequest_url: %s \nheader: %s\nbody: %s" % (url, json.dumps(headers), json.dumps(body)))
        try:
            response = urllib2.urlopen(request)
            response_json = json.loads(response.read())
            LOG.info("Response of calling h3c bind tunnel:\n%s" % json.dumps(response_json))
        except urllib2.URLError as e: 
            LOG.exception("Error when calling h3c bind tunnel.")
            response_json = json.loads(e.read())
            LOG.info("Response of calling h3c bind tunnel:\n%s" % json.dumps(response_json))
            return e.code   
        else:
            LOG.info("SUCCESS to call h3c bind tunnel")
            return 'SUCCESS'

'''
vni = "1"
vtep_ip = "10.156.29.1"
client_h3c_tor_conf(vni, vtep_ip)
vni = "1"
vtep_ip = "10.255.3.137"
client_mlnx_tor_conf(vni, vtep_ip)
'''


