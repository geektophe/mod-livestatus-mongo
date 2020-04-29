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

from shinken_test import unittest

from shinken_modules import TestConfig
from shinken.comment import Comment

from mock_livestatus import mock_livestatus_handle_request
from pprint import pprint


sys.setcheckinterval(10000)



@mock_livestatus_handle_request
class TestConfig(TestConfig):

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

    def test_simple_query(self):
        """
        Tests a simple query execution
        """
        # Exact match
        expected_result = [['test_host_001', 'pending_001']]
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Case insensitive match
        query = """GET hosts
Columns: name alias
Filter: name =~ TEST_host_001
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Regex exact match
        query = """GET hosts
Columns: name alias
Filter: name ~ test_[a-z]+_001
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Regex case insensitive match
        query = """GET hosts
Columns: name alias
Filter: name ~~ TEST_[a-z]+_001
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Miging several conditions
        query = """GET hosts
Columns: name alias
Filter: name ~~ TEST_[a-z]+_001
Filter: alias = pending_001
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Miging several conditions
        query = """GET hosts
Columns: name alias
Filter: name ~~ TEST_[a-z]+_001
Filter: alias = fake
OutputFormat: python
"""
        self.execute_and_assert(query, [])

        # Integer ge comparison
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: max_check_attempts >= 5
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Integer gt comparison
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: max_check_attempts > 5
OutputFormat: python
"""
        print("Just before execute")
        self.execute_and_assert(query, [])

        # Integer le comparison
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: max_check_attempts <= 5
OutputFormat: python
"""

        # Integer gt comparison
        self.execute_and_assert(query, expected_result)
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: max_check_attempts < 5
OutputFormat: python
"""
        self.execute_and_assert(query, [])

        # Not conditions

        def not_hosts_condition(result):
            self.assertNotIn(['test_host_001', 'pending_001'], result)
            self.assertIn(['test_host_002', 'down_002'], result)

        # Exact match
        query = """GET hosts
Columns: name alias
Filter: name != test_host_001
OutputFormat: python
"""
        self.execute_and_assert(query, not_hosts_condition)
        # Case insensitive match
        query = """GET hosts
Columns: name alias
Filter: name !=~ TEST_host_001
OutputFormat: python
"""
        self.execute_and_assert(query, not_hosts_condition)
        # Regex exact match
        query = """GET hosts
Columns: name alias
Filter: name !~ test_[a-z]+_001
OutputFormat: python
"""
        self.execute_and_assert(query, not_hosts_condition)
        # Regex case insensitive match
        query = """GET hosts
Columns: name alias
Filter: name !~~ TEST_[a-z]+_001
OutputFormat: python
"""
        self.execute_and_assert(query, not_hosts_condition)

        # Integer ge comparison
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: max_check_attempts !>= 5
OutputFormat: python
"""
        self.execute_and_assert(query, [])

        # Integer gt comparison
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: max_check_attempts !> 5
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Integer le comparison
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: max_check_attempts !<= 5
OutputFormat: python
"""
        self.execute_and_assert(query, [])

        # Integer gt comparison
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: max_check_attempts !< 5
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # List is empty
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: labels =
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # List is not empty
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: labels !=
OutputFormat: python
"""
        self.execute_and_assert(query, [])

        # List contains
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: notification_options >= u
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # List does not contain
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: notification_options < u
OutputFormat: python
"""
        self.execute_and_assert(query, [])

        # List contains (case insensitive)
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: notification_options <= U
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # List does not contains (case insensitive)
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: notification_options > U
OutputFormat: python
"""
        self.execute_and_assert(query, [])

        # List matches
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: notification_options ~ ^u$
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # List matches (case insensitive)
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: notification_options ~~ ^U$
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

    def test_nested_and_or_query(self):
        """
        Tests a simple query execution
        """
        host_005 = self.sched.hosts.find_by_name("test_host_001")
        self.assertEqual(host_005.host_name, "test_host_001")
        test_ok_00 = self.sched.services.find_srv_by_name_and_hostname("test_host_001", "test_ok_00")
        self.assertEqual(test_ok_00.host_name, "test_host_001")
        self.assertEqual(test_ok_00.service_description, "test_ok_00")

        # Get an host
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: name = test_host_002
Or: 2
OutputFormat: python
"""
        expected_result = [
            ['test_host_001', 'pending_001'],
            ['test_host_002', 'down_002']
        ]
        #self.execute_and_assert(query, expected_result)

        # Get a service
        query = """GET services
Columns: host_name description
Filter: host_name = test_host_001
Filter: host_name = test_host_002
Or: 2
Filter: description = test_ok_00
OutputFormat: python
"""
        expected_result = [
            ['test_host_001', 'test_ok_00'],
            ['test_host_002', 'test_ok_00']
        ]
        self.execute_and_assert(query, expected_result)

        query = """GET services
Columns: host_name description
Filter: host_name = test_host_001
Filter: host_name = test_host_002
Or: 2
Filter: description = test_ok_00
Filter: display_name = fake
Or:2
And: 2
OutputFormat: python
"""
        expected_result = [
            ['test_host_001', 'test_ok_00'],
            ['test_host_002', 'test_ok_00']
        ]
        self.execute_and_assert(query, expected_result)

        query = """GET services
Columns: host_name description
Filter: host_name = test_host_001
Filter: host_name = test_host_002
Or: 2
Filter: description = test_ok_00
Filter: display_name = fake
And:2
And: 2
OutputFormat: python
"""
        expected_result = []
        self.execute_and_assert(query, expected_result)

    def test_negate(self):
        expected_result = [['test_host_001', 'pending_001']]
        # List matches (case insensitive)
        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: notification_options ~~ ^U$
OutputFormat: python
"""
        expected_result = [['test_host_001', 'pending_001']]
        self.execute_and_assert(query, expected_result)

        def negate_hosts_condition(result):
            self.assertNotIn(['test_host_001', 'pending_001'], result)
            self.assertIn(['test_host_002', 'down_002'], result)

        query = """GET hosts
Columns: name alias
Filter: name = test_host_001
Filter: notification_options ~~ ^U$
Negate:
OutputFormat: python
"""
        self.execute_and_assert(query, negate_hosts_condition)

        query = """GET hosts
Columns: name alias
Filter: name != test_host_001
Filter: alias !~~ pending_001
Negate:2
Filter: notification_options < d
Filter: notification_options !~~ ^U$
Negate: 2
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        query = """GET hosts
Columns: name alias
Filter: name != test_host_001
Filter: alias !~~ pending_001
Negate:2
Filter: notification_options < d
Filter: notification_options !~~ ^U$
Negate: 2
Negate:
OutputFormat: python
"""
        self.execute_and_assert(query, negate_hosts_condition)


if __name__ == '__main__':
    #import cProfile
    command = """unittest.main()"""
    unittest.main()
