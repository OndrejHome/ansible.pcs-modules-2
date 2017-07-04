#!/usr/bin/python

DOCUMENTATION = '''
---
author: "Ondrej Famera <ondrej-xa2iel8u@famera.cz>"
module: pcs_constraint
short_description: "wrapper module for 'pcs constraint'"
description:
  - "module for creating and deleting clusters constraints using 'pcs' utility"
version_added: "2.0"
options:
  state:
    description:
      - "'present' - ensure that cluster constraint exists"
      - "'absent' - ensure cluster constraints doesn't exist"
    required: false
    default: present
    choices: ['present', 'absent']
  constraint_type:
    description:
      - type of the constraint
    required: true
    choices: ['order', 'location', 'colocation']
  resource1:
    description:
      - first resource for constraint
    required: true
  resource2:
    description:
      - second resource for constraint (order and colocation constraints only)
    required: false
  node_name:
    description:
      - node for constraint (only for location constraint)
    required: false
  score:
    description:
      - constraint score in range -INFINITY..0..INFINITY
    required: false
    default: 'INFINITY'
notes:
   - tested on CentOS 7.3
   - no extra options allowed for constraints
   - "TODO: validation of resource names, node names, score values"
'''

EXAMPLES = '''
- name: Ensure that resA starts before resB
  pcs_constraint: constraint_type='order' resource1='resA' resource2='resB'

- name: prefer resA and resB to run on same node
  pcs_constraint: constraint_type='colocation' resource1='resA' resource2='resB'

- name: resource resA prefers to run on node1
  pcs_constraint: constraint_type='location' resource1='resA' node_name='node1'

- name: resource resB avoids running on node2
  pcs_constraint: constraint_type='location' resource1='resB' node_name='node2' score='-INFINITY'
'''

import os.path
import xml.etree.ElementTree as ET
from distutils.spawn import find_executable

def main():
        module = AnsibleModule(
                argument_spec = dict(
                        state=dict(default="present", choices=['present', 'absent']),
                        constraint_type=dict(required=True, choices=['order', 'location', 'colocation']),
                        resource1=dict(required=True),
                        resource2=dict(required=False),
                        node_name=dict(required=False),
                        score=dict(required=False, default="INFINITY"),
                ),
                supports_check_mode=True
        )

        state = module.params['state']
        constraint_type = module.params['constraint_type']
        resource1 = module.params['resource1']
        resource2 = module.params['resource2']
        node_name = module.params['node_name']
        score = module.params['score']

        if constraint_type == 'location' and (not node_name):
            module.fail_json(msg='Location constraint requires node_name')
        if constraint_type != 'location' and (not resource2):
            module.fail_json(msg='Order and colocation constraints requires resource2')
        result = {}

        if find_executable('pcs') is None:
            module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")

        if constraint_type == 'colocation' or constraint_type == 'order':
            result["warnings"] = 'DEPRECATION: This module is deprecated for "' + constraint_type + '" constraint type! Use pcs_constraint_' + constraint_type + ' module instead.'

        ## get running cluster configuration
        rc, out, err = module.run_command('pcs cluster cib')
        if rc == 0:
            current_cib_root = ET.fromstring(out)
        else:
            module.fail_json(msg='Failed to load current cluster configuration')
        
        ## try to find the constraint we have defined
        constraint = None
        constraints = current_cib_root.findall("./configuration/constraints/rsc_" + constraint_type)
        for constr in constraints:
            if constraint_type == 'location' and constr.attrib.get('rsc') == resource1 and constr.attrib.get('node') == node_name:
                constraint = constr
                break
            if constraint_type == 'colocation' and constr.attrib.get('rsc') == resource1 and constr.attrib.get('with-rsc') == resource2:
                constraint = constr
                break
            if constraint_type == 'order' and constr.attrib.get('first') == resource1 and constr.attrib.get('then') == resource2:
                constraint = constr
                break

        if state == 'present' and constraint is None:
            # constraint should be present, but we don't see it in configuration - lets create it
            result['changed'] = True
            if not module.check_mode:
                if constraint_type == 'location':
                    cmd='pcs constraint location %(resource1)s prefers %(node_name)s=%(score)s' % module.params
                elif constraint_type == 'colocation':
                    cmd='pcs constraint colocation add %(resource1)s with %(resource2)s %(score)s' % module.params
                elif constraint_type == 'order':
                    cmd='pcs constraint order %(resource1)s then %(resource2)s' % module.params
                else:
                    module.fail_json(msg="This should not happen")
                rc, out, err = module.run_command(cmd)
                if rc == 0:
                    module.exit_json(**result)
                else:
                    module.fail_json(msg="Failed to create constraint: " + out)

        elif state == 'present' and constraint is not None and constraint_type != 'order':
            # constraint should be present and we have find constraint with same definition, lets check the scores

            if constraint.attrib.get('score') != score:
                result['changed'] = True
                if not module.check_mode:
                    rc, out, err = module.run_command('pcs constraint delete '+ constraint.attrib.get('id'))
                    if rc != 0:
                        module.fail_json(msg="Failed to delete constraint for replacement: " + out)
                    else:
                        if constraint_type == 'location':
                            cmd='pcs constraint location %(resource1)s prefers %(node_name)s=%(score)s' % module.params
                        elif constraint_type == 'colocation':
                            cmd='pcs constraint colocation add %(resource1)s with %(resource2)s %(score)s' % module.params
                        else:
                            module.fail_json(msg="This should not happen")
                        rc, out, err = module.run_command(cmd)
                        if rc == 0:
                            module.exit_json(**result)
                        else:
                            module.fail_json(msg="Failed to create constraint replacement: " + out)
                   
        elif state == 'absent' and constraint is not None:
            # constraint should not be present but we have found something - lets remove that
            result['changed'] = True
            if not module.check_mode:
                rc, out, err = module.run_command('pcs constraint delete '+ constraint.attrib.get('id'))
                if rc == 0:
                    module.exit_json(**result)
                else:
                    module.fail_json(msg="Failed to delete constraint: " + out)
        else:
            # constraint should not be present and is not there, nothing to do
            result['changed'] = False

        ## END of module
        module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()
