from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.errors import AnsibleError, AnsibleAction, AnsibleActionFail, AnsibleActionSkip
from ansible.module_utils.parsing.convert_bool import boolean
from ansible.plugins.action import ActionBase
from ansible.utils.vars import merge_hash

class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):

        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect

        ####
        this_host = task_vars.get('inventory_hostname')
        state = self._task.args.get('state', 'present')
        allow_node_remove = boolean(self._task.args.get('allow_node_remove', False), strict=False)
        allow_node_add = boolean(self._task.args.get('allow_node_add', False), strict=False)
        node_list = self._task.args.get('node_list', '')

        ## Sanity check - allow only one operation at a time
        # while it is possible to make both, this way this enforces that one writing a playbook will
        # decide which operation is first - adding the nodes or removing them
        if allow_node_remove and allow_node_add:
            raise AnsibleError('Only one option of "allow_node_add" or "allow_node_remove" can be enabled.')

        # first lets check how many hosts reports to be part of cluster
        cluster_hosts = 0
        for host in task_vars['play_hosts']:
            if boolean(task_vars['hostvars'][host]['cluster_present'], strict=False):
                cluster_hosts += 1

        execute_host = ''

        # (scenario A) when we don't want cluster to exist and no hosts reports cluster to be present
        if cluster_hosts == 0 and state == 'absent':
            raise AnsibleActionSkip("No cluster detected on any of the nodes")
        
        # (scenario B) when we don't want cluster to be present and there are nodes with cluster
        if cluster_hosts > 0 and state == 'absent':
            # remove cluster from nodes unconditionally 
            # we don't consider allow_node_remove when "state=absent" is used!
            execute_host = this_host
            allow_node_remove = True

        # lets check the discrepancies between detected_nodes and node_list
        node_list_set = set(node_list.split())
        detected_node_list_set = set()
        if 'detected_cluster_nodes' in task_vars['hostvars'][this_host]:
            detected_node_list_set = set(task_vars['hostvars'][this_host]['detected_cluster_nodes'].split())

        this_host_name = task_vars['hostvars'][this_host]['ansible_fqdn'].split('.')[0]

        # (scenario C) when we want cluster to be present and there are nodes with cluster
        if cluster_hosts > 0 and state == 'present':

            # if there are no common nodes, refuse to continue
            if len(detected_node_list_set) > 0 and node_list_set.isdisjoint(detected_node_list_set):
                raise AnsibleError('Requested node_list and list of nodes detected on this node have no common nodes (%s - %s)' % (node_list_set,detected_node_list_set))

            # node_list requested matches what node reports, no changes needed
            if node_list_set == detected_node_list_set:
                raise AnsibleActionSkip("Cluster present, but no changes in node membership are needed.")
 
            if allow_node_add and len(node_list_set - detected_node_list_set) > 0:
                # there are nodes that are in node_list but not detected on node
                if this_host_name in (node_list_set - detected_node_list_set):
                    # this host needs to be added, but we cannot add node from itself, skip
                    raise AnsibleActionSkip("This node will be added by other node into cluster.")
                else:
                    # if we are the other node, we need to deterministically determine if we should be the node that adds new nodes to cluster
                    # first node from node_list that has cluster_present=true adds new nodes
                    for host in task_vars['play_hosts']:
                        if boolean(task_vars['hostvars'][host]['cluster_present'], strict=False) and this_host_name in node_list_set:
                            # we are the node that will be adding the nodes
                            execute_host = host
                            break
                
            elif allow_node_remove and len(detected_node_list_set - node_list_set) > 0:
                # there are nodes that are detected on node, but not present in node_list
                if this_host_name in (detected_node_list_set - node_list_set):
                    # remove this host directly by calling pcs_cluster state=absent
                    execute_host = this_host
                else:
                    # skip, this host should not be removed
                    raise AnsibleActionSkip("Cluster present, and this node should stay part of cluster.")
            else:
                # here we need to explain the situations that leads to this, all of them are without action
                if not boolean(task_vars['hostvars'][this_host]['cluster_present'], strict=False) and this_host_name not in node_list_set:
                    raise AnsibleActionSkip("This node is not part of cluster and will not be added to cluster as it was not requested")

                # unimplemented behaviour
                raise AnsibleActionSkip("This situation is not implemented, allow_add: %s, allow_remove: %s " % (allow_node_add,allow_node_remove))

        if execute_host == this_host:
            # add or remove nodes
            if allow_node_remove:
                task_vars['state'] = 'absent'
                result = merge_hash(result, self._execute_module(task_vars=task_vars))
                #return result
                raise AnsibleError('This node will remove itself from cluster')
            if allow_node_add:
                result = merge_hash(result, self._execute_module(task_vars=task_vars))
                #return result
                raise AnsibleError('This node will add nodes %s to cluster' % (node_list_set - detected_node_list_set))
        else:
            raise AnsibleActionSkip("There are nodes that needs to be added/removed but not by this node")

        raise AnsibleError('xxxx')

        return result
