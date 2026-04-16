import os

target_dir = "/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/img/configurator/ui/"
os.makedirs(target_dir, exist_ok=True)

svgs = {
    "size-a6.svg": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="9" y="10" width="6" height="8" rx="1" stroke="currentColor" stroke-dasharray="1.5 1.5" stroke-width="1.5" fill="rgba(215, 164, 80, 0.15)"/>
<path d="M4 4h16v16H4V4z" stroke="rgba(255, 255, 255, 0.1)" stroke-width="1"/>
</svg>''',

    "size-a5.svg": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="7" y="7" width="10" height="13.5" rx="1" stroke="currentColor" stroke-dasharray="1.5 1.5" stroke-width="1.5" fill="rgba(215, 164, 80, 0.15)"/>
<path d="M4 4h16v16H4V4z" stroke="rgba(255, 255, 255, 0.1)" stroke-width="1"/>
</svg>''',

    "size-a4.svg": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="5" y="4" width="14" height="18" rx="1.5" stroke="currentColor" stroke-dasharray="1.5 1.5" stroke-width="1.5" fill="rgba(215, 164, 80, 0.15)"/>
<path d="M2 2h20v20H2V2z" stroke="rgba(255, 255, 255, 0.1)" stroke-width="1"/>
</svg>''',

    "size-a3.svg": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="3" y="3" width="18" height="20" rx="1.5" stroke="currentColor" stroke-dasharray="2 2" stroke-width="1.5" fill="rgba(215, 164, 80, 0.15)"/>
</svg>''',

    "size-a2.svg": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="2" y="2" width="20" height="22" rx="2" stroke="currentColor" stroke-dasharray="2 2" stroke-width="2" fill="rgba(215, 164, 80, 0.15)"/>
</svg>''',

    "view-front.svg": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M7 4C7 4 9 7 12 7C15 7 17 4 17 4L21 8L18 10V20H6V10L3 8L7 4Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M9 7V10 M15 7V10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-opacity="0.5"/>
</svg>''',

    "view-back.svg": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M7 4C7 4 9 4.5 12 4.5C15 4.5 17 4 17 4L21 8L18 10V20H6V10L3 8L7 4Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''
}

for name, content in svgs.items():
    with open(os.path.join(target_dir, name), "w") as f:
        f.write(content)
