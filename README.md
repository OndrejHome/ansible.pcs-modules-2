pcs-modules-2
=============

Ansible modules for configuring pacemaker cluster on CentOS/RHEL 6/7/8/9, AlmaLinux 8/9/10 and Fedora 31/32/33/34/35/36/37/38/39/40/41/42 systems.

PCS versions supported:
- pcs-0.9
- pcs-0.10
- pcs-0.11
- pcs-0.12

If you are looking for a role that will configure a basic pacemaker cluster on CentOS/RHEL 6/7/8/9, AlmaLinux 8/9/10 or Fedora 31/32/33/34/35/36/37/38/39/40/41/42 systems, then check out the [ondrejhome.ha-cluster-pacemaker](https://github.com/OndrejHome/ansible.ha-cluster-pacemaker) role that uses the pcs-modules-2.

Note that modules manipulating with cluster configuration such as `pcs_resource`, `pcs_constraint_*`, `pcs_property`, `pcs_resource_defaults` and `pcs_stonith_level` should be run only from one of the cluster nodes in cluster by using either `run_once: True` or `delegate_to:` options.

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

*pcs_quorum_qdevice* - crete/delete qdevice in pacemaker cluster

*pcs_stonith_level* - crete/delete stonith levels in pacemaker cluster

*detect_pacemaker_cluster* - fact collecting module for collecting various information about pacemaker cluster (currently only the nodes cluster considers to be part of)

Example Playbook
----------------

Example playbook for including modules in your playbook

    - hosts: servers
      roles:
         - { role: ondrejhome.pcs-modules-2 }

Use the `ansible-doc` command to get more information about each module and to see examples of its use.

    ansible-doc -M library/ pcs_resource

Known issues and limitations
----------------------------

- RRP on EL7 is limited to 2 links and following message can be observed if more than 2 links are attempted. `pcs_cluster` module will consider only 2 links and ignore rest of specified silently to avoid this issue. If you have platform with `pcs-0.9` where you can create cluster with 3 or more redundant links (using `pcs`) then feel free to open issue and provide details.

    ~~~
    [MAIN  ] parse error in config: interface ring number 2 is bigger than allowed maximum 1
    ~~~


License
-------

GPLv3 or Apache License 2.0, check LICENSE file for more information

Author Information
------------------

WARNING: Despite the modules are used by the Author regularly they are tested only manually

To get in touch with author you can use email ondrej-xa2iel8u@famera.cz or create a issue on github when requesting some feature.
