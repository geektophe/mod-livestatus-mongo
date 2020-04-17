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


def worst_host_state(state_1, state_2):
    """Return the worst of two host states."""
    #lambda x: reduce(lambda g, c: c if g == 0 else (c if c == 1 else g), (y.state_id for y in x), 0),
    if state_2 == 0:
        return state_1
    if state_1 == 1:
        return state_1
    return state_2


def worst_service_state(state_1, state_2):
    """Return the worst of two service states."""
    #reduce(lambda g, c: c if g == 0 else (c if c == 2 else (c if (c == 3 and g != 2) else g)), (z.state_id for y in x for z in y.services if z.state_type_id == 1), 0),
    if state_2 == 0:
        return state_1
    if state_1 == 2:
        return state_1
    if state_1 == 3 and state_2 != 2:
        return state_1
    return state_2


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


def from_svc_hst_distinct_lists(dct):
    """Transform a dict with keys hosts and services to a list."""
    t = []
    for item in dct:
        try:
            t.append(item.get_full_name()),
        except Exception:
            t.append(item.get_name()),
    return t


def get_livestatus_full_name(item, req):
    """Returns a host's or a service's name in livestatus notation.

    This function takes either a host or service object as it's first argument.
    The third argument is a livestatus request object. The important information
    in the request object is the separators array. It contains the character
    that separates host_name and service_description which is used for services'
    names with the csv output format. If the output format is json, services' names
    are lists composed of host_name and service_description.
    """
    cls_name = item.__class__.my_type
    if req.response.outputformat == 'csv':
        if cls_name == 'service':
            return item.host_name + req.response.separators.pipe + item.service_description
        else:
            return item.host_name
    elif req.response.outputformat == 'json' or req.response.outputformat == 'python':
        if cls_name == 'service':
            return [item.host_name, item.service_description]
        else:
            return item.host_name
        pass


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


def linked_host_attr(item, attr, default=""):
    """
    Returnrs the linked host attribute value, or default if it does not exist

    :param dict item: The item to read attribute from
    :param str attr: The attribute name to read
    :param mixed defaut: The default value
    """
    if item.get("hosts"):
        return item["hosts"][0].get(attr, default)
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
            'function': lambda item: item["passive_checks_enabled"],
            'datatype': bool,
            'filters': {
                'attr': 'passive_checks_enabled',
            },
        },
        'acknowledged': {
            'description': 'Whether the current host problem has been acknowledged (0/1)',
            'function': lambda item: item.get("problem_has_been_acknowledged", False),
            'datatype': bool,
            'filters': {
                'attr': 'problem_has_been_acknowledged',
            },
        },
        'acknowledgement_type': {
            'description': 'Type of acknowledgement (0: none, 1: normal, 2: stick)',
            'function': lambda item: item.get("acknowledgement_type", 0),
            'datatype': int,
        },
        'action_url': {
            'description': 'An optional URL to custom actions or information about this host',
            'function': lambda item: item["action_url"],
        },
        'action_url_expanded': {
            'description': 'The same as action_url, but with the most important macros expanded',
            'function': lambda item: "", #FIXME
            'projections': [],
            'filters': {},
        },
        'active_checks_enabled': {
            'description': 'Whether active checks are enabled for the host (0/1)',
            'function': lambda item: item["active_checks_enabled"],
            'datatype': bool,
        },
        'address': {
            'description': 'IP address',
            'function': lambda item: item["address"],
        },
        'alias': {
            'description': 'An alias name for the host',
            'function': lambda item: item["alias"],
        },
        'business_impact': {
            'description': 'The importance we gave to this host between the minimum 0 and the maximum 5',
            'function': lambda item: item["business_impact"],
            'datatype': int,
        },
        'check_command': {
            'description': 'Nagios command for active host check of this host',
            'function': lambda item: item["check_command"],
        },
        'check_flapping_recovery_notification': {
            'description': 'Whether to check to send a recovery notification when flapping stops (0/1)',
            'function': lambda item: item["check_flapping_recovery_notification"],  # REPAIRME WTF
            'datatype': int,
        },
        'check_freshness': {
            'description': 'Whether freshness checks are activated (0/1)',
            'function': lambda item: item["check_freshness"],
            'datatype': bool,
        },
        'check_interval': {
            'description': 'Number of basic interval lengths between two scheduled checks of the host',
            'function': lambda item: item["check_interval"],
            'datatype': float,
        },
        'check_options': {
            'description': 'The current check option, forced, normal, freshness... (0-2)',
            'function': lambda item: 0,  #FIXME
            'datatype': int,
        },
        'check_period': {
            'description': 'Time period in which this host will be checked. If empty then the host will always be checked.',
            'function': lambda item: item["check_period"],
        },
        'check_type': {
            'description': 'Type of check (0: active, 1: passive)',
            'function': lambda item: item["check_type"],
            'datatype': int,
        },
        'checks_enabled': {
            'description': 'Whether checks of the host are enabled (0/1)',
            'function': lambda item: item["active_checks_enabled"],
            'datatype': bool,
            'filters': {
                'attr': 'active_checks_enabled',
            },
        },
        'child_dependencies': {
            'description': 'List of the host/service that depend on this host (logical, network or business one).',
            'function': lambda item: item.get("child_dependencies", []),
            'datatype': list,
        },
        'childs': {
            'description': 'A list of all direct childs of the host',
            'function': lambda item: item.get("childs", []),
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
            'function': lambda item: item["contacts"],
            'datatype': list,
        },
        'contact_groups': {
            'description': 'A list of all contact groups this host is in',
            'function': lambda item: item["contact_groups"],
            'datatype': list,
        },
        'criticity': {
            'description': 'The importance we gave to this host between the minimum 0 and the maximum 5',
            'function': lambda item: item["business_impact"],
            'datatype': int,
            'filters': {
                'attr': 'business_impact',
            },
        },
        'current_attempt': {
            'description': 'Number of the current check attempts',
            'function': lambda item: item["attempt"],
            'datatype': int,
            'filters': {
                'attr': 'attempt',
            },
        },
        'current_notification_number': {
            'description': 'Number of the current notification',
            'function': lambda item: item.get("current_notification_number", 0),
            'datatype': int,
        },
        'custom_variable_names': {
            'description': 'A list of the names of all custom variables',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {}
        },
        'custom_variable_values': {
            'description': 'A list of the values of the custom variables',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {}
        },
        'custom_variables': {
            'description': 'A dictionary of the custom variables',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {}
        },
        'display_name': {
            'description': 'Optional display name of the host - not used by Nagios\' web interface',
            'function': lambda item: item["display_name"],
        },
        'downtimes': {
            'description': 'A list of the ids of all scheduled downtimes of this host',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'downtimes_with_info': {
            'description': 'A list of the all scheduled downtimes of the host with id, author and comment',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'event_handler': {
            'description': 'Nagios command used as event handler',
            'function': lambda item: item["event_handler"],
        },
        'event_handler_enabled': {
            'description': 'Whether event handling is enabled (0/1)',
            'function': lambda item: item["event_handler_enabled"],
            'datatype': bool,
        },
        'execution_time': {
            'description': 'Time the host check needed for execution',
            'function': lambda item: item.get("execution_time", 0),
            'datatype': float,
        },
        'filename': {
            'description': 'The value of the custom variable FILENAME',
            'function': lambda item: '', #FIXME
            'projections': [],
            'filters': {},
        },
        'first_notification_delay': {
            'description': 'Delay before the first notification',
            'function': lambda item: item["first_notification_delay"],
            'datatype': float,
        },
        'flap_detection_enabled': {
            'description': 'Whether flap detection is enabled (0/1)',
            'function': lambda item: item["flap_detection_enabled"],
            'datatype': bool,
        },
        'got_business_rule': {
            'description': 'Whether the host state is an business rule based host or not (0/1)',
            'function': lambda item: item["got_business_rule"],
            'datatype': bool,
        },
        'groups': {
            'description': 'A list of all host groups this host is in',
            'function': lambda item: item["hostgroups"],
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
            'function': lambda item: item.get("has_been_checked", 0),
            'datatype': int,
        },
        'high_flap_threshold': {
            'description': 'High threshold of flap detection',
            'function': lambda item: item["high_flap_threshold"],
            'datatype': float,
        },
        'host_name': {
            'description': 'Host name',
            'function': lambda item: item["host_name"],
        },
        'icon_image': {
            'description': 'The name of an image file to be used in the web pages',
            'function': lambda item: item["icon_image"],
        },
        'icon_image_alt': {
            'description': 'Alternative text for the icon_image',
            'function': lambda item: item["icon_image_alt"],
        },
        'icon_image_expanded': {
            'description': 'The same as icon_image, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projections': [],
            'filters': {},
        },
        'impacts': {
            'description': 'List of what the source impact (list of hosts and services)',
            'function': lambda item: item.get("impacts", []),  # REPAIRME MAYBE (separators in python and csv),
            'datatype': list,
            'filters': {},
        },
        'in_check_period': {
            'description': 'Whether this host is currently in its check period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projections': [],
            'filters': {},
        },
        'in_notification_period': {
            'description': 'Whether this host is currently in its notification period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projections': [],
            'filters': {},
        },
        'initial_state': {
            'description': 'Initial host state',
            'function': lambda item: item["initial_state"],
        },
        'is_executing': {
            'description': 'is there a host check currently running... (0/1)',
            'function': lambda item: False,  #FIXME value in scheduler is not real-time
            'datatype': bool,
            'projections': [],
            'filters': {},
        },
        'is_flapping': {
            'description': 'Whether the host state is flapping (0/1)',
            'function': lambda item: item.get("is_flapping", False),
            'datatype': bool,
        },
        'is_impact': {
            'description': 'Whether the host state is an impact or not (0/1)',
            'function': lambda item: item.get("is_impact", False),
            'datatype': bool,
        },
        'is_problem': {
            'description': 'Whether the host state is a problem or not (0/1)',
            'function': lambda item: item.get("is_problem", False),
            'datatype': bool,
        },
        'labels': {
            'description': 'Arbitrary labels (separated by comma character)',
            'function': lambda item: item["labels"],
            'datatype': list,
        },
        'last_check': {
            'description': 'Time of the last check (Unix timestamp)',
            'function': lambda item: item.get("last_chk", 0),
            'datatype': int,
            'filters': {
                'attr': 'last_chk',
            },
        },
        'last_hard_state': {
            'description': 'Last hard state',
            'function': lambda item: item.get("last_hard_state_id", 0),
            'datatype': int,
            'filters': {
                'attr': 'last_hard_state_id',
            },

        },
        'last_hard_state_change': {
            'description': 'Time of the last hard state change (Unix timestamp)',
            'function': lambda item: item.get("last_hard_state_change", 0),
            'datatype': int,
        },
        'last_notification': {
            'description': 'Time of the last notification (Unix timestamp)',
            'function': lambda item: item.get("last_notification", 0),
            'datatype': int,
        },
        'last_state': {
            'description': 'State before last state change',
            'function': lambda item: item.get("last_state", ""),
        },
        'last_state_change': {
            'description': 'Time of the last state change - soft or hard (Unix timestamp)',
            'function': lambda item: item.get("last_state_change", 0),
            'datatype': int,
        },
        'last_time_down': {
            'description': 'The last time the host was DOWN (Unix timestamp)',
            'function': lambda item: item.get("last_time_down", 0),  # REPAIRME
            'datatype': int,
        },
        'last_time_unreachable': {
            'description': 'The last time the host was UNREACHABLE (Unix timestamp)',
            'function': lambda item: item.get("last_time_unreachable", 0),  # REPAIRME
            'datatype': int,
        },
        'last_time_up': {
            'description': 'The last time the host was UP (Unix timestamp)',
            'function': lambda item: item.get("last_time_up", 0),  # REPAIRME
            'datatype': int,
        },
        'latency': {
            'description': 'Time difference between scheduled check time and actual check time',
            'function': lambda item: item.get("latency", 0),
            'datatype': float,
        },
        'long_plugin_output': {
            'description': 'Complete output from check plugin',
            'function': lambda item: item.get("long_output", ""),
            'filters': {
                'attr': 'long_output',
            },
        },
        'low_flap_threshold': {
            'description': 'Low threshold of flap detection',
            'function': lambda item: item.get("low_flap_threshold", 0),
            'datatype': float,
        },
        'max_check_attempts': {
            'description': 'Max check attempts for active host checks',
            'function': lambda item: item.get("max_check_attempts", 0),
            'datatype': int,
        },
        'modified_attributes': {
            'description': 'A bitmask specifying which attributes have been modified',
            'function': lambda item: item.get("modified_attributes", 0),  # CONTROLME
            'datatype': int,
        },
        'modified_attributes_list': {
            'description': 'A list of all modified attributes',
            'function': lambda item: [],  #FIXME
            'datatype': list,
        },
        'name': {
            'description': 'Host name',
            'function': lambda item: item["host_name"],
            'filters': {
                'attr': 'host_name',
            },
        },
        'next_check': {
            'description': 'Scheduled time for the next check (Unix timestamp)',
            'function': lambda item: item.get("next_chk", 0),
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
            'function': lambda item: item["notes"],
        },
        'notes_expanded': {
            'description': 'The same as notes, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projections': [],
            'filters': {},
        },
        'notes_url': {
            'description': 'An optional URL with further information about the host',
            'function': lambda item: item["notes_url"],
        },
        'notes_url_expanded': {
            'description': 'Same es notes_url, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projections': [],
            'filters': {},
        },
        'notification_interval': {
            'description': 'Interval of periodic notification or 0 if its off',
            'function': lambda item: item["notification_interval"],
            'datatype': float,
        },
        'notification_options': {
            'description': 'The options controlling when notification should be sent',
            'function': lambda item: item["notification_options"],
            'datatype': list,
        },
        'notification_period': {
            'description': 'Time period in which problems of this host will be notified. If empty then notification will be always',
            'function': lambda item: item["notification_period"],
        },
        'notifications_enabled': {
            'description': 'Whether notifications of the host are enabled (0/1)',
            'function': lambda item: item["notifications_enabled"],
            'datatype': bool,
        },
        'no_more_notifications': {
            'description': 'Whether to stop sending notifications (0/1)',
            'function': lambda item: item.get("no_more_notifications", False),  # REPAIRME, maybe ask both instance and class
            'datatype': bool,
        },
        'obsess_over_host': {
            'description': 'The current obsess_over_host setting... (0/1)',
            'function': lambda item: item["obsess_over_host"],
            'datatype': bool,
        },
        'parent_dependencies': {
            'description': 'List of the dependencies (logical, network or business one) of this host.',
            'function': lambda item: item.get("parent_dependencies", []),
            'datatype': list,
            'filters': {},
        },
        'parents': {
            'description': 'A list of all direct parents of the host',
            'function': lambda item: item.get("parents", []),
            'datatype': list,
            'filters': {},
        },
        'pending_flex_downtime': {
            'description': 'Whether a flex downtime is pending (0/1)',
            'function': lambda item: item.get("pending_flex_downtime", 0),
            'datatype': int,
        },
        'percent_state_change': {
            'description': 'Percent state change',
            'function': lambda item: item.get("percent_state_change", 0),
            'datatype': float,
        },
        'perf_data': {
            'description': 'Optional performance data of the last host check',
            'function': lambda item: item.get("perf_data", ""),
        },
        'plugin_output': {
            'description': 'Output of the last host check',
            'function': lambda item: item.get("output", ""),
            'filters': {
                'attr': 'output',
            },
        },
        'pnpgraph_present': {
            'description': 'Whether there is a PNP4Nagios graph present for this host (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projections': [],
            'filters': {},
        },
        'process_performance_data': {
            'description': 'Whether processing of performance data is enabled (0/1)',
            'function': lambda item: item["process_perf_data"],
            'datatype': bool,
            'filters': {
                'attr': 'process_perf_data',
            },
        },
        'realm': {
            'description': 'Realm',
            'function': lambda item: item["realm"],
        },
        'retry_interval': {
            'description': 'Number of basic interval lengths between checks when retrying after a soft error',
            'function': lambda item: item["retry_interval"],
            'datatype': float,
        },
        'scheduled_downtime_depth': {
            'description': 'The number of downtimes this host is currently in',
            'function': lambda item: item.get("scheduled_downtime_depth", 0),
            'datatype': int,
        },
        'services': {
            'description': 'A list of all services of the host',
            'function': lambda item: item.get("services", []),
            'datatype': list,
            'projections': ['services.service_description'],
            'filters': {},
        },
        'services_with_info': {
            'description': 'A list of all services including detailed information about each service',
            'function': lambda item: [],  #FIXME
            'datatype': list,
            'projections': [
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
            'projections': [
                'services.service_description',
                'services.state_id',
                'services.state_type_id'
            ],
            'filters': {},
        },
        'source_problems': {
            'description': 'The name of the source problems (host or service)',
            'function': lambda item: item.get("source_problems", []),  # REPAIRME MAYBE (separators in python and csv),
            'datatype': list,
        },
        'state': {
            'description': 'The current state of the host (0: up, 1: down, 2: unreachable)',
            'function': lambda item: item.get("state_id", 0),
            'datatype': int,
            'filters': {
                'attr': 'state_id',
            },
        },
        'state_type': {
            'description': 'Type of the current state (0: soft, 1: hard)',
            'function': lambda item: item.get("state_type_id", 0),
            'datatype': int,
            'filters': {
                'attr': 'state_type_id',
            },
        },
        'statusmap_image': {
            'description': 'The name of in image file for the status map',
            'function': lambda item: item["statusmap_image"],
        },
        'tags': {
            'description': 'The list of Host Tags',
            'function': lambda item: item["tags"],
            'datatype': list,
        },
        'total_services': {
            'description': 'The total number of services of the host',
            'function': lambda item: len(item.get("services", [])),
            'datatype': int,
            'projections': ['services.service_description'],
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
            'function': lambda item: linked_host_attr(item, "passive_checks_enabled", True),
            'datatype': bool,
            'filters': {
                'attr': 'hosts.passive_checks_enabled',
            },
        },
        'host_acknowledged': {
            'description': 'Whether the current host problem has been acknowledged (0/1)',
            'function': lambda item: linked_host_attr(item, "problem_has_been_acknowledged", False),
            'datatype': bool,
            'filters': {
                'attr': 'hosts.problem_has_been_acknowledged',
            },
        },
        'host_acknowledgement_type': {
            'description': 'Type of acknowledgement (0: none, 1: normal, 2: stick)',
            'function': lambda item: linked_host_attr(item, "acknowledgement_type", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.acknowledgement_type',
            },
        },
        'host_action_url': {
            'description': 'An optional URL to custom actions or information about this host',
            'function': lambda item: linked_host_attr(item, "action_url", ""),
            'filters': {
                'attr': 'hosts.action_url',
            },
        },
        'host_action_url_expanded': {
            'description': 'The same as action_url, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projections': [],
            'filters': {},
        },
        'host_active_checks_enabled': {
            'description': 'Whether active checks are enabled for the host (0/1)',
            'function': lambda item: linked_host_attr(item, "active_checks_enabled", True),
            'datatype': bool,
            'filters': {
                'attr': 'hosts.active_checks_enabled',
            },
        },
        'host_address': {
            'description': 'IP address',
            'function': lambda item: linked_host_attr(item, "address"),
            'filters': {
                'attr': 'hosts.address',
            },
        },
        'host_alias': {
            'description': 'An alias name for the host',
            'function': lambda item: linked_host_attr(item, "alias"),
            'filters': {
                'attr': 'hosts.alias',
            },
        },
        'host_check_command': {
            'description': 'Nagios command used for active checks',
            'function': lambda item: linked_host_attr(item, "check_command"),
            'filters': {
                'attr': 'hosts.check_command',
            },
        },
        'host_check_flapping_recovery_notification': {
            'description': 'Whether to check to send a recovery notification when flapping stops (0/1)',
            'function': lambda item: item["host"]["check_flapping_recovery_notification"],
            'datatype': int,
            'filters': {
                'attr': 'hosts.check_flapping_recovery_notification',
            },
        },
        'host_check_freshness': {
            'description': 'Whether freshness checks are activated (0/1)',
            'function': lambda item: linked_host_attr(item, "check_freshness", False),
            'datatype': bool,
            'filters': {
                'attr': 'hosts.check_freshness',
            },
        },
        'host_check_interval': {
            'description': 'Number of basic interval lengths between two scheduled checks of the host',
            'function': lambda item: linked_host_attr(item, "check_interval", 0),
            'datatype': float,
            'filters': {
                'attr': 'hosts.check_interval',
            },
        },
        'host_check_options': {
            'description': 'The current check option, forced, normal, freshness... (0-2)',
            'function': lambda item: linked_host_attr(item, "check_options"),
            'filters': {
                'attr': 'hosts.check_options',
            },
        },
        'host_check_period': {
            'description': 'Time period in which this host will be checked. If empty then the host will always be checked.',
            'function': lambda item: linked_host_attr(item, "check_period"),
            'filters': {
                'attr': 'hosts.period',
            },
        },
        'host_check_type': {
            'description': 'Type of check (0: active, 1: passive)',
            'function': lambda item: 0,  # REPAIRME
            'datatype': int,
            'projections': [],
            'filters': {},
        },
        'host_checks_enabled': {
            'description': 'Whether active checks of the host are enabled (0/1)',
            'function': lambda item: linked_host_attr(item, "active_checks_enabled", True),
            'datatype': bool,
            'filters': {
                'attr': 'hosts.active_checks_enabled',
            },
        },
        'host_childs': {
            'description': 'A list of all direct childs of the host',
            'function': lambda item: linked_host_attr(item, "childs", []),
            'datatype': list,
            'projections': ['hosts.childs'],
            'filters': {},
        },
        'host_comments': {
            'description': 'A list of the ids of all comments of this host',
            'function': lambda item: linked_host_attr(item, "comments", []),
            'datatype': list,
            'filters': {
                'attr': 'hosts.comments',
            },
        },
        'host_comments_with_info': {
            'description': 'A list of all comments of the host with id, author and comment',
            'function': lambda item: [],  #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'host_contacts': {
            'description': 'A list of all contacts of this host, either direct or via a contact group',
            'function': lambda item: linked_host_attr(item, "contacts", []),
            'datatype': list,
            'filters': {
                'attr': 'hosts.contacts',
            },
        },
        'host_contact_groups': {
            'description': 'A list of all contact groups this host is in',
            'function': lambda item: linked_host_attr(item, "contact_groups", []),
            'datatype': list,
            'filters': {
                'attr': 'hosts.contact_groups',
            },
        },
        'host_current_attempt': {
            'description': 'Number of the current check attempts',
            'function': lambda item: linked_host_attr(item, "attempt", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.attempt',
            },
        },
        'host_current_notification_number': {
            'description': 'Number of the current notification',
            'function': lambda item: linked_host_attr(item, "current_notification_number", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.current_notification_number',
            },
        },
        'host_custom_variables': {
            'description': 'A dictionary of the custom variables of the service',
            'function': lambda item: [], #FIXME
            'type': list,
            'projections': [],
            'filters': {},
        },
        'host_custom_variable_names': {
            'description': 'A list of the names of all custom variables of the service',
            'function': lambda item: [], #FIXME
            'type': list,
            'projections': [],
            'filters': {},
        },
        'host_custom_variable_values': {
            'description': 'A list of the values of the custom variables of the service',
            'function': lambda item: [], #FIXME
            'type': list,
            'projections': [],
            'filters': {},
        },
        'host_display_name': {
            'description': 'Optional display name of the host - not used by Nagios\' web interface',
            'function': lambda item: linked_host_attr(item, "display_name"),
            'filters': {
                'attr': 'hosts.display_name',
            },
        },
        'host_downtimes': {
            'description': 'A list of the ids of all scheduled downtimes of this host',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'host_downtimes_with_info': {
            'description': 'A list of the all scheduled downtimes of the host with id, author and comment',

            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'host_event_handler': {
            'description': 'Nagios command used as event handler of this host',
            'function': lambda item: linked_host_attr(item, "event_handler"),
            'filters': {
                'attr': 'hosts.event_handler',
            },
        },
        'host_event_handler_enabled': {
            'description': 'Whether event handling is enabled for the host (0/1)',
            'function': lambda item: linked_host_attr(item, "event_handler_enabled", True),
            'datatype': bool,
            'filters': {
                'attr': 'hosts.event_handler_enabled',
            },
        },
        'host_execution_time': {
            'description': 'Time the host check needed for execution',
            'function': lambda item: linked_host_attr(item, "execution_time", 0),
            'datatype': float,
            'filters': {
                'attr': 'hosts.execution_time',
            },
        },
        'host_filename': {
            'description': 'The value of the custom variable FILENAME',
            'function': lambda item: '',  #FIXME
            'projections': [],
            'filters': {},
        },
        'host_first_notification_delay': {
            'description': 'Delay before the first notification',
            'function': lambda item: linked_host_attr(item, "first_notification_delay", 0),
            'datatype': float,
            'filters': {
                'attr': 'hosts.first_notification_delay',
            },
        },
        'host_flap_detection_enabled': {
            'description': 'Whether flap detection is enabled (0/1)',
            'function': lambda item: linked_host_attr(item, "flap_detection_enabled", True),
            'datatype': bool,
            'filters': {
                'attr': 'hosts.flap_detection_enabled',
            },
        },
        'host_groups': {
            'description': 'A list of all host groups this host is in',
            'function': lambda item: linked_host_attr(item, "hostgroups", []),
            'datatype': list,
            'filters': {
                'attr': 'hosts.hostgroups',
            },
        },
        'host_hard_state': {
            'description': 'The effective hard state of the host (eliminates a problem in hard_state)',
            'function': lambda item: linked_host_attr(item, "hard_state", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.hard_state',
            },
        },
        'host_has_been_checked': {
            'description': 'Whether the host has already been checked (0/1)',
            'function': lambda item: linked_host_attr(item, "has_been_checked", True),
            'datatype': bool,
            'filters': {
                'attr': 'hosts.has_been_checked',
            },
        },
        'host_high_flap_threshold': {
            'description': 'High threshold of flap detection',
            'function': lambda item: linked_host_attr(item, "high_flap_threshold", 0),
            'datatype': float,
            'filters': {
                'attr': 'hosts.high_flap_threshold',
            },
        },
        'host_icon_image': {
            'description': 'The name of an image file to be used in the web pages',
            'function': lambda item: linked_host_attr(item, "icon_image"),
            'filters': {
                'attr': 'hosts.icon_image',
            },
        },
        'host_icon_image_alt': {
            'description': 'Alternative text for the icon_image',
            'function': lambda item: linked_host_attr(item, "icon_image_alt"),
            'filters': {
                'attr': 'hosts.icon_image_alt',
            },
        },
        'host_icon_image_expanded': {
            'description': 'The same as icon_image, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projections': [],
            'filters': {},
        },
        'host_in_check_period': {
            'description': 'Whether this host is currently in its check period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projections': [],
            'filters': {},
        },
        'host_in_notification_period': {
            'description': 'Whether this host is currently in its notification period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projections': [],
            'filters': {},
        },
        'host_initial_state': {
            'description': 'Initial host state',
            'function': lambda item: linked_host_attr(item, "initial_state"),
            'datatype': int,
            'filters': {
                'attr': 'hosts.initial_state',
            },
        },
        'host_is_executing': {
            'description': 'is there a host check currently running... (0/1)',
            'function': lambda item: False,  #FIXME # value in scheduler is not real-time
            'datatype': bool,
            'filters': {},
        },
        'host_is_flapping': {
            'description': 'Whether the host state is flapping (0/1)',
            'function': lambda item: linked_host_attr(item, "is_flapping", False),
            'datatype': bool,
            'filters': {
                'attr': 'hosts.is_flapping',
            },
        },
        'host_last_check': {
            'description': 'Time of the last check (Unix timestamp)',
            'function': lambda item: linked_host_attr(item, "last_chk", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.last_chk',
            },
        },
        'host_last_hard_state': {
            'description': 'Last hard state',
            'function': lambda item: linked_host_attr(item, "last_hard_state_id", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.last_hard_state_id',
            },
        },
        'host_last_hard_state_change': {
            'description': 'Time of the last hard state change (Unix timestamp)',
            'function': lambda item: linked_host_attr(item, "last_hard_state_change", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.last_hard_state_change',
            },
        },
        'host_last_notification': {
            'description': 'Time of the last notification (Unix timestamp)',
            'function': lambda item: linked_host_attr(item, "last_notification", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.last_notification',
            },
        },
        'host_last_state': {
            'description': 'State before last state change',
            'function': lambda item: linked_host_attr(item, "last_state"),
            'filters': {
                'attr': 'hosts.last_state',
            },
        },
        'host_last_state_change': {
            'description': 'Time of the last state change - soft or hard (Unix timestamp)',
            'function': lambda item: linked_host_attr(item, "last_state_change", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.last_state_change',
            },
        },
        'host_last_time_down': {
            'description': 'The last time the host was DOWN (Unix timestamp)',
            'function': lambda item: linked_host_attr(item, "last_time_down", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.last_time_down',
            },
        },
        'host_last_time_unreachable': {
            'description': 'The last time the host was UNREACHABLE (Unix timestamp)',
            'function': lambda item: linked_host_attr(item, "last_time_unreachable", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.last_time_unreachable',
            },
        },
        'host_last_time_up': {
            'description': 'The last time the host was UP (Unix timestamp)',
            'function': lambda item: linked_host_attr(item, "last_time_up", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.last_time_up',
            },
        },
        'host_latency': {
            'description': 'Time difference between scheduled check time and actual check time',
            'function': lambda item: linked_host_attr(item, "latency", 0),
            'datatype': float,
            'filters': {
                'attr': 'hosts.latency',
            },
        },
        'host_long_plugin_output': {
            'description': 'Complete output from check plugin',
            'function': lambda item: linked_host_attr(item, "long_output"),
            'filters': {
                'attr': 'hosts.long_output',
            },
        },
        'host_low_flap_threshold': {
            'description': 'Low threshold of flap detection',
            'function': lambda item: linked_host_attr(item, "low_flap_threshold", 0),
            'datatype': float,
            'filters': {
                'attr': 'hosts.low_flap_threshold',
            },
        },
        'host_max_check_attempts': {
            'description': 'Max check attempts for active host checks',
            'function': lambda item: linked_host_attr(item, "max_checks_attempts", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.max_checks_attempts',
            },
        },
        'host_modified_attributes': {
            'description': 'A bitmask specifying which attributes have been modified',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'filters': {
                'attr': 'hosts.modified_attributes',
            },
        },
        'host_modified_attributes_list': {
            'description': 'A list of all modified attributes',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'filters': {},
        },
        'host_name': {
            'description': 'Host name',
            'function': lambda item: item["host_name"],
        },
        'host_next_check': {
            'description': 'Scheduled time for the next check (Unix timestamp)',
            'function': lambda item: linked_host_attr(item, "next_chk", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.next_chk',
            },
        },
        'host_next_notification': {
            'description': 'Time of the next notification (Unix timestamp)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'filters': {},
        },
        'host_notes': {
            'description': 'Optional notes about the service',
            'function': lambda item: linked_host_attr(item, "notes"),
            'filters': {
                'attr': 'hosts.notes',
            },
        },
        'host_notes_expanded': {
            'description': 'The same as notes, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'filters': {},
        },
        'host_notes_url': {
            'description': 'An optional URL with further information about the host',
            'function': lambda item: linked_host_attr(item, "notes_url"),
            'filters': {
                'attr': 'hosts.notes_url',
            },
        },
        'host_notes_url_expanded': {
            'description': 'Same es notes_url, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'filters': {},
        },
        'host_notification_interval': {
            'description': 'Interval of periodic notification or 0 if its off',
            'function': lambda item: linked_host_attr(item, "notification_interval", 0),
            'datatype': float,
            'filters': {
                'attr': 'hosts.notification_interval',
            },
        },
        'host_notification_period': {
            'description': 'Time period in which problems of this host will be notified. If empty then notification will be always',
            'function': lambda item: linked_host_attr(item, "notification_period"),
            'filters': {
                'attr': 'hosts.notification_period',
            },
        },
        'host_notifications_enabled': {
            'description': 'Whether notifications of the host are enabled (0/1)',
            'function': lambda item: linked_host_attr(item, "notifications_enabled", True),
            'datatype': bool,
            'filters': {
                'attr': 'hosts.notifications_enabled',
            },
        },
        'host_no_more_notifications': {
            'description': 'Whether to stop sending notifications (0/1)',
            'function': lambda item: linked_host_attr(item, "no_more_notifications", True),
            'datatype': bool,
            'filters': {
                'attr': 'hosts.no_more_notifications',
            },
        },
        'host_num_services': {
            'description': 'The total number of services of the host',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'filters': {},
        },
        'host_num_services_crit': {
            'description': 'The number of the host\'s services with the soft state CRIT',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'filters': {},
        },
        'host_num_services_hard_crit': {
            'description': 'The number of the host\'s services with the hard state CRIT',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'filters': {},
        },
        'host_num_services_hard_ok': {
            'description': 'The number of the host\'s services with the hard state OK',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'filters': {},
        },
        'host_num_services_hard_unknown': {
            'description': 'The number of the host\'s services with the hard state UNKNOWN',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'filters': {},
        },
        'host_num_services_hard_warn': {
            'description': 'The number of the host\'s services with the hard state WARN',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'filters': {},
        },
        'host_num_services_ok': {
            'description': 'The number of the host\'s services with the soft state OK',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'filters': {},
        },
        'host_num_services_pending': {
            'description': 'The number of the host\'s services which have not been checked yet (pending)',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'filters': {},
        },
        'host_num_services_unknown': {
            'description': 'The number of the host\'s services with the soft state UNKNOWN',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'filters': {},
        },
        'host_num_services_warn': {
            'description': 'The number of the host\'s services with the soft state WARN',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'filters': {},
        },
        'host_obsess_over_host': {
            'description': 'The current obsess_over_host setting... (0/1)',
            'function': lambda item: 0, #FIXME
            'datatype':int,
            'filters': {},
        },
        'host_parents': {
            'description': 'A list of all direct parents of the host',
            'function': lambda item: linked_host_attr(item, "alias", []),
            'datatype':list,
            'filters': {
                'attr': 'hosts.parents',
            },
        },
        'host_pending_flex_downtime': {
            'description': 'Whether a flex downtime is pending (0/1)',
            'function': lambda item: linked_host_attr(item, "pending_flex_downtimes", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.pending_flex_downtimes',
            },
        },
        'host_percent_state_change': {
            'description': 'Percent state change',
            'function': lambda item: linked_host_attr(item, "percent_state_change", 0),
            'datatype': float,
            'filters': {
                'attr': 'hosts.percent_state_change',
            },
        },
        'host_perf_data': {
            'description': 'Optional performance data of the last host check',
            'function': lambda item: linked_host_attr(item, "perf_data"),
            'filters': {
                'attr': 'hosts.perf_data',
            },
        },
        'host_plugin_output': {
            'description': 'Output of the last host check',
            'function': lambda item: linked_host_attr(item, "output"),
            'filters': {
                'attr': 'hosts.output',
            },
        },
        'host_pnpgraph_present': {
            'description': 'Whether there is a PNP4Nagios graph present for this host (0/1)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'filters': {},
        },
        'host_process_performance_data': {
            'description': 'Whether processing of performance data is enabled (0/1)',
            'function': lambda item: linked_host_attr(item, "process_performances_data", True),
            'datatype': bool,
            'filters': {
                'attr': 'hosts.process_performances_data',
            },
        },
        'host_retry_interval': {
            'description': 'Number of basic interval lengths between checks when retrying after a soft error',
            'function': lambda item: linked_host_attr(item, "retry_interval", 0),
            'datatype': float,
            'filters': {
                'attr': 'hosts.retry_interval',
            },
        },
        'host_scheduled_downtime_depth': {
            'description': 'The number of downtimes this host is currently in',
            'function': lambda item: linked_host_attr(item, "scheduled_downtime_depth", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.scheduled_downtime_depth',
            },
        },
        'host_services_with_info': {
            'description': 'A list of all services including detailed information about each service',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'filters': {},
        },
        'host_services': {
            'description': 'A list of all services of the host',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'filters': {},
        },
        'host_services_with_state': {
            'description': 'A list of all services of the host together with state and has_been_checked',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'filters': {},
        },
        'host_state': {
            'description': 'The current state of the host (0: up, 1: down, 2: unreachable)',
            'function': lambda item: linked_host_attr(item, "state_id", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.state_id',
            },
        },
        'host_state_type': {
            'description': 'Type of the current state (0: soft, 1: hard)',
            'function': lambda item: linked_host_attr(item, "state_type_id", 0),
            'datatype': int,
            'filters': {
                'attr': 'hosts.state_type_id',
            },
        },
        'host_statusmap_image': {
            'description': 'The name of in image file for the status map',
            'function': lambda item: linked_host_attr(item, "statusmap_image"),
            'filters': {
                'attr': 'hosts.statusmap_image',
            },
        },
        'host_tags': {
            'description': 'The list of Host Tags',
            'function': lambda item: linked_host_attr(item, "tags", []),
            'datatype': list,
            'filters': {
                'attr': 'hosts.tags',
            },
        },
        'host_total_services': {
            'description': 'The total number of services of the host',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'filters': {},
        },
        'host_worst_service_hard_state': {
            'description': 'The worst hard state of all of the host\'s services (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'filters': {},
        },
        'host_worst_service_state': {
            'description': 'The worst soft state of all of the host\'s services (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'filters': {},
        },
        'host_x_3d': {
            'description': '3D-Coordinates: X',
            'function': lambda item: linked_host_attr(item, "x_3d"),
            'datatype': float,
            'filters': {
                'attr': 'hosts.x_3d',
            },
        },
        'host_y_3d': {
            'description': '3D-Coordinates: Y',
            'function': lambda item: linked_host_attr(item, "y_3d"),
            'datatype': float,
            'filters': {
                'attr': 'hosts.y_3d',
            },
        },
        'host_z_3d': {
            'description': '3D-Coordinates: Z',
            'function': lambda item: linked_host_attr(item, "z_3d"),
            'datatype': float,
            'filters': {
                'attr': 'hosts.z_3d',
            },
        },
    },
    'Service': {
        'accept_passive_checks': {
            'description': 'Whether the service accepts passive checks (0/1)',
            'function': lambda item: item["passive_checks_enabled"],
            'datatype': bool,
            'filters': {
                'attr': 'passive_checks_enabled',
            },
        },
        'acknowledged': {
            'description': 'Whether the current service problem has been acknowledged (0/1)',
            'function': lambda item: item["problem_has_been_acknowledged"],
            'datatype': bool,
            'filters': {
                'attr': 'problem_has_been_acknowledged',
            },
        },
        'acknowledgement_type': {
            'description': 'The type of the acknownledgement (0: none, 1: normal, 2: sticky)',
            'function': lambda item: item["acknowledgement_type"],
            'datatype': int,
        },
        'action_url': {
            'description': 'An optional URL for actions or custom information about the service',
            'function': lambda item: item["action_url"],
        },
        'action_url_expanded': {
            'description': 'The action_url with (the most important) macros expanded',
            'function': lambda item: '', #FIXME
            'projections': [],
            'filters': {},
        },
        'active_checks_enabled': {
            'description': 'Whether active checks are enabled for the service (0/1)',
            'function': lambda item: item["active_checks_enabled"],
            'datatype': bool,
        },
        'business_impact': {
            'description': 'The importance we gave to this service between the minimum 0 and the maximum 5',
            'function': lambda item: item["business_impact"],
            'datatype': int,
        },
        'check_command': {
            'description': 'Nagios command used for active checks',
            'function': lambda item: item["check_command"],
        },
        'check_interval': {
            'description': 'Number of basic interval lengths between two scheduled checks of the service',
            'function': lambda item: item["check_interval"],
            'datatype': float,
        },
        'check_options': {
            'description': 'The current check option, forced, normal, freshness... (0/1)',
            'function': lambda item: 0,  #FIXME
            'datatype': int,
            'projections': [],
            'filters': {},
        },
        'check_period': {
            'description': 'The name of the check period of the service. It this is empty, the service is always checked.',
            'function': lambda item: item["check_period"],
        },
        'check_type': {
            'description': 'The type of the last check (0: active, 1: passive)',
            'function': lambda item: item["check_type"],
            'datatype': int,
        },
        'checks_enabled': {
            'description': 'Whether active checks are enabled for the service (0/1)',
            'function': lambda item: item["active_checks_enabled"],
            'datatype': bool,
            'filters': {
                'attr': 'active_checks_enabled',
            },
        },
        'child_dependencies': {
            'description': 'List of the host/service that depend on this service (logical, network or business one).',
            'function': lambda item: item["child_dependencies"],
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
            'projections': [],
            'filters': {},
        },
        'contacts': {
            'description': 'A list of all contacts of the service, either direct or via a contact group',
            'function': lambda item: item["contacts"], # CONTROLME c1 is in group cg1, c2 is in no group. svc has cg1,c2. only c2 is shown here
            'datatype': list,
        },
        'contact_groups': {
            'description': 'A list of all contact groups this service is in',
            'function': lambda item: item["contact_groups"],
            'datatype': list,
        },
        'criticity': {
            'description': 'The importance we gave to this service between the minimum 0 and the maximum 5',
            'function': lambda item: item["business_impact"],
            'datatype': int,
            'filters': {
                'attr': 'business_impact',
            },
        },
        'current_attempt': {
            'description': 'The number of the current check attempt',
            'function': lambda item: item["attempt"],
            'datatype': int,
            'filters': {
                'attr': 'attempt',
            },
        },
        'current_notification_number': {
            'description': 'The number of the current notification',
            'function': lambda item: item["current_notification_number"],
            'datatype': int,
        },
        'custom_variables': {
            'description': 'A dictionary of the custom variables',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'custom_variable_names': {
            'description': 'A list of the names of all custom variables of the service',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'custom_variable_values': {
            'description': 'A list of the values of all custom variable of the service',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'description': {
            'description': 'Description of the service (also used as key)',
            'function': lambda item: item["service_description"],
            'filters': {
                'attr': 'service_description',
            },
        },
        'display_name': {
            'description': 'An optional display name (not used by Nagios standard web pages)',
            'function': lambda item: item["display_name"],
        },
        'downtimes': {
            'description': 'A list of all downtime ids of the service',
            'function': lambda item: item["downtimes"],
            'datatype': list,
            'filters': {},
        },
        'downtimes_with_info': {
            'description': 'A list of all downtimes of the service with id, author and comment',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'event_handler': {
            'description': 'Nagios command used as event handler',
            'function': lambda item: item["event_handler"],
        },
        'event_handler_enabled': {
            'description': 'Whether and event handler is activated for the service (0/1)',
            'function': lambda item: item["event_handler_enabled"],
            'datatype': bool,
        },
        'execution_time': {
            'description': 'Time the host check needed for execution',
            'function': lambda item: item["execution_time"],
            'datatype': float,
        },
        'first_notification_delay': {
            'description': 'Delay before the first notification',
            'function': lambda item: item["first_notification_delay"],
            'datatype': float,
        },
        'flap_detection_enabled': {
            'description': 'Whether flap detection is enabled for the service (0/1)',
            'function': lambda item: item["flap_detection_enabled"],
            'datatype': bool,
        },
        'got_business_rule': {
            'description': 'Whether the service state is an business rule based host or not (0/1)',
            'function': lambda item: item["got_business_rule"],
            'datatype': bool,
        },
        'groups': {
            'description': 'A list of all service groups the service is in',
            'function': lambda item: item["servicegroups"],
            'datatype': list,
            'filters': {
                'attr': 'servicegroups',
            },
        },
        'has_been_checked': {
            'description': 'Whether the service already has been checked (0/1)',
            'function': lambda item: item["has_been_checked"],
            'datatype': int,
        },
        'high_flap_threshold': {
            'description': 'High threshold of flap detection',
            'function': lambda item: item["high_flap_threshold"],
            'datatype': float,
        },
        'icon_image': {
            'description': 'The name of an image to be used as icon in the web interface',
            'function': lambda item: item["icon_image"],
        },
        'icon_image_alt': {
            'description': 'An alternative text for the icon_image for browsers not displaying icons',
            'function': lambda item: item["icon_image_alt"],
        },
        'icon_image_expanded': {
            'description': 'The icon_image with (the most important) macros expanded',
            'function': lambda tem: '', #FIXME
            'projections': [],
            'filters': {},
        },
        'impacts': {
            'description': 'List of what the source impact (list of hosts and services)',
            'function': lambda item: item["impacts"],
            'datatype': list,
        },
        'in_check_period': {
            'description': 'Whether the service is currently in its check period (0/1)',
            'function': lambda tem: False, #FIXME
            'datatype': bool,
            'projections': [],
            'filters': {},
        },
        'in_notification_period': {
            'description': 'Whether the service is currently in its notification period (0/1)',
            'function': lambda tem: False, #FIXME
            'datatype': bool,
            'projections': [],
            'filters': {},
        },
        'initial_state': {
            'description': 'The initial state of the service',
            'function': lambda item: item["initial_state"],
        },
        'is_executing': {
            'description': 'is there a service check currently running... (0/1)',
            'function': lambda item: False,  # REPAIRME # value in scheduler is not real-time
            'datatype': bool,
            'projections': [],
            'filters': {},
        },
        'is_flapping': {
            'description': 'Whether the service is flapping (0/1)',
            'function': lambda item: item["is_flapping"],
            'datatype': bool,
        },
        'is_impact': {
            'description': 'Whether the host state is an impact or not (0/1)',
            'function': lambda item: item["is_impact"],
            'datatype': bool,
        },
        'is_problem': {
            'description': 'Whether the host state is a problem or not (0/1)',
            'function': lambda item: item["is_problem"],
            'datatype': bool,
        },
        'labels': {
            'description': 'Arbitrary labels (separated by comma character)',
            'function': lambda item: item["labels"],
            'datatype': list,
        },
        'latency': {
            'description': 'Time difference between scheduled check time and actual check time',
            'function': lambda item: item["latency"],  # CONTROLME INSORTME
            'datatype': float,
        },
        'last_check': {
            'description': 'The time of the last check (Unix timestamp)',
            'function': lambda item: int(item.last_chk),
            'datatype': int,
        },
        'last_hard_state': {
            'description': 'The last hard state of the service',
            'function': lambda item: item["last_hard_state"],
            'datatype': int,
        },
        'last_hard_state_change': {
            'description': 'The time of the last hard state change (Unix timestamp)',
            'function': lambda item: item["last_hard_state_change"],
            'datatype': int,
        },
        'last_notification': {
            'description': 'The time of the last notification (Unix timestamp)',
            'function': lambda item: item["last_notification"],
            'datatype': int,
        },
        'last_state': {
            'description': 'The last state of the service',
            'function': lambda item: item["last_state"],
        },
        'last_state_change': {
            'description': 'The time of the last state change (Unix timestamp)',
            'function': lambda item: item["last_state_change"],
            'datatype': int,
        },
        'last_time_critical': {
            'description': 'The last time the service was CRITICAL (Unix timestamp)',
            'function': lambda item: item["last_time_critical"],  # CONTROLME INSORTME
            'datatype': int,
        },
        'last_time_warning': {
            'description': 'The last time the service was in WARNING state (Unix timestamp)',
            'function': lambda item: item["last_time_warning"],  # CONTROLME INSORTME
            'datatype': int,
        },
        'last_time_ok': {
            'description': 'The last time the service was OK (Unix timestamp)',
            'function': lambda item: item["last_time_ok"],  # CONTROLME INSORTME
            'datatype': int,
        },
        'last_time_unknown': {
            'description': 'The last time the service was UNKNOWN (Unix timestamp)',
            'function': lambda item: item["last_time_unknown"],  # CONTROLME INSORTME
            'datatype': int,
        },
        'latency': {
            'description': 'Time difference between scheduled check time and actual check time',
            'function': lambda item: item["latency"],
            'datatype': int,
        },
        'long_plugin_output': {
            'description': 'Unabbreviated output of the last check plugin',
            'function': lambda item: item["long_output"],
            'filter': 'long_output',
        },
        'low_flap_threshold': {
            'description': 'Low threshold of flap detection',
            'function': lambda item: item["low_flap_threshold"],
            'datatype': float,
        },
        'max_check_attempts': {
            'description': 'The maximum number of check attempts',
            'function': lambda item: item["max_check_attempts"],
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
            'projections': [],
            'filters': {},
        },
        'next_check': {
            'description': 'The scheduled time of the next check (Unix timestamp)',
            'function': lambda item: item["next_chk"],
            'datatype': int,
            'filter': {
                'pre': ['next_chk']
            },
        },
        'next_notification': {
            'description': 'The time of the next notification (Unix timestamp)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projections': [],
            'filters': {},
        },
        'notes': {
            'description': 'Optional notes about the service',
            'function': lambda item: item["notes"],
        },
        'notes_expanded': {
            'description': 'The notes with (the most important) macros expanded',
            'function': lambda item: '', #FIXME
            'projections': [],
            'filters': {},
        },
        'notes_url': {
            'description': 'An optional URL for additional notes about the service',
            'function': lambda item: item["notes_url"],
        },
        'notes_url_expanded': {
            'description': 'The notes_url with (the most important) macros expanded',
            'function': lambda item: MacroResolver().resolve_simple_macros_in_string(item.notes_url, item.get_data_for_checks()),
        },
        'notification_interval': {
            'description': 'Interval of periodic notification or 0 if its off',
            'function': lambda item: item["notification_interval"],
            'datatype': float,
        },
        'notification_options': {
            'description': 'The options controlling when notification should be sent',
            'function': lambda item: item["notification_options"],
            'datatype': list,
        },
        'notification_period': {
            'description': 'The name of the notification period of the service. It this is empty, service problems are always notified.',
            'function': lambda item: item["notification_period"],
        },
        'notifications_enabled': {
            'description': 'Whether notifications are enabled for the service (0/1)',
            'function': lambda item: item["notifications_enabled"],
            'datatype': bool,
        },
        'no_more_notifications': {
            'description': 'Whether to stop sending notifications (0/1)',
            'function': lambda item: item["no_more_notifications"],  # CONTROLME INSORTME
            'datatype': bool,
        },
        'obsess_over_service': {
            'description': 'Whether \'obsess_over_service\' is enabled for the service (0/1)',
            'function': lambda item: item["obsess_over_service"],
            'datatype': bool,
        },
        'parent_dependencies': {
            'description': 'List of the dependencies (logical, network or business one) of this service.',
            'function': lambda item: item["parent_dependencies"],
            'datatype': list,
        },
        'percent_state_change': {
            'description': 'Percent state change',
            'function': lambda item: item["percent_state_change"],
            'datatype': float,
        },
        'perf_data': {
            'description': 'Performance data of the last check plugin',
            'function': lambda item: item["perf_data"],
        },
        'plugin_output': {
            'description': 'Output of the last check plugin',
            'function': lambda item: item["output"],
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
            'function': lambda item: item["poller_tag"],
        },
        'process_performance_data': {
            'description': 'Whether processing of performance data is enabled for the service (0/1)',
            'function': lambda item: item["process_perf_data"],
            'datatype': bool,
            'filters': {
                'attr': 'process_perf_data',
            },
        },
        'retry_interval': {
            'description': 'Number of basic interval lengths between checks when retrying after a soft error',
            'function': lambda item: item["retry_interval"],
            'datatype': float,
        },
        'scheduled_downtime_depth': {
            'description': 'The number of scheduled downtimes the service is currently in',
            'function': lambda item: item["scheduled_downtime_depth"],
            'datatype': int,
        },
        'service_description': {
            'description': 'Description of the service (also used as key)',
            'function': lambda item: item["service_description"],
        },
        'source_problems': {
            'description': 'The name of the source problems (host or service)',
            'function': lambda item: "",  # REPAIRME
            'datatype': list,
        },
        'state': {
            'description': 'The current state of the service (0: OK, 1: WARN, 2: CRITICAL, 3: UNKNOWN)',
            'function': lambda item: item["state_id"],
            'datatype': int,
            'filters': {
                'attr': 'state_id',
            },
        },
        'state_type': {
            'description': 'The type of the current state (0: soft, 1: hard)',
            'function': lambda item: item["state_type_id"],
            'datatype': int,
            'filters': {
                'attr': 'state_type_id',
            },
        },
    },
    'ServiceLink': {
        'service_accept_passive_checks': {
            'description': 'Whether passive service checks are accepted (0/1)',
            'function': lambda item: item["service"]["problem_has_been_acknowledged"],
            'datatype': bool,
            'filters': {
                'attr': 'service.passive_checks_enabled',
            },
        },
        'service_acknowledged': {
            'description': 'Whether the current service problem has been acknowledged (0/1)',
            'function': lambda item: item["service"]["problem_has_been_acknowledged"],
            'datatype': bool,
            'filters': {
                'attr': 'service.problem_has_been_acknowledged',
            },
        },
        'service_acknowledgement_type': {
            'description': 'Type of acknowledgement (0: none, 1: normal, 2: stick)',
            'function': lambda item: item["service"]["acknowledgement_type"],
            'datatype': int,
            'filters': {
                'attr': 'service.acknowledgement_type',
            },
        },
        'service_action_url': {
            'description': 'An optional URL to custom actions or information about this service',
            'function': lambda item: item["service"]["action_url"],
            'filters': {
                'attr': 'service.action_url',
            },
        },
        'service_action_url_expanded': {
            'description': 'The same as action_url, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projections': [],
            'filters': {},
        },
        'service_active_checks_enabled': {
            'description': 'Whether active checks are enabled for the service (0/1)',
            'function': lambda item: item["service"]["active_checks_enabled"],
            'filters': {
                'attr': 'service.active_checks_enabled',
            },
        },
        'service_check_command': {
            'description': 'Nagios command used for active checks',
            'function': lambda item: item["service"]["check_command"],
            'filters': {
                'attr': 'service.check_command',
            },
        },
        'service_check_interval': {
            'description': 'Number of basic interval lengths between two scheduled checks of the service',
            'function': lambda item: item["service"]["check_interval"],
            'datatype': float,
            'filters': {
                'attr': 'service.check_interval',
            },
        },
        'service_check_options': {
            'description': 'The current check option, forced, normal, freshness... (0-2)',
            'function': lambda item: item["service"]["alias"],
            'filters': {
                'attr': 'service.alias',
            },
        },
        'service_check_period': {
            'description': 'Time period in which this service will be checked. If empty then the service will always be checked.',
            'function': lambda item: item["service"]["alias"],
            'filters': {
                'attr': 'service.alias',
            },
        },
        'service_check_type': {
            'description': 'Type of check (0: active, 1: passive)',
            'function': lambda item: 0,  # REPAIRME
            'datatype': int,
            'projections': [],
            'filters': {},
        },
        'service_checks_enabled': {
            'description': 'Whether active checks of the service are enabled (0/1)',
            'function': lambda item: item["service"]["checks_enabled"],
            'datatype': bool,
            'filters': {
                'attr': 'service.checks_enabled',
            },
        },
        'service_comments': {
            'description': 'A list of the ids of all comments of this service',
            'function': lambda item: item["service"]["comments"],
            'datatype': list,
            'filters': {
                'attr': 'service.comments',
            },
        },
        'service_comments_with_info': {
            'description': 'A list of all comments of the service with id, author and comment',
            'function': lambda item: [],  #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'service_contacts': {
            'description': 'A list of all contacts of this service, either direct or via a contact group',
            'function': lambda item: item["service"]["contacts"],
            'datatype': list,
            'filters': {
                'attr': 'service.contacts',
            },
        },
        'service_contact_groups': {
            'description': 'A list of all contact groups this service is in',
            'function': lambda item: item["service"]["contact_groups"],
            'datatype': list,
            'filters': {
                'attr': 'service.contact_groups',
            },
        },
        'service_current_attempt': {
            'description': 'Number of the current check attempts',
            'function': lambda item: item["service"]["attempt"],
            'datatype': int,
            'filters': {
                'attr': 'service.attempt',
            },
        },
        'service_current_notification_number': {
            'description': 'Number of the current notification',
            'function': lambda item: item["service"]["current_notification_number"],
            'datatype': int,
            'filters': {
                'attr': 'service.current_notification_number',
            },
        },
        'service_custom_variables': {
            'description': 'A dictionary of the custom variables of the service',
            'function': lambda item: [], #FIXME
            'type': list,
            'projections': [],
            'filters': {},
        },
        'service_custom_variable_names': {
            'description': 'A list of the names of all custom variables of the service',
            'function': lambda item: [], #FIXME
            'type': list,
            'projections': [],
            'filters': {},
        },
        'service_custom_variable_values': {
            'description': 'A list of the values of the custom variables of the service',
            'function': lambda item: [], #FIXME
            'type': list,
            'projections': [],
            'filters': {},
        },
        'service_display_name': {
            'description': 'Optional display name of the service - not used by Nagios\' web interface',
            'function': lambda item: item["service"]["display_name"],
            'filters': {
                'attr': 'service.display_name',
            },
        },
        'service_downtimes': {
            'description': 'A list of the ids of all scheduled downtimes of this service',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'service_downtimes_with_info': {
            'description': 'A list of the all scheduled downtimes of the service with id, author and comment',

            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'service_event_handler': {
            'description': 'Nagios command used as event handler of this service',
            'function': lambda item: item["service"]["event_handler"],
            'filters': {
                'attr': 'service.event_handler',
            },
        },
        'service_event_handler_enabled': {
            'description': 'Whether event handling is enabled for the service (0/1)',
            'function': lambda item: item["service"]["event_handler_enabled"],
            'datatype': bool,
            'filters': {
                'attr': 'service.event_handler_enabled',
            },
        },
        'service_execution_time': {
            'description': 'Time the service check needed for execution',
            'function': lambda item: item["service"]["execution_time"],
            'datatype': float,
            'filters': {
                'attr': 'service.execution_time',
            },
        },
        'service_first_notification_delay': {
            'description': 'Delay before the first notification',
            'function': lambda item: item["service"]["first_notification_delay"],
            'datatype': float,
            'filters': {
                'attr': 'service.first_notification_delay',
            },
        },
        'service_flap_detection_enabled': {
            'description': 'Whether flap detection is enabled (0/1)',
            'function': lambda item: item["service"]["flap_detection_enabled"],
            'datatype': bool,
            'filters': {
                'attr': 'service.flap_detection_enabled',
            },
        },
        'service_groups': {
            'description': 'A list of all service groups this service is in',
            'function': lambda item: item["service"]["servicegroups"],
            'datatype': list,
            'filters': {
                'attr': 'service.servicegroups',
            },
        },
        'service_has_been_checked': {
            'description': 'Whether the service has already been checked (0/1)',
            'function': lambda item: item["service"]["has_been_checked"],
            'datatype': bool,
            'filters': {
                'attr': 'service.has_been_checked',
            },
        },
        'service_high_flap_threshold': {
            'description': 'High threshold of flap detection',
            'function': lambda item: item["service"]["high_flap_threshold"],
            'datatype': float,
            'filters': {
                'attr': 'service.high_flap_threshold',
            },
        },
        'service_icon_image': {
            'description': 'The name of an image file to be used in the web pages',
            'function': lambda item: item["service"]["icon_image"],
            'filters': {
                'attr': 'service.icon_image',
            },
        },
        'service_icon_image_alt': {
            'description': 'Alternative text for the icon_image',
            'function': lambda item: item["service"]["icon_image_alt"],
            'filters': {
                'attr': 'service.icon_image_alt',
            },
        },
        'service_icon_image_expanded': {
            'description': 'The same as icon_image, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'projections': [],
            'filters': {},
        },
        'service_in_check_period': {
            'description': 'Whether this service is currently in its check period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projections': [],
            'filters': {},
        },
        'service_in_notification_period': {
            'description': 'Whether this service is currently in its notification period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projections': [],
            'filters': {},
        },
        'service_initial_state': {
            'description': 'Initial service state',
            'function': lambda item: item["service"]["initial_state"],
            'filters': {
                'attr': 'service.initial_state',
            },
        },
        'service_is_executing': {
            'description': 'is there a service check currently running... (0/1)',
            'function': lambda item: False,  #FIXME # value in scheduler is not real-time
            'datatype': bool,
            'filters': {},
        },
        'service_is_flapping': {
            'description': 'Whether the service state is flapping (0/1)',
            'function': lambda item: item["service"]["is_flapping"],
            'datatype': bool,
            'filters': {
                'attr': 'service.is_flapping',
            },
        },
        'service_last_check': {
            'description': 'Time of the last check (Unix timestamp)',
            'function': lambda item: item["service"]["last_chk"],
            'datatype': int,
            'filters': {
                'attr': 'service.last_chk',
            },
        },
        'service_last_hard_state': {
            'description': 'Last hard state',
            'function': lambda item: item["service"]["last_hard_state_id"],
            'datatype': int,
            'filters': {
                'attr': 'service.last_hard_state_id',
            },
        },
        'service_last_hard_state_change': {
            'description': 'Time of the last hard state change (Unix timestamp)',
            'function': lambda item: item["service"]["last_hard_state_change"],
            'datatype': int,
            'filters': {
                'attr': 'service.last_hard_state_change',
            },
        },
        'service_last_notification': {
            'description': 'Time of the last notification (Unix timestamp)',
            'function': lambda item: item["service"]["last_notification"],
            'datatype': int,
            'filters': {
                'attr': 'service.last_notification',
            },
        },
        'service_last_state': {
            'description': 'State before last state change',
            'function': lambda item: item["service"]["last_state"],
            'filters': {
                'attr': 'service.last_state',
            },
        },
        'service_last_state_change': {
            'description': 'Time of the last state change - soft or hard (Unix timestamp)',
            'function': lambda item: item["service"]["last_state_change"],
            'datatype': int,
            'filters': {
                'attr': 'service.last_state_change',
            },
        },
        'service_last_time_down': {
            'description': 'The last time the service was DOWN (Unix timestamp)',
            'function': lambda item: item["service"]["last_time_down"],
            'datatype': int,
            'filters': {
                'attr': 'service.last_time_down',
            },
        },
        'service_last_time_unreachable': {
            'description': 'The last time the service was UNREACHABLE (Unix timestamp)',
            'function': lambda item: item["service"]["last_time_unreachable"],
            'datatype': int,
            'filters': {
                'attr': 'service.last_time_unreachable',
            },
        },
        'service_last_time_up': {
            'description': 'The last time the service was UP (Unix timestamp)',
            'function': lambda item: item["service"]["last_time_up"],
            'datatype': int,
            'filters': {
                'attr': 'service.last_time_up',
            },
        },
        'service_latency': {
            'description': 'Time difference between scheduled check time and actual check time',
            'function': lambda item: item["service"]["latency"],
            'datatype': float,
            'filters': {
                'attr': 'service.latency',
            },
        },
        'service_long_plugin_output': {
            'description': 'Complete output from check plugin',
            'function': lambda item: item["service"]["long_output"],
            'filters': {
                'attr': 'service.long_output',
            },
        },
        'service_low_flap_threshold': {
            'description': 'Low threshold of flap detection',
            'function': lambda item: item["service"]["low_flap_threshold"],
            'datatype': float,
            'filters': {
                'attr': 'service.low_flap_threshold',
            },
        },
        'service_max_check_attempts': {
            'description': 'Max check attempts for active service checks',
            'function': lambda item: item["service"]["max_checks_attempts"],
            'datatype': int,
            'filters': {
                'attr': 'service.max_checks_attempts',
            },
        },
        'service_modified_attributes': {
            'description': 'A bitmask specifying which attributes have been modified',
            'function': lambda item: len(item["service"]["modified_attributes"]),
            'datatype': int,
            'filters': {
                'attr': 'service.modified_attributes',
            },
        },
        'service_modified_attributes_list': {
            'description': 'A list of all modified attributes',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'filters': {},
        },
        'service_next_check': {
            'description': 'Scheduled time for the next check (Unix timestamp)',
            'function': lambda item: item["service"]["alias"],
            'datatype': int,
            'filters': {
                'attr': 'service.next_chk',
            },
        },
        'service_next_notification': {
            'description': 'Time of the next notification (Unix timestamp)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'filters': {},
        },
        'service_notes': {
            'description': 'Optional notes about the service',
            'function': lambda item: item["service"]["notes"],
            'filters': {
                'attr': 'service.notes',
            },
        },
        'service_notes_expanded': {
            'description': 'The same as notes, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'filters': {},
        },
        'service_notes_url': {
            'description': 'An optional URL with further information about the service',
            'function': lambda item: item["service"]["notes_url"],
            'filters': {
                'attr': 'service.notes_url',
            },
        },
        'service_notes_url_expanded': {
            'description': 'Same es notes_url, but with the most important macros expanded',
            'function': lambda item: '', #FIXME
            'filters': {},
        },
        'service_notification_interval': {
            'description': 'Interval of periodic notification or 0 if its off',
            'function': lambda item: item["service"]["notification_interval"],
            'datatype': float,
            'filters': {
                'attr': 'service.notification_interval',
            },
        },
        'service_notification_period': {
            'description': 'Time period in which problems of this service will be notified. If empty then notification will be always',
            'function': lambda item: item["service"]["notification_period"],
            'filters': {
                'attr': 'service.notification_period',
            },
        },
        'service_notifications_enabled': {
            'description': 'Whether notifications of the service are enabled (0/1)',
            'function': lambda item: item["service"]["notifications_enabled"],
            'datatype': bool,
            'filters': {
                'attr': 'service.notifications_enabled',
            },
        },
        'service_no_more_notifications': {
            'description': 'Whether to stop sending notifications (0/1)',
            'function': lambda item: item["service"]["no_more_notifications"],
            'datatype': bool,
            'filters': {
                'attr': 'service.no_more_notifications',
            },
        },
        'service_percent_state_change': {
            'description': 'Percent state change',
            'function': lambda item: item["service"]["percent_state_change"],
            'datatype': float,
            'filters': {
                'attr': 'service.percent_state_change',
            },
        },
        'service_perf_data': {
            'description': 'Optional performance data of the last service check',
            'function': lambda item: item["service"]["perf_data"],
            'filters': {
                'attr': 'service.perf_data',
            },
        },
        'service_plugin_output': {
            'description': 'Output of the last service check',
            'function': lambda item: item["service"]["output"],
            'filters': {
                'attr': 'service.output',
            },
        },
        'service_pnpgraph_present': {
            'description': 'Whether there is a PNP4Nagios graph present for this service (0/1)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'filters': {},
        },
        'service_process_performance_data': {
            'description': 'Whether processing of performance data is enabled (0/1)',
            'function': lambda item: item["service"]["process_performances_data"],
            'datatype': bool,
            'filters': {
                'attr': 'service.process_performances_data',
            },
        },
        'service_retry_interval': {
            'description': 'Number of basic interval lengths between checks when retrying after a soft error',
            'function': lambda item: item["service"]["retry_interval"],
            'datatype': float,
            'filters': {
                'attr': 'service.retry_interval',
            },
        },
        'service_scheduled_downtime_depth': {
            'description': 'The number of downtimes this service is currently in',
            'function': lambda item: item["service"]["scheduled_downtime_depth"],
            'datatype': int,
            'filters': {
                'attr': 'service.scheduled_downtime_depth',
            },
        },
        'service_state': {
            'description': 'The current state of the service (0: up, 1: down, 2: unreachable)',
            'function': lambda item: item["service"]["state_id"],
            'datatype': int,
            'filters': {
                'attr': 'service.state_id',
            },
        },
        'service_state_type': {
            'description': 'Type of the current state (0: soft, 1: hard)',
            'function': lambda item: item["service"]["state_type_id"],
            'datatype': int,
            'filters': {
                'attr': 'service.state_type_id',
            },
        },
    },
    'ServicesLink': {
        'num_services': {
            'description': 'The total number of services of the host',
            'function': lambda item: len(item["services"]),
            'projections': ['services.service_description'],
            'filters': {},
        },
        'num_services_crit': {
            'description': 'The number of the host\'s services with the soft state CRIT',
            'function': lambda item: state_count(item, "services", 0, 2),
            'datatype': int,
            'projections': [
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
            'projections': [
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
            'projections': [
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
            'projections': [
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
            'projections': [
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
            'projections': [
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
            'projections': [
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
            'projections': [
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
            'projections': [
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
            'projections': [
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
            'projections': [
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
            'projections': ["hosts.host_name"],
        },
        'num_hosts_down': {
            'description': 'The number of hosts in the group that are down',
            'function': lambda item: state_count(item, "hosts", 1, 1),
            'datatype': int,
            'projections': [
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
            'projections': [
                'hosts.state',
                'hosts.state_id',
                'hosts.state_type_id'
            ],
            'filters': {},
        },
        'num_hosts_unreach': {
            'function': lambda item: state_count(item, "hosts", 1, 2),
            'datatype': int,
            'projections': [
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
            'projections': [
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
            'projections': [
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
            'function': lambda item: item["action_url"],
        },
        'alias': {
            'description': 'An alias of the hostgroup',
            'function': lambda item: item["alias"],
        },
        'hostgroup_name': {
            'description': 'Name of the hostgroup',
            'function': lambda item: item["hostgroup_name"],
        },
        'members': {
            'description': 'A list of all host names that are members of the hostgroup',
            'function': lambda item: item["members"],
            'datatype': list,
        },
        'members_with_state': {
            'description': 'A list of all host names that are members of the hostgroup together with state and has_been_checked',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'name': {
            'description': 'Name of the hostgroup',
            'function': lambda item: item["hostgroup_name"],
            'filter': 'hostgroup_name',
        },
        'notes': {
            'description': 'Optional notes to the hostgroup',
            'function': lambda item: item["notes"],
        },
        'notes_url': {
            'description': 'An optional URL with further information about the hostgroup',
            'function': lambda item: item["notes_url"],
        },
        'num_hosts': {
            'description': 'The total number of hosts in the group',
            'function': lambda item: len(item.members),
            'projections': ["hosts.host_name"],
        },
        'num_hosts_down': {
            'description': 'The number of hosts in the group that are down',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projections': ["hosts.state_id"],
            'filters': {},
        },
        'num_hosts_pending': {
            'description': 'The number of hosts in the group that are pending',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projections': ["hosts.state_id"],
            'filters': {},
        },
        'num_hosts_unreach': {
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projections': ["hosts.state_id"],
            'filters': {},
        },
        'num_hosts_up': {
            'description': 'The number of hosts in the group that are up',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projections': ["hosts.state_id"],
            'filters': {},
        },
        'num_services': {
            'description': 'The total number of services of hosts in this group',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projections': ["services.state_id"],
            'filters': {},
        },
        'worst_host_state': {
            'description': 'The worst state of all of the groups\' hosts (UP <= UNREACHABLE <= DOWN)',
            'function': lambda item: 0, #FIXME
            'datatype': int,
            'projections': ["services.state_id"],
            'filters': {},
        },
    },
    'Servicegroup': {
        'action_url': {
            'description': 'An optional URL to custom notes or actions on the service group',
            'function': lambda item: item["action_url"],
        },
        'alias': {
            'description': 'An alias of the service group',
            'function': lambda item: item["alias"],
        },
        'members': {
            'description': 'A list of all members of the service group as host/service pairs',
            'function': lambda item: item["members"],
            'datatype': list,
        },
        'members_with_state': {
            'description': 'A list of all members of the service group with state and has_been_checked',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'name': {
            'description': 'The name of the service group',
            'function': lambda item: item["servicegroup_name"],
            'filters': {
                'attr': 'servicegroup_name',
            },
        },
        'notes': {
            'description': 'Optional additional notes about the service group',
            'function': lambda item: item["notes"],
        },
        'notes_url': {
            'description': 'An optional URL to further notes on the service group',
            'function': lambda item: item["notes_url"],
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
            'projections': ["services.state_id"],
            'filters': {},
        },
    },
    'Contact': {
        'address1': {
            'description': 'The additional field address1',
            'function': lambda item: item["address1"],
        },
        'address2': {
            'description': 'The additional field address2',
            'function': lambda item: item["address2"],
        },
        'address3': {
            'description': 'The additional field address3',
            'function': lambda item: item["address3"],
        },
        'address4': {
            'description': 'The additional field address4',
            'function': lambda item: item["address4"],
        },
        'address5': {
            'description': 'The additional field address5',
            'function': lambda item: item["address5"],
        },
        'address6': {
            'description': 'The additional field address6',
            'function': lambda item: item["address6"],
        },
        'alias': {
            'description': 'The full name of the contact',
            'function': lambda item: item["alias"],
        },
        'can_submit_commands': {
            'description': 'Whether the contact is allowed to submit commands (0/1)',
            'function': lambda item: item["can_submit_commands"],
            'datatype': bool,
        },
        'contact_name': {
            'description': 'The login name of the contact person',
            'function': lambda item: item["contact_name"],
        },
        'custom_variables': {
            'description': 'A dictionary of the custom variables',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'custom_variable_names': {
            'description': 'A list of all custom variables of the contact',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'custom_variable_values': {
            'description': 'A list of the values of all custom variables of the contact',
            'function': lambda item: [], #FIXME
            'datatype': list,
            'projections': [],
            'filters': {},
        },
        'email': {
            'description': 'The email address of the contact',
            'function': lambda item: item["email"],
        },
        'host_notification_period': {
            'description': 'The time period in which the contact will be notified about host problems',
            'function': lambda item: item["host_notification_period"],
        },
        'host_notifications_enabled': {
            'description': 'Whether the contact will be notified about host problems in general (0/1)',
            'function': lambda item: item["host_notifications_enabled"],
            'datatype': bool,
        },
        'host_notification_options': {
            'description': 'The options controlling when host notification should be sent to the contact',
            'function': lambda item: item["host_notification_options"],
            'datatype': list,
        },
        'in_host_notification_period': {
            'description': 'Whether the contact is currently in his/her host notification period (0/1)',
            'function': lambda item: False, #FIXME
            'datatype': bool,
            'projections': [],
            'filters': {},
        },
        'in_service_notification_period': {
            'description': 'Whether the contact is currently in his/her service notification period (0/1)',
            'function': lambda item: (item.service_notification_period is None and [False] or [item.service_notification_period.is_time_valid(req.tic)])[0],
            'datatype': bool,
        },
        'modified_attributes': {
            'description': 'A bitmask specifying which attributes have been modified',
            'function': lambda item: item["modified_attributes"],  # CONTROLME
            'datatype': int,
        },
        'modified_attributes_list': {
            'description': 'A list of all modified attributes',
            'function': lambda item: modified_attributes_names(item),
            'datatype': list,
        },
        'name': {
            'description': 'The login name of the contact person',
            'function': lambda item: item["contact_name"],
            'filter': 'contact_name',
        },
        'pager': {
            'description': 'The pager address of the contact',
            'function': lambda item: item["pager"],
        },
        'service_notification_options': {
            'description': 'The options controlling when service notification should be sent to the contact',
            'function': lambda item: item["service_notification_options"],
            'datatype': list,
        },
        'service_notification_period': {
            'description': 'The time period in which the contact will be notified about service problems',
            'function': lambda item: item["service_notification_period"],
        },
        'service_notifications_enabled': {
            'description': 'Whether the contact will be notified about service problems in general (0/1)',
            'function': lambda item: item["service_notifications_enabled"],
            'datatype': bool,
        },

    },
    'Contactgroup': {
        'alias': {
            'description': 'The alias of the contactgroup',
            'function': lambda item: item["alias"],
        },
        'contactgroup_name': {
            'description': 'The name of the contactgroup',
            'function': lambda item: item["contactgroup_name"],
        },
        'members': {
            'description': 'A list of all members of this contactgroup',
            'function': lambda item: item["members"],
            'datatype': list,
        },
        'name': {
            'description': 'The name of the contactgroup',
            'function': lambda item: item["contactgroup_name"],
            'filters': {
                'attr': 'contactgroup_name',
            },
        },
    },
    'Timeperiod': {
        'alias': {
            'description': 'The alias of the timeperiod',
            'function': lambda item: item["alias"],
        },
        'in': {
            'description': 'Whether we are currently in this period (0/1)',
            'function': lambda item: item["is_in"],  # CONTROLME REPAIRME
            'datatype': int,
        },
        'name': {
            'description': 'The name of the timeperiod',
            'function': lambda item: item["timeperiod_name"],
            'filters': {
                'attr': 'timeperiod_name',
            },
        },
        'timeperiod_name': {
            'description': 'The name of the timeperiod',
            'function': lambda item: item["timeperiod_name"],
        },
    },
    'Command': {
        'command_name': {
            'description': 'The name of the command',
            'function': lambda item: item["command_name"],
        },
        'command_line': {
            'description': 'The shell command line',
            'function': lambda item: item["command_line"],
        },
        'line': {
            'description': 'The shell command line',
            'function': lambda item: item["command_line"],
            'filters': {
                'attr': 'command_line',
            },
        },
        'name': {
            'description': 'The name of the command',
            'function': lambda item: item["command_name"],
            'filters': {
                'attr': 'command_name',
            },
        },
    },
    'SchedulerLink': {
        'address': {
            'description': 'The ip or dns address of the scheduler',
            'function': lambda item: item["address"],  # REPAIRME
        },
        'alive': {
            'description': 'If the scheduler is alive or not',
            'function': lambda item: item["alive"],
            'datatype': bool,
        },
        'name': {
            'description': 'The name of the scheduler',
            'function': lambda item: item["scheduler_name"],  # REPAIRME
            'filters': {
                'attr': 'scheduler_name',
            },
        },
        'port': {
            'description': 'The TCP port of the scheduler',
            'function': lambda item: item["port"],  # REPAIRME
            'datatype': int,
        },
        'scheduler_name': {
            'description': 'The name of the scheduler',
            'function': lambda item: item["scheduler_name"],  # REPAIRME
        },
        'spare': {
            'description': 'If the scheduler is a spare or not',
            'function': lambda item: item["spare"],
            'datatype': bool,
        },
        'weight': {
            'description': 'Weight (in terms of hosts) of the scheduler',
            'function': lambda item: item["weight"],  # REPAIRME
            'datatype': int,
        },
    },
    'PollerLink': {
        'address': {
            'description': 'The ip or dns address of the poller',
            'function': lambda item: item["address"],  # REPAIRME
        },
        'alive': {
            'description': 'If the poller is alive or not',
            'function': lambda item: item["alive"],
            'datatype': bool,
        },
        'name': {
            'description': 'The name of the poller',
            'function': lambda item: item["poller_name"],  # REPAIRME
            'filters': {
                'attr': 'poller_name',
            },
        },
        'poller_name': {
            'description': 'The name of the poller',
            'function': lambda item: item["poller_name"],  # REPAIRME
        },
        'port': {
            'description': 'The TCP port of the poller',
            'function': lambda item: item["port"],  # REPAIRME
            'datatype': int,
        },
        'spare': {
            'description': 'If the poller is a spare or not',
            'function': lambda item: item["spare"],
            'datatype': bool,
        },
    },
    'ReactionnerLink': {
        'address': {
            'description': 'The ip or dns address of the reactionner',
            'function': lambda item: item["address"],  # REPAIRME
        },
        'alive': {
            'description': 'If the reactionner is alive or not',
            'function': lambda item: item["alive"],
            'datatype': bool,
        },
        'name': {
            'description': 'The name of the reactionner',
            'function': lambda item: item["reactionner_name"],  # REPAIRME
            'filters': {
                'attr': 'reactionner_name',
            },
        },
        'port': {
            'description': 'The TCP port of the reactionner',
            'function': lambda item: item["port"],  # REPAIRME
            'datatype': int,
        },
        'reactionner_name': {
            'description': 'The name of the reactionner',
            'function': lambda item: item["reactionner_name"],  # REPAIRME
        },
        'spare': {
            'description': 'If the reactionner is a spare or not',
            'function': lambda item: item["spare"],
            'datatype': bool,
        },
    },
    'BrokerLink': {
        'address': {
            'description': 'The ip or dns address of the broker',
            'function': lambda item: item["address"],  # REPAIRME
        },
        'alive': {
            'description': 'If the broker is alive or not',
            'function': lambda item: item["alive"],
            'datatype': bool,
        },
        'broker_name': {
            'description': 'The name of the broker',
            'function': lambda item: item["broker_name"],  # REPAIRME
        },
        'name': {
            'description': 'The name of the broker',
            'function': lambda item: item["broker_name"],  # REPAIRME
            'filters': {
                'attr': 'broker_name',
            },
        },
        'port': {
            'description': 'The TCP port of the broker',
            'function': lambda item: item["port"],  # REPAIRME
            'datatype': int,
        },
        'spare': {
            'description': 'If the broker is a spare or not',
            'function': lambda item: item["spare"],
            'datatype': bool,
        },
    },
    'Problem': {
        'impacts': {
            'description': 'List of what the source impact (list of hosts and services)',
            'function': lambda item: item["impacts"],
        },
        'source': {
            'description': 'The source name of the problem (host or service)',
            'function': lambda item: item["source"],
        },
    },
    'Downtime': {
        'author': {
            'description': 'The contact that scheduled the downtime',
            'function': lambda item: item["author"],
        },
        'comment': {
            'description': 'A comment text',
            'function': lambda item: item["comment"],
        },
        'duration': {
            'description': 'The duration of the downtime in seconds',
            'function': lambda item: item["duration"],
            'datatype': int,
        },
        'end_time': {
            'description': 'The end time of the downtime as UNIX timestamp',
            'function': lambda item: item["end_time"],
            'datatype': int,
        },
        'entry_time': {
            'description': 'The time the entry was made as UNIX timestamp',
            'function': lambda item: item["entry_time"],
            'datatype': int,
        },
        'fixed': {
            'description': 'A 1 if the downtime is fixed, a 0 if it is flexible',
            'function': lambda item: item["fixed"],
            'datatype': bool,
        },
        'id': {
            'description': 'The id of the downtime',
            'function': lambda item: item["id"],
            'datatype': int,
        },
        'is_service': {
            'description': '0, if this entry is for a host, 1 if it is for a service',
            'function': lambda item: 'service_description' in item["ref"],
            'datatype': bool,
        },
        'start_time': {
            'description': 'The start time of the downtime as UNIX timestamp',
            'function': lambda item: item["start_time"],
            'datatype': int,
        },
        'triggered_by': {
            'description': 'The id of the downtime this downtime was triggered by or 0 if it was not triggered by another downtime',
            'function': lambda item: item["trigger_id"],
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
            'function': lambda item: item["author"],
        },
        'comment': {
            'description': 'A comment text',
            'function': lambda item: item["comment"],
        },
        'entry_time': {
            'description': 'The time the entry was made as UNIX timestamp',
            'function': lambda item: item["entry_time"],
            'datatype': int,
        },
        'entry_type': {
            'description': 'The type of the comment: 1 is user, 2 is downtime, 3 is flap and 4 is acknowledgement',
            'function': lambda item: item["entry_type"],
            'datatype': int,
        },
        'expire_time': {
            'description': 'The time of expiry of this comment as a UNIX timestamp',
            'function': lambda item: item["expire_time"],
            'datatype': int,
        },
        'expires': {
            'description': 'Whether this comment expires',
            'function': lambda item: item["expires"],
            'datatype': bool,
        },
        'id': {
            'description': 'The id of the comment',
            'function': lambda item: item["id"],
            'datatype': int,
        },
        'is_service': {
            'description': '0, if this entry is for a host, 1 if it is for a service',
            'function': lambda item: item["comment_type"] == 2,
            'datatype': bool,
        },
        'persistent': {
            'description': 'Whether this comment is persistent (0/1)',
            'function': lambda item: item["persistent"],
            'datatype': bool,
        },
        'source': {
            'description': 'The source of the comment (0 is internal and 1 is external)',
            'function': lambda item: item["source"],
            'datatype': int,
        },
        'type': {
            'description': 'The type of the comment: 1 is host, 2 is service',
            'function': lambda item: item["comment_type"],  # CONTROLME INSORTME
            'datatype': int,
        },
    },
    'Hostsbygroup': {
        'hostgroup_action_url': {
            'description': 'An optional URL to custom actions or information about the hostgroup',
            'function': lambda item: item["hostgroup"],  # REPAIRME
        },
        'hostgroup_alias': {
            'description': 'An alias of the hostgroup',
            'function': lambda item: "",  # REPAIRME
        },
        'hostgroup_members': {
            'description': 'A list of all host names that are members of the hostgroup',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': list,
        },
        'hostgroup_members_with_state': {
            'description': 'A list of all host names that are members of the hostgroup together with state and has_been_checked',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': list,
        },
        'hostgroup_name': {
            'description': 'Name of the hostgroup',
            'function': lambda item: "",  # REPAIRME
        },
        'hostgroup_notes': {
            'description': 'Optional notes to the hostgroup',
            'function': lambda item: item["hostgroup"],  # REPAIRME
        },
        'hostgroup_notes_url': {
            'description': 'An optional URL with further information about the hostgroup',
            'function': lambda item: item["hostgroup"],  # REPAIRME
        },
        'hostgroup_num_hosts': {
            'description': 'The total number of hosts in the group',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_hosts_down': {
            'description': 'The number of hosts in the group that are down',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_hosts_pending': {
            'description': 'The number of hosts in the group that are pending',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_hosts_unreach': {
            'description': 'The number of hosts in the group that are unreachable',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_hosts_up': {
            'description': 'The number of hosts in the group that are up',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services': {
            'description': 'The total number of services of hosts in this group',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_crit': {
            'description': 'The total number of services with the state CRIT of hosts in this group',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_hard_crit': {
            'description': 'The total number of services with the state CRIT of hosts in this group',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_hard_ok': {
            'description': 'The total number of services with the state OK of hosts in this group',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_hard_unknown': {
            'description': 'The total number of services with the state UNKNOWN of hosts in this group',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_hard_warn': {
            'description': 'The total number of services with the state WARN of hosts in this group',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_ok': {
            'description': 'The total number of services with the state OK of hosts in this group',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_pending': {
            'description': 'The total number of services with the state Pending of hosts in this group',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_unknown': {
            'description': 'The total number of services with the state UNKNOWN of hosts in this group',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_warn': {
            'description': 'The total number of services with the state WARN of hosts in this group',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_worst_host_state': {
            'description': 'The worst state of all of the groups\' hosts (UP <= UNREACHABLE <= DOWN)',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_worst_service_hard_state': {
            'description': 'The worst state of all services that belong to a host of this group (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
        'hostgroup_worst_service_state': {
            'description': 'The worst state of all services that belong to a host of this group (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: item["hostgroup"],  # REPAIRME
            'datatype': int,
        },
    },
    'Servicesbygroup': {
        'servicegroup_action_url': {
            'description': 'An optional URL to custom notes or actions on the service group',
            'function': lambda item: "",  # REPAIRME
        },
        'servicegroup_alias': {
            'description': 'An alias of the service group',
            'function': lambda item: "",  # REPAIRME
        },
        'servicegroup_members': {
            'description': 'A list of all members of the service group as host/service pairs',
            'function': lambda item: "",  # REPAIRME
            'datatype': list,
        },
        'servicegroup_members_with_state': {
            'description': 'A list of all members of the service group with state and has_been_checked',
            'function': lambda item: "",  # REPAIRME
            'datatype': list,
        },
        'servicegroup_name': {
            'description': 'The name of the service group',
            'function': lambda item: "",  # REPAIRME
        },
        'servicegroup_notes': {
            'description': 'Optional additional notes about the service group',
            'function': lambda item: "",  # REPAIRME
        },
        'servicegroup_notes_url': {
            'description': 'An optional URL to further notes on the service group',
            'function': lambda item: "",  # REPAIRME
        },
        'servicegroup_num_services': {
            'description': 'The total number of services in the group',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'servicegroup_num_services_crit': {
            'description': 'The number of services in the group that are CRIT',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'servicegroup_num_services_hard_crit': {
            'description': 'The number of services in the group that are CRIT',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'servicegroup_num_services_hard_ok': {
            'description': 'The number of services in the group that are OK',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'servicegroup_num_services_hard_unknown': {
            'description': 'The number of services in the group that are UNKNOWN',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'servicegroup_num_services_hard_warn': {
            'description': 'The number of services in the group that are WARN',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'servicegroup_num_services_ok': {
            'description': 'The number of services in the group that are OK',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'servicegroup_num_services_pending': {
            'description': 'The number of services in the group that are PENDING',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'servicegroup_num_services_unknown': {
            'description': 'The number of services in the group that are UNKNOWN',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'servicegroup_num_services_warn': {
            'description': 'The number of services in the group that are WARN',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'servicegroup_worst_service_state': {
            'description': 'The worst soft state of all of the groups services (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
    },
    'Servicesbyhostgroup': {
        'hostgroup_action_url': {
            'description': 'An optional URL to custom actions or information about the hostgroup',
            'function': lambda item: "",  # REPAIRME
        },
        'hostgroup_alias': {
            'description': 'An alias of the hostgroup',
            'function': lambda item: "",  # REPAIRME
        },
        'hostgroup_members': {
            'description': 'A list of all host names that are members of the hostgroup',
            'function': lambda item: "",  # REPAIRME
            'datatype': list,
        },
        'hostgroup_members_with_state': {
            'description': 'A list of all host names that are members of the hostgroup together with state and has_been_checked',
            'function': lambda item: "",  # REPAIRME
            'datatype': list,
        },
        'hostgroup_name': {
            'description': 'Name of the hostgroup',
            'function': lambda item: "",  # REPAIRME
        },
        'hostgroup_notes': {
            'description': 'Optional notes to the hostgroup',
            'function': lambda item: "",  # REPAIRME
        },
        'hostgroup_notes_url': {
            'description': 'An optional URL with further information about the hostgroup',
            'function': lambda item: "",  # REPAIRME
        },
        'hostgroup_num_hosts': {
            'description': 'The total number of hosts in the group',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_hosts_down': {
            'description': 'The number of hosts in the group that are down',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_hosts_pending': {
            'description': 'The number of hosts in the group that are pending',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_hosts_unreach': {
            'description': 'The number of hosts in the group that are unreachable',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_hosts_up': {
            'description': 'The number of hosts in the group that are up',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services': {
            'description': 'The total number of services of hosts in this group',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_crit': {
            'description': 'The total number of services with the state CRIT of hosts in this group',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_hard_crit': {
            'description': 'The total number of services with the state CRIT of hosts in this group',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_hard_ok': {
            'description': 'The total number of services with the state OK of hosts in this group',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_hard_unknown': {
            'description': 'The total number of services with the state UNKNOWN of hosts in this group',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_hard_warn': {
            'description': 'The total number of services with the state WARN of hosts in this group',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_ok': {
            'description': 'The total number of services with the state OK of hosts in this group',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_pending': {
            'description': 'The total number of services with the state Pending of hosts in this group',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_unknown': {
            'description': 'The total number of services with the state UNKNOWN of hosts in this group',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_num_services_warn': {
            'description': 'The total number of services with the state WARN of hosts in this group',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_worst_host_state': {
            'description': 'The worst state of all of the groups\' hosts (UP <= UNREACHABLE <= DOWN)',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_worst_service_hard_state': {
            'description': 'The worst state of all services that belong to a host of this group (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
        'hostgroup_worst_service_state': {
            'description': 'The worst state of all services that belong to a host of this group (OK <= WARN <= UNKNOWN <= CRIT)',
            'function': lambda item: "",  # REPAIRME
            'datatype': int,
        },
    },
    'Config': {
        'accept_passive_host_checks': {
            'description': 'Whether passive host checks are accepted in general (0/1)',
            'function': lambda item: item["passive_host_checks_enabled"],
            'datatype': bool,
        },
        'accept_passive_service_checks': {
            'description': 'Whether passive service checks are activated in general (0/1)',
            'function': lambda item: item["passive_service_checks_enabled"],
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
            'function': lambda item: item["check_external_commands"],
            'datatype': bool,
        },
        'check_host_freshness': {
            'description': 'Whether host freshness checking is activated in general (0/1)',
            'function': lambda item: item["check_host_freshness"],
            'datatype': bool,
        },
        'check_service_freshness': {
            'description': 'Whether service freshness checking is activated in general (0/1)',
            'function': lambda item: item["check_service_freshness"],
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
            'function': lambda item: item["event_handlers_enabled"],
            'datatype': bool,
        },
        'enable_flap_detection': {
            'description': 'Whether flap detection is activated in general (0/1)',
            'function': lambda item: item["flap_detection_enabled"],
            'datatype': bool,
        },
        'enable_notifications': {
            'description': 'Whether notifications are enabled in general (0/1)',
            'function': lambda item: item["notifications_enabled"],
            'datatype': bool,
        },
        'execute_host_checks': {
            'description': 'Whether host checks are executed in general (0/1)',
            'function': lambda item: item["active_host_checks_enabled"],
            'datatype': bool,
        },
        'execute_service_checks': {
            'description': 'Whether active service checks are activated in general (0/1)',
            'function': lambda item: item["active_service_checks_enabled"],
            'datatype': bool,
        },
        'external_command_buffer_max': {
            'description': 'The maximum number of slots used in the external command buffer',
            'function': lambda item: item["external_command_buffer_max"],  # REPAIRME
            'datatype': int,
        },
        'external_command_buffer_slots': {
            'description': 'The size of the buffer for the external commands',
            'function': lambda item: item["external_command_buffer_slots"],  # REPAIRME
            'datatype': int,
        },
        'external_command_buffer_usage': {
            'description': 'The number of slots in use of the external command buffer',
            'function': lambda item: item["external_command_buffer_usage"],  # REPAIRME
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
            'function': lambda item: item["interval_length"],
            'datatype': int,
        },
        'last_command_check': {
            'description': 'The time of the last check for a command as UNIX timestamp',
            'function': lambda item: item["last_command_check"],  # REPAIRME
            'datatype': int,
        },
        'last_log_rotation': {
            'description': 'Time time of the last log file rotation',
            'function': lambda item: item["last_log_rotation"],  # REPAIRME
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
            'function': lambda item: item["pid"],  # REPAIRME
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
            'function': lambda item: item["obsess_over_hosts"],
            'datatype': bool,
        },
        'obsess_over_services': {
            'description': 'Whether Nagios will obsess over service checks and run the ocsp_command (0/1)',
            'function': lambda item: item["obsess_over_services"],
            'datatype': bool,
        },
        'process_performance_data': {
            'description': 'Whether processing of performance data is activated in general (0/1)',
            'function': lambda item: item["process_performance_data"],
            'datatype': bool,
        },
        'program_start': {
            'description': 'The time of the last program start as UNIX timestamp',
            'function': lambda item: item["program_start"],
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
            'function': lambda item: item["attempt"],
            'datatype': int,
        },
        'class': {
            'description': 'The class of the message as integer (0:info, 1:state, 2:program, 3:notification, 4:passive, 5:command)',
            'function': lambda item: item["logclass"],
            'datatype': int,
        },
        'command_name': {
            'description': 'The name of the command of the log entry (e.g. for notifications)',
            'function': lambda item: item["command_name"],
        },
        'comment': {
            'description': 'A comment field used in various message types',
            'function': lambda item: item["comment"],
        },
        'contact_name': {
            'description': 'The name of the contact the log entry is about (might be empty)',
            'function': lambda item: item["contact_name"],
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
            'function': lambda item: item["host_name"],
        },
        'lineno': {
            'description': 'The number of the line in the log file',
            'function': lambda item: item["lineno"],
            'datatype': int,
        },
        'message': {
            'description': 'The complete message line including the timestamp',
            'function': lambda item: item["message"],
        },
        'options': {
            'description': 'The part of the message after the \':\'',
            # >2.4 'function': lambda item: item.message.partition(":")[2].lstrip(),
            'function': lambda item: item["message"].split(":")[1].lstrip(),
        },
        'plugin_output': {
            'description': 'The output of the check, if any is associated with the message',
            'function': lambda item: item["plugin_output"],
        },
        'service_description': {
            'description': 'The description of the service log entry is about (might be empty)',
            'function': lambda item: item["service_description"],
        },
        'state': {
            'description': 'The state of the host or service in question',
            'function': lambda item: item["state"],
            'datatype': int,
        },
        'state_type': {
            'description': 'The type of the state (varies on different log classes)',
            'function': lambda item: item["state_type"],  # REPAIRME
        },
        'time': {
            'description': 'Time of the log event (UNIX timestamp)',
            'function': lambda item: item["time"],  # REPAIRME
            'datatype': int,
        },
        'type': {
            'description': 'The type of the message (text before the colon), the message itself for info messages',
            'function': lambda item: item["type"],  # REPAIRME
        },
    },
}

# Updates Service, Downtime and Comment classe definitions with HostLink
# and ServiceLink attributes
for class_map in ("Comment", "Downtime", "Service"):
    livestatus_attribute_map[class_map].update(
        livestatus_attribute_map["HostLink"]
    ),
for class_map in ("Comment", "Downtime"):
    livestatus_attribute_map[class_map].update(
        livestatus_attribute_map["ServiceLink"]
    ),
for class_map in ('Host', 'Hostgroup', 'Servicegroup'):
    livestatus_attribute_map[class_map].update(
        livestatus_attribute_map["ServicesLink"]
    ),
for class_map in ('Hostgroup', 'Servicegroup'):
    livestatus_attribute_map[class_map].update(
        livestatus_attribute_map["HostsLink"]
    ),

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

"""Build the new livestatus-methods and add delegate keys for certain attributes.

Some attributes are not directly reachable via prop or
need a complicated depythonize function.
Example: Logline (the objects created for a "GET log" request
have the column current_host_state. The Logline object does
not have an attribute of this name, but a log_host attribute.
The Host object represented by log_host has an attribute state
which is the desired current_host_state. Because it's the same
for all columns starting with current_host, a rule can
be applied that automatically redirects the resolving to the
corresponding object. Instead of creating a complicated
depythonize handler which gets log_host and then state, two new
keys for Logline/current_host_state are added:
delegate = log_host
as = state
This instructs the hook function to first get attribute state of
the object represented by log_host.

"""


def host_redirect_factory(attribute):
    """attribute already comes with lsm_"""
    return lambda item, req: getattr(item.host, attribute)(req),


def ref_redirect_factory(attribute):
    return lambda item, req: getattr(item.ref, attribute)(req),


def log_service_redirect_factory(attribute):
    return lambda item, req: getattr(item.log_service, attribute)(req),


def log_host_redirect_factory(attribute):
    return lambda item, req: getattr(item.log_host, attribute)(req),


def log_contact_redirect_factory(attribute):
    return lambda item, req: getattr(item.log_contact, attribute)(req),


def hostgroup_redirect_factory(attribute):
    return lambda item, req: getattr(item.hostgroup, attribute)(req),


def servicegroup_redirect_factory(attribute):
    return lambda item, req: getattr(item.servicegroup, attribute)(req),


def catchall_factory(name, req):
    def method(*args):
        logger.info("[Livestatus Broker Mapping] Tried to handle unknown method %s" % name),
        if args:
            logger.info("[Livestatus Broker Mapping] It had arguments: %s" % str(args)),
    return method


#print "FINISHING THE ATTRIBUTE MAPPING>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
#for objtype in ['Host', 'Service', 'Contact', 'Command', 'Timeperiod', 'Downtime', 'Comment', 'Hostgroup', 'Servicegroup', 'Contactgroup', 'SchedulerLink', 'PollerLink', 'ReactionnerLink', 'BrokerLink', 'Problem', 'Logline', 'Config']:
for objtype in []:
    cls = [t[1] for t in table_class_map.values() if t[0] == objtype][0]
    setattr(cls, 'livestatus_attributes', []),
    for attribute in livestatus_attribute_map[objtype]:
        entry = livestatus_attribute_map[objtype][attribute]
        if 'function' in entry:
            setattr(cls, 'lsm_'+attribute, entry['function']),
            if 'datatype' in entry:
                #getattr(cls, 'lsm_'+attribute).im_func.datatype = entry['datatype']
                getattr(cls, 'lsm_'+attribute).im_func.datatype = entry['datatype']
            elif attribute.startswith('num_'):
                # With this, we don't need to explicitly set int datatype for attributes like num_services_hard_state_ok
                getattr(cls, 'lsm_'+attribute).im_func.datatype = int
            else:
                getattr(cls, 'lsm_'+attribute).im_func.datatype = str
        elif objtype == 'Service' and attribute.startswith('host_'):
            # Service,host_address -> Service.lsm_host_address -> Host.lsm_address
            setattr(cls, 'lsm_'+attribute, host_redirect_factory('lsm_'+attribute.replace('host_', ''))),
            # Service.lsm_host_address.datatype = Host.lsm_address.datatype
            getattr(cls, 'lsm_'+attribute).im_func.datatype = getattr(Host, 'lsm_'+attribute.replace('host_', '')).datatype
        elif (objtype == 'Comment' or objtype == 'Downtime') and attribute.startswith('host_'):
            # Downtime,host_address -> Downtime.lsm_host_address -> "Ref".lsm_host_address
            #   ref is a host: Host.lsm_host_address works, because all lsm_* also exist as lsm_host_*
            #   ref is a service: Service.lsm_host_address works, because it's delegated to the service's host
            setattr(cls, 'lsm_'+attribute, ref_redirect_factory('lsm_'+attribute)),
            getattr(cls, 'lsm_'+attribute).im_func.datatype = getattr(Host, 'lsm_'+attribute).datatype
        elif (objtype == 'Comment' or objtype == 'Downtime') and attribute.startswith('service_'):
            # Downtime,service_state -> Downtime.lsm_service_state -> "Ref".lsm_state
            #   ref is a host: Host.lsm_state works, although it is wrong. other service-only attributes return 0
            #   ref is a service: Service.lsm_state works
            setattr(cls, 'lsm_'+attribute, ref_redirect_factory('lsm_'+attribute.replace('service_', ''))),
            getattr(cls, 'lsm_'+attribute).im_func.datatype = getattr(Service, 'lsm_'+attribute.replace('service_', '')).datatype
        elif objtype == 'Logline' and attribute.startswith('current_service_'):
            setattr(cls, 'lsm_'+attribute, log_service_redirect_factory('lsm_'+attribute.replace('current_service_', ''))),
            getattr(cls, 'lsm_'+attribute).im_func.datatype = getattr(Service, 'lsm_'+attribute.replace('current_service_', '')).datatype
        elif objtype == 'Logline' and attribute.startswith('current_host_'):
            setattr(cls, 'lsm_'+attribute, log_host_redirect_factory('lsm_'+attribute.replace('current_host_', ''))),
            getattr(cls, 'lsm_'+attribute).im_func.datatype = getattr(Host, 'lsm_'+attribute.replace('current_host_', '')).datatype
        elif objtype == 'Logline' and attribute.startswith('current_contact_'):
            setattr(cls, 'lsm_'+attribute, log_contact_redirect_factory('lsm_'+attribute.replace('current_contact_', ''))),
            getattr(cls, 'lsm_'+attribute).im_func.datatype = getattr(Contact, 'lsm_'+attribute.replace('current_contact_', '')).datatype
        else:
            pass
            # let the lambda return a default value
            # setattr(cls, 'lsm_'+attribute, lambda item, req: 0),
            # getattr(cls, 'lsm_'+attribute).im_func.datatype =?
        # _Every_ attribute _must_ have a description
        getattr(cls, 'lsm_'+attribute).im_func.description = entry['description']
    if objtype == 'Host':
        # for every lsm_* there is also a lsm_host_*
        for attribute in livestatus_attribute_map['Host']:
            setattr(cls, 'lsm_host_'+attribute, getattr(cls, 'lsm_'+attribute)),
            getattr(cls, 'lsm_host_'+attribute).im_func.description = getattr(cls, 'lsm_'+attribute).im_func.description
            getattr(cls, 'lsm_host_'+attribute).im_func.datatype = getattr(cls, 'lsm_'+attribute).im_func.datatype
        # this is for "GET downtimes\nFilter: service_description !=\n" which is used to fetch host-downtimes
        setattr(cls, 'lsm_description', lambda item, ref: ''),

#for objtype in ['Host', 'Service']:
for objtype in []:
    cls = [t[1] for t in table_class_map.values() if t[0] == objtype][0]
    if objtype == 'Host':
        # in LivestatusQuery.get_group_livedata, (copied) Host objects get an extra "hostgroup" attribute
        # and Service objects get an extra "servicegroup" attribute. Here we set the lsm-attributes for them
        for attribute in livestatus_attribute_map['Hostgroup']:
            setattr(cls, 'lsm_hostgroup_'+attribute, hostgroup_redirect_factory('lsm_'+attribute.replace('hostgroup_', ''))),
            getattr(cls, 'lsm_hostgroup_'+attribute).im_func.description = getattr(Hostgroup, 'lsm_'+attribute).im_func.description
            getattr(cls, 'lsm_hostgroup_'+attribute).im_func.datatype = getattr(Hostgroup, 'lsm_'+attribute).im_func.datatype
    if objtype == 'Service':
        for attribute in livestatus_attribute_map['Servicegroup']:
            setattr(cls, 'lsm_servicegroup_'+attribute, servicegroup_redirect_factory('lsm_'+attribute.replace('servicegroup_', ''))),
            getattr(cls, 'lsm_servicegroup_'+attribute).im_func.description = getattr(Servicegroup, 'lsm_'+attribute).im_func.description
            getattr(cls, 'lsm_servicegroup_'+attribute).im_func.datatype = getattr(Servicegroup, 'lsm_'+attribute).im_func.datatype
        # in LivestatusQuery.get_service_by_hostgroup, (copied) Service objects get an extra "hostgroup" attribute
        # and Service objects get an extra "servicegroup" attribute. Here we set the lsm-attributes for them
        for attribute in livestatus_attribute_map['Hostgroup']:
            setattr(cls, 'lsm_hostgroup_'+attribute, hostgroup_redirect_factory('lsm_'+attribute.replace('hostgroup_', ''))),
            getattr(cls, 'lsm_hostgroup_'+attribute).im_func.description = getattr(Hostgroup, 'lsm_'+attribute).im_func.description
            getattr(cls, 'lsm_hostgroup_'+attribute).im_func.datatype = getattr(Hostgroup, 'lsm_'+attribute).im_func.datatype

# Finally set some default values for the different datatypes
#for objtype in ['Host', 'Service', 'Contact', 'Command', 'Timeperiod', 'Downtime', 'Comment', 'Hostgroup', 'Servicegroup', 'Contactgroup', 'SchedulerLink', 'PollerLink', 'ReactionnerLink', 'BrokerLink', 'Problem', 'Logline', 'Config']:
for objtype in []:
    cls = [t[1] for t in table_class_map.values() if t[0] == objtype][0]
    for attribute in livestatus_attribute_map[objtype]:
        entry =  livestatus_attribute_map[objtype][attribute]
        if not hasattr(getattr(cls, 'lsm_'+attribute).im_func, 'datatype'):
            getattr(cls, 'lsm_'+attribute).im_func.default = 0
        elif getattr(cls, 'lsm_'+attribute).im_func.datatype == int:
            getattr(cls, 'lsm_'+attribute).im_func.default = 0
        elif getattr(cls, 'lsm_'+attribute).im_func.datatype == float:
            getattr(cls, 'lsm_'+attribute).im_func.default = 0.0
        elif getattr(cls, 'lsm_'+attribute).im_func.datatype == str:
            getattr(cls, 'lsm_'+attribute).im_func.default = ''
        elif getattr(cls, 'lsm_'+attribute).im_func.datatype == list:
            getattr(cls, 'lsm_'+attribute).im_func.default = []
        elif getattr(cls, 'lsm_'+attribute).im_func.datatype == bool:
            getattr(cls, 'lsm_'+attribute).im_func.default = False

#for objtype in ['Host', 'Service', 'Contact', 'Command', 'Timeperiod', 'Downtime', 'Comment', 'Hostgroup', 'Servicegroup', 'Contactgroup', 'SchedulerLink', 'PollerLink', 'ReactionnerLink', 'BrokerLink', 'Problem', 'Logline', 'Config']:
for objtype in []:
    cls = [t[1] for t in table_class_map.values() if t[0] == objtype][0]
    cls.lsm_columns = []
    for attribute in sorted([x for x in livestatus_attribute_map[objtype]]):
        cls.lsm_columns.append(attribute),

#print "FINISHED THE ATTRIBUTE MAPPING<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

def find_filter_converter(table, attribute, reverse=False):
    """Return a function which converts a string to the attribute's data type"""

    tableclass = table_class_map[table][1]
    # attribute already has a lsm-prefix
    function = getattr(tableclass, attribute, None),
    if function == None:
        return None
    else:
        datatype = getattr(function, 'datatype', None),
        if datatype == None:
            return None
        elif datatype == str:
            return None
        elif datatype == int:
            return int
        elif datatype == float:
            return float
        elif datatype == bool:
            return lambda string: string != "0"
        elif datatype == list:
            return None
        else:
            return None


def list_livestatus_attributes(table):
    return sorted(livestatus_attribute_map[table].keys()),
