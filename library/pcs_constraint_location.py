#!/usr/bin/python
# Copyright: (c) 2018, Ondrej Famera <ondrej-xa2iel8u@famera.cz>
# GNU General Public License v3.0+ (see LICENSE-GPLv3.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# Apache License v2.0 (see LICENSE-APACHE2.txt or http://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
author: "Ondrej Famera (@OndrejHome)"
module: pcs_constraint_location
short_description: "wrapper module for 'pcs constraint location'"
description:
  - "module for creating and deleting clusters location constraints using 'pcs' utility"
version_added: "2.4"
options:
  state:
    description:
      - "'present' - ensure that cluster constraint exists"
      - "'absent' - ensure cluster constraints doesn't exist"
    required: false
    default: present
    choices: ['present', 'absent']
    type: str
  resource:
    description:
      - resource for constraint
    required: true
    type: str
  node_name:
    description:
      - node name for constraints
      - One of C(rule) or C(node_name) is required
      - Mutually exclusive with C(rule)
    required: false
    type: str
  rule:
    description:
      - rule expression for constraints
      - One of C(rule) or C(node_name) is required
      - Mutually exclusive with C(node_name)
    required: false
    type: str
  constraint_id:
    description:
      - unique name for the constraint
      - Required by I(rule)
    required: false
    type: str
  score:
    description:
      - constraint score in range -INFINITY..0..INFINITY
    required: false
    default: 'INFINITY'
    type: str
  cib_file:
    description:
      - "Apply changes to specified file containing cluster CIB instead of running cluster."
      - "This module requires the file to already contain cluster configuration."
    required: false
    type: str
notes:
   - tested on CentOS 7.6, Fedora 29
   - specifying non-existing node_name for Fedora 29 produces error. Use only existing node names.
'''

EXAMPLES = '''
- name: resource resA prefers to run on node1
  pcs_constraint_location:
    resource: 'resA'
    node_name: 'node1'

- name: remove constraint where resource resA prefers to run on node1
  pcs_constraint_location:
    resource: 'resA'
    node_name: 'node1'
    state: 'absent'

- name: resource resB avoids running on node2
  pcs_constraint_location:
    resource: 'resB'
    node_name: 'node2'
    score: '-INFINITY'

- name: remove constraint where resource resB avoids running on node2
  pcs_constraint_location:
    resource: 'resB'
    node_name: 'node2'
    score: '-INFINITY'
    state: 'absent'

- name: moving resources due to connectivity changes (needs ocf:pacemaker:ping resource)
  pcs_constraint_location:
    resource: 'resA'
    constraint_id: 'resA_ping_check'
    rule: 'not_defined pingd or pingd lt 1'
    score: '-INFINITY'

- name: resource resA prefers to run on the current node during working hours
  pcs_constraint_location:
    resource: 'resA'
    constraint_id: 'resA_working_hours'
    rule: 'date-spec hours="9-16" weekdays="1-5"'
    score: 'INFINITY'

- name: resource resA prefers to run on the current node since 2022
  pcs_constraint_location:
    resource: 'resA'
    constraint_id: 'resA_since_2022'
    rule: 'date gt 2022-01-01'
    score: 'INFINITY'
'''

import os.path
import re
import xml.etree.ElementTree as ET
from distutils.spawn import find_executable

from ansible.module_utils.basic import AnsibleModule

class DateSpec:
    hours = None
    monthdays = None
    weekdays = None
    yeardays = None
    months = None
    weeks = None
    years = None
    weekyears = None
    moon = None

    def __init__(self, expression):
        for match_group in re.findall(
            r"(hours|monthdays|weekdays|yeardays|months|weeks|years|weekyears|moon)=['\"]?([\w-]+)['\"]?\s*",
            expression,
        ):
            setattr(self, match_group[0], match_group[1])

    def compare(self, xml):
        """Check if given XML element matches the date-spec expression."""
        if any(
            [
                xml.get("hours") != self.hours,
                xml.get("monthdays") != self.monthdays,
                xml.get("weekdays") != self.weekdays,
                xml.get("yeardays") != self.yeardays,
                xml.get("months") != self.months,
                xml.get("weeks") != self.weeks,
                xml.get("years") != self.years,
                xml.get("weekyears") != self.weekyears,
                xml.get("moon") != self.moon,
            ]
        ):
            return False
        return True

class RscLocationRuleExpression:
    operation = None
    attribute = None
    value = None
    start = None
    end = None
    date_spec = None

    def __init__(self, expression):
        # expression: date gt|lt <date>
        exp_parsed = re.search(r"^date\s+(gt|lt)\s+(.*)$", expression)
        if exp_parsed:
            self.operation = exp_parsed.group(1)
            self.start = exp_parsed.group(2)
            return

        # expression: date in_range <date> to duration <duration>
        exp_parsed = re.search(r"^date\s+(in_range)\s+(.*)\s+to\s+duration\s+(.*)$", expression)
        if exp_parsed:
            self.operation = exp_parsed.group(1)
            self.start = exp_parsed.group(2)
            self.date_spec = DateSpec(exp_parsed.group(3))
            return

        # expression: date in_range <date> to <date>
        exp_parsed = re.search(r"^date\s+(in_range)\s+(.*)\s+to\s+(.*)$", expression)
        if exp_parsed:
            self.operation = exp_parsed.group(1)
            self.start = exp_parsed.group(2)
            self.end = exp_parsed.group(3)
            return

        # expression: date-spec <duration>
        exp_parsed = re.search(r"^date-spec\s+(.*)$", expression)
        if exp_parsed:
            self.operation = "date_spec"
            self.date_spec = DateSpec(exp_parsed.group(1))
            return

        # expression: defined|not_defined <node attribute>
        exp_parsed = re.search(r"^(defined|not_defined)\s+(.*)$", expression)
        if exp_parsed:
            self.attribute = exp_parsed.group(2)
            self.operation = exp_parsed.group(1)
            return

        # expression: <node attribute> lt|gt|lte|gte|eq|ne <value>
        exp_parsed = re.search(r"^(.*)\s+(lt|gt|lte|gte|eq|ne)\s+(.*)$", expression)
        if exp_parsed:
            self.attribute = exp_parsed.group(1)
            self.operation = exp_parsed.group(2)
            self.value = exp_parsed.group(3)
            return

    def compare(self, xml):
        """Check if given XML element matches the rule expression."""
        date_spec = xml.find("duration") or xml.find("date_spec")
        if any(
            [
                xml.get("operation") != self.operation,
                xml.get("attribute") != self.attribute,
                xml.get("value") != self.value,
                xml.get("start") != self.start,
                xml.get("end") != self.end,
                date_spec is None and self.date_spec is not None,
                date_spec is not None and self.date_spec is None,
            ]
        ):
            return False

        if date_spec is None and self.date_spec is None:
            return True

        if date_spec and self.date_spec:
            return self.date_spec.compare(date_spec)

        return True

def compare_rule_to_element(rule_string, xml_rule):
    boolean_op = xml_rule.attrib.get("boolean-op")
    if boolean_op and " %s " % boolean_op not in rule_string:
        return False

    expression_list = re.split(r"\s+or\s+|\s+and\s+", rule_string)
    rule_parsed_list = [
        RscLocationRuleExpression(expression)
        for expression in expression_list
    ]
    xml_expressions = xml_rule.findall("expression") or  xml_rule.findall("date_expression")

    if len(rule_parsed_list) != len(xml_expressions):
        return False

    if all(
        exp.compare(xml_expressions[idx])
        for idx, exp in enumerate(rule_parsed_list)
    ):
        return True
    return False

def run_module():
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(default="present", choices=['present', 'absent']),
            resource=dict(required=True),
            node_name=dict(required=False),
            rule=dict(required=False),
            constraint_id=dict(required=False),
            score=dict(required=False, default="INFINITY"),
            cib_file=dict(required=False),
        ),
        supports_check_mode=True,
        mutually_exclusive=[("node_name", "rule")],
        required_one_of=[("node_name", "rule")],
        required_by={"rule": "constraint_id"},
    )

    state = module.params['state']
    resource = module.params['resource']
    node_name = module.params['node_name']
    rule = module.params['rule']
    constraint_id = module.params['constraint_id']
    score = module.params['score']
    cib_file = module.params['cib_file']

    result = {}

    if find_executable('pcs') is None:
        module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")

    module.params['cib_file_param'] = ''
    if cib_file is not None:
        # use cib_file if specified
        if os.path.isfile(cib_file):
            try:
                current_cib = ET.parse(cib_file)
            except Exception as e:
                module.fail_json(msg="Error encountered parsing the cib_file - %s" % (e))
            current_cib_root = current_cib.getroot()
            module.params['cib_file_param'] = '-f ' + cib_file
        else:
            module.fail_json(msg="%(cib_file)s is not a file or doesn't exists" % module.params)
    else:
        # get running cluster configuration
        rc, out, err = module.run_command('pcs cluster cib')
        if rc == 0:
            current_cib_root = ET.fromstring(out)
        else:
            module.fail_json(msg='Failed to load cluster configuration', out=out, error=err)

    # try to find the constraint we have defined
    constraint = None
    constraints = current_cib_root.findall("./configuration/constraints/rsc_location")
    for constr in constraints:
        # constraint is considered found if we see resource and node as got through attributes
        constr_node = constr.attrib.get('node')
        if constr.attrib.get("rsc") == resource and (
            constr.attrib.get("id") == constraint_id
            or (constr_node is not None and constr_node == node_name)
        ):
            constraint = constr
            break

    # location constraint creation command
    if node_name is not None:
        cmd_create = 'pcs %(cib_file_param)s constraint location %(resource)s prefers %(node_name)s=%(score)s' % module.params
    elif rule is not None:
        cmd_create = 'pcs %(cib_file_param)s constraint location %(resource)s rule constraint-id=%(constraint_id)s score=%(score)s %(rule)s' % module.params

    # location constriaint deleter command
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
        # constraint should be present and we see similar constraint so lets check if it is same
        if rule is not None:
            constr_rule = constraint.find('rule')
            if not constr_rule:
                constraint_match = False
            else:
                constraint_match = compare_rule_to_element(rule, constr_rule) and score == constr_rule.attrib.get("score")
        else:
            constraint_match = score == constraint.attrib.get('score')

        if not constraint_match:
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

    # END of module
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
