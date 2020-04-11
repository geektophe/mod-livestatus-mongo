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
        response, _ = self.livestatus_broker.livestatus.handle_request(query, "mongo")
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
Columns: host_name alias
Filter: host_name = test_host_001
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Case insensitive match
        query = """GET hosts
Columns: host_name alias
Filter: host_name =~ TEST_host_001
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Regex exact match
        query = """GET hosts
Columns: host_name alias
Filter: host_name ~ test_[a-z]+_001
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Regex case insensitive match
        query = """GET hosts
Columns: host_name alias
Filter: host_name ~~ TEST_[a-z]+_001
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Miging several conditions
        query = """GET hosts
Columns: host_name alias
Filter: host_name ~~ TEST_[a-z]+_001
Filter: alias = pending_001
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Miging several conditions
        query = """GET hosts
Columns: host_name alias
Filter: host_name ~~ TEST_[a-z]+_001
Filter: alias = fake
OutputFormat: python
"""
        self.execute_and_assert(query, [])

        # Integer ge comparison
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: max_check_attempts >= 5
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Integer gt comparison
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: max_check_attempts > 5
OutputFormat: python
"""
        print("Just before execute")
        self.execute_and_assert(query, [])

        # Integer le comparison
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: max_check_attempts <= 5
OutputFormat: python
"""

        # Integer gt comparison
        self.execute_and_assert(query, expected_result)
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
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
Columns: host_name alias
Filter: host_name != test_host_001
OutputFormat: python
"""
        self.execute_and_assert(query, not_hosts_condition)
        # Case insensitive match
        query = """GET hosts
Columns: host_name alias
Filter: host_name !=~ TEST_host_001
OutputFormat: python
"""
        self.execute_and_assert(query, not_hosts_condition)
        # Regex exact match
        query = """GET hosts
Columns: host_name alias
Filter: host_name !~ test_[a-z]+_001
OutputFormat: python
"""
        self.execute_and_assert(query, not_hosts_condition)
        # Regex case insensitive match
        query = """GET hosts
Columns: host_name alias
Filter: host_name !~~ TEST_[a-z]+_001
OutputFormat: python
"""
        self.execute_and_assert(query, not_hosts_condition)

        # Integer ge comparison
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: max_check_attempts !>= 5
OutputFormat: python
"""
        self.execute_and_assert(query, [])

        # Integer gt comparison
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: max_check_attempts !> 5
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # Integer le comparison
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: max_check_attempts !<= 5
OutputFormat: python
"""
        self.execute_and_assert(query, [])

        # Integer gt comparison
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: max_check_attempts !< 5
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # List is empty
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: labels =
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # List is not empty
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: labels !=
OutputFormat: python
"""
        self.execute_and_assert(query, [])

        # List contains
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: notification_options >= u
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # List does not contain
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: notification_options < u
OutputFormat: python
"""
        self.execute_and_assert(query, [])

        # List contains (case insensitive)
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: notification_options <= U
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # List does not contains (case insensitive)
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: notification_options > U
OutputFormat: python
"""
        self.execute_and_assert(query, [])

        # List matches
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: notification_options ~ ^u$
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        # List matches (case insensitive)
        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
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
Columns: host_name alias
Filter: host_name = test_host_001
Filter: host_name = test_host_002
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
Columns: host_name alias
Filter: host_name = test_host_001
Filter: notification_options ~~ ^U$
OutputFormat: python
"""
        expected_result = [['test_host_001', 'pending_001']]
        self.execute_and_assert(query, expected_result)

        def negate_hosts_condition(result):
            self.assertNotIn(['test_host_001', 'pending_001'], result)
            self.assertIn(['test_host_002', 'down_002'], result)

        query = """GET hosts
Columns: host_name alias
Filter: host_name = test_host_001
Filter: notification_options ~~ ^U$
Negate:
OutputFormat: python
"""
        self.execute_and_assert(query, negate_hosts_condition)

        query = """GET hosts
Columns: host_name alias
Filter: host_name != test_host_001
Filter: alias !~~ pending_001
Negate:2
Filter: notification_options < d
Filter: notification_options !~~ ^U$
Negate: 2
OutputFormat: python
"""
        self.execute_and_assert(query, expected_result)

        query = """GET hosts
Columns: host_name alias
Filter: host_name != test_host_001
Filter: alias !~~ pending_001
Negate:2
Filter: notification_options < d
Filter: notification_options !~~ ^U$
Negate: 2
Negate:
OutputFormat: python
"""
        self.execute_and_assert(query, negate_hosts_condition)

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
        pprint([[svc1, 1, 'W'], [svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C'], [svc7, 2, 'C']])
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

        expected_result = [200, 193, 3, 3, 1]
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

        expected_result = [193]
        self.execute_and_assert(query, expected_result)


    def test_limit(self):
        """
        Tests result count limitting
        """
        query = """GET hosts
Columns: host_name alias
Filter: host_name ~ test_host_00[0-9]
OutputFormat: python
"""

        expected_length = 10

        def assert_len(result):
            self.assertEqual(len(result), expected_length)

        self.execute_and_assert(query, assert_len)

        query = """GET hosts
Columns: host_name alias
Filter: host_name ~ test_host_00[0-9]
Limit: 5
OutputFormat: python
"""

        expected_length = 5

        def assert_len(result):
            self.assertEqual(len(result), expected_length)

        self.execute_and_assert(query, assert_len)

    def test_authuser(self):
        """
        Tests limitting results what's authorized to authenticated user
        """
        query = """GET hosts
Columns: host_name alias
Filter: host_name ~ test_host_00[0-9]
OutputFormat: python
"""

        def assert_no_authuser(result):
            self.assertEqual(len(result), 10)
            self.assertIn(['test_host_001', 'pending_001'], result)
            self.assertIn(['test_host_009', 'up_009'], result)

        self.execute_and_assert(query, assert_no_authuser)

        query = """GET hosts
Columns: host_name alias
Filter: host_name ~ test_host_00[0-9]
AuthUser: test_contact_02
OutputFormat: python
"""

        def assert_authuser(result):
            self.assertEqual(len(result), 1)
            self.assertIn(['test_host_001', 'pending_001'], result)
            self.assertNotIn(['test_host_009', 'up_009'], result)

        self.execute_and_assert(query, assert_authuser)

    def test_cross_collections_objects(self):

        query = """GET hosts
Columns: host_name num_services
Filter: host_name ~ test_host_00[0-9]
AuthUser: test_contact_02
OutputFormat: python
"""

        def assert_dummy(result):
            pass

        expected_result = [[u'test_host_001', 20]]
        self.execute_and_assert(query, expected_result)

        query = """GET hosts
Columns: host_name num_services
Filter: host_name ~ test_host_00[0-9]
AuthUser: test_contact_02
OutputFormat: python
"""

        def assert_dummy(result):
            pass

        expected_result = [[u'test_host_001', 20]]
        self.execute_and_assert(query, expected_result)





    def _test_worst_service_state(self):
        # test_host_005 is in hostgroup_01
        # 20 services   from  400 services
        hostgroup_01 = self.sched.hostgroups.find_by_name("hostgroup_01")
        host_005 = self.sched.hosts.find_by_name("test_host_005")
        test_ok_00 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_00")
        test_ok_01 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_01")
        test_ok_04 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_04")
        test_ok_16 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_16")
        objlist = []
        for service in [svc for host in hostgroup_01.get_hosts() for svc in host.services]:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(2, objlist)
        self.update_broker()
        #h_request = """GET hosts\nColumns: name num_services_ok num_services_warn num_services_crit num_services_unknown worst_service_state worst_service_hard_state\nFilter: name = test_host_005\nColumnHeaders: on\nResponseHeader: fixed16"""
        h_request = """GET hosts\nColumns: num_services_warn num_services_crit num_services_unknown worst_service_state worst_service_hard_state\nFilter: name = test_host_005\nColumnHeaders: off\nResponseHeader: off"""
        #hg_request = """GET hostgroups\nColumns: name num_services_ok num_services_warn num_services_crit num_services_unknown worst_service_state worst_service_hard_state\nFilter: name = hostgroup_01\nColumnHeaders: on\nResponseHeader: fixed16"""
        hg_request = """GET hostgroups\nColumns: num_services_warn num_services_crit num_services_unknown worst_service_state worst_service_hard_state\nFilter: name = hostgroup_01\nColumnHeaders: off\nResponseHeader: off"""

        # test_ok_00
        # test_ok_01
        # test_ok_04
        # test_ok_16
        h_response, keepalive = self.livestatus_broker.livestatus.handle_request(h_request)
        hg_response, keepalive = self.livestatus_broker.livestatus.handle_request(hg_request)
        print "ho_reponse", h_response
        print "hg_reponse", hg_response
        self.assertEqual(hg_response, h_response )
        self.assert_(h_response == """0;0;0;0;0
""")

        # test_ok_00
        # test_ok_01 W(S)
        # test_ok_04
        # test_ok_16
        self.scheduler_loop(1, [[test_ok_01, 1, 'WARN']])
        self.update_broker()
        h_response, keepalive = self.livestatus_broker.livestatus.handle_request(h_request)
        hg_response, keepalive = self.livestatus_broker.livestatus.handle_request(hg_request)
        self.assertEqual(hg_response, h_response )
        self.assert_(h_response == """1;0;0;1;0
""")

        # test_ok_00
        # test_ok_01 W(S)
        # test_ok_04 C(S)
        # test_ok_16
        self.scheduler_loop(1, [[test_ok_04, 2, 'CRIT']])
        self.update_broker()
        h_response, keepalive = self.livestatus_broker.livestatus.handle_request(h_request)
        hg_response, keepalive = self.livestatus_broker.livestatus.handle_request(hg_request)
        self.assertEqual(hg_response, h_response )
        self.assert_(h_response == """1;1;0;2;0
""")

        # test_ok_00
        # test_ok_01 W(H)
        # test_ok_04 C(S)
        # test_ok_16
        self.scheduler_loop(2, [[test_ok_01, 1, 'WARN']])
        self.update_broker()
        h_response, keepalive = self.livestatus_broker.livestatus.handle_request(h_request)
        hg_response, keepalive = self.livestatus_broker.livestatus.handle_request(hg_request)
        self.assertEqual(hg_response, h_response )
        self.assert_(h_response == """1;1;0;2;1
""")

        # test_ok_00
        # test_ok_01 W(H)
        # test_ok_04 C(H)
        # test_ok_16
        self.scheduler_loop(2, [[test_ok_04, 2, 'CRIT']])
        self.update_broker()
        h_response, keepalive = self.livestatus_broker.livestatus.handle_request(h_request)
        hg_response, keepalive = self.livestatus_broker.livestatus.handle_request(hg_request)
        self.assertEqual(hg_response, h_response )
        self.assert_(h_response == """1;1;0;2;2
""")



    def _test_statsgroupby(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()
        svc1 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_00")
        print svc1
        svc2 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_15")
        print svc2
        svc3 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_16")
        print svc3
        svc4 = self.sched.services.find_srv_by_name_and_hostname("test_host_007", "test_ok_05")
        print svc4
        svc5 = self.sched.services.find_srv_by_name_and_hostname("test_host_007", "test_ok_11")
        svc6 = self.sched.services.find_srv_by_name_and_hostname("test_host_025", "test_ok_01")
        svc7 = self.sched.services.find_srv_by_name_and_hostname("test_host_025", "test_ok_03")
        self.scheduler_loop(1, [[svc1, 1, 'W'], [svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C'], [svc7, 2, 'C']])
        self.update_broker()
        # 1993O, 3xW, 3xC, 1xU

        request = 'GET services\nFilter: contacts >= test_contact\nStats: state != 9999\nStats: state = 0\nStats: state = 1\nStats: state = 2\nStats: state = 3\nStatsGroupBy: host_name'
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print response
        self.assert_(self.contains_line(response, 'test_host_005;20;17;3;0;0'))
        self.assert_(self.contains_line(response, 'test_host_007;20;18;0;1;1'))
        self.assert_(self.contains_line(response, 'test_host_025;20;18;0;2;0'))
        self.assert_(self.contains_line(response, 'test_host_026;20;20;0;0;0'))

        request = """GET services
Stats: state != 9999
StatsGroupBy: state
"""
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print response
        self.assert_(self.contains_line(response, '0;1993'))
        self.assert_(self.contains_line(response, '1;3'))
        self.assert_(self.contains_line(response, '2;3'))
        self.assert_(self.contains_line(response, '3;1'))

    def _test_hostsbygroup(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()
        request = """GET hostsbygroup
ColumnHeaders: on
Columns: host_name hostgroup_name
OutputFormat: csv
KeepAlive: on
ResponseHeader: fixed16
"""

        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print response
        # TODO

    def _test_servicesbyhostgroup(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()
        request = """GET servicesbyhostgroup
Filter: host_groups >= up
Stats: has_been_checked = 0
Stats: state = 0
Stats: has_been_checked != 0
Stats: scheduled_downtime_depth = 0
Stats: host_scheduled_downtime_depth = 0
StatsAnd: 4
Stats: state = 0
Stats: scheduled_downtime_depth > 0
Stats: host_scheduled_downtime_depth > 0
StatsAnd: 3
Stats: state = 1
Stats: acknowledged = 0
Stats: host_acknowledged = 0
Stats: scheduled_downtime_depth = 0
Stats: host_scheduled_downtime_depth = 0
StatsAnd: 5
Stats: state = 1
Stats: acknowledged = 1
Stats: host_acknowledged = 1
StatsOr: 2
StatsAnd: 2
Stats: state = 1
Stats: scheduled_downtime_depth > 0
Stats: host_scheduled_downtime_depth > 0
StatsOr: 2
StatsAnd: 2
Stats: state = 2
Stats: acknowledged = 0
Stats: host_acknowledged = 0
Stats: scheduled_downtime_depth = 0
Stats: host_scheduled_downtime_depth = 0
StatsAnd: 5
Stats: state = 2
Stats: acknowledged = 1
Stats: host_acknowledged = 1
StatsOr: 2
StatsAnd: 2
Stats: state = 2
Stats: scheduled_downtime_depth > 0
Stats: host_scheduled_downtime_depth > 0
StatsOr: 2
StatsAnd: 2
Stats: state = 3
Stats: acknowledged = 0
Stats: host_acknowledged = 0
Stats: scheduled_downtime_depth = 0
Stats: host_scheduled_downtime_depth = 0
StatsAnd: 5
Stats: state = 3
Stats: acknowledged = 1
Stats: host_acknowledged = 1
StatsOr: 2
StatsAnd: 2
Stats: state = 3
Stats: scheduled_downtime_depth > 0
Stats: host_scheduled_downtime_depth > 0
StatsOr: 2
StatsAnd: 2
StatsGroupBy: hostgroup_name
OutputFormat: csv
KeepAlive: on
ResponseHeader: fixed16
"""
        tic = time.clock()
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        tac = time.clock()
        print "livestatus duration %f" % (tac - tic)
        print response
        # TODO

        # Again, without Filter:
        request = """GET servicesbyhostgroup
Stats: has_been_checked = 0
Stats: state = 0
Stats: has_been_checked != 0
Stats: scheduled_downtime_depth = 0
Stats: host_scheduled_downtime_depth = 0
StatsAnd: 4
Stats: state = 0
Stats: scheduled_downtime_depth > 0
Stats: host_scheduled_downtime_depth > 0
StatsAnd: 3
Stats: state = 1
Stats: acknowledged = 0
Stats: host_acknowledged = 0
Stats: scheduled_downtime_depth = 0
Stats: host_scheduled_downtime_depth = 0
StatsAnd: 5
Stats: state = 1
Stats: acknowledged = 1
Stats: host_acknowledged = 1
StatsOr: 2
StatsAnd: 2
Stats: state = 1
Stats: scheduled_downtime_depth > 0
Stats: host_scheduled_downtime_depth > 0
StatsOr: 2
StatsAnd: 2
Stats: state = 2
Stats: acknowledged = 0
Stats: host_acknowledged = 0
Stats: scheduled_downtime_depth = 0
Stats: host_scheduled_downtime_depth = 0
StatsAnd: 5
Stats: state = 2
Stats: acknowledged = 1
Stats: host_acknowledged = 1
StatsOr: 2
StatsAnd: 2
Stats: state = 2
Stats: scheduled_downtime_depth > 0
Stats: host_scheduled_downtime_depth > 0
StatsOr: 2
StatsAnd: 2
Stats: state = 3
Stats: acknowledged = 0
Stats: host_acknowledged = 0
Stats: scheduled_downtime_depth = 0
Stats: host_scheduled_downtime_depth = 0
StatsAnd: 5
Stats: state = 3
Stats: acknowledged = 1
Stats: host_acknowledged = 1
StatsOr: 2
StatsAnd: 2
Stats: state = 3
Stats: scheduled_downtime_depth > 0
Stats: host_scheduled_downtime_depth > 0
StatsOr: 2
StatsAnd: 2
StatsGroupBy: hostgroup_name
OutputFormat: csv
KeepAlive: on
ResponseHeader: fixed16
"""
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print response
        # TODO

    def _test_childs(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()
        request = """GET hosts
Columns: childs
Filter: name = test_host_0
OutputFormat: csv
KeepAlive: on
ResponseHeader: fixed16
"""
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print response
        # TODO

        request = """GET hosts
Columns: childs
Filter: name = test_router_0
OutputFormat: csv
KeepAlive: on
ResponseHeader: fixed16
"""
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print response
        # TODO

    def _test_thruk_servicegroup(self):
        self.print_header()
        now = time.time()
        self.update_broker()
        #---------------------------------------------------------------
        # get services of a certain servicegroup
        # test_host_0/test_ok_0 is in
        #   servicegroup_01,ok via service.servicegroups
        #   servicegroup_02 via servicegroup.members
        #---------------------------------------------------------------
        request = """GET services
Columns: host_name service_description
Filter: groups >= servicegroup_01
OutputFormat: csv
ResponseHeader: fixed16
"""
        # 400 services => 400 lines + header + empty last line
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print "r1", response
        self.assertEqual(402, len(response.split("\n")) )

        request = """GET servicegroups
Columns: name members
Filter: name = servicegroup_01
OutputFormat: csv
"""
        sg01 = self.livestatus_broker.livestatus.datamgr.rg.servicegroups.find_by_name("servicegroup_01")
        print "sg01 is", sg01
        # 400 services => 400 lines
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print "r2", response
        # take first line, take members column, count list elements = 400 services
        self.assertEqual(400, len(((response.split("\n")[0]).split(';')[1]).split(',')) )

    def _test_sorted_limit(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        # now send the list of services to the broker in an unordered way
        sched_unsorted = '\n'.join(["%s;%s;%d" % (s.host_name, s.service_description, s.state_id) for s in self.sched.services])

        self.update_broker()
        #print "in ls test", self.livestatus_broker.rg.services._id_heap
        #for s in self.livestatus_broker.rg.services:
        #    print s.get_full_name()
        if hasattr(self.livestatus_broker.rg.services, "__iter__") and hasattr(self.livestatus_broker.rg.services, "itersorted"):
            print "ris__iter__", self.livestatus_broker.rg.services.__iter__
            print "ris__itersorted__", self.livestatus_broker.rg.services.itersorted
        i = 0
        while i < 10:
            print self.livestatus_broker.rg.services._id_heap[i]
            idx = self.livestatus_broker.rg.services._id_heap[i]
            print self.livestatus_broker.rg.services[idx].get_full_name()
            i += 1
        i = 0

        live_sorted = '\n'.join(sorted(["%s;%s;%d" % (s.host_name, s.service_description, s.state_id) for s in self.livestatus_broker.rg.services]))

        # Unsorted in the scheduler, sorted in livestatus
        self.assert_(sched_unsorted != live_sorted)
        sched_live_sorted = '\n'.join(sorted(sched_unsorted.split('\n'))) + '\n'
        sched_live_sorted = sched_live_sorted.strip()
        print "first of sched\n(%s)\n--------------\n" % sched_unsorted[:100]
        print "first of live \n(%s)\n--------------\n" % live_sorted[:100]
        print "first of sssed \n(%s)\n--------------\n" % sched_live_sorted[:100]
        print "last of sched\n(%s)\n--------------\n" % sched_unsorted[-100:]
        print "last of live \n(%s)\n--------------\n" % live_sorted[-100:]
        print "last of sssed \n(%s)\n--------------\n" % sched_live_sorted[-100:]
        # But sorted they are the same.
        self.assertEqual(live_sorted, '\n'.join(sorted(sched_unsorted.split('\n'))) )

        svc1 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_00")
        print svc1
        svc2 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_15")
        print svc2
        svc3 = self.sched.services.find_srv_by_name_and_hostname("test_host_005", "test_ok_16")
        print svc3
        svc4 = self.sched.services.find_srv_by_name_and_hostname("test_host_007", "test_ok_05")
        print svc4
        svc5 = self.sched.services.find_srv_by_name_and_hostname("test_host_007", "test_ok_11")
        svc6 = self.sched.services.find_srv_by_name_and_hostname("test_host_025", "test_ok_01")
        svc7 = self.sched.services.find_srv_by_name_and_hostname("test_host_025", "test_ok_03")
        self.scheduler_loop(1, [[svc1, 1, 'W'], [svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C'], [svc7, 2, 'C']])
        self.update_broker()
        # 1993O, 3xW, 3xC, 1xU

        # Get all bad services from livestatus
        request = """GET services
Columns: host_name service_description state
ColumnHeaders: off
OutputFormat: csv
Filter: state != 0"""
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        # Get all bad services from the scheduler
        sched_bad_unsorted = '\n'.join(["%s;%s;%d" % (s.host_name, s.service_description, s.state_id) for s in self.sched.services if s.state_id != 0])
        # Check if the result of the query is sorted
        self.assertEqual(response.strip(), '\n'.join(sorted(sched_bad_unsorted.split('\n'))) )

        # Now get the first 3 bad services from livestatus
        request = """GET services
Limit: 3
Columns: host_name service_description state
ColumnHeaders: off
OutputFormat: csv
Filter: state != 0"""
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print 'query_6_______________\n%s\n%s\n' % (request, response)

        # Now compare the first 3 bad services with the scheduler data
        self.assertEqual(response.strip(), '\n'.join(sorted(sched_bad_unsorted.split('\n'))[:3]) )

        # Now check if all services are sorted when queried with a livestatus request
        request = """GET services
Columns: host_name service_description state
ColumnHeaders: off
OutputFormat: csv"""
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        # Again, get all bad services from the scheduler
        sched_bad_unsorted = '\n'.join(["%s;%s;%d" % (s.host_name, s.service_description, s.state_id) for s in self.sched.services])

        # Check if the result of the query is sorted
        ## FIXME LAUSSER self.assertEqual(response.strip(), '\n'.join(sorted(sched_bad_unsorted.split('\n'))) )



    # We look for the perf of the unhandled srv
    # page view of Thruk. We only enable it when we need
    # it's not a true test.
    def _test_thruk_unhandled_srv_page_perf(self):
        # COMMENT THIS LINE to enable the bench and call
        # python test_livestatus.py TestConfigBig.test_thruk_unhandled_srv_page_perf
        return
        import cProfile
        cProfile.runctx('''self.do_test_thruk_unhandled_srv_page_perf()''', globals(), locals(), '/tmp/livestatus_thruk_perf.profile')

    def do_test_thruk_unhandled_srv_page_perf(self):
        self.print_header()

        objlist = []
        # We put 10% of elemetnsi n bad states
        i = 0
        for host in self.sched.hosts:
            i += 1
            if i % 10 == 0:
                objlist.append([host, 1, 'DOWN'])
            else:
                objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            i += 1
            if i % 10 == 0:
                objlist.append([service, 2, 'CRITICAL'])
            else:
                objlist.append([service, 0, 'OK'])
        self.scheduler_loop(2, objlist)
        self.update_broker()

        # We will look for the overall page loading time
        total_page = 0.0

        # First Query
        query_start = time.time()
        request = """
GET status
Columns: accept_passive_host_checks accept_passive_service_checks check_external_commands check_host_freshness check_service_freshness enable_event_handlers enable_flap_detection enable_notifications execute_host_checks execute_service_checks last_command_check last_log_rotation livestatus_version nagios_pid obsess_over_hosts obsess_over_services process_performance_data program_start program_version interval_length
OutputFormat: json
ResponseHeader: fixed16
"""
        print "Query 1 launched (Get overall status)"
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        #print response
        load_time = time.time() - query_start
        total_page += load_time
        print "Response time 1: %.3f" % load_time

        # Second Query
        query_start = time.time()
        request = """
GET hosts
Stats: name !=
StatsAnd: 1
Stats: check_type = 0
StatsAnd: 1
Stats: check_type = 1
StatsAnd: 1
Stats: has_been_checked = 0
StatsAnd: 1
Stats: has_been_checked = 0
Stats: active_checks_enabled = 0
StatsAnd: 2
Stats: has_been_checked = 0
Stats: scheduled_downtime_depth > 0
StatsAnd: 2
Stats: has_been_checked = 1
Stats: state = 0
StatsAnd: 2
Stats: check_type = 0
Stats: has_been_checked = 1
Stats: state = 0
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: check_type = 1
Stats: has_been_checked = 1
Stats: state = 0
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: has_been_checked = 1
Stats: state = 0
Stats: scheduled_downtime_depth > 0
StatsAnd: 3
Stats: has_been_checked = 1
Stats: state = 1
StatsAnd: 2
Stats: has_been_checked = 1
Stats: state = 1
Stats: acknowledged = 1
StatsAnd: 3
Stats: has_been_checked = 1
Stats: state = 1
Stats: scheduled_downtime_depth > 0
StatsAnd: 3
Stats: check_type = 0
Stats: has_been_checked = 1
Stats: state = 1
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: check_type = 1
Stats: has_been_checked = 1
Stats: state = 1
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: has_been_checked = 1
Stats: state = 1
Stats: active_checks_enabled = 1
Stats: acknowledged = 0
Stats: scheduled_downtime_depth = 0
StatsAnd: 5
Stats: has_been_checked = 1
Stats: state = 2
StatsAnd: 2
Stats: has_been_checked = 1
Stats: state = 2
Stats: acknowledged = 1
StatsAnd: 3
Stats: has_been_checked = 1
Stats: state = 2
Stats: scheduled_downtime_depth > 0
StatsAnd: 3
Stats: check_type = 0
Stats: has_been_checked = 1
Stats: state = 2
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: check_type = 1
Stats: has_been_checked = 1
Stats: state = 2
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: has_been_checked = 1
Stats: state = 2
Stats: active_checks_enabled = 1
Stats: acknowledged = 0
Stats: scheduled_downtime_depth = 0
StatsAnd: 5
Stats: is_flapping = 1
StatsAnd: 1
Stats: flap_detection_enabled = 0
StatsAnd: 1
Stats: notifications_enabled = 0
StatsAnd: 1
Stats: event_handler_enabled = 0
StatsAnd: 1
Stats: check_type = 0
Stats: active_checks_enabled = 0
StatsAnd: 2
Stats: check_type = 1
Stats: active_checks_enabled = 0
StatsAnd: 2
Stats: accept_passive_checks = 0
StatsAnd: 1
Stats: state = 1
Stats: childs !=
StatsAnd: 2
OutputFormat: json
ResponseHeader: fixed16
"""
        print "Query 2 launched (Get hosts stistics)"
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        #print response
        load_time = time.time() - query_start
        total_page += load_time
        print "Response time 2: %.3f" % load_time

        # Now Query 3 (service stats)
        query_start = time.time()
        request = """
GET services
Stats: description !=
StatsAnd: 1
Stats: check_type = 0
StatsAnd: 1
Stats: check_type = 1
StatsAnd: 1
Stats: has_been_checked = 0
StatsAnd: 1
Stats: has_been_checked = 0
Stats: active_checks_enabled = 0
StatsAnd: 2
Stats: has_been_checked = 0
Stats: scheduled_downtime_depth > 0
StatsAnd: 2
Stats: has_been_checked = 1
Stats: state = 0
StatsAnd: 2
Stats: has_been_checked = 1
Stats: state = 0
Stats: scheduled_downtime_depth > 0
StatsAnd: 3
Stats: check_type = 0
Stats: has_been_checked = 1
Stats: state = 0
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: check_type = 1
Stats: has_been_checked = 1
Stats: state = 0
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: has_been_checked = 1
Stats: state = 1
StatsAnd: 2
Stats: has_been_checked = 1
Stats: state = 1
Stats: scheduled_downtime_depth > 0
StatsAnd: 3
Stats: check_type = 0
Stats: has_been_checked = 1
Stats: state = 1
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: check_type = 1
Stats: has_been_checked = 1
Stats: state = 1
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: has_been_checked = 1
Stats: state = 1
Stats: acknowledged = 1
StatsAnd: 3
Stats: has_been_checked = 1
Stats: state = 1
Stats: host_state != 0
StatsAnd: 3
Stats: has_been_checked = 1
Stats: state = 1
Stats: host_state = 0
Stats: active_checks_enabled = 1
Stats: acknowledged = 0
Stats: scheduled_downtime_depth = 0
StatsAnd: 6
Stats: has_been_checked = 1
Stats: state = 2
StatsAnd: 2
Stats: has_been_checked = 1
Stats: state = 2
Stats: scheduled_downtime_depth > 0
StatsAnd: 3
Stats: check_type = 0
Stats: has_been_checked = 1
Stats: state = 2
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: check_type = 1
Stats: has_been_checked = 1
Stats: state = 2
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: has_been_checked = 1
Stats: state = 2
Stats: acknowledged = 1
StatsAnd: 3
Stats: has_been_checked = 1
Stats: state = 2
Stats: host_state != 0
StatsAnd: 3
Stats: has_been_checked = 1
Stats: state = 2
Stats: host_state = 0
Stats: active_checks_enabled = 1
Stats: acknowledged = 0
Stats: scheduled_downtime_depth = 0
StatsAnd: 6
Stats: has_been_checked = 1
Stats: state = 3
StatsAnd: 2
Stats: has_been_checked = 1
Stats: state = 3
Stats: scheduled_downtime_depth > 0
StatsAnd: 3
Stats: check_type = 0
Stats: has_been_checked = 1
Stats: state = 3
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: check_type = 1
Stats: has_been_checked = 1
Stats: state = 3
Stats: active_checks_enabled = 0
StatsAnd: 4
Stats: has_been_checked = 1
Stats: state = 3
Stats: acknowledged = 1
StatsAnd: 3
Stats: has_been_checked = 1
Stats: state = 3
Stats: host_state != 0
StatsAnd: 3
Stats: has_been_checked = 1
Stats: state = 3
Stats: host_state = 0
Stats: active_checks_enabled = 1
Stats: acknowledged = 0
Stats: scheduled_downtime_depth = 0
StatsAnd: 6
Stats: is_flapping = 1
StatsAnd: 1
Stats: flap_detection_enabled = 0
StatsAnd: 1
Stats: notifications_enabled = 0
StatsAnd: 1
Stats: event_handler_enabled = 0
StatsAnd: 1
Stats: check_type = 0
Stats: active_checks_enabled = 0
StatsAnd: 2
Stats: check_type = 1
Stats: active_checks_enabled = 0
StatsAnd: 2
Stats: accept_passive_checks = 0
StatsAnd: 1
OutputFormat: json
ResponseHeader: fixed16
"""
        print "Query 3 launched (Get services statistics)"
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        #print response
        load_time = time.time() - query_start
        total_page += load_time
        print "Response time 3: %.3f" % load_time

        # 4th Query
        query_start = time.time()
        request = """
GET comments
Columns: author comment entry_time entry_type expires expire_time host_name id persistent service_description source type
Filter: service_description !=
Filter: service_description =
Or: 2
OutputFormat: json
ResponseHeader: fixed16
"""
        print "Query 4 launched (Get comments)"
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        #print response
        load_time = time.time() - query_start
        total_page += load_time
        print "Response time 4: %.3f" % load_time

        # 5th Query
        query_start = time.time()
        request = """
GET downtimes
Columns: author comment end_time entry_time fixed host_name id start_time service_description triggered_by
Filter: service_description !=
Filter: service_description =
Or: 2
OutputFormat: json
ResponseHeader: fixed16
"""
        print "Query 5 launched (Get downtimes)"
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        #print response
        load_time = time.time() - query_start
        total_page += load_time
        print "Response time 5: %.3f" % load_time

        # 6th Query
        query_start = time.time()
        request = """
GET services
Filter: host_has_been_checked = 0
Filter: host_state = 0
Filter: host_has_been_checked = 1
And: 2
Or: 2
Filter: state = 1
Filter: has_been_checked = 1
And: 2
Filter: state = 3
Filter: has_been_checked = 1
And: 2
Filter: state = 2
Filter: has_been_checked = 1
And: 2
Or: 3
Filter: scheduled_downtime_depth = 0
Filter: acknowledged = 0
Filter: checks_enabled = 1
And: 3
And: 3
Stats: description !=
OutputFormat: json
ResponseHeader: fixed16
"""
        print "Query 6 launched (Get bad services)"
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        #print response
        load_time = time.time() - query_start
        total_page += load_time
        print "Response time 6: %.3f" % load_time

        # 7th Query
        query_start = time.time()
        request = """
GET services
Columns: accept_passive_checks acknowledged action_url action_url_expanded active_checks_enabled check_command check_interval check_options check_period check_type checks_enabled comments current_attempt current_notification_number description event_handler event_handler_enabled custom_variable_names custom_variable_values execution_time first_notification_delay flap_detection_enabled groups has_been_checked high_flap_threshold host_acknowledged host_action_url_expanded host_active_checks_enabled host_address host_alias host_checks_enabled host_comments host_groups host_has_been_checked host_icon_image_expanded host_icon_image_alt host_is_executing host_is_flapping host_name host_notes_url_expanded host_notifications_enabled host_scheduled_downtime_depth host_state icon_image icon_image_alt icon_image_expanded is_executing is_flapping last_check last_notification last_state_change latency long_plugin_output low_flap_threshold max_check_attempts next_check notes notes_expanded notes_url notes_url_expanded notification_interval notification_period notifications_enabled obsess_over_service percent_state_change perf_data plugin_output process_performance_data retry_interval scheduled_downtime_depth state state_type is_impact source_problems impacts criticity business_impact is_problem got_business_rule parent_dependencies
Filter: host_has_been_checked = 0
Filter: host_state = 0
Filter: host_has_been_checked = 1
And: 2
Or: 2
Filter: state = 1
Filter: has_been_checked = 1
And: 2
Filter: state = 3
Filter: has_been_checked = 1
And: 2
Filter: state = 2
Filter: has_been_checked = 1
And: 2
Or: 3
Filter: scheduled_downtime_depth = 0
Filter: acknowledged = 0
Filter: checks_enabled = 1
And: 3
And: 3
Limit: 150
OutputFormat: json
ResponseHeader: fixed16
"""
        print "Query 7 launched (Get bad service data)"
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        #print response
        load_time = time.time() - query_start
        total_page += load_time
        print "Response time 7: %.3f" % load_time

        print ""
        print "Overall Queries time: %.3f" % total_page

    def _test_thruk_search(self):
        self.print_header()
        now = time.time()
        self.update_broker()
        # 99 test_host_099
        request = """GET comments
Columns: author comment entry_time entry_type expires expire_time host_name id persistent service_description source type
Filter: service_description !=
Filter: service_description =
Or: 2
Filter: comment ~~ 99
Filter: author ~~ 99
Or: 2
OutputFormat: csv
"""
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print "r1", response
        self.assert_(response == """
""")

        request = """GET downtimes
Columns: author comment end_time entry_time fixed host_name id start_time service_description triggered_by
Filter: service_description !=
Filter: service_description =
Or: 2
Filter: comment ~~ 99
Filter: author ~~ 99
Or: 2
OutputFormat: csv
"""
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print "r1", response
        self.assert_(response == """
""")

        request = """GET services
Columns: host_has_been_checked host_name host_state
Filter: description ~~ 99
Filter: groups >= 99
Filter: plugin_output ~~ 99
Filter: long_plugin_output ~~ 99
Filter: host_name ~~ 99
Filter: host_alias ~~ 99
Filter: host_address ~~ 99
Filter: host_groups >= 99
Filter: host_comments >= -1
Filter: host_downtimes >= -1
Filter: comments >= -1
Filter: downtimes >= -1
Or: 4
Or: 9
OutputFormat: csv
"""
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print "r1", response
        # test_host_099 matches by name
        # test_host_098 matches by address (test_host_098 has 127.0.0.99)
        self.assert_(response == """0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_098;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
0;test_host_099;0
""")

    def _test_display_name(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()
        request = """GET hosts
Filter: name = test_router_0
Columns: name display_name"""
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print response
        self.assertEqual('test_router_0;display_router_0\n', response)
        request = """GET services
Filter: host_name = test_host_000
Filter: description = test_unknown_00
Columns: description host_name display_name"""
        response, keepalive = self.livestatus_broker.livestatus.handle_request(request)
        print response
        self.assertEqual('test_unknown_00;test_host_000;display_unknown_00\n', response )

if __name__ == '__main__':
    #import cProfile
    command = """unittest.main()"""
    unittest.main()
