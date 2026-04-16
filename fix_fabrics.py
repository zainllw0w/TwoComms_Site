import re

path = "twocomms/storefront/custom_print_config.py"
with open(path, "r") as f:
    orig = f.read()

# Fix hoodie fabrics
hoodie_fabrics = """        "fabrics": {
            "regular": [
                {"value": "standard", "label": "База", "price_delta": 0, "included_in_base": True},
                {"value": "premium", "label": "Преміум", "price_delta": 250, "included_in_base": False},
            ],
            "oversize": [
                {"value": "premium", "label": "Преміум", "price_delta": 0, "included_in_base": True},
            ],
        },"""

broken_fabrics = re.compile(r'"fabrics": \{\n            "regular": \[\n.*?\n            \],\n            "oversize": \[\n.*?\n            \],\n        \},', re.DOTALL)

parts = orig.split('"tshirt": {')
hoodie_part = parts[0]
tshirt_part = parts[1]

# Only replace in hoodie_part!
hoodie_part = broken_fabrics.sub(hoodie_fabrics, hoodie_part, count=1)

# Fix tshirt sleeve
tshirt_part = re.sub(r'"zones": \["front", "back", "sleeve"\]', r'"zones": ["front", "back"]', tshirt_part, count=1)

orig = hoodie_part + '"tshirt": {' + tshirt_part

with open(path, "w") as f:
    f.write(orig)

print("done")
