#!/bin/bash

echo "node-version=$(node -v)" >> $GITHUB_OUTPUT
echo "yarn-cache-dir=$(yarn cache dir)" >> $GITHUB_OUTPUT
