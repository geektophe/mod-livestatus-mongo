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

    def test_authuser(self):
        """
        Tests limitting results what's authorized to authenticated user
        """
        query = """GET hosts
Columns: name alias
Filter: name ~ test_host_00[0-9]
OutputFormat: python
"""

        def assert_no_authuser(result):
            self.assertEqual(len(result), 10)
            self.assertIn(['test_host_001', 'pending_001'], result)
            self.assertIn(['test_host_009', 'up_009'], result)

        self.execute_and_assert(query, assert_no_authuser)

        query = """GET hosts
Columns: name alias
Filter: name ~ test_host_00[0-9]
AuthUser: test_contact_02
OutputFormat: python
"""

        def assert_authuser(result):
            self.assertEqual(len(result), 1)
            self.assertIn(['test_host_001', 'pending_001'], result)
            self.assertNotIn(['test_host_009', 'up_009'], result)

        self.execute_and_assert(query, assert_authuser)


if __name__ == '__main__':
    #import cProfile
    command = """unittest.main()"""
    unittest.main()
