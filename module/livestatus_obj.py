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
import traceback
import cStringIO
import pymongo

from shinken.log import logger

from .livestatus_counters import LiveStatusCounters
from .livestatus_request import LiveStatusRequest
from .livestatus_response import LiveStatusResponse
from .livestatus_query_error import LiveStatusQueryError
from .livestatus_mongo_datamanager import datamgr as mongo_datamgr


_VALID_QUERIES_TYPE_SORTED = (
    # used in handle_request() to validate the components we get in one query/request.
    # each inner tuple is sorted alphabetically: command < query < wait
    ('command', ),  # there can be multiple commands also, special cased below..
    ('query', ),
    ('query', 'wait', ),
    ('command', 'query', ),
    ('command', 'query', 'wait', ),
)


def _is_valid_queries(queries_type):
    assert isinstance(queries_type, tuple)
    return (
        queries_type in _VALID_QUERIES_TYPE_SORTED
        # special case: we accept one or many commands, in one request:
        or all(qtype == 'command' for qtype in queries_type)
    )


class LiveStatus(object):
    """A class that represents the status of all objects in the broker

    """

    def __init__(self, datamgr, query_cache, db, pnp_path, return_queue, counters=None):
        self.datamgr = datamgr
        self.query_cache = query_cache
        self.db = db
        self.pnp_path = pnp_path
        self.return_queue = return_queue
        if counters is None:
            counters = LiveStatusCounters()
        self.counters = counters
        self.mongo_client = pymongo.MongoClient("localhost", 27017)
        self.mongo_datamgr = mongo_datamgr
        self.mongo_datamgr.load(self.mongo_client.livestatus)

    def handle_request(self, data):
        try:
            return self.handle_request_and_fail(data)
        except LiveStatusQueryError as err:
            # LiveStatusQueryError(404, table)
            # LiveStatusQueryError(450, column)
            code, output = err.args
        except Exception as err:
            logger.error(
                "[Livestatus] Unexpected error during process of request %r : %s",
                 data,
                 err
            )
            # Also show the exception
            trb = traceback.format_exc()
            logger.error("[Livestatus] Back trace of this exception: %s", trb)
            code = 500
            output = err
        # Ok now we can return something
        response = LiveStatusResponse()
        response.set_error(code, output)
        if 'fixed16' in data:
            response.responseheader = 'fixed16'
        return response.respond()

    def handle_request_and_fail(self, data):
        """Execute the livestatus request.

        This function creates a LiveStatusRequest instance, calls the parser,
        handles the execution of the request and formatting of the result.
        """
        request = LiveStatusRequest(
                data,
                self.datamgr,
                self.mongo_datamgr,
                self.db,
                self.pnp_path,
                self.return_queue,
                self.counters)
        request.parse_input(data)
        # sort alphabetically on the query type :
        queries = sorted(request.queries, key=lambda q: q.my_type)
        # have to tuple it for testing with 'in' in _is_valid_queries() just after:
        queries_type = tuple(query.my_type for query in queries)
        if not _is_valid_queries(queries_type):
            logger.error("[Livestatus] We currently do not handle this kind "
                         "of composed request: %s", queries_type)
            return '', False

        cur_idx = 0
        keepalive = False

        # process the command(s), if any.
        for query in queries:
            # as they are sorted alphabetically, once we get one which isn't a 'command'..
            if query.my_type != 'command':
                break   # then we are done.
            query.process_query()
            # according to Check_Mk, COMMAND doesn't require a response (argh!),
            # that is no response or more simply: an empty response:
            output = ''
            cur_idx += 1

        if 'wait' in queries_type:
            keepalive = True
            # we return  'wait' first and 'query' second..
            output = list(reversed(queries[cur_idx:]))
        elif len(queries[cur_idx:]):
            # last possibility :
            assert (
                1 == len(queries[cur_idx:])
                and query == queries[cur_idx] and query.my_type == 'query'
            )
            output, keepalive = query.process_query()
        else:
            output = ''  # no command, query, or anything could be parsed from the input data.

        logger.debug("[Livestatus] Request duration %.4fs" % (time.time() - request.tic))
        return output, keepalive

    def count_event(self, counter):
        self.counters.increment(counter)
