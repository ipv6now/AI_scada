"""
Create alignment and distribute tool icons for HMI Designer
"""
from PIL import Image, ImageDraw
import os

def create_icon(filename, draw_func, size=(24, 24), bg_color=(240, 240, 240), fg_color=(80, 80, 80)):
    """Create an icon image"""
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw background
    draw.rectangle([0, 0, size[0]-1, size[1]-1], fill=bg_color, outline=(200, 200, 200), width=1)
    
    # Call custom draw function
    draw_func(draw, size, fg_color)
    
    # Save
    img.save(filename)
    print(f"Created: {filename}")

# Draw functions for each icon
def draw_align_left(draw, size, color):
    """Left align icon: lines aligned to left"""
    x, y = 4, 4
    draw.rectangle([x, y, x+3, y+16], fill=color)  # Left bar
    draw.rectangle([x+5, y+2, x+14, y+5], fill=color)  # Top line
    draw.rectangle([x+5, y+7, x+12, y+10], fill=color)  # Middle line
    draw.rectangle([x+5, y+12, x+16, y+15], fill=color)  # Bottom line

def draw_align_center(draw, size, color):
    """Center align icon: lines centered"""
    cx = size[0] // 2
    y = 4
    draw.rectangle([cx-1, y, cx+1, y+16], fill=color)  # Center bar
    draw.rectangle([cx-6, y+2, cx+5, y+5], fill=color)  # Top line
    draw.rectangle([cx-5, y+7, cx+4, y+10], fill=color)  # Middle line
    draw.rectangle([cx-7, y+12, cx+6, y+15], fill=color)  # Bottom line

def draw_align_right(draw, size, color):
    """Right align icon: lines aligned to right"""
    x, y = size[0] - 5, 4
    draw.rectangle([x-2, y, x+1, y+16], fill=color)  # Right bar
    draw.rectangle([x-13, y+2, x-4, y+5], fill=color)  # Top line
    draw.rectangle([x-11, y+7, x-4, y+10], fill=color)  # Middle line
    draw.rectangle([x-15, y+12, x-4, y+15], fill=color)  # Bottom line

def draw_align_top(draw, size, color):
    """Top align icon: lines aligned to top"""
    x, y = 4, 4
    draw.rectangle([x, y, x+16, y+3], fill=color)  # Top bar
    draw.rectangle([x+2, y+5, x+5, y+14], fill=color)  # Left line
    draw.rectangle([x+7, y+5, x+10, y+12], fill=color)  # Middle line
    draw.rectangle([x+12, y+5, x+15, y+16], fill=color)  # Right line

def draw_align_middle(draw, size, color):
    """Middle align icon: lines centered vertically"""
    cx, cy = size[0] // 2, size[1] // 2
    draw.rectangle([2, cy-1, 22, cy+1], fill=color)  # Middle bar
    draw.rectangle([cx-6, cy-6, cx-3, cy+5], fill=color)  # Left line
    draw.rectangle([cx-1, cy-5, cx+2, cy+4], fill=color)  # Middle line
    draw.rectangle([cx+4, cy-7, cx+7, cy+6], fill=color)  # Right line

def draw_align_bottom(draw, size, color):
    """Bottom align icon: lines aligned to bottom"""
    x, y = 4, size[1] - 5
    draw.rectangle([x, y-2, x+16, y+1], fill=color)  # Bottom bar
    draw.rectangle([x+2, y-13, x+5, y-4], fill=color)  # Left line
    draw.rectangle([x+7, y-11, x+10, y-4], fill=color)  # Middle line
    draw.rectangle([x+12, y-15, x+15, y-4], fill=color)  # Right line

def draw_distribute_h(draw, size, color):
    """Horizontal distribute icon"""
    # Three vertical bars with equal spacing
    draw.rectangle([3, 4, 5, 20], fill=color)   # Left bar
    draw.rectangle([11, 4, 13, 20], fill=color) # Middle bar
    draw.rectangle([19, 4, 21, 20], fill=color) # Right bar
    # Small rectangles between bars
    draw.rectangle([6, 10, 10, 14], fill=color) # Between left and middle
    draw.rectangle([14, 10, 18, 14], fill=color) # Between middle and right

def draw_distribute_v(draw, size, color):
    """Vertical distribute icon"""
    # Three horizontal bars with equal spacing
    draw.rectangle([4, 3, 20, 5], fill=color)   # Top bar
    draw.rectangle([4, 11, 20, 13], fill=color) # Middle bar
    draw.rectangle([4, 19, 20, 21], fill=color) # Bottom bar
    # Small rectangles between bars
    draw.rectangle([10, 6, 14, 10], fill=color) # Between top and middle
    draw.rectangle([10, 14, 14, 18], fill=color) # Between middle and bottom

# Create all icons
if __name__ == "__main__":
    icon_dir = os.path.dirname(os.path.abspath(__file__))
    
    icons = [
        ("align_left.png", draw_align_left),
        ("align_center.png", draw_align_center),
        ("align_right.png", draw_align_right),
        ("align_top.png", draw_align_top),
        ("align_middle.png", draw_align_middle),
        ("align_bottom.png", draw_align_bottom),
        ("distribute_h.png", draw_distribute_h),
        ("distribute_v.png", draw_distribute_v),
    ]
    
    for filename, draw_func in icons:
        filepath = os.path.join(icon_dir, filename)
        create_icon(filepath, draw_func)
    
    print("\nAll icons created successfully!")
