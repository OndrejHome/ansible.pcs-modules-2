#!/usr/bin/python

DOCUMENTATION = '''
---
author: "Ondrej Famera <ondrej-xa2iel8u@famera.cz>"
module: pcs_constraint_colocation
short_description: "wrapper module for 'pcs constraint colocation'"
description:
  - "module for creating and deleting clusters colocation constraints using 'pcs' utility"
version_added: "2.0"
options:
  state:
    description:
      - "'present' - ensure that cluster constraint exists"
      - "'absent' - ensure cluster constraints doesn't exist"
    required: false
    default: present
    choices: ['present', 'absent']
  resource1:
    description:
      - first resource for constraint
    required: true
  resource2:
    description:
      - second resource for constraint
    required: true
  resource1_role:
    description:
      - Role of resource1
    required: false
    choices: ['Master', 'Slave']
  resource2_role:
    description:
      - Role of resource2
    required: false
    choices: ['Master', 'Slave']
  score:
    description:
      - constraint score in range -INFINITY..0..INFINITY
    required: false
    default: 'INFINITY'
notes:
   - tested on CentOS 7.3
   - no extra options allowed for constraints
   - "TODO: validation of resource names, score values"
'''

EXAMPLES = '''
- name: prefer resA and resB to run on same node
  pcs_constraint_colocation: resource1='resA' resource2='resB'

- name: prefer resA to run on same node as Master resource of resB-master resource
  pcs_constraint_colocation: resource1='resA' resource2='resB-master' resource2_role='Master'
'''

import os.path
import xml.etree.ElementTree as ET
from distutils.spawn import find_executable

def main():
        module = AnsibleModule(
                argument_spec = dict(
                        state=dict(default="present", choices=['present', 'absent']),
                        resource1=dict(required=True),
                        resource2=dict(required=True),
                        resource1_role=dict(required=False, choices=['Master', 'Slave']),
                        resource2_role=dict(required=False, choices=['Master', 'Slave']),
                        score=dict(required=False, default="INFINITY"),
                ),
                supports_check_mode=True
        )

        state = module.params['state']
        resource1 = module.params['resource1']
        resource2 = module.params['resource2']
        resource1_role = module.params['resource1_role']
        resource2_role = module.params['resource2_role']
        score = module.params['score']

        result = {}

        if find_executable('pcs') is None:
            module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")

        ## get running cluster configuration
        rc, out, err = module.run_command('pcs cluster cib')
        if rc == 0:
            current_cib_root = ET.fromstring(out)
        else:
            module.fail_json(msg='Failed to load current cluster configuration')
        
        ## try to find the constraint we have defined
        constraint = None
        with_roles = False
        role1,role2,detected_role1,detected_role2 = None, None, None, None
        # resolve resource roles if they were provided
        if resource1_role or resource2_role:
            role1 = 'Started' if not resource1_role else resource1_role
            role2 = 'Started' if not resource2_role else resource2_role
            with_roles = True
        constraints = current_cib_root.findall("./configuration/constraints/rsc_colocation")
        for constr in constraints:
            # constraint is considered found if we see resources with same names and order as given to module
            if constr.attrib.get('rsc') == resource1 and constr.attrib.get('with-rsc') == resource2:
                constraint = constr
                detected_role1 = 'Started' if not constr.attrib.get('rsc-role') else constr.attrib.get('rsc-role')
                detected_role2 = 'Started' if not constr.attrib.get('with-rsc-role') else constr.attrib.get('with-rsc-role')
                break

        # additional variables for verbose output
        result.update( {
            'old_score': None if constraint is None else constraint.attrib.get('score'), 'new_score': score,
            'old_role1': detected_role1, 'new_role1': role1,
            'old_role2': detected_role2, 'new_role2': role2
        } )

        # colocation constraint creation command
        if with_roles == True:
            if resource1_role is not None and resource2_role is not None:
                cmd_create='pcs constraint colocation add %(resource1_role)s %(resource1)s with %(resource2_role)s %(resource2)s %(score)s' % module.params
            elif resource1_role is not None and resource2_role is None:
                cmd_create='pcs constraint colocation add %(resource1_role)s %(resource1)s with %(resource2)s %(score)s' % module.params
            elif resource1_role is None and resource2_role is not None:
                cmd_create='pcs constraint colocation add %(resource1)s with %(resource2_role)s %(resource2)s %(score)s' % module.params
        else:
            cmd_create='pcs constraint colocation add %(resource1)s with %(resource2)s %(score)s' % module.params

        if state == 'present' and constraint is None:
            # constraint should be present, but we don't see it in configuration - lets create it
            result['changed'] = True
            if not module.check_mode:
                rc, out, err = module.run_command(cmd_create)
                if rc == 0:
                    module.exit_json(changed=True)
                else:
                    module.fail_json(msg="Failed to create constraint with cmd: '" + cmd_create + "'", output=out, error=err)

        elif state == 'present' and constraint is not None:
            # constraint should be present based on resource names and order, lets check the scores and roles
            if constraint.attrib.get('score') != score or (role1 is not None and role1 != detected_role1) or (role2 is not None and role2 != detected_role2):
                result['changed'] = True
                if not module.check_mode:
                    rc, out, err = module.run_command('pcs constraint delete '+ constraint.attrib.get('id'))
                    if rc != 0:
                        module.fail_json(msg="Failed to delete constraint for replacement with cmd: '" + cmd + "'", output=out, error=err)
                    else:
                        rc, out, err = module.run_command(cmd_create)
                        if rc == 0:
                            module.exit_json(changed=True)
                        else:
                            module.fail_json(msg="Failed to create constraint replacement with cmd: '" + cmd_create + "'", output=out, error=err)
                   
        elif state == 'absent' and constraint is not None:
            # constraint should not be present but we have found something - lets remove that
            result['changed'] = True
            if not module.check_mode:
                rc, out, err = module.run_command('pcs constraint delete '+ constraint.attrib.get('id'))
                if rc == 0:
                    module.exit_json(changed=True)
                else:
                    module.fail_json(msg="Failed to delete constraint with cmd: '" + cmd + "'", output=out, error=err)
        else:
            # constraint should not be present and is not there, nothing to do
            result['changed'] = False

        ## END of module
        module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()
