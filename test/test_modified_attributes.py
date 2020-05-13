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
import logging

from shinken_test import unittest

from shinken_modules import TestConfig
from shinken.comment import Comment
from shinken.log import logger
logger.setLevel(logging.DEBUG)

from mock_livestatus import mock_livestatus_handle_request
from pprint import pprint


sys.setcheckinterval(10000)



@mock_livestatus_handle_request
class TestConfigBig(TestConfig):
    def setUp(self):
        start_setUp = time.time()
        self.setup_with_file('etc/shinken_5r_10h_200s.cfg')
        Comment.id = 1
        self.testid = str(os.getpid() + random.randint(1, 1000))
        self.init_livestatus()
        print "Cleaning old broks?"
        self.sched.conf.skip_initial_broks = False
        self.sched.brokers['Default-Broker'] = {'broks' : [], 'has_full_broks' : False}
        self.sched.fill_initial_broks('Default-Broker')

        self.update_broker()
        print "************* Overall Setup:", time.time() - start_setUp
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

    def test_modified_attributes_host(self):
        cmd = '[%lu] CHANGE_NORMAL_HOST_CHECK_INTERVAL;test_host_005;600' % time.time()
        self.sched.run_external_command(cmd)
        cmd = '[%lu] CHANGE_RETRY_HOST_CHECK_INTERVAL;test_host_005;120' % time.time()
        self.sched.run_external_command(cmd)
        self.scheduler_loop(1, [], do_sleep=False)  # push the downtime notification
        time.sleep(10)
        self.update_broker()

        query = """GET hosts
Columns: name modified_attributes modified_attributes_list
Filter: name = test_host_005
OutputFormat: python
"""

        expected_result = [
            ['test_host_005', 3072, ['check_interval', 'retry_interval']]
        ]

        self.execute_and_assert(query, expected_result)

        query = """GET services
Columns: host_name description modified_attributes modified_attributes_list host_modified_attributes host_modified_attributes_list
Filter: host_name = test_host_005
Filter: description = test_ok_00
OutputFormat: python
"""

        expected_result = [
            ['test_host_005', 'test_ok_00', 0, [], 3072, ['check_interval', 'retry_interval']]
        ]

        self.execute_and_assert(query, expected_result)

    def test_modified_attributes_srevice(self):
        cmd = '[%lu] CHANGE_NORMAL_SVC_CHECK_INTERVAL;test_host_005;test_ok_00;600' % time.time()
        self.sched.run_external_command(cmd)
        cmd = '[%lu] CHANGE_RETRY_SVC_CHECK_INTERVAL;test_host_005;test_ok_00;120' % time.time()
        self.sched.run_external_command(cmd)
        self.scheduler_loop(1, [], do_sleep=False)  # push the downtime notification
        time.sleep(10)
        self.update_broker()

        query = """GET services
Columns: host_name description modified_attributes modified_attributes_list
Filter: host_name = test_host_005
Filter: description = test_ok_00
OutputFormat: python
"""

        expected_result = [
            ['test_host_005', 'test_ok_00', 3072, ['check_interval', 'retry_interval']]
        ]
        self.execute_and_assert(query, expected_result)


if __name__ == '__main__':
    #import cProfile
    command = """unittest.main()"""
    unittest.main()
