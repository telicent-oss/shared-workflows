#!/bin/bash

error_exit() {
    echo "Error: $1"
    exit 1
}
    
# Validate the registry type.
if [[ "$REGISTRY" != "aws" && "$REGISTRY" != "quay" ]]; then
    error_exit "Unsupported registry '$REGISTRY'. Supported values are 'aws' or 'quay'."
fi

# Validate registry supporting inputs.
if [[ "$REGISTRY" == "quay" && ( -z $QUAY_USERNAME || -z $QUAY_TOKEN ) ]]; then
    error_exit "Inputs 'quay-username' and 'quay-token' are required when registry is 'quay'."
fi
