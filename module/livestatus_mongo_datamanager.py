#!/usr/bin/python

# -*- coding: utf-8 -*-

# Copyright (C) 2009-2014:
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

from shinken.util import safe_print
from shinken.misc.sorter import hst_srv_sort, last_state_change_earlier
from shinken.misc.filter import only_related_to
from mongo_mapping import table_class_map, find_filter_converter, list_livestatus_attributes, Problem
from livestatus_query_error import LiveStatusQueryError
from pprint import pprint
import pymongo
import re

class DataManager(object):
    def __init__(self):
        self.db = None

    def load(self, db):
        self.db = db

    def normalize(self, obj):
        if hasattr(obj, "get_full_name"):
            return obj.get_full_name()
        elif hasattr(obj, "get_name"):
            return obj.get_name()
        elif isinstance(obj, list):
            return [self.normalize(o) for o in obj]
        elif isinstance(obj, dict):
            return dict([(k, self.normalize(v)) for k, v in obj.items()])
        else:
            return obj

    def manage_brok(self, brok):
        """
        Manages a received brok

        :param Brok brok: The brok to manage
        """
        handler_name = "manage_%s_brok" % brok.type
        handler = getattr(self, handler_name, None)
        if handler is not None:
            handler(brok)

    def manage_program_status_brok(self, brok):
        """
        Display brok content

        :param Brok brok: The brok object to update object from
        """
        print("Brok: %s" % brok.type)
        pprint(brok.data)

    def manage_initial_host_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        # Manages some brok format curiosities
        # Hostgroups transformation into list
        hg = brok.data.get("hostgroups")
        if hg is not None and not isinstance(hg, list):
            brok.data["hostgroups"] = [
                n.strip() for n in hg.split(',') if n.strip()
            ]
        self.update_object("host", brok)

    def manage_initial_hostgroup_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        # Manages some brok format curiosities
        # Hostgroup members
        members = brok.data.get("members")
        if members is not None:
            brok.data["members"] = [
                m[1] for m in members
            ]
        self.update_object("hostgroup", brok)

    def manage_initial_service_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        # Manages some brok format curiosities
        # Servicegroups transformation into list
        sg = brok.data.get("servicegroups")
        if sg is not None and not isinstance(sg, list):
            brok.data["servicegroups"] = [
                n.strip() for n in sg.split(',') if n.strip()
            ]
        self.update_object("service", brok)

    def manage_initial_servicegroup_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("servicegroup", brok)

    def manage_initial_contact_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("contact", brok)

    def manage_initial_contactgroup_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("contactgroup", brok)

    def manage_initial_timeperiod_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("timeperiod", brok)

    def manage_initial_command_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("command", brok)

    def manage_initial_scheduler_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("scheduler", brok)

    def manage_initial_poller_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("poller", brok)

    def manage_initial_reactionner_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("reactionner", brok)

    def manage_initial_broker_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("broker", brok)

    def manage_initial_receiver_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("receiver", brok)

    def manage_initial_broks_done_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        print("Brok: %s" % brok.type)
        pprint(brok.data)
        # Builds cross objects references
        # Hostgroups -> hosts (members)
        # Hostgroups -> services (members_hosts)
        # Hostgroups -> services (members_services)
        # Hostgroups -> contacts (contacts)
        services_hg = {}
        for hg in self.db.hostgroups.find(projection={'_id': 1}):
            group_name = hg["_id"]
            members = []
            members_services = []
            contacts = []
            hosts = self.db.hosts.aggregate([
                {"$match": {"hostgroups": {"$in": [group_name]}}},
                {
                    "$lookup": {
                        'from': 'services',
                        'as': '__services__',
                        'localField': 'host_name',
                        'foreignField': 'host_name',
                    }
                },
                {
                    "$project": {
                        '_id': 1,
                        'contacts': 1,
                        'host_name': 1,
                        '__services__._id': 1,
                        '__services__.contacts': 1,
                    }
                },
            ])

            for host in hosts:
                members.append(host["_id"])
                contacts.extend(host.get("contacts", []))
                for service in host["__services__"]:
                    svc_id = service["_id"]
                    contacts.extend(service.get("contacts", []))
                    # Registers hostgroup intto the service
                    services_hg.setdefault(svc_id, []).append(group_name)
            members_services = list(set(members_services))
            contacts = list(set(contacts))
            self.db.hostgroups.update(
                {"_id": group_name},
                {
                    "$set": {
                        "members": members,
                        "contacts": contacts
                    }
                }
            )
        for svc_id, hostgroups in services_hg.items():
            self.db.services.update(
                {"_id": svc_id},
                {"$set": {"hostgroups": list(set(hostgroups))}},
            )

        # Servicegroups -> services (members)
        # Servicegroups -> services (members_hosts)
        # Servicegroups -> services (members_services)
        # Servicegroups -> contacts (contacts)
        hosts_sg = {}
        for sg in self.db.servicegroups.find(projection={'_id': 1}):
            group_name = sg["_id"]
            members = []
            members_hosts = []
            contacts = []
            services = self.db.services.aggregate([
                {"$match": {"servicegroups": {"$in": [group_name]}}},
                {
                    "$lookup": {
                        'from': 'hosts',
                        'as': '__hosts__',
                        'localField': 'host_name',
                        'foreignField': 'host_name',
                    }
                },
                {
                    "$project": {
                        '_id': 1,
                        'contacts': 1,
                        'host_name': 1,
                        '__hosts__.contacts': 1,
                    }
                },
            ])
            for service in services:
                members.append(service["_id"])
                contacts.extend(service.get("contacts", []))
                members_hosts.append(service["host_name"])
                hname = service["host_name"]
                hosts_sg.setdefault(hname, []).append(group_name)
                for host in service["__hosts__"]:
                    contacts.extend(host.get("contacts", []))
                    # Registers serviecgroup intto the host
            members = list(set(members))
            contacts = list(set(contacts))
            self.db.servicegroups.update(
                {"_id": group_name},
                {
                    "$set": {
                        "members": members,
                        "contacts": contacts,
                    },
                }
            )
        for hst_id, servicegroups in hosts_sg.items():
            self.db.hosts.update(
                {"_id": hst_id},
                {"$set": {"servicegroups": list(set(servicegroups))}},
            )

    def manage_update_program_status_brok(self, brok):
        """
        Display brok content

        :param Brok brok: The brok object to update object from
        """
        print("Brok: %s" % brok.type)
        pprint(brok.data)

    def manage_update_host_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        # Manages some brok format curiosities
        # Hostgroups transformation into list
        hg = brok.data.get("hostgroups")
        if hg is not None and not isinstance(hg, list):
            brok.data["hostgroups"] = [
                n.strip() for n in hg.split(',') if n.strip()
            ]
        self.update_object("host", brok)

    def manage_update_service_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        # Manages some brok format curiosities
        # Servicegroups transformation into list
        sg = brok.data.get("servicegroups")
        if sg is not None and not isinstance(sg, list):
            brok.data["servicegroups"] = [
                n.strip() for n in sg.split(',') if n.strip()
            ]
        self.update_object("service", brok)

    def manage_update_broker_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("broker", brok)

    def manage_update_receiver_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("receiver", brok)

    def manage_update_reactionner_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("reactionner", brok)

    def manage_update_poller_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("poller", brok)

    def manage_update_scheduler_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("scheduler", brok)

    def manage_host_check_result_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("host", brok)

    def manage_host_next_schedule_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("host", brok)

    def manage_service_check_result_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("service", brok)

    def manage_service_next_schedule_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("service", brok)

    def update_object(self, object_type, brok):
        """
        Updates and object in the database from the brok data

        :param str objct_type: The object type
        :param Brok brok: The brok object to update object from
        """
        # Parses brok
        if brok.data.get("host_name") == "test_host_005":
            if "host" in brok.type:
                print("Brok type: %s" % brok.type)
                pprint(brok.data)
            elif "service" in brok.type and \
                    brok.data.get("service_description") == "test_ok_00":
                print("Brok type: %s" % brok.type)
                pprint(brok.data)
        data = {}
        for name, value in brok.data.items():
            if name == "dateranges":
                continue
            else:
                data[name] = self.normalize(value)
        # Insert brok into database
        # Services are particular because their name is a combination of
        # host_name and service_description
        if object_type == "service":
            object_name = "%s/%s" % (
                data["host_name"],
                data["service_description"]
            )
        else:
            object_name = data["%s_name" % object_type]
        data["_id"] = object_name
        collection = getattr(self.db, "%ss" % object_type)
        collection.update(
            {"_id": object_name},
            {"$set": data},
            upsert=True
        )

    def make_stack(self):
        """
        Builds a stack to add filters to
        """
        return []

    def get_column_attribute(self, table, attribute, raise_error=True):
        """
        Return the attribute name to use to query the mongo database.

        Some attribute hold different names when requested through LQL, and
        queried in mongo. Return the suitable attribute for Mongo query
        from LQL.

        :param str table: The table the attribute is in
        :param str attribute: The LQL requested attribute
        :param bool raise_error: A flag indicating if an error should be risen
                                 when an attribute is not usable as filter
        :rtype: str
        :return: The attribute name to use in mongo query
        """
        print("get_column_attribute(): table: %s" % table)
        mapping = table_class_map[table][attribute]
        # Special case, if mapping is {}, no filtering is supported on this
        # attribute
        if "filters" in mapping and mapping["filters"] == {} and raise_error:
            raise LiveStatusQueryError(452, "can't filter on attribute %s" % attribute)
        return mapping.get("filters", {}).get("attr", attribute)

    def get_column_datatype(self, table, attribute):
        """
        Returns the attribute type, as shown in object mapping

        :param str attribute: The LQL requested attribute
        :param str table: The table the attribute is in
        :rtype: type
        :return: The attribute type
        """
        return table_class_map[table][attribute].get("datatype")

    def add_filter_eq(self, stack, table, attribute, reference, ignore_type=False):
        """
        Transposes an equalitiy operator filter into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        attrtype = self.get_column_datatype(table, attribute)
        if attrtype is list and ignore_type is False:
            stack.append({
                attrname: []
            })
        elif attrtype is not None and ignore_type is False:
            stack.append({
                attrname: {
                    "$eq": attrtype(reference)
                }
            })
        else:
            stack.append({
                attrname: {
                    "$eq": reference
                }
            })

    def add_filter_eqeq(self, stack, table, attribute, reference, ignore_type=False):
        """
        Transposes a generic equalitiy operator filter into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        stack.append({
            attrname: {
                "$eq": reference
            }
        })

    def add_filter_eq_ci(self, stack, table, attribute, reference):
        """
        Transposes a case insensitive equalitiy operator filter into a mongo
        query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        attrtype = self.get_column_datatype(table, attribute)
        if attrtype is list:
            raise LiveStatusQueryError(452, 'operator not available for lists')
        # Builds regular expression
        reg = "^%s$" % reference
        stack.append({
            attrname: re.compile(reg, re.IGNORECASE)
        })

    def add_filter_reg(self, stack, table, attribute, reference):
        """
        Transposes a regex match operator filter into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        attrtype = self.get_column_datatype(table, attribute)
        # Builds regular expression
        reg = str(reference)
        if attrtype is list:
            stack.append({
                attrname: {
                    "$in": [re.compile(reg)]
                }
            })
        else:
            stack.append({
                attrname: re.compile(reg)
            })

    def add_filter_reg_ci(self, stack, table, attribute, reference):
        """
        Transposes a case insensitive regex match operator filter into a mongo
        query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        attrtype = self.get_column_datatype(table, attribute)
        # Builds regular expression
        reg = str(reference)
        if attrtype is list:
            stack.append({
                attrname: {
                    "$in": [
                        re.compile(reg, re.IGNORECASE)
                    ]
                }
            })
        else:
            stack.append({
                attrname: re.compile(reg, re.IGNORECASE)
            })

    def add_filter_lt(self, stack, table, attribute, reference):
        """
        Transposes a lower than operator filter into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        attrtype = self.get_column_datatype(table, attribute)
        if attrtype is list:
            stack.append({
                attrname: {
                    "$nin": [reference]
                }
            })
        else:
            stack.append({
                attrname: {"$lt": reference}
            })

    def add_filter_le(self, stack, table, attribute, reference):
        """
        Transposes a lower than or equal operator filter into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        attrtype = self.get_column_datatype(table, attribute)
        if attrtype is list:
            # Builds regular expression
            reg = "^%s$" % reference
            stack.append({
                attrname: {
                    "$in": [re.compile(reg, re.IGNORECASE)]
                }
            })
        elif attrtype is not None:
            stack.append({
                attrname: {"$lte": attrtype(reference)}
            })
        else:
            stack.append({
                attrname: {"$lte": reference}
            })

    def add_filter_gt(self, stack, table, attribute, reference):
        """
        Transposes a lower than operator filter into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        attrtype = self.get_column_datatype(table, attribute)
        if attrtype is list:
            # Builds regular expression
            reg = "^%s$" % reference
            stack.append({
                attrname: {
                    "$nin": [re.compile(reg, re.IGNORECASE)]
                }
            })
        elif attrtype is not None:
            stack.append({
                attrname: {"$gt": attrtype(reference)}
            })
        else:
            stack.append({
                attrname: {"$gt": reference}
            })

    def add_filter_ge(self, stack, table, attribute, reference):
        """
        Transposes a greater than or equal operator filter into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        attrtype = self.get_column_datatype(table, attribute)
        if attrtype is list:
            stack.append({
                attrname: {"$in": [reference]}
            })
        elif attrtype is not None:
            stack.append({
                attrname: {"$gte": attrtype(reference)}
            })
        else:
            stack.append({
                attrname: {"$gte": reference}
            })

    def add_filter_in(self, stack, table, attribute, reference):
        """
        Transposes an in operator filter into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        stack.append({
            attrname: {"$in": [reference]}
        })

    def add_filter_not_eq(self, stack, table, attribute, reference):
        """
        Transposes a not equal  operator filter into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        attrtype = self.get_column_datatype(table, attribute)
        if attrtype is list:
            stack.append({
                attrname: {"$ne": []}
            })
        elif attrtype is not None:
            stack.append({
                attrname: {"$ne": attrtype(reference)}
            })
        else:
            stack.append({
                attrname: {"$ne": reference}
            })

    def add_filter_not_eq_ci(self, stack, table, attribute, reference):
        """
        Transposes a case insensitive not equal operator filter into a mongo
        query

        Before MongoDB version 4.0.7, $not does not support $regex
        This, using bson.regex.Regex regular expressions is required

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        attrtype = self.get_column_datatype(table, attribute)
        if attrtype is list:
            raise LiveStatusQueryError(452, 'operator not available for lists')
        # Builds regular expression
        reg = "^%s$" % reference
        stack.append({
            attrname: {
                "$not": re.compile(reg, re.IGNORECASE)
            }
        })

    def add_filter_not_reg(self, stack, table, attribute, reference):
        """
        Transposes a regex not match operator filter into a mongo query

        Before MongoDB version 4.0.7, $not does not support $regex
        This, using bson.regex.Regex regular expressions is required

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        attrtype = self.get_column_datatype(table, attribute)
        # Builds regular expression
        reg = str(reference)
        if attrtype is list:
            stack.append({
                attrname: {
                    "$nin": [re.compile(reg)]
                }
            })
        else:
            stack.append({
                attrname: {"$not": re.compile(reg)}
            })

    def add_filter_not_reg_ci(self, stack, table, attribute, reference):
        """
        Transposes a case insensitive regex not match operator filter into a
        mongo query

        Before MongoDB version 4.0.7, $not does not support $regex
        This, using bson.regex.Regex regular expressions is required

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        attrname = self.get_column_attribute(table, attribute)
        attrtype = self.get_column_datatype(table, attribute)
        # Builds regular expression
        reg = str(reference)
        if attrtype is list:
            stack.append({
                attrname: {
                    "$nin": [re.compile(reg, re.IGNORECASE)]
                }
            })
        else:
            stack.append({
                attrname: {
                    "$not": re.compile(reg, re.IGNORECASE)
                }
            })

    def add_filter_dummy(self, stack, table, attribute, reference):
        """
        Transposes a dummy (always true) operator filter into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        stack.append({})

    def add_filter_user(self, stack, attribute, username):
        """
        Add a filter limitting the output to hosts/services having the
        username as contact.

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str username: The username to limit output to
        """
        stack.append({
            attribute: {
                "$in": [str(username)]
            }
        })

    grouping_tables = {
        "hostsbygroup": "hostgroups",
        "servicesbygroup": "servicegroups",
        "servicesbyhostgroup": "hostgroups",
    }

    def add_aggregation_sum(self, stack, table, attribute, columns=None):
        """
        Transposes a stats sum aggregation into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param list columns: The columns to group by stats
        """
        print("add_aggregation_sum(): columns: %s" % columns)
        attrname = self.get_column_attribute(table, attribute)
        if table in self.grouping_tables and columns is None:
            columns = [self.grouping_tables[table]]
        if columns:
            groupby = {}
            for column in columns:
                groupby_attr = self.get_column_attribute(table, column)
                groupby[column] = groupby_attr
            # Build grouping query
            groupby_expr = dict([
                (a, "$%s" % a) for a in groupby.values()
            ])
        else:
            groupby_expr = None
        query = [
            {
                "$group": {
                    "_id": groupby_expr,
                    "result": {
                        "$sum": "$%s" % attrname
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "result": 1,
                    "group": "$_id"
                }
            }
        ]
        # Appends query to stack
        stack.append(query)

    def add_aggregation_max(self, stack, table, attribute, columns=None):
        """
        Transposes a stats max aggregation into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param list columns: The columns to group by stats
        """
        print("add_aggregation_max(): columns: %s" % columns)
        attrname = self.get_column_attribute(table, attribute)
        if table in self.grouping_tables and columns is None:
            columns = [self.grouping_tables[table]]
        if columns:
            groupby = {}
            for column in columns:
                groupby_attr = self.get_column_attribute(table, column)
                groupby[column] = groupby_attr
            # Build grouping query
            groupby_expr = dict([
                (a, "$%s" % a) for a in groupby.values()
            ])
        else:
            groupby_expr = None
        query = [
            {
                "$group": {
                    "_id": groupby_expr,
                    "result": {
                        "$max": "$%s" % attrname
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "result": 1,
                    "group": "$_id"
                }
            }
        ]
        # Appends query to stack
        stack.append(query)

    def add_aggregation_min(self, stack, table, attribute, columns=None):
        """
        Transposes a stats min aggregation into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param list columns: The columns to group by stats
        """
        print("add_aggregation_min(): columns: %s" % columns)
        attrname = self.get_column_attribute(table, attribute)
        if table in self.grouping_tables and columns is None:
            columns = [self.grouping_tables[table]]
        if columns:
            groupby = {}
            for column in columns:
                groupby_attr = self.get_column_attribute(table, column)
                groupby[column] = groupby_attr
            # Build grouping query
            groupby_expr = dict([
                (a, "$%s" % a) for a in groupby.values()
            ])
        else:
            groupby_expr = None
        query = [
            {
                "$group": {
                    "_id": groupby_expr,
                    "result": {
                        "$min": "$%s" % attrname
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "result": 1,
                    "group": "$_id"
                }
            }
        ]
        # Appends query to stack
        stack.append(query)

    def add_aggregation_avg(self, stack, table, attribute, columns=None):
        """
        Transposes a stats average aggregation into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param list columns: The columns to group by stats
        """
        print("add_aggregation_avg(): columns: %s" % columns)
        attrname = self.get_column_attribute(table, attribute)
        if table in self.grouping_tables and columns is None:
            columns = [self.grouping_tables[table]]
        if columns:
            groupby = {}
            for column in columns:
                groupby_attr = self.get_column_attribute(table, column)
                groupby[column] = groupby_attr
            # Build grouping query
            groupby_expr = dict([
                (a, "$%s" % a) for a in groupby.values()
            ])
        else:
            groupby_expr = None
        query = [
            {
                "$group": {
                    "_id": groupby_expr,
                    "result": {
                        "$avg": "$%s" % attrname
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "result": 1,
                    "group": "$_id"
                }
            }
        ]
        # Appends query to stack
        stack.append(query)

    def add_aggregation_count(self, stack, table, attribute=None, columns=None):
        """
        Transposes a stats count aggregation into a mongo query

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param str attribute: The attribute name to compare
        :param list columns: The columns to group by stats
        """
        print("add_aggregation_count(): columns: %s" % columns)
        if table in self.grouping_tables and columns is None:
            columns = [self.grouping_tables[table]]
        if columns:
            groupby = {}
            for column in columns:
                groupby_attr = self.get_column_attribute(table, column)
                groupby[column] = groupby_attr
            # Build grouping query
            groupby_expr = dict([
                (a, "$%s" % a) for a in groupby.values()
            ])
        else:
            groupby_expr = None
        query = [
            {
                "$group": {
                    "_id": groupby_expr,
                    "result": {
                        "$sum": 1
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "result": 1,
                    "group": "$_id"
                }
            }
        ]
        # Appends query to stack
        stack.append(query)

    def stack_filter_and(self, stack, table, count):
        """
        Stacks the last `count` operations into an `and` group

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param int count: The number of statements to stack
        """
        if len(stack) < count:
            raise LiveStatusQueryError(452, 'No enough filters to stack into `and`')
        and_filter = {
            "$and": stack[-count:]
        }
        del stack[-count:]
        stack.append(and_filter)

    def stack_filter_or(self, stack, table, count):
        """
        Stacks the last `count` operations into an `or` group

        :param list stack: The stack to append filter to
        :param str table: The table the attribute is in
        :param int count: The number of statements to stack
        """
        if len(stack) < count:
            raise LiveStatusQueryError(452, 'No enough filters to stack into `or`')
        or_filter = {
            "$or": stack[-count:]
        }
        del stack[-count:]
        stack.append(or_filter)

    def stack_filter_negate(self, stack, count, wrap=True):
        """
        Inverts the logic of the previous filters stack

        As there's no global $not operator in MongoDB query ($not can only
        be applied to an attribute), we're forced to negate by inverting
        the query logic itself.

        :param list stack: The stack to append filter to
        :param int count: The number of statements to negate
        :param bool wrap: Should the result be wrapped in an "$or"
        """
        if not count:
            count = len(stack)
        if len(stack) < count:
            raise LiveStatusQueryError(452, 'No enough filters to stack into `negate`')
        # Negates each element in the stack
        for i in range(len(stack)-count, len(stack)):
            statement = stack[i]
            if isinstance(statement, list):
                raise LiveStatusQueryError(452, 'Cannot negate aggregation stats')
            stack[i] = self.stack_filter_negate_statement(statement)
        if wrap is True:
            reversed_stack = list(stack[-count:])
            del stack[-count:]
            stack.append({
                "$or": reversed_stack
            })
        return stack

    def stack_filter_negate_statement(self, statement):
        """
        Inverts the logic of a single statement

        As there's no global $not operator in MongoDB query ($not can only
        be applied to an attribute), we're forced to negate by inverting
        the query logic itself.

        :param dict statement: The statement to negate
        :rtype: dict
        :return: The negated statement
        """
        reversed_operators = {
            "$eq": "$ne",
            "$ne": "$eq",
            "$gt": "$le",
            "$le": "$gt",
            "$ge": "$lt",
            "$lt": "$ge",
            "$in": "$nin",
            "$nin": "$in",
            "$or": "$and",
            "$and": "$or",
        }
        for attribute, comparator in list(statement.items()):
            if attribute in ("$and", "$or"):
                # Manages $and, $or, and other grouping statements
                # Statement has pattern: {"$or": [...]} or {"$and": [...]}
                # $or becomes $and and conversely
                reversed_operator = reversed_operators[attribute]
                stack = list(statement[attribute])
                # There can't both $and or $or with another operartor
                # Returning the value directly
                return {
                    reversed_operator: self.stack_filter_negate(
                        stack=stack,
                        count=len(stack),
                        wrap=False
                    )
                }
            # Statement has pattern: {field: comparator}
            if isinstance(comparator, dict):
                # Statement has pattern: {field: {"$eq": value}}
                # {"$eq": value} becomes {"$ne": value} and so on...
                for operator, value in list(comparator.items()):
                    if operator == "$not":
                        # Statement has pattern: {field: {"$not": value}}
                        # {field: {"$not": value}} becomes {field: value}
                        statement[attribute] = value
                        break
                    if operator not in reversed_operators:
                        raise LiveStatusQueryError(452, 'Cannot negate statement %s' % statement)
                    reversed_operator = reversed_operators[operator]
                    del comparator[operator]
                    comparator[reversed_operator] = value
            else:
                # Statement has pattern: {field: value}
                # {field: value} becomes {field: {"$not": value}}
                statement[attribute] = {
                    "$not": statement[attribute]
                }
        return statement

    def get_mongo_column_projection(self, table, column):
        """
        Return the attribute projection for the given column

        Some attribute hold different names when requested through LQL, and
        queried in mongo. Return the suitable attribute for Mongo query
        from LQL.

        :param str table: The table name
        :param str column: The LQL requested column
        :rtype: str
        :return: The attribute name to use in mongo query
        """
        mapping = table_class_map[table][column]
        projection = mapping.get(
            "projection",
            self.get_column_attribute(table, column, False)
        )
        if isinstance(projection, list):
            return projection
        else:
            return [projection]

    def get_mongo_columns_projection(self, table, columns):
        """
        Generates the projection dictionnary from the table and requested
        columns

        :param str table: The table name
        :param list columns: The requested columns
        :rtype: dict
        :return: The projection dictionnary
        """
        projection = ["_id"]
        for column in columns:
            projection.extend(
                self.get_mongo_column_projection(table, column)
            )
        projection = list(set(projection))
        return dict(
            [(p, 1) for p in projection]
        )

    def get_mongo_lookup_hosts(self, pipeline, projection):
        """
        Adds cross collections $lookup stage to the pipeline if columns
        require access to child objects attributes.

        :param list pipeline: The mongo pipeline to update
        :param list projection: The
        """
        # If at least one attribtue from the service is requested, add
        # the $lookup pipeline stage
        if not projection or any([p.startswith("__services__") for p in projection]):
            return [
                {
                    "$lookup": {
                        "from": "services",
                        "localField": "host_name",
                        "foreignField": "host_name",
                        "as": "__services__",
                    },
                }
            ]
        else:
            return []

    def get_mongo_lookup_services(self, pipeline, projection):
        """
        Adds cross collections $lookup stage to the pipeline if columns
        require access to child objects attributes.

        :param list pipeline: The mongo pipeline to update
        :param list projection: The
        """
        # If at least one attribtue from the service is requested, add
        # the $lookup pipeline stage
        if not projection or any([p.startswith("__host__") for p in projection]):
            return [
                {
                    "$lookup": {
                        "from": "hosts",
                        "localField": "host_name",
                        "foreignField": "host_name",
                        "as": "__host__",
                    },
                },
                {"$unwind": "$__host__"},
            ]
        else:
            return []

    def get_mongo_lookup_hostgroups(self, pipeline, projection):
        """
        Adds cross collections $lookup stage to the pipeline if columns
        require access to child objects attributes.

        :param list pipeline: The mongo pipeline to update
        :param list projection: The
        """
        # If at least one attribtue from the service is requested, add
        # the $lookup pipeline stage
        lookup = []
        if not projection or any([p.startswith("__hosts__") for p in projection]):
            lookup.append({
                "$lookup": {
                    "from": "hosts",
                    "localField": "hostgroup_name",
                    "foreignField": "hostgroups",
                    "as": "__hosts__",
                }
            })
        if not projection or any([p.startswith("__services__") for p in projection]):
            lookup.append({
                "$lookup": {
                    "from": "services",
                    "localField": "hostgroup_name",
                    "foreignField": "hostgroups",
                    "as": "__services__",
                }
            })
        return lookup

    def get_mongo_lookup_servicegroups(self, pipeline, projection):
        """
        Adds cross collections $lookup stage to the pipeline if columns
        require access to child objects attributes.

        :param list pipeline: The mongo pipeline to update
        :param list projection: The
        """
        # If at least one attribtue from the service is requested, add
        # the $lookup pipeline stage
        lookup = []
        if not projection or any([p.startswith("__hosts__") for p in projection]):
            lookup.append({
                "$lookup": {
                    "from": "hosts",
                    "localField": "servicegroup_name",
                    "foreignField": "servicegroups",
                    "as": "__hosts__",
                }
            })
        if not projection or any([p.startswith("__services__") for p in projection]):
            lookup.append({
                "$lookup": {
                    "from": "services",
                    "localField": "servicegroup_name",
                    "foreignField": "servicegroups",
                    "as": "__services__",
                }
            })
        return lookup

    def get_mongo_lookup_hostsbygroup(self, pipeline, projection):
        """
        Adds cross collections $lookup stage to the pipeline if columns
        require access to child objects attributes.

        :param list pipeline: The mongo pipeline to update
        :param list projection: The
        """
        # If at least one attribtue from the service is requested, add
        # the $lookup pipeline stage
        lookup = []
        if not projection or any([p.startswith("__services__") for p in projection]):
            lookup.extend([
                {
                    "$lookup": {
                        "from": "services",
                        "localField": "host_name",
                        "foreignField": "host_name_name",
                        "as": "__services__",
                    }
                },
            ])
        if not projection or any([p.startswith("__hostgroup__") for p in projection]):
            lookup.extend([
                {
                    "$lookup": {
                        "from": "hostgroups",
                        "localField": "hostgroups",
                        "foreignField": "hostgroup_name",
                        "as": "__hostgroup__",
                    }
                },
                {"$unwind": "$__hostgroup__"},
            ])
        if not projection or any([p.startswith("__hostgroup_hosts__") for p in projection]):
            lookup.append({
                "$lookup": {
                    "from": "hosts",
                    "localField": "hostgroups",
                    "foreignField": "hostgroups",
                    "as": "__hostgroup_hosts__",
                }
            })
        if not projection or any([p.startswith("__hostgroup_services__") for p in projection]):
            lookup.append({
                "$lookup": {
                    "from": "services",
                    "localField": "hostgroups",
                    "foreignField": "hostgroups",
                    "as": "__hostgroup_services__",
                }
            })
        return lookup

    def get_mongo_lookup_servicesbygroup(self, pipeline, projection):
        """
        Adds cross collections $lookup stage to the pipeline if columns
        require access to child objects attributes.

        :param list pipeline: The mongo pipeline to update
        :param list projection: The
        """
        # If at least one attribtue from the service is requested, add
        # the $lookup pipeline stage
        lookup = []
        if not projection or any([p.startswith("__host__") for p in projection]):
            lookup.extend([
                {
                    "$lookup": {
                        "from": "hosts",
                        "localField": "host_name",
                        "foreignField": "host_name",
                        "as": "__host__",
                    }
                },
                {"$unwind": "$__host__"}
            ])
        if not projection or any([p.startswith("__servicegroup__") for p in projection]):
            lookup.extend([
                {
                    "$lookup": {
                        "from": "servicegroups",
                        "localField": "servicegroups",
                        "foreignField": "servicegroup_name",
                        "as": "__servicegroup__",
                    }
                },
                {"$unwind": "$__servicegroup__"}
            ])
        if not projection or any([p.startswith("__servicegroup_hosts__") for p in projection]):
            lookup.append({
                "$lookup": {
                    "from": "hosts",
                    "localField": "servicegroups",
                    "foreignField": "servicegroups",
                    "as": "__servicegroup_hosts__",
                }
            })
        if not projection or any([p.startswith("__servicegroup_services__") for p in projection]):
            lookup.append({
                "$lookup": {
                    "from": "services",
                    "localField": "servicegroups",
                    "foreignField": "servicegroups",
                    "as": "__servicegroup_services__",
                }
            })
        return lookup

    def get_mongo_lookup_servicesbyhostgroup(self, pipeline, projection):
        """
        Adds cross collections $lookup stage to the pipeline if columns
        require access to child objects attributes.

        :param list pipeline: The mongo pipeline to update
        :param list projection: The
        """
        # If at least one attribtue from the service is requested, add
        # the $lookup pipeline stage
        lookup = []
        if not projection or any([p.startswith("__host__") for p in projection]):
            lookup.extend([
                {
                    "$lookup": {
                        "from": "hosts",
                        "localField": "host_name",
                        "foreignField": "host_name",
                        "as": "__host__",
                    }
                },
                {"$unwind": "$__host__"}
            ])
        if not projection or any([p.startswith("__hostgroup__") for p in projection]):
            lookup.extend([
                {
                    "$lookup": {
                        "from": "hostgroups",
                        "localField": "hostgroups",
                        "foreignField": "hostgroup_name",
                        "as": "__hostgroup__",
                    }
                },
                {"$unwind": "$__hostgroup__"}
            ])
        if not projection or any([p.startswith("__hostgroup_hosts__") for p in projection]):
            lookup.append({
                "$lookup": {
                    "from": "hosts",
                    "localField": "hostgroups",
                    "foreignField": "hostgroups",
                    "as": "__hostgroup_hosts__",
                }
            })
        if not projection or any([p.startswith("__hostgroup_services__") for p in projection]):
            lookup.append({
                "$lookup": {
                    "from": "services",
                    "localField": "hostgroups",
                    "foreignField": "hostgroups",
                    "as": "__hostgroup_services__",
                }
            })
        return lookup

    def get_filter_query(self, table, stack, columns=None, limit=None, sort=None, query_format=None):
        """
        Generates the final filter query from the list of queries in
        mongo_filters

        :param str table: The table name to build query against
        :param list stack: The filters stack to build query from
        :param int limit: The maximum number of records to return
        :param str sort: The attribute name to sort against
        :param str query_format: An indicator telling the query format to
                                 return. May be None or "aggregation"
        :rtype: dict/list
        :return: The filter query
        """
        if stack:
            if len(stack) > 1:
                query = {"$and": stack}
            else:
                query = stack[0]
        else:
            query = {}

        columns = self.filter_query_columns(table, columns)
        projection = self.get_mongo_columns_projection(table, columns)
        groupby = self.grouping_tables.get(table)

        if groupby is not None and groupby not in projection:
            projection[groupby] = 1

        print("get_filter_query(): columns")
        pprint(columns)
        print("get_filter_query(): projetions")
        pprint(projection)

        # Check if another collection lookup is necessary
        get_lookup_fct_name = "get_mongo_lookup_%s" % table
        print("find(): get_lookup_fct_name: %s" % get_lookup_fct_name)
        get_lookup_fct = getattr(self, get_lookup_fct_name, None)

        if get_lookup_fct:
            lookup = get_lookup_fct(table, projection)
        else:
            lookup = []

        # If another collection $lookup is necessary, use an aggregation
        # rather than a search
        if lookup or groupby or query_format == "aggregation":
            pipeline = [
                {"$match": query}
            ]
            if limit:
                pipeline.append({"$limit": limit})
            if groupby is not None:
                # We do a second match as the $unwind may have expanded
                # documents that we do not want
                pipeline.extend([
                    {"$unwind": "$%s" % groupby},
                    {"$match": query}
                ])
            pipeline.extend(lookup)
            if projection and query_format != "aggregation":
                pipeline.append({
                    "$project": projection
                })
            if sort is not None:
                pipeline.append(
                    {"$sort": {sort: 1}}
                )
            else:
                pipeline.append(
                    {"$sort": {"_id": 1}}
                )
            if groupby is not None:
                pipeline.append(
                    {"$sort": {groupby: 1}}
                )
            print("get_filter_query(): aggregation pipeline")
            pprint(pipeline)
            return pipeline
        else:
            parms = {
                "filter": query,
                "projection": projection,
            }
            if sort is None:
                parms["sort"] = [("_id", pymongo.ASCENDING)]
            elif sort is not None:
                parms["sort"] = [(sort, pymongo.ASCENDING)]
            if limit is not None:
                parms["limit"] = limit
            return parms

    def get_aggregation_query(self, table, filter_stack, query, columns=None):
        """
        Generates the final aggregation query from the list of queries in
        mongo_stats_filters

        :param str table: The table name
        :param dict filter_query: The initial filter query limitting the
                                  aggregation scope
        :param list,dict query: The aggregation/stats query
        :rtype: list
        :return: The aggregation query
        """
        groupby = self.grouping_tables.get(table)

        if groupby is not None and columns is None:
            columns = [groupby]
        elif columns is None:
            columns = []

        if isinstance(query, list):
            pipeline = self.get_filter_query(table, filter_stack, columns, query_format="aggregation")
            pipeline.extend(query)
        else:
            # The query is a stat filter, and needs to be enclosed in a count
            # aggregation
            stack = list(filter_stack)
            stack.append(query)
            pipeline = self.get_filter_query(table, stack, columns, query_format="aggregation")
            stack = []
            self.add_aggregation_count(stack, table, columns=columns)
            pipeline.extend(stack.pop(0))
        return pipeline

    def filter_query_columns(self, table, columns):
        """
        Filters query colums to only keep those known to the class mapping

        :param str table: The table name filter columns from
        :param list columns: The requested columns
        :rtype: list
        :return: The filterred columns
        """
        mapping = table_class_map[table]
        if columns is None:
            columns = mapping.keys()
        else:
            # Filter columns to only keep those known to the mapping
            columns = [c for c in columns if c in mapping.keys()]
        return columns

    def get_collection(self, table):
        """
        Returns the collection object corresponding to the requested table.

        :param str table: The table name
        """
        match = re.match("^([a-z]+)by([a-z]+)$", table)
        if match is not None:
            collection = match.group(1)
        else:
            collection = table
        print("get_collection(): collection: %s" % collection)
        return getattr(self.db, collection)

    def find(self, table, query):
        """
        Find hosts, and request cross collection documents when necessary

        :rtype: iterator
        :return: The query result
        """
        collection = self.get_collection(table)
        if isinstance(query, list):
            return collection.aggregate(query)
        else:
#            parms = [query["filter"]]
#            if "projection" in query:
#                parms.append(query["projection"])
#            cursor = collection.find(*parms)
#            if "sort" in query:
#                cursor = cursor.sort(query["sort"])
#            if "limit" in query:
#                cursor = cursor.limit(query["limit"])
#            return cursor
            return collection.find(**query)

    def count(self, table, query):
        """
        General purpose MongoDB count() query

        :rtype: iterator
        :return: The query result
        """
        collection = self.get_collection(table)
        return collection.count(query)

    def aggregate(self, table, query):
        """
        General purpose MongoDB aggregate() query

        :rtype: iterator
        :return: The query result
        """
        collection = self.get_collection(table)
        return collection.aggregate(query)

    # UI will launch us names in str, we got unicode
    # in our rg, so we must manage it here
    def get_host(self, hname):
        hname = hname.decode('utf8', 'ignore')
        collection = getattr(self.db, "hosts")
        return collection.find_one({"_id": hname})

    def get_service(self, hname, sdesc):
        hname = hname.decode('utf8', 'ignore')
        sdesc = sdesc.decode('utf8', 'ignore')
        collection = getattr(self.db, "services")
        key = "%s/%s" % (hname, sdesc)
        return collection.find_one({"_id": key})

    def get_all_hosts_and_services(self):
        all = []
        all.extend(self.rg.hosts)
        all.extend(self.rg.services)
        return all

    def get_contact(self, name):
        name = name.decode('utf8', 'ignore')
        collection = getattr(self.db, "contacts")
        return collection.find_one({"_id": name})

    def get_contactgroup(self, name):
        name = name.decode('utf8', 'ignore')
        collection = getattr(self.db, "contactgroups")
        return collection.find_one({"_id": name})

    def get_contacts(self):
        collection = getattr(self.db, "contacts")
        return collection.find()

    def get_hostgroups(self):
        collection = getattr(self.db, "contactgroups")
        return collection.find()

    def get_hostgroup(self, name):
        name = name.decode('utf8', 'ignore')
        collection = getattr(self.db, "hostgroups")
        return collection.find_one({"_id": name})

    def get_servicegroups(self):
        collection = getattr(self.db, "servicegroups")
        return collection.find()

    def get_servicegroup(self, name):
        name = name.decode('utf8', 'ignore')
        collection = getattr(self.db, "servicegroups")
        return collection.find_one({"_id": name})

    # Get the hostgroups sorted by names, and zero size in the end
    # if selected one, put it in the first place
    def get_hostgroups_sorted(self, selected=''):
        r = []
        selected = selected.strip()

        hg_names = [hg.get_name() for hg in self.rg.hostgroups
                    if len(hg.members) > 0 and hg.get_name() != selected]
        hg_names.sort()
        hgs = [self.rg.hostgroups.find_by_name(n) for n in hg_names]
        hgvoid_names = [hg.get_name() for hg in self.rg.hostgroups
                        if len(hg.members) == 0 and hg.get_name() != selected]
        hgvoid_names.sort()
        hgvoids = [self.rg.hostgroups.find_by_name(n) for n in hgvoid_names]

        if selected:
            hg = self.rg.hostgroups.find_by_name(selected)
            if hg:
                r.append(hg)

        r.extend(hgs)
        r.extend(hgvoids)

        return r

    def get_hosts(self):
        collection = getattr(self.db, "hosts")
        return collection.find()

    def get_services(self):
        collection = getattr(self.db, "services")
        return collection.find()

    def get_schedulers(self):
        collection = getattr(self.db, "schedulers")
        return collection.find()

    def get_pollers(self):
        collection = getattr(self.db, "pollers")
        return collection.find()

    def get_brokers(self):
        collection = getattr(self.db, "brokers")
        return collection.find()

    def get_receivers(self):
        collection = getattr(self.db, "receivers")
        return collection.find()

    def get_reactionners(self):
        collection = getattr(self.db, "reactionners")
        return collection.find()

    def get_program_start(self):
        for c in self.rg.configs.values():
            return c.program_start
        return None

    def get_realms(self):
        return self.rg.realms

    def get_realm(self, r):
        collection = getattr(self.db, "realms")
        return collection.find()

    # Get the hosts tags sorted by names, and zero size in the end
    def get_host_tags_sorted(self):
        collection = getattr(self.db, "realms")
        hosts = collection.find(projection={"_id": 0, "tags": 1})
        tags = []
        for host in hosts:
            tags.extend(host["tags"])
        return
        r = []
        names = self.rg.tags.keys()
        names.sort()
        for n in names:
            r.append((n, self.rg.tags[n]))
        return r

    # Get the hosts tagged with a specific tag
    def get_hosts_tagged_with(self, tag):
        r = []
        for h in self.get_hosts():
            if tag in h.get_host_tags():
                r.append(h)
        return r

    # Get the services tags sorted by names, and zero size in the end
    def get_service_tags_sorted(self):
        r = []
        names = self.rg.services_tags.keys()
        names.sort()
        for n in names:
            r.append((n, self.rg.services_tags[n]))
        return r

    def get_important_impacts(self):
        res = []
        for s in self.rg.services:
            if s.is_impact and s.state not in ['OK', 'PENDING']:
                if s.business_impact > 2:
                    res.append(s)
        for h in self.rg.hosts:
            if h.is_impact and h.state not in ['UP', 'PENDING']:
                if h.business_impact > 2:
                    res.append(h)
        return res

    # Returns all problems
    def get_all_problems(self, to_sort=True, get_acknowledged=False):
        res = []
        if not get_acknowledged:
            res.extend([s for s in self.rg.services
                        if s.state not in ['OK', 'PENDING'] and
                        not s.is_impact and not s.problem_has_been_acknowledged and
                        not s.host.problem_has_been_acknowledged])
            res.extend([h for h in self.rg.hosts
                        if h.state not in ['UP', 'PENDING'] and
                        not h.is_impact and not h.problem_has_been_acknowledged])
        else:
            res.extend([s for s in self.rg.services
                        if s.state not in ['OK', 'PENDING'] and not s.is_impact])
            res.extend([h for h in self.rg.hosts
                        if h.state not in ['UP', 'PENDING'] and not h.is_impact])

        if to_sort:
            res.sort(hst_srv_sort)
        return res

    # returns problems, but the most recent before
    def get_problems_time_sorted(self):
        pbs = self.get_all_problems(to_sort=False)
        pbs.sort(last_state_change_earlier)
        return pbs

    # Return all non managed impacts
    def get_all_impacts(self):
        res = []
        for s in self.rg.services:
            if s.is_impact and s.state not in ['OK', 'PENDING']:
                # If s is acked, pass
                if s.problem_has_been_acknowledged:
                    continue
                # We search for impacts that were NOT currently managed
                if len([p for p in s.source_problems if not p.problem_has_been_acknowledged]) > 0:
                    res.append(s)
        for h in self.rg.hosts:
            if h.is_impact and h.state not in ['UP', 'PENDING']:
                # If h is acked, pass
                if h.problem_has_been_acknowledged:
                    continue
                # We search for impacts that were NOT currently managed
                if len([p for p in h.source_problems if not p.problem_has_been_acknowledged]) > 0:
                    res.append(h)
        return res

    # Return the number of problems
    def get_nb_problems(self):
        return len(self.get_all_problems(to_sort=False))

    # Get the number of all problems, even the ack ones
    def get_nb_all_problems(self, user):
        res = []
        res.extend([s for s in self.rg.services
                    if s.state not in ['OK', 'PENDING'] and not s.is_impact])
        res.extend([h for h in self.rg.hosts
                    if h.state not in ['UP', 'PENDING'] and not h.is_impact])
        return len(only_related_to(res, user))

    # Return the number of impacts
    def get_nb_impacts(self):
        return len(self.get_all_impacts())

    def get_nb_elements(self):
        return len(self.rg.services) + len(self.rg.hosts)

    def get_important_elements(self):
        res = []
        # We want REALLY important things, so business_impact > 2, but not just IT elements that are
        # root problems, so we look only for config defined my_own_business_impact value too
        res.extend([s for s in self.rg.services
                    if (s.business_impact > 2 and not 0 <= s.my_own_business_impact <= 2)])
        res.extend([h for h in self.rg.hosts
                    if (h.business_impact > 2 and not 0 <= h.my_own_business_impact <= 2)])
        print "DUMP IMPORTANT"
        for i in res:
            safe_print(i.get_full_name(), i.business_impact, i.my_own_business_impact)
        return res

    # For all business impacting elements, and give the worse state
    # if warning or critical
    def get_overall_state(self):
        h_states = [h.state_id for h in self.rg.hosts
                    if h.business_impact > 2 and h.is_impact and h.state_id in [1, 2]]
        s_states = [s.state_id for s in self.rg.services
                    if s.business_impact > 2 and s.is_impact and s.state_id in [1, 2]]
        print "get_overall_state:: hosts and services business problems", h_states, s_states
        if len(h_states) == 0:
            h_state = 0
        else:
            h_state = max(h_states)
        if len(s_states) == 0:
            s_state = 0
        else:
            s_state = max(s_states)
        # Ok, now return the max of hosts and services states
        return max(h_state, s_state)

    # Same but for pure IT problems
    def get_overall_it_state(self):
        h_states = [h.state_id for h in self.rg.hosts if h.is_problem and h.state_id in [1, 2]]
        s_states = [s.state_id for s in self.rg.services if s.is_problem and s.state_id in [1, 2]]
        if len(h_states) == 0:
            h_state = 0
        else:
            h_state = max(h_states)
        if len(s_states) == 0:
            s_state = 0
        else:
            s_state = max(s_states)
        # Ok, now return the max of hosts and services states
        return max(h_state, s_state)

    # Get percent of all Services
    def get_per_service_state(self):
        all_services = self.rg.services
        problem_services = []
        problem_services.extend([s for s in self.rg.services
                                 if s.state not in ['OK', 'PENDING'] and not s.is_impact])
        if len(all_services) == 0:
            res = 0
        else:
            res = int(100 - (len(problem_services) * 100) / float(len(all_services)))
        return res

    # Get percent of all Hosts
    def get_per_hosts_state(self):
        all_hosts = self.rg.hosts
        problem_hosts = []
        problem_hosts.extend([s for s in self.rg.hosts
                              if s.state not in ['UP', 'PENDING'] and not s.is_impact])
        if len(all_hosts) == 0:
            res = 0
        else:
            res = int(100 - (len(problem_hosts) * 100) / float(len(all_hosts)))
        return res

    # For all business impacting elements, and give the worse state
    # if warning or critical
    def get_len_overall_state(self):
        h_states = [h.state_id for h in self.rg.hosts
                    if h.business_impact > 2 and h.is_impact and h.state_id in [1, 2]]
        s_states = [s.state_id for s in self.rg.services
                    if s.business_impact > 2 and s.is_impact and s.state_id in [1, 2]]
        print "get_len_overall_state:: hosts and services business problems", h_states, s_states
        # Just return the number of impacting elements
        return len(h_states) + len(s_states)

    # Return a tree of {'elt': Host, 'fathers': [{}, {}]}
    def get_business_parents(self, obj, levels=3):
        res = {'node': obj, 'fathers': []}
        # if levels == 0:
        #     return res

        for i in obj.parent_dependencies:
            # We want to get the levels deep for all elements, but
            # go as far as we should for bad elements
            if levels != 0 or i.state_id != 0:
                par_elts = self.get_business_parents(i, levels=levels - 1)
                res['fathers'].append(par_elts)

        print "get_business_parents::Give elements", res
        return res

    # Ok, we do not have true root problems, but we can try to guess isn't it?
    # We can just guess for services with the same services of this host in fact
    def guess_root_problems(self, obj):
        if obj.__class__.my_type != 'service':
            return []
        r = [s for s in obj.host.services if s.state_id != 0 and s != obj]
        return r

datamgr = DataManager()
