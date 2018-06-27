#!/usr/bin/python

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
author: "Ondrej Famera <ondrej-xa2iel8u@famera.cz>"
module: pcs_constraint_order
short_description: "wrapper module for 'pcs constraint order'"
description:
  - "module for creating and deleting clusters order constraints using 'pcs' utility"
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
  resource1_action:
    description:
      - action to which constraint applies for resource1
    required: false
    choices: ['start','promote','demote','stop']
    default: 'start'
  resource2_action:
    description:
      - action to which constraint applies for resource2
    required: false
    choices: ['start','promote','demote','stop']
    default: 'start'
  kind:
    description:
      - Kind of the order constraint
    required: false
    choices: ['Optional','Mandatory','Serialize']
    default: 'Mandatory'
  symmetrical:
    description:
      - Is the constraint symmetrical?
    required: false
    choices: ['true','false']
    default: 'true'
  cib_file:
    description:
      - "Apply changes to specified file containing cluster CIB instead of running cluster."
      - "This module requires the file to already contain cluster configuration."
    required: false
notes:
   - tested on CentOS 7.3
'''

EXAMPLES = '''
- name: start resA before starting resB
  pcs_constraint_order: resource1='resA' resource2='resB'

- name: make Optional order constraint where resA should start before resB
  pcs_constraint_order: resource1='resA' resource2='resB' kind='Optional'

- name: start resB after resA was promoted
  pcs_constraint_order: resource1='resA' resource1_action='promote' resource2='resB'

- name: start resA before starting resB but don't require that resB stope before resA
  pcs_constraint_order: resource1='resA' resource2='resB' symmetrical='false'

- name: remove order constraint between resA and resB
  pcs_constraint_order: resource='resA' resource2='resB' state='absent'
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
                        resource1_action=dict(required=False, choices=['start', 'promote', 'demote', 'stop'], default='start'),
                        resource2_action=dict(required=False, choices=['start', 'promote', 'demote', 'stop'], default='start'),
                        kind=dict(required=False, choices=['Optional', 'Mandatory', 'Serialize'], default='Mandatory'),
                        symmetrical=dict(required=False, choices=['true', 'false'], default='true'),
                        cib_file=dict(required=False),
                ),
                supports_check_mode=True
        )

        state = module.params['state']
        resource1 = module.params['resource1']
        resource2 = module.params['resource2']
        resource1_action = module.params['resource1_action']
        resource2_action = module.params['resource2_action']
        kind = module.params['kind']
        symmetrical = module.params['symmetrical']
        cib_file = module.params['cib_file']

        result = {}

        if find_executable('pcs') is None:
            module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")

        module.params['cib_file_param'] = ''
        if cib_file is not None:
            ## use cib_file if specified
            if os.path.isfile(cib_file):
                try:
                    current_cib = ET.parse(cib_file)
                except Exception as e:
                    module.fail_json(msg="Error encountered parsing the cib_file - %s" %(e) )
                current_cib_root = current_cib.getroot()
                module.params['cib_file_param'] = '-f ' + cib_file
            else:
                module.fail_json(msg="%(cib_file)s is not a file or doesn't exists" % module.params)
        else:
            ## get running cluster configuration
            rc, out, err = module.run_command('pcs cluster cib')
            if rc == 0:
                current_cib_root = ET.fromstring(out)
            else:
                module.fail_json(msg='Failed to load cluster configuration', out=out, error=err)
        
        ## try to find the constraint we have defined
        constraint = None
        constraints = current_cib_root.findall("./configuration/constraints/rsc_order")
        for constr in constraints:
            # constraint is considered found if we see resources with same names and order as given to module
            if constr.attrib.get('first') == resource1 and constr.attrib.get('then') == resource2:
                constraint = constr
                break

        # additional variables for verbose output
        result.update( {
            'resource1_action': None if constraint is None else constraint.attrib.get('first-action'),
            'resource2_action': None if constraint is None else constraint.attrib.get('then-action'),
            'kind': None if constraint is None else constraint.attrib.get('kind'),
            'symmetrical': None if constraint is None else constraint.attrib.get('symmetrical'),
        } )

        # order constraint creation command
        cmd_create='pcs %(cib_file_param)s constraint order %(resource1_action)s %(resource1)s then %(resource2_action)s %(resource2)s kind=%(kind)s symmetrical=%(symmetrical)s' % module.params

        # order constraint deletion command
        if constraint is not None:
            cmd_delete = 'pcs %(cib_file_param)s constraint delete ' % module.params + constraint.attrib.get('id')

        if state == 'present' and constraint is None:
            # constraint should be present, but we don't see it in configuration - lets create it
            result['changed'] = True
            if not module.check_mode:
                rc, out, err = module.run_command(cmd_create)
                if rc == 0:
                    module.exit_json(**result)
                else:
                    module.fail_json(msg="Failed to create constraint with cmd: '" + cmd_create + "'", output=out, error=err)

        elif state == 'present' and constraint is not None:
            # constraint should be present based on resource names and order, lets check the attributes
            if resource1_action != constraint.attrib.get('first-action')  or resource2_action != constraint.attrib.get('then-action') or (constraint.attrib.get('kind') is not None and constraint.attrib.get('kind') != kind) or (constraint.attrib.get('symmetrical') is not None and constraint.attrib.get('symmetrical') != symmetrical ):
                result['changed'] = True
                if not module.check_mode:
                    rc, out, err = module.run_command(cmd_delete)
                    if rc != 0:
                        module.fail_json(msg="Failed to delete constraint for replacement with cmd: '" + cmd_delete + "'", output=out, error=err)
                    else:
                        rc, out, err = module.run_command(cmd_create)
                        if rc == 0:
                            module.exit_json(**result)
                        else:
                            module.fail_json(msg="Failed to create constraint replacement with cmd: '" + cmd_create + "'", output=out, error=err)
                   
        elif state == 'absent' and constraint is not None:
            # constraint should not be present but we have found something - lets remove that
            result['changed'] = True
            if not module.check_mode:
                rc, out, err = module.run_command(cmd_delete)
                if rc == 0:
                    module.exit_json(**result)
                else:
                    module.fail_json(msg="Failed to delete constraint with cmd: '" + cmd_delete + "'", output=out, error=err)
        else:
            # constraint should not be present and is not there, nothing to do
            result['changed'] = False

        ## END of module
        module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()
