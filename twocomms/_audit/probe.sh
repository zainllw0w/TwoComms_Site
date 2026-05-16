#!/usr/bin/env bash
set -u
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
for path in "/" "/uk/" "/ru/" "/en/" "/about" "/uk/about" "/ru/about" "/en/about" "/catalog/" "/sitemap.xml" "/sitemap-static.xml"; do
  code=$(curl -sS -A "$UA" -o /dev/null -w "%{http_code}" "https://twocomms.shop$path")
  echo "$path -> HTTP $code"
done
echo "---"
curl -sS -L -A "$UA" -o /tmp/_www_root.html -w "WWW root -> HTTP %{http_code}, final=%{url_effective}, size=%{size_download}\n" "https://www.twocomms.shop/"
