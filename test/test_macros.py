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

    def test_simple_custom_variables(self):
        query = """GET hosts
Columns: name alias custom_variable_names
Filter: name = test_host_005
OutputFormat: python
"""

        expected_result = [
            [u'test_host_005', u'flap_005', [u'CUSTOM1', u'CUSTOM2']]
        ]
        self.execute_and_assert(query, expected_result)

        query = """GET hosts
Columns: name alias custom_variable_values
Filter: name = test_host_005
OutputFormat: python
"""

        expected_result = [
            [u'test_host_005', u'flap_005', [u'test_host_custom1', u'test_host_custom2']]
        ]
        self.execute_and_assert(query, expected_result)

        query = """GET hosts
Columns: name alias custom_variables
Filter: name = test_host_005
OutputFormat: python
"""

        expected_result = [
            [
                u'test_host_005', u'flap_005', [
                    (u'CUSTOM1', u'test_host_custom1'),
                    (u'CUSTOM2', u'test_host_custom2')
                ]
            ]
        ]
        self.execute_and_assert(query, expected_result)


if __name__ == '__main__':
    #import cProfile
    command = """unittest.main()"""
    unittest.main()
