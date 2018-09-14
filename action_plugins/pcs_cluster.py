from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.errors import AnsibleError, AnsibleAction, AnsibleActionFail, AnsibleActionSkip, AnsibleOptionsError
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
            raise AnsibleOptionsError('Only one option of "allow_node_add" or "allow_node_remove" can be enabled.')

        # first lets check how many hosts reports to be part of cluster and deduct some other things
        node_list_set = set(node_list.split())
        cluster_hosts = 0
        independent_cluster = True # True if there are no common nodes between node_list and what was detected on all nodes
        for host in task_vars['play_hosts']:
            if boolean(task_vars['hostvars'][host]['pacemaker_cluster_present'], strict=False):
                cluster_hosts += 1
                if len(node_list_set.intersection(set(task_vars['hostvars'][host]['pacemaker_detected_cluster_nodes']))) > 0:
                    independent_cluster = False

        execute_host = ''

        # (scenario A) when we don't want cluster to exist and no hosts reports cluster to be present
        if cluster_hosts == 0 and state == 'absent':
            raise AnsibleActionSkip("No cluster detected on any of the nodes")
        
        # (scenario B) when we don't want cluster to be present and there are nodes with cluster
        if cluster_hosts > 0 and state == 'absent':
            # this will just destroy cluster on given nodes. IMPORTANT: this may cause that if not all cluster
            # nodes were specified in play, then the ones that remain will still see the nodes in their CIB.
            result = merge_hash(result, self._execute_module(task_vars=task_vars))

        # (scenario C) when we want cluster to be present and there are no nodes reporting existing cluster on them
        if cluster_hosts == 0 and state == 'present':
            # just run the module without any special options, make sure that we unset the special options
            allow_node_remove = False
            allow_node_add = False
            if node_list.split()[0] == this_host_name:
                result = merge_hash(result, self._execute_module(task_vars=task_vars))
            else:
                raise AnsibleActionSkip("Cluster will be created from node %s" % node_list.split()[0])

        # lets check the discrepancies between detected_nodes and node_list
        detected_node_list_set = set()
        if 'pacemaker_detected_cluster_nodes' in task_vars['hostvars'][this_host]:
            detected_node_list_set = set(task_vars['hostvars'][this_host]['pacemaker_detected_cluster_nodes'])

        this_host_name = task_vars['hostvars'][this_host]['ansible_fqdn'].split('.')[0]

        # (scenario D) when we want cluster to be present and there are nodes with cluster
        if cluster_hosts > 0 and state == 'present':

            ## Sanity checks

            # FIXME: detect discrepancies in detected_node_list among nodes reporting cluster, refuse to continue if such thing happens

            # D.1 node_list requested matches what node reports, no changes needed
            if node_list_set == detected_node_list_set:
                raise AnsibleActionSkip("Cluster present, but no changes in node membership are needed on this host.")
 
            # D.2 there are no common nodes between node_list and what we see on node, refuse to continue
            if len(detected_node_list_set) > 0 and node_list_set.isdisjoint(detected_node_list_set) and ( allow_node_add or allow_node_remove ):
                raise AnsibleError('Requested node_list and list of nodes detected on this node have no common nodes (%s - %s)' % (node_list_set,detected_node_list_set))

            # D.4 skip node that doesn't have cluster and was not requested to be part of cluster
            if not boolean(task_vars['hostvars'][this_host]['pacemaker_cluster_present'], strict=False) and this_host_name not in node_list_set:
                raise AnsibleActionSkip("This node is not part of cluster and will not be added to cluster as it was not requested")

            # D.5 skip node that that is in cluster unrelated to one being operated
            if boolean(task_vars['hostvars'][this_host]['pacemaker_cluster_present'], strict=False) and this_host_name not in node_list_set and node_list_set.isdisjoint(detected_node_list_set):
                raise AnsibleActionSkip("This node is part of cluster that is unrelated to one that was requested to be changed/created by module.")
            
            ## all nodes that detected cluster are not part of node_list_set and this node is not running cluster
            independent_cluster = True
            for hh in task_vars['play_hosts']:
                if boolean(task_vars['hostvars'][hh]['pacemaker_cluster_present'], strict=False) and len(node_list_set.intersection(set(task_vars['hostvars'][hh]['pacemaker_detected_cluster_nodes']))) > 0:
                    independent_cluster = False

            # D.6 pass control to pcs_cluster module when we are creating a new cluster in play where some other cluster exists on other nodes
            if not boolean(task_vars['hostvars'][this_host]['pacemaker_cluster_present'], strict=False) and this_host_name in node_list_set and independent_cluster:
                allow_node_remove = False
                allow_node_add = False
                if node_list.split()[0] == this_host_name:
                    result = merge_hash(result, self._execute_module(task_vars=task_vars))
                else:
                    raise AnsibleActionSkip("Cluster will be created from node %s" % node_list.split()[0])

            ##### actual operations
            # D.X1 Adding the nodes to cluster
            if allow_node_add and len(node_list_set - detected_node_list_set) > 0:
                # there are nodes that are in node_list but not detected on current node

                # check if we are not trying to add node already participating in some other cluster
                for add_node in (node_list_set - detected_node_list_set):
                    if boolean(task_vars['hostvars'][host]['pacemaker_cluster_present'], strict=False):
                        raise AnsibleError('Nodes that should be added to cluster must not be part of other cluster')

                # lets determine which node in cluster adds nodes
                for host in task_vars['play_hosts']:
                    # first node that has cluster and is part of node_list will add new nodes
                    # Note for further development: we may consider searching the 'detected_node_list' here instaed of 'node_list'
                    if boolean(task_vars['hostvars'][host]['pacemaker_cluster_present'], strict=False) and task_vars['hostvars'][host]['ansible_fqdn'].split('.')[0] in node_list_set:
                        # we are the node that will be adding the nodes
                        execute_host = host
                        break

                if this_host == execute_host:
                    # this node will be adding nodes to cluster
                    result = merge_hash(result, self._execute_module(task_vars=task_vars))
                elif this_host_name in node_list_set and this_host_name not in detected_node_list_set:
                    raise AnsibleActionSkip("This node will be added to cluster by node %s." % execute_host)
                elif this_host_name in node_list_set and this_host_name in detected_node_list_set:
                    raise AnsibleActionSkip("No changes in node membership are needed on this host.")

            # D.X2 Removing the nodes from cluster 
            if allow_node_remove and len(detected_node_list_set - node_list_set) > 0:
                # there are nodes that are detected on node, but not present in node_list

                # TODO: for EL7 the node cannot remove itself from cluster without help from another node - https://bugzilla.redhat.com/show_bug.cgi?id=1360882

                # lets determine which node in cluster removes nodes
                for host in task_vars['play_hosts']:
                    if boolean(task_vars['hostvars'][host]['pacemaker_cluster_present'], strict=False) and task_vars['hostvars'][host]['ansible_fqdn'].split('.')[0] in node_list_set:
                        # we are the node that will be removing the nodes
                        execute_host = host
                        break

                if this_host == execute_host:
                    # this node will be removing nodes from cluster
                    result = merge_hash(result, self._execute_module(task_vars=task_vars))
                elif this_host_name not in node_list_set and this_host_name in detected_node_list_set:
                    raise AnsibleActionSkip("This node will be removed from cluster by node %s." % execute_host)
                elif this_host_name in node_list_set and this_host_name in detected_node_list_set:
                    raise AnsibleActionSkip("No changes in node membership are needed on this host.")

        return result
