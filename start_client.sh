#! /bin/bash

set -e -x -o pipefail

# Poll dask scheduler healthcheck until it is healthy
curl --connect-timeout 5 \
	--max-time 10 \
	--retry 5 \
	--retry-delay 1 \
	--retry-max-time 60 \
	--retry-all-errors \
	--fail \
	$DASK_SCHEDULER_HOST:$DASK_SCHEDULER_DASHBOARD_PORT/health

python client.py $DASK_SCHEDULER_HOST:$DASK_SCHEDULER_PORT
