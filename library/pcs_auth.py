#!/usr/bin/python

DOCUMENTATION = '''
---
author: "Ondrej Famera <ondrej-xa2iel8u@famera.cz>"
module: pcs_auth
short_description: Module for interacting with 'pcs auth'
description:
  - module for authenticating nodes in pacemaker cluster using 'pcs auth' for RHEL/CentOS.
version_added: "2.0"
options:
  state:
    description:
    - "'present' authenticates the node while 'absent' will remove the node authentification"
    - "node from which this is run is (de)authenticated agains the node specified in 'node_name'"
    required: false
    default: present
    choices: [ 'present', 'absent' ]
  node_name:
    description:
      - hostname of node for authentication
    required: true
  username:
    description:
      - "username of 'cluster user' for cluster authentication"
    required: false
    default: 'hacluster'
  password:
    description:
      - "password of 'cluster user' for cluster authentication"
    required: false
notes:
  - This module is (de)authenticating nodes only 1-way == authenticating node 1 agains
    node 2 doesn't mean that node 2 is authenticated agains node 1!
  - tested on CentOS 6.8, 7.3
'''

EXAMPLES = '''
- name: Authorize node 'n1' with default user 'hacluster' and password 'testtest'
  pcs_auth: node_name='n1' password='testtest'

- name: authorize all nodes in ansible play to each other
  pcs_auth: node_name="{{ hostvars[item]['ansible_hostname'] }}" password='testtest'
  with_items: "{{ play_hosts }}"

- name: de-authorize all nodes from each other in ansible play
  pcs_auth: node_name="{{  hostvars[item]['ansible_hostname'] }}" state='absent'
  with_items: "{{ play_hosts }}"

'''

import os.path
import json

def main():
        module = AnsibleModule(
                argument_spec = dict(
                        state=dict(default="present", choices=['present', 'absent']),
                        node_name=dict(required=True),
                        username=dict(required=False, default="hacluster"),
                        password=dict(required=False)
                ),
                supports_check_mode=True
        )

        state = module.params['state']
        node_name = module.params['node_name']

        if state == 'present' and not module.params['password']:
            module.fail_json(msg="Missing password parameter needed for authorizing the node")

        result = {}

        ## FIXME check if we have 'pcs' command

	if os.path.isfile('/var/lib/pcsd/tokens'):
	    tokens_file = open('/var/lib/pcsd/tokens','r+')
	    # load JSON tokens
	    tokens_data = json.load(tokens_file)

        rc, out, err = module.run_command('pcs cluster pcsd-status %(node_name)s' % module.params)

        if state == 'present' and rc != 0:
            # WARNING: this will also consider nodes to which we cannot connect as unauthorized
            result['changed'] = True
            if not module.check_mode:
                rc, out, err = module.run_command('pcs cluster auth %(node_name)s -u %(username)s -p %(password)s --local' % module.params)
                if rc == 0:
                    module.exit_json(changed=True)
                else:
                    module.fail_json(msg="Failed to authenticate node " + node_name)
        elif state == 'absent' and tokens_data and tokens_data['tokens'].has_key(node_name):
            result['changed'] = True
            if not module.check_mode:
		del tokens_data['tokens'][node_name]
		tokens_data['data_version'] += 1
		# write the change into token file
		tokens_file.seek(0)
		json.dump(tokens_data,tokens_file,indent=4)
		tokens_file.truncate()
        else:
            result['changed'] = False
            module.exit_json(changed=False)

        ## END of module
        module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()
