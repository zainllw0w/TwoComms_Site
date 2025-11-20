
from PIL import Image
from pathlib import Path
import os

def optimize_placeholder():
    base_dir = Path('/Users/zainllw0w/PycharmProjects/TwoComms/twocomms/twocomms_django_theme/static/img')
    placeholder_path = base_dir / 'placeholder.jpg'
    
    if not placeholder_path.exists():
        print(f"Placeholder not found at {placeholder_path}")
        return

    # Create optimized directory if it doesn't exist (though template tag looks in same dir or optimized subdir)
    # responsive_images.py checks:
    # 1. base_dir / "optimized" / f"{base_name}.webp"
    # 2. OR just static path if passed directly?
    # Let's check responsive_images.py again.
    # It checks `optimized_dir = base_dir / "optimized"`
    
    optimized_dir = base_dir / 'optimized'
    optimized_dir.mkdir(exist_ok=True)
    
    print(f"Optimizing {placeholder_path}...")
    
    with Image.open(placeholder_path) as img:
        # WebP
        webp_path = optimized_dir / 'placeholder.webp'
        img.save(webp_path, format='WEBP', quality=85, method=6)
        print(f"Saved {webp_path}")
        
        # AVIF
        avif_path = optimized_dir / 'placeholder.avif'
        try:
            img.save(avif_path, format='AVIF', quality=85)
            print(f"Saved {avif_path}")
        except Exception as e:
            print(f"Could not save AVIF: {e}")

if __name__ == '__main__':
    optimize_placeholder()
