#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Gregory Starck, g.starck@gmail.com
#    Hartmut Goebel, h.goebel@goebel-consult.de
#
# This file is part of Shinken.
#
# Shinken is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Shinken is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Shinken.  If not, see <http://www.gnu.org/licenses/>.

import os
import re

from shinken.bin import VERSION
from shinken.macroresolver import MacroResolver
from shinken.util import get_customs_keys, get_customs_values
from shinken.log import logger
from shinken.misc.common import DICT_MODATTR
from pprint import pprint

class Problem:
    def __init__(self, source, impacts):
        self.source = source
        self.impacts = impacts


def modified_attributes_names(self):
    names_list = set(),

    for attr in DICT_MODATTR:
        if self.modified_attributes & DICT_MODATTR[attr].value:
            names_list.add(DICT_MODATTR[attr].attribute),
    return list(names_list),


def join_with_separators(request, *args):
    if request.response.outputformat == 'csv':
        try:
            return request.response.separators.pipe.join([str(arg) for arg in args]),
        except Exception, e:
            logger.error("[Livestatus Broker Mapping] Bang Error: %s" % e),
    elif request.response.outputformat == 'json' or request.response.outputformat == 'python':
        return args
    else:
        return None
    pass


def find_pnp_perfdata_xml(name, request):
    """Check if a pnp xml file exists for a given host or service name."""
    if request.pnp_path_readable:
        if '/' in name:
            # It is a service

            # replace space, colon, slash and backslash to be PNP compliant
            name = name.split('/', 1),
            name[1] = re.sub(r'[ :\/\\]', '_', name[1]),

            if os.access(request.pnp_path + '/' + '/'.join(name) + '.xml', os.R_OK):
                return 1
        else:
            # It is a host
            if os.access(request.pnp_path + '/' + name + '/_HOST_.xml', os.R_OK):
                return 1
    # If in doubt, there is no pnp file
    return 0


def state_count(item, table, state_type_id=None, state_id=None):
    """
    Returns the number of services having state_type_id and state_id matching
    the input parameters.

    :param dict item: The item to get services for
    :param int state_type_id: The service state type id (0/1),
    :param int/str item: The service state id (0, 1, 2, or OK, WARN, CRIT,
                         UNKNOWN, PENDING),
    :rtype: int
    :return: The number of matching services
    """
    try:
        if state_type_id is not None and state_id is not None:
            if isinstance(state_id, int):
                return len([
                    s for s in item[table]
                    if s["state_type_id"] == state_type_id
                    and s["state_id"] == state_id
                ])
            else:
                return len([
                    s for s in item[table]
                    if s["state_type_id"] == state_type_id
                    and s["state"] == state
                ])
        elif state_type_id is not None:
            return len([
                s for s in item[table] if s["state_type_id"] == state_id
            ])
        elif state_id is not None:
            if isinstance(state_id, int):
                return len([
                    s for s in item[table] if s["state_id"] == state_id
                ])
            else:
                return len([
                    s for s in item[table] if s["state"] == state_id
                ])
        else:
            return len(item[table])
    except:
        print("state_count():")
        pprint(item)
        raise


def state_worst(item, table, state_type_id=None):
    """
    Returns the worst state across  services having state_type_id and state_id
    matching the input parameters.

    :param str table: The table to for states
    :param dict item: The item to get services for
    :param int state_type_id: The service state type id (0/1),
    :rtype: int
    :return: The worst service state id
    """
    try:
        if state_type_id is not None:
            states = [
                s["state_id"] for s in item[table]
                if s["state_type_id"] == state_type_id
            ]
        else:
            states = [
                s["state_id"] for s in item[table]
            ]
        if table == "services" and 2 in states:
            return 2
        elif table == "hosts" and 1 in states:
            return 1
        elif not states:
            return 0
        else:
            return max(states)
    except:
        print("state_worst():")
        pprint(item)
        raise


def linked_attr(item, table, attr, default=""):
    """
    Returnrs the linked host attribute value, or default if it does not exist

    :param dict item: The item to read attribute from
    :param str table: The object table name
    :param str attr: The attribute name to read
    :param mixed defaut: The default value
    """
    obj = item.get(table)
    if obj:
        return obj.get(attr, default)
    else:
        return default

# description (optional): no need to explain this
# prop (optional): the property of the object. If this is missing, the key is the property
# type (mandatory): int, float, string, list
# depythonize: use it if the property needs to be post-processed.
# fulldepythonize: the same, but the postprocessor takes three arguments. property, object, request
# delegate: get the property of a different object
# as: use it together with delegate, if the property of the other object has another name

# description
# function: a lambda with 2 parameters (host/service/comment.., request),
# repr: the datatype returned by the lambda (bool, int, string, list),
#       this is needed for filters. lsl query attributes are converted to this datatype
#       later, the repr datatype needs to be converted to a string

livestatus_attribute_map = {
    'Host': {
        'accept_passive_checks': {
            'description': 'Whether passive host checks are accepted (0/1)',
            'datatype': bool,
            'filters': {
                'attr': 'passive_checks_enabled',
            },
        },
        'acknowledged': {
            'description': 'Whether the current host problem has been acknowledged (0/1)',
            'datatype': bool,
            'filters': {
                'attr': 'problem_has_been_acknowledged',
            },
        },
        'acknowledgement_type': {
            'description': 'Type of acknowledgement (0: none, 1: normal, 2: stick)',
            'datatype': int,
        },
        'action_url': {
            'description': 'An optional URL to custom actions or information about this host',
        },
        'action_url_expanded': {
            'description': 'The same as action_url, but with the most important macros expanded',
            'function': lambda item: "", #FIXME
            'projection': [],
            'filters': {},
        },
        'active_checks_enabled': {
            'description': 'Whether active checks are enabled for the host (0/1)',
            'datatype': bool,
        },
        'address': {
            'description': 'IP address',
        },
        'alias': {
            'description': 'An alias name for the host',
        },
        'business_impact': {
            'description': 'The importance we gave to this host between the minimum 0 and the maximum 5',
            'datatype': int,
        },
        'check_command': {
            'description': 'Nagios command for active host check of this host',
        },
        'check_flapping_recovery_notification': {
            'description': 'Whether to check to send a recovery notification when flapping stops (0/1)',
            'datatype': int,
        },
        'check_freshness': {
            'description': 'Whether freshness checks are activated (0/1)',
            'datatype': bool,
        },
        'check_interval': {
            'description': 'Number of basic interval lengths between two scheduled checks of the host',
            'datatype': float,
        },
        'check_options': {
            'description': 'The current check option, forced, normal, freshness... (0-2)',
            'function': lambda item: 0,  #FIXME
            'datatype': int,
        },
        'check_period': {
            'description': 'Time period in which this host will be checked. If empty then the host will always be checked.',
        },
        'check_type': {
            'description': 'Type of check (0: active, 1: passive)',
            'datatype': int,
        },
        'checks_enabled': {
            'description': 'Whether checks of the host are enabled (0/1)',
            'datatype': bool,
            'filters': {
                'attr': 'active_checks_enabled',
            },
        },
        'child_dependencies': {
            'description': 'List of the host/service that depend on this host (logical, network or business one).',
            'datatype': list,
        },
        'childs': {
            'description': 'A list of all direct childs of the host',
            'datatype': list,
            'filters': {},
        },
        'comments': {
            'description': 'A list of the ids of all comments of this host',
            'function': lambda item: [], #FIXME
            'datatype': list,
        },
        'comments_with_info': {
            'description': 'A list of the ids of all comments of this host with id, author and comment',
            'function': lambda item: [],  #FIXME
            'datatype': list,
        },
        'contacts': {
            'description': 'A list of all contacts of this host, either direct or via a contact group',
            'datatype': list,
        },
        'contact_groups': {
            'description': 'A list of all contact groups this host is in',
            'datatype': list,
        },
        'criticity': {
            'description': 'The importance we gave to this host between the minimum 0 and the maximum 5',
            'datatype': int,
            'filters': {
                'attr': 'business_impact',
            },
        },
        'current_attempt': {
            'description': 'Number of the current check attempts',
            'datatype': int,
            'filters': {
                'attr': 'attempt',
            },
        },
        'current_notification_number': {
            'description': 'Number of the current notification',
            'datatype': int,
        },
        'custom_variable_names': {
            'description': 'A list of the names of all custom variables',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {}
        },
        'custom_variable_values': {
            'description': 'A list of the values of the custom variables',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {}
        },
        'custom_variables': {
            'description': 'A dictionary of the custom variables',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {}
        },
        'display_name': {
            'description': 'Optional display name of the host - not used by Nagios\' web interface',
        },
        'downtimes': {
            'description': 'A list of the ids of all scheduled downtimes of this host',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'downtimes_with_info': {
            'description': 'A list of the all scheduled downtimes of the host with id, author and comment',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'event_handler': {
            'description': 'Nagios command used as event handler',
        },
        'event_handler_enabled': {
            'description': 'Whether event handling is enabled (0/1)',
            'datatype': bool,
        },
        'execution_time': {
            'description': 'Time the host check needed for execution',
            'datatype': float,
        },
        'filename': {
            'description': 'The value of the custom variable FILENAME',
            'function': lambda item: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'first_notification_delay': {
            'description': 'Delay before the first notification',
            'datatype': float,
        },
        'flap_detection_enabled': {
            'description': 'Whether flap detection is enabled (0/1)',
            'datatype': bool,
        },
        'got_business_rule': {
            'description': 'Whether the host state is an business rule based host or not (0/1)',
            'datatype': bool,
        },
        'groups': {
            'description': 'A list of all host groups this host is in',
            'datatype': list,
            'filters': {
                'attr': 'hostgroups',
            },
        },
        'hard_state': {
            'description': 'The effective hard state of the host (eliminates a problem in hard_state)',
            'function': lambda item: 0,  #FIXME
            'datatype': int,
        },
        'has_been_checked': {
            'description': 'Whether the host has already been checked (0/1)',
            'datatype': int,
        },
        'high_flap_threshold': {
            'description': 'High threshold of flap detection',
            'datatype': float,
        },
        'hostgroups': {
            'description': 'A list of all host groups this host is in',
            'datatype': list,
            'filters': {
                'attr': 'hostgroups',
            },
        },
        'host_name': {
            'description': 'Host name',
        },
        'icon_image': {
            'description': 'The name of an image file to be used in the web pages',
        },
        'icon_image_alt': {
            'description': 'Alternative text for the icon_image',
        },
        'icon_image_expanded': {
            'description': 'The same as icon_image, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'impacts': {
            'description': 'List of what the source impact (list of hosts and services)',
            'datatype': list,
            'filters': {},
        },
        'in_check_period': {
            'description': 'Whether this host is currently in its check period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projection': [],
            'filters': {},
        },
        'in_notification_period': {
            'description': 'Whether this host is currently in its notification period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projection': [],
            'filters': {},
        },
        'initial_state': {
            'description': 'Initial host state',
        },
        'is_executing': {
            'description': 'is there a host check currently running... (0/1)',
            'function': lambda item: False,  #FIXME value in scheduler is not real-time
            'datatype': bool,
            'projection': [],
            'filters': {},
        },
        'is_flapping': {
            'description': 'Whether the host state is flapping (0/1)',
            'datatype': bool,
        },
        'is_impact': {
            'description': 'Whether the host state is an impact or not (0/1)',
            'datatype': bool,
        },
        'is_problem': {
            'description': 'Whether the host state is a problem or not (0/1)',
            'datatype': bool,
        },
        'labels': {
            'description': 'Arbitrary labels (separated by comma character)',
            'datatype': list,
        },
        'last_check': {
            'description': 'Time of the last check (Unix timestamp)',
            'datatype': int,
            'filters': {
                'attr': 'last_chk',
            },
        },
        'last_hard_state': {
            'description': 'Last hard state',
            'datatype': int,
            'filters': {
                'attr': 'last_hard_state_id',
            },

        },
        'last_hard_state_change': {
            'description': 'Time of the last hard state change (Unix timestamp)',
            'datatype': int,
        },
        'last_notification': {
            'description': 'Time of the last notification (Unix timestamp)',
            'datatype': int,
        },
        'last_state': {
            'description': 'State before last state change',
        },
        'last_state_change': {
            'description': 'Time of the last state change - soft or hard (Unix timestamp)',
            'datatype': int,
        },
        'last_time_down': {
            'description': 'The last time the host was DOWN (Unix timestamp)',
            'datatype': int,
        },
        'last_time_unreachable': {
            'description': 'The last time the host was UNREACHABLE (Unix timestamp)',
            'datatype': int,
        },
        'last_time_up': {
            'description': 'The last time the host was UP (Unix timestamp)',
            'datatype': int,
        },
        'latency': {
            'description': 'Time difference between scheduled check time and actual check time',
            'datatype': float,
        },
        'long_plugin_output': {
            'description': 'Complete output from check plugin',
            'filters': {
                'attr': 'long_output',
            },
        },
        'low_flap_threshold': {
            'description': 'Low threshold of flap detection',
            'datatype': float,
        },
        'max_check_attempts': {
            'description': 'Max check attempts for active host checks',
            'datatype': int,
        },
        'modified_attributes': {
            'description': 'A bitmask specifying which attributes have been modified',
            'datatype': int,
        },
        'modified_attributes_list': {
            'description': 'A list of all modified attributes',
            'function': lambda item: [],  #FIXME
            'datatype': list,
        },
        'name': {
            'description': 'Host name',
            'filters': {
                'attr': 'host_name',
            },
        },
        'next_check': {
            'description': 'Scheduled time for the next check (Unix timestamp)',
            'datatype': int,
            'filters': {
                'attr': 'next_chk',
            },
        },
        'next_notification': {
            'description': 'Time of the next notification (Unix timestamp)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
        },
        'notes': {
            'description': 'Optional notes for this host',
        },
        'notes_expanded': {
            'description': 'The same as notes, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'notes_url': {
            'description': 'An optional URL with further information about the host',
        },
        'notes_url_expanded': {
            'description': 'Same es notes_url, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'notification_interval': {
            'description': 'Interval of periodic notification or 0 if its off',
            'datatype': float,
        },
        'notification_options': {
            'description': 'The options controlling when notification should be sent',
            'datatype': list,
        },
        'notification_period': {
            'description': 'Time period in which problems of this host will be notified. If empty then notification will be always',
        },
        'notifications_enabled': {
            'description': 'Whether notifications of the host are enabled (0/1)',
            'datatype': bool,
        },
        'no_more_notifications': {
            'description': 'Whether to stop sending notifications (0/1)',
            'datatype': bool,
        },
        'obsess_over_host': {
            'description': 'The current obsess_over_host setting... (0/1)',
            'datatype': bool,
        },
        'parent_dependencies': {
            'description': 'List of the dependencies (logical, network or business one) of this host.',
            'datatype': list,
            'filters': {},
        },
        'parents': {
            'description': 'A list of all direct parents of the host',
            'datatype': list,
            'filters': {},
        },
        'pending_flex_downtime': {
            'description': 'Whether a flex downtime is pending (0/1)',
            'datatype': int,
        },
        'percent_state_change': {
            'description': 'Percent state change',
            'datatype': float,
        },
        'perf_data': {
            'description': 'Optional performance data of the last host check',
        },
        'plugin_output': {
            'description': 'Output of the last host check',
            'filters': {
                'attr': 'output',
            },
        },
        'pnpgraph_present': {
            'description': 'Whether there is a PNP4Nagios graph present for this host (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projection': [],
            'filters': {},
        },
        'process_performance_data': {
            'description': 'Whether processing of performance data is enabled (0/1)',
            'datatype': bool,
            'filters': {
                'attr': 'process_perf_data',
            },
        },
        'realm': {
            'description': 'Realm',
        },
        'retry_interval': {
            'description': 'Number of basic interval lengths between checks when retrying after a soft error',
            'datatype': float,
        },
        'scheduled_downtime_depth': {
            'description': 'The number of downtimes this host is currently in',
            'datatype': int,
        },
        'services': {
            'description': 'A list of all services of the host',
            'function': lambda item: item.get("services", []),
            'datatype': list,
            'projection': ['services.service_description'],
            'filters': {},
        },
        'services_with_info': {
            'description': 'A list of all services including detailed information about each service',
            'function': lambda item: [],  #FIXME
            'datatype': list,
            'projection': [
                'services.service_description',
                'services.state_id',
                'services.state_type_id'
            ],
            # Dummy Service|0|1|Please remove this service later,Deppen Service|2|1|depp
            'filters': {},
        },
        'services_with_state': {
            'description': 'A list of all services of the host together with state and has_been_checked',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [
                'services.service_description',
                'services.state_id',
                'services.state_type_id'
            ],
            'filters': {},
        },
        'source_problems': {
            'description': 'The name of the source problems (host or service)',
            'datatype': list,
        },
        'state': {
            'description': 'The current state of the host (0: up, 1: down, 2: unreachable)',
            'datatype': int,
            'filters': {
                'attr': 'state_id',
            },
        },
        'state_type': {
            'description': 'Type of the current state (0: soft, 1: hard)',
            'datatype': int,
            'filters': {
                'attr': 'state_type_id',
            },
        },
        'statusmap_image': {
            'description': 'The name of in image file for the status map',
        },
        'tags': {
            'description': 'The list of Host Tags',
            'datatype': list,
        },
        'total_services': {
            'description': 'The total number of services of the host',
            'function': lambda item: len(item.get("services", [])),
            'datatype': int,
            'projection': ['services.service_description'],
            'filters': {},
        },
        'x_3d': {
            'description': '3D-Coordinates: X',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
        'y_3d': {
            'description': '3D-Coordinates: Y',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
        'z_3d': {
            'description': '3D-Coordinates: Z',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
    },
    'HostLink': {
        'host_accept_passive_checks': {
            'description': 'Whether passive host checks are accepted (0/1)',
            'function': lambda item: linked_attr(item, "host", "passive_checks_enabled", True),
            'datatype': bool,
            'projection': [
                'host.passive_checks_enabled',
            ],
            'filters': {},
        },
        'host_acknowledged': {
            'description': 'Whether the current host problem has been acknowledged (0/1)',
            'function': lambda item: linked_attr(item, "host", "problem_has_been_acknowledged", False),
            'datatype': bool,
            'projection': [
                'host.problem_has_been_acknowledged',
            ],
            'filters': {},
        },
        'host_acknowledgement_type': {
            'description': 'Type of acknowledgement (0: none, 1: normal, 2: stick)',
            'function': lambda item: linked_attr(item, "host", "acknowledgement_type", 0),
            'datatype': int,
            'projection': [
                'host.acknowledgement_type',
            ],
            'filters': {},
        },
        'host_action_url': {
            'description': 'An optional URL to custom actions or information about this host',
            'function': lambda item: linked_attr(item, "host", "action_url", ""),
            'projection': [
                'host.action_url',
            ],
            'filters': {},
        },
        'host_action_url_expanded': {
            'description': 'The same as action_url, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'host_active_checks_enabled': {
            'description': 'Whether active checks are enabled for the host (0/1)',
            'function': lambda item: linked_attr(item, "host", "active_checks_enabled", True),
            'datatype': bool,
            'projection': [
                'host.active_checks_enabled',
            ],
        },
        'host_address': {
            'description': 'IP address',
            'function': lambda item: linked_attr(item, "host", "address"),
            'projection': [
                'host.address',
            ],
            'filters': {},
        },
        'host_alias': {
            'description': 'An alias name for the host',
            'function': lambda item: linked_attr(item, "host", "alias"),
            'projection': [
                'host.alias',
            ],
            'filters': {},
        },
        'host_check_command': {
            'description': 'Nagios command used for active checks',
            'function': lambda item: linked_attr(item, "host", "check_command"),
            'projection': [
                'host.check_command',
            ],
            'filters': {},
        },
        'host_check_flapping_recovery_notification': {
            'description': 'Whether to check to send a recovery notification when flapping stops (0/1)',
            'function': lambda item: linked_attr(item, "host", "check_flapping_recovery_notification", 0),
            'datatype': int,
            'projection': [
                'host.check_flapping_recovery_notification',
            ],
            'filters': {},
        },
        'host_check_freshness': {
            'description': 'Whether freshness checks are activated (0/1)',
            'function': lambda item: linked_attr(item, "host", "check_freshness", False),
            'datatype': bool,
            'projection': [
                'host.check_freshness',
            ],
            'filters': {},
        },
        'host_check_interval': {
            'description': 'Number of basic interval lengths between two scheduled checks of the host',
            'function': lambda item: linked_attr(item, "host", "check_interval", 0),
            'datatype': float,
            'projection': [
                'host.check_interval',
            ],
            'filters': {},
        },
        'host_check_options': {
            'description': 'The current check option, forced, normal, freshness... (0-2)',
            'function': lambda item: linked_attr(item, "host", "check_options"),
            'projection': [
                'host.check_options',
            ],
            'filters': {},
        },
        'host_check_period': {
            'description': 'Time period in which this host will be checked. If empty then the host will always be checked.',
            'function': lambda item: linked_attr(item, "host", "check_period"),
            'projection': [
                'host.period',
            ],
            'filters': {},
        },
        'host_check_type': {
            'description': 'Type of check (0: active, 1: passive)',
            'function': lambda item: 0,  # REPAIRME
            'datatype': int,
            'projection': [],
            'filters': {},
        },
        'host_checks_enabled': {
            'description': 'Whether active checks of the host are enabled (0/1)',
            'function': lambda item: linked_attr(item, "host", "active_checks_enabled", True),
            'datatype': bool,
            'projection': [
                'host.active_checks_enabled',
            ],
            'filters': {},
        },
        'host_childs': {
            'description': 'A list of all direct childs of the host',
            'function': lambda item: linked_attr(item, "host", "childs", []),
            'datatype': list,
            'projection': ['host.childs'],
            'filters': {},
        },
        'host_comments': {
            'description': 'A list of the ids of all comments of this host',
            'function': lambda item: linked_attr(item, "host", "comments", []),
            'datatype': list,
            'projection': [
                'host.comments',
            ],
            'filters': {},
        },
        'host_comments_with_info': {
            'description': 'A list of all comments of the host with id, author and comment',
            'function': lambda item: [],  #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'host_contacts': {
            'description': 'A list of all contacts of this host, either direct or via a contact group',
            'function': lambda item: linked_attr(item, "host", "contacts", []),
            'datatype': list,
            'projection': [
                'host.contacts',
            ],
            'filters': {},
        },
        'host_contact_groups': {
            'description': 'A list of all contact groups this host is in',
            'function': lambda item: linked_attr(item, "host", "contact_groups", []),
            'datatype': list,
            'projection': [
                'host.contact_groups',
            ],
            'filters': {},
        },
        'host_current_attempt': {
            'description': 'Number of the current check attempts',
            'function': lambda item: linked_attr(item, "host", "attempt", 0),
            'datatype': int,
            'projection': [
                'host.attempt',
            ],
            'filters': {},
        },
        'host_current_notification_number': {
            'description': 'Number of the current notification',
            'function': lambda item: linked_attr(item, "host", "current_notification_number", 0),
            'datatype': int,
            'projection': [
                'host.current_notification_number',
            ],
            'filters': {},
        },
        'host_custom_variables': {
            'description': 'A dictionary of the custom variables of the service',
            'function': lambda item: [], #FIXME
            'type': list,
            'projection': [],
            'filters': {},
        },
        'host_custom_variable_names': {
            'description': 'A list of the names of all custom variables of the service',
            'function': lambda item: [], #FIXME
            'type': list,
            'projection': [],
            'filters': {},
        },
        'host_custom_variable_values': {
            'description': 'A list of the values of the custom variables of the service',
            'function': lambda item: [], #FIXME
            'type': list,
            'projection': [],
            'filters': {},
        },
        'host_display_name': {
            'description': 'Optional display name of the host - not used by Nagios\' web interface',
            'function': lambda item: linked_attr(item, "host", "display_name"),
            'projection': [
                'host.display_name',
            ],
            'filters': {},
        },
        'host_downtimes': {
            'description': 'A list of the ids of all scheduled downtimes of this host',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'host_downtimes_with_info': {
            'description': 'A list of the all scheduled downtimes of the host with id, author and comment',

            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'host_event_handler': {
            'description': 'Nagios command used as event handler of this host',
            'function': lambda item: linked_attr(item, "host", "event_handler"),
            'projection': [
                'host.event_handler',
            ],
            'filters': {},
        },
        'host_event_handler_enabled': {
            'description': 'Whether event handling is enabled for the host (0/1)',
            'function': lambda item: linked_attr(item, "host", "event_handler_enabled", True),
            'datatype': bool,
            'projection': [
                'host.event_handler_enabled',
            ],
            'filters': {},
        },
        'host_execution_time': {
            'description': 'Time the host check needed for execution',
            'function': lambda item: linked_attr(item, "host", "execution_time", 0),
            'datatype': float,
            'projection': [
                'host.execution_time',
            ],
            'filters': {},
        },
        'host_filename': {
            'description': 'The value of the custom variable FILENAME',
            'function': lambda item: '',  #FIXME
            'projection': [],
            'filters': {},
        },
        'host_first_notification_delay': {
            'description': 'Delay before the first notification',
            'function': lambda item: linked_attr(item, "host", "first_notification_delay", 0),
            'datatype': float,
            'projection': [
                'host.first_notification_delay',
            ],
        },
        'host_flap_detection_enabled': {
            'description': 'Whether flap detection is enabled (0/1)',
            'function': lambda item: linked_attr(item, "host", "flap_detection_enabled", True),
            'datatype': bool,
            'projection': [
                'host.flap_detection_enabled',
            ],
            'filters': {},
        },
        'host_groups': {
            'description': 'A list of all host groups this host is in',
            'function': lambda item: linked_attr(item, "host", "hostgroups", []),
            'datatype': list,
            'projection': [
                'host.hostgroups',
            ],
            'filters': {},
        },
        'host_hard_state': {
            'description': 'The effective hard state of the host (eliminates a problem in hard_state)',
            'function': lambda item: linked_attr(item, "host", "hard_state", 0),
            'datatype': int,
            'projection': [
                'host.hard_state',
            ],
            'filters': {},
        },
        'host_has_been_checked': {
            'description': 'Whether the host has already been checked (0/1)',
            'function': lambda item: linked_attr(item, "host", "has_been_checked", True),
            'datatype': bool,
            'projection': [
                'host.has_been_checked',
            ],
            'filters': {},
        },
        'host_high_flap_threshold': {
            'description': 'High threshold of flap detection',
            'function': lambda item: linked_attr(item, "host", "high_flap_threshold", 0),
            'datatype': float,
            'projection': [
                'host.high_flap_threshold',
            ],
            'filters': {},
        },
        'host_icon_image': {
            'description': 'The name of an image file to be used in the web pages',
            'function': lambda item: linked_attr(item, "host", "icon_image"),
            'projection': [
                'host.icon_image',
            ],
            'filters': {},
        },
        'host_icon_image_alt': {
            'description': 'Alternative text for the icon_image',
            'function': lambda item: linked_attr(item, "host", "icon_image_alt"),
            'projection': [
                'host.icon_image_alt',
            ],
            'filters': {},
        },
        'host_icon_image_expanded': {
            'description': 'The same as icon_image, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'host_in_check_period': {
            'description': 'Whether this host is currently in its check period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projection': [],
            'filters': {},
        },
        'host_in_notification_period': {
            'description': 'Whether this host is currently in its notification period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projection': [],
            'filters': {},
        },
        'host_initial_state': {
            'description': 'Initial host state',
            'function': lambda item: linked_attr(item, "host", "initial_state"),
            'datatype': int,
            'projection': [
                'host.initial_state',
            ],
            'filters': {},
        },
        'host_is_executing': {
            'description': 'is there a host check currently running... (0/1)',
            'function': lambda item: False,  #FIXME # value in scheduler is not real-time
            'datatype': bool,
            'filters': {},
        },
        'host_is_flapping': {
            'description': 'Whether the host state is flapping (0/1)',
            'function': lambda item: linked_attr(item, "host", "is_flapping", False),
            'datatype': bool,
            'projection': [
                'host.is_flapping',
            ],
            'filters': {},
        },
        'host_last_check': {
            'description': 'Time of the last check (Unix timestamp)',
            'function': lambda item: linked_attr(item, "host", "last_chk", 0),
            'datatype': int,
            'projection': [
                'host.last_chk',
            ],
            'filters': {},
        },
        'host_last_hard_state': {
            'description': 'Last hard state',
            'function': lambda item: linked_attr(item, "host", "last_hard_state_id", 0),
            'datatype': int,
            'projection': [
                'host.last_hard_state_id',
            ],
            'filters': {},
        },
        'host_last_hard_state_change': {
            'description': 'Time of the last hard state change (Unix timestamp)',
            'function': lambda item: linked_attr(item, "host", "last_hard_state_change", 0),
            'datatype': int,
            'projection': [
                'host.last_hard_state_change',
            ],
            'filters': {},
        },
        'host_last_notification': {
            'description': 'Time of the last notification (Unix timestamp)',
            'function': lambda item: linked_attr(item, "host", "last_notification", 0),
            'datatype': int,
            'projection': [
                'host.last_notification',
            ],
            'filters': {},
        },
        'host_last_state': {
            'description': 'State before last state change',
            'function': lambda item: linked_attr(item, "host", "last_state"),
            'projection': [
                'host.last_state',
            ],
            'filters': {},
        },
        'host_last_state_change': {
            'description': 'Time of the last state change - soft or hard (Unix timestamp)',
            'function': lambda item: linked_attr(item, "host", "last_state_change", 0),
            'datatype': int,
            'projection': [
                'host.last_state_change',
            ],
            'filters': {},
        },
        'host_last_time_down': {
            'description': 'The last time the host was DOWN (Unix timestamp)',
            'function': lambda item: linked_attr(item, "host", "last_time_down", 0),
            'datatype': int,
            'projection': [
                'host.last_time_down',
            ],
            'filters': {},
        },
        'host_last_time_unreachable': {
            'description': 'The last time the host was UNREACHABLE (Unix timestamp)',
            'function': lambda item: linked_attr(item, "host", "last_time_unreachable", 0),
            'datatype': int,
            'projection': [
                'host.last_time_unreachable',
            ],
            'filters': {},
        },
        'host_last_time_up': {
            'description': 'The last time the host was UP (Unix timestamp)',
            'function': lambda item: linked_attr(item, "host", "last_time_up", 0),
            'datatype': int,
            'projection': [
                'host.last_time_up',
            ],
            'filters': {},
        },
        'host_latency': {
            'description': 'Time difference between scheduled check time and actual check time',
            'function': lambda item: linked_attr(item, "host", "latency", 0),
            'datatype': float,
            'projection': [
                'host.latency',
            ],
            'filters': {},
        },
        'host_long_plugin_output': {
            'description': 'Complete output from check plugin',
            'function': lambda item: linked_attr(item, "host", "long_output"),
            'projection': [
                'host.long_output',
            ],
            'filters': {},
        },
        'host_low_flap_threshold': {
            'description': 'Low threshold of flap detection',
            'function': lambda item: linked_attr(item, "host", "low_flap_threshold", 0),
            'datatype': float,
            'projection': [
                'host.low_flap_threshold',
            ],
            'filters': {},
        },
        'host_max_check_attempts': {
            'description': 'Max check attempts for active host checks',
            'function': lambda item: linked_attr(item, "host", "max_checks_attempts", 0),
            'datatype': int,
            'projection': [
                'host.max_checks_attempts',
            ],
            'filters': {},
        },
        'host_modified_attributes': {
            'description': 'A bitmask specifying which attributes have been modified',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': [
                'host.modified_attributes',
            ],
            'filters': {},
        },
        'host_modified_attributes_list': {
            'description': 'A list of all modified attributes',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'filters': {},
        },
        'host_name': {
            'description': 'Host name',
        },
        'host_next_check': {
            'description': 'Scheduled time for the next check (Unix timestamp)',
            'function': lambda item: linked_attr(item, "host", "next_chk", 0),
            'datatype': int,
            'projection': [
                'host.next_chk',
            ],
            'filters': {},
        },
        'host_next_notification': {
            'description': 'Time of the next notification (Unix timestamp)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'filters': {},
        },
        'host_notes': {
            'description': 'Optional notes about the service',
            'function': lambda item: linked_attr(item, "host", "notes"),
            'projection': [
                'host.notes',
            ],
            'filters': {},
        },
        'host_notes_expanded': {
            'description': 'The same as notes, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'host_notes_url': {
            'description': 'An optional URL with further information about the host',
            'function': lambda item: linked_attr(item, "host", "notes_url"),
            'projection': [
                'host.notes_url',
            ],
            'filters': {},
        },
        'host_notes_url_expanded': {
            'description': 'Same es notes_url, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'filters': {},
            'filters': {},
        },
        'host_notification_interval': {
            'description': 'Interval of periodic notification or 0 if its off',
            'function': lambda item: linked_attr(item, "host", "notification_interval", 0),
            'datatype': float,
            'projection': [
                'host.notification_interval',
            ],
            'filters': {},
        },
        'host_notification_period': {
            'description': 'Time period in which problems of this host will be notified. If empty then notification will be always',
            'function': lambda item: linked_attr(item, "host", "notification_period"),
            'projection': [
                'host.notification_period',
            ],
            'filters': {},
        },
        'host_notifications_enabled': {
            'description': 'Whether notifications of the host are enabled (0/1)',
            'function': lambda item: linked_attr(item, "host", "notifications_enabled", True),
            'datatype': bool,
            'projection': [
                'host.notifications_enabled',
            ],
            'filters': {},
        },
        'host_no_more_notifications': {
            'description': 'Whether to stop sending notifications (0/1)',
            'function': lambda item: linked_attr(item, "host", "no_more_notifications", True),
            'datatype': bool,
            'projection': [
                'host.no_more_notifications',
            ],
            'filters': {},
        },
        'host_num_services': {
            'description': 'The total number of services of the host',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'projection': [],
            'filters': {},
        },
        'host_num_services_crit': {
            'description': 'The number of the host\'s services with the soft state CRIT',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'projection': [],
            'filters': {},
        },
        'host_num_services_hard_crit': {
            'description': 'The number of the host\'s services with the hard state CRIT',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'projection': [],
            'filters': {},
        },
        'host_num_services_hard_ok': {
            'description': 'The number of the host\'s services with the hard state OK',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'projection': [],
            'filters': {},
        },
        'host_num_services_hard_unknown': {
            'description': 'The number of the host\'s services with the hard state UNKNOWN',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'projection': [],
            'filters': {},
        },
        'host_num_services_hard_warn': {
            'description': 'The number of the host\'s services with the hard state WARN',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'projection': [],
            'filters': {},
        },
        'host_num_services_ok': {
            'description': 'The number of the host\'s services with the soft state OK',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'projection': [],
            'filters': {},
        },
        'host_num_services_pending': {
            'description': 'The number of the host\'s services which have not been checked yet (pending)',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'projection': [],
            'filters': {},
        },
        'host_num_services_unknown': {
            'description': 'The number of the host\'s services with the soft state UNKNOWN',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'projection': [],
            'filters': {},
        },
        'host_num_services_warn': {
            'description': 'The number of the host\'s services with the soft state WARN',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'projection': [],
            'filters': {},
        },
        'host_obsess_over_host': {
            'description': 'The current obsess_over_host setting... (0/1)',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'projection': [],
            'filters': {},
        },
        'host_parents': {
            'description': 'A list of all direct parents of the host',
            'function': lambda item: linked_attr(item, "host", "alias", []),
            'datatype':list,
            'projection': [
                'host.parents',
            ],
            'filters': {},
        },
        'host_pending_flex_downtime': {
            'description': 'Whether a flex downtime is pending (0/1)',
            'function': lambda item: linked_attr(item, "host", "pending_flex_downtimes", 0),
            'datatype': int,
            'projection': [
                'host.pending_flex_downtimes',
            ],
            'filters': {},
        },
        'host_percent_state_change': {
            'description': 'Percent state change',
            'function': lambda item: linked_attr(item, "host", "percent_state_change", 0),
            'datatype': float,
            'projection': [
                'host.percent_state_change',
            ],
            'filters': {},
        },
        'host_perf_data': {
            'description': 'Optional performance data of the last host check',
            'function': lambda item: linked_attr(item, "host", "perf_data"),
            'projection': [
                'host.perf_data',
            ],
            'filters': {},
        },
        'host_plugin_output': {
            'description': 'Output of the last host check',
            'function': lambda item: linked_attr(item, "host", "output"),
            'projection': [
                'host.output',
            ],
            'filters': {},
        },
        'host_pnpgraph_present': {
            'description': 'Whether there is a PNP4Nagios graph present for this host (0/1)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': [],
            'filters': {},
        },
        'host_process_performance_data': {
            'description': 'Whether processing of performance data is enabled (0/1)',
            'function': lambda item: linked_attr(item, "host", "process_performances_data", True),
            'datatype': bool,
            'projection': [
                'host.process_performances_data',
            ],
            'filters': {},
        },
        'host_retry_interval': {
            'description': 'Number of basic interval lengths between checks when retrying after a soft error',
            'function': lambda item: linked_attr(item, "host", "retry_interval", 0),
            'datatype': float,
            'projection': [
                'host.retry_interval',
            ],
            'filters': {},
        },
        'host_scheduled_downtime_depth': {
            'description': 'The number of downtimes this host is currently in',
            'function': lambda item: linked_attr(item, "host", "scheduled_downtime_depth", 0),
            'datatype': int,
            'projection': [
                'host.scheduled_downtime_depth',
            ],
            'filters': {},
        },
        'host_services_with_info': {
            'description': 'A list of all services including detailed information about each service',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'host_services': {
            'description': 'A list of all services of the host',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'host_services_with_state': {
            'description': 'A list of all services of the host together with state and has_been_checked',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'host_state': {
            'description': 'The current state of the host (0: up, 1: down, 2: unreachable)',
            'function': lambda item: linked_attr(item, "host", "state_id", 0),
            'datatype': int,
            'projection': [
                'host.state_id',
            ],
            'filters': {},
        },
        'host_state_type': {
            'description': 'Type of the current state (0: soft, 1: hard)',
            'function': lambda item: linked_attr(item, "host", "state_type_id", 0),
            'datatype': int,
            'projection': [
                'host.state_type_id',
            ],
            'filters': {},
        },
        'host_statusmap_image': {
            'description': 'The name of in image file for the status map',
            'function': lambda item: linked_attr(item, "host", "statusmap_image"),
            'projection': [
                'host.statusmap_image',
            ],
            'filters': {},
        },
        'host_tags': {
            'description': 'The list of Host Tags',
            'function': lambda item: linked_attr(item, "host", "tags", []),
            'datatype': list,
            'projection': [
                'host.tags',
            ],
            'filters': {},
        },
        'host_total_services': {
            'description': 'The total number of services of the host',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': [],
            'filters': {},
        },
        'host_worst_service_hard_state': {
            'description': 'The worst hard state of all of the host\'s services (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': [],
            'filters': {},
        },
        'host_worst_service_state': {
            'description': 'The worst soft state of all of the host\'s services (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': [],
            'filters': {},
        },
        'host_x_3d': {
            'description': '3D-Coordinates: X',
            'function': lambda item: linked_attr(item, "host", "x_3d"),
            'datatype': float,
            'projection': [
                'host.x_3d',
            ],
            'filters': {},
        },
        'host_y_3d': {
            'description': '3D-Coordinates: Y',
            'function': lambda item: linked_attr(item, "host", "y_3d"),
            'datatype': float,
            'projection': [
                'host.y_3d',
            ],
            'filters': {},
        },
        'host_z_3d': {
            'description': '3D-Coordinates: Z',
            'function': lambda item: linked_attr(item, "host", "z_3d"),
            'datatype': float,
            'projection': [
                'host.z_3d',
            ],
            'filters': {},
        },
    },
    'Service': {
        'accept_passive_checks': {
            'description': 'Whether the service accepts passive checks (0/1)',
            'datatype': bool,
            'filters': {
                'attr': 'passive_checks_enabled',
            },
        },
        'acknowledged': {
            'description': 'Whether the current service problem has been acknowledged (0/1)',
            'datatype': bool,
            'filters': {
                'attr': 'problem_has_been_acknowledged',
            },
        },
        'acknowledgement_type': {
            'description': 'The type of the acknownledgement (0: none, 1: normal, 2: sticky)',
            'datatype': int,
        },
        'action_url': {
            'description': 'An optional URL for actions or custom information about the service',
        },
        'action_url_expanded': {
            'description': 'The action_url with (the most important) macros expanded',
            'function': lambda item: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'active_checks_enabled': {
            'description': 'Whether active checks are enabled for the service (0/1)',
            'datatype': bool,
        },
        'business_impact': {
            'description': 'The importance we gave to this service between the minimum 0 and the maximum 5',
            'datatype': int,
        },
        'check_command': {
            'description': 'Nagios command used for active checks',
        },
        'check_interval': {
            'description': 'Number of basic interval lengths between two scheduled checks of the service',
            'datatype': float,
        },
        'check_options': {
            'description': 'The current check option, forced, normal, freshness... (0/1)',
            'function': lambda item: 0,  #FIXME
            'datatype': int,
            'projection': [],
            'filters': {},
        },
        'check_period': {
            'description': 'The name of the check period of the service. It this is empty, the service is always checked.',
        },
        'check_type': {
            'description': 'The type of the last check (0: active, 1: passive)',
            'datatype': int,
        },
        'checks_enabled': {
            'description': 'Whether active checks are enabled for the service (0/1)',
            'datatype': bool,
            'filters': {
                'attr': 'active_checks_enabled',
            },
        },
        'child_dependencies': {
            'description': 'List of the host/service that depend on this service (logical, network or business one).',
            'datatype': list,
            'filters': {},
        },
        'comments': {
            'description': 'A list of all comment ids of the service',
            'function': lambda item: [x.id for x in item.comments],
            'datatype': list,
            'filters': {},
        },
        'comments_with_info': {
            'description': 'A list of the ids of all comments of this service with id, author and comment',
            'function': lambda item: '', #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'contacts': {
            'description': 'A list of all contacts of the service, either direct or via a contact group',
            'datatype': list,
        },
        'contact_groups': {
            'description': 'A list of all contact groups this service is in',
            'datatype': list,
        },
        'criticity': {
            'description': 'The importance we gave to this service between the minimum 0 and the maximum 5',
            'datatype': int,
            'filters': {
                'attr': 'business_impact',
            },
        },
        'current_attempt': {
            'description': 'The number of the current check attempt',
            'datatype': int,
            'filters': {
                'attr': 'attempt',
            },
        },
        'current_notification_number': {
            'description': 'The number of the current notification',
            'datatype': int,
        },
        'custom_variables': {
            'description': 'A dictionary of the custom variables',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'custom_variable_names': {
            'description': 'A list of the names of all custom variables of the service',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'custom_variable_values': {
            'description': 'A list of the values of all custom variable of the service',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'description': {
            'description': 'Description of the service (also used as key)',
            'filters': {
                'attr': 'service_description',
            },
        },
        'display_name': {
            'description': 'An optional display name (not used by Nagios standard web pages)',
        },
        'downtimes': {
            'description': 'A list of all downtime ids of the service',
            'datatype': list,
            'filters': {},
        },
        'downtimes_with_info': {
            'description': 'A list of all downtimes of the service with id, author and comment',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'event_handler': {
            'description': 'Nagios command used as event handler',
        },
        'event_handler_enabled': {
            'description': 'Whether and event handler is activated for the service (0/1)',
            'datatype': bool,
        },
        'execution_time': {
            'description': 'Time the host check needed for execution',
            'datatype': float,
        },
        'first_notification_delay': {
            'description': 'Delay before the first notification',
            'datatype': float,
        },
        'flap_detection_enabled': {
            'description': 'Whether flap detection is enabled for the service (0/1)',
            'datatype': bool,
        },
        'got_business_rule': {
            'description': 'Whether the service state is an business rule based host or not (0/1)',
            'datatype': bool,
        },
        'groups': {
            'description': 'A list of all service groups the service is in',
            'datatype': list,
            'filters': {
                'attr': 'servicegroups',
            },
        },
        'has_been_checked': {
            'description': 'Whether the service already has been checked (0/1)',
            'datatype': int,
        },
        'high_flap_threshold': {
            'description': 'High threshold of flap detection',
            'datatype': float,
        },
        'icon_image': {
            'description': 'The name of an image to be used as icon in the web interface',
        },
        'icon_image_alt': {
            'description': 'An alternative text for the icon_image for browsers not displaying icons',
        },
        'icon_image_expanded': {
            'description': 'The icon_image with (the most important) macros expanded',
            'function': lambda tem: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'impacts': {
            'description': 'List of what the source impact (list of hosts and services)',
            'datatype': list,
        },
        'in_check_period': {
            'description': 'Whether the service is currently in its check period (0/1)',
            'function': lambda tem: False, #FIXME
            'datatype': bool,
            'projection': [],
            'filters': {},
        },
        'in_notification_period': {
            'description': 'Whether the service is currently in its notification period (0/1)',
            'function': lambda tem: False, #FIXME
            'datatype': bool,
            'projection': [],
            'filters': {},
        },
        'initial_state': {
            'description': 'The initial state of the service',
        },
        'is_executing': {
            'description': 'is there a service check currently running... (0/1)',
            'function': lambda item: False,  # REPAIRME # value in scheduler is not real-time
            'datatype': bool,
            'projection': [],
            'filters': {},
        },
        'is_flapping': {
            'description': 'Whether the service is flapping (0/1)',
            'datatype': bool,
        },
        'is_impact': {
            'description': 'Whether the host state is an impact or not (0/1)',
            'datatype': bool,
        },
        'is_problem': {
            'description': 'Whether the host state is a problem or not (0/1)',
            'datatype': bool,
        },
        'labels': {
            'description': 'Arbitrary labels (separated by comma character)',
            'datatype': list,
        },
        'latency': {
            'description': 'Time difference between scheduled check time and actual check time',
            'datatype': float,
        },
        'last_check': {
            'description': 'The time of the last check (Unix timestamp)',
            'function': lambda item: int(item.last_chk),
            'datatype': int,
        },
        'last_hard_state': {
            'description': 'The last hard state of the service',
            'datatype': int,
        },
        'last_hard_state_change': {
            'description': 'The time of the last hard state change (Unix timestamp)',
            'datatype': int,
        },
        'last_notification': {
            'description': 'The time of the last notification (Unix timestamp)',
            'datatype': int,
        },
        'last_state': {
            'description': 'The last state of the service',
        },
        'last_state_change': {
            'description': 'The time of the last state change (Unix timestamp)',
            'datatype': int,
        },
        'last_time_critical': {
            'description': 'The last time the service was CRITICAL (Unix timestamp)',
            'datatype': int,
        },
        'last_time_warning': {
            'description': 'The last time the service was in WARNING state (Unix timestamp)',
            'datatype': int,
        },
        'last_time_ok': {
            'description': 'The last time the service was OK (Unix timestamp)',
            'datatype': int,
        },
        'last_time_unknown': {
            'description': 'The last time the service was UNKNOWN (Unix timestamp)',
            'datatype': int,
        },
        'latency': {
            'description': 'Time difference between scheduled check time and actual check time',
            'datatype': int,
        },
        'long_plugin_output': {
            'description': 'Unabbreviated output of the last check plugin',
            'filter': 'long_output',
        },
        'low_flap_threshold': {
            'description': 'Low threshold of flap detection',
            'datatype': float,
        },
        'max_check_attempts': {
            'description': 'The maximum number of check attempts',
            'datatype': int,
        },
        'modified_attributes': {
            'description': 'A bitmask specifying which attributes have been modified',
            'function': lambda item: len(item["modified_attributes"]),
            'datatype': int,
        },
        'modified_attributes_list': {
            'description': 'A list of all modified attributes',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'next_check': {
            'description': 'The scheduled time of the next check (Unix timestamp)',
            'datatype': int,
            'filter': {
                'pre': ['next_chk']
            },
        },
        'next_notification': {
            'description': 'The time of the next notification (Unix timestamp)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': [],
            'filters': {},
        },
        'notes': {
            'description': 'Optional notes about the service',
        },
        'notes_expanded': {
            'description': 'The notes with (the most important) macros expanded',
            'function': lambda item: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'notes_url': {
            'description': 'An optional URL for additional notes about the service',
        },
        'notes_url_expanded': {
            'description': 'The notes_url with (the most important) macros expanded',
            'function': lambda item: MacroResolver().resolve_simple_macros_in_string(item.notes_url, item.get_data_for_checks()),
        },
        'notification_interval': {
            'description': 'Interval of periodic notification or 0 if its off',
            'datatype': float,
        },
        'notification_options': {
            'description': 'The options controlling when notification should be sent',
            'datatype': list,
        },
        'notification_period': {
            'description': 'The name of the notification period of the service. It this is empty, service problems are always notified.',
        },
        'notifications_enabled': {
            'description': 'Whether notifications are enabled for the service (0/1)',
            'datatype': bool,
        },
        'no_more_notifications': {
            'description': 'Whether to stop sending notifications (0/1)',
            'datatype': bool,
        },
        'obsess_over_service': {
            'description': 'Whether \'obsess_over_service\' is enabled for the service (0/1)',
            'datatype': bool,
        },
        'parent_dependencies': {
            'description': 'List of the dependencies (logical, network or business one) of this service.',
            'datatype': list,
        },
        'percent_state_change': {
            'description': 'Percent state change',
            'datatype': float,
        },
        'perf_data': {
            'description': 'Performance data of the last check plugin',
        },
        'plugin_output': {
            'description': 'Output of the last check plugin',
            'filters': {
                'attr': 'output',
            },
        },
        'pnpgraph_present': {
            'description': 'Whether there is a PNP4Nagios graph present for this service (0/1)',
            'function': lambda item: find_pnp_perfdata_xml(item.get_full_name(), req),
            'datatype': int,
        },
        'poller_tag': {
            'description': 'Poller Tag',
        },
        'process_performance_data': {
            'description': 'Whether processing of performance data is enabled for the service (0/1)',
            'datatype': bool,
            'filters': {
                'attr': 'process_perf_data',
            },
        },
        'retry_interval': {
            'description': 'Number of basic interval lengths between checks when retrying after a soft error',
            'datatype': float,
        },
        'scheduled_downtime_depth': {
            'description': 'The number of scheduled downtimes the service is currently in',
            'datatype': int,
        },
        'service_description': {
            'description': 'Description of the service (also used as key)',
        },
        'servicegroups': {
            'description': 'A list of all service groups the service is in',
            'datatype': list,
            'filters': {
                'attr': 'servicegroups',
            },
        },
        'source_problems': {
            'description': 'The name of the source problems (host or service)',
            'function': lambda item: "",  # REPAIRME
            'datatype': list,
        },
        'state': {
            'description': 'The current state of the service (0: OK, 1: WARN, 2: CRITICAL, 3: UNKNOWN)',
            'datatype': int,
            'filters': {
                'attr': 'state_id',
            },
        },
        'state_type': {
            'description': 'The type of the current state (0: soft, 1: hard)',
            'datatype': int,
            'filters': {
                'attr': 'state_type_id',
            },
        },
    },
    'ServiceLink': {
        'service_accept_passive_checks': {
            'description': 'Whether passive service checks are accepted (0/1)',
            'function': lambda item: linked_attr(item, "service", "passive_checks_enabled", True),
            'datatype': bool,
            'projection': [
                'service.passive_checks_enabled',
            ],
            'filters': {},
        },
        'service_acknowledged': {
            'description': 'Whether the current service problem has been acknowledged (0/1)',
            'function': lambda item: linked_attr(item, "service", "problem_has_been_acknowledged", False),
            'datatype': bool,
            'projection': [
                'service.problem_has_been_acknowledged',
            ],
            'filters': {},
        },
        'service_acknowledgement_type': {
            'description': 'Type of acknowledgement (0: none, 1: normal, 2: stick)',
            'function': lambda item: linked_attr(item, "service", "acknowledgement_type", 0),
            'datatype': int,
            'projection': [
                'service.acknowledgement_type',
            ],
            'filters': {},
        },
        'service_action_url': {
            'description': 'An optional URL to custom actions or information about this service',
            'function': lambda item: linked_attr(item, "service", "action_url"),
            'projection': [
                'service.action_url',
            ],
            'filters': {},
        },
        'service_action_url_expanded': {
            'description': 'The same as action_url, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'service_active_checks_enabled': {
            'description': 'Whether active checks are enabled for the service (0/1)',
            'function': lambda item: linked_attr(item, "service", "active_checks_enabled", True),
            'type': bool,
            'projection': [
                'service.active_checks_enabled',
            ],
            'filters': {},
        },
        'service_check_command': {
            'description': 'Nagios command used for active checks',
            'function': lambda item: linked_attr(item, "service", "check_command"),
            'projection': [
                'service.check_command',
            ],
            'filters': {},
        },
        'service_check_interval': {
            'description': 'Number of basic interval lengths between two scheduled checks of the service',
            'function': lambda item: linked_attr(item, "service", "check_interval", 0),
            'datatype': float,
            'projection': [
                'service.check_interval',
            ],
            'filters': {},
        },
        'service_check_options': {
            'description': 'The current check option, forced, normal, freshness... (0-2)',
            'function': lambda item: linked_attr(item, "service", "check_options"),
            'type': list,
            'projection': [
                'service.check_options',
            ],
            'filters': {},
        },
        'service_check_period': {
            'description': 'Time period in which this service will be checked. If empty then the service will always be checked.',
            'function': lambda item: linked_attr(item, "service", "check_period"),
            'projection': [
                'service.check_period',
            ],
            'filters': {},
        },
        'service_check_type': {
            'description': 'Type of check (0: active, 1: passive)',
            'function': lambda item: 0,  # REPAIRME
            'datatype': int,
            'projection': [],
            'filters': {},
        },
        'service_checks_enabled': {
            'description': 'Whether active checks of the service are enabled (0/1)',
            'function': lambda item: linked_attr(item, "service", "checks_enabled", True),
            'datatype': bool,
            'projection': [
                'service.checks_enabled',
            ],
            'filters': {},
        },
        'service_comments': {
            'description': 'A list of the ids of all comments of this service',
            'function': lambda item: linked_attr(item, "service", "comments", []),
            'datatype': list,
            'projection': [
                'service.comments',
            ],
            'filters': {},
        },
        'service_comments_with_info': {
            'description': 'A list of all comments of the service with id, author and comment',
            'function': lambda item: [],  #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'service_contacts': {
            'description': 'A list of all contacts of this service, either direct or via a contact group',
            'function': lambda item: linked_attr(item, "service", "contacts", []),
            'datatype': list,
            'projection': [
                'service.contacts',
            ],
            'filters': {},
        },
        'service_contact_groups': {
            'description': 'A list of all contact groups this service is in',
            'function': lambda item: linked_attr(item, "service", "contact_groups", []),
            'datatype': list,
            'projection': [
                'service.contact_groups',
            ],
            'filters': {},
        },
        'service_current_attempt': {
            'description': 'Number of the current check attempts',
            'function': lambda item: linked_attr(item, "service", "attempt", 0),
            'datatype': int,
            'projection': [
                'service.attempt',
            ],
            'filters': {},
        },
        'service_current_notification_number': {
            'description': 'Number of the current notification',
            'function': lambda item: linked_attr(item, "service", "current_notification_number", 0),
            'datatype': int,
            'projection': [
                'service.current_notification_number',
            ],
            'filters': {},
        },
        'service_custom_variables': {
            'description': 'A dictionary of the custom variables of the service',
            'function': lambda item: [], #FIXME
            'type': list,
            'projection': [],
            'filters': {},
        },
        'service_custom_variable_names': {
            'description': 'A list of the names of all custom variables of the service',
            'function': lambda item: [], #FIXME
            'type': list,
            'projection': [],
            'filters': {},
        },
        'service_custom_variable_values': {
            'description': 'A list of the values of the custom variables of the service',
            'function': lambda item: [], #FIXME
            'type': list,
            'projection': [],
            'filters': {},
        },
        'service_display_name': {
            'description': 'Optional display name of the service - not used by Nagios\' web interface',
            'function': lambda item: linked_attr(item, "service", "display_name"),
            'projection': [
                'service.display_name',
            ],
            'filters': {},
        },
        'service_downtimes': {
            'description': 'A list of the ids of all scheduled downtimes of this service',
            'function': lambda item: linked_attr(item, "service", "downtimes", []),
            'datatype': list,
            'projection': [
                'service.display_name',
            ],
            'filters': {},
        },
        'service_downtimes_with_info': {
            'description': 'A list of the all scheduled downtimes of the service with id, author and comment',

            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'service_event_handler': {
            'description': 'Nagios command used as event handler of this service',
            'function': lambda item: linked_attr(item, "service", "event_handler"),
            'projection': [
                'service.event_handler',
            ],
            'filters': {},
        },
        'service_event_handler_enabled': {
            'description': 'Whether event handling is enabled for the service (0/1)',
            'function': lambda item: linked_attr(item, "service", "event_handler_enabled", True),
            'datatype': bool,
            'projection': [
                'service.event_handler_enabled',
            ],
            'filters': {},
        },
        'service_execution_time': {
            'description': 'Time the service check needed for execution',
            'function': lambda item: linked_attr(item, "service", "execution_time", 0),
            'datatype': float,
            'projection': [
                'service.execution_time',
            ],
            'filters': {},
        },
        'service_first_notification_delay': {
            'description': 'Delay before the first notification',
            'function': lambda item: linked_attr(item, "service", "first_notification_delay", 0),
            'datatype': float,
            'projection': [
                'service.first_notification_delay',
            ],
            'filters': {},
        },
        'service_flap_detection_enabled': {
            'description': 'Whether flap detection is enabled (0/1)',
            'function': lambda item: linked_attr(item, "service", "flap_detection_enabled", True),
            'datatype': bool,
            'projection': [
                'service.flap_detection_enabled',
            ],
            'filters': {},
        },
        'service_groups': {
            'description': 'A list of all service groups this service is in',
            'function': lambda item: linked_attr(item, "service", "servicegroups", []),
            'datatype': list,
            'projection': [
                'service.servicegroups',
            ],
            'filters': {},
        },
        'service_has_been_checked': {
            'description': 'Whether the service has already been checked (0/1)',
            'function': lambda item: linked_attr(item, "service", "has_been_checked", False),
            'datatype': bool,
            'projection': [
                'service.has_been_checked',
            ],
            'filters': {},
        },
        'service_high_flap_threshold': {
            'description': 'High threshold of flap detection',
            'function': lambda item: linked_attr(item, "service", "high_flap_threshold", 0),
            'datatype': float,
            'projection': [
                'service.high_flap_threshold',
            ],
            'filters': {},
        },
        'service_icon_image': {
            'description': 'The name of an image file to be used in the web pages',
            'function': lambda item: linked_attr(item, "service", "icon_image"),
            'projection': [
                'service.icon_image',
            ],
            'filters': {},
        },
        'service_icon_image_alt': {
            'description': 'Alternative text for the icon_image',
            'function': lambda item: linked_attr(item, "service", "icon_image_alt"),
            'projection': [
                'service.icon_image_alt',
            ],
            'filters': {},
        },
        'service_icon_image_expanded': {
            'description': 'The same as icon_image, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'service_in_check_period': {
            'description': 'Whether this service is currently in its check period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projection': [],
            'filters': {},
        },
        'service_in_notification_period': {
            'description': 'Whether this service is currently in its notification period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projection': [],
            'filters': {},
        },
        'service_initial_state': {
            'description': 'Initial service state',
            'function': lambda item: linked_attr(item, "service", "initial_state"),
            'projection': [
                'service.initial_state',
            ],
            'filters': {},
        },
        'service_is_executing': {
            'description': 'is there a service check currently running... (0/1)',
            'function': lambda item: False,  #FIXME # value in scheduler is not real-time
            'datatype': bool,
            'projection': [],
            'filters': {},
        },
        'service_is_flapping': {
            'description': 'Whether the service state is flapping (0/1)',
            'function': lambda item: linked_attr(item, "service", "is_flapping", False),
            'datatype': bool,
            'projection': [
                'service.is_flapping',
            ],
            'filters': {},
        },
        'service_last_check': {
            'description': 'Time of the last check (Unix timestamp)',
            'function': lambda item: linked_attr(item, "service", "last_chk", 0),
            'datatype': int,
            'projection': [
                'service.last_chk',
            ],
            'filters': {},
        },
        'service_last_hard_state': {
            'description': 'Last hard state',
            'function': lambda item: linked_attr(item, "service", "last_hard_state_id", 0),
            'datatype': int,
            'projection': [
                'service.last_hard_state_id',
            ],
            'filters': {},
        },
        'service_last_hard_state_change': {
            'description': 'Time of the last hard state change (Unix timestamp)',
            'function': lambda item: linked_attr(item, "service", "last_hard_state_change", 0),
            'datatype': int,
            'projection': [
                'service.last_hard_state_change',
            ],
            'filters': {},
        },
        'service_last_notification': {
            'description': 'Time of the last notification (Unix timestamp)',
            'function': lambda item: linked_attr(item, "service", "last_notification", 0),
            'datatype': int,
            'projection': [
                'service.last_notification',
            ],
            'filters': {},
        },
        'service_last_state': {
            'description': 'State before last state change',
            'function': lambda item: linked_attr(item, "service", "last_state"),
            'projection': [
                'service.last_state',
            ],
            'filters': {},
        },
        'service_last_state_change': {
            'description': 'Time of the last state change - soft or hard (Unix timestamp)',
            'function': lambda item: linked_attr(item, "service", "last_state_change", 0),
            'datatype': int,
            'projection': [
                'service.last_state_change',
            ],
            'filters': {},
        },
        'service_last_time_down': {
            'description': 'The last time the service was DOWN (Unix timestamp)',
            'function': lambda item: linked_attr(item, "service", "last_time_down", 0),
            'datatype': int,
            'projection': [
                'service.last_time_down',
            ],
            'filters': {},
        },
        'service_last_time_unreachable': {
            'description': 'The last time the service was UNREACHABLE (Unix timestamp)',
            'function': lambda item: linked_attr(item, "service", "last_time_unreachable", 0),
            'datatype': int,
            'projection': [
                'service.last_time_unreachable',
            ],
            'filters': {},
        },
        'service_last_time_up': {
            'description': 'The last time the service was UP (Unix timestamp)',
            'function': lambda item: linked_attr(item, "service", "last_time_up", 0),
            'datatype': int,
            'projection': [
                'service.last_time_up',
            ],
            'filters': {},
        },
        'service_latency': {
            'description': 'Time difference between scheduled check time and actual check time',
            'function': lambda item: linked_attr(item, "service", "latency", 0),
            'datatype': float,
            'projection': [
                'service.latency',
            ],
            'filters': {},
        },
        'service_long_plugin_output': {
            'description': 'Complete output from check plugin',
            'function': lambda item: linked_attr(item, "service", "long_output"),
            'projection': [
                'service.long_output',
            ],
            'filters': {},
        },
        'service_low_flap_threshold': {
            'description': 'Low threshold of flap detection',
            'function': lambda item: linked_attr(item, "service", "low_flap_threshold", 0),
            'datatype': float,
            'projection': [
                'service.low_flap_threshold',
            ],
            'filters': {},
        },
        'service_max_check_attempts': {
            'description': 'Max check attempts for active service checks',
            'function': lambda item: linked_attr(item, "service", "max_checks_attempts", 0),
            'datatype': int,
            'projection': [
                'service.max_checks_attempts',
            ],
            'filters': {},
        },
        'service_modified_attributes': {
            'description': 'A bitmask specifying which attributes have been modified',
            'function': lambda item: len(linked_attr(item, "service", "modified_attributes", 0)),
            'datatype': int,
            'projection': [
                'service.modified_attributes',
            ],
            'filters': {},
        },
        'service_modified_attributes_list': {
            'description': 'A list of all modified attributes',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'service_next_check': {
            'description': 'Scheduled time for the next check (Unix timestamp)',
            'function': lambda item: linked_attr(item, "service", "next_chk", 0),
            'datatype': int,
            'projection': [
                'service.next_chk',
            ],
            'filters': {},
        },
        'service_next_notification': {
            'description': 'Time of the next notification (Unix timestamp)',
            'function': lambda item: linked_attr(item, "service", "next_notification", 0),
            'datatype': int,
            'projection': [
                'service.next_notifications',
            ],
            'filters': {},
        },
        'service_notes': {
            'description': 'Optional notes about the service',
            'function': lambda item: linked_attr(item, "service", "notes"),
            'projection': [
                'service.notes',
            ],
            'filters': {},
        },
        'service_notes_expanded': {
            'description': 'The same as notes, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'service_notes_url': {
            'description': 'An optional URL with further information about the service',
            'function': lambda item: linked_attr(item, "service", "notes_url"),
            'projection': [
                'service.notes_url',
            ],
            'filters': {},
        },
        'service_notes_url_expanded': {
            'description': 'Same es notes_url, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projection': [],
            'filters': {},
        },
        'service_notification_interval': {
            'description': 'Interval of periodic notification or 0 if its off',
            'function': lambda item: linked_attr(item, "service", "notification_interval", 0),
            'datatype': float,
            'projection': [
                'service.notification_interval',
            ],
            'filters': {},
        },
        'service_notification_period': {
            'description': 'Time period in which problems of this service will be notified. If empty then notification will be always',
            'function': lambda item: linked_attr(item, "service", "notification_period"),
            'projection': [
                'service.notification_period',
            ],
            'filters': {},
        },
        'service_notifications_enabled': {
            'description': 'Whether notifications of the service are enabled (0/1)',
            'function': lambda item: linked_attr(item, "service", "notifications_enabled", True),
            'datatype': bool,
            'projection': [
                'service.notifications_enabled',
            ],
            'filters': {},
        },
        'service_no_more_notifications': {
            'description': 'Whether to stop sending notifications (0/1)',
            'function': lambda item: linked_attr(item, "service", "no_more_notifications", True),
            'datatype': bool,
            'projection': [
                'service.no_more_notifications',
            ],
            'filters': {},
        },
        'service_percent_state_change': {
            'description': 'Percent state change',
            'function': lambda item: linked_attr(item, "service", "percent_state_change", 0),
            'datatype': float,
            'projection': [
                'service.percent_state_change',
            ],
            'filters': {},
        },
        'service_perf_data': {
            'description': 'Optional performance data of the last service check',
            'function': lambda item: linked_attr(item, "service", "perf_data"),
            'projection': [
                'service.perf_data',
            ],
            'filters': {},
        },
        'service_plugin_output': {
            'description': 'Output of the last service check',
            'function': lambda item: linked_attr(item, "service", "output"),
            'projection': [
                'service.output',
            ],
            'filters': {},
        },
        'service_pnpgraph_present': {
            'description': 'Whether there is a PNP4Nagios graph present for this service (0/1)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': [],
            'filters': {},
        },
        'service_process_performance_data': {
            'description': 'Whether processing of performance data is enabled (0/1)',
            'function': lambda item: linked_attr(item, "service", "process_performances_data", True),
            'datatype': bool,
            'projection': [
                'service.process_performances_data',
            ],
            'filters': {},
        },
        'service_retry_interval': {
            'description': 'Number of basic interval lengths between checks when retrying after a soft error',
            'function': lambda item: linked_attr(item, "service", "retry_interval", 0),
            'datatype': float,
            'projection': [
                'service.retry_interval',
            ],
            'filters': {},
        },
        'service_scheduled_downtime_depth': {
            'description': 'The number of downtimes this service is currently in',
            'function': lambda item: linked_attr(item, "service", "scheduled_downtime_depth", 0),
            'datatype': int,
            'projection': [
                'service.scheduled_downtime_depth',
            ],
            'filters': {},
        },
        'service_state': {
            'description': 'The current state of the service (0: up, 1: down, 2: unreachable)',
            'function': lambda item: linked_attr(item, "service", "state_id", 0),
            'datatype': int,
            'projection': [
                'service.state_id',
            ],
            'filters': {},
        },
        'service_state_type': {
            'description': 'Type of the current state (0: soft, 1: hard)',
            'function': lambda item: linked_attr(item, "service", "state_type_id", 0),
            'datatype': int,
            'projection': [
                'service.state_type_id',
            ],
            'filters': {},
        },
    },
    'ServicesLink': {
        'num_services': {
            'description': 'The total number of services of the host',
            'function': lambda item: len(item["services"]),
            'projection': ['services.service_description'],
            'filters': {},
        },
        'num_services_crit': {
            'description': 'The number of the host\'s services with the soft state CRIT',
            'function': lambda item: state_count(item, "services", 0, 2),
            'datatype': int,
            'projection': [
                'services.state',
                'services.state_id',
                'services.state_type_id'
            ],
            'filters': {},
        },
        'num_services_hard_crit': {
            'description': 'The number of the host\'s services with the hard state CRIT',
            'function': lambda item: state_count(item, "services", 1, 2),
            'datatype': int,
            'projection': [
                'services.state',
                'services.state_id',
                'services.state_type_id'
            ],
            'filters': {},
        },
        'num_services_hard_ok': {
            'description': 'The number of the host\'s services with the hard state OK',
            'function': lambda item: state_count(item, "services", 1, 0),
            'datatype': int,
            'projection': [
                'services.state',
                'services.state_id',
                'services.state_type_id'
            ],
            'filters': {},
        },
        'num_services_hard_unknown': {
            'description': 'The number of the host\'s services with the hard state UNKNOWN',
            'function': lambda item: state_count(item, "services", 1, 3),
            'datatype': int,
            'projection': [
                'services.state',
                'services.state_id',
                'services.state_type_id'
            ],
            'filters': {},
        },
        'num_services_hard_warn': {
            'description': 'The number of the host\'s services with the hard state WARN',
            'function': lambda item: state_count(item, "services", 1, 1),
            'datatype': int,
            'projection': [
                'services.state',
                'services.state_id',
                'services.state_type_id'
            ],
            'filters': {},
        },
        'num_services_ok': {
            'description': 'The number of the host\'s services with the soft state OK',
            'function': lambda item: state_count(item, "services", 0, 0),
            'datatype': int,
            'projection': [
                'services.state',
                'services.state_id',
                'services.state_type_id'
            ],
            'filters': {},
        },
        'num_services_pending': {
            'description': 'The number of the host\'s services which have not been checked yet (pending)',
            'function': lambda item: state_count(item, "services", state_id="PENDING"),
            'datatype': int,
            'projection': [
                'services.state',
                'services.state_id',
                'services.state_type_id'
            ],
            'filters': {},
        },
        'num_services_unknown': {
            'description': 'The number of the host\'s services with the soft state UNKNOWN',
            'function': lambda item: state_count(item, "services", 0, 3),
            'datatype': int,
            'projection': [
                'services.state',
                'services.state_id',
                'services.state_type_id'
            ],
            'filters': {},
        },
        'num_services_warn': {
            'description': 'The number of the host\'s services with the soft state WARN',
            'function': lambda item: state_count(item, "services", 0, 1),
            'datatype': int,
            'projection': [
                'services.state',
                'services.state_id',
                'services.state_type_id'
            ],
            'filters': {},
        },
        'worst_service_hard_state': {
            'description': 'The worst state of all services that belong to a host of this group (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: state_worst(item, "services", 1),
            'datatype': int,
            'projection': [
                'services.state',
                'services.state_id',
                'services.state_type_id'
            ],
            'filters': {},
        },
        'worst_service_state': {
            'description': 'The worst state of all services that belong to a host of this group (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: state_worst(item, "services", 0),
            'datatype': int,
            'projection': [
                'services.state',
                'services.state_id',
                'services.state_type_id'
            ],
            'filters': {},
            'datatype': int,
        },
    },
    'HostsLink': {
        'num_hosts': {
            'description': 'The total number of hosts in the group',
            'function': lambda item: len(item["hosts"]),
            'projection': ["hosts.host_name"],
        },
        'num_hosts_down': {
            'description': 'The number of hosts in the group that are down',
            'function': lambda item: state_count(item, "hosts", 1, 1),
            'datatype': int,
            'projection': [
                'hosts.state',
                'hosts.state_id',
                'hosts.state_type_id'
            ],
            'filters': {},
        },
        'num_hosts_pending': {
            'description': 'The number of hosts in the group that are pending',
            'function': lambda item: state_count(item, "hosts", state_id="PENDING"),
            'datatype': int,
            'projection': [
                'hosts.state',
                'hosts.state_id',
                'hosts.state_type_id'
            ],
            'filters': {},
        },
        'num_hosts_unreach': {
            'function': lambda item: state_count(item, "hosts", 1, 2),
            'datatype': int,
            'projection': [
                'hosts.state',
                'hosts.state_id',
                'hosts.state_type_id'
            ],
            'filters': {},
        },
        'num_hosts_up': {
            'description': 'The number of hosts in the group that are up',
            'function': lambda item: state_count(item, "hosts", 1, 0),
            'datatype': int,
            'projection': [
                'hosts.state',
                'hosts.state_id',
                'hosts.state_type_id'
            ],
            'filters': {},
        },
        'worst_host_state': {
            'description': 'The worst state of all of the groups\' hosts (UP <= UNREACHABLE <= DOWN)',
            'function': lambda item: state_worst(item, "hosts", 1),
            'datatype': int,
            'projection': [
                'hosts.state',
                'hosts.state_id',
                'hosts.state_type_id'
            ],
            'filters': {},
        },
    },
    'Hostgroup': {
        'action_url': {
            'description': 'An optional URL to custom actions or information about the hostgroup',
        },
        'alias': {
            'description': 'An alias of the hostgroup',
        },
        'hostgroup_name': {
            'description': 'Name of the hostgroup',
        },
        'members': {
            'description': 'A list of all host names that are members of the hostgroup',
            'datatype': list,
        },
        'members_with_state': {
            'description': 'A list of all host names that are members of the hostgroup together with state and has_been_checked',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'name': {
            'description': 'Name of the hostgroup',
            'filters': {
                'attr': 'hostgroup_name',
            },
        },
        'notes': {
            'description': 'Optional notes to the hostgroup',
        },
        'notes_url': {
            'description': 'An optional URL with further information about the hostgroup',
        },
        'num_hosts': {
            'description': 'The total number of hosts in the group',
            'function': lambda item: len(item.members),
            'projection': ["hosts.host_name"],
        },
        'num_hosts_down': {
            'description': 'The number of hosts in the group that are down',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': ["hosts.state_id"],
            'filters': {},
        },
        'num_hosts_pending': {
            'description': 'The number of hosts in the group that are pending',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': ["hosts.state_id"],
            'filters': {},
        },
        'num_hosts_unreach': {
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': ["hosts.state_id"],
            'filters': {},
        },
        'num_hosts_up': {
            'description': 'The number of hosts in the group that are up',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': ["hosts.state_id"],
            'filters': {},
        },
        'num_services': {
            'description': 'The total number of services of hosts in this group',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': ["services.state_id"],
            'filters': {},
        },
        'worst_host_state': {
            'description': 'The worst state of all of the groups\' hosts (UP <= UNREACHABLE <= DOWN)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': ["services.state_id"],
            'filters': {},
        },
    },
    'Servicegroup': {
        'action_url': {
            'description': 'An optional URL to custom notes or actions on the service group',
        },
        'alias': {
            'description': 'An alias of the service group',
        },
        'members': {
            'description': 'A list of all members of the service group as host/service pairs',
            'datatype': list,
        },
        'members_with_state': {
            'description': 'A list of all members of the service group with state and has_been_checked',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'name': {
            'description': 'The name of the service group',
            'filters': {
                'attr': 'servicegroup_name',
            },
        },
        'notes': {
            'description': 'Optional additional notes about the service group',
        },
        'notes_url': {
            'description': 'An optional URL to further notes on the service group',
        },
        'num_services': {
            'description': 'The total number of services in the group',
            'function': lambda item: len(item["members"]),
            'datatype': int,
        },
        'num_services_crit': {
            'description': 'The number of services in the group that are CRIT',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projection': ["services.state_id"],
            'filters': {},
        },
    },
    'Contact': {
        'address1': {
            'description': 'The additional field address1',
        },
        'address2': {
            'description': 'The additional field address2',
        },
        'address3': {
            'description': 'The additional field address3',
        },
        'address4': {
            'description': 'The additional field address4',
        },
        'address5': {
            'description': 'The additional field address5',
        },
        'address6': {
            'description': 'The additional field address6',
        },
        'alias': {
            'description': 'The full name of the contact',
        },
        'can_submit_commands': {
            'description': 'Whether the contact is allowed to submit commands (0/1)',
            'datatype': bool,
        },
        'contact_name': {
            'description': 'The login name of the contact person',
        },
        'custom_variables': {
            'description': 'A dictionary of the custom variables',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'custom_variable_names': {
            'description': 'A list of all custom variables of the contact',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'custom_variable_values': {
            'description': 'A list of the values of all custom variables of the contact',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projection': [],
            'filters': {},
        },
        'email': {
            'description': 'The email address of the contact',
        },
        'host_notification_period': {
            'description': 'The time period in which the contact will be notified about host problems',
        },
        'host_notifications_enabled': {
            'description': 'Whether the contact will be notified about host problems in general (0/1)',
            'datatype': bool,
        },
        'host_notification_options': {
            'description': 'The options controlling when host notification should be sent to the contact',
            'datatype': list,
        },
        'in_host_notification_period': {
            'description': 'Whether the contact is currently in his/her host notification period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projection': [],
            'filters': {},
        },
        'in_service_notification_period': {
            'description': 'Whether the contact is currently in his/her service notification period (0/1)',
            'function': lambda item: (item.service_notification_period is None and [False] or [item.service_notification_period.is_time_valid(req.tic)])[0],
            'datatype': bool,
        },
        'modified_attributes': {
            'description': 'A bitmask specifying which attributes have been modified',
            'datatype': int,
        },
        'modified_attributes_list': {
            'description': 'A list of all modified attributes',
            'function': lambda item: modified_attributes_names(item),
            'datatype': list,
        },
        'name': {
            'description': 'The login name of the contact person',
            'filter': 'contact_name',
        },
        'pager': {
            'description': 'The pager address of the contact',
        },
        'service_notification_options': {
            'description': 'The options controlling when service notification should be sent to the contact',
            'datatype': list,
        },
        'service_notification_period': {
            'description': 'The time period in which the contact will be notified about service problems',
        },
        'service_notifications_enabled': {
            'description': 'Whether the contact will be notified about service problems in general (0/1)',
            'datatype': bool,
        },

    },
    'Contactgroup': {
        'alias': {
            'description': 'The alias of the contactgroup',
        },
        'contactgroup_name': {
            'description': 'The name of the contactgroup',
        },
        'members': {
            'description': 'A list of all members of this contactgroup',
            'datatype': list,
        },
        'name': {
            'description': 'The name of the contactgroup',
            'filters': {
                'attr': 'contactgroup_name',
            },
        },
    },
    'Timeperiod': {
        'alias': {
            'description': 'The alias of the timeperiod',
        },
        'in': {
            'description': 'Whether we are currently in this period (0/1)',
            'datatype': int,
        },
        'name': {
            'description': 'The name of the timeperiod',
            'filters': {
                'attr': 'timeperiod_name',
            },
        },
        'timeperiod_name': {
            'description': 'The name of the timeperiod',
        },
    },
    'Command': {
        'command_name': {
            'description': 'The name of the command',
        },
        'command_line': {
            'description': 'The shell command line',
        },
        'line': {
            'description': 'The shell command line',
            'filters': {
                'attr': 'command_line',
            },
        },
        'name': {
            'description': 'The name of the command',
            'filters': {
                'attr': 'command_name',
            },
        },
    },
    'SchedulerLink': {
        'address': {
            'description': 'The ip or dns address of the scheduler',
        },
        'alive': {
            'description': 'If the scheduler is alive or not',
            'datatype': bool,
        },
        'name': {
            'description': 'The name of the scheduler',
            'filters': {
                'attr': 'scheduler_name',
            },
        },
        'port': {
            'description': 'The TCP port of the scheduler',
            'datatype': int,
        },
        'scheduler_name': {
            'description': 'The name of the scheduler',
        },
        'spare': {
            'description': 'If the scheduler is a spare or not',
            'datatype': bool,
        },
        'weight': {
            'description': 'Weight (in terms of hosts) of the scheduler',
            'datatype': int,
        },
    },
    'PollerLink': {
        'address': {
            'description': 'The ip or dns address of the poller',
        },
        'alive': {
            'description': 'If the poller is alive or not',
            'datatype': bool,
        },
        'name': {
            'description': 'The name of the poller',
            'filters': {
                'attr': 'poller_name',
            },
        },
        'poller_name': {
            'description': 'The name of the poller',
        },
        'port': {
            'description': 'The TCP port of the poller',
            'datatype': int,
        },
        'spare': {
            'description': 'If the poller is a spare or not',
            'datatype': bool,
        },
    },
    'ReactionnerLink': {
        'address': {
            'description': 'The ip or dns address of the reactionner',
        },
        'alive': {
            'description': 'If the reactionner is alive or not',
            'datatype': bool,
        },
        'name': {
            'description': 'The name of the reactionner',
            'filters': {
                'attr': 'reactionner_name',
            },
        },
        'port': {
            'description': 'The TCP port of the reactionner',
            'datatype': int,
        },
        'reactionner_name': {
            'description': 'The name of the reactionner',
        },
        'spare': {
            'description': 'If the reactionner is a spare or not',
            'datatype': bool,
        },
    },
    'BrokerLink': {
        'address': {
            'description': 'The ip or dns address of the broker',
        },
        'alive': {
            'description': 'If the broker is alive or not',
            'datatype': bool,
        },
        'broker_name': {
            'description': 'The name of the broker',
        },
        'name': {
            'description': 'The name of the broker',
            'filters': {
                'attr': 'broker_name',
            },
        },
        'port': {
            'description': 'The TCP port of the broker',
            'datatype': int,
        },
        'spare': {
            'description': 'If the broker is a spare or not',
            'datatype': bool,
        },
    },
    'Problem': {
        'impacts': {
            'description': 'List of what the source impact (list of hosts and services)',
        },
        'source': {
            'description': 'The source name of the problem (host or service)',
        },
    },
    'Downtime': {
        'author': {
            'description': 'The contact that scheduled the downtime',
        },
        'comment': {
            'description': 'A comment text',
        },
        'duration': {
            'description': 'The duration of the downtime in seconds',
            'datatype': int,
        },
        'end_time': {
            'description': 'The end time of the downtime as UNIX timestamp',
            'datatype': int,
        },
        'entry_time': {
            'description': 'The time the entry was made as UNIX timestamp',
            'datatype': int,
        },
        'fixed': {
            'description': 'A 1 if the downtime is fixed, a 0 if it is flexible',
            'datatype': bool,
        },
        'id': {
            'description': 'The id of the downtime',
            'datatype': int,
        },
        'is_service': {
            'description': '0, if this entry is for a host, 1 if it is for a service',
            'function': lambda item: 'service_description' in item["ref"],
            'datatype': bool,
        },
        'start_time': {
            'description': 'The start time of the downtime as UNIX timestamp',
            'datatype': int,
        },
        'triggered_by': {
            'description': 'The id of the downtime this downtime was triggered by or 0 if it was not triggered by another downtime',
            'datatype': int,
        },
        'type': {
            'description': 'The type of the downtime: 0 if it is active, 1 if it is pending',
            'function': lambda item: {True: 0, False: 1}[item.is_in_effect],
            'datatype': int,
        },
    },
    'Comment': {
        'author': {
            'description': 'The contact that entered the comment',
        },
        'comment': {
            'description': 'A comment text',
        },
        'entry_time': {
            'description': 'The time the entry was made as UNIX timestamp',
            'datatype': int,
        },
        'entry_type': {
            'description': 'The type of the comment: 1 is user, 2 is downtime, 3 is flap and 4 is acknowledgement',
            'datatype': int,
        },
        'expire_time': {
            'description': 'The time of expiry of this comment as a UNIX timestamp',
            'datatype': int,
        },
        'expires': {
            'description': 'Whether this comment expires',
            'datatype': bool,
        },
        'id': {
            'description': 'The id of the comment',
            'datatype': int,
        },
        'is_service': {
            'description': '0, if this entry is for a host, 1 if it is for a service',
            'datatype': bool,
        },
        'persistent': {
            'description': 'Whether this comment is persistent (0/1)',
            'datatype': bool,
        },
        'source': {
            'description': 'The source of the comment (0 is internal and 1 is external)',
            'datatype': int,
        },
        'type': {
            'description': 'The type of the comment: 1 is host, 2 is service',
            'datatype': int,
        },
    },
    'Hostsbygroup': {
        'hostgroup_action_url': {
            'description': 'An optional URL to custom actions or information about the hostgroup',
            'function': lambda item: linked_attr(item, "hostgroup", "action_url"),
            'filters': {
                'attr': 'hostgroup.action_url',
            },
        },
        'hostgroup_alias': {
            'description': 'An alias of the hostgroup',
            'function': lambda item: linked_attr(item, "hostgroup", "alias"),
            'filters': {
                'attr': 'hostgroup.alias',
            },
        },
        'hostgroup_members': {
            'description': 'A list of all host names that are members of the hostgroup',
            'function': lambda item: linked_attr(item, "hostgroup", "members"),
            'datatype': list,
            'filters': {
                'attr': 'hostgroup.members',
            },
        },
        'hostgroup_members_with_state': {
            'description': 'A list of all host names that are members of the hostgroup together with state and has_been_checked',
            'function': lambda item: [],  # REPAIRME
            'datatype': list,
        },
        'hostgroup_name': {
            'description': 'Name of the hostgroup',
            'function': lambda item: linked_attr(item, "hostgroup", "hostgroup_name"),
            'filters': {
                'attr': 'hostgroup.hostgroup_name',
            },
        },
        'hostgroup_notes': {
            'description': 'Optional notes to the hostgroup',
            'function': lambda item: linked_attr(item, "hostgroup", "notes"),
            'filters': {
                'attr': 'hostgroup.notes',
            },
        },
        'hostgroup_notes_url': {
            'description': 'An optional URL with further information about the hostgroup',
            'function': lambda item: linked_attr(item, "hostgroup", "notes_url"),
            'filters': {
                'attr': 'hostgroup.notes_url',
            },
        },
        'hostgroup_num_hosts': {
            'description': 'The total number of hosts in the group',
            'function': lambda item: len(item["hostgroup_hosts"]),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.host_name',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_hosts_down': {
            'description': 'The number of hosts in the group that are down',
            'function': lambda item: state_count(item, "hostgroup_hosts", 1, 1),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.state',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_hosts_pending': {
            'description': 'The number of hosts in the group that are pending',
            'function': lambda item: state_count(item, "hostgroup_hosts", state_id="PENDING"),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.state',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_hosts_unreach': {
            'description': 'The number of hosts in the group that are unreachable',
            'function': lambda item: state_count(item, "hostgroup_hosts", 1, 2),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.state',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_hosts_up': {
            'description': 'The number of hosts in the group that are up',
            'function': lambda item: state_count(item, "hostgroup_hosts", 1, 0),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.state',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services': {
            'description': 'The total number of services of hosts in this group',
            'function': lambda item: len(item["hostgroup_services"]),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.state',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_crit': {
            'description': 'The total number of services with the state CRIT of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 0, 2),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_hard_crit': {
            'description': 'The total number of services with the state CRIT of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 1, 2),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_hard_ok': {
            'description': 'The total number of services with the state OK of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 1, 0),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_hard_unknown': {
            'description': 'The total number of services with the state UNKNOWN of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 1, 3),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_hard_warn': {
            'description': 'The total number of services with the state WARN of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 1, 1),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_ok': {
            'description': 'The total number of services with the state OK of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 0, 0),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_pending': {
            'description': 'The total number of services with the state Pending of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", state_id="PENDING"),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_unknown': {
            'description': 'The total number of services with the state UNKNOWN of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 0, 3),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_warn': {
            'description': 'The total number of services with the state WARN of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 0, 1),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_worst_host_state': {
            'description': 'The worst state of all of the groups\' hosts (UP <= UNREACHABLE <= DOWN)',
            'function': lambda item: state_worst(item, "hostgroup_hosts", 1),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.state',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_worst_service_hard_state': {
            'description': 'The worst state of all services that belong to a host of this group (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: state_worst(item, "hostgroup_services", 1),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_worst_service_state': {
            'description': 'The worst state of all services that belong to a host of this group (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: state_worst(item, "hostgroup_services", 0),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
    },
    'Servicesbygroup': {
        'servicegroup_action_url': {
            'description': 'An optional URL to custom notes or actions on the service group',
            'function': lambda item: linked_attr(item, "servicegroup", "action_url"),
            'filters': {
                'attr': 'servicegroup.action_url',
            },
        },
        'servicegroup_alias': {
            'description': 'An alias of the service group',
            'function': lambda item: linked_attr(item, "servicegroup", "alias"),
            'filters': {
                'attr': 'servicegroup.alias',
            },
        },
        'servicegroup_members': {
            'description': 'A list of all members of the service group as host/service pairs',
            'function': lambda item: linked_attr(item, "servicegroup", "members"),
            'datatype': list,
            'filters': {
                'attr': 'servicegroup.members',
            },
        },
        'servicegroup_members_with_state': {
            'description': 'A list of all members of the service group with state and has_been_checked',
            'function': lambda item: [],  # REPAIRME
            'datatype': list,
        },
        'servicegroup_name': {
            'description': 'The name of the service group',
            'function': lambda item: linked_attr(item, "servicegroup", "servicegroup_name"),
            'filters': {
                'attr': 'servicegroup.servicegroup_name',
            },
        },
        'servicegroup_notes': {
            'description': 'Optional additional notes about the service group',
            'function': lambda item: linked_attr(item, "servicegroup", "notes"),
            'filters': {
                'attr': 'servicegroup.notes',
            },
        },
        'servicegroup_notes_url': {
            'description': 'An optional URL to further notes on the service group',
            'function': lambda item: linked_attr(item, "servicegroup", "notes_url"),
            'filters': {
                'attr': 'servicegroup.notes_url',
            },
        },
        'servicegroup_num_services': {
            'description': 'The total number of services in the group',
            'function': lambda item: len(item["servicegroup_services"]),
            'datatype': int,
            'projection': [
                'servicegroup_hosts.state',
                'servicegroup_hosts.state_id',
                'servicegroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'servicegroup_num_services_crit': {
            'description': 'The number of services in the group that are CRIT',
            'function': lambda item: state_count(item, "servicegroup_services", 0, 2),
            'datatype': int,
            'projection': [
                'servicegroup_services.state',
                'servicegroup_services.state_id',
                'servicegroup_services.state_type_id'
            ],
            'filters': {}
        },
        'servicegroup_num_services_hard_crit': {
            'description': 'The number of services in the group that are CRIT',
            'function': lambda item: state_count(item, "servicegroup_services", 1, 2),
            'datatype': int,
            'projection': [
                'servicegroup_services.state',
                'servicegroup_services.state_id',
                'servicegroup_services.state_type_id'
            ],
            'filters': {}
        },
        'servicegroup_num_services_hard_ok': {
            'description': 'The number of services in the group that are OK',
            'function': lambda item: state_count(item, "servicegroup_services", 1, 0),
            'datatype': int,
            'projection': [
                'servicegroup_services.state',
                'servicegroup_services.state_id',
                'servicegroup_services.state_type_id'
            ],
            'filters': {}
        },
        'servicegroup_num_services_hard_warn': {
            'description': 'The number of services in the group that are WARN',
            'function': lambda item: state_count(item, "servicegroup_services", 1, 1),
            'datatype': int,
            'projection': [
                'servicegroup_services.state',
                'servicegroup_services.state_id',
                'servicegroup_services.state_type_id'
            ],
            'filters': {}
        },
        'servicegroup_num_services_ok': {
            'description': 'The number of services in the group that are OK',
            'function': lambda item: state_count(item, "servicegroup_services", 0, 0),
            'datatype': int,
            'projection': [
                'servicegroup_services.state',
                'servicegroup_services.state_id',
                'servicegroup_services.state_type_id'
            ],
            'filters': {}
        },
        'servicegroup_num_services_pending': {
            'description': 'The number of services in the group that are PENDING',
            'function': lambda item: state_count(item, "servicegroup_services", state_id="PENDING"),
            'datatype': int,
            'projection': [
                'servicegroup_services.state',
                'servicegroup_services.state_id',
                'servicegroup_services.state_type_id'
            ],
            'filters': {}
        },
        'servicegroup_num_services_unknown': {
            'description': 'The number of services in the group that are UNKNOWN',
            'function': lambda item: state_count(item, "servicegroup_services", 1, 3),
            'datatype': int,
            'projection': [
                'servicegroup_services.state',
                'servicegroup_services.state_id',
                'servicegroup_services.state_type_id'
            ],
            'filters': {}
        },
        'servicegroup_num_services_warn': {
            'description': 'The number of services in the group that are WARN',
            'function': lambda item: state_count(item, "servicegroup_services", 0, 1),
            'datatype': int,
            'projection': [
                'servicegroup_services.state',
                'servicegroup_services.state_id',
                'servicegroup_services.state_type_id'
            ],
            'filters': {}
        },
        'servicegroup_worst_service_state': {
            'description': 'The worst soft state of all of the groups services (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: state_worst(item, "servicegroup_services", 1),
            'datatype': int,
            'projection': [
                'servicegroup_services.state',
                'servicegroup_services.state_id',
                'servicegroup_services.state_type_id'
            ],
            'filters': {}
        },
    },
    'Servicesbyhostgroup': {
        'hostgroups': {
            'description': 'A list of all host groups this service is in',
            'datatype': list,
        },
        'host_groups': {
            'description': 'A list of all host groups this service is in',
            'datatype': list,
            'filters': {
                'attr': 'hostgroups',
            },
        },
        'hostgroup_action_url': {
            'description': 'An optional URL to custom actions or information about the hostgroup',
            'function': lambda item: linked_attr(item, "hostgroup", "action_url"),
            'filters': {
                'attr': 'hostgroup.action_url',
            },
        },
        'hostgroup_alias': {
            'description': 'An alias of the hostgroup',
            'function': lambda item: linked_attr(item, "hostgroup", "alias"),
            'filters': {
                'attr': 'hostgroup.alias',
            },
        },
        'hostgroup_members': {
            'description': 'A list of all host names that are members of the hostgroup',
            'function': lambda item: linked_attr(item, "hostgroup", "members"),
            'datatype': list,
            'filters': {
                'attr': 'hostgroup.members',
            },
        },
        'hostgroup_members_with_state': {
            'description': 'A list of all host names that are members of the hostgroup together with state and has_been_checked',
            'function': lambda item: [],  # REPAIRME
            'datatype': list,
        },
        'hostgroup_name': {
            'description': 'Name of the hostgroup',
            'function': lambda item: linked_attr(item, "hostgroup", "hostgroup_name"),
            'filters': {
                'attr': 'hostgroup.hostgroup_name',
            },
        },
        'hostgroup_notes': {
            'description': 'Optional notes to the hostgroup',
            'function': lambda item: linked_attr(item, "hostgroup", "notes"),
            'filters': {
                'attr': 'hostgroup.notes',
            },
        },
        'hostgroup_notes_url': {
            'description': 'An optional URL with further information about the hostgroup',
            'function': lambda item: linked_attr(item, "hostgroup", "notes_url"),
            'filters': {
                'attr': 'hostgroup.notes_url',
            },
        },
        'hostgroup_num_hosts': {
            'description': 'The total number of hosts in the group',
            'function': lambda item: len(item["hostgroup_hosts"]),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.host_name',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_hosts_down': {
            'description': 'The number of hosts in the group that are down',
            'function': lambda item: state_count(item, "hostgroup_hosts", 1, 1),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.state',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_hosts_pending': {
            'description': 'The number of hosts in the group that are pending',
            'function': lambda item: state_count(item, "hostgroup_hosts", state_id="PENDING"),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.state',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_hosts_unreach': {
            'description': 'The number of hosts in the group that are unreachable',
            'function': lambda item: state_count(item, "hostgroup_hosts", 1, 2),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.state',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_hosts_up': {
            'description': 'The number of hosts in the group that are up',
            'function': lambda item: state_count(item, "hostgroup_hosts", 1, 0),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.state',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services': {
            'description': 'The total number of services of hosts in this group',
            'function': lambda item: len(item["hostgroup_services"]),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.state',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_crit': {
            'description': 'The total number of services with the state CRIT of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 0, 2),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_hard_crit': {
            'description': 'The total number of services with the state CRIT of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 1, 2),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_hard_ok': {
            'description': 'The total number of services with the state OK of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 1, 0),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_hard_unknown': {
            'description': 'The total number of services with the state UNKNOWN of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 1, 3),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_hard_warn': {
            'description': 'The total number of services with the state WARN of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 1, 1),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_ok': {
            'description': 'The total number of services with the state OK of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 0, 0),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_pending': {
            'description': 'The total number of services with the state Pending of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", state_id="PENDING"),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_unknown': {
            'description': 'The total number of services with the state UNKNOWN of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 0, 3),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_num_services_warn': {
            'description': 'The total number of services with the state WARN of hosts in this group',
            'function': lambda item: state_count(item, "hostgroup_services", 0, 1),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_worst_host_state': {
            'description': 'The worst state of all of the groups\' hosts (UP <= UNREACHABLE <= DOWN)',
            'function': lambda item: state_worst(item, "hostgroup_hosts", 1),
            'datatype': int,
            'projection': [
                'hostgroup_hosts.state',
                'hostgroup_hosts.state_id',
                'hostgroup_hosts.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_worst_service_hard_state': {
            'description': 'The worst state of all services that belong to a host of this group (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: state_worst(item, "hostgroup_services", 1),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
        'hostgroup_worst_service_state': {
            'description': 'The worst state of all services that belong to a host of this group (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: state_worst(item, "hostgroup_services", 0),
            'datatype': int,
            'projection': [
                'hostgroup_services.state',
                'hostgroup_services.state_id',
                'hostgroup_services.state_type_id'
            ],
            'filters': {}
        },
    },
    'Config': {
        'accept_passive_host_checks': {
            'description': 'Whether passive host checks are accepted in general (0/1)',
            'datatype': bool,
        },
        'accept_passive_service_checks': {
            'description': 'Whether passive service checks are activated in general (0/1)',
            'datatype': bool,
        },
        'cached_log_messages': {
            'description': 'The current number of log messages MK Livestatus keeps in memory',
            'function': lambda item: 0,  # REPAIRME
            'datatype': int,
        },
        'cached_log_messages_rate': {
            'description': 'The current number of log messages MK Livestatus keeps in memory',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
        'check_external_commands': {
            'description': 'Whether Nagios checks for external commands at its command pipe (0/1)',
            'datatype': bool,
        },
        'check_host_freshness': {
            'description': 'Whether host freshness checking is activated in general (0/1)',
            'datatype': bool,
        },
        'check_service_freshness': {
            'description': 'Whether service freshness checking is activated in general (0/1)',
            'datatype': bool,
        },
        'connections': {
            'description': 'The number of client connections to Livestatus since program start',
            'function': lambda item: 0,  # REPAIRME
            'datatype': int,
        },
        'connections_rate': {
            'description': 'The averaged number of new client connections to Livestatus per second',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
        'enable_event_handlers': {
            'description': 'Whether event handlers are activated in general (0/1)',
            'datatype': bool,
        },
        'enable_flap_detection': {
            'description': 'Whether flap detection is activated in general (0/1)',
            'datatype': bool,
        },
        'enable_notifications': {
            'description': 'Whether notifications are enabled in general (0/1)',
            'datatype': bool,
        },
        'execute_host_checks': {
            'description': 'Whether host checks are executed in general (0/1)',
            'datatype': bool,
        },
        'execute_service_checks': {
            'description': 'Whether active service checks are activated in general (0/1)',
            'datatype': bool,
        },
        'external_command_buffer_max': {
            'description': 'The maximum number of slots used in the external command buffer',
            'datatype': int,
        },
        'external_command_buffer_slots': {
            'description': 'The size of the buffer for the external commands',
            'datatype': int,
        },
        'external_command_buffer_usage': {
            'description': 'The number of slots in use of the external command buffer',
            'datatype': int,
        },
        'external_commands_rate': {
            'description': 'The averaged number of external commands per second',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
        'forks': {
            'description': 'The number of process creations since program start',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
        'forks_rate': {
            'description': 'The averaged number of forks per second',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
        'host_checks': {
            'description': 'The number of host checks since program start',
            'function': lambda item: 0,  # REPAIRME
            'datatype': int,
        },
        'host_checks_rate': {
            'description': 'the averaged number of host checks per second',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
        'interval_length': {
            'description': 'The default interval length from nagios.cfg',
            'datatype': int,
        },
        'last_command_check': {
            'description': 'The time of the last check for a command as UNIX timestamp',
            'datatype': int,
        },
        'last_log_rotation': {
            'description': 'Time time of the last log file rotation',
            'datatype': int,
        },
        'livestatus_version': {
            'description': 'The version of the MK Livestatus module',
            'function': lambda item: '2.0-shinken',
        },
        'log_messages': {
            'description': 'The number of new log messages since program start',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
        'log_messages_rate': {
            'description': 'The averaged number of log messages per second',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
        'nagios_pid': {
            'description': 'The process ID of the Nagios main process',
            'datatype': int,
        },
        'neb_callbacks': {
            'description': 'The number of NEB call backs since program start',
            'function': lambda item: 0,  # REPAIRME
            'datatype': int,
        },
        'neb_callbacks_rate': {
            'description': 'The averaged number of NEB call backs per second',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
        'obsess_over_hosts': {
            'description': 'Whether Nagios will obsess over host checks (0/1)',
            'datatype': bool,
        },
        'obsess_over_services': {
            'description': 'Whether Nagios will obsess over service checks and run the ocsp_command (0/1)',
            'datatype': bool,
        },
        'process_performance_data': {
            'description': 'Whether processing of performance data is activated in general (0/1)',
            'datatype': bool,
        },
        'program_start': {
            'description': 'The time of the last program start as UNIX timestamp',
            'datatype': int,
        },
        'program_version': {
            'description': 'The version of the monitoring daemon',
            'function': lambda item: VERSION,
        },
        'requests': {
            'description': 'The number of requests to Livestatus since program start',
            'function': lambda item: 0,  # REPAIRME
            'datatype': int,
        },
        'requests_rate': {
            'description': 'The averaged number of request to Livestatus per second',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
        'service_checks': {
            'description': 'The number of completed service checks since program start',
            'function': lambda item: 0,  # REPAIRME
            'datatype': int,
        },
        'service_checks_rate': {
            'description': 'The averaged number of service checks per second',
            'function': lambda item: 0,  # REPAIRME
            'datatype': float,
        },
    },
    'Logline': {
        'attempt': {
            'description': 'The number of the check attempt',
            'datatype': int,
        },
        'class': {
            'description': 'The class of the message as integer (0:info, 1:state, 2:program, 3:notification, 4:passive, 5:command)',
            'datatype': int,
        },
        'command_name': {
            'description': 'The name of the command of the log entry (e.g. for notifications)',
        },
        'comment': {
            'description': 'A comment field used in various message types',
        },
        'contact_name': {
            'description': 'The name of the contact the log entry is about (might be empty)',
        },
        'current_command_line': {
            'description': 'The shell command line',
            'function': lambda item: "",  # REPAIRME
        },
        'current_command_name': {
            'description': 'The name of the command',
            'function': lambda item: "",  # REPAIRME
        },
        'current_contact_address1': {
            'description': 'The additional field address1',
        },
        'current_contact_address2': {
            'description': 'The additional field address2',
        },
        'current_contact_address3': {
            'description': 'The additional field address3',
        },
        'current_contact_address4': {
            'description': 'The additional field address4',
        },
        'current_contact_address5': {
            'description': 'The additional field address5',
        },
        'current_contact_address6': {
            'description': 'The additional field address6',
        },
        'current_contact_alias': {
            'description': 'The full name of the contact',
        },
        'current_contact_can_submit_commands': {
            'description': 'Whether the contact is allowed to submit commands (0/1)',
        },
        'current_contact_custom_variable_names': {
            'description': 'A list of all custom variables of the contact',
        },
        'current_contact_custom_variable_values': {
            'description': 'A list of the values of all custom variables of the contact',
        },
        'current_contact_custom_variables': {
            'description': 'A dictionary of the custom variables',
        },
        'current_contact_email': {
            'description': 'The email address of the contact',
        },
        'current_contact_host_notification_period': {
            'description': 'The time period in which the contact will be notified about host problems',
        },
        'current_contact_host_notifications_enabled': {
            'description': 'Whether the contact will be notified about host problems in general (0/1)',
        },
        'current_contact_in_host_notification_period': {
            'description': 'Whether the contact is currently in his/her host notification period (0/1)',
        },
        'current_contact_in_service_notification_period': {
            'description': 'Whether the contact is currently in his/her service notification period (0/1)',
        },
        'current_contact_modified_attributes': {
            'description': 'A bitmask specifying which attributes have been modified',
        },
        'current_contact_modified_attributes_list': {
            'description': 'A list of all modified attributes',
        },
        'current_contact_name': {
            'description': 'The login name of the contact person',
        },
        'current_contact_pager': {
            'description': 'The pager address of the contact',
        },
        'current_contact_service_notification_period': {
            'description': 'The time period in which the contact will be notified about service problems',
        },
        'current_contact_service_notifications_enabled': {
            'description': 'Whether the contact will be notified about service problems in general (0/1)',
        },
        'current_host_accept_passive_checks': {
            'description': 'Whether passive host checks are accepted (0/1)',
        },
        'current_host_acknowledged': {
            'description': 'Whether the current host problem has been acknowledged (0/1)',
        },
        'current_host_acknowledgement_type': {
            'description': 'Type of acknowledgement (0: none, 1: normal, 2: stick)',
        },
        'current_host_action_url': {
            'description': 'An optional URL to custom actions or information about this host',
        },
        'current_host_action_url_expanded': {
            'description': 'The same as action_url, but with the most important macros expanded',
        },
        'current_host_active_checks_enabled': {
            'description': 'Whether active checks are enabled for the host (0/1)',
        },
        'current_host_address': {
            'description': 'IP address',
        },
        'current_host_alias': {
            'description': 'An alias name for the host',
        },
        'current_host_check_command': {
            'description': 'Nagios command for active host check of this host',
        },
        'current_host_check_flapping_recovery_notification': {
            'description': 'Whether to check to send a recovery notification when flapping stops (0/1)',
        },
        'current_host_check_freshness': {
            'description': 'Whether freshness checks are activated (0/1)',
        },
        'current_host_check_interval': {
            'description': 'Number of basic interval lengths between two scheduled checks of the host',
        },
        'current_host_check_options': {
            'description': 'The current check option, forced, normal, freshness... (0-2)',
        },
        'current_host_check_period': {
            'description': 'Time period in which this host will be checked. If empty then the host will always be checked.',
        },
        'current_host_check_type': {
            'description': 'Type of check (0: active, 1: passive)',
        },
        'current_host_checks_enabled': {
            'description': 'Whether checks of the host are enabled (0/1)',
        },
        'current_host_childs': {
            'description': 'A list of all direct childs of the host',
        },
        'current_host_comments': {
            'description': 'A list of the ids of all comments of this host',
        },
        'current_host_comments_with_info': {
            'description': 'A list of all comments of the host with id, author and comment',
        },
        'current_host_contact_groups': {
            'description': 'A list of all contact groups this host is in',
        },
        'current_host_contacts': {
            'description': 'A list of all contacts of this host, either direct or via a contact group',
        },
        'current_host_current_attempt': {
            'description': 'Number of the current check attempts',
        },
        'current_host_current_notification_number': {
            'description': 'Number of the current notification',
        },
        'current_host_custom_variable_names': {
            'description': 'A list of the names of all custom variables',
        },
        'current_host_custom_variable_values': {
            'description': 'A list of the values of the custom variables',
        },
        'current_host_custom_variables': {
            'description': 'A dictionary of the custom variables',
        },
        'current_host_display_name': {
            'description': 'Optional display name of the host - not used by Nagios\' web interface',
        },
        'current_host_downtimes': {
            'description': 'A list of the ids of all scheduled downtimes of this host',
        },
        'current_host_downtimes_with_info': {
            'description': 'A list of the all scheduled downtimes of the host with id, author and comment',
        },
        'current_host_event_handler_enabled': {
            'description': 'Whether event handling is enabled (0/1)',
        },
        'current_host_execution_time': {
            'description': 'Time the host check needed for execution',
        },
        'current_host_filename': {
            'description': 'The value of the custom variable FILENAME',
        },
        'current_host_first_notification_delay': {
            'description': 'Delay before the first notification',
        },
        'current_host_flap_detection_enabled': {
            'description': 'Whether flap detection is enabled (0/1)',
        },
        'current_host_groups': {
            'description': 'A list of all host groups this host is in',
        },
        'current_host_hard_state': {
            'description': 'The effective hard state of the host (eliminates a problem in hard_state)',
        },
        'current_host_has_been_checked': {
            'description': 'Whether the host has already been checked (0/1)',
        },
        'current_host_high_flap_threshold': {
            'description': 'High threshold of flap detection',
        },
        'current_host_icon_image': {
            'description': 'The name of an image file to be used in the web pages',
        },
        'current_host_icon_image_alt': {
            'description': 'Alternative text for the icon_image',
        },
        'current_host_icon_image_expanded': {
            'description': 'The same as icon_image, but with the most important macros expanded',
        },
        'current_host_in_check_period': {
            'description': 'Whether this host is currently in its check period (0/1)',
        },
        'current_host_in_notification_period': {
            'description': 'Whether this host is currently in its notification period (0/1)',
        },
        'current_host_initial_state': {
            'description': 'Initial host state',
        },
        'current_host_is_executing': {
            'description': 'is there a host check currently running... (0/1)',
        },
        'current_host_is_flapping': {
            'description': 'Whether the host state is flapping (0/1)',
        },
        'current_host_last_check': {
            'description': 'Time of the last check (Unix timestamp)',
        },
        'current_host_last_hard_state': {
            'description': 'Last hard state',
        },
        'current_host_last_hard_state_change': {
            'description': 'Time of the last hard state change (Unix timestamp)',
        },
        'current_host_last_notification': {
            'description': 'Time of the last notification (Unix timestamp)',
        },
        'current_host_last_state': {
            'description': 'State before last state change',
        },
        'current_host_last_state_change': {
            'description': 'Time of the last state change - soft or hard (Unix timestamp)',
        },
        'current_host_last_time_down': {
            'description': 'The last time the host was DOWN (Unix timestamp)',
        },
        'current_host_last_time_unreachable': {
            'description': 'The last time the host was UNREACHABLE (Unix timestamp)',
        },
        'current_host_last_time_up': {
            'description': 'The last time the host was UP (Unix timestamp)',
        },
        'current_host_latency': {
            'description': 'Time difference between scheduled check time and actual check time',
        },
        'current_host_long_plugin_output': {
            'description': 'Complete output from check plugin',
        },
        'current_host_low_flap_threshold': {
            'description': 'Low threshold of flap detection',
        },
        'current_host_max_check_attempts': {
            'description': 'Max check attempts for active host checks',
        },
        'current_host_modified_attributes': {
            'description': 'A bitmask specifying which attributes have been modified',
        },
        'current_host_modified_attributes_list': {
            'description': 'A list of all modified attributes',
        },
        'current_host_name': {
            'description': 'Host name',
        },
        'current_host_next_check': {
            'description': 'Scheduled time for the next check (Unix timestamp)',
        },
        'current_host_next_notification': {
            'description': 'Time of the next notification (Unix timestamp)',
        },
        'current_host_no_more_notifications': {
            'description': 'Whether to stop sending notifications (0/1)',
        },
        'current_host_notes': {
            'description': 'Optional notes for this host',
        },
        'current_host_notes_expanded': {
            'description': 'The same as notes, but with the most important macros expanded',
        },
        'current_host_notes_url': {
            'description': 'An optional URL with further information about the host',
        },
        'current_host_notes_url_expanded': {
            'description': 'Same es notes_url, but with the most important macros expanded',
        },
        'current_host_notification_interval': {
            'description': 'Interval of periodic notification or 0 if its off',
        },
        'current_host_notification_period': {
            'description': 'Time period in which problems of this host will be notified. If empty then notification will be always',
        },
        'current_host_notifications_enabled': {
            'description': 'Whether notifications of the host are enabled (0/1)',
        },
        'current_host_num_services': {
            'description': 'The total number of services of the host',
        },
        'current_host_num_services_crit': {
            'description': 'The number of the host\'s services with the soft state CRIT',
        },
        'current_host_num_services_hard_crit': {
            'description': 'The number of the host\'s services with the hard state CRIT',
        },
        'current_host_num_services_hard_ok': {
            'description': 'The number of the host\'s services with the hard state OK',
        },
        'current_host_num_services_hard_unknown': {
            'description': 'The number of the host\'s services with the hard state UNKNOWN',
        },
        'current_host_num_services_hard_warn': {
            'description': 'The number of the host\'s services with the hard state WARN',
        },
        'current_host_num_services_ok': {
            'description': 'The number of the host\'s services with the soft state OK',
        },
        'current_host_num_services_pending': {
            'description': 'The number of the host\'s services which have not been checked yet (pending)',
        },
        'current_host_num_services_unknown': {
            'description': 'The number of the host\'s services with the soft state UNKNOWN',
        },
        'current_host_num_services_warn': {
            'description': 'The number of the host\'s services with the soft state WARN',
        },
        'current_host_obsess_over_host': {
            'description': 'The current obsess_over_host setting... (0/1)',
        },
        'current_host_parents': {
            'description': 'A list of all direct parents of the host',
        },
        'current_host_pending_flex_downtime': {
            'description': 'Whether a flex downtime is pending (0/1)',
        },
        'current_host_percent_state_change': {
            'description': 'Percent state change',
        },
        'current_host_perf_data': {
            'description': 'Optional performance data of the last host check',
        },
        'current_host_plugin_output': {
            'description': 'Output of the last host check',
        },
        'current_host_pnpgraph_present': {
            'description': 'Whether there is a PNP4Nagios graph present for this host (0/1)',
        },
        'current_host_process_performance_data': {
            'description': 'Whether processing of performance data is enabled (0/1)',
        },
        'current_host_retry_interval': {
            'description': 'Number of basic interval lengths between checks when retrying after a soft error',
        },
        'current_host_scheduled_downtime_depth': {
            'description': 'The number of downtimes this host is currently in',
        },
        'current_host_services_with_info': {
            'description': 'A list of all services including detailed information about each service',
        },
        'current_host_services': {
            'description': 'A list of all services of the host',
        },
        'current_host_services_with_state': {
            'description': 'A list of all services of the host together with state and has_been_checked',
        },
        'current_host_state': {
            'description': 'The current state of the host (0: up, 1: down, 2: unreachable)',
        },
        'current_host_state_type': {
            'description': 'Type of the current state (0: soft, 1: hard)',
        },
        'current_host_statusmap_image': {
            'description': 'The name of in image file for the status map',
        },
        'current_host_total_services': {
            'description': 'The total number of services of the host',
        },
        'current_host_worst_service_hard_state': {
            'description': 'The worst hard state of all of the host\'s services (OK <= WARN <= UNKNOWN <= CRIT)',
        },
        'current_host_worst_service_state': {
            'description': 'The worst soft state of all of the host\'s services (OK <= WARN <= UNKNOWN <= CRIT)',
        },
        'current_host_x_3d': {
            'description': '3D-Coordinates: X',
        },
        'current_host_y_3d': {
            'description': '3D-Coordinates: Y',
        },
        'current_host_z_3d': {
            'description': '3D-Coordinates: Z',
        },
        'current_service_accept_passive_checks': {
            'description': 'Whether the service accepts passive checks (0/1)',
        },
        'current_service_acknowledged': {
            'description': 'Whether the current service problem has been acknowledged (0/1)',
        },
        'current_service_acknowledgement_type': {
            'description': 'The type of the acknownledgement (0: none, 1: normal, 2: sticky)',
        },
        'current_service_action_url': {
            'description': 'An optional URL for actions or custom information about the service',
        },
        'current_service_action_url_expanded': {
            'description': 'The action_url with (the most important) macros expanded',
        },
        'current_service_active_checks_enabled': {
            'description': 'Whether active checks are enabled for the service (0/1)',
        },
        'current_service_check_command': {
            'description': 'Nagios command used for active checks',
        },
        'current_service_check_interval': {
            'description': 'Number of basic interval lengths between two scheduled checks of the service',
        },
        'current_service_check_options': {
            'description': 'The current check option, forced, normal, freshness... (0/1)',
        },
        'current_service_check_period': {
            'description': 'The name of the check period of the service. It this is empty, the service is always checked.',
        },
        'current_service_check_type': {
            'description': 'The type of the last check (0: active, 1: passive)',
        },
        'current_service_checks_enabled': {
            'description': 'Whether active checks are enabled for the service (0/1)',
        },
        'current_service_comments': {
            'description': 'A list of all comment ids of the service',
        },
        'current_service_comments_with_info': {
            'description': 'A list of all comments of the service with id, author and comment',
        },
        'current_service_contact_groups': {
            'description': 'A list of all contact groups this service is in',
        },
        'current_service_contacts': {
            'description': 'A list of all contacts of the service, either direct or via a contact group',
        },
        'current_service_current_attempt': {
            'description': 'The number of the current check attempt',
        },
        'current_service_current_notification_number': {
            'description': 'The number of the current notification',
        },
        'current_service_custom_variable_names': {
            'description': 'A list of the names of all custom variables of the service',
        },
        'current_service_custom_variables': {
            'description': 'A dictionary of the custom variables',
        },
        'current_service_custom_variable_values': {
            'description': 'A list of the values of all custom variable of the service',
        },
        'current_service_description': {
            'description': 'Description of the service (also used as key)',
        },
        'current_service_display_name': {
            'description': 'An optional display name (not used by Nagios standard web pages)',
        },
        'current_service_downtimes': {
            'description': 'A list of all downtime ids of the service',
        },
        'current_service_downtimes_with_info': {
            'description': 'A list of all downtimes of the service with id, author and comment',
        },
        'current_service_event_handler': {
            'description': 'Nagios command used as event handler',
        },
        'current_service_event_handler_enabled': {
            'description': 'Whether and event handler is activated for the service (0/1)',
        },
        'current_service_execution_time': {
            'description': 'Time the host check needed for execution',
        },
        'current_service_first_notification_delay': {
            'description': 'Delay before the first notification',
        },
        'current_service_flap_detection_enabled': {
            'description': 'Whether flap detection is enabled for the service (0/1)',
        },
        'current_service_groups': {
            'description': 'A list of all service groups the service is in',
        },
        'current_service_has_been_checked': {
            'description': 'Whether the service already has been checked (0/1)',
        },
        'current_service_high_flap_threshold': {
            'description': 'High threshold of flap detection',
        },
        'current_service_icon_image': {
            'description': 'The name of an image to be used as icon in the web interface',
        },
        'current_service_icon_image_alt': {
            'description': 'An alternative text for the icon_image for browsers not displaying icons',
        },
        'current_service_icon_image_expanded': {
            'description': 'The icon_image with (the most important) macros expanded',
        },
        'current_service_in_check_period': {
            'description': 'Whether the service is currently in its check period (0/1)',
        },
        'current_service_in_notification_period': {
            'description': 'Whether the service is currently in its notification period (0/1)',
        },
        'current_service_initial_state': {
            'description': 'The initial state of the service',
        },
        'current_service_is_executing': {
            'description': 'is there a service check currently running... (0/1)',
        },
        'current_service_is_flapping': {
            'description': 'Whether the service is flapping (0/1)',
        },
        'current_service_last_check': {
            'description': 'The time of the last check (Unix timestamp)',
        },
        'current_service_last_hard_state': {
            'description': 'The last hard state of the service',
        },
        'current_service_last_hard_state_change': {
            'description': 'The time of the last hard state change (Unix timestamp)',
        },
        'current_service_last_notification': {
            'description': 'The time of the last notification (Unix timestamp)',
        },
        'current_service_last_state': {
            'description': 'The last state of the service',
        },
        'current_service_last_state_change': {
            'description': 'The time of the last state change (Unix timestamp)',
        },
        'current_service_last_time_critical': {
            'description': 'The last time the service was CRITICAL (Unix timestamp)',
        },
        'current_service_last_time_ok': {
            'description': 'The last time the service was OK (Unix timestamp)',
        },
        'current_service_last_time_unknown': {
            'description': 'The last time the service was UNKNOWN (Unix timestamp)',
        },
        'current_service_last_time_warning': {
            'description': 'The last time the service was in WARNING state (Unix timestamp)',
        },
        'current_service_latency': {
            'description': 'Time difference between scheduled check time and actual check time',
        },
        'current_service_long_plugin_output': {
            'description': 'Unabbreviated output of the last check plugin',
        },
        'current_service_low_flap_threshold': {
            'description': 'Low threshold of flap detection',
        },
        'current_service_max_check_attempts': {
            'description': 'The maximum number of check attempts',
        },
        'current_service_modified_attributes': {
            'description': 'A bitmask specifying which attributes have been modified',
        },
        'current_service_modified_attributes_list': {
            'description': 'A list of all modified attributes',
        },
        'current_service_next_check': {
            'description': 'The scheduled time of the next check (Unix timestamp)',
        },
        'current_service_next_notification': {
            'description': 'The time of the next notification (Unix timestamp)',
        },
        'current_service_no_more_notifications': {
            'description': 'Whether to stop sending notifications (0/1)',
        },
        'current_service_notes': {
            'description': 'Optional notes about the service',
        },
        'current_service_notes_expanded': {
            'description': 'The notes with (the most important) macros expanded',
        },
        'current_service_notes_url': {
            'description': 'An optional URL for additional notes about the service',
        },
        'current_service_notes_url_expanded': {
            'description': 'The notes_url with (the most important) macros expanded',
        },
        'current_service_notification_interval': {
            'description': 'Interval of periodic notification or 0 if its off',
        },
        'current_service_notification_period': {
            'description': 'The name of the notification period of the service. It this is empty, service problems are always notified.',
        },
        'current_service_notifications_enabled': {
            'description': 'Whether notifications are enabled for the service (0/1)',
        },
        'current_service_obsess_over_service': {
            'description': 'Whether \'obsess_over_service\' is enabled for the service (0/1)',
        },
        'current_service_percent_state_change': {
            'description': 'Percent state change',
        },
        'current_service_perf_data': {
            'description': 'Performance data of the last check plugin',
        },
        'current_service_plugin_output': {
            'description': 'Output of the last check plugin',
        },
        'current_service_pnpgraph_present': {
            'description': 'Whether there is a PNP4Nagios graph present for this service (0/1)',
        },
        'current_service_process_performance_data': {
            'description': 'Whether processing of performance data is enabled for the service (0/1)',
        },
        'current_service_retry_interval': {
            'description': 'Number of basic interval lengths between checks when retrying after a soft error',
        },
        'current_service_scheduled_downtime_depth': {
            'description': 'The number of scheduled downtimes the service is currently in',
        },
        'current_service_state': {
            'description': 'The current state of the service (0: OK, 1: WARN, 2: CRITICAL, 3: UNKNOWN)',
        },
        'current_service_state_type': {
            'description': 'The type of the current state (0: soft, 1: hard)',
        },
        'host_name': {
            'description': 'The name of the host the log entry is about (might be empty)',
        },
        'lineno': {
            'description': 'The number of the line in the log file',
            'datatype': int,
        },
        'message': {
            'description': 'The complete message line including the timestamp',
        },
        'options': {
            'description': 'The part of the message after the \':\'',
            # >2.4 'function': lambda item: item.message.partition(":")[2].lstrip(),
        },
        'plugin_output': {
            'description': 'The output of the check, if any is associated with the message',
        },
        'service_description': {
            'description': 'The description of the service log entry is about (might be empty)',
        },
        'state': {
            'description': 'The state of the host or service in question',
            'datatype': int,
        },
        'state_type': {
            'description': 'The type of the state (varies on different log classes)',
        },
        'time': {
            'description': 'Time of the log event (UNIX timestamp)',
            'datatype': int,
        },
        'type': {
            'description': 'The type of the message (text before the colon), the message itself for info messages',
        },
    },
}

# Updates Service, Downtime and Comment classe definitions with HostLink
# and ServiceLink attributes
for class_map in ("Comment", "Downtime", "Service"):
    livestatus_attribute_map[class_map].update(
        livestatus_attribute_map["HostLink"]
    )
for class_map in ("Comment", "Downtime"):
    livestatus_attribute_map[class_map].update(
        livestatus_attribute_map["ServiceLink"]
    )
for class_map in ('Host', 'Hostgroup', 'Servicegroup'):
    livestatus_attribute_map[class_map].update(
        livestatus_attribute_map["ServicesLink"]
    )
for class_map in ('Hostgroup', 'Servicegroup'):
    livestatus_attribute_map[class_map].update(
        livestatus_attribute_map["HostsLink"]
    )
for class_map in ("Hostsbygroup",):
    livestatus_attribute_map[class_map].update(
        livestatus_attribute_map["Host"]
    )
for class_map in ("Servicesbygroup", "Servicesbyhostgroup"):
    # The group parameter semantic can be different is some tables
    # We keep the more specialized version
    livestatus_attribute_map[class_map].update(
        livestatus_attribute_map["Service"]
    )

table_class_map = {
    'hosts': livestatus_attribute_map['Host'],
    'services': livestatus_attribute_map['Service'],
    'hostgroups': livestatus_attribute_map['Hostgroup'],
    'servicegroups': livestatus_attribute_map['Servicegroup'],
    'contacts': livestatus_attribute_map['Contact'],
    'contactgroups': livestatus_attribute_map['Contactgroup'],
    'comments': livestatus_attribute_map['Comment'],
    'downtimes': livestatus_attribute_map['Downtime'],
    'commands': livestatus_attribute_map['Command'],
    'timeperiods': livestatus_attribute_map['Timeperiod'],
    'hostsbygroup': livestatus_attribute_map['Hostsbygroup'],
    'servicesbygroup': livestatus_attribute_map['Servicesbygroup'],
    'servicesbyhostgroup': livestatus_attribute_map['Servicesbyhostgroup'],
    'status': livestatus_attribute_map['Config'],
    'log': livestatus_attribute_map['Logline'],
    'schedulers': livestatus_attribute_map['SchedulerLink'],
    'pollers': livestatus_attribute_map['PollerLink'],
    'reactionners': livestatus_attribute_map['ReactionnerLink'],
    'brokers': livestatus_attribute_map['BrokerLink'],
    'problems': livestatus_attribute_map['Problem'],
    'columns': livestatus_attribute_map['Config'],
}
