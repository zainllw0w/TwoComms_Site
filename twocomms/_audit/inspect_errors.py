import json, os
HERE=os.path.dirname(os.path.abspath(__file__))
data=json.load(open(os.path.join(HERE,'raw_results.json'),encoding='utf-8'))
print('=== ERRORS ===')
for r in data:
    if r.get('error'):
        print(r['url'], r.get('status'), r.get('issues'))
print()
print('=== UK PAGES WITH LEAKS ===')
for r in data:
    if r.get('locale')=='uk' and r.get('leaks'):
        print(r['url'])
        for l in r['leaks']:
            print('  ', l['field'], '->', l['markers'], '|', l['value'][:100])
