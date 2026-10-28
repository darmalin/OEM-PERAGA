#!/bin/sh
# Run by the nginx image before it starts (/docker-entrypoint.d). With EMS_CAMPAIGN_BASE_URL
# set (https://events.example.com), adds the forms host and sends /r/{token} on the desk host
# there with a 301, so links and posters made before the move keep working. Without it the
# forms stay at /r/{token} on the desk host.
set -eu

conf=/etc/nginx/conf.d/campaign-host.conf
redirect=/etc/nginx/campaign/redirect.conf
rm -f "$conf" "$redirect"

origin=$(printf '%s' "${EMS_CAMPAIGN_BASE_URL:-}" | sed 's#/*$##')
[ -z "$origin" ] && exit 0
if ! printf '%s' "$origin" | grep -Eq '^https?://[A-Za-z0-9.-]+(:[0-9]+)?$'; then
    echo "15-campaign-host: EMS_CAMPAIGN_BASE_URL must look like https://events.example.com" >&2
    exit 1
fi
host=$(printf '%s' "$origin" | sed -E 's#^https?://##; s#:[0-9]+$##')

sed "s#__CAMPAIGN_HOST__#$host#g" /etc/nginx/campaign/host.conf.template > "$conf"
printf 'rewrite "^/r/([A-Za-z0-9_-]{12})/?$" %s/$1 permanent;\n' "$origin" > "$redirect"
echo "15-campaign-host: campaign forms on $origin"
