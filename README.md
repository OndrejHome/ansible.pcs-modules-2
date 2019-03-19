pcs-modules-2
=============

Ansible modules for configuring pacemaker cluster on CentOS/RHEL 6/7 and Fedora 29 systems.

If you are looking for a role that will configure a basic pacemaker cluster on CentOS/RHEL 6/7 or Fedora 29 systems, then check out the [OndrejHome.ha-cluster-pacemaker](https://github.com/OndrejHome/ansible.ha-cluster-pacemaker) role that uses the pcs-modules-2.

Note that modules manipulating with cluster configuration such as `pcs_resource`, `pcs_constraint_*`, `pcs_property` and `pcs_resource_defaults` should be run only from one of the cluster nodes in cluster by using either `run_once: True` or `delegate_to:` options.

Requirements
------------

RHEL: It is expected that machines will already be registered and subscribed for access to 'High Availability' or 'Resilient storage' channels.

Role Variables
--------------

None. This role is intended to be included as dependency.

Provided Modules
----------------

*pcs_auth* - (de)authorization of nodes in pacemaker cluster

*pcs_resource* - create/update/delete cluster resources in pacemaker cluster including stonith resources

*pcs_constraint_location* - create/delete cluster location constraints in pacemaker cluster

*pcs_constraint_colocation* - create/delete cluster colocation constraints in pacemaker cluster

*pcs_constraint_order* - create/delete cluster order constraints in pacemaker cluster

*pcs_cluster* - create/destroy pacemaker cluster, adds/removes nodes to/from existing clusters

*pcs_property* - set/unset pacemaker cluster properties

*pcs_resource_defaults* - set/unset resource defaults and resource operation defaults

*detect_pacemaker_cluster* - fact collecting module for collecting various information about pacemaker cluster (currently only the nodes cluster considers to be part of)

Example Playbook
----------------

Example playbook for including modules in your playbook

    - hosts: servers
      roles:
         - { role: OndrejHome.pcs-modules-2 }

Use the `ansible-doc` command to get more information about each module and to see examples of its use.

    ansible-doc -M library/ pcs_resource

License
-------

GPLv3 or Apache License 2.0, check LICENSE file for more information

Author Information
------------------

WARNING: Despite the modules are used by the Author regularly they are tested only manually

To get in touch with author you can use email ondrej-xa2iel8u@famera.cz or create a issue on github when requesting some feature.
