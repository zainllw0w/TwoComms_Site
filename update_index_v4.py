import sys
import re

with open('/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update CSS
css_add = """
    .sl-panel-light {
      background: linear-gradient(135deg, rgba(255, 150, 80, 0.15), rgba(255, 209, 140, 0.05));
      border-radius: 20px;
      padding: 1rem;
      border: 1px solid rgba(255, 140, 66, 0.3);
      box-shadow: 0 8px 24px rgba(0,0,0,0.25);
    }
"""
html = html.replace('.survey-panel-dark {', css_add + '\n    .survey-panel-dark {')
html = re.sub(r'\.survey-container-v3 \{\s*display: grid;\s*gap: 1\.25rem;\s*margin: 1rem 0;\s*\}', 
              '.survey-container-v3 {\n      display: grid;\n      gap: 1rem;\n      margin: 1rem 0;\n    }', html)
html = re.sub(r'\.sl-header \{\s*display: flex;\s*align-items: center;\s*gap: 1rem;\s*margin-bottom: 1rem;\s*\}',
              '.sl-header {\n      display: flex;\n      align-items: center;\n      gap: 1rem;\n      margin-bottom: 0.75rem;\n    }', html)
html = re.sub(r'\.sl-desc \{\s*font-size: 0\.85rem;\s*color: rgba\(255, 255, 255, 0\.7\);\s*line-height: 1\.4;\s*margin-bottom: 1\.25rem;\s*\}',
              '.sl-desc {\n      font-size: 0.85rem;\n      color: rgba(255, 255, 255, 0.7);\n      line-height: 1.4;\n      margin-bottom: 0.75rem;\n    }', html)
html = re.sub(r'\.sl-tags \{\s*display: flex;\s*flex-direction: column;\s*gap: 0\.5rem;\s*\}',
              '.sl-tags {\n      display: flex;\n      flex-direction: column;\n      gap: 0.35rem;\n    }', html)
html = re.sub(r'\.sl-tag \{\s*background: rgba\(0, 0, 0, 0\.3\);\s*padding: 0\.5rem 0\.8rem;\s*',
              '.sl-tag {\n      background: rgba(0, 0, 0, 0.3);\n      padding: 0.4rem 0.6rem;\n      ', html)


# 2. Change Left Panel class
html = html.replace('<!-- Left Panel -->\n        <div class="survey-panel-dark">', '<!-- Left Panel -->\n        <div class="sl-panel-light">')

# 3. Replace SVG Gift Basket
new_svg = """<svg width="100" height="100" viewBox="0 0 100 100" fill="none" style="filter: drop-shadow(0 0 20px rgba(255,140,66,0.5));">
                <!-- Coin left back -->
                <circle cx="20" cy="75" r="10" fill="#FFD18C" stroke="#FF8C42" stroke-width="2"/>
                <circle cx="20" cy="75" r="6" fill="none" stroke="#FF8C42" stroke-width="1"/>

                <!-- Main Box -->
                <rect x="25" y="45" width="50" height="40" rx="4" fill="url(#boxBodyGrad)"/>
                
                <!-- Vertical Ribbon -->
                <rect x="42" y="45" width="16" height="40" fill="url(#ribbonGrad)"/>
                
                <!-- Lid -->
                <rect x="20" y="32" width="60" height="15" rx="3" fill="url(#boxLidGrad)"/>
                <!-- Lid Ribbon -->
                <rect x="42" y="32" width="16" height="15" fill="url(#ribbonGrad)"/>

                <!-- Bow Loops -->
                <path d="M50 32 C 40 10, 25 20, 42 32 Z" fill="url(#bowGrad)"/>
                <path d="M50 32 C 60 10, 75 20, 58 32 Z" fill="url(#bowGrad)"/>

                <!-- Stack of coins on right -->
                <ellipse cx="85" cy="78" rx="14" ry="6" fill="#FFD18C" stroke="#FF8C42" stroke-width="1.5"/>
                <rect x="71" y="74" width="28" height="4" fill="#FFD18C"/>
                <ellipse cx="85" cy="74" rx="14" ry="6" fill="#FFD18C" stroke="#FF8C42" stroke-width="1.5"/>
                
                <rect x="71" y="68" width="28" height="6" fill="#FFD18C"/>
                <ellipse cx="85" cy="68" rx="14" ry="6" fill="#FFD18C" stroke="#FF8C42" stroke-width="1.5"/>

                <circle cx="85" cy="55" r="14" fill="#FFD18C" stroke="#FF8C42" stroke-width="2"/>
                <circle cx="85" cy="55" r="10" fill="none" stroke="#FF8C42" stroke-width="1"/>
                <!-- $ sign -->
                <text x="85" y="61" font-family="Arial, sans-serif" font-weight="900" font-size="16" fill="#FF8C42" text-anchor="middle">$</text>

                <defs>
                  <linearGradient id="boxBodyGrad" x1="25" y1="45" x2="75" y2="85" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#FFD18C" />
                    <stop offset="1" stop-color="#FF8C42" />
                  </linearGradient>
                  <linearGradient id="boxLidGrad" x1="20" y1="32" x2="80" y2="47" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#ffedcc" />
                    <stop offset="1" stop-color="#ffb873" />
                  </linearGradient>
                  <linearGradient id="ribbonGrad" x1="42" y1="32" x2="58" y2="85" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#fff5e6" />
                    <stop offset="1" stop-color="#ffd699" />
                  </linearGradient>
                  <linearGradient id="bowGrad" x1="25" y1="10" x2="75" y2="32" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#fff5e6" />
                    <stop offset="1" stop-color="#ffc97f" />
                  </linearGradient>
                </defs>
              </svg>"""

html = re.sub(r'<svg width="90" height="90" viewBox="0 0 24 24" fill="none" style="filter: drop-shadow\(0 0 16px rgba\(255,140,66,0\.3\)\);">.*?</svg>', new_svg, html, flags=re.DOTALL)

with open('/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("V4 CSS/HTML applied successfully.")
