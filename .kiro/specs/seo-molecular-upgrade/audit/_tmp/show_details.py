import json
with open('/Users/zainllw0w/TwoComms/site/.kiro/specs/seo-molecular-upgrade/audit/_tmp/metrics.json') as f:
    m = json.load(f)
focus = ['home','catalog-root','cat-tshirts','cat-hoodie','cat-long-sleeve','sup-pro-brand','sup-custom-print','sup-faq','pdp-classic-tshirt','pdp-hoodie-classic','pdp-kharkiv-district-ts','pdp-my-little-baby','pdp-where-mi-present-hd']
for name in focus:
    p = m[name]
    print(f'== {name} ==')
    print(f'  H2 first5 ({p.get("h2_count",0)} total):')
    for h in p.get('h2_first5',[]):
        print(f'    - {h}')
    print(f'  TOP15 KW: {p.get("top15_keywords",[])}')
    print(f'  FIRST_P ({p.get("first_p_len",0)} ch): {(p.get("first_paragraph") or "")[:300]}')
    print(f'  body_text_preview: {p.get("body_text_preview","")[:300]}')
    print()
