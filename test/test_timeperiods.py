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

    def test_datamgr_timeperiods(self):
        datamgr = self.livestatus_broker.livestatus.datamgr
        self.assertTrue(
            datamgr.is_timeperiod_active("24x7")
        )
        self.assertFalse(
            datamgr.is_timeperiod_active("none_24x7")
        )

    def test_timeperiods_host(self):
        query = """GET hosts
Columns: name check_period in_check_period notification_period in_notification_period
Filter: name = test_host_005
OutputFormat: python
"""

        expected_result = [
            ["test_host_005", "24x7", True, "24x7", True]
        ]

        self.execute_and_assert(query, expected_result)


    def test_timeperiods_service(self):
        query = """GET services
Columns: host_name description check_period in_check_period notification_period in_notification_period
Filter: host_name = test_host_005
Filter: description = test_ok_00
OutputFormat: python
"""

        expected_result = [
            ["test_host_005", "test_ok_00", "24x7", True, "none_24x7", False]
        ]
        self.execute_and_assert(query, expected_result)

        query = """GET services
Columns: host_name description host_check_period host_in_check_period host_notification_period host_in_notification_period
Filter: host_name = test_host_005
Filter: description = test_ok_00
OutputFormat: python
"""

        expected_result = [
            ["test_host_005", "test_ok_00", "24x7", True, "24x7", True]
        ]
        self.execute_and_assert(query, expected_result)


if __name__ == '__main__':
    #import cProfile
    command = """unittest.main()"""
    unittest.main()
