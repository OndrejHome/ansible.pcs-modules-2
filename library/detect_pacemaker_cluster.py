#!/usr/bin/python

DOCUMENTATION = '''
---
module: detect_pacemaker_cluster
short_description: detect facts about installed pacemaker cluster
description:
     - Module for collecting various information about pacemaker cluster
version_added: "2.4"
options:
notes:
   - Tested on CentOS 7.5
   - works only with pacemaker clusters that uses /etc/corosync/corosync.conf
requirements: [ ]
author: "Ondrej Famera <ondrej-xa2iel8u@famera.cz>"
'''

EXAMPLES = '''
- detect_pacemaker_cluster

'''


def main():
        module = AnsibleModule(
                argument_spec=dict(),
                supports_check_mode=True
        )

        result = {}

        try:
            corosync_conf = open('/etc/corosync/corosync.conf', 'r')
            nodes = re.compile(r"node\s*\{([^}]+)\}", re.M+re.S)
            nodes_list = nodes.findall(corosync_conf.read())
            node_list_set = set()
            if len(nodes_list) > 0:
                n_name = re.compile(r"ring0_addr\s*:\s*([\w.-]+)\s*", re.M)
                for node in nodes_list:
                    n_name2 = None
                    n_name2 = n_name.search(node)
                    if n_name2:
                        node_name = n_name2.group(1)
                        node_list_set.add(node_name.rstrip())

            result['ansible_facts'] = {}
            result['ansible_facts']['pacemaker_detected_cluster_nodes'] = node_list_set
            result['ansible_facts']['pacemaker_cluster_present'] = True
        except IOError as e:
            result['ansible_facts'] = {}
            result['ansible_facts']['pacemaker_cluster_present'] = False
        except OSError as e:
            result['ansible_facts'] = {}
            result['ansible_facts']['pacemaker_cluster_present'] = False
        module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()
