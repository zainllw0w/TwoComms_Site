import re

path = "twocomms/storefront/custom_print_notifications.py"
with open(path, "r") as f:
    orig = f.read()

# Add ADDON_LABELS
addon_labels = """
ADDON_LABELS = {
    "lacing": "Люверси зі шнурками",
    "ribbed_neck": "Щільна горловина (Рібана)",
    "twill_tape": "Кіперна стрічка",
    "fleece": "З флісом",
    "no_fleece": "Без флісу"
}
"""
orig = re.sub(r'(TRIAGE_LABELS = \{.*?\n\})', r'\1\n' + addon_labels, orig, flags=re.DOTALL)

# Modify _snapshot_placements_text 
def repl1(m):
    return """
    mapped_addons = [ADDON_LABELS.get(a, a) for a in add_ons]
    if mapped_addons:
        parts.append(f"Add-ons: {', '.join(mapped_addons)}")
"""
orig = re.sub(r'    if add_ons:\n        parts\.append\(f"Add-ons: \{\', \'\.join\(add_ons\)\}"\)\n', repl1, orig)

# Find where lead.add_ons is processed in _build_message
# Actually, lead.add_ons isn't currently used in _build_message! 
# Let's insert it under "Виріб" section or "Макет / зони".
def repl2(m):
    return m.group(0) + """
    if getattr(lead, "add_ons", None):
        mapped_addons = [ADDON_LABELS.get(a, a) for a in lead.add_ons]
        parts.append(f"• <b>Доповнення:</b> {escape(', '.join(mapped_addons))}")
"""
orig = re.sub(r'            f"• <b>Конфігурація:</b> \{\' / \'\.join\(product_parts\)\}",\n        \]\n    \)', repl2, orig)


with open(path, "w") as f:
    f.write(orig)

print("done")
