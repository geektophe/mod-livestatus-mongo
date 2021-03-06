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

import sys
import time
import unittest
from pprint import pprint
from livestatus_test import LivestatusTestBase
from livestatus.mongo_mapping import table_class_map

sys.setcheckinterval(10000)

class LivestatusTest(LivestatusTestBase):

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

        query = """GET services
Columns: host_name host_num_services host_num_services_crit host_num_services_hard_crit host_num_services_hard_ok host_num_services_hard_unknown host_num_services_hard_warn host_num_services_ok host_num_services_pending host_num_services_unknown host_num_services_warn host_worst_service_state host_worst_service_hard_state
Filter: host_name = test_host_005
Filter: description = test_ok_00
OutputFormat: python
"""

        expected_result = [['test_host_005', 20, 0, 0, 20, 0, 0, 0, 0, 0, 0, 0, 0]]
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

        expected_result = [['test_host_005', 20, 1, 2, 13, 1, 2, 0, 0, 0, 0, 2, 2]]
        self.execute_and_assert(query, expected_result)

        query = """GET services
Columns: host_services
Filter: host_name = test_host_005
Filter: description = test_ok_00
OutputFormat: python
"""

        expected_result = [
            'test_ok_05',
            'test_ok_10',
            'test_random_06',
            'test_ok_14',
            'test_warning_13',
            'test_ok_01',
            'test_ok_04',
            'test_ok_12',
            'test_random_03',
            'test_pending_17',
            'test_ok_07',
            'test_warning_02',
            'test_critical_11',
            'test_ok_16',
            'test_ok_19',
            'test_ok_00',
            'test_ok_15',
            'test_unknown_08',
            'test_pending_18',
            'test_flap_09'
        ]

        def assert_host_services(result):
            self.assertEqual(len(result[0][0]), 20)
            for s in expected_result:
                self.assertIn(s, result[0][0])

        self.execute_and_assert(query, assert_host_services)

        query = """GET services
Columns: host_services_with_info
Filter: host_name = test_host_005
Filter: description = test_ok_00
OutputFormat: python
"""

        expected_result = [
            ('test_ok_05', 0, 1, 'OK'),
            ('test_ok_10', 0, 1, 'OK'),
            ('test_random_06', 2, 1, 'C'),
            ('test_ok_14', 0, 1, 'OK'),
            ('test_warning_13', 1, 1, 'W'),
            ('test_ok_01', 0, 1, 'OK'),
            ('test_ok_04', 0, 1, 'OK'),
            ('test_ok_12', 0, 1, 'OK'),
            ('test_random_03', 1, 1, 'W'),
            ('test_pending_17', 0, 1, 'OK'),
            ('test_ok_07', 0, 1, 'OK'),
            ('test_warning_02', 1, 1, 'W'),
            ('test_critical_11', 2, 1, 'C'),
            ('test_ok_16', 0, 1, 'OK'),
            ('test_ok_19', 0, 1, 'OK'),
            ('test_ok_00', 0, 1, 'OK'),
            ('test_ok_15', 0, 1, 'OK'),
            ('test_unknown_08', 3, 1, 'U'),
            ('test_pending_18', 0, 1, 'OK'),
            ('test_flap_09', 2, 1, 'C')
        ]

        self.execute_and_assert(query, assert_host_services)

        query = """GET services
Columns: host_services_with_state
Filter: host_name = test_host_005
Filter: description = test_ok_00
OutputFormat: python
"""

        expected_result = [
            ('test_ok_05', 0, 1),
            ('test_ok_10', 0, 1),
            ('test_random_06', 2, 1),
            ('test_ok_14', 0, 1),
            ('test_warning_13', 1, 1),
            ('test_ok_01', 0, 1),
            ('test_ok_04', 0, 1),
            ('test_ok_12', 0, 1),
            ('test_random_03', 1, 1),
            ('test_pending_17', 0, 1),
            ('test_ok_07', 0, 1),
            ('test_warning_02', 1, 1),
            ('test_critical_11', 2, 1),
            ('test_ok_16', 0, 1),
            ('test_ok_19', 0, 1),
            ('test_ok_00', 0, 1),
            ('test_ok_15', 0, 1),
            ('test_unknown_08', 3, 1),
            ('test_pending_18', 0, 1),
            ('test_flap_09', 2, 1)
        ]

        self.execute_and_assert(query, assert_host_services)

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

        # Tests in initial state
        query_stats = """GET hostgroups
Columns: name num_hosts_pending num_hosts_unreach num_hosts_up num_hosts_down worst_host_state num_hosts num_services num_services_ok num_services_hard_ok num_services_warn num_services_hard_warn num_services_crit num_services_hard_crit num_services_unknown num_services_hard_unknown worst_service_state worst_service_hard_state
Filter: name = hostgroup_01
OutputFormat: python
"""

        expected_result = [['hostgroup_01', 0, 0, 2, 0, 0, 2, 40, 0, 40, 0, 0, 0, 0, 0, 0, 0, 0]]
        self.execute_and_assert(query_stats, expected_result)

        query_state = """GET hostgroups
Columns: name members_with_state
Filter: name = hostgroup_01
OutputFormat: python
"""

        expected_result = [
            ['hostgroup_01', [('test_host_000', 0, 1), ('test_host_005', 0, 1)]]
        ]
        self.execute_and_assert(query_state, expected_result)

        # Tests with hosts or services state
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
        self.execute_and_assert(query_stats, expected_result)

        query = """GET hostgroups
Columns: name members_with_state
Filter: name = hostgroup_01
OutputFormat: python
"""

        expected_result = [
            ['hostgroup_01', [('test_host_000', 0, 1), ('test_host_005', 1, 1)]]
        ]
        self.execute_and_assert(query_state, expected_result)

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

        # Tests in initial state
        query_stats = """GET servicegroups
Columns: name num_hosts_pending num_hosts_unreach num_hosts_up num_hosts_down worst_host_state num_hosts num_services num_services_ok num_services_hard_ok num_services_warn num_services_hard_warn num_services_crit num_services_hard_crit num_services_unknown num_services_hard_unknown worst_service_state worst_service_hard_state
Filter: name = servicegroup_06
OutputFormat: python
"""

        expected_result = [['servicegroup_06', 0, 0, 2, 0, 0, 2, 40, 0, 40, 0, 0, 0, 0, 0, 0, 0, 0]]
        self.execute_and_assert(query_stats, expected_result)

        query_state = """GET servicegroups
Columns: name members_with_state
Filter: name = servicegroup_06
OutputFormat: python
"""

        expected_result = [
            ['servicegroup_06', [
                ('test_host_005', 'test_critical_11', 0, 1),
                ('test_host_005', 'test_flap_09', 0, 1),
                ('test_host_005', 'test_ok_00', 0, 1),
                ('test_host_005', 'test_ok_01', 0, 1),
                ('test_host_005', 'test_ok_04', 0, 1),
                ('test_host_005', 'test_ok_05', 0, 1),
                ('test_host_005', 'test_ok_07', 0, 1),
                ('test_host_005', 'test_ok_10', 0, 1),
                ('test_host_005', 'test_ok_12', 0, 1),
                ('test_host_005', 'test_ok_14', 0, 1),
                ('test_host_005', 'test_ok_15', 0, 1),
                ('test_host_005', 'test_ok_16', 0, 1),
                ('test_host_005', 'test_ok_19', 0, 1),
                ('test_host_005', 'test_pending_17', 0, 1),
                ('test_host_005', 'test_pending_18', 0, 1),
                ('test_host_005', 'test_random_03', 0, 1),
                ('test_host_005', 'test_random_06', 0, 1),
                ('test_host_005', 'test_unknown_08', 0, 1),
                ('test_host_005', 'test_warning_02', 0, 1),
                ('test_host_005', 'test_warning_13', 0, 1),
                ('test_host_006', 'test_flap_08', 0, 1),
                ('test_host_006', 'test_ok_03', 0, 1),
                ('test_host_006', 'test_ok_06', 0, 1),
                ('test_host_006', 'test_ok_07', 0, 1),
                ('test_host_006', 'test_ok_09', 0, 1),
                ('test_host_006', 'test_ok_10', 0, 1),
                ('test_host_006', 'test_ok_11', 0, 1),
                ('test_host_006', 'test_ok_12', 0, 1),
                ('test_host_006', 'test_ok_13', 0, 1),
                ('test_host_006', 'test_ok_15', 0, 1),
                ('test_host_006', 'test_ok_18', 0, 1),
                ('test_host_006', 'test_pending_00', 0, 1),
                ('test_host_006', 'test_random_01', 0, 1),
                ('test_host_006', 'test_random_04', 0, 1),
                ('test_host_006', 'test_random_14', 0, 1),
                ('test_host_006', 'test_random_16', 0, 1),
                ('test_host_006', 'test_random_19', 0, 1),
                ('test_host_006', 'test_unknown_05', 0, 1),
                ('test_host_006', 'test_warning_02', 0, 1),
                ('test_host_006', 'test_warning_17', 0, 1)
            ]]
        ]
        self.execute_and_assert(query_state, expected_result)

        # Tests with hosts or services state
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
        self.execute_and_assert(query_stats, expected_result)

        expected_result = [
            [u'servicegroup_06', [
                ('test_host_005', 'test_critical_11', 2, 1),
                ('test_host_005', 'test_flap_09', 2, 1),
                ('test_host_005', 'test_ok_00', 0, 1),
                ('test_host_005', 'test_ok_01', 0, 1),
                ('test_host_005', 'test_ok_04', 0, 1),
                ('test_host_005', 'test_ok_05', 0, 1),
                ('test_host_005', 'test_ok_07', 0, 1),
                ('test_host_005', 'test_ok_10', 0, 1),
                ('test_host_005', 'test_ok_12', 0, 1),
                ('test_host_005', 'test_ok_14', 0, 1),
                ('test_host_005', 'test_ok_15', 0, 1),
                ('test_host_005', 'test_ok_16', 0, 1),
                ('test_host_005', 'test_ok_19', 0, 1),
                ('test_host_005', 'test_pending_17', 0, 1),
                ('test_host_005', 'test_pending_18', 0, 1),
                ('test_host_005', 'test_random_03', 1, 1),
                ('test_host_005', 'test_random_06', 2, 1),
                ('test_host_005', 'test_unknown_08', 3, 1),
                ('test_host_005', 'test_warning_02', 1, 1),
                ('test_host_005', 'test_warning_13', 1, 1),
                ('test_host_006', 'test_flap_08', 0, 1),
                ('test_host_006', 'test_ok_03', 0, 1),
                ('test_host_006', 'test_ok_06', 0, 1),
                ('test_host_006', 'test_ok_07', 0, 1),
                ('test_host_006', 'test_ok_09', 0, 1),
                ('test_host_006', 'test_ok_10', 0, 1),
                ('test_host_006', 'test_ok_11', 0, 1),
                ('test_host_006', 'test_ok_12', 0, 1),
                ('test_host_006', 'test_ok_13', 0, 1),
                ('test_host_006', 'test_ok_15', 0, 1),
                ('test_host_006', 'test_ok_18', 0, 1),
                ('test_host_006', 'test_pending_00', 0, 1),
                ('test_host_006', 'test_random_01', 0, 1),
                ('test_host_006', 'test_random_04', 0, 1),
                ('test_host_006', 'test_random_14', 0, 1),
                ('test_host_006', 'test_random_16', 0, 1),
                ('test_host_006', 'test_random_19', 0, 1),
                ('test_host_006', 'test_unknown_05', 0, 1),
                ('test_host_006', 'test_warning_02', 0, 1),
                ('test_host_006', 'test_warning_17', 0, 1)
            ]]
        ]
        self.execute_and_assert(query_state, expected_result)

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
