
import urllib2
import json
import random

from oslo_config import cfg
from oslo_log import log as logging
from conf.load_conf import CONF

from test import test_case
from test import utils as test_utils

LOG = logging.getLogger(__name__)

bind_host = CONF.bind_host
bind_port = CONF.bind_port

def add_post(postDict):
    url = "http://%s:%s/pxe-server-deployment/api/v1.0/add-client" % (bind_host, bind_port)
    headers = {'Content-Type':'application/json'}
    request = urllib2.Request(url, headers = headers, data = json.dumps(postDict))
    request.get_method = lambda : "POST"
    response = urllib2.urlopen(request)
    return response

def del_post(postDict):
    url = "http://%s:%s/pxe-server-deployment/api/v1.0/del-client" % (bind_host, bind_port)
    headers = {'Content-Type':'application/json'}
    request = urllib2.Request(url, headers = headers, data = json.dumps(postDict))
    request.get_method = lambda : "POST"
    response = urllib2.urlopen(request)
    return response

def check_test_cases():
    test_cases = test_case.test_cases
    test_case_name = "test_case_"

    '''
    test_case_num = 2
    case_name = test_case_name + "%d" % test_case_num
    LOG.info("Start to test the case %s." % case_name)
    case_group = test_cases[case_name]
    post_dict_1 = case_group[0]
    post_dict_2 = case_group[1]

    add_post(post_dict_1)
    add_post(post_dict_2)
    test_utils.check_db_conf()
    del_post(post_dict_1)
    del_post(post_dict_2)
    '''
    
    for test_case_num in range(1, len(test_cases) + 1):
        case_name = test_case_name + "%d" % test_case_num
        LOG.info("Start to test the case %s." % case_name)
        case_group = test_cases[case_name]
        post_dict_1 = case_group[0]
        post_dict_2 = case_group[1]

        add_post(post_dict_1)
        add_post(post_dict_2)
        test_utils.check_db_conf()
        del_post(post_dict_1)
        del_post(post_dict_2)

def pressure_test_cases():
    post_dicts = []
    post_dicts_add_casue_problem = []
    post_dicts_del_casue_problem = []
    # since the linux resource limitation, max_case_num = 200 
    case_num = 10
    test_case_name = "test_case_"
    for test_case_num in range(0, case_num):
        case_name = test_case_name + "%d" % test_case_num
        LOG.info("Start to test the case %s." % case_name)

        subnet_id = "%d" % test_utils.gene_rand_num_in_1000()
        network_id = subnet_id
        tenant_id = subnet_id
        vni = "%d" % test_utils.gene_rand_num_in_1000()
        client_mac = test_utils.gene_rand_mac()
        client_ip = test_utils.genr_rand_ip()
        client_vtep_ip = test_utils.genr_rand_ip()

        post_dict = {
            "subnet_id" : subnet_id, 
            "network_id": network_id,
            "tenant_id": tenant_id,
            "clients": [
                {
                    "ip": client_ip,
                    "mac": client_mac,
                    "vtep_ip": client_vtep_ip,
                    "vni": vni
                }
            ]
        }

        response = add_post(post_dict)
        response_josn = json.loads(response.read())
        print json.dumps(response_josn, indent=4)
        if response_josn["api_res"][0]["done"] == "undone":
            post_dicts_add_casue_problem.append(post_dict)
            break
        post_dicts.append(post_dict)

    pxe_server_num, pxe_server_fail_num, remote_client_num, remote_client_fail_num = test_utils.check_db_conf()

    for post_dict in post_dicts:
        response = del_post(post_dict)
        response_josn = json.loads(response.read())
        if response_josn["api_res"][0]["done"] == "undone":
            post_dicts_del_casue_problem.append(post_dict)
            break

    print "cases cause problems when adding a client: \n"
    for post_dict in post_dicts_add_casue_problem:
        print json.dumps(post_dict, indent=4)

    print "cases cause problems when deleting a client: \n"
    for post_dict in post_dicts_del_casue_problem:
        print json.dumps(post_dict, indent=4)

    return case_num, pxe_server_num, pxe_server_fail_num, remote_client_num, remote_client_fail_num

#check_test_cases()
case_num, pxe_server_num, pxe_server_fail_num, remote_client_num, remote_client_fail_num = pressure_test_cases()
print "case: %d \npxe_server_num: %d \npxe_server_fail_num: %d \n\nremote_client_num: %d \nremote_client_fail_num: %d \n" \
    % (case_num, pxe_server_num, pxe_server_fail_num, remote_client_num, remote_client_fail_num)





    