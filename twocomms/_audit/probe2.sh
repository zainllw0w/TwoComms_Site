#!/usr/bin/env sh
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
for path in "/about/" "/ru/about/" "/en/about/" "/faq/" "/ru/faq/" "/en/faq/" "/catalog/hoodie/" "/ru/catalog/hoodie/" "/en/catalog/hoodie/" "/sitemap.xml" "/ru/sitemap.xml" "/sitemap-static.xml" "/sitemap-products.xml"; do
  code=$(curl -sS -A "$UA" -o /dev/null -w "%{http_code}" "https://twocomms.shop$path")
  echo "$path -> HTTP $code"
done