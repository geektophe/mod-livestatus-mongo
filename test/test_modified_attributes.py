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
