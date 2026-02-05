import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

ASSET_DIR = "twocomms/dtf/static/dtf/assets/"
os.makedirs(ASSET_DIR, exist_ok=True)

COLORS = {
    "bg": (20, 20, 20),
    "accent": (255, 69, 0),
    "text": (220, 220, 220),
    "grid": (60, 60, 60)
}

def create_noise_texture(filename):
    size = (512, 512)
    img = Image.new("RGB", size, (30, 30, 30))
    pixels = img.load()
    for i in range(size[0]):
        for j in range(size[1]):
            r = random.randint(-15, 15)
            pixels[i, j] = (30 + r, 30 + r, 30 + r)
    img.save(os.path.join(ASSET_DIR, filename))
    print(f"Generated {filename}")

def create_placeholder_image(filename, text, size=(1200, 800), details=None):
    img = Image.new("RGB", size, COLORS["bg"])
    draw = ImageDraw.Draw(img)
    
    # Draw grid
    for x in range(0, size[0], 50):
        draw.line([(x, 0), (x, size[1])], fill=COLORS["grid"], width=1)
    for y in range(0, size[1], 50):
        draw.line([(0, y), (size[0], y)], fill=COLORS["grid"], width=1)
        
    # Draw border
    draw.rectangle([(10, 10), (size[0]-10, size[1]-10)], outline=COLORS["accent"], width=4)
    
    # Draw Text - Try to load font, fallback to default
    try:
        # Try to find a system font
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 30)
    except:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()
        
    # Centered Text
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    draw.text(((size[0]-text_width)/2, (size[1]-text_height)/2 - 40), text, fill=COLORS["accent"], font=font)
    
    if details:
        details_bbox = draw.textbbox((0,0), details, font=font_small)
        w = details_bbox[2] - details_bbox[0]
        draw.text(((size[0]-w)/2, (size[1])/2 + 40), details, fill=COLORS["text"], font=font_small)

    img.save(os.path.join(ASSET_DIR, filename))
    print(f"Generated {filename}")

def create_requirements_chart(filename):
    size = (1400, 600)
    img = Image.new("RGB", size, (10, 10, 10))
    draw = ImageDraw.Draw(img)
    
    # Split
    draw.rectangle([(0,0), (700, 600)], fill=(20, 40, 20)) # OK Zone
    draw.rectangle([(700,0), (1400, 600)], fill=(40, 20, 20)) # RISK Zone
    
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)
    except:
        font = ImageFont.load_default()
        
    draw.text((250, 260), "OK: VECTOR", fill=(100, 255, 100), font=font)
    draw.text((850, 260), "RISK: RASTER", fill=(255, 100, 100), font=font)
    
    img.save(os.path.join(ASSET_DIR, filename))
    print(f"Generated {filename}")

def create_template_preview(filename):
    size = (1200, 800)
    img = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # 60cm representation
    margin = 50
    draw.rectangle([(margin, margin), (1200-margin, 800-margin)], outline="black", width=2)
    draw.text((margin+10, margin+10), "60cm DTF Roll Template Preview", fill="black")
    
    # Draw some "gang sheet" boxes
    draw.rectangle([(100, 100), (300, 400)], fill=(200, 200, 200), outline="red")
    draw.rectangle([(320, 100), (520, 300)], fill=(200, 200, 200), outline="red")
    
    img.save(os.path.join(ASSET_DIR, filename))
    print(f"Generated {filename}")

def create_pdf_template(filename):
    c = canvas.Canvas(os.path.join(ASSET_DIR, filename), pagesize=(60*cm, 100*cm))
    c.setLineWidth(1)
    c.setStrokeColorRGB(1, 0, 0) # Red guide
    c.rect(1*cm, 1*cm, 58*cm, 98*cm)
    
    c.setFont("Helvetica", 40)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawString(20*cm, 95*cm, "DTF 60cm Template - Safe Area (Red Line)")
    c.save()
    print(f"Generated {filename}")

# --- Execution ---

# 1. Noise
create_noise_texture("noise-tiling-1.png")

# 2. Photos Placeholders (Batch)
for i in range(1, 13):
    create_placeholder_image(f"gallery-macro-{i:02d}.jpg", "GALLERY MACRO", details=f"Photo {i} Placeholder")

# 3. Lab Proof Placeholders
for i in range(1, 7):
    create_placeholder_image(f"lab-proof-{i:02d}.jpg", "LAB PROOF", details=f"QC Step {i}")

# 4. Requirements
create_requirements_chart("requirements-ok-risk.jpg")

# 5. Templates
create_template_preview("template-preview-60cm.jpg")
create_pdf_template("template-60cm.pdf")

# 6. Dummy/SVG renames for AI/FIG
svg_path = os.path.join(ASSET_DIR, "template-60cm.svg") # Already exists from previous step? If not, ignored.
# Assuming SVG exists from previous tool calls, if not we will skip or simple copy
# Actually, let's create a minimal SVG if it doesn't exist
if not os.path.exists(svg_path):
    with open(svg_path, "w") as f:
        f.write('<svg width="600" height="1000"><rect width="600" height="1000" fill="white"/><text x="10" y="50">Template</text></svg>')

import shutil
shutil.copy(svg_path, os.path.join(ASSET_DIR, "template-60cm.ai"))
shutil.copy(svg_path, os.path.join(ASSET_DIR, "template-60cm.fig"))
print("Generated AI/FIG templates")
