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

    def test_limit(self):
        """
        Tests result count limitting
        """
        query = """GET hosts
Columns: name alias
Filter: name ~ test_host_00[0-9]
OutputFormat: python
"""

        expected_length = 10

        def assert_len(result):
            self.assertEqual(len(result), expected_length)

        self.execute_and_assert(query, assert_len)

        query = """GET hosts
Columns: name alias
Filter: name ~ test_host_00[0-9]
Limit: 5
OutputFormat: python
"""

        expected_length = 5

        def assert_len(result):
            self.assertEqual(len(result), expected_length)

        self.execute_and_assert(query, assert_len)


if __name__ == '__main__':
    #import cProfile
    command = """unittest.main()"""
    unittest.main()
