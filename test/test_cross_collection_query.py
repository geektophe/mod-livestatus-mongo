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
from livestatus.mongo_mapping import table_class_map
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

    def test_cross_collections_hosts(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()

        query = """GET hosts
Columns: name num_services num_services_ok num_services_hard_ok num_services_warn num_services_hard_warn num_services_crit num_services_hard_crit num_services_unknown num_services_hard_unknown worst_service_state worst_service_hard_state
Filter: name = test_host_005
OutputFormat: python
"""

        #                   H                 N   SO HO SW HW SC HC SU HU WS WH
        expected_result = [['test_host_005', 20, 0, 20, 0, 0, 0, 0, 0, 0, 0, 0]]
        self.execute_and_assert(query, expected_result)

        svc1 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_warning_02")
        svc2 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_warning_13")
        svc3 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_random_03")
        svc4 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_critical_11")
        svc5 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_unknown_08")
        svc6 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_random_06")
        svc7 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_flap_09")
        self.scheduler_loop(1, [[svc1, 1, 'W'], [svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C'], [svc7, 2, 'C']])
        self.scheduler_loop(2, [[svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C']])
        self.update_broker()

        #                   H                 N  SO  HO SW HW SC HC SU HU WS WH
        expected_result = [['test_host_005', 20, 0, 13, 1, 2, 1, 2, 0, 1, 2, 2]]
        self.execute_and_assert(query, expected_result)

    def test_host_all_attrs(self):
        query = """GET hosts
Filter: name = test_host_005
OutputFormat: python
"""

        def assert_column_count(result):
            mapping = table_class_map['hosts']
            self.assertEqual(len(result), 1)
            self.assertEqual(len(result[0]), len(mapping))

        self.execute_and_assert(query, assert_column_count)

    def test_cross_collections_services(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()

        query = """GET services
Columns: host_name host_alias host_state host_state_type host_plugin_output
Filter: host_name = test_host_005
Filter: description = test_ok_00
OutputFormat: python
"""

        expected_result = [['test_host_005', 'flap_005', 0, 1, 'UP']]
        self.execute_and_assert(query, expected_result)

        host = self.sched.hosts.find_by_name("test_host_005")
        self.scheduler_loop(1, [[host, 1, 'DOWN']])
        self.update_broker()

        expected_result = [['test_host_005', 'flap_005', 1, 0, 'DOWN']]
        self.execute_and_assert(query, expected_result)


    def test_cross_collections_hostgroups(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()

        query = """GET hostgroups
Columns: name num_hosts_pending num_hosts_unreach num_hosts_up num_hosts_down worst_host_state num_hosts num_services num_services_ok num_services_hard_ok num_services_warn num_services_hard_warn num_services_crit num_services_hard_crit num_services_unknown num_services_hard_unknown worst_service_state worst_service_hard_state
Filter: name = hostgroup_01
OutputFormat: python
"""

        expected_result = [['hostgroup_01', 0, 0, 2, 0, 0, 2, 40, 0, 40, 0, 0, 0, 0, 0, 0, 0, 0]]
        self.execute_and_assert(query, expected_result)

        svc1 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_warning_02")
        svc2 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_warning_13")
        svc3 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_random_03")
        svc4 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_critical_11")
        svc5 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_unknown_08")
        svc6 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_random_06")
        svc7 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_flap_09")
        self.scheduler_loop(1, [[svc1, 1, 'W'], [svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C'], [svc7, 2, 'C']])
        self.scheduler_loop(2, [[svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C']])

        host = self.sched.hosts.find_by_name("test_host_005")
        self.scheduler_loop(1, [[host, 1, 'DOWN']])
        self.update_broker()

        expected_result = [['hostgroup_01', 0, 0, 1, 0, 0, 2, 40, 0, 33, 1, 2, 1, 2, 0, 1, 2, 2]]
        self.execute_and_assert(query, expected_result)

    def test_cross_collections_servicegroup(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()

        query = """GET servicegroups
Columns: name num_hosts_pending num_hosts_unreach num_hosts_up num_hosts_down worst_host_state num_hosts num_services num_services_ok num_services_hard_ok num_services_warn num_services_hard_warn num_services_crit num_services_hard_crit num_services_unknown num_services_hard_unknown worst_service_state worst_service_hard_state
Filter: name = servicegroup_06
OutputFormat: python
"""

        expected_result = [['servicegroup_06', 0, 0, 2, 0, 0, 2, 40, 0, 40, 0, 0, 0, 0, 0, 0, 0, 0]]
        self.execute_and_assert(query, expected_result)

        svc1 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_warning_02")
        svc2 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_warning_13")
        svc3 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_random_03")
        svc4 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_critical_11")
        svc5 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_unknown_08")
        svc6 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_random_06")
        svc7 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_flap_09")
        self.scheduler_loop(1, [[svc1, 1, 'W'], [svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C'], [svc7, 2, 'C']])
        self.scheduler_loop(2, [[svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C']])

        host = self.sched.hosts.find_by_name("test_host_005")
        self.scheduler_loop(1, [[host, 1, 'DOWN']])
        self.update_broker()

        #                   H                 N  SO  HO SW HW SC HC SU HU WS WH
        expected_result = [['servicegroup_06', 0, 0, 1, 0, 0, 2, 40, 0, 33, 1, 2, 1, 2, 0, 1, 2, 2]]
        self.execute_and_assert(query, expected_result)

    def test_hostgroup_all_attrs(self):
        query = """GET hostgroups
Filter: name = hostgroup_01
OutputFormat: python
"""

        def assert_column_count(result):
            mapping = table_class_map['hostgroups']
            self.assertEqual(len(result), 1)
            self.assertEqual(len(result[0]), len(mapping))

        self.execute_and_assert(query, assert_column_count)

    def test_servicegroup_all_attrs(self):
        query = """GET servicegroups
Filter: name = servicegroup_01
OutputFormat: python
"""

        def assert_column_count(result):
            mapping = table_class_map['servicegroups']
            self.assertEqual(len(result), 1)
            self.assertEqual(len(result[0]), len(mapping))

        self.execute_and_assert(query, assert_column_count)


if __name__ == '__main__':
    #import cProfile
    command = """unittest.main()"""
    unittest.main()
