#!/bin/bash

echo "node: $(node -v) | npm: $(npm -v) | yarn: $(yarn -v)"
echo "npm default registry: $(npm config get registry)"
echo "@telicent-io registry: $(npm config get @telicent-io:registry)"
echo "@fortawesome registry: $(npm config get @fortawesome:registry)"

# Show if proxy env vars exist (names only)
for v in HTTP_PROXY HTTPS_PROXY NO_PROXY http_proxy https_proxy no_proxy; do
    if [ -n "${!v:-}" ]; then echo "$v is set"; fi
done
# DNS + reachability checks
for h in registry.npmjs.org registry.yarnpkg.com npm.pkg.github.com npm.fontawesome.com; do
    echo "== $h =="
    getent hosts "$h" || true
    curl -sSIL --max-time 10 "https://$h/" | head -n 1 || echo "curl FAIL: $h"
done

# What hosts yarn.lock will fetch from
if [ -f yarn.lock ]; then
    echo "Hosts from yarn.lock:"
    awk '/^  resolved /{print $2}' yarn.lock | sed -E 's/^"//; s/"$//' | awk -F/ '{print $3}' | sort -u
fi