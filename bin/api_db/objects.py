import datetime

from init_api import db

class pxeServer(db.Model):
    __tablename__ = "pxe_server"
    __bind_key__ = "pxe_server"

    subnet_id = db.Column(db.String(30), primary_key=True)
    port_ip = db.Column(db.String(30))
    port_id = db.Column(db.String(30))
    add_time = db.Column(db.DateTime, nullable = False, default = datetime.datetime.utcnow)
    #remote_clients = db.relationship('remoteClient', backref = 'pxe_server', lazy = 'select')

    def __init__(self, subnet_id, port_ip, port_id):
        self.subnet_id = subnet_id
        self.port_ip = port_ip
        self.port_id = port_id
    def __repr__(self):
        return "<pxeServer subnet_id %r port_ip %r port_id %r>" % (self.subnet_id, self.port_ip, self.port_id)

class remoteClient(db.Model):
    __tablename__ = "remote_client"
    __bind_key__ = "remote_client"

    ip = db.Column(db.String(30), primary_key=True)
    mac = db.Column(db.String(30))
    vni = db.Column(db.String(30))
    vtep_ip = db.Column(db.String(30))
    #subnet_id = db.Colunmn(db.String(30), db.ForeignKey('pxe_server.subnet_id'))
    subnet_id = db.Column(db.String(50))
    network_id = db.Column(db.String(50))
    tenant_id = db.Column(db.String(50))
    add_time = db.Column(db.DateTime, nullable = False, default = datetime.datetime.utcnow)

    def __init__(self, ip, mac, vni, vtep_ip, subnet_id, network_id, tenant_id):
        self.ip = ip
        self.mac = mac
        self.vni = vni
        self.vtep_ip = vtep_ip
        self.subnet_id = subnet_id
        self.network_id = network_id
        self.tenant_id = tenant_id
    def __repr__(self):
        return "<remoteClient ip %r mac %r vni %r vtep_ip %r subnet_id %r network_id %r tenant_id %r add_time %r>"\
         % (self.ip, self.mac, self.vni, self.vtep_ip, self.subnet_id, self.network_id, self.tenant_id, self.add_time.strftime('%B %d %Y - %H:%M:%S'))
