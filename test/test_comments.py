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
from shinken.objects.module import Module
from shinken.comment import Comment
from shinken.log import logger
logger.setLevel(logging.DEBUG)

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

    def test_downtime_comments(self):
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

        host1 = self.sched.hosts.find_by_name("test_host_005")
        host2 = self.sched.hosts.find_by_name("test_host_009")

        self.scheduler_loop(5, [[host1, 1, 'D'], [host2, 2, 'U']])
        self.update_broker()

        duration = 6000
        now = int(time.time())
        end = now + duration

        for host in (host1, host2):
            cmd = "[%lu] SCHEDULE_HOST_DOWNTIME;%s;%d;%d;1;0;%d;test_contact;dth" % \
                (now, host.host_name, now, end, duration)
            self.sched.run_external_command(cmd)
        for service in (svc1, svc2, svc3, svc4, svc5, svc6, svc7):
            cmd = "[%lu] SCHEDULE_SVC_DOWNTIME;%s;%s;%d;%d;0;0;%d;test_contact;dts" % \
                (now, service.host.host_name, service.service_description,
                 now, end, duration)
            self.sched.run_external_command(cmd)
        self.sched.update_downtimes_and_comments()
        self.scheduler_loop(1, [], do_sleep=False)  # push the downtime notification
        self.worker_loop() # push the downtime notification
        time.sleep(10)
        self.update_broker()

        query = """GET comments
Columns: host_name author
Filter: is_service = 0
OutputFormat: python
"""

        expected_result = [
            ['test_host_005', '(Nagios Process)'],
            ['test_host_009', '(Nagios Process)']
        ]

        def assert_host_comments(result):
            self.assertEqual(len(result), 2)
            for comment in expected_result:
                self.assertIn(comment, result)

        self.execute_and_assert(query, assert_host_comments)

        query = """GET comments
Columns: host_name service_description author
Filter: is_service = 1
OutputFormat: python
"""

        expected_result = [
            ['test_host_001', 'test_warning_19', '(Nagios Process)'],
            ['test_host_003', 'test_warning_03', '(Nagios Process)'],
            ['test_host_005', 'test_warning_02', '(Nagios Process)'],
            ['test_host_000', 'test_critical_03', '(Nagios Process)'],
            ['test_host_005', 'test_critical_11', '(Nagios Process)'],
            ['test_host_007', 'test_critical_02', '(Nagios Process)'],
            ['test_host_008', 'test_critical_13', '(Nagios Process)']
        ]

        def assert_service_comments(result):
            self.assertEqual(len(result), 7)
            for comment in expected_result:
                self.assertIn(comment, result)

        self.execute_and_assert(query, assert_service_comments)

        for host in (host1, host2):
            cmd = "[%lu] DEL_ALL_HOST_DOWNTIMES;%s" % \
                (now, host.host_name)
            self.sched.run_external_command(cmd)
        for service in (svc1, svc2, svc3, svc4, svc5, svc6, svc7):
            cmd = "[%lu] DEL_ALL_SVC_DOWNTIMES;%s;%s" % \
                (now, service.host.host_name, service.service_description)
            self.sched.run_external_command(cmd)
        self.sched.update_downtimes_and_comments()
        self.scheduler_loop(1, [], do_sleep=False)  # push the downtime notification
        self.worker_loop() # push the downtime notification
        time.sleep(10)
        self.update_broker()

        query = """GET comments
Columns: host_name author
Filter: is_service = 0
OutputFormat: python
"""

        expected_result = []
        self.execute_and_assert(query, expected_result)

        query = """GET comments
Columns: host_name service_description author
Filter: is_service = 1
OutputFormat: python
"""

        expected_result = []
        self.execute_and_assert(query, expected_result)

    def test_sticky_comments(self):
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

        host1 = self.sched.hosts.find_by_name("test_host_005")
        host2 = self.sched.hosts.find_by_name("test_host_009")

        self.scheduler_loop(5, [[host1, 1, 'D'], [host2, 2, 'U']])
        self.update_broker()

        for host in (host1, host2):
            cmd = "[%lu] ACKNOWLEDGE_HOST_PROBLEM;%s;1;1;1;test_contact;ackh" % \
                (now, host.host_name)
            self.sched.run_external_command(cmd)
        for service in (svc1, svc2, svc3, svc4, svc5, svc6, svc7):
            cmd = "[%lu] ACKNOWLEDGE_SVC_PROBLEM;%s;%s;1;1;1;test_contact;acks" % \
                (now, service.host_name, service.service_description)
            self.sched.run_external_command(cmd)
        self.sched.update_downtimes_and_comments()
        self.scheduler_loop(1, [], do_sleep=False)  # push the downtime notification
        time.sleep(10)
        self.update_broker()

        query = """GET comments
Columns: host_name author comment
Filter: is_service = 0
OutputFormat: python
"""

        expected_host_result = [
	    ['test_host_005', 'test_contact', 'ackh'],
            ['test_host_009', 'test_contact', 'ackh']
        ]

        def assert_host_comments(result):
            self.assertEqual(len(result), 2)
            for comment in expected_host_result:
                self.assertIn(comment, result)

        self.execute_and_assert(query, assert_host_comments)

        query = """GET comments
Columns: host_name service_description author comment
Filter: is_service = 1
OutputFormat: python
"""

        expected_service_result = [
            ['test_host_001', 'test_warning_19', 'test_contact', 'acks'],
            ['test_host_003', 'test_warning_03', 'test_contact', 'acks'],
            ['test_host_005', 'test_warning_02', 'test_contact', 'acks'],
            ['test_host_000', 'test_critical_03', 'test_contact', 'acks'],
            ['test_host_005', 'test_critical_11', 'test_contact', 'acks'],
            ['test_host_007', 'test_critical_02', 'test_contact', 'acks'],
            ['test_host_008', 'test_critical_13', 'test_contact', 'acks']
        ]

        def assert_service_comments(result):
            self.assertEqual(len(result), 7)
            for comment in expected_service_result:
                self.assertIn(comment, result)

        self.execute_and_assert(query, assert_service_comments)

        for host in (host1, host2):
            cmd = "[%lu] REMOVE_HOST_ACKNOWLEDGEMENT;%s" % \
                (now, host.host_name)
            self.sched.run_external_command(cmd)
        for service in (svc1, svc2, svc3, svc4, svc5, svc6, svc7):
            cmd = "[%lu] REMOVE_SVC_ACKNOWLEDGEMENT;%s;%s" % \
                (now, service.host.host_name, service.service_description)
            self.sched.run_external_command(cmd)
        self.sched.update_downtimes_and_comments()
        self.scheduler_loop(1, [], do_sleep=False)  # push the downtime notification
        self.worker_loop() # push the downtime notification
        time.sleep(10)
        self.update_broker()

        query = """GET comments
Columns: host_name author comment
Filter: is_service = 0
OutputFormat: python
"""

        self.execute_and_assert(query, assert_host_comments)

        query = """GET comments
Columns: host_name service_description author comment
Filter: is_service = 1
OutputFormat: python
"""

        expected_result = []
        self.execute_and_assert(query, assert_service_comments)

    def test_non_sticky_comments(self):
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

        host1 = self.sched.hosts.find_by_name("test_host_005")
        host2 = self.sched.hosts.find_by_name("test_host_009")

        self.scheduler_loop(5, [[host1, 1, 'D'], [host2, 2, 'U']])
        self.update_broker()

        for host in (host1, host2):
            cmd = "[%lu] ACKNOWLEDGE_HOST_PROBLEM;%s;0;1;0;test_contact;ackh" % \
                (now, host.host_name)
            self.sched.run_external_command(cmd)
        for service in (svc1, svc2, svc3, svc4, svc5, svc6, svc7):
            cmd = "[%lu] ACKNOWLEDGE_SVC_PROBLEM;%s;%s;0;1;0;test_contact;acks" % \
                (now, service.host_name, service.service_description)
            self.sched.run_external_command(cmd)
        self.sched.update_downtimes_and_comments()
        self.scheduler_loop(1, [], do_sleep=False)  # push the downtime notification
        time.sleep(10)
        self.update_broker()

        query = """GET comments
Columns: host_name author comment
Filter: is_service = 0
OutputFormat: python
"""

        expected_host_result = [
	    ['test_host_005', 'test_contact', 'ackh'],
            ['test_host_009', 'test_contact', 'ackh']
        ]

        def assert_host_comments(result):
            self.assertEqual(len(result), 2)
            for comment in expected_host_result:
                self.assertIn(comment, result)

        self.execute_and_assert(query, assert_host_comments)

        query = """GET comments
Columns: host_name service_description author comment
Filter: is_service = 1
OutputFormat: python
"""

        expected_service_result = [
            ['test_host_001', 'test_warning_19', 'test_contact', 'acks'],
            ['test_host_003', 'test_warning_03', 'test_contact', 'acks'],
            ['test_host_005', 'test_warning_02', 'test_contact', 'acks'],
            ['test_host_000', 'test_critical_03', 'test_contact', 'acks'],
            ['test_host_005', 'test_critical_11', 'test_contact', 'acks'],
            ['test_host_007', 'test_critical_02', 'test_contact', 'acks'],
            ['test_host_008', 'test_critical_13', 'test_contact', 'acks']
        ]

        def assert_service_comments(result):
            self.assertEqual(len(result), 7)
            for comment in expected_service_result:
                self.assertIn(comment, result)

        self.execute_and_assert(query, assert_service_comments)

        for host in (host1, host2):
            cmd = "[%lu] REMOVE_HOST_ACKNOWLEDGEMENT;%s" % \
                (now, host.host_name)
            self.sched.run_external_command(cmd)
        for service in (svc1, svc2, svc3, svc4, svc5, svc6, svc7):
            cmd = "[%lu] REMOVE_SVC_ACKNOWLEDGEMENT;%s;%s" % \
                (now, service.host.host_name, service.service_description)
            self.sched.run_external_command(cmd)
        self.sched.update_downtimes_and_comments()
        self.scheduler_loop(1, [], do_sleep=False)  # push the downtime notification
        self.worker_loop() # push the downtime notification
        time.sleep(10)
        self.update_broker()

        query = """GET comments
Columns: host_name author comment
Filter: is_service = 0
OutputFormat: python
"""

        self.execute_and_assert(query, [])

        query = """GET comments
Columns: host_name service_description author comment
Filter: is_service = 1
OutputFormat: python
"""

        expected_result = []
        self.execute_and_assert(query, [])


if __name__ == '__main__':
    #import cProfile
    command = """unittest.main()"""
    unittest.main()
