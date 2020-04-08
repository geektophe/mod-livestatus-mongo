#!/usr/bin/python

# -*- coding: utf-8 -*-

# Copyright (C) 2009-2014:
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

from shinken.util import safe_print
from shinken.misc.sorter import hst_srv_sort, last_state_change_earlier
from shinken.misc.filter import only_related_to
from pprint import pprint
import pymongo

class DataManager(object):
    def __init__(self):
        self.db = None

    def load(self, db):
        self.db = db

    def normalize(self, obj):
        if hasattr(obj, "get_name"):
            return obj.get_name()
        elif isinstance(obj, list):
            return [self.normalize(o) for o in obj]
        elif isinstance(obj, dict):
            return dict([(k, self.normalize(v)) for k, v in obj.items()])
        else:
            return obj

    def manage_brok(self, brok):
        """
        Manages a received brok

        :param Brok brok: The brok to manage
        """
        handler_name = "manage_%s_brok" % brok.type
        handler = getattr(self, handler_name, None)
        if handler is not None:
            handler(brok)

    def manage_program_status_brok(self, brok):
        """
        Display brok content

        :param Brok brok: The brok object to update object from
        """
        print("Brok: %s" % brok.type)
        pprint(brok.data)

    def manage_initial_host_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("host", brok)

    def manage_initial_hostgroup_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("hostgroup", brok)

    def manage_initial_service_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("service", brok)

    def manage_initial_servicegroup_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("servicegroup", brok)

    def manage_initial_contact_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("contact", brok)

    def manage_initial_contactgroup_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("contactgroup", brok)

    def manage_initial_timeperiod_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("timeperiod", brok)

    def manage_initial_command_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("command", brok)

    def manage_initial_scheduler_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("scheduler", brok)

    def manage_initial_poller_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("poller", brok)

    def manage_initial_reactionner_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("reactionner", brok)

    def manage_initial_broker_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("broker", brok)

    def manage_initial_receiver_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("receiver", brok)

    def manage_initial_broks_done_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        print("Brok: %s" % brok.type)
        pprint(brok.data)

    def manage_update_program_status_brok(self, brok):
        """
        Display brok content

        :param Brok brok: The brok object to update object from
        """
        print("Brok: %s" % brok.type)
        pprint(brok.data)

    def manage_update_host_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("host", brok)

    def manage_update_service_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("service", brok)

    def manage_update_broker_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("broker", brok)

    def manage_update_receiver_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("receiver", brok)

    def manage_update_reactionner_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("reactionner", brok)

    def manage_update_poller_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("poller", brok)

    def manage_update_scheduler_status_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("scheduler", brok)

    def manage_host_check_result_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("host", brok)

    def manage_host_next_schedule_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("host", brok)

    def manage_service_check_result_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("service", brok)

    def manage_service_next_schedule_brok(self, brok):
        """
        Updates and object from the brok data

        :param Brok brok: The brok object to update object from
        """
        self.update_object("service", brok)

    def update_object(self, object_type, brok):
        """
        Updates and object in the database from the brok data

        :param str objct_type: The object type
        :param Brok brok: The brok object to update object from
        """
        # Parses brok
        if brok.data.get("host_name") == "test_host_005" and brok.data.get("service_description") == "test_ok_00":
            pprint(brok.data)
        data = {}
        for name, value in brok.data.items():
            if name == "dateranges":
                continue
            else:
                data[name] = self.normalize(value)
        # Insert brok into database
        # Services are particular because their name is a combination of
        # host_name and service_description
        if object_type == "service":
            object_name = "%s/%s" % (
                data["host_name"],
                data["service_description"]
            )
        else:
            object_name = data["%s_name" % object_type]
        collection = getattr(self.db, "%ss" % object_type)
        count = collection.count({"_id": object_name})
        if not count:
            data["_id"] = object_name
            collection.insert_one(data)
        else:
            collection.update(
                {"_id": object_name},
                {"$set": data}
            )

    def find(self, table, query, limit=None):
        """
        General purpose MongoDB find() query

        :rtype: iterator
        :return: The query result
        """
        collection = getattr(self.db, table)
        if limit is None:
            return collection.find(query).sort(
                "_id",
                pymongo.ASCENDING
            )
        else:
            return collection.find(query).limit(limit).sort(
                "_id",
                pymongo.ASCENDING
            )


    def count(self, table, query):
        """
        General purpose MongoDB count() query

        :rtype: iterator
        :return: The query result
        """
        collection = getattr(self.db, table)
        return collection.count(query)

    def aggregate(self, table, query):
        """
        General purpose MongoDB aggregate() query

        :rtype: iterator
        :return: The query result
        """
        collection = getattr(self.db, table)
        return collection.aggregate(query)

    # UI will launch us names in str, we got unicode
    # in our rg, so we must manage it here
    def get_host(self, hname):
        hname = hname.decode('utf8', 'ignore')
        collection = getattr(self.db, "hosts")
        return collection.find_one({"_id": hname})

    def get_service(self, hname, sdesc):
        hname = hname.decode('utf8', 'ignore')
        sdesc = sdesc.decode('utf8', 'ignore')
        collection = getattr(self.db, "services")
        key = "%s/%s" % (hname, sdesc)
        return collection.find_one({"_id": key})

    def get_all_hosts_and_services(self):
        all = []
        all.extend(self.rg.hosts)
        all.extend(self.rg.services)
        return all

    def get_contact(self, name):
        name = name.decode('utf8', 'ignore')
        collection = getattr(self.db, "contacts")
        return collection.find_one({"_id": name})

    def get_contactgroup(self, name):
        name = name.decode('utf8', 'ignore')
        collection = getattr(self.db, "contactgroups")
        return collection.find_one({"_id": name})

    def get_contacts(self):
        collection = getattr(self.db, "contacts")
        return collection.find()

    def get_hostgroups(self):
        collection = getattr(self.db, "contactgroups")
        return collection.find()

    def get_hostgroup(self, name):
        name = name.decode('utf8', 'ignore')
        collection = getattr(self.db, "hostgroups")
        return collection.find_one({"_id": name})

    def get_servicegroups(self):
        collection = getattr(self.db, "servicegroups")
        return collection.find()

    def get_servicegroup(self, name):
        name = name.decode('utf8', 'ignore')
        collection = getattr(self.db, "servicegroups")
        return collection.find_one({"_id": name})

    # Get the hostgroups sorted by names, and zero size in the end
    # if selected one, put it in the first place
    def get_hostgroups_sorted(self, selected=''):
        r = []
        selected = selected.strip()

        hg_names = [hg.get_name() for hg in self.rg.hostgroups
                    if len(hg.members) > 0 and hg.get_name() != selected]
        hg_names.sort()
        hgs = [self.rg.hostgroups.find_by_name(n) for n in hg_names]
        hgvoid_names = [hg.get_name() for hg in self.rg.hostgroups
                        if len(hg.members) == 0 and hg.get_name() != selected]
        hgvoid_names.sort()
        hgvoids = [self.rg.hostgroups.find_by_name(n) for n in hgvoid_names]

        if selected:
            hg = self.rg.hostgroups.find_by_name(selected)
            if hg:
                r.append(hg)

        r.extend(hgs)
        r.extend(hgvoids)

        return r

    def get_hosts(self):
        collection = getattr(self.db, "hosts")
        return collection.find()

    def get_services(self):
        collection = getattr(self.db, "services")
        return collection.find()

    def get_schedulers(self):
        collection = getattr(self.db, "schedulers")
        return collection.find()

    def get_pollers(self):
        collection = getattr(self.db, "pollers")
        return collection.find()

    def get_brokers(self):
        collection = getattr(self.db, "brokers")
        return collection.find()

    def get_receivers(self):
        collection = getattr(self.db, "receivers")
        return collection.find()

    def get_reactionners(self):
        collection = getattr(self.db, "reactionners")
        return collection.find()

    def get_program_start(self):
        for c in self.rg.configs.values():
            return c.program_start
        return None

    def get_realms(self):
        return self.rg.realms

    def get_realm(self, r):
        collection = getattr(self.db, "realms")
        return collection.find()

    # Get the hosts tags sorted by names, and zero size in the end
    def get_host_tags_sorted(self):
        collection = getattr(self.db, "realms")
        hosts = collection.find(projection={"_id": 0, "tags": 1})
        tags = []
        for host in hosts:
            tags.extend(host["tags"])
        return
        r = []
        names = self.rg.tags.keys()
        names.sort()
        for n in names:
            r.append((n, self.rg.tags[n]))
        return r

    # Get the hosts tagged with a specific tag
    def get_hosts_tagged_with(self, tag):
        r = []
        for h in self.get_hosts():
            if tag in h.get_host_tags():
                r.append(h)
        return r

    # Get the services tags sorted by names, and zero size in the end
    def get_service_tags_sorted(self):
        r = []
        names = self.rg.services_tags.keys()
        names.sort()
        for n in names:
            r.append((n, self.rg.services_tags[n]))
        return r

    def get_important_impacts(self):
        res = []
        for s in self.rg.services:
            if s.is_impact and s.state not in ['OK', 'PENDING']:
                if s.business_impact > 2:
                    res.append(s)
        for h in self.rg.hosts:
            if h.is_impact and h.state not in ['UP', 'PENDING']:
                if h.business_impact > 2:
                    res.append(h)
        return res

    # Returns all problems
    def get_all_problems(self, to_sort=True, get_acknowledged=False):
        res = []
        if not get_acknowledged:
            res.extend([s for s in self.rg.services
                        if s.state not in ['OK', 'PENDING'] and
                        not s.is_impact and not s.problem_has_been_acknowledged and
                        not s.host.problem_has_been_acknowledged])
            res.extend([h for h in self.rg.hosts
                        if h.state not in ['UP', 'PENDING'] and
                        not h.is_impact and not h.problem_has_been_acknowledged])
        else:
            res.extend([s for s in self.rg.services
                        if s.state not in ['OK', 'PENDING'] and not s.is_impact])
            res.extend([h for h in self.rg.hosts
                        if h.state not in ['UP', 'PENDING'] and not h.is_impact])

        if to_sort:
            res.sort(hst_srv_sort)
        return res

    # returns problems, but the most recent before
    def get_problems_time_sorted(self):
        pbs = self.get_all_problems(to_sort=False)
        pbs.sort(last_state_change_earlier)
        return pbs

    # Return all non managed impacts
    def get_all_impacts(self):
        res = []
        for s in self.rg.services:
            if s.is_impact and s.state not in ['OK', 'PENDING']:
                # If s is acked, pass
                if s.problem_has_been_acknowledged:
                    continue
                # We search for impacts that were NOT currently managed
                if len([p for p in s.source_problems if not p.problem_has_been_acknowledged]) > 0:
                    res.append(s)
        for h in self.rg.hosts:
            if h.is_impact and h.state not in ['UP', 'PENDING']:
                # If h is acked, pass
                if h.problem_has_been_acknowledged:
                    continue
                # We search for impacts that were NOT currently managed
                if len([p for p in h.source_problems if not p.problem_has_been_acknowledged]) > 0:
                    res.append(h)
        return res

    # Return the number of problems
    def get_nb_problems(self):
        return len(self.get_all_problems(to_sort=False))

    # Get the number of all problems, even the ack ones
    def get_nb_all_problems(self, user):
        res = []
        res.extend([s for s in self.rg.services
                    if s.state not in ['OK', 'PENDING'] and not s.is_impact])
        res.extend([h for h in self.rg.hosts
                    if h.state not in ['UP', 'PENDING'] and not h.is_impact])
        return len(only_related_to(res, user))

    # Return the number of impacts
    def get_nb_impacts(self):
        return len(self.get_all_impacts())

    def get_nb_elements(self):
        return len(self.rg.services) + len(self.rg.hosts)

    def get_important_elements(self):
        res = []
        # We want REALLY important things, so business_impact > 2, but not just IT elements that are
        # root problems, so we look only for config defined my_own_business_impact value too
        res.extend([s for s in self.rg.services
                    if (s.business_impact > 2 and not 0 <= s.my_own_business_impact <= 2)])
        res.extend([h for h in self.rg.hosts
                    if (h.business_impact > 2 and not 0 <= h.my_own_business_impact <= 2)])
        print "DUMP IMPORTANT"
        for i in res:
            safe_print(i.get_full_name(), i.business_impact, i.my_own_business_impact)
        return res

    # For all business impacting elements, and give the worse state
    # if warning or critical
    def get_overall_state(self):
        h_states = [h.state_id for h in self.rg.hosts
                    if h.business_impact > 2 and h.is_impact and h.state_id in [1, 2]]
        s_states = [s.state_id for s in self.rg.services
                    if s.business_impact > 2 and s.is_impact and s.state_id in [1, 2]]
        print "get_overall_state:: hosts and services business problems", h_states, s_states
        if len(h_states) == 0:
            h_state = 0
        else:
            h_state = max(h_states)
        if len(s_states) == 0:
            s_state = 0
        else:
            s_state = max(s_states)
        # Ok, now return the max of hosts and services states
        return max(h_state, s_state)

    # Same but for pure IT problems
    def get_overall_it_state(self):
        h_states = [h.state_id for h in self.rg.hosts if h.is_problem and h.state_id in [1, 2]]
        s_states = [s.state_id for s in self.rg.services if s.is_problem and s.state_id in [1, 2]]
        if len(h_states) == 0:
            h_state = 0
        else:
            h_state = max(h_states)
        if len(s_states) == 0:
            s_state = 0
        else:
            s_state = max(s_states)
        # Ok, now return the max of hosts and services states
        return max(h_state, s_state)

    # Get percent of all Services
    def get_per_service_state(self):
        all_services = self.rg.services
        problem_services = []
        problem_services.extend([s for s in self.rg.services
                                 if s.state not in ['OK', 'PENDING'] and not s.is_impact])
        if len(all_services) == 0:
            res = 0
        else:
            res = int(100 - (len(problem_services) * 100) / float(len(all_services)))
        return res

    # Get percent of all Hosts
    def get_per_hosts_state(self):
        all_hosts = self.rg.hosts
        problem_hosts = []
        problem_hosts.extend([s for s in self.rg.hosts
                              if s.state not in ['UP', 'PENDING'] and not s.is_impact])
        if len(all_hosts) == 0:
            res = 0
        else:
            res = int(100 - (len(problem_hosts) * 100) / float(len(all_hosts)))
        return res

    # For all business impacting elements, and give the worse state
    # if warning or critical
    def get_len_overall_state(self):
        h_states = [h.state_id for h in self.rg.hosts
                    if h.business_impact > 2 and h.is_impact and h.state_id in [1, 2]]
        s_states = [s.state_id for s in self.rg.services
                    if s.business_impact > 2 and s.is_impact and s.state_id in [1, 2]]
        print "get_len_overall_state:: hosts and services business problems", h_states, s_states
        # Just return the number of impacting elements
        return len(h_states) + len(s_states)

    # Return a tree of {'elt': Host, 'fathers': [{}, {}]}
    def get_business_parents(self, obj, levels=3):
        res = {'node': obj, 'fathers': []}
        # if levels == 0:
        #     return res

        for i in obj.parent_dependencies:
            # We want to get the levels deep for all elements, but
            # go as far as we should for bad elements
            if levels != 0 or i.state_id != 0:
                par_elts = self.get_business_parents(i, levels=levels - 1)
                res['fathers'].append(par_elts)

        print "get_business_parents::Give elements", res
        return res

    # Ok, we do not have true root problems, but we can try to guess isn't it?
    # We can just guess for services with the same services of this host in fact
    def guess_root_problems(self, obj):
        if obj.__class__.my_type != 'service':
            return []
        r = [s for s in obj.host.services if s.state_id != 0 and s != obj]
        return r

datamgr = DataManager()
