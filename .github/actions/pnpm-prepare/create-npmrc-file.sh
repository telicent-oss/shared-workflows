#!/bin/bash

# Append private-registry auth tokens to the user-level ~/.npmrc. We deliberately
# do NOT write the project .npmrc: the consumer repo commits its own .npmrc with
# the scope→registry mappings and engine-strict, and pnpm merges user + project
# npmrc at install time. Keeping the tokens in the ephemeral ~/.npmrc means they
# never land in the checked-out tree.
{
  echo "registry=https://registry.npmjs.org/"
  echo "@telicent-io:registry=https://npm.pkg.github.com/"
  echo "//npm.pkg.github.com/:_authToken=${PACKAGE_PAT}"
  echo "@awesome.me:registry=https://npm.fontawesome.com/"
  echo "@fortawesome:registry=https://npm.fontawesome.com/"
  echo "//npm.fontawesome.com/:_authToken=${FONT_AWESOME_KEY}"
} >> ~/.npmrc
