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

# On a dry-run the registry URL is empty (no login/push happens). Omit the prefix so the reference
# degrades to `name:version` rather than emitting a malformed `/name:version`. This keeps the output
# consistent with the tarball tag the dry-run build produces, so downstream Trivy/Grype scans resolve it.
if [ -n "$REGISTRY_URL" ]; then
  echo "image=$REGISTRY_URL/$IMAGE_NAME:$IMAGE_VERSION" >> $GITHUB_OUTPUT
else
  echo "image=$IMAGE_NAME:$IMAGE_VERSION" >> $GITHUB_OUTPUT
fi
