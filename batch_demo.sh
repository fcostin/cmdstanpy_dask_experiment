#!/bin/bash

set -x -e -o pipefail

docker build -t cmdstanpy_dask:dev -f cmdstanpy_dask.Dockerfile .

function teardown()
{
	docker-compose down
}
trap teardown EXIT

docker-compose up -d scheduler
docker-compose up -d --scale worker=4 worker
docker-compose run client
