#!/usr/bin/python
# Copyright: (c) 2018, Ondrej Famera <ondrej-xa2iel8u@famera.cz>
# GNU General Public License v3.0+ (see LICENSE-GPLv3.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# Apache License v2.0 (see LICENSE-APACHE2.txt or http://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

import time

__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
author: "Roman Kislinskii (@Hoijima)"
module: pcs_wait_for
short_description: "wrapper module for 'pcs resource' "
description:
     - "Module for stopping and starting resources using 'pcs' utility."
     - "This module should be executed for same resource only on one of the nodes in cluster at a time."
version_added: "2.4"
options:
  resource_name:
    description:
      - "name of cluster resource - cluster resource identifier"
    required: true
  resource_state:
    description:
      - "'started' - ensure that cluster resource has meta attribute started"
      - "'stopped' - ensure that cluster resource has meta attribute stopped"
    required: false
    default: present
    choices: ['started', 'stopped']

  child_name:
    description:
      - "define custom name of child resource when creating multistate resource ('master' or 'promotable' resource_class)."
      - "If not specified then the child resource name will have for of name+'-child'."
    required: false
notes:
   - tested on CentOS Linux release 7.5.1804 (Core)
'''

EXAMPLES = '''
- name: Start service
  pcs_wait_for:
    resource_name: nginx
    resource_state: started

- name: Stop service
  pcs_wait_for:
    resource_name: nginx
    resource_state: stopped

'''

# TODO if group exists and is not part of group, then specifying group won't put it into group
# same problem is with clone and master - it might be better to make this functionality into separate module

import sys
import os.path
import xml.etree.ElementTree as ET
import tempfile
import re
import json
from distutils.spawn import find_executable
from ansible.module_utils.basic import AnsibleModule

# determine if we have 'to_native' function that we can use for 'ansible --diff' output
to_native_support = False
try:
    from ansible.module_utils._text import to_native

    to_native_support = True
except ImportError:
    pass

def find_resource(cib, resource_id):
    my_resource = None
    tags = ['group', 'clone', 'master', 'primitive']
    for elem in list(cib):
        if elem.attrib.get('id') == resource_id:
            return elem
        elif elem.tag in tags:
            my_resource = find_resource(elem, resource_id)
            if my_resource is not None:
                break
    return my_resource

def run_module():
    module = AnsibleModule(
        argument_spec=dict(
            resource_name=dict(required=True),
            resource_state=dict(default="present", choices=['started', 'stopped']),
            delay=dict(required=False, default=0, type='int'),#delay first check for 10 seconds - optional
            sleep=dict(required=False, default=15, type='int') #wait 5 seconds between checks - optional
        ),
        supports_check_mode=True
    )

    resource_state = module.params['resource_state']
    resource_name = module.params['resource_name']
    delay = module.params['delay']
    sleep = module.params['sleep']
    result = {}

    if resource_name is not None:

        resource_states = {"started": "Started", "starting": "Staring", "stopped": "Stopped", "stopping": "Stopping",
                           "failed": "FAILED", "blocked": "blocked", "disabled": "disabled"}

        resource_state_regexp = {}
        for key in resource_states.keys():
            resource_state_regexp[key] = re.compile(resource_states[key])

        if not module.check_mode:



            res_name, res_state, res_host, res_add_state = check_status(resource_name, module, delay)
            cmd = 'pcs resource cleanup %(resource_name)s' % module.params
            rc, out, err = module.run_command(cmd)
            if rc == 0:
                pass
            else:
                module.fail_json(msg="Failed cleanup resource %(resource_name)s") % module.params

            if resource_state == 'started':
                if resource_state_regexp['started'].search(res_state):
                    module.exit_json(changed=False)
                if resource_state_regexp['starting'].search(res_state):
                    for i in range(1, 5):
                        time.sleep(sleep)
                        res_name, res_state, res_host, res_add_state = check_status(resource_name, module, delay)
                        if resource_state_regexp['starting'].search(res_state):
                            pass
                    if resource_state_regexp['starting'].search(res_state):
                        module.exit_json(changed=True)

                if resource_state_regexp['stopping'].search(res_state):
                    for i in range(1, 5):
                        time.sleep(sleep)
                        res_name, res_state, res_host, res_add_state = check_status(resource_name, module, delay)
                        if resource_state_regexp['stopping'].search(res_state):
                            pass
                        else:
                            break
                    if resource_state_regexp['stopping'].search(res_state):
                        module.fail_json(
                            msg="Failed to wait until the resource went down, check resource %(resource_name)s") % module.params

                res_name, res_state, res_host, res_add_state = check_status(resource_name, module, delay)
                if resource_state_regexp['stopped'].search(res_state) or resource_state_regexp['failed'].search(
                        res_state):

                    cmd = 'pcs resource cleaup %(resource_name)s' % module.params
                    module.run_command(cmd)
                    time.sleep(sleep)
                    cmd = 'pcs resource meta %(resource_name)s target-role=Started' % module.params
                    rc, out, err = module.run_command(cmd)

                    if rc == 0:
                        time.sleep(sleep)
                        res_name, res_state, res_host, res_add_state = check_status(resource_name, module, delay)
                        if resource_state_regexp['started'].search(res_state):
                            module.exit_json(changed=True)
                        if resource_state_regexp['starting'].search(res_state):
                            module.exit_json(changed=True)
                        if resource_state_regexp['failed'].search(res_state):
                            module.fail_json(msg=res_name + " Failed to start")


            if resource_state == 'stopped':
                if resource_state_regexp['stopped'].search(res_state):
                    module.exit_json(changed=False)
                if resource_state_regexp['stopping'].search(res_state):
                    for i in range(1, 5):
                        time.sleep(sleep)
                        res_name, res_state, res_host, res_add_state = check_status(resource_name, module, delay)
                        if resource_state_regexp['stopping'].search(res_state):
                            pass
                        else:
                            module.exit_json(changed=True)
                    module.exit_json(changed=True)


                if resource_state_regexp['starting'].search(res_state):
                    for i in range(1, 5):
                        time.sleep(sleep)
                        res_name, res_state, res_host, res_add_state = check_status(resource_name, module, delay)
                        if resource_state_regexp['starting'].search(res_state):
                            pass
                        else:
                            break
                    if resource_state_regexp['starting'].search(res_state):
                        module.fail_json(
                            msg="Failed to wait until the resource went up,to stop it afterwards, check resource %(resource_name)s") % module.params

                res_name, res_state, res_host, res_add_state = check_status(resource_name, module, delay)
                if resource_state_regexp['started'].search(res_state) or resource_state_regexp['failed'].search(
                        res_state):
                    cmd = 'pcs resource meta %(resource_name)s target-role=Stopped' % module.params
                    rc, out, err = module.run_command(cmd)
                    if rc == 0:
                        time.sleep(sleep)
                        res_name, res_state, res_host, res_add_state = check_status(resource_name, module, delay)
                        if resource_state_regexp['stopped'].search(res_state):
                            module.exit_json(changed=True)
                        if resource_state_regexp['stopping'].search(res_state):
                            module.exit_json(changed=True)
                        if resource_state_regexp['failed'].search(res_state):
                            module.exit_json(changed=True, msg=res_name + " Stopped but status Failed")

                    else:
                        module.fail_json(msg="Failed to disable resource using command '" + cmd + "'", output=out,
                                         error=err)

            cmd = 'pcs resource cleanup %(resource_name)s' % module.params
            rc, out, err = module.run_command(cmd)
            if rc == 0:
                pass
            else:
                module.fail_json(msg="Failed cleanup resource %(resource_name)s") % module.params
    else:
        # resource should not be present and is nto there, nothing to do
        result['changed'] = False

    # END of module
    module.exit_json(**result)


def check_status(resource, module, delay):
    # get resource state
    time.sleep(delay)
    cmd = 'pcs resource show'

    rc, out, err = module.run_command(cmd)

    content = out.splitlines()

    resource_regexp = re.compile(resource)

    res_name, res_state, res_host, res_add_state = "", "", "", ""
    for res in content:
        if resource_regexp.search(res):
            splitted = res.split("\t")

            if len(splitted[2].split(" ")) == 1:
                res_name, res_state, res_host, res_add_state = splitted[0].replace(" ", ""), splitted[2].split(" ")[0], "", ""

            if len(splitted[2].split(" ")) == 2:

                if re.compile("disabled").search(splitted[2].split(" ")[1]):
                    res_name, res_state, res_host, res_add_state = splitted[0].replace(" ", ""), splitted[2].split(" ")[0], "", splitted[2].split(" ")[1]
                else:
                    res_name, res_state, res_host, res_add_state = splitted[0].replace(" ", ""), splitted[2].split(" ")[0], splitted[2].split(" ")[1], ""
            if len(splitted[2].split(" ")) == 3:
                res_name, res_state, res_host, res_add_state = splitted[0].replace(" ", ""), splitted[2].split(" ")[0], splitted[2].split(" ")[1] , splitted[2].split(" ")[2]

    return res_name, res_state, res_host, res_add_state



def main():
    run_module()


if __name__ == '__main__':
    main()
