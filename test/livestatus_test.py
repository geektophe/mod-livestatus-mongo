#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Copyright (C) 2009-2010:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Sebastien Coavoux, s.coavoux@free.fr
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


#
# This file is used to test host- and service-downtimes.
#

import os
import sys
import time
import random
import unittest

from shinken.modulesctx import modulesctx
from shinken.objects.module import Module
from shinken_test import ShinkenTest
from pprint import pprint
from shinken.log import logger
import logging

if os.getenv("TEST_DEBUG") == "1" or True:
    logger.setLevel(logging.DEBUG)

sys.setcheckinterval(10000)

path = ".."
modulesctx.set_modulesdir(path)

livestatus_broker = modulesctx.get_module('module')
LiveStatus_broker = livestatus_broker.LiveStatus_broker
LiveStatus = livestatus_broker.LiveStatus

class LivestatusTestBase(ShinkenTest):

    cfg_file = 'etc/shinken_5r_10h_200s.cfg'

    def init_livestatus(self):
        modconf = Module({'module_name': 'LiveStatus2',
            'module_type': 'livestatus2',
            'port': str(50000 + os.getpid()),
            'host': '127.0.0.1',
            'socket': 'live',
            'name': 'test'
        })

        self.livestatus_broker = LiveStatus_broker(modconf)
        self.livestatus_broker.log = logger
        self.livestatus_broker.debug_output = []
        self.livestatus_broker.create_queues()
        self.livestatus_broker.init()
        self.livestatus_broker.livestatus = LiveStatus(
            datamgr=self.livestatus_broker.datamgr,
            return_queue=self.livestatus_broker.from_q
        )

    def update_broker(self, dodeepcopy=False):
        # The brok should be manage in the good order
        for brok in self.sched.brokers['Default-Broker']['broks']:
            if dodeepcopy:
                brok = copy.deepcopy(brok)
            brok.prepare()
            self.livestatus_broker.manage_brok(brok)
        self.sched.brokers['Default-Broker']['broks'] = []

    def setUp(self):
        start_setUp = time.time()
        self.setup_with_file(self.cfg_file)
        self.testid = str(os.getpid() + random.randint(1, 1000))
        self.init_livestatus()
        if os.getenv("TEST_CLEANUP_DATABASE") == "YES":
            print("Clearing database content")
            self.livestatus_broker.datamgr.clear_db()
        print("Cleaning old broks?")
        self.sched.conf.skip_initial_broks = False
        self.sched.brokers['Default-Broker'] = {'broks' : [], 'has_full_broks' : False}
        self.sched.fill_initial_broks('Default-Broker')

        self.update_broker()
        print("************* Overall Setup:", time.time() - start_setUp)
        # add use_aggressive_host_checking so we can mix exit codes 1 and 2
        # but still get DOWN state
        host = self.sched.hosts.find_by_name("test_host_000")
        host.__class__.use_aggressive_host_checking = 1

    def execute_and_assert(self, query, expected_result):
        """
        Executes a Livestatus query, and asserts the got result is the one
        expected.

        :param str query: The query to execute
        :param list expected_result: The result to match
        """
        # With memory backend
        print("\n***")
        print("Query:")
        print(query)
        response, _ = self.livestatus_broker.livestatus.handle_request(query)
        print("Response")
        print(response)
        pyresponse = eval(response)
        print("PyResponse")
        pprint(pyresponse)
        if callable(expected_result):
            expected_result(pyresponse)
        else:
            self.assertEqual(pyresponse, expected_result)
