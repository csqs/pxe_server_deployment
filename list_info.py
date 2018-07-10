
import urllib2
import json

from oslo_config import cfg
from conf.load_conf import CONF

bind_host = CONF.bind_host
bind_port = CONF.bind_port
def post():
    url = "http://%s:%s/pxe-clients" % (bind_host, bind_port)
    postDict = {}
    headers = {'Content-Type':'application/json'}
    request = urllib2.Request(url, headers = headers, data = json.dumps(postDict))
    request.get_method = lambda : "GET"
    response = urllib2.urlopen(request)
    print response.read()

if __name__ == '__main__':
    post()
    
