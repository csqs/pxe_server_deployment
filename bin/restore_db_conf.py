
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
from bin import pxe_server_api

LOG = logging.getLogger(__name__)

ovs_flow_rule_idle_timeout = CONF.ovs_flow_rule_idle_timeout

def restore_ns_ovs_conf():
    LOG.info("Start to restore ovs and pxe server configurations.")
    db.create_all(bind = "remote_client")
    current_time = datetime.datetime.utcnow()
    conf_timeout_time = current_time - datetime.timedelta(seconds = ovs_flow_rule_idle_timeout)

    remote_clients_dead = remoteClient.query.filter(remoteClient.add_time < conf_timeout_time).all()
    if remote_clients_dead is not None:
        for remote_client in remote_clients_dead:
            db_utils.del_db_remote_client(remote_client.ip)
            pxe_server_api.del_client_api(remote_client.mac, remote_client.ip, remote_client.vni, remote_client.vtep_ip, remote_client.subnet_id)

    db.create_all(bind = "pxe_server")
    all_pxe_servers =  pxeServer.query.all()
    for pxe_server in all_pxe_servers:
        db.create_all(bind = "remote_client")
        all_remote_clients = remoteClient.query.filter_by(subnet_id = pxe_server.subnet_id).all()
        if all_remote_clients is None:
            db_utils.del_db_pxe_server(pxe_server)

