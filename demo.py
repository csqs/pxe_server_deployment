
import re
import socket
import datetime
import json 

from flask import Flask, jsonify, request, abort
from flask_sqlalchemy import SQLAlchemy

from conf.load_conf import CONF
from conf.load_conf import logging
from init_api import app, db
from bin.api_db.objects import pxeServer, remoteClient
from bin import restore_db_conf
from bin import pxe_server_api
from bin import client_tor_api

LOG = logging.getLogger(__name__)

mlnx_vtep_name_map = CONF.mlnx_vtep_name_map
h3c_vtep_name_map = CONF.h3c_vtep_name_map

@app.route('/pxe-client', methods = ['POST'])
#@app.route('/pxe-server-deployment/api/v1.0/add-client', methods = ['POST'])
def add_client():
    if not request.json:
        abort(400)

    LOG.info("Details of add client:\n%s" % json.dumps(request.json))
    ip =  request.json['clients'][0]['ip']
    mac =  request.json['clients'][0]['mac']
    vni = request.json['clients'][0]['vni']
    vtep_ip = request.json['clients'][0]['vtep_ip']
    subnet_id = request.json['subnet_id']
    network_id = request.json['network_id']
    tenant_id = request.json['tenant_id']

    if vtep_ip in mlnx_vtep_name_map.keys():
        client_tor_conf_res = client_tor_api.client_mlnx_tor_conf(vni, vtep_ip)
        if client_tor_conf_res is not "SUCCESS":
            LOG.exception("Error in client_mlnx_tor_conf.")
            abort(400)
    elif vtep_ip in h3c_vtep_name_map.keys():
        client_tor_conf_res = client_tor_api.client_h3c_tor_conf(vni, vtep_ip)
        if client_tor_conf_res is not "SUCCESS":
            LOG.exception("Error in client_h3c_tor_conf.")
            abort(400)
    else:
        LOG.exception("vtep_ip is not in mlnx_vtep_name_map and client_h3c_tor_conf.")
        abort(400)

    api_res = pxe_server_api.add_client_api(mac, ip, vni, vtep_ip, subnet_id, network_id, tenant_id)
    return jsonify({'api_res': api_res}), 201

@app.route('/pxe-clients', methods=['GET'])
def list_pxe_servers():
    api_res = pxe_server_api.list_pxe_servers()
    return jsonify({'api_res': api_res}), 201

@app.route('/pxe-clients-in-db', methods=['DEL'])
def del_db_clients():
    api_res = pxe_server_api.del_db_client_api()
    return jsonify({'api_res': api_res}), 201

@app.route('/pxe-client', methods=['DEL'])
def del_client():
    if not request.json:
        abort(400)

    mac =  request.json['clients'][0]['mac']
    ip =  request.json['clients'][0]['ip']
    vni = request.json['clients'][0]['vni']
    vtep_ip = request.json['clients'][0]['vtep_ip']
    subnet_id = request.json['subnet_id']

    api_res = pxe_server_api.del_client_api(mac, ip, vni, vtep_ip, subnet_id) 
    return jsonify({'api_res': api_res}), 201

if __name__ == '__main__':
    restore_db_conf.restore_ns_ovs_conf()
    app.run(
        host = CONF.bind_host,
        port = CONF.bind_port,
        debug=True
    )