
import os
import random
import colorsys
import math
from PIL import Image, ImageDraw, ImageFilter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

# Configuration
ASSET_DIR = "twocomms/dtf/static/dtf/assets"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_DIR = os.path.join(BASE_DIR, ASSET_DIR)

if not os.path.exists(TARGET_DIR):
    os.makedirs(TARGET_DIR, exist_ok=True)
    print(f"Created directory: {TARGET_DIR}")

def generate_ink_droplets():
    """Generates a seamless transparency layer with soft orange droplets."""
    width, height = 1400, 1400
    # Creates fully transparent image
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Molten Orange: #FF4500 -> (255, 69, 0)
    # We want it very transparent: alpha ~ 50-100
    
    droplets = 12
    for _ in range(droplets):
        # Random size 50 to 200px
        r = random.randint(30, 150)
        x = random.randint(0, width)
        y = random.randint(0, height)
        
        # Color with variation
        alpha = random.randint(40, 90)
        # Slight hue shift for realism
        hue = 0.04 + (random.random() * 0.02) # approx orange
        rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        color = (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255), alpha)
        
        # Draw ellipse
        shape = [(x, y), (x+r, y+r*0.8)] # slightly flattened
        draw.ellipse(shape, fill=color)
        
    # Heavy blur to make them "soft" and "liquid"
    img = img.filter(ImageFilter.GaussianBlur(radius=15))
    
    # Save
    path = os.path.join(TARGET_DIR, "ink-droplets-field.png")
    img.save(path, "PNG")
    print(f"Generated: {path}")

def generate_pdf_template():
    """Generates a technical PDF template for 60cm DTF."""
    filename = "template-60cm.pdf"
    path = os.path.join(TARGET_DIR, filename)
    
    # Dimensions: 60cm x 100cm (Gang Sheet)
    width_mm = 600
    height_mm = 1000
    
    c = canvas.Canvas(path, pagesize=(width_mm*mm, height_mm*mm))
    c.setAuthor("TwoComms DTF Lab")
    c.setTitle("60cm DTF Gang Sheet Template")
    
    # Draw Guides
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0, 1, 1) # Cyan guides
    
    # Safe Area (1cm margin)
    margin = 10 * mm
    c.rect(margin, margin, (width_mm*mm) - (2*margin), (height_mm*mm) - (2*margin))
    
    # Center Line
    c.setStrokeColorRGB(1, 0, 1) # Magenta center
    c.line(width_mm*mm / 2, 0, width_mm*mm / 2, height_mm*mm)
    
    # Text
    c.setFont("Helvetica", 12)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(15*mm, 15*mm, "Safe Area (10mm Margin)")
    c.drawString(15*mm, height_mm*mm - 20*mm, "DTF Gang Sheet 60cm - TwoComms Lab Proof")
    
    c.save()
    print(f"Generated: {path}")
    
    # Create dummy .ai (copy pdf)
    ai_path = os.path.join(TARGET_DIR, "template-60cm.ai")
    with open(path, 'rb') as s, open(ai_path, 'wb') as d:
        d.write(s.read())
    print(f"Generated: {ai_path} (from PDF)")

def generate_textures():
    """Generates procedural dark textures for gallery/lab."""
    
    def create_noise_texture(name, width=1920, height=1080):
        img = Image.new('RGB', (width, height), (15, 15, 15)) # Carbon black
        pixels = img.load()
        
        # Add simple noise
        for i in range(width):
            for j in range(height):
                if random.random() > 0.95:
                    v = random.randint(10, 30)
                    pixels[i, j] = (v, v, v)
        
        # Add subtle orange line occasionally
        draw = ImageDraw.Draw(img)
        if random.random() > 0.5:
             y = random.randint(0, height)
             draw.line([(0, y), (width, y)], fill=(50, 20, 0), width=1)

        path = os.path.join(TARGET_DIR, name)
        img.save(path, "JPEG", quality=90)
        print(f"Generated: {path}")

    # Gallery Macro 01-12
    for i in range(1, 13):
        format_name = f"gallery-macro-{i:02d}.jpg"
        create_noise_texture(format_name)
    
    # Lab Proof 01-06
    for i in range(1, 7):
        format_name = f"lab-proof-{i:02d}.jpg"
        create_noise_texture(format_name)

if __name__ == "__main__":
    try:
        generate_ink_droplets()
        generate_pdf_template()
        generate_textures()
        print("Success: All procedural assets generated.")
    except Exception as e:
        print(f"Error: {e}")
