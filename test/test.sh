#!/bin/sh

for filename in \
	test_filter_query.py \
	test_comments.py \
	test_downtimes.py \
	test_grouping_query.py \
	test_stats.py \
	test_limit.py \
	test_authuser.py \
	test_cross_collection_query.py \
	test_modified_attributes.py \
	test_modified_attributes.py \
	test_problems.py \
	test_timeperiods.py
do
	echo "==============================================================================="
	echo "|"
	echo "| Executing test $filename"
	echo "|"
	echo "==============================================================================="
	python2 $filename
	if [ $? -ne 0 ]; then
		exit 1
	fi
done
