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

from datetime import datetime, date, timedelta
from pprint import pprint
import calendar


class TimeperiodError(Exception):
    pass


class Timeperiods(object):

    instance = None

    @classmethod
    def get_instance(cls):
        if cls.instance is None:
            cls.instance = Timeperiods()
        return cls.instance

    def __init__(self):
        self.timeperiods = {}

    def __contains__(self, timeperiod):
        if isinstance(timeperiod, dict):
            return timeperiod["timeperiod_name"] in self.timeperiods
        else:
            return timeperiod in self.timeperiods

    def add_timeperiod(self, timeperiod):
        self.timeperiods[timeperiod["timeperiod_name"]] = Timeperiod(timeperiod)
        return timeperiod

    def is_active(self, timeperiod_name):
        """
        Tells if a timeperiod is currently active
        """
        if timeperiod_name not in self.timeperiods:
            raise TimeperiodError("unknown timeperiod %s" % timeperiod_name)
        timeperiod = self.timeperiods[timeperiod_name]
        is_active = timeperiod.is_active()
        if is_active is False:
            return False
        for exclude_name in timeperiod["exclude"]:
            exclude = self.timeperiods[exclude_name]
            if exclude.is_active() is True:
                return False
        return True

    def clear(self):
        """
        Clears cached timeperiods
        """
        self.timeperiods.clear()


class Timeperiod(dict):

    weekdays = {  # NB : 0 based : 0 == monday
        'monday': 0,
        'tuesday': 1,
        'wednesday': 2,
        'thursday': 3,
        'friday': 4,
        'saturday': 5,
        'sunday': 6
    }
    months = {  # NB : 1 based : 1 == january..
        'january': 1,
        'february': 2,
        'march': 3,
        'april': 4,
        'may': 5,
        'june': 6,
        'july': 7,
        'august': 8,
        'september': 9,
        'october': 10,
        'november': 11,
        'december': 12
    }

    def __init__(self, data):
        self.update(data)
        self.dateranges = []
        for daterange in self["dateranges"]:
            self.dateranges.extend(
                self.parse_daterange(daterange)
            )

    def parse_date_experssion(self, year, mon, mday, wday, wday_offset, day):
        """
        Parses a the date part of a timeperiod's daterange
        """
        cal = calendar.Calendar(calendar.MONDAY)
        now = datetime.now()
        dt = []
        # Parses date
        # Year parsing
        if year == 0:
            dt.append(now.year)
        else:
            dt.append(year)
        # Month parsing
        if mon == 0:
            dt.append(now.month)
        elif mon in self.months:
            dt.append(self.months[mon])
        else:
            dt.append(mon)
        # Day parsing day of month
        if mday == 0 and wday == 0:
            dt.append(now.day)
        elif mday != 0:
            month = dt[-1]
            monthdays = [
                d.day for d in cal.itermonthdates(*dt)
                if d.month == month
            ]
            dt.append(monthdays[mday])
        # Parsing day of week
        elif day in self.weekdays:
            monthdays = [
                d.day for d in cal.itermonthdates(*dt)
                if d.month == month
                and d.weekday() == day
                and d.isocalendar()[1] == d.isocalendar()[1]
            ]
            dt.append(monthdays[-1])
        elif wday in self.weekdays:
            month = dt[-1]
            day = self.weekdays[wday]
            monthdays = [
                d.day for d in cal.itermonthdates(*dt)
                if d.month == month and d.weekday() == day
            ]
            print("monthdays for %s: %s" % (day, monthdays))
            print("offset: %s" % wday_offset)
            if wday_offset == 0:
                dt.append(monthdays[-1])
            elif wday_offset <= len(monthdays):
                dt.append(monthdays[wday_offset-1])
            else:
                monthdays = [
                    d.day for d in cal.itermonthdates(*dt)
                    if d.month == month
                ]
                dt.append(monthdays[-1])
        else:
            dt.append(now.day)
        return date(*dt)

    def parse_daterange(self, daterange):
        """
        Parses a daterange, returning a list of (datetime_start, datetime_end)
        tuples.

        :param dict daterange: The daterange to parse
        :rtype: list
        :return: The list of (datetime_start, datetime_end)
        """
        sdt = self.parse_date_experssion(
            daterange.get("syear", 0),
            daterange.get("smon", 0),
            daterange.get("smday", 0),
            daterange.get("swday", 0),
            daterange.get("swday_offset", 0),
            daterange.get("day", 0)
        )
        edt = self.parse_date_experssion(
            daterange.get("eyear", 0),
            daterange.get("emon", 0),
            daterange.get("emday", 0),
            daterange.get("ewday", 0),
            daterange.get("ewday_offset", 0),
            daterange.get("day", 0)
        )
        dates = [sdt]
        skip_interval = daterange.get("skip_interval", 0)
        if skip_interval == 0:
            delta = timedelta(days=1)
        else:
            delta = timedelta(days=skip_interval)

        while True:
            next_dt = dates[-1] + delta
            if next_dt <= edt:
                dates.append(next_dt)
            else:
                break
        dateranges = []
        for dt in dates:
            next_dt = dt + timedelta(days=1)
            for timerange in daterange["timeranges"]:
                if timerange["hstart"] < 24:
                    dt_start = datetime(
                        dt.year,
                        dt.month,
                        dt.day,
                        timerange["hstart"],
                        timerange["mstart"]
                    )
                else:
                    dt_start = datetime(
                        next_dt.year,
                        next_dt.month,
                        next_dt.day,
                        0,
                        0
                    )
                if timerange["hend"] < 24:
                    dt_end = datetime(
                        dt.year,
                        dt.month,
                        dt.day,
                        timerange["hend"],
                        timerange["mend"]
                    )
                else:
                    dt_end = datetime(
                        next_dt.year,
                        next_dt.month,
                        next_dt.day,
                        0,
                        0
                    )
                dateranges.append((dt_start, dt_end))
        return dateranges

    def is_active(self):
        """
        Tells if a timeperiod is currently active
        """
        now = datetime.now()
        for daterange in self.dateranges:
            if now >= daterange[0] and now <= daterange[1]:
                return True
        return False


timeperiods = Timeperiods.get_instance()
