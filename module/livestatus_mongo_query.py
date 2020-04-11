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
from pprint import pprint

from shinken.log import logger
from mongo_mapping import table_class_map, find_filter_converter, list_livestatus_attributes, Problem
from livestatus_mongo_response import LiveStatusMongoResponse
from livestatus_stack import LiveStatusStack
from livestatus_constraints import LiveStatusConstraints
from livestatus_query_metainfo import LiveStatusQueryMetainfo
from livestatus_mongo_response import Separators
from livestatus_query_error import LiveStatusQueryError
from livestatus_mongo_datamanager import datamgr as mongo_datamgr

#############################################################################

def gen_all(values):
    for val in values:
        yield val

def gen_filtered(values, filterfunc):
    for val in values:
        if filterfunc(val):
            yield val

def gen_limit(values, maxelements):
    ''' This is a generator which returns up to <limit> elements '''
    loopcnt = 1
    for val in values:
        if loopcnt > maxelements:
            return
        yield val
        loopcnt += 1

# This is a generator which returns up to <limit> elements
# which passed the filter. If the limit has been reached
# it is no longer necessary to loop through the original list.
def gen_limit_filtered(values, maxelements, filterfunc):
    for val in gen_limit(gen_filtered(values, filterfunc), maxelements):
        yield val

#############################################################################

class LiveStatusMongoQuery(object):

    my_type = 'query'

    def __init__(self, datamgr, mongo_datamgr, query_cache, db, pnp_path, return_queue, counters):
        # Runtime data form the global LiveStatus object
        self.datamgr = datamgr
        self.mongo_datamgr = mongo_datamgr
        self.query_cache = query_cache
        self.db = db
        self.pnp_path = pnp_path
        self.return_queue = return_queue
        self.counters = counters

        # Private attributes for this specific request
        self.response = LiveStatusMongoResponse()
        self.authuser = None
        self.table = None
        self.columns = []
        self.filtercolumns = []
        self.prefiltercolumns = []
        self.outputcolumns = []
        self.stats_group_by = []
        self.stats_columns = []
        self.aliases = []
        self.limit = None
        self.extcmd = False

        # Initialize the stacks which are needed for the Filter: and Stats:
        # filter- and count-operations
        self.filter_stack = LiveStatusStack()
        self.stats_filter_stack = LiveStatusStack()
        self.stats_postprocess_stack = LiveStatusStack()
        self.stats_query = False

        # When was this query launched?
        self.tic = time.time()
        # Clients can also send their local time with the request
        self.client_localtime = self.tic

        # This is mostly used in the Response.format... which needs to know
        # the class behind a queries table
        self.table_class_map = table_class_map
        self.mongo_filters = mongo_datamgr.make_stack()
        self.mongo_aggregations = mongo_datamgr.make_stack()
        self.mongo_stats_filters = mongo_datamgr.make_stack()

    def __str__(self):
        output = "LiveStatusRequest:\n"
        for attr in ["table", "columns", "filtercolumns", "prefiltercolumns", "aliases", "stats_group_by", "stats_query"]:
            output += "request %s: %s\n" % (attr, getattr(self, attr))
        return output

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
        return cmd, [self.strip_table_from_column(c) for c in re.compile(r'\s+').split(columns)]

    def strip_table_from_column(self, column):
        """Cut off the table name, because it is possible
        to say service_state instead of state"""
        bygroupmatch = re.compile('(\w+)by.*group').search(self.table)
        if bygroupmatch:
            return re.sub(re.sub('s$', '', bygroupmatch.group(1)) + '_', '', column, 1)
        else:
            return re.sub(re.sub('s$', '', self.table) + '_', '', column, 1)

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
            raise LiveStatusQueryError(452, 'invalid filter: %s' % line)
        # Parses a row with patterns like:
        # Filter: state = 3
        # Or
        # Stats: scheduled_downtime_depth = 0
        if operator in ['=', '>', '>=', '<', '<=', '=~', '~', '~~', '!=', '!>', '!>=', '!<', '!<=', '!=~', '!~', '!~~']:
            # Cut off the table name
            attribute = self.strip_table_from_column(attribute)
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
            raise LiveStatusQueryError(452, 'invalid filter: %s' % line)

    def parse_input(self, data):
        """Parse the lines of a livestatus request.

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
                if self.table not in table_class_map.keys():
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
                if self.table in ['hosts', 'services']:
                    mongo_datamgr.add_filter_user(
                        self.mongo_filters,
                        "contacts",
                        authuser
                    )
                elif self.table in ['hostgroups', 'servicegroups', 'hostsbygroup', 'servicesbygroup', 'servicesbyhostgroup']:
                    pass
            elif keyword == 'Filter':
                try:
                    attribute, operator, reference = self.parse_filter_line(line)
                    # Builds mongo filters
                    if self.table == 'log':
                        self.db.add_filter(operator, attribute, reference)
                    else:
                        self.add_filter(
                            self.mongo_filters,
                            operator,
                            attribute,
                            reference
                        )
                except Exception as e:
                    logger.warning("[Livestatus Query] Illegal operation: %s" % e)
                    raise
                    continue
            elif keyword == 'And':
                _, andnum = self.split_option(line)
                # Take the last andnum functions from the stack
                # Construct a new function which makes a logical and
                # Put the function back onto the stack
                if self.table == 'log':
                    self.db.add_filter_and(andnum)
                else:
                    mongo_datamgr.stack_filter_and(
                        self.mongo_filters,
                        self.table,
                        andnum
                    )
            elif keyword == 'Or':
                _, ornum = self.split_option(line)
                # Take the last ornum functions from the stack
                # Construct a new function which makes a logical or
                # Put the function back onto the stack
                if self.table == 'log':
                    self.db.add_filter_or(ornum)
                else:
                    mongo_datamgr.stack_filter_or(
                        self.mongo_filters,
                        self.table,
                        ornum
                    )
            elif keyword == 'Negate':
                _, notnum = self.split_option(line)
                if self.table == 'log':
                    self.db.add_filter_not()
                else:
                    mongo_datamgr.stack_filter_negate(
                        self.mongo_filters,
                        notnum
                    )
            elif keyword == 'Stats':
                self.stats_query = True
                try:
                    attribute, operator, reference = self.parse_filter_line(line)
                    self.add_filter(
                        self.mongo_stats_filters,
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
                mongo_datamgr.stack_filter_and(
                    self.mongo_stats_filters,
                    self.table,
                    andnum
                )
            elif keyword == 'StatsOr':
                _, ornum = self.split_option(line)
                mongo_datamgr.stack_filter_or(
                    self.mongo_stats_filters,
                    self.table,
                    ornum
                )
            elif keyword == 'StatsNegate':
                _, notnum = self.split_option(line)
                mongo_datamgr.stack_filter_negate(
                    self.mongo_stats_filters,
                    notnum
                )
            elif keyword == 'Separators':
                separators = map(lambda sep: chr(int(sep)), line.split(' ', 5)[1:])
                self.response.separators = Separators(*separators)
            elif keyword == 'Localtime':
                _, self.client_localtime = self.split_option(line)
            elif keyword == 'COMMAND':
                _, self.extcmd = line.split(' ', 1)
            else:
                # This line is not valid or not implemented
                logger.error("[Livestatus Query] Received a line of input which i can't handle: '%s'" % line)
                pass
        self.metainfo = LiveStatusQueryMetainfo(data)

    def process_query(self):
        result = self.launch_query()
        self.response.format_live_data(result, self.columns, self.aliases)
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
            if self.table == 'log':
                return self.get_live_data_log(cs)
            else:
                # If the pnpgraph_present column is involved, then check
                # with each request if the pnp perfdata path exists
                if 'pnpgraph_present' in self.columns + self.filtercolumns + self.prefiltercolumns and self.pnp_path and os.access(self.pnp_path, os.R_OK):
                    self.pnp_path_readable = True
                else:
                    self.pnp_path_readable = False
                return self.get_live_data()
        except Exception, e:
            import traceback
            logger.error("[Livestatus Query] Error: %s" % e)
            logger.debug("[Livestatus Query] %s" % traceback.format_exc())
            traceback.print_exc(32)
            return []

    def get_table(self, table_name):
        """
        Returns a given table from the regenerator.

        :param str table_name: The table name to retrieve
        """
        return self.datamgr.rg.get_table(table_name)

    def execute_mongo_query(self):
        """
        Check input parameters, and get queries depending on the query
        requested
        """
        if self.mongo_stats_filters:
            return self.execute_mongo_aggregation_query()
        else:
            return self.execute_mongo_filter_query()

    def execute_mongo_filter_query(self):
        """
        Execute a filter query
        """
        print("Mongo filter query: table: %s" % self.table)
        query = mongo_datamgr.get_filter_query(self.table, self.mongo_filters)
        pprint(query)
        return mongo_datamgr.find(
            self.table,
            query,
            self.columns,
            self.limit
        )

#    def get_mongo_aggregation_query(self, filter_query, query):
#        """
#        Generates the final aggregation query from the list of queries in
#        mongo_stats_filters
#
#        :param dict filter_query: The initial filter query limitting the
#                                  aggregation scope
#        :param list,dict query: The aggregation/stats query
#        :rtype: list
#        :return: The aggregation query
#        """
#        if isinstance(query, list):
#            # The query is already an aggregation
#            query.insert(0, {
#                "$match": filter_query
#            })
#        else:
#            # The query is a stat filter, and needs to be enclosed in a count
#            # aggregation
#            stack = []
#            self.add_mongo_aggregation_count(stack)
#            aggregation_query = stack.pop()
#            if filter_query:
#                aggregation_query.insert(0, {
#                    "$match": {
#                        "$and": [
#                            filter_query,
#                            query
#                        ]
#                    }
#                })
#            else:
#                aggregation_query.insert(0, {
#                    "$match": query
#                })
#            query = aggregation_query
#        return query

    def execute_mongo_aggregation_query(self):
        """
        Execute an aggregation query

        There's 2 distinct Stats queries:

        - The attribute = value stats that is in fact
        """
        results = []
        filter_query = mongo_datamgr.get_filter_query(
            self.table,
            self.mongo_filters
        )
        # If no aggregation has been
        for query in self.mongo_stats_filters:
            query = mongo_datamgr.get_aggregation_query(self.table, filter_query, query)
            print("Mongo aggregation query: table: %s" % self.table)
            pprint(query)
            for result in mongo_datamgr.aggregate(self.table, query):
                results.append(result["result"])
        return results

    def get_filtered_livedata(self):
        """
        Retrieves direct hosts or services from the mongo database
        """
        return self.execute_mongo_query()

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

    def get_group_livedata(self, cs, objs, groupattr1, groupattr2, sorter):
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

    def get_hostsbygroup_livedata(self, cs):
        sorter = lambda k: k.hostgroup.hostgroup_name
        return self.get_group_livedata(cs, self.get_table("hosts").__itersorted__(self.metainfo.query_hints), 'hostgroups', 'hostgroup', sorter)

    def get_servicesbygroup_livedata(self, cs):
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
            cls = self.table_class_map[table][1]
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

    def get_servicesbyhostgroup_livedata(self, cs):
        objs = self.get_table("services").__itersorted__(self.metainfo.query_hints)
        return sorted([x for x in (
            setattr(svchgrp[0], 'hostgroup', svchgrp[1]) or svchgrp[0] for svchgrp in (
                (copy.copy(inner_list0[0]), item0) for inner_list0 in ( # 2 service clone and a hostgroup
                    (s, s.host.hostgroups) for s in objs if (cs.without_filter or cs.filter_func(s))  # 1 service, and it's host
                ) for item0 in inner_list0[1] if inner_list0[1] # 2b only if the service's (from all services->filtered in the innermost loop) host has groups
            )
        )], key=lambda svc: svc.hostgroup.hostgroup_name)

    objects_get_handlers = {
        'hosts':                get_filtered_livedata,
        'services':             get_filtered_livedata,
        'commands':             get_filtered_livedata,
        'schedulers':           get_filtered_livedata,
        'brokers':              get_filtered_livedata,
        'pollers':              get_filtered_livedata,
        'reactionners':         get_filtered_livedata,
        'contacts':             get_filtered_livedata,
        'contactgroups':        get_filtered_livedata,
        'hostgroups':           get_filtered_livedata,
        'servicegroups':        get_filtered_livedata,
        'timeperiods':          get_filtered_livedata,
        'downtimes':            get_list_livedata,
        'comments':             get_list_livedata,
        'hostsbygroup':         get_hostsbygroup_livedata,
        'servicesbygroup':      get_servicesbygroup_livedata,
        'problems':             get_problem_livedata,
        'status':               get_status_livedata,
        'columns':              get_columns_livedata,
        'servicesbyhostgroup':  get_servicesbyhostgroup_livedata
    }

    def get_live_data(self):
        """
        Find the objects which match the request.
        """
        handler = self.objects_get_handlers.get(self.table, None)
        if not handler:
            logger.warning("[Livestatus Query] Got unhandled table: %s" % (self.table))
            return []

        return handler(self)

    def _get_live_data_log(self, cs):
        for x in self.db.get_live_data_log():
            z = x.fill(self.datamgr)
            if cs.without_filter or cs.filter_func(z):
                yield z

    def get_live_data_log(self, cs):
        '''
        :param cs: The `LiveStatusConstraints´ instance to use for the live data logs.
        :return: a generator which yields logs matching the given "cs" constraints.
        '''
        items = self._get_live_data_log(cs)
        if self.limit:
            items = gen_limit(items, self.limit)
        return items

#    def get_mongo_attribute_name(self, attribute):
#        """
#        Return the attribute name to use to query the mongo database.
#
#        Some attribute hold different names when requested through LQL, and
#        queried in mongo. Return the suitable attribute for Mongo query
#        from LQL.
#
#        :param str attribute: The LQL requested attribute
#        :rtype: str
#        :return: The attribute name to use in mongo query
#        """
#        mapping = self.table_class_map[self.table][attribute]
#        return mapping.get("filters", {}).get("attr", attribute)
#
#    def get_mongo_attribute_type(self, attribute):
#        """
#        Returns the attribute type, as shown in object mapping
#
#        :param str attribute: The LQL requested attribute
#        :rtype: type
#        :return: The attribute type
#        """
#        return self.table_class_map[self.table][attribute].get("datatype")
#
#    def add_mongo_filter_eq(self, stack, attribute, reference):
#        """
#        Transposes an equalitiy operator filter into a mongo query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        attrtype = self.get_mongo_attribute_type(attribute)
#        if attrtype is list:
#            stack.append({
#                attrname: []
#            })
#        elif attrtype is not None:
#            stack.append({
#                attrname: {
#                    "$eq": attrtype(reference)
#                }
#            })
#        else:
#            stack.append({
#                attrname: {
#                    "$eq": reference
#                }
#            })
#
#    def add_mongo_filter_eq_ci(self, stack, attribute, reference):
#        """
#        Transposes a case insensitive equalitiy operator filter into a mongo
#        query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        attrtype = self.get_mongo_attribute_type(attribute)
#        if attrtype is list:
#            raise LiveStatusQueryError(452, 'operator not available for lists')
#        # Builds regular expression
#        reg = "^%s$" % reference
#        stack.append({
#            attrname: re.compile(reg, re.IGNORECASE)
#        })
#
#    def add_mongo_filter_reg(self, stack, attribute, reference):
#        """
#        Transposes a regex match operator filter into a mongo query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        attrtype = self.get_mongo_attribute_type(attribute)
#        # Builds regular expression
#        reg = str(reference)
#        if attrtype is list:
#            stack.append({
#                attrname: {
#                    "$in": [re.compile(reg)]
#                }
#            })
#        else:
#            stack.append({
#                attrname: re.compile(reg)
#            })
#
#    def add_mongo_filter_reg_ci(self, stack, attribute, reference):
#        """
#        Transposes a case insensitive regex match operator filter into a mongo
#        query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        attrtype = self.get_mongo_attribute_type(attribute)
#        # Builds regular expression
#        reg = str(reference)
#        if attrtype is list:
#            stack.append({
#                attrname: {
#                    "$in": [
#                        re.compile(reg, re.IGNORECASE)
#                    ]
#                }
#            })
#        else:
#            stack.append({
#                attrname: re.compile(reg, re.IGNORECASE)
#            })
#
#    def add_mongo_filter_lt(self, stack, attribute, reference):
#        """
#        Transposes a lower than operator filter into a mongo query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        attrtype = self.get_mongo_attribute_type(attribute)
#        if attrtype is list:
#            stack.append({
#                attrname: {
#                    "$nin": [reference]
#                }
#            })
#        else:
#            stack.append({
#                attrname: {"$lt": reference}
#            })
#
#    def add_mongo_filter_le(self, stack, attribute, reference):
#        """
#        Transposes a lower than or equal operator filter into a mongo query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        attrtype = self.get_mongo_attribute_type(attribute)
#        if attrtype is list:
#            # Builds regular expression
#            reg = "^%s$" % reference
#            stack.append({
#                attrname: {
#                    "$in": [re.compile(reg, re.IGNORECASE)]
#                }
#            })
#        elif attrtype is not None:
#            stack.append({
#                attrname: {"$lte": attrtype(reference)}
#            })
#        else:
#            stack.append({
#                attrname: {"$lte": reference}
#            })
#
#    def add_mongo_filter_gt(self, stack, attribute, reference):
#        """
#        Transposes a lower than operator filter into a mongo query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        attrtype = self.get_mongo_attribute_type(attribute)
#        if attrtype is list:
#            # Builds regular expression
#            reg = "^%s$" % reference
#            stack.append({
#                attrname: {
#                    "$nin": [re.compile(reg, re.IGNORECASE)]
#                }
#            })
#        elif attrtype is not None:
#            stack.append({
#                attrname: {"$gt": attrtype(reference)}
#            })
#        else:
#            stack.append({
#                attrname: {"$gt": reference}
#            })
#
#    def add_mongo_filter_ge(self, stack, attribute, reference):
#        """
#        Transposes a greater than or equal operator filter into a mongo query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        attrtype = self.get_mongo_attribute_type(attribute)
#        if attrtype is list:
#            stack.append({
#                attrname: {"$in": [reference]}
#            })
#        elif attrtype is not None:
#            stack.append({
#                attrname: {"$gte": attrtype(reference)}
#            })
#        else:
#            stack.append({
#                attrname: {"$gte": reference}
#            })
#
#    def add_mongo_filter_not_eq(self, stack, attribute, reference):
#        """
#        Transposes a not equal  operator filter into a mongo query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        attrtype = self.get_mongo_attribute_type(attribute)
#        if attrtype is list:
#            stack.append({
#                attrname: {"$ne": []}
#            })
#        elif attrtype is not None:
#            stack.append({
#                attrname: {"$ne": attrtype(reference)}
#            })
#        else:
#            stack.append({
#                attrname: {"$ne": reference}
#            })
#
#    def add_mongo_filter_not_eq_ci(self, stack, attribute, reference):
#        """
#        Transposes a case insensitive not equal operator filter into a mongo
#        query
#
#        Before MongoDB version 4.0.7, $not does not support $regex
#        This, using bson.regex.Regex regular expressions is required
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        attrtype = self.get_mongo_attribute_type(attribute)
#        if attrtype is list:
#            raise LiveStatusQueryError(452, 'operator not available for lists')
#        # Builds regular expression
#        reg = "^%s$" % reference
#        stack.append({
#            attrname: {
#                "$not": re.compile(reg, re.IGNORECASE)
#            }
#        })
#
#    def add_mongo_filter_not_reg(self, stack, attribute, reference):
#        """
#        Transposes a regex not match operator filter into a mongo query
#
#        Before MongoDB version 4.0.7, $not does not support $regex
#        This, using bson.regex.Regex regular expressions is required
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        attrtype = self.get_mongo_attribute_type(attribute)
#        # Builds regular expression
#        reg = str(reference)
#        if attrtype is list:
#            stack.append({
#                attrname: {
#                    "$nin": [re.compile(reg)]
#                }
#            })
#        else:
#            stack.append({
#                attrname: {"$not": re.compile(reg)}
#            })
#
#    def add_mongo_filter_not_reg_ci(self, stack, attribute, reference):
#        """
#        Transposes a case insensitive regex not match operator filter into a
#        mongo query
#
#        Before MongoDB version 4.0.7, $not does not support $regex
#        This, using bson.regex.Regex regular expressions is required
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        attrtype = self.get_mongo_attribute_type(attribute)
#        # Builds regular expression
#        reg = str(reference)
#        if attrtype is list:
#            stack.append({
#                attrname: {
#                    "$nin": [re.compile(reg, re.IGNORECASE)]
#                }
#            })
#        else:
#            stack.append({
#                attrname: {
#                    "$not": re.compile(reg, re.IGNORECASE)
#                }
#            })
#
#    def add_mongo_filter_dummy(self, stack, attribute, reference):
#        """
#        Transposes a dummy (always true) operator filter into a mongo query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        stack.append({})
#
#    def add_mongo_filter_user(self, stack, attribute, username):
#        """
#        Add a filter limitting the output to hosts/services having the
#        username as contact.
#
#        :param list stack: The stack to append filter to
#        :param str username: The username to limit output to
#        """
#        stack.append({
#            attribute: {
#                "$in": [str(username)]
#            }
#        })
#
#    def add_mongo_aggregation_sum(self, stack, attribute, reference=None):
#        """
#        Transposes a stats sum aggregation into a mongo query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        stack.append([
#            {
#                "$group": {
#                    "_id": None,
#                    "result": {
#                        "$sum": "$%s" % attrname
#                    }
#                },
#            },
#            {
#                "$project": {
#                    "_id": 0,
#                    "result": 1
#                }
#            }
#        ])
#
#    def add_mongo_aggregation_max(self, stack, attribute, reference=None):
#        """
#        Transposes a stats max aggregation into a mongo query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        stack.append([
#            {
#                "$group": {
#                    "_id": None,
#                    "result": {
#                        "$max": "$%s" % attrname
#                    }
#                },
#            },
#            {
#                "$project": {
#                    "_id": 0,
#                    "result": 1
#                }
#            }
#        ])
#
#    def add_mongo_aggregation_min(self, stack, attribute, reference=None):
#        """
#        Transposes a stats min aggregation into a mongo query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        stack.append([
#            {
#                "$group": {
#                    "_id": "$item",
#                    "result": {
#                        "$min": "$%s" % attrname
#                    }
#                },
#            },
#            {
#                "$project": {
#                    "_id": 0,
#                    "result": 1
#                }
#            }
#        ])
#
#    def add_mongo_aggregation_avg(self, stack, attribute, reference=None):
#        """
#        Transposes a stats average aggregation into a mongo query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        attrname = self.get_mongo_attribute_name(attribute)
#        stack.append([
#            {
#                "$group": {
#                    "_id": None,
#                    "result": {
#                        "$avg": "$%s" % attrname
#                    }
#                },
#            },
#            {
#                "$project": {
#                    "_id": 0,
#                    "result": 1
#                }
#            }
#        ])
#
#    def add_mongo_aggregation_count(self, stack, attribute=None, reference=None):
#        """
#        Transposes a stats count aggregation into a mongo query
#
#        :param list stack: The stack to append filter to
#        :param str attribute: The attribute name to compare
#        :param str reference: The reference value to compare to
#        """
#        stack.append([
#            {
#                "$group": {
#                    "_id": None,
#                    "result": {
#                        "$sum": 1
#                    }
#                },
#            },
#            {
#                "$project": {
#                    "_id": 0,
#                    "result": 1
#                }
#            }
#        ])

    operator_mapping = {
        "=":  mongo_datamgr.add_filter_eq,
        "=~":  mongo_datamgr.add_filter_eq_ci,
        "~":  mongo_datamgr.add_filter_reg,
        "~~":  mongo_datamgr.add_filter_reg_ci,
        ">":  mongo_datamgr.add_filter_gt,
        ">=":  mongo_datamgr.add_filter_ge,
        "<":  mongo_datamgr.add_filter_lt,
        "<=":  mongo_datamgr.add_filter_le,
        "!=":  mongo_datamgr.add_filter_not_eq,
        "!=~":  mongo_datamgr.add_filter_not_eq_ci,
        "!~":  mongo_datamgr.add_filter_not_reg,
        "!~~":  mongo_datamgr.add_filter_not_reg_ci,
        "sum":  mongo_datamgr.add_aggregation_sum,
        "min":  mongo_datamgr.add_aggregation_min,
        "max":  mongo_datamgr.add_aggregation_max,
        "avg":  mongo_datamgr.add_aggregation_avg,
        "count":  mongo_datamgr.add_aggregation_count,
    }

    def add_filter(self, stack, operator, attribute, reference):
        """
        Builds a mongo filter from the comparison operation

        :param list stack: The stack to append filter to
        :param str operator: The comparison operator
        :param str attribute: The attribute name to compare
        :param str reference: The reference value to compare to

        """
        # Map livestatus attribute `name` to the object's name
        fct = self.operator_mapping.get(operator)
        # Matches operators
        if fct:
            fct(stack, self.table, attribute, reference)
        else:
            raise LiveStatusQueryError(452, 'invalid filter: %s' % line)

#    def stack_mongo_filter_and(self, stack, count):
#        """
#        Stacks the last `count` operations into an `and` group
#
#        :param list stack: The stack to append filter to
#        :param str table: The table the attribute is in
#        :param int count: The number of statements to stack
#        """
#        if len(stack) < count:
#            raise LiveStatusQueryError(452, 'No enough filters to stack into `and`')
#        and_filter = {
#            "$and": stack[-count:]
#        }
#        del stack[-count:]
#        stack.append(and_filter)
#
#    def stack_mongo_filter_or(self, stack, count):
#        """
#        Stacks the last `count` operations into an `or` group
#
#        :param list stack: The stack to append filter to
#        :param str table: The table the attribute is in
#        :param int count: The number of statements to stack
#        """
#        if len(stack) < count:
#            raise LiveStatusQueryError(452, 'No enough filters to stack into `or`')
#        or_filter = {
#            "$or": stack[-count:]
#        }
#        del stack[-count:]
#        stack.append(or_filter)
#
#    def stack_mongo_filter_negate(self, stack, count, wrap=True):
#        """
#        Inverts the logic of the previous filters stack
#
#        As there's no global $not operator in MongoDB query ($not can only
#        be applied to an attribute), we're forced to negate by inverting
#        the query logic itself.
#
#        :param list stack: The stack to append filter to
#        :param str table: The table the attribute is in
#        :param int count: The number of statements to negate
#        :param bool wrap: Should the result be wrapped in an "$or"
#        """
#        if not count:
#            count = len(stack)
#        if len(stack) < count:
#            raise LiveStatusQueryError(452, 'No enough filters to stack into `negate`')
#        # Negates each element in the stack
#        for i in range(len(stack)-count, len(stack)):
#            statement = stack[i]
#            if isinstance(statement, list):
#                raise LiveStatusQueryError(452, 'Cannot negate aggregation stats')
#            stack[i] = self.stack_mongo_filter_negate_statement(statement)
#        if wrap is True:
#            reversed_stack = list(stack[-count:])
#            del stack[-count:]
#            stack.append({
#                "$or": reversed_stack
#            })
#        return stack
#
#    def stack_mongo_filter_negate_statement(self, statement):
#        """
#        Inverts the logic of a single statement
#
#        As there's no global $not operator in MongoDB query ($not can only
#        be applied to an attribute), we're forced to negate by inverting
#        the query logic itself.
#
#        :param str table: The table the attribute is in
#        :param dict statement: The statement to negate
#        :rtype: dict
#        :return: The negated statement
#        """
#        reversed_operators = {
#            "$eq": "$ne",
#            "$ne": "$eq",
#            "$gt": "$le",
#            "$le": "$gt",
#            "$ge": "$lt",
#            "$lt": "$ge",
#            "$in": "$nin",
#            "$nin": "$in",
#            "$or": "$and",
#            "$and": "$or",
#        }
#        for attribute, comparator in list(statement.items()):
#            if attribute in ("$and", "$or"):
#                # Manages $and, $or, and other grouping statements
#                # Statement has pattern: {"$or": [...]} or {"$and": [...]}
#                # $or becomes $and and conversely
#                reversed_operator = reversed_operators[attribute]
#                stack = list(statement[attribute])
#                # There can't both $and or $or with another operartor
#                # Returning the value directly
#                return {
#                    reversed_operator: self.stack_mongo_filter_negate(
#                        stack=stack,
#                        count=len(stack),
#                        wrap=False
#                    )
#                }
#            # Statement has pattern: {field: comparator}
#            if isinstance(comparator, dict):
#                # Statement has pattern: {field: {"$eq": value}}
#                # {"$eq": value} becomes {"$ne": value} and so on...
#                for operator, value in list(comparator.items()):
#                    if operator == "$not":
#                        # Statement has pattern: {field: {"$not": value}}
#                        # {field: {"$not": value}} becomes {field: value}
#                        statement[attribute] = value
#                        break
#                    if operator not in reversed_operators:
#                        raise LiveStatusQueryError(452, 'Cannot negate statement %s' % statement)
#                    reversed_operator = reversed_operators[operator]
#                    del comparator[operator]
#                    comparator[reversed_operator] = value
#            else:
#                # Statement has pattern: {field: value}
#                # {field: value} becomes {field: {"$not": value}}
#                statement[attribute] = {
#                    "$not": statement[attribute]
#                }
#        return statement
