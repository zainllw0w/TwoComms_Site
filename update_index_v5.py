import sys
import re

with open('/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update Left Panel Color
# Find the sl-panel-light class and replace background.
# Previous: background: linear-gradient(135deg, rgba(255, 150, 80, 0.15), rgba(255, 209, 140, 0.05));
# New harmonious color: linear-gradient(135deg, #4A2011, #281006) which is lighter than central (#38160d to #1c0602) but dark enough for text
html = re.sub(
    r'\.sl-panel-light \{\s*background: linear-gradient\(135deg, rgba\(255, 150, 80, 0\.15\), rgba\(255, 209, 140, 0\.05\)\);',
    '.sl-panel-light {\n      background: linear-gradient(135deg, #5A2714, #2A1107);',
    html
)

# Also ensure border is slightly brighter so it pops
html = re.sub(
    r'border: 1px solid rgba\(255, 140, 66, 0\.3\);',
    'border: 1px solid rgba(255, 140, 66, 0.2);',
    html
)


# 2. Update SVG to Banknote Gift
new_svg = """<svg width="100" height="100" viewBox="0 0 100 100" fill="none" style="filter: drop-shadow(0 0 20px rgba(255,140,66,0.5));">
  
  <!-- Second Banknote (Behind the first) -->
  <g transform="translate(25, 22) rotate(-15)">
    <rect x="0" y="0" width="38" height="55" rx="3" fill="url(#noteGradDark)" stroke="#e66820" stroke-width="2"/>
    <rect x="3" y="3" width="32" height="49" rx="1" fill="none" stroke="rgba(255,209,140,0.2)" stroke-width="1"/>
    <text x="19" y="24" font-family="Inter, Arial, sans-serif" font-weight="900" font-size="12" fill="rgba(255,255,255,0.6)" text-anchor="middle">200</text>
  </g>

  <!-- The Main Banknote -->
  <g transform="translate(45, 12) rotate(12)">
    <!-- Base paper -->
    <rect x="0" y="0" width="40" height="55" rx="3" fill="url(#noteGrad)" stroke="#FFd18c" stroke-width="2"/>
    <!-- Inner border -->
    <rect x="4" y="4" width="32" height="47" rx="1" fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="1" stroke-dasharray="3 3"/>
    <!-- "200" text -->
    <text x="20" y="24" font-family="Inter, Arial, sans-serif" font-weight="900" font-size="14" fill="#fff" text-anchor="middle">200</text>
    <!-- Grivna symbol -->
    <text x="20" y="42" font-family="Inter, Arial, sans-serif" font-weight="900" font-size="18" fill="#fff" text-anchor="middle">₴</text>
  </g>

  <!-- Main Box -->
  <rect x="25" y="55" width="50" height="35" rx="4" fill="url(#boxBodyGrad)"/>
  
  <!-- Vertical Ribbon -->
  <rect x="42" y="55" width="16" height="35" fill="url(#ribbonGrad)"/>
  
  <!-- Lid -->
  <rect x="20" y="45" width="60" height="12" rx="3" fill="url(#boxLidGrad)"/>
  <!-- Lid Ribbon -->
  <rect x="42" y="45" width="16" height="12" fill="url(#ribbonGrad)"/>

  <!-- Minimalist Sparkles -->
  <path d="M12 40 L16 32 L20 40 L12 36 L20 36 Z" fill="#FFD18C"/>
  <path d="M85 30 L88 22 L91 30 L83 26 L93 26 Z" fill="#FFD18C"/>

  <defs>
    <!-- Banknote gradients -->
    <linearGradient id="noteGrad" x1="0" y1="0" x2="40" y2="55" gradientUnits="userSpaceOnUse">
      <stop stop-color="#ffb366" />
      <stop offset="1" stop-color="#f26e10" />
    </linearGradient>
    <linearGradient id="noteGradDark" x1="0" y1="0" x2="38" y2="55" gradientUnits="userSpaceOnUse">
      <stop stop-color="#b85f25" />
      <stop offset="1" stop-color="#993900" />
    </linearGradient>

    <!-- Box gradients -->
    <linearGradient id="boxBodyGrad" x1="25" y1="55" x2="75" y2="90" gradientUnits="userSpaceOnUse">
      <stop stop-color="#FF8C42" />
      <stop offset="1" stop-color="#b54810" />
    </linearGradient>
    <linearGradient id="boxLidGrad" x1="20" y1="45" x2="80" y2="57" gradientUnits="userSpaceOnUse">
      <stop stop-color="#ffa566" />
      <stop offset="1" stop-color="#d15a15" />
    </linearGradient>
    <linearGradient id="ribbonGrad" x1="42" y1="45" x2="58" y2="90" gradientUnits="userSpaceOnUse">
      <stop stop-color="#FFD18C" />
      <stop offset="1" stop-color="#e6922e" />
    </linearGradient>
  </defs>
</svg>"""

html = re.sub(r'<svg width="100" height="100" viewBox="0 0 100 100" fill="none" style="filter: drop-shadow\(0 0 20px rgba\(255,140,66,0\.5\)\);">.*?</svg>', new_svg, html, flags=re.DOTALL)

with open('/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("V5 applied.")
