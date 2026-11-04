#!/bin/sh
# Run by the nginx image before it starts (/docker-entrypoint.d). With EMS_PORTAL_BASE_URL set
# (https://exhibitor.example.com), adds the portal host and sends /exhibitor/... on the desk host
# there with a 301. Without it (dev, staging) the portal stays at /exhibitor/ on the desk host.
# The API builds invitation links from the same variable (exhibitors/service.py portal_url).
set -eu

conf=/etc/nginx/conf.d/portal-host.conf
redirect=/etc/nginx/portal/redirect.conf
rm -f "$conf" "$redirect"

origin=$(printf '%s' "${EMS_PORTAL_BASE_URL:-}" | sed 's#/*$##')
[ -z "$origin" ] && exit 0
if ! printf '%s' "$origin" | grep -Eq '^https?://[A-Za-z0-9.-]+(:[0-9]+)?$'; then
    echo "16-portal-host: EMS_PORTAL_BASE_URL must look like https://exhibitor.example.com" >&2
    exit 1
fi
host=$(printf '%s' "$origin" | sed -E 's#^https?://##; s#:[0-9]+$##')

sed "s#__PORTAL_HOST__#$host#g" /etc/nginx/portal/host.conf.template > "$conf"
printf 'rewrite "^/exhibitor(/.*)?$" %s$1 permanent;\n' "$origin" > "$redirect"
echo "16-portal-host: exhibitor portal on $origin"
