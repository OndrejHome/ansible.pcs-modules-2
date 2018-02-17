#!/usr/bin/python

DOCUMENTATION = '''
---
author: "Ondrej Famera <ondrej-xa2iel8u@famera.cz>"
module: pcs_cluster
short_description: "wrapper module for 'pcs cluster setup' and 'pcs cluster destroy'"
description:
  - "module for creating and destroying clusters using 'pcs' utility"
version_added: "1.9"
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
notes:
   - Tested on CentOS 6.8, 7.3
   - Tested on Red Hat Enterprise Linux 7.3, 7.4
'''

EXAMPLES = '''
- name: Setup cluster
  pcs_cluster: node_list="{% for item in play_hosts %}{{ hostvars[item]['ansible_hostname'] }} {% endfor %}" cluster_name="test-cluster"
  run_once: true

- name: Destroy cluster on each node
  pcs_cluster: state='absent'
'''

import os.path
from distutils.spawn import find_executable

def main():
        module = AnsibleModule(
                argument_spec = dict(
                        state=dict(default="present", choices=['present', 'absent']),
                        node_list=dict(required=False),
                        cluster_name=dict(required=False),
                        token=dict(required=False, type='int'),
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
            if not module.params['token']:
                cmd = 'pcs cluster setup --name %(cluster_name)s %(node_list)s' % module.params
            else:
                cmd = 'pcs cluster setup --name %(cluster_name)s %(node_list)s --token %(token)s' % module.params
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

# import module snippets
from ansible.module_utils.basic import *
main()
