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

import time
import os

from shinken.log import logger
from livestatus_mongo_query import LiveStatusQuery
from livestatus_mongo_response import LiveStatusResponse
from livestatus_constraints import LiveStatusConstraints
from livestatus_query_metainfo import LiveStatusQueryMetainfo


class LiveStatusWaitQuery(LiveStatusQuery):

    my_type = 'wait'

    def __init__(self, *args, **kwargs):
        super(LiveStatusWaitQuery, self).__init__(*args, **kwargs)
        self.response = LiveStatusResponse()
        self.wait_start = time.time()
        self.wait_timeout = 0
        self.wait_trigger = 'all'

    def parse_input(self, data):
        """Parse the lines of a livestatus request.

        This function looks for keywords in input lines and
        sets the attributes of the request object.
        WaitCondition statements are written into the metafilter string as if they
        were ordinary Filter:-statements. (metafilter is then used for a MetaData object)

        """
        metafilter = ""
        for line in data.splitlines():
            line = line.strip()
            # Tools like NagVis send KEYWORK:option, and we prefer to have
            # a space following the:
            if ':' in line and ' ' not in line:
                line = line.replace(':', ': ')
            keyword = line.split(' ')[0].rstrip(':')
            if keyword == 'GET':  # Get the name of the base table
                _, self.table = self.split_command(line)
                metafilter += "GET %s\n" % self.table
            elif keyword == 'WaitObject':  # Pick a specific object by name
                _, item = self.split_option(line)
                # It's like Filter: name = %s
                # Only for services it's host<blank>servicedesc
                if self.table == 'services':
                    if ';' in item:
                        host_name, service_description = item.split(';', 1)
                    else:
                        host_name, service_description = item.split(' ', 1)
                    self.add_filter(self.filters_stack, '=', 'name', host_name)
                    self.add_filter(
                        self.filters_stack,
                        '=',
                        'description',
                        service_description
                    )
                    self.datamgr.stack_filter_and(
                        self.filters_stack,
                        self.table,
                        2
                    )
                else:
                    self.add_filter(self.filters_stack, '=', 'name', item)
            elif keyword == 'WaitCondition':
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

            elif keyword == 'WaitConditionAnd':
                # Take the last andnum functions from the stack
                # Construct a new function which makes a logical and
                # Put the function back onto the stack
                self.datamgr.stack_filter_and(
                    self.filters_stack,
                    self.table,
                    andnum
                )
            elif keyword == 'WaitConditionOr':
                _, ornum = self.split_option(line)
                # Take the last ornum functions from the stack
                # Construct a new function which makes a logical or
                # Put the function back onto the stack
                self.datamgr.stack_filter_or(
                    self.filters_stack,
                    self.table,
                    ornum
                )
            elif keyword == 'WaitTimeout':
                _, self.wait_timeout = self.split_option(line)
                self.wait_timeout = int(self.wait_timeout) / 1000
            else:
                # This line is not valid or not implemented
                logger.warning("[Livestatus Wait Query] Received a line of input "
                               "which i can't handle: '%s'", line)

    def condition_fulfilled(self):
        '''
        :return: True if the WaitQuery condition is fulfilled.
                 False otherwise.
        The result of launch_query is non-empty when an item matches the filter criteria
        '''
        items = self.launch_query()
        if items:
            return True
        else:
            return False
