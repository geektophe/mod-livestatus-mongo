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

    def test_stats(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()
        svc1 = self.sched.services.find_srv_by_name_and_hostname("test_host_001", "test_warning_19")
        svc2 = self.sched.services.find_srv_by_name_and_hostname("test_host_003", "test_warning_03")
        svc3 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_warning_02")
        svc4 = self.sched.services.find_srv_by_name_and_hostname("test_host_000", "test_critical_03")
        svc5 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_critical_11")
        svc6 = self.sched.services.find_srv_by_name_and_hostname("test_host_007", "test_critical_02")
        svc7 = self.sched.services.find_srv_by_name_and_hostname("test_host_008", "test_critical_13")
        self.scheduler_loop(1, [[svc1, 1, 'W'], [svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C'], [svc7, 2, 'C']])
        self.update_broker()
        # 1993O, 3xW, 3xC, 1xU

        query = """GET services
Filter: contacts >= test_contact
Stats: state != 9999
Stats: state = 0
Stats: state = 1
Stats: state = 2
Stats: state = 3
OutputFormat: python"""

        expected_result = [[200, 193, 3, 3, 1]]
        self.execute_and_assert(query, expected_result)

        query = """GET services
Filter: contacts >= test_contact
Filter: state > 0
Stats: state = 1
Stats: state = 2
Stats: state = 3
Stats: max state
Stats: min state
Stats: sum state
Stats: avg state
OutputFormat: python"""

        def compare_stats_1(result):
            result = result.pop(0)
            self.assertEqual(result[:-1], [3, 3, 1, 3, 1, 12])
            self.assertEqual("%.02f" % result[-1], "1.71")

        self.execute_and_assert(query, compare_stats_1)

        query = """GET services
Filter: contacts >= test_contact
Filter: state > 0
Stats: state = 1
Stats: state = 2
Stats: state = 3
StatsOr:3
Stats: max_check_attempts = 3
StatsAnd:2
Stats: max state
Stats: min state
Stats: sum state
Stats: avg state
OutputFormat: python"""

        def compare_stats_2(result):
            result = result.pop(0)
            self.assertEqual(result[:-1], [7, 3, 1, 12])
            self.assertEqual("%.02f" % result[-1], "1.71")

        self.execute_and_assert(query, compare_stats_2)

        query = """GET services
Filter: contacts >= test_contact
Stats: state = 1
Stats: state = 2
Stats: state = 3
StatsOr:3
Stats: max_check_attempts = 3
StatsAnd:2
StatsNegate:
OutputFormat: python"""

        expected_result = [[193]]
        self.execute_and_assert(query, expected_result)

    def test_stats_hostsbygroup(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()

        query = """GET hostsbygroup
Filter: contacts >= test_contact
Stats: state != 9999
Stats: state = 0
Stats: state = 1
Stats: state = 2
OutputFormat: python"""

        expected_result = [
            ['flap', 1, 1, 0, 0],
            ['random', 1, 1, 0, 0],
            ['up', 5, 5, 0, 0],
            ['down', 1, 1, 0, 0],
            ['hostgroup_04', 2, 2, 0, 0],
            ['hostgroup_05', 2, 2, 0, 0],
            ['hostgroup_02', 2, 2, 0, 0],
            ['hostgroup_03', 2, 2, 0, 0],
            ['hostgroup_01', 2, 2, 0, 0],
            ['router', 5, 5, 0, 0],
            ['pending', 2, 2, 0, 0]
        ]

        def assert_in(result):
            for r in expected_result:
                self.assertIn(r, result)

        self.execute_and_assert(query, assert_in)

        query = """GET hostsbygroup
Columns: hostgroup_name hostgroup_alias
Filter: contacts >= test_contact
Stats: state != 9999
Stats: state = 0
Stats: state = 1
Stats: state = 2
OutputFormat: python"""

        expected_result = [
            ['flap', 'All Flapping Hosts', 1, 1, 0, 0],
            ['random', 'All Random Hosts', 1, 1, 0, 0],
            ['up', 'All Up Hosts', 5, 5, 0, 0],
            ['down', 'All Down Hosts', 1, 1, 0, 0],
            ['hostgroup_04', 'hostgroup_alias_04', 2, 2, 0, 0],
            ['hostgroup_05', 'hostgroup_alias_05', 2, 2, 0, 0],
            ['hostgroup_02', 'hostgroup_alias_02', 2, 2, 0, 0],
            ['hostgroup_03', 'hostgroup_alias_03', 2, 2, 0, 0],
            ['hostgroup_01', 'hostgroup_alias_01', 2, 2, 0, 0],
            ['router', 'All Router Hosts', 5, 5, 0, 0],
            ['pending', 'All Pending Hosts', 2, 2, 0, 0]
        ]

        self.execute_and_assert(query, assert_in)

        host1 = self.sched.hosts.find_by_name("test_host_003")
        host2 = self.sched.hosts.find_by_name("test_host_005")
        host3 = self.sched.hosts.find_by_name("test_host_007")
        host4 = self.sched.hosts.find_by_name("test_host_008")
        self.scheduler_loop(5, [[host1, 1, 'D'], [host2, 1, 'D'], [host3, 2, 'U'], [host4, 2, 'U']])
        self.update_broker()

        expected_result = [
            ['flap', 'All Flapping Hosts', 1, 0, 1, 0],
            ['random', 'All Random Hosts', 1, 0, 1, 0],
            ['up', 'All Up Hosts', 5, 3, 2, 0],
            ['down', 'All Down Hosts', 1, 1, 0, 0],
            ['hostgroup_04', 'hostgroup_alias_04', 2, 0, 2, 0],
            ['hostgroup_05', 'hostgroup_alias_05', 2, 2, 0, 0],
            ['hostgroup_02', 'hostgroup_alias_02', 2, 2, 0, 0],
            ['hostgroup_03', 'hostgroup_alias_03', 2, 1, 1, 0],
            ['hostgroup_01', 'hostgroup_alias_01', 2, 1, 1, 0],
            ['router', 'All Router Hosts', 5, 5, 0, 0],
            ['pending', 'All Pending Hosts', 2, 2, 0, 0]
        ]

        self.execute_and_assert(query, assert_in)

        query = """GET hostsbygroup
Columns: hostgroup_name hostgroup_alias
Filter: contacts >= test_contact
Stats: state != 9999
Stats: state = 1
Stats: state = 2
Stats: max state
Stats: min state
Stats: sum state
Stats: avg state
OutputFormat: python"""

        expected_result = [
            ['flap', 'All Flapping Hosts', 1, 1, 0, 1, 1, 1, 1.0],
            ['random', 'All Random Hosts', 1, 1, 0, 1, 1, 1, 1.0],
            ['up', 'All Up Hosts', 5, 2, 0, 1, 0, 2, 0.4],
            ['down', 'All Down Hosts', 1, 0, 0, 0, 0, 0, 0.0],
            ['hostgroup_04', 'hostgroup_alias_04', 2, 2, 0, 1, 1, 2, 1.0],
            ['hostgroup_05', 'hostgroup_alias_05', 2, 0, 0, 0, 0, 0, 0.0],
            ['hostgroup_02', 'hostgroup_alias_02', 2, 0, 0, 0, 0, 0, 0.0],
            ['hostgroup_03', 'hostgroup_alias_03', 2, 1, 0, 1, 0, 1, 0.5],
            ['hostgroup_01', 'hostgroup_alias_01', 2, 1, 0, 1, 0, 1, 0.5],
            ['router', 'All Router Hosts', 5, 0, 0, 0, 0, 0, 0.0],
            ['pending', 'All Pending Hosts', 2, 0, 0, 0, 0, 0, 0.0]
        ]

        self.execute_and_assert(query, assert_in)

        query = """GET hostsbygroup
Filter: contacts >= test_contact
Columns: hostgroup_name hostgroup_alias
Stats: state != 9999
Stats: state = 1
Stats: state = 2
StatsOr:3
Stats: max_check_attempts = 5
StatsAnd:2
Stats: max state
Stats: min state
Stats: sum state
Stats: avg state
OutputFormat: python"""

        expected_result = [
            ['flap', 'All Flapping Hosts', 1, 1, 1, 1, 1.0],
            ['random', 'All Random Hosts', 1, 1, 1, 1, 1.0],
            ['up', 'All Up Hosts', 5, 1, 0, 2, 0.4],
            ['down', 'All Down Hosts', 1, 0, 0, 0, 0.0],
            ['hostgroup_04', 'hostgroup_alias_04', 2, 1, 1, 2, 1.0],
            ['hostgroup_05', 'hostgroup_alias_05', 2, 0, 0, 0, 0.0],
            ['hostgroup_02', 'hostgroup_alias_02', 2, 0, 0, 0, 0.0],
            ['hostgroup_03', 'hostgroup_alias_03', 2, 1, 0, 1, 0.5],
            ['hostgroup_01', 'hostgroup_alias_01', 2, 1, 0, 1, 0.5],
            ['router', 'All Router Hosts', 5, 0, 0, 0, 0.0],
            ['pending', 'All Pending Hosts', 2, 0, 0, 0, 0.0]
        ]

        self.execute_and_assert(query, assert_in)

    def test_stats_servicesbygroup(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()

        query = """GET servicesbygroup
Filter: contacts >= test_contact
Stats: state != 9999
Stats: state = 0
Stats: state = 1
Stats: state = 2
Stats: state = 3
OutputFormat: python"""

        expected_result = [
            ['critical', 9, 9, 0, 0, 0],
            ['flap', 10, 10, 0, 0, 0],
            ['ok', 99, 99, 0, 0, 0],
            ['pending', 8, 8, 0, 0, 0],
            ['random', 51, 51, 0, 0, 0],
            ['servicegroup_01', 40, 40, 0, 0, 0],
            ['servicegroup_02', 40, 40, 0, 0, 0],
            ['servicegroup_03', 40, 40, 0, 0, 0],
            ['servicegroup_04', 40, 40, 0, 0, 0],
            ['servicegroup_05', 40, 40, 0, 0, 0],
            ['servicegroup_06', 40, 40, 0, 0, 0],
            ['unknown', 7, 7, 0, 0, 0],
            ['warning', 16, 16, 0, 0, 0]
        ]

        def assert_in(result):
            for r in expected_result:
                self.assertIn(r, result)

        self.execute_and_assert(query, assert_in)

        query = """GET servicesbygroup
Columns: servicegroup_name servicegroup_alias
Filter: contacts >= test_contact
Stats: state != 9999
Stats: state = 0
Stats: state = 1
Stats: state = 2
Stats: state = 3
OutputFormat: python"""

        expected_result = [
            ['critical', 'All Critical Services', 9, 9, 0, 0, 0],
            ['flap', 'All Flapping Services', 10, 10, 0, 0, 0],
            ['ok', 'All Ok Services', 99, 99, 0, 0, 0],
            ['pending', 'All Pending Services', 8, 8, 0, 0, 0],
            ['random', 'All Random Services', 51, 51, 0, 0, 0],
            ['servicegroup_01', 'servicegroup_alias_01', 40, 40, 0, 0, 0],
            ['servicegroup_02', 'servicegroup_alias_02', 40, 40, 0, 0, 0],
            ['servicegroup_03', 'servicegroup_alias_03', 40, 40, 0, 0, 0],
            ['servicegroup_04', 'servicegroup_alias_04', 40, 40, 0, 0, 0],
            ['servicegroup_05', 'servicegroup_alias_05', 40, 40, 0, 0, 0],
            ['servicegroup_06', 'servicegroup_alias_06', 40, 40, 0, 0, 0],
            ['unknown', 'All Unknown Services', 7, 7, 0, 0, 0],
            ['warning', 'All Warning Services', 16, 16, 0, 0, 0]
        ]

        self.execute_and_assert(query, assert_in)

        svc1 = self.sched.services.find_srv_by_name_and_hostname("test_host_001", "test_warning_19")
        svc2 = self.sched.services.find_srv_by_name_and_hostname("test_host_003", "test_warning_03")
        svc3 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_warning_02")
        svc4 = self.sched.services.find_srv_by_name_and_hostname("test_host_000", "test_critical_03")
        svc5 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_critical_11")
        svc6 = self.sched.services.find_srv_by_name_and_hostname("test_host_007", "test_critical_02")
        svc7 = self.sched.services.find_srv_by_name_and_hostname("test_host_008", "test_critical_13")
        self.scheduler_loop(1, [[svc1, 1, 'W'], [svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C'], [svc7, 2, 'C']])
        self.update_broker()

        expected_result = [
            ['critical', 'All Critical Services', 9, 5, 0, 3, 1],
            ['flap', 'All Flapping Services', 10, 10, 0, 0, 0],
            ['ok', 'All Ok Services', 99, 99, 0, 0, 0],
            ['pending', 'All Pending Services', 8, 8, 0, 0, 0],
            ['random', 'All Random Services', 51, 51, 0, 0, 0],
            ['servicegroup_01', 'servicegroup_alias_01', 40, 40, 0, 0, 0],
            ['servicegroup_02', 'servicegroup_alias_02', 40, 39, 0, 0, 1],
            ['servicegroup_03', 'servicegroup_alias_03', 40, 38, 1, 1, 0],
            ['servicegroup_04', 'servicegroup_alias_04', 40, 37, 1, 2, 0],
            ['servicegroup_05', 'servicegroup_alias_05', 40, 39, 1, 0, 0],
            ['servicegroup_06', 'servicegroup_alias_06', 40, 38, 1, 0, 1],
            ['unknown', 'All Unknown Services', 7, 7, 0, 0, 0],
            ['warning', 'All Warning Services', 16, 13, 3, 0, 0]
        ]

        self.execute_and_assert(query, assert_in)

        query = """GET servicesbygroup
Columns: servicegroup_name servicegroup_alias
Filter: contacts >= test_contact
Stats: state != 9999
Stats: state = 0
Stats: state = 1
Stats: state = 2
Stats: state = 3
Stats: max state
Stats: min state
Stats: sum state
Stats: avg state
OutputFormat: python"""

        expected_result = [
            ['critical', 'All Critical Services', 9, 5, 0, 3, 1, 3, 0, 9, 1.0],
            ['flap', 'All Flapping Services', 10, 10, 0, 0, 0, 0, 0, 0, 0.0],
            ['ok', 'All Ok Services', 99, 99, 0, 0, 0, 0, 0, 0, 0.0],
            ['pending', 'All Pending Services', 8, 8, 0, 0, 0, 0, 0, 0, 0.0],
            ['random', 'All Random Services', 51, 51, 0, 0, 0, 0, 0, 0, 0.0],
            ['servicegroup_01', 'servicegroup_alias_01', 40, 40, 0, 0, 0, 0, 0, 0, 0.0],
            ['servicegroup_02', 'servicegroup_alias_02', 40, 39, 0, 0, 1, 3, 0, 3, 0.075],
            ['servicegroup_03', 'servicegroup_alias_03', 40, 38, 1, 1, 0, 2, 0, 3, 0.075],
            ['servicegroup_04', 'servicegroup_alias_04', 40, 37, 1, 2, 0, 2, 0, 5, 0.125],
            ['servicegroup_05', 'servicegroup_alias_05', 40, 39, 1, 0, 0, 1, 0, 1, 0.025],
            ['servicegroup_06', 'servicegroup_alias_06', 40, 38, 1, 0, 1, 3, 0, 4, 0.1],
            ['unknown', 'All Unknown Services', 7, 7, 0, 0, 0, 0, 0, 0, 0.0],
            ['warning', 'All Warning Services', 16, 13, 3, 0, 0, 1, 0, 3, 0.1875]
        ]

        self.execute_and_assert(query, assert_in)

        query = """GET servicesbygroup
Columns: servicegroup_name servicegroup_alias
Filter: contacts >= test_contact
Stats: state != 9999
Stats: state = 1
Stats: state = 2
StatsOr:3
Stats: max_check_attempts = 3
StatsAnd:2
Stats: max state
Stats: min state
Stats: sum state
Stats: avg state
OutputFormat: python"""

        expected_result = [
            ['critical', 'All Critical Services', 9, 3, 0, 9, 1.0],
	    ['flap', 'All Flapping Services', 10, 0, 0, 0, 0.0],
	    ['ok', 'All Ok Services', 99, 0, 0, 0, 0.0],
	    ['pending', 'All Pending Services', 8, 0, 0, 0, 0.0],
	    ['random', 'All Random Services', 51, 0, 0, 0, 0.0],
	    ['servicegroup_01', 'servicegroup_alias_01', 40, 0, 0, 0, 0.0],
	    ['servicegroup_02', 'servicegroup_alias_02', 40, 3, 0, 3, 0.075],
	    ['servicegroup_03', 'servicegroup_alias_03', 40, 2, 0, 3, 0.075],
	    ['servicegroup_04', 'servicegroup_alias_04', 40, 2, 0, 5, 0.125],
	    ['servicegroup_05', 'servicegroup_alias_05', 40, 1, 0, 1, 0.025],
	    ['servicegroup_06', 'servicegroup_alias_06', 40, 3, 0, 4, 0.1],
	    ['unknown', 'All Unknown Services', 7, 0, 0, 0, 0.0],
	    ['warning', 'All Warning Services', 16, 1, 0, 3, 0.1875]
        ]

        self.execute_and_assert(query, assert_in)

    def test_stats_servicesbyhostgroup(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()

        query = """GET servicesbyhostgroup
Filter: contacts >= test_contact
Stats: state != 9999
Stats: state = 0
Stats: state = 1
Stats: state = 2
Stats: state = 3
OutputFormat: python"""

        expected_result = [
            ['down', 20, 20, 0, 0, 0],
            ['flap', 20, 20, 0, 0, 0],
            ['hostgroup_01', 40, 40, 0, 0, 0],
            ['hostgroup_02', 40, 40, 0, 0, 0],
            ['hostgroup_03', 40, 40, 0, 0, 0],
            ['hostgroup_04', 40, 40, 0, 0, 0],
            ['hostgroup_05', 40, 40, 0, 0, 0],
            ['pending', 40, 40, 0, 0, 0],
            ['random', 20, 20, 0, 0, 0],
            ['up', 100, 100, 0, 0, 0]
        ]

        def assert_in(result):
            for r in expected_result:
                self.assertIn(r, result)

        query = """GET servicesbyhostgroup
Columns: hostgroup_name hostgroup_alias
Filter: contacts >= test_contact
Stats: state != 9999
Stats: state = 0
Stats: state = 1
Stats: state = 2
Stats: state = 3
OutputFormat: python"""

        expected_result = [
            ['down', 'All Down Hosts', 20, 20, 0, 0, 0],
            ['flap', 'All Flapping Hosts', 20, 20, 0, 0, 0],
            ['hostgroup_01', 'hostgroup_alias_01', 40, 40, 0, 0, 0],
            ['hostgroup_02', 'hostgroup_alias_02', 40, 40, 0, 0, 0],
            ['hostgroup_03', 'hostgroup_alias_03', 40, 40, 0, 0, 0],
            ['hostgroup_04', 'hostgroup_alias_04', 40, 40, 0, 0, 0],
            ['hostgroup_05', 'hostgroup_alias_05', 40, 40, 0, 0, 0],
            ['pending', 'All Pending Hosts', 40, 40, 0, 0, 0],
            ['random', 'All Random Hosts', 20, 20, 0, 0, 0],
            ['up', 'All Up Hosts', 100, 100, 0, 0, 0]
        ]

        self.execute_and_assert(query, assert_in)

        svc1 = self.sched.services.find_srv_by_name_and_hostname("test_host_001", "test_warning_19")
        svc2 = self.sched.services.find_srv_by_name_and_hostname("test_host_003", "test_warning_03")
        svc3 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_warning_02")
        svc4 = self.sched.services.find_srv_by_name_and_hostname("test_host_000", "test_critical_03")
        svc5 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_critical_11")
        svc6 = self.sched.services.find_srv_by_name_and_hostname("test_host_007", "test_critical_02")
        svc7 = self.sched.services.find_srv_by_name_and_hostname("test_host_008", "test_critical_13")
        self.scheduler_loop(1, [[svc1, 1, 'W'], [svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C'], [svc7, 2, 'C']])
        self.update_broker()

        expected_result = [
            ['down', 'All Down Hosts', 20, 20, 0, 0, 0],
            ['flap', 'All Flapping Hosts', 20, 18, 1, 0, 1],
            ['hostgroup_01', 'hostgroup_alias_01', 40, 37, 1, 1, 1],
            ['hostgroup_02', 'hostgroup_alias_02', 40, 39, 1, 0, 0],
            ['hostgroup_03', 'hostgroup_alias_03', 40, 39, 0, 1, 0],
            ['hostgroup_04', 'hostgroup_alias_04', 40, 38, 1, 1, 0],
            ['hostgroup_05', 'hostgroup_alias_05', 40, 40, 0, 0, 0],
            ['pending', 'All Pending Hosts', 40, 39, 1, 0, 0],
            ['random', 'All Random Hosts', 20, 19, 0, 1, 0],
            ['up', 'All Up Hosts', 100, 97, 1, 2, 0]
        ]

        self.execute_and_assert(query, assert_in)

        query = """GET servicesbyhostgroup
Columns: hostgroup_name hostgroup_alias
Filter: contacts >= test_contact
Stats: state != 9999
Stats: state = 0
Stats: state = 1
Stats: state = 2
Stats: state = 3
Stats: max state
Stats: min state
Stats: sum state
Stats: avg state
OutputFormat: python"""

        expected_result = [
            ['down', 'All Down Hosts', 20, 20, 0, 0, 0, 0, 0, 0, 0.0],
            ['flap', 'All Flapping Hosts', 20, 18, 1, 0, 1, 3, 0, 4, 0.2],
            ['hostgroup_01', 'hostgroup_alias_01', 40, 37, 1, 1, 1, 3, 0, 6, 0.15],
            ['hostgroup_02', 'hostgroup_alias_02', 40, 39, 1, 0, 0, 1, 0, 1, 0.025],
            ['hostgroup_03', 'hostgroup_alias_03', 40, 39, 0, 1, 0, 2, 0, 2, 0.05],
            ['hostgroup_04', 'hostgroup_alias_04', 40, 38, 1, 1, 0, 2, 0, 3, 0.075],
            ['hostgroup_05', 'hostgroup_alias_05', 40, 40, 0, 0, 0, 0, 0, 0, 0.0],
            ['pending', 'All Pending Hosts', 40, 39, 1, 0, 0, 1, 0, 1, 0.025],
            ['random', 'All Random Hosts', 20, 19, 0, 1, 0, 2, 0, 2, 0.1],
            ['up', 'All Up Hosts', 100, 97, 1, 2, 0, 2, 0, 5, 0.05]
        ]

        self.execute_and_assert(query, assert_in)

        query = """GET servicesbyhostgroup
Columns: hostgroup_name hostgroup_alias
Filter: contacts >= test_contact
Stats: state != 9999
Stats: state = 1
Stats: state = 2
StatsOr:3
Stats: max_check_attempts = 3
StatsAnd:2
Stats: max state
Stats: min state
Stats: sum state
Stats: avg state
OutputFormat: python"""

        expected_result = [
            ['down', 'All Down Hosts', 20, 0, 0, 0, 0.0],
	    ['flap', 'All Flapping Hosts', 20, 3, 0, 4, 0.2],
	    ['hostgroup_01', 'hostgroup_alias_01', 40, 3, 0, 6, 0.15],
	    ['hostgroup_02', 'hostgroup_alias_02', 40, 1, 0, 1, 0.025],
	    ['hostgroup_03', 'hostgroup_alias_03', 40, 2, 0, 2, 0.05],
	    ['hostgroup_04', 'hostgroup_alias_04', 40, 2, 0, 3, 0.075],
	    ['hostgroup_05', 'hostgroup_alias_05', 40, 0, 0, 0, 0.0],
	    ['pending', 'All Pending Hosts', 40, 1, 0, 1, 0.025],
	    ['random', 'All Random Hosts', 20, 2, 0, 2, 0.1],
	    ['up', 'All Up Hosts', 100, 2, 0, 5, 0.05]
        ]

        self.execute_and_assert(query, assert_in)


if __name__ == '__main__':
    #import cProfile
    command = """unittest.main()"""
    unittest.main()
