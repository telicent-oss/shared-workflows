#!/bin/bash

export NODE_OPTIONS="${NODE_OPTIONS:-} --dns-result-order=ipv4first"
LOCAL_MACHINE=false yarn install $FROZEN_LOCKFILE $NETWORK_CONCURRENCY $VERBOSE $ADDITIONAL_ARGS
