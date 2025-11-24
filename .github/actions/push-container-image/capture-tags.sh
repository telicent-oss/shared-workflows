#!/bin/bash

error_exit() {
    echo "Error: $1"
    exit 1
}

case "$REGISTRY" in
  aws)
    REGISTRY_URL=$AWS_REGISTRY_URL;;
  quay)
    REGISTRY_URL=$QUAY_REGISTRY_URL;;
  *)
    error_exit "Unsupported registry '$REGISTRY'. Supported values are 'aws' or 'quay'.";;
esac

echo "image=$REGISTRY_URL/$IMAGE_NAME:$IMAGE_VERSION" >> $GITHUB_OUTPUT
