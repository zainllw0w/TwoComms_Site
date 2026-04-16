import json

path = "twocomms/storefront/custom_print_config.py"
with open(path, "r") as f:
    orig = f.read()

# Replace fabrics
new_fabrics = """        "fabrics": {
            "regular": [
                {"value": "standard", "label": "Стандарт", "price_delta": 0, "included_in_base": True},
                {"value": "premium", "label": "Преміум", "price_delta": 150, "included_in_base": False},
            ],
            "oversize": [
                {"value": "standard", "label": "Стандарт", "price_delta": 0, "included_in_base": True},
                {"value": "premium", "label": "Преміум", "price_delta": 150, "included_in_base": False},
                {
                    "value": "thermo", "label": "Термо", "price_delta": 500, "included_in_base": False,
                    "info_title": "Футболка з WOW-ефектом❤️",
                    "info_desc": "Реагує на тепло тіла та змінює колір.\\nІдеальна для образів, які привертають увагу.",
                    "colors": [
                        {"value": "thermo_green", "label": "Зелений (Термо)", "hex": "#8ba38d"},
                        {"value": "thermo_pink", "label": "Рожевий (Термо)", "hex": "#e78ba7"}
                    ]
                },
            ],
        },"""

import re
pattern = re.compile(r'        "fabrics": \{\n            "regular": \[\n.*?\n            \],\n            "oversize": \[\n.*?\n            \],\n        \},', re.DOTALL)
orig = pattern.sub(new_fabrics, orig)

# Replace add_ons
new_addons = """        "add_ons": [
            {
                "value": "ribbed_neck",
                "label": "Щільна горловина (Рібана)",
                "price_delta": 0,
                "icon": "ribbed_neck",
                "badge": "Включено",
                "hint": "Еластична горловина, що довго не втрачає форму.",
                "auto_include_condition": "premium_or_oversize"
            },
            {
                "value": "twill_tape",
                "label": "Кіперна стрічка",
                "price_delta": 0,
                "icon": "twill_tape",
                "badge": "Включено",
                "hint": "Укріплення задньої частини шиї, підвищений комфорт.",
                "auto_include_condition": "premium_or_oversize"
            }
        ],"""

# we need to find `"add_ons": [],` for tshirt! Wait wait, let's just do a string replace
# Since it is lines 365, "default_zones": [], "add_ons": [], "pricing": {
orig = orig.replace('"add_ons": [],\n        "pricing": {', new_addons + '\n        "pricing": {')

with open(path, "w") as f:
    f.write(orig)

print("done")
