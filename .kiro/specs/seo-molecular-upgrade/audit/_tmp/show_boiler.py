import json
with open('/Users/zainllw0w/TwoComms/site/.kiro/specs/seo-molecular-upgrade/audit/_tmp/boilerplate.json') as f:
    b = json.load(f)
print(f'Total chunks: {len(b)}')
for ch in b[:30]:
    print(f'[{ch["page_count"]}] {ch["text"][:160]}')
    print(f'    pages: {ch["pages"][:10]}')
