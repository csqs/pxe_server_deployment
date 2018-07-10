
import urllib2
import json

from conf.load_conf import CONF

bind_host = CONF.bind_host
bind_port = CONF.bind_port
def post():
    url = "http://%s:%s/pxe-client" % (bind_host, bind_port)
    postDict = {
        "subnet_id": "211ef57e-e4bd-4add-ab50-671d5e0cf2c8",
        "network_id": "7462bba7-901e-405b-8bb9-c73c1b383968",
        "tenant_id": "1bd360e1027147a2af24ac360905a964",
        "clients": [
            {
            'mac' : '90:E2:BA:39:23:98',
            'ip' : '192.168.11.7',
            'vni' : '826',
            'vtep_ip' : '10.130.80.1'
            }
        ]
    }
    headers = {'Content-Type':'application/json'}
    request = urllib2.Request(url, headers = headers, data = json.dumps(postDict))
    request.get_method = lambda : "DEL"
    response = urllib2.urlopen(request)
    print response.read()

if __name__ == '__main__':
    post()
    
