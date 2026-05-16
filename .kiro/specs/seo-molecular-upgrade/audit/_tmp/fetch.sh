#!/bin/bash
set -e
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 SEO-Audit-Bot"
BASE="https://twocomms.shop"
OUTDIR="/tmp/seo_audit/pages"
mkdir -p "$OUTDIR"
LIST="/Users/zainllw0w/TwoComms/site/.kiro/specs/seo-molecular-upgrade/audit/_tmp/fetch_list.txt"
while IFS='|' read -r name path; do
  [ -z "$name" ] && continue
  encoded=$(python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe='/?=&'))" "$path")
  url="${BASE}${encoded}"
  out="${OUTDIR}/${name}.html"
  echo "Fetching: $url -> $out"
  curl -sL --compressed --max-time 30 -A "$UA" -o "$out" "$url"
  size=$(wc -c < "$out")
  http_code=$(curl -sL -o /dev/null -w "%{http_code}" --max-time 15 -A "$UA" "$url")
  echo "  size=$size code=$http_code"
done < "$LIST"
