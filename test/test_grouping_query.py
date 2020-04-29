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

    def test_hostsbygroup(self):
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
Columns: name hostgroup_name hostgroup_alias
Filter: contacts >= test_contact
Filter: name = test_host_005
OutputFormat: python"""

        expected_result = [
            ['test_host_005', 'flap', 'All Flapping Hosts'],
            ['test_host_005', 'hostgroup_01', 'hostgroup_alias_01']
        ]

        self.execute_and_assert(query, expected_result)

        query = """GET hostsbygroup
Columns: name hostgroup_name hostgroup_alias hostgroup_num_hosts_up hostgroup_num_services_warn hostgroup_num_services_hard_unknown hostgroup_num_services hostgroup_num_services_crit hostgroup_num_hosts_pending hostgroup_num_hosts_down hostgroup_num_services_hard_crit hostgroup_num_services_hard_warn hostgroup_num_services_unknown hostgroup_num_services_pending hostgroup_num_hosts hostgroup_num_services_ok hostgroup_num_services_hard_ok hostgroup_num_hosts_unreach
Filter: groups >= hostgroup_01
Filter: groups >= hostgroup_02
Or: 2
OutputFormat: python
"""

        expected_result = [
            ['test_host_000', 'hostgroup_01', 'hostgroup_alias_01', 2, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 2, 0, 40, 0],
            ['test_host_005', 'hostgroup_01', 'hostgroup_alias_01', 2, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 2, 0, 40, 0],
            ['test_host_001', 'hostgroup_02', 'hostgroup_alias_02', 2, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 2, 0, 40, 0],
            ['test_host_006', 'hostgroup_02', 'hostgroup_alias_02', 2, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 2, 0, 40, 0]
        ]

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

        expected_result = [
            ['test_host_000', 'hostgroup_01', 'hostgroup_alias_01', 1, 1, 1, 40, 1, 0, 0, 2, 2, 0, 0, 2, 0, 33, 0],
            ['test_host_005', 'hostgroup_01', 'hostgroup_alias_01', 1, 1, 1, 40, 1, 0, 0, 2, 2, 0, 0, 2, 0, 33, 0],
            ['test_host_001', 'hostgroup_02', 'hostgroup_alias_02', 2, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 2, 0, 40, 0],
            ['test_host_006', 'hostgroup_02', 'hostgroup_alias_02', 2, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 2, 0, 40, 0]
        ]

        self.execute_and_assert(query, expected_result)

    def test_servicesbygroup(self):
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
Columns: host_name description servicegroup_name servicegroup_alias
Filter: contacts >= test_contact
Filter: host_name = test_host_005
Filter: description = test_ok_00
OutputFormat: python"""

        expected_result = [
            ['test_host_005', 'test_ok_00', 'ok', 'All Ok Services'],
            ['test_host_005', 'test_ok_00', 'servicegroup_01', 'servicegroup_alias_01'],
            ['test_host_005', 'test_ok_00', 'servicegroup_06', 'servicegroup_alias_06']
        ]

        def assert_in(result):
            for r in expected_result:
                self.assertIn(r, result)

        self.execute_and_assert(query, assert_in)

        query = """GET servicesbygroup
Columns: host_name name description servicegroup_name servicegroup_alias servicegroup_num_services_warn servicegroup_num_services_hard_unknown servicegroup_num_services servicegroup_num_services_crit servicegroup_num_services_hard_crit servicegroup_num_services_hard_warn servicegroup_num_services_unknown servicegroup_num_services_pending servicegroup_num_hosts servicegroup_num_services_ok servicegroup_num_services_hard_ok servicegroup_num_hosts_unreach
Filter: groups >= servicegroup_01
Filter: groups >= servicegroup_02
Or: 2
OutputFormat: python
"""

        expected_result = [
         ['test_host_005', 'test_critical_11', 'servicegroup_02', 'servicegroup_alias_02', 0, 40, 0, 0, 0, 0, 0, 0, 40],
        ]

        def assert_servicegroups(result):
            self.assertEqual(len(result), 80)
            for r in expected_result:
                self.assertIn(r, result)

        self.execute_and_assert(query, assert_servicegroups)

        svc1 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_00")
        svc2 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_01")
        svc3 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_05")
        svc4 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_10")
        svc5 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_15")
        svc6 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_16")
        svc7 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_critical_11")
        self.scheduler_loop(1, [[svc1, 1, 'W'], [svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C'], [svc7, 2, 'C']])
        self.scheduler_loop(2, [[svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C']])

        host = self.sched.hosts.find_by_name("test_host_005")
        self.scheduler_loop(1, [[host, 1, 'DOWN']])
        self.update_broker()

        expected_result = [
            ['test_host_005', 'test_critical_11', 'servicegroup_02', 'servicegroup_alias_02', 0, 40, 1, 1, 1, 0, 0, 0, 37],
        ]

        self.execute_and_assert(query, assert_servicegroups)

    def test_servicesbyhostgroup(self):
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
Columns: host_name description hostgroup_name hostgroup_alias
Filter: contacts >= test_contact
Filter: host_name = test_host_005
Filter: description = test_ok_00
OutputFormat: python"""

        expected_result = [
            [u'test_host_005', u'test_ok_00', u'flap', u'All Flapping Hosts'],
            [u'test_host_005', u'test_ok_00', u'hostgroup_01', u'hostgroup_alias_01']
        ]

        self.execute_and_assert(query, expected_result)

        query = """GET servicesbyhostgroup
Columns: host_name name description hostgroup_name hostgroup_alias hostgroup_num_hosts_up hostgroup_num_services_warn hostgroup_num_services_hard_unknown hostgroup_num_services hostgroup_num_services_crit hostgroup_num_hosts_pending hostgroup_num_hosts_down hostgroup_num_services_hard_crit hostgroup_num_services_hard_warn hostgroup_num_services_unknown hostgroup_num_services_pending hostgroup_num_hosts hostgroup_num_services_ok hostgroup_num_services_hard_ok hostgroup_num_hosts_unreach
Filter: hostgroups >= hostgroup_01
Filter: hostgroups >= hostgroup_02
Or: 2
OutputFormat: python
"""

        expected_result = [
            ['test_host_000', 'test_critical_03', 'hostgroup_01', 'hostgroup_alias_01', 2, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 2, 0, 40, 0],
            ['test_host_005', 'test_critical_11', 'hostgroup_01', 'hostgroup_alias_01', 2, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 2, 0, 40, 0],
            ['test_host_001', 'test_flap_12', 'hostgroup_02', 'hostgroup_alias_02', 2, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 2, 0, 40, 0],
            ['test_host_006', 'test_flap_08', 'hostgroup_02', 'hostgroup_alias_02', 2, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 2, 0, 40, 0]
        ]

        def assert_hostgroups(result):
            self.assertEqual(len(result), 80)
            for r in expected_result:
                self.assertIn(r, result)

        self.execute_and_assert(query, assert_hostgroups)

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

        expected_result = [
            ['test_host_000', 'test_critical_03', 'hostgroup_01', 'hostgroup_alias_01', 1, 1, 1, 40, 1, 0, 0, 2, 2, 0, 0, 2, 0, 33, 0],
            ['test_host_005', 'test_critical_11', 'hostgroup_01', 'hostgroup_alias_01', 1, 1, 1, 40, 1, 0, 0, 2, 2, 0, 0, 2, 0, 33, 0],
            ['test_host_001', 'test_flap_12', 'hostgroup_02', 'hostgroup_alias_02', 2, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 2, 0, 40, 0],
            ['test_host_006', 'test_flap_08', 'hostgroup_02', 'hostgroup_alias_02', 2, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 2, 0, 40, 0]
        ]

        self.execute_and_assert(query, assert_hostgroups)


if __name__ == '__main__':
    #import cProfile
    command = """unittest.main()"""
    unittest.main()
