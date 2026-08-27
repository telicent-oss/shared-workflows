#!/bin/bash

echo "node: $(node -v) | npm: $(npm -v)"
if [ "$DETECTED_PM" = "pnpm" ]; then
  echo "pnpm: $(pnpm -v)"
else
  echo "yarn: $(yarn -v)"
fi
echo "npm default registry: $(npm config get registry)"
echo "@telicent-io registry: $(npm config get @telicent-io:registry)"
echo "@fortawesome registry: $(npm config get @fortawesome:registry)"

for v in HTTP_PROXY HTTPS_PROXY NO_PROXY http_proxy https_proxy no_proxy; do
    if [ -n "${!v:-}" ]; then echo "$v is set"; fi
done

for h in registry.npmjs.org npm.pkg.github.com npm.fontawesome.com; do
    echo "== $h =="
    getent hosts "$h" || true
    curl -sSIL --max-time 10 "https://$h/" | head -n 1 || echo "curl FAIL: $h"
done

if [ "$DETECTED_PM" = "pnpm" ] && [ -f pnpm-lock.yaml ]; then
    echo "Lockfile: pnpm-lock.yaml"
elif [ -f yarn.lock ]; then
    echo "Hosts from yarn.lock:"
    awk '/^  resolved /{print $2}' yarn.lock | sed -E 's/^"//; s/"$//' | awk -F/ '{print $3}' | sort -u
fi
