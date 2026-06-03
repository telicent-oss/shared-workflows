#!/bin/bash

export NODE_OPTIONS="${NODE_OPTIONS:-} --dns-result-order=ipv4first"

if [ "$DETECTED_PM" = "pnpm" ]; then
  ARGS=""
  if [ "$FROZEN_LOCKFILE" = "true" ]; then
    ARGS="$ARGS --frozen-lockfile"
  fi
  LOCAL_MACHINE=false pnpm install $ARGS
else
  ARGS=""
  if [ "$FROZEN_LOCKFILE" = "true" ]; then
    ARGS="$ARGS --frozen-lockfile"
  fi
  if [ -n "$NETWORK_CONCURRENCY" ] && [ "$NETWORK_CONCURRENCY" != "" ]; then
    ARGS="$ARGS --network-concurrency $NETWORK_CONCURRENCY"
  fi
  if [ "$VERBOSE" = "true" ]; then
    ARGS="$ARGS --verbose"
  fi
  if [ -n "$ADDITIONAL_ARGS" ]; then
    ARGS="$ARGS $ADDITIONAL_ARGS"
  fi
  LOCAL_MACHINE=false yarn install $ARGS
fi
