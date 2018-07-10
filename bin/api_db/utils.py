import datetime

from conf.load_conf import logging
from bin.api_db.objects import pxeServer, remoteClient
from init_api import db

LOG = logging.getLogger(__name__)

def get_pxe_ip_id(subnet_id):
    db.create_all(bind = "pxe_server")
    existed_pxe_server = pxeServer.query.filter_by(subnet_id = subnet_id).first()
    if existed_pxe_server is not None:
        LOG.info("pxe_server port_ip is %s." % existed_pxe_server.port_ip)
        return existed_pxe_server.port_ip, existed_pxe_server.port_id
    LOG.exception("Fail to get pxe_server port_ip.")
    return None, None

def init_pxe_server(subnet_id):
    pxe_port_ip, pxe_port_id = get_pxe_ip_id(subnet_id)
    if pxe_port_ip is not None and pxe_port_id is not None:
        pxe_server = pxeServer(subnet_id, pxe_port_ip, pxe_port_id)
        return pxe_server
    return None

def add_db_pxe_server(pxe_server):
    LOG.info("Start to add a record in pxe_server db.")
    db.create_all(bind = "pxe_server")
    existed_pxe_server = pxeServer.query.filter_by(subnet_id = pxe_server.subnet_id).first()
    if existed_pxe_server is None:
        db.session.add(pxe_server)
        db.session.commit()
        LOG.info("pxe_server db record add is comleted.")

def del_db_pxe_server(pxe_server_subnet_id):
    LOG.info("Start to delete a record in pxe_server db.")
    db.create_all(bind = "pxe_server")
    existed_pxe_server = pxeServer.query.filter_by(subnet_id = pxe_server_subnet_id).first()
    if existed_pxe_server is not None:
        db.session.delete(existed_pxe_server)
        db.session.commit()
        LOG.info("pxe_server db record delete is comleted.")

def add_db_remote_client(remote_client):
    LOG.info("Start to add a record in remote_client db.")
    db.create_all(bind = "remote_client")
    existed_remote_client = remoteClient.query.filter_by(ip = remote_client.ip).first()
    if existed_remote_client is None:
        db.session.add(remote_client)
        db.session.commit()
        LOG.info("remote_client db record add is comleted.")

def del_db_remote_client(remote_client_ip):
    LOG.info("Start to delete a record in remote_client db.")
    db.create_all(bind = "remote_client")
    existed_remote_client = remoteClient.query.filter_by(ip = remote_client_ip).first()
    if existed_remote_client is not None:
        db.session.delete(existed_remote_client)
        db.session.commit()
        LOG.info("remote_client db record delete is comleted.")
