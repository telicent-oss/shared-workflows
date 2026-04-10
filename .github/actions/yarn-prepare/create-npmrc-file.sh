#!/bin/bash

# npm config set "@telicent-io:registry" "https://npm.pkg.github.com/"
# npm config set "//npm.pkg.github.com/:_authToken" $PACKAGE_PAT
# npm config set "@awesome.me:registry" https://npm.fontawesome.com/
# npm config set "@fortawesome:registry" https://npm.fontawesome.com/
# npm config set  "//npm.fontawesome.com/:_authToken" $FONT_AWESOME_KEY
cat > .npmrc << EOF
registry=https://registry.npmjs.org/
@telicent-io:registry=https://npm.pkg.github.com/
//npm.pkg.github.com/:_authToken=$PACKAGE_PAT
@awesome.me:registry=https://npm.fontawesome.com/
@fortawesome:registry=https://npm.fontawesome.com/
//npm.fontawesome.com/:_authToken=$FONT_AWESOME_KEY
always-auth=true
EOF