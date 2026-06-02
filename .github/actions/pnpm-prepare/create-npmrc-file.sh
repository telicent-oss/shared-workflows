#!/bin/bash

# Append private-registry auth tokens to the user-level ~/.npmrc. We deliberately
# do NOT write the project .npmrc: the consumer repo commits its own .npmrc with
# the scope→registry mappings and engine-strict, and pnpm merges user + project
# npmrc at install time. Keeping the tokens in the ephemeral ~/.npmrc means they
# never land in the checked-out tree.
{
  echo "//npm.fontawesome.com/:_authToken=${FONT_AWESOME_KEY}"
  echo "//npm.pkg.github.com/:_authToken=${PACKAGE_PAT}"
} >> ~/.npmrc
