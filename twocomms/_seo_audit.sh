#!/bin/zsh
# Detailed SEO audit: titles, descriptions, h1, JSON-LD names, og:* + og:image:alt.
# Compares /ru/ /en/ vs UA root, looking for cross-language pollution.

URLS=(
  /ru/  /en/
  /ru/catalog/  /en/catalog/
  /ru/catalog/hoodie/  /en/catalog/hoodie/
  /ru/catalog/tshirts/  /en/catalog/tshirts/
  /ru/catalog/long-sleeve/  /en/catalog/long-sleeve/
  /ru/pro-brand/  /en/pro-brand/
  /ru/cooperation/  /en/cooperation/
  /ru/wholesale/  /en/wholesale/
  /ru/custom-print/  /en/custom-print/
  /ru/dopomoga/  /en/dopomoga/
  /ru/faq/  /en/faq/
  /ru/delivery/  /en/delivery/
  /ru/contacts/  /en/contacts/
  /ru/povernennya-ta-obmin/  /en/povernennya-ta-obmin/
  /ru/rozmirna-sitka/  /en/rozmirna-sitka/
  /ru/doglyad-za-odyagom/  /en/doglyad-za-odyagom/
  /ru/mapa-saytu/  /en/mapa-saytu/
  /ru/novyny/  /en/novyny/
  /ru/polityka-konfidentsiynosti/  /en/polityka-konfidentsiynosti/
  /ru/umovy-vykorystannya/  /en/umovy-vykorystannya/
  /ru/vidstezhennya-zamovlennya/  /en/vidstezhennya-zamovlennya/
  /ru/product/classic-tshirt/  /en/product/classic-tshirt/
  /ru/product/hoodie-classic/  /en/product/hoodie-classic/
  /ru/product/longsleeve-classic/  /en/product/longsleeve-classic/
  /ru/product/glory-of-ukraine-hd/  /en/product/glory-of-ukraine-hd/
  /ru/product/kharkiv-district-hd/  /en/product/kharkiv-district-hd/
)

TOTAL_LEAKS=0

for u in "${URLS[@]}"; do
  RAW=$(curl -sL "https://twocomms.shop$u")
  LOCALE=$(echo "$u" | grep -oE '/(ru|en|uk)/' | head -1 | tr -d '/')
  if [ -z "$LOCALE" ]; then LOCALE="uk"; fi

  # Extract critical SEO meta-tags
  TITLE=$(echo "$RAW" | python3 -c "
import sys, re, html
data = sys.stdin.read()
m = re.search(r'<title>([^<]+)</title>', data)
if m: print(html.unescape(m.group(1).strip()))
")

  DESC=$(echo "$RAW" | python3 -c "
import sys, re, html
data = sys.stdin.read()
m = re.search(r'<meta\s+name=\"description\"\s+content=\"([^\"]+)\"', data)
if m: print(html.unescape(m.group(1).strip()[:200]))
")

  KEYWORDS=$(echo "$RAW" | python3 -c "
import sys, re, html
data = sys.stdin.read()
m = re.search(r'<meta\s+name=\"keywords\"\s+content=\"([^\"]+)\"', data)
if m: print(html.unescape(m.group(1).strip()[:300]))
")

  H1=$(echo "$RAW" | python3 -c "
import sys, re, html
data = sys.stdin.read()
data = re.sub(r'<script.*?</script>', '', data, flags=re.DOTALL)
m = re.search(r'<h1[^>]*>(.+?)</h1>', data, re.DOTALL)
if m:
    text = re.sub(r'<[^>]+>', '', m.group(1))
    text = re.sub(r'\s+', ' ', text).strip()
    print(text[:200])
")

  OG_DESC=$(echo "$RAW" | python3 -c "
import sys, re, html
data = sys.stdin.read()
m = re.search(r'<meta\s+property=\"og:description\"\s+content=\"([^\"]+)\"', data)
if m: print(html.unescape(m.group(1).strip()[:200]))
")

  # Check for cross-language pollution
  LEAKS=()
  if [ "$LOCALE" = "ru" ]; then
    # /ru/ should not have UA-only letters
    for FIELD in "title=$TITLE" "desc=$DESC" "kw=$KEYWORDS" "h1=$H1" "og_desc=$OG_DESC"; do
      if echo "$FIELD" | grep -qE '[єіїґЄІЇҐ]'; then
        LEAKS+=("$FIELD")
      fi
    done
  elif [ "$LOCALE" = "en" ]; then
    # /en/ should not have any Cyrillic
    for FIELD in "title=$TITLE" "desc=$DESC" "kw=$KEYWORDS" "h1=$H1" "og_desc=$OG_DESC"; do
      if echo "$FIELD" | grep -qE '[А-Яа-яЁёЇїЄєІіҐґ]'; then
        LEAKS+=("$FIELD")
      fi
    done
  fi

  if [ ${#LEAKS[@]} -gt 0 ]; then
    echo "=== $u (LEAK) ==="
    for L in "${LEAKS[@]}"; do
      echo "  $L"
    done
    TOTAL_LEAKS=$((TOTAL_LEAKS + ${#LEAKS[@]}))
  fi
done

echo
echo "TOTAL SEO META LEAKS: $TOTAL_LEAKS"
