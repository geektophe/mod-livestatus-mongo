#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Gregory Starck, g.starck@gmail.com
#    Hartmut Goebel, h.goebel@goebel-consult.de
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


from types import GeneratorType
from collections import namedtuple
from mongo_mapping import table_class_map
from livestatus_mongo_datamanager import datamgr

import csv
import json
from StringIO import StringIO

try:
    from ujson import dumps, loads
except ImportError:
    try:
        from simplejson import dumps, loads, JSONEncoder
        # ujson's dumps() cannot handle a separator parameter, which is
        # needed to avoid unnecessary spaces in the json output
        # That's why simplejson and json manipulate the encoder class
        JSONEncoder.item_separator = ','
        JSONEncoder.key_separator = ':'
    except ImportError:
        from json import dumps, loads, JSONEncoder
        JSONEncoder.item_separator = ','
        JSONEncoder.key_separator = ':'

#############################################################################

from shinken.log import logger
from livestatus_query_error import LiveStatusQueryError

#############################################################################

Separators = namedtuple('Separators',
                        ('line', 'field', 'list', 'pipe')) # pipe is used within livestatus_broker.mapping


class LiveStatusListResponse(list):
    ''' A class to be able to recognize list of data/bytes to be sent vs plain data/bytes. '''

    def __iter__(self):
        '''Iter over the values and eventual sub-values. This so also
recursively iter of the values of eventual sub-LiveStatusListResponse. '''
        for value in super(LiveStatusListResponse, self).__iter__():
            if isinstance(value, (LiveStatusListResponse, GeneratorType)):
                for v2 in value:
                    yield v2
            else:
                yield value

    def total_len(self):
        '''
        :return: The total "len" of what's contained in this LiveStatusListResponse instance.
If this instance contains others LiveStatusListResponse instances then their total_len() will also be summed
If this instance contains generators then they will be exhausted and their generated data will replace the
generator value at its index in this list.
        '''
        tot = 0
        for idx in range(len(self)):
            value = self[idx]
            if isinstance(value, GeneratorType):
                newlist = LiveStatusListResponse()
                for generated_data in value:
                    newlist.append(generated_data)
                    tot += len(generated_data)
                self[idx] = newlist
            elif isinstance(value, LiveStatusListResponse):
                tot += value.total_len()
            else:
                tot += len(value)
        return tot

    def clean(self):
        idx = len(self) - 1
        while idx >= 0:
            v = self[idx]
            if isinstance(v, LiveStatusListResponse):
                v.clean()
            idx -= 1
        del self[:]


class LiveStatusResponse(object):
    """A class which represents the response to a LiveStatusRequest.

    Public functions:
    respond -- Add a header to the response text
    format_live_data -- Take the raw output and format it according to
    the desired output format (csv or json)

    """

    separators = Separators('\n', ';', ',', '|')

    def __init__(self, responseheader='off', outputformat='csv', keepalive='off', columnheaders='off', separators=separators):
        self.responseheader = responseheader
        self.outputformat = outputformat
        self.keepalive = keepalive
        self.columnheaders = columnheaders
        self.separators = separators
        self.statuscode = 200
        self.output = LiveStatusListResponse()

    def set_error(self, statuscode, data):
        del self.output[:]
        self.output.append( LiveStatusQueryError.messages[statuscode] % data )
        self.statuscode = statuscode

    def load(self, query):
        self.query = query

    def respond(self):
        if self.responseheader == 'fixed16':
            responselength = 1 + len(self.output) # 1 for the final '\n'
            self.output = '%3d %11d\n%s' % (
                self.statuscode,
                responselength,
                self.output
            )
        return self.output, self.keepalive

    def _format_json_python_value(self, value):
        if isinstance(value, bool):
            return 1 if value else 0
        else:
            return value

    def _format_csv_value(self, value):
        if isinstance(value, list):
            return self.separators.list.join(str(x) for x in value)
        elif isinstance(value, bool):
            return '1' if value else '0'
        else:
            try:
                return str(value)
            except UnicodeEncodeError as err:
                logger.warning('UnicodeEncodeError on str() of: %r : %s' % (value, err))
                return value.encode('utf-8', 'replace')
            except Exception as err:
                logger.warning('Unexpected error on str() of: %r : %s' % (value, err))
                return ''

    def _csv_end_row(self, row, line_nr=0):
        f = StringIO()
        writer = csv.writer(f, delimiter=self.separators.field, lineterminator=self.separators.line)
        writer.writerow(row)
        res = f.getvalue()[:-1]
        return '%s%s' % (
            self.separators.line if line_nr else '',
            res)

    def _json_end_row(self, row, line_nr=0):
        return (',' if line_nr else '') + dumps(row)

    def _python_end_row(self, row, line_nr=0):
        ret = [',' if line_nr else '']
        ret.append('[')
        for item in row:
            if isinstance(item, unicode):
                item = item.encode('UTF-8')
            ret.append(repr(item))
            ret.append(', ')
        if row:
            del ret[-1] # skip last ','
        ret.append(']')
        return ''.join(ret)

    _format_2_value_handler = {
        'csv':      (_csv_end_row, _format_csv_value),
        'json':     (_json_end_row, _format_json_python_value),
        'python':   (_python_end_row, _format_json_python_value)
    }

    def format_item(self, item, columns):
        """
        Format an item returing the requested columns only

        :param dict item: The item to format
        :param list columns: The requested columns
        :rtype: list
        :return: The object's columns
        """
        row = []
        for column in columns:
            try:
                mapping = table_class_map[self.query.table][column]
                attr = mapping.get('filters', {}).get('attr', column)
                if "function" in mapping:
                    value = mapping["function"](item)
                elif "datatype" in mapping:
                        datatype = mapping["datatype"]
                        default = datatype()
                        value = item.get(attr, default)
                        value = datatype(value)
                else:
                    value = item.get(attr, "")
                row.append(value)
            except Exception as e:
                raise LiveStatusQueryError(
                    450,
                    "failed to map value %s/%s: %s" %
                    (self.query.table, column, e)
                )
        return row

    def format_live_data_items(self, results, columns):
        if columns is None:
            columns = table_class_map[self.query.table].keys()
            # There is no pre-selected list of columns. In this case
            # we output all columns.

        headers = columns

        if self.outputformat != 'csv':
            showheader = self.columnheaders == 'on'
        else: # csv has a somehow more complicated showheader rule than json or python..
            showheader = (
                results and self.columnheaders == 'on'
                or (not results and (self.columnheaders != 'off' or not columns)))

        rows = []
        if showheader:
            rows.append(headers)
        for item in results:
            rows.append(self.format_item(item, columns))
        if self.outputformat == "json":
            return json.dumps(rows)
        if self.outputformat.startswith("python"):
            return repr(rows)
        else:
            f = StringIO()
            writer = csv.writer(f,
                delimiter=self.separators.field,
                lineterminator=self.separators.line
            )
            writer.writerow(rows)
            return f.getvalue()

    def format_live_data_stats(self, results, columns):
        rows = []
        for result in results:
            item = result.pop(0)
            row = []
            if item is None:
                pass
            elif len(item) == 1:
                row.append(item.values().pop(0))
            else:
                for column in columns:
                    attr = datamgr.get_column_attribute(self.query.table, column)
                    row.append(item.get(attr, ""))
            row.extend(result)
            rows.append(row)
        if self.outputformat == "json":
            return json.dumps(rows)
        elif self.outputformat.startswith("python"):
            return repr(rows)
        else:
            f = StringIO()
            writer = csv.writer(f,
                delimiter=self.separators.field,
                lineterminator=self.separators.line
            )
            writer.writerow(rows)
            return f.getvalue()

    def format_live_data(self, results, columns):
        '''

        :param results:
        :param columns:
        :return:
        '''
        if self.query.stats_query:
            self.output = self.format_live_data_stats(results, columns)
        else:
            self.output = self.format_live_data_items(results, columns)
