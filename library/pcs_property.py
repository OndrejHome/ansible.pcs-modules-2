#!/usr/bin/python

DOCUMENTATION = '''
---
author: "Ondrej Famera <ondrej-xa2iel8u@famera.cz>"
module: pcs_property
short_description: "wrapper module for 'pcs property'"
description:
  - "module for setting and unsetting clusters properties using 'pcs' utility"
version_added: "2.0"
options:
  state:
    description:
      - "'present' - ensure that cluster property exists with given value"
      - "'absent' - ensure cluster property doesn't exist (is unset)"
    required: false
    default: present
    choices: ['present', 'absent']
  name:
    description:
      - name of cluster property
    required: true
  value:
    description:
      - value of cluster property
    required: false
notes:
   - tested on CentOS 7.3
'''

EXAMPLES = '''
- name: set maintenance mode cluster property (enable maintenance mode)
  pcs_property: name='maintenance-mode' value='true'

- name: unset maintenance mode cluster property (disable maintenance mode)
  pcs_property: name='maintenance-mode' state='absent'
'''

from distutils.spawn import find_executable

def main():
        module = AnsibleModule(
                argument_spec = dict(
                        state=dict(default="present", choices=['present', 'absent']),
                        name=dict(required=True),
                        value=dict(required=False),
                ),
                supports_check_mode=True
        )

        state = module.params['state']
        name = module.params['name']
        value = module.params['value']

        result = {}

        if find_executable('pcs') is None:
            module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")

        if state == 'present' and value is None:
            module.fail_json(msg="To set property 'value' must be specified.")
           
        ## get property list from running cluster
        rc, out, err = module.run_command('pcs property show')
        properties={}
        if rc == 0:
            # we are stripping first and last line as they doesn't contain properties
            for row in out.split('\n')[1:-1]:
                tmp=row.lstrip().split(':')
                properties[tmp[0]]=tmp[1].lstrip()
        else:
            module.fail_json(msg='Failed to load properties from cluster. Is cluster running?')

        result['detected_properties'] = properties

        if state == 'present' and (name not in properties or properties[name] != value):
            # property not found or having a different value
            result['changed'] = True
            if not module.check_mode:
                cmd_set = 'pcs property set %(name)s=%(value)s' % module.params
                rc, out, err = module.run_command(cmd_set)
                if rc == 0:
                    module.exit_json(**result)
                else:
                    module.fail_json(msg="Failed to set property with cmd : '" + cmd_set + "'", output=out, error=err)

        elif state == 'absent' and name in properties:
            # property found but it should not be set
            result['changed'] = True
            if not module.check_mode:
                cmd_unset = 'pcs property unset %(name)s' % module.params
                rc, out, err = module.run_command(cmd_unset)
                if rc == 0:
                    module.exit_json(**result)
                else:
                    module.fail_json(msg="Failed to unset property with cmd: '" + cmd_unset + "'", output=out, error=err)
        else:
            # No change needed
            result['changed'] = False

        ## END of module
        module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()
