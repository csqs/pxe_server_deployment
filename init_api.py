
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy

from conf.load_conf import logging

LOG = logging.getLogger(__name__)

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///bin/api_db/config.sqlite3"
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

databases = {
    'pxe_server': 'sqlite:///bin/api_db/pxe_server.sqlite3',
    'remote_client': 'sqlite:///bin/api_db/remote_client.sqlite3'
}
app.config['SQLALCHEMY_BINDS'] = databases

db = SQLAlchemy(app)
db.create_all()
