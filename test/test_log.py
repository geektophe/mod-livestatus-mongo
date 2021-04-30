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

sys.setcheckinterval(10000)

class LivestatusTest(LivestatusTestBase):

    def test_log_service(self):
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
        self.scheduler_loop(3, [[svc1, 1, 'W'], [svc2, 1, 'W'], [svc3, 1, 'W'], [svc4, 2, 'C'], [svc5, 3, 'U'], [svc6, 2, 'C'], [svc7, 2, 'C']])
        self.update_broker()
        # 1993O, 3xW, 3xC, 1xU

        query = """GET log
Columns: type host_name service_description state state_type current_host_state current_host_state_type contact_name current_contact_alias
Filter: host_name = test_host_005
OutputFormat: python"""

        expected_result = [
            ['SERVICE ALERT', 'test_host_005', 'test_warning_02', 1, 'SOFT', 0, 1, '', ''],
            ['SERVICE ALERT', 'test_host_005', 'test_critical_11', 3, 'SOFT', 0, 1, '', ''],
            ['SERVICE ALERT', 'test_host_005', 'test_warning_02', 1, 'HARD', 0, 1, '', ''],
            ['SERVICE ALERT', 'test_host_005', 'test_critical_11', 3, 'HARD', 0, 1, '', ''],
            ['SERVICE NOTIFICATION', 'test_host_005', 'test_warning_02', 1, 'WARNING', 0, 1, 'test_contact', 'test_contact_alias'],
            ['SERVICE NOTIFICATION', 'test_host_005', 'test_warning_02', 1, 'WARNING', 0, 1, 'test_contact_01', 'test_contact_alias_01'],
            ['SERVICE NOTIFICATION', 'test_host_005', 'test_critical_11', 3, 'UNKNOWN', 0, 1, 'test_contact', 'test_contact_alias'],
            ['SERVICE NOTIFICATION', 'test_host_005', 'test_critical_11', 3, 'UNKNOWN', 0, 1, 'test_contact_01', 'test_contact_alias_01']
        ]

        def assert_log(result):
            self.assertEqual(len(result), 10)
            for r in expected_result:
                self.assertIn(r, result)

        self.execute_and_assert(query, assert_log)

    def test_log_host(self):
        self.print_header()
        now = time.time()
        objlist = []
        for host in self.sched.hosts:
            objlist.append([host, 0, 'UP'])
        for service in self.sched.services:
            objlist.append([service, 0, 'OK'])
        self.scheduler_loop(1, objlist)
        self.update_broker()
        host = self.sched.hosts.find_by_name("test_host_005")

        self.scheduler_loop(5, [[host, 1, 'D']])
        self.update_broker()

        query = """GET log
Columns: type host_name state state_type current_host_state current_host_state_type contact_name current_contact_alias
Filter: host_name = test_host_005
OutputFormat: python"""

        expected_result = [
            ['HOST ALERT', 'test_host_005', 1, 'SOFT', 1, 1, '', ''],
            ['HOST ALERT', 'test_host_005', 1, 'HARD', 1, 1, '', ''],
            ['HOST NOTIFICATION', 'test_host_005', 1, 'DOWN', 1, 1, 'test_contact', 'test_contact_alias'],
            ['HOST NOTIFICATION', 'test_host_005', 1, 'DOWN', 1, 1, 'test_contact_01', 'test_contact_alias_01']
        ]

        def assert_log(result):
            self.assertEqual(len(result), 7)
            for r in expected_result:
                self.assertIn(r, result)

        self.execute_and_assert(query, assert_log)

if __name__ == '__main__':
    #import cProfile
    command = """unittest.main()"""
    unittest.main()
