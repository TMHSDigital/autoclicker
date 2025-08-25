#!/usr/bin/env python3
"""
Create a simple icon for the autoclicker application
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    """Create a simple autoclicker icon"""
    # Create a 256x256 image
    size = (256, 256)
    image = Image.new('RGBA', size, (64, 128, 255, 255))  # Blue background
    draw = ImageDraw.Draw(image)

    # Draw a simple mouse cursor shape
    # Mouse pointer (triangle)
    pointer_points = [(128, 60), (140, 80), (128, 100), (160, 90)]
    draw.polygon(pointer_points, fill=(255, 255, 255, 255))

    # Mouse body (rectangle with rounded corners)
    draw.rectangle([80, 90, 180, 180], fill=(200, 200, 200, 255), outline=(100, 100, 100, 255), width=3)

    # Left mouse button
    draw.rectangle([90, 100, 130, 170], fill=(255, 255, 255, 255), outline=(100, 100, 100, 255), width=2)

    # Right mouse button
    draw.rectangle([130, 100, 170, 170], fill=(255, 255, 255, 255), outline=(100, 100, 100, 255), width=2)

    # Scroll wheel
    draw.rectangle([125, 125, 135, 145], fill=(150, 150, 150, 255), outline=(100, 100, 100, 255), width=1)

    # Add text "AC" in the center
    try:
        # Try to use a system font
        font = ImageFont.truetype("arial.ttf", 48)
    except:
        # Fall back to default font
        font = ImageFont.load_default()

    # Draw "AC" text
    draw.text((100, 200), "AC", fill=(255, 255, 255, 255), font=font)

    # Save as ICO file
    image.save('autoclicker.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])

    # Also save as PNG for reference
    image.save('autoclicker.png', format='PNG')

    print("Icon created successfully!")
    print("Files: autoclicker.ico, autoclicker.png")

if __name__ == "__main__":
    create_icon()
