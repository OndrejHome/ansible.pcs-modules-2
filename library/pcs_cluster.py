#!/usr/bin/python

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
author: "Ondrej Famera <ondrej-xa2iel8u@famera.cz>"
module: pcs_cluster
short_description: "wrapper module for 'pcs cluster setup' and 'pcs cluster destroy'"
description:
  - "module for creating and destroying clusters using 'pcs' utility"
version_added: "2.4"
options:
  state:
    description:
      - "'present' - ensure that cluster exists"
      - "'absent' - ensure cluster doesn't exist"
    required: false
    default: present
    choices: ['present', 'absent']
  node_list:
    description:
      - space separated list of nodes in cluster
    required: false
  cluster_name:
    description:
      - pacemaker cluster name
    required: true
  token:
    description:
      - sets time in milliseconds until a token loss is declared after not receiving a token
    required: false
  transport:
    description:
      - "'default' - use default transport protocol ('udp' in CentOS/RHEL 6, 'udpu' in CentOS/RHEL 7)"
      - "'udp' - use UDP multicast protocol"
      - "'udpu' - use UDP unicast protocol"
    required: false
    default: default
    choices: ['default', 'udp', 'udpu']
notes:
   - Tested on CentOS 6.8, 6.9, 7.3, 7.4
   - Tested on Red Hat Enterprise Linux 7.3, 7.4
'''

EXAMPLES = '''
- name: Setup cluster
  pcs_cluster: node_list="{% for item in play_hosts %}{{ hostvars[item]['ansible_hostname'] }} {% endfor %}" cluster_name="test-cluster"
  run_once: true

- name: Create cluster with totem token timeout of 5000 ms and UDP unicast transport protocol
  pcs_cluster: node_list="{% for item in play_hosts %}{{ hostvars[item]['ansible_hostname'] }} {% endfor %}" cluster_name="test-cluster" token=5000 transport='udpu'
  run_once: true

- name: Destroy cluster on each node
  pcs_cluster: state='absent'
'''

import os.path
from distutils.spawn import find_executable

from ansible.module_utils.basic import AnsibleModule

def run_module():
        module = AnsibleModule(
                argument_spec = dict(
                        state=dict(default="present", choices=['present', 'absent']),
                        node_list=dict(required=False),
                        cluster_name=dict(required=False),
                        token=dict(required=False, type='int'),
                        transport=dict(required=False, default="default", choices=['default','udp','udpu']),
                        #allow_rename=dict(required=False, default='no', type='bool'),
                ),
                supports_check_mode=True
        )

        state = module.params['state']
        if state == 'present' and (not module.params['node_list'] or not module.params['cluster_name']):
            module.fail_json(msg='When creating cluster you must specify both node_list and cluster_name')
        result = {}

        if find_executable('pcs') is None:
            module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")
        
        # /var/lib/pacemaker/cib/cib.xml exists on cluster that were at least once started
        cib_xml_exists = os.path.isfile('/var/lib/pacemaker/cib/cib.xml') 
        ## EL 6 configuration file
        cluster_conf_exists = os.path.isfile('/etc/cluster/cluster.conf') 
        ## EL 7 configuration file
        corosync_conf_exists = os.path.isfile('/etc/corosync/corosync.conf') 
        if state == 'present' and not (cluster_conf_exists or corosync_conf_exists or cib_xml_exists):
            result['changed'] = True
            # create cluster from node list that was provided to module
            module.params['token_param'] = '' if (not module.params['token']) else '--token %(token)s' % module.params
            module.params['transport_param'] = '' if (module.params['transport'] == 'default') else '--transport %(transport)s' % module.params
            cmd = 'pcs cluster setup --name %(cluster_name)s %(node_list)s %(token_param)s %(transport_param)s' % module.params
            if not module.check_mode:
                rc, out, err = module.run_command(cmd)
                if rc == 0:
                    module.exit_json(changed=True)
                else:
                    module.fail_json(msg="Failed to create cluster using command '" + cmd + "'", output=out, error=err)
        elif state == 'absent' and (cluster_conf_exists or corosync_conf_exists or cib_xml_exists):
            result['changed'] = True
            # destroy cluster on node where this module is executed
            cmd = 'pcs cluster destroy'
            if not module.check_mode:
                rc, out, err = module.run_command(cmd)
                if rc == 0:
                    module.exit_json(changed=True)
                else:
                    module.fail_json(msg="Failed to delete cluster using command '" + cmd + "'", output=out, error=err)
        else:
            result['changed'] = False
            #FIXME not implemented yet
            module.exit_json(changed=False)

        ## END of module
        module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
