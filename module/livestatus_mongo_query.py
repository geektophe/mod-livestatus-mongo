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
import time
import copy
import pymongo
import bson

from shinken.log import logger
from livestatus_mongo_response import LiveStatusResponse
from livestatus_mongo_response import Separators
from livestatus_query_error import LiveStatusQueryError

#############################################################################


class LiveStatusQuery(object):

    my_type = 'query'

    def __init__(self, datamgr):
        # Runtime data form the global LiveStatus object
        self.datamgr = datamgr
        self.mapping = datamgr.mapping

        # Private attributes for this specific request
        self.response = LiveStatusResponse()
        self.table = None
        self.columns = None
        self.limit = None

        # Initialize the stacks which are needed for the Filter: and Stats:
        # filter- and count-operations
        self.stats_query = False

        # When was this query launched?
        self.tic = time.time()
        # Clients can also send their local time with the request
        self.client_localtime = self.tic

        # This is mostly used in the Response.format... which needs to know
        # the class behind a queries table
        self.filters_stack = self.datamgr.make_stack()
        self.aggregations_stack = self.datamgr.make_stack()

        self.objects_get_handlers = {
            'hosts':                self.get_filtered_livedata,
            'services':             self.get_filtered_livedata,
            'commands':             self.get_filtered_livedata,
            'schedulers':           self.get_filtered_livedata,
            'brokers':              self.get_filtered_livedata,
            'pollers':              self.get_filtered_livedata,
            'reactionners':         self.get_filtered_livedata,
            'contacts':             self.get_filtered_livedata,
            'contactgroups':        self.get_filtered_livedata,
            'hostgroups':           self.get_filtered_livedata,
            'servicegroups':        self.get_filtered_livedata,
            'timeperiods':          self.get_filtered_livedata,
            'downtimes':            self.get_filtered_livedata,
            'comments':             self.get_filtered_livedata,
            'hostsbygroup':         self.get_filtered_livedata,
            'servicesbygroup':      self.get_filtered_livedata,
            'servicesbyhostgroup':  self.get_filtered_livedata,
            'problems':             self.get_filtered_livedata,
            'log':                  self.get_filtered_livedata,
            'status':               self.get_status_livedata,
            'columns':              self.get_columns_livedata,
        }
        self.operator_mapping = {
            "=":  self.datamgr.add_filter_eq,
            "=~":  self.datamgr.add_filter_eq_ci,
            "~":  self.datamgr.add_filter_reg,
            "~~":  self.datamgr.add_filter_reg_ci,
            ">":  self.datamgr.add_filter_gt,
            ">=":  self.datamgr.add_filter_ge,
            "<":  self.datamgr.add_filter_lt,
            "<=":  self.datamgr.add_filter_le,
            "!=":  self.datamgr.add_filter_not_eq,
            "!=~":  self.datamgr.add_filter_not_eq_ci,
            "!~":  self.datamgr.add_filter_not_reg,
            "!~~":  self.datamgr.add_filter_not_reg_ci,
            "sum":  self.datamgr.add_aggregation_sum,
            "min":  self.datamgr.add_aggregation_min,
            "max":  self.datamgr.add_aggregation_max,
            "avg":  self.datamgr.add_aggregation_avg,
            "count":  self.datamgr.add_aggregation_count,
        }

    def split_command(self, line, splits=1):
        """Create a list from the words of a line"""
        return line.split(' ', splits)

    def split_option(self, line, splits=1):
        """Like split_commands, but converts numbers to int data type"""
        x = map(lambda i: (i.isdigit() and int(i)) or i, [token.strip() for token in re.split(r"[\s]+", line, splits)])
        return x

    def split_option_with_columns(self, line):
        """Split a line in a command and a list of words"""
        cmd, columns = self.split_option(line)
        mapping = self.mapping[self.table]
        table_columns = mapping.keys()
        return cmd, [c for c in columns.split() if c in table_columns]

    def parse_filter_line(self, line):
        """
        Map some operators to theyr complementary form to reduce the cases
        to manage.

        :param str operator: The operator to analyze
        :return: A tuple with operator, alias
        """
        # Rows should have patterns
        # Filter: state = 3
        # Stats: avg execution_time = ...
        # Stats: avg execution_time as exec_time
        parts = len(line.split())
        if parts >= 4:
            _, attribute, operator, reference = self.split_option(line, 3)
        elif parts >= 3:
            _, attribute, operator = self.split_option(line, 2)
            reference = ''
        else:
            raise LiveStatusQueryError(450, 'invalid filter: %s' % line)

        # Parses a row with patterns like:
        # Filter: state = 3
        # Or
        # Stats: scheduled_downtime_depth = 0
        if operator in ['=', '>', '>=', '<', '<=', '=~', '~', '~~', '!=', '!>', '!>=', '!<', '!<=', '!=~', '!~', '!~~']:
            # Some operators can simply be negated
            if operator in ['!>', '!>=', '!<', '!<=']:
                operator = {'!>': '<=', '!>=': '<', '!<': '>=', '!<=': '>'}[operator]
            return attribute, operator, reference
        # Parses a row with patterns like:
        # Stats: avg execution_time
        # Stats: avg execution_time = ...
        # Stats: avg execution_time as exec_time
        elif attribute in ['sum', 'min', 'max', 'avg', 'std']:
            operator, attribute = attribute, operator
            if reference.startswith('as '):
                _, alias = reference.split(' ', 2)
            return attribute, operator, None
        else:
            raise LiveStatusQueryError(450, 'invalid filter: %s' % line)

    def parse_input(self, data):
        """
        Parse the lines of a livestatus request.

        This function looks for keywords in input lines and
        sets the attributes of the request object
        """
        for line in data.splitlines():
            line = line.strip()
            # Tools like NagVis send KEYWORK:option, and we prefer to have
            # a space following the:
            if ':' in line and not ' ' in line:
                line = line.replace(':', ': ')
            keyword = line.split(' ')[0].rstrip(':')
            if keyword == 'GET':  # Get the name of the base table
                _, self.table = self.split_command(line)
                if self.table not in self.mapping.keys():
                    raise LiveStatusQueryError(404, self.table)
            elif keyword == 'Columns':  # Get the names of the desired columns
                _, self.columns = self.split_option_with_columns(line)
                self.response.columnheaders = 'off'
            elif keyword == 'ResponseHeader':
                _, responseheader = self.split_option(line)
                self.response.responseheader = responseheader
            elif keyword == 'OutputFormat':
                _, outputformat = self.split_option(line)
                self.response.outputformat = outputformat
            elif keyword == 'KeepAlive':
                _, keepalive = self.split_option(line)
                self.response.keepalive = keepalive
            elif keyword == 'ColumnHeaders':
                _, columnheaders = self.split_option(line)
                self.response.columnheaders = columnheaders
            elif keyword == 'Limit':
                _, self.limit = self.split_option(line)
            elif keyword == 'AuthUser':
                _, authuser = self.split_option(line)
                if self.table in ['hosts', 'services', 'hostgroups',
                        'servicegroups', 'hostsbygroup', 'servicesbygroup',
                        'servicesbyhostgroup', 'problems']:
                    self.datamgr.add_filter_user(
                        self.filters_stack,
                        "contacts",
                        authuser
                    )
                elif self.table in ['contactgroups']:
                    self.datamgr.add_filter_user(
                        self.filters_stack,
                        "members",
                        authuser
                    )
            elif keyword == 'Filter':
                try:
                    attribute, operator, reference = self.parse_filter_line(line)
                    self.add_filter(
                        self.filters_stack,
                        operator,
                        attribute,
                        reference
                    )
                except Exception as e:
                    logger.warning("[Livestatus Query] Illegal operation: %s" % e)
                    raise
            elif keyword == 'And':
                _, andnum = self.split_option(line)
                # Take the last andnum functions from the stack
                # Construct a new function which makes a logical and
                # Put the function back onto the stack
                self.datamgr.stack_filter_and(
                    self.filters_stack,
                    self.table,
                    andnum
                )
            elif keyword == 'Or':
                _, ornum = self.split_option(line)
                # Take the last ornum functions from the stack
                # Construct a new function which makes a logical or
                # Put the function back onto the stack
                self.datamgr.stack_filter_or(
                    self.filters_stack,
                    self.table,
                    ornum
                )
            elif keyword == 'Negate':
                _, notnum = self.split_option(line)
                self.datamgr.stack_filter_negate(
                    self.filters_stack,
                    notnum
                )
            elif keyword == 'Stats':
                self.stats_query = True
                try:
                    attribute, operator, reference = self.parse_filter_line(line)
                    self.add_filter(
                        self.aggregations_stack,
                        operator,
                        attribute,
                        reference
                    )
                except Exception as e:
                    logger.warning("[Livestatus Query] Illegal operation: %s" % e)
                    raise
                    continue
            elif keyword == 'StatsAnd':
                _, andnum = self.split_option(line)
                self.datamgr.stack_filter_and(
                    self.aggregations_stack,
                    self.table,
                    andnum
                )
            elif keyword == 'StatsOr':
                _, ornum = self.split_option(line)
                self.datamgr.stack_filter_or(
                    self.aggregations_stack,
                    self.table,
                    ornum
                )
            elif keyword == 'StatsNegate':
                _, notnum = self.split_option(line)
                self.datamgr.stack_filter_negate(
                    self.aggregations_stack,
                    notnum
                )
            elif keyword == 'Separators':
                separators = map(lambda sep: chr(int(sep)), line.split(' ', 5)[1:])
                self.response.separators = Separators(*separators)
            elif keyword == 'Localtime':
                _, self.client_localtime = self.split_option(line)
            else:
                # This line is not valid or not implemented
                logger.error("[Livestatus Query] Received a line of input which i can't handle: '%s'" % line)

    def process_query(self):
        result = self.launch_query()
        self.response.format_live_data(result, self.columns)
        return self.response.respond()

    def launch_query(self):
        """ Prepare the request object's filter stacks """

        # The Response object needs to access the Query
        self.response.load(self)

        # A minimal integrity check
        if not self.table:
            return []
        try:
            # Remember the number of stats filters. We need these numbers as columns later.
            # But we need to ask now, because get_live_data() will empty the stack
            return self.get_live_data()
        except Exception, e:
            import traceback
            logger.error("[Livestatus Query] Error: %s" % e)
            logger.debug("[Livestatus Query] %s" % traceback.format_exc())
            traceback.print_exc(32)
            return []

    def execute_filter_query(self, table=None):
        """
        Execute a filter query
        """
        if table is None:
            table = self.table
        query = self.datamgr.get_filter_query(
            table,
            self.filters_stack,
            self.columns,
            self.limit,
        )
        logger.debug("executing mongo filter query against table: %s" % table)
        logger.debug(query)
        return self.datamgr.find(table, query)

    def execute_aggregation_query(self, table=None):
        """
        Execute an aggregation query
        """
        if table is None:
            table = self.table
        results = {}
        # If no aggregation has been
        for i, query in enumerate(self.aggregations_stack):
            query = self.datamgr.get_aggregation_query(table, self.filters_stack, query, self.columns)
            logger.debug(
                "executing mongo aggregation query agains table: %s" % table
            )
            logger.debug(query)
            logger.debug("aggregation result")
            for result in self.datamgr.aggregate(table, query):
                logger.debug(result)
                if result["group"] is None:
                    group = results.setdefault(
                        None,
                        {"group": None, "stats": {}}
                    )
                else:
                    key = "".join([
                        "%s%s" % (k, v)
                        for k, v in sorted(result["group"].items())
                    ])
                    group = results.setdefault(
                        key,
                        {"group": result["group"], "stats": {}}
                    )
                group["stats"][i] = result["result"]
        rows = []
        for key, stats in sorted(results.items(), key=lambda r: r[0]):
            row = []
            item = stats["group"]
            if item is None:
                pass
            elif len(item) == 1:
                row.append(item.values().pop(0))
            else:
                for column in self.columns:
                    attr = self.datamgr.get_column_attribute(
                        self.table,
                        column
                    )
                    row.append(item.get(attr, ""))
            row.extend([
                stats["stats"].get(i, 0)
                for i in range(len(self.aggregations_stack))
            ])
            rows.append(row)
        return rows

    def get_filtered_livedata(self, table=None):
        """
        Retrieves direct hosts or services from the mongo database
        """
        """
        Check input parameters, and get queries depending on the query
        requested
        """
        if self.aggregations_stack:
            return self.execute_aggregation_query(table)
        else:
            return self.execute_filter_query(table)

    def get_hostsbygroup_livedata(self):
        """
        For each hostgroup, get the member hosts (filterred) and merge the
        hostgroup attributes.
        """
        if self.aggregations_stack:
            return self.execute_aggregation_query("hostsbygroup")
        else:
            return self.execute_filter_query("hostsbygroup")

    def get_servicesbygroup_livedata(self):
        """
        For each hostgroup, get the member hosts (filterred) and merge the
        hostgroup attributes.
        """
        if self.aggregations_stack:
            return self.execute_aggregation_query("servicesbygroup", "servicegroups")
        else:
            return self.execute_filter_query("servicesbygroup", "servicegroups")

    def get_servicesbyhostgroup_livedata(self):
        """
        For each hostgroup, get the member hosts (filterred) and merge the
        hostgroup attributes.
        """
        if self.aggregations_stack:
            return self.execute_aggregation_query("servicesbyhostgroup", "hostgroups")
        else:
            return self.execute_filter_query("servicesbyhostgroup", "hostgroups")


    def get_list_livedata(self, cs):
        t = self.table
        if cs.without_filter:
            res = [y for y in reduce(list.__add__,
                [getattr(x, t) for x in self.get_table("services") if len(getattr(x, t)) > 0] +
                [getattr(x, t) for x in self.get_table("hosts") if len(getattr(x, t)) > 0],
                []
            )]
        else:
            res = [c for c in reduce(list.__add__ ,
                [getattr(x, t) for x in self.get_table("services") if len(getattr(x, t)) > 0] +
                [getattr(x, t) for x in self.get_table("hosts") if len(getattr(x, t)) > 0],
                []
            ) if cs.filter_func(c)]
        return res

    def _get_group_livedata(self, cs, objs, groupattr1, groupattr2, sorter):
        """
        return a list of elements from a "group" of 'objs'. group can be a hostgroup or a servicegroup.
        if an element of objs (a host or a service) is member of groups
        (which means, it has >1 entry in its host/servicegroup attribute (groupattr1))
        then for each of these groups there will be a copy of the original element with a new attribute called groupattr2
        which points to the group
        objs: the objects to get elements from.
        groupattr1: the attribute where an element's groups can be found
        groupattr2: the attribute name to set on result.
        group_key: the key to be used to sort the group members.
        """

        def factory(obj, attribute, groupobj):
            setattr(obj, attribute, groupobj)

        return sorted((
            factory(og[0], groupattr2, og[1]) or og[0] for og in ( # host, attr, hostgroup or host
                (copy.copy(inner_list0[0]), item0) for inner_list0 in ( # host', hostgroup
                    (h, getattr(h, groupattr1)) for h in objs if (cs.without_filter or cs.filter_func(h))  # 1 host, [seine hostgroups]
                ) for item0 in inner_list0[1] # item0 ist einzelne hostgroup
            )
        ), key=sorter)

    def _get_hostsbygroup_livedata(self, cs):
        sorter = lambda k: k.hostgroup.hostgroup_name
        return self.get_group_livedata(cs, self.get_table("hosts").__itersorted__(self.metainfo.query_hints), 'hostgroups', 'hostgroup', sorter)

    def _get_servicesbygroup_livedata(self, cs):
        sorter = lambda k: k.servicegroup.servicegroup_name
        return self.get_group_livedata(cs, self.get_table("services").__itersorted__(self.metainfo.query_hints), 'servicegroups', 'servicegroup', sorter)

    def get_problem_livedata(self, cs):
        # We will create a problems list first with all problems and source in it
        # TODO: create with filter
        problems = []
        for h in self.get_table("hosts").__itersorted__(self.metainfo.query_hints):
            if h.is_problem:
                pb = Problem(h, h.impacts)
                problems.append(pb)
        for s in self.get_table("services").__itersorted__(self.metainfo.query_hints):
            if s.is_problem:
                pb = Problem(s, s.impacts)
                problems.append(pb)
        # Then return
        return problems

    def get_status_livedata(self, cs):
        return [c for c in self.get_table("configs").values()]

    def get_columns_livedata(self, cs):
        result = []
        # The first 5 lines must be hard-coded
        # description;name;table;type
        # A description of the column;description;columns;string
        # The name of the column within the table;name;columns;string
        # The name of the table;table;columns;string
        # The data type of the column (int, float, string, list);type;columns;string
        result.append({
            'description': 'A description of the column', 'name': 'description', 'table': 'columns', 'type': 'string'})
        result.append({
            'description': 'The name of the column within the table', 'name': 'name', 'table': 'columns', 'type': 'string'})
        result.append({
            'description': 'The name of the table', 'name': 'table', 'table': 'columns', 'type': 'string'})
        result.append({
            'description': 'The data type of the column (int, float, string, list)', 'name': 'type', 'table': 'columns', 'type': 'string'})
        tablenames = ['hosts', 'services', 'hostgroups', 'servicegroups', 'contacts', 'contactgroups', 'commands', 'downtimes', 'comments', 'timeperiods', 'status', 'log', 'hostsbygroup', 'servicesbygroup', 'servicesbyhostgroup', 'status']
        for table in tablenames:
            cls = self.mapping[table][1]
            for attribute in cls.lsm_columns:
                result.append({
                    'description': getattr(cls, 'lsm_' + attribute).im_func.description,
                    'name': attribute,
                    'table': table,
                    'type': {
                        int: 'int',
                        float: 'float',
                        bool: 'int',
                        list: 'list',
                        str: 'string',
                    }[getattr(cls, 'lsm_' + attribute).im_func.datatype],
                })
        self.columns = ['description', 'name', 'table', 'type']
        return result

    def _get_servicesbyhostgroup_livedata(self, cs):
        objs = self.get_table("services").__itersorted__(self.metainfo.query_hints)
        return sorted([x for x in (
            setattr(svchgrp[0], 'hostgroup', svchgrp[1]) or svchgrp[0] for svchgrp in (
                (copy.copy(inner_list0[0]), item0) for inner_list0 in ( # 2 service clone and a hostgroup
                    (s, s.host.hostgroups) for s in objs if (cs.without_filter or cs.filter_func(s))  # 1 service, and it's host
                ) for item0 in inner_list0[1] if inner_list0[1] # 2b only if the service's (from all services->filtered in the innermost loop) host has groups
            )
        )], key=lambda svc: svc.hostgroup.hostgroup_name)

    def get_live_data(self):
        """
        Find the objects which match the request.
        """
        handler = self.objects_get_handlers.get(self.table, None)
        if not handler:
            logger.warning("[Livestatus Query] Got unhandled table: %s" % (self.table))
            return []

        return handler()

    def add_filter(self, stack, operator, attribute, reference):
        """
        Builds a mongo filter from the comparison operation

        :param list stack: The stack to append filter to
        :param str operator: The comparison operator
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to
        """
        if attribute not in self.datamgr.mapping[self.table]:
            raise LiveStatusQueryError(
                450,
                "no column %s in table %s" % (attribute, self.table)
            )
        # Map livestatus attribute `name` to the object's name
        fct = self.operator_mapping.get(operator)
        # Matches operators
        if fct:
            if operator in ("sum", "min", "max", "avg", "count"):
                fct(stack, self.table, attribute, self.columns)
            else:
                fct(stack, self.table, attribute, reference)
        else:
            raise LiveStatusQueryError(450, 'invalid filter: %s' % line)
