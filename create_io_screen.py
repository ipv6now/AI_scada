"""
Create IO Monitor Screen for myproject.scada
Adds I0.0-I5.7 and Q0.0-Q5.7 indicators
"""
import json
import os

# Load existing project
project_path = 'myproject.scada'
with open(project_path, 'r', encoding='utf-8') as f:
    project = json.load(f)

# Generate IO tags
io_tags = []

# Input tags I0.0 - I5.7
for byte in range(6):  # 0-5
    for bit in range(8):  # 0-7
        tag_name = f"I{byte}.{bit}"
        address = f"I{byte}.{bit}"
        io_tags.append({
            "name": tag_name,
            "tag_type": "PLC",
            "data_type": "BOOL",
            "address": address,
            "description": f"输入点 {tag_name}",
            "plc_connection": "123",
            "value": False,
            "timestamp": "2026-02-12T00:00:00",
            "quality": "GOOD"
        })

# Output tags Q0.0 - Q5.7
for byte in range(6):  # 0-5
    for bit in range(8):  # 0-7
        tag_name = f"Q{byte}.{bit}"
        address = f"Q{byte}.{bit}"
        io_tags.append({
            "name": tag_name,
            "tag_type": "PLC",
            "data_type": "BOOL",
            "address": address,
            "description": f"输出点 {tag_name}",
            "plc_connection": "123",
            "value": False,
            "timestamp": "2026-02-12T00:00:00",
            "quality": "GOOD"
        })

# Add IO tags to project
print(f"Adding {len(io_tags)} IO tags...")
project['tags'].extend(io_tags)

# Create IO monitor screen objects
screen_objects = []

# Title
screen_objects.append({
    "obj_type": "rectangle",
    "x": 0,
    "y": 0,
    "width": 1920,
    "height": 80,
    "properties": {
        "color": "#000000",
        "line_width": 0,
        "filled": True,
        "fill_color": "#aaffff"
    },
    "variables": []
})

screen_objects.append({
    "obj_type": "label",
    "x": 760,
    "y": 6,
    "width": 400,
    "height": 70,
    "properties": {
        "text": "IO点状态监控",
        "color": "#000000",
        "background_color": "",
        "font_size": 40,
        "font_bold": False,
        "font_italic": False,
        "font_underline": False,
        "text_h_align": "left",
        "text_v_align": "middle",
        "border": False,
        "display_format": "{}",
        "unit": "",
        "precision": 2,
        "font_family": "Microsoft YaHei",
        "text_color": "#000000"
    },
    "variables": []
})

# Input section title
screen_objects.append({
    "obj_type": "label",
    "x": 50,
    "y": 100,
    "width": 200,
    "height": 40,
    "properties": {
        "text": "输入点 (I0.0 - I5.7)",
        "color": "#000000",
        "background_color": "",
        "font_size": 20,
        "font_bold": True,
        "font_italic": False,
        "font_underline": False,
        "text_h_align": "left",
        "text_v_align": "middle",
        "border": False,
        "display_format": "{}",
        "unit": "",
        "precision": 2,
        "font_family": "Microsoft YaHei",
        "text_color": "#0000FF"
    },
    "variables": []
})

# Create input indicators (6 rows x 8 columns)
start_x = 50
start_y = 150
spacing_x = 120
spacing_y = 80

for byte in range(6):  # I0 - I5
    for bit in range(8):  # .0 - .7
        x = start_x + bit * spacing_x
        y = start_y + byte * spacing_y
        
        # Label
        screen_objects.append({
            "obj_type": "label",
            "x": x,
            "y": y,
            "width": 60,
            "height": 20,
            "properties": {
                "text": f"I{byte}.{bit}",
                "color": "#000000",
                "background_color": "",
                "font_size": 12,
                "font_bold": False,
                "font_italic": False,
                "font_underline": False,
                "text_h_align": "center",
                "text_v_align": "middle",
                "border": False,
                "display_format": "{}",
                "unit": "",
                "precision": 2,
                "font_family": "Microsoft YaHei",
                "text_color": "#000000"
            },
            "variables": []
        })
        
        # Indicator light
        screen_objects.append({
            "obj_type": "light",
            "x": x + 15,
            "y": y + 25,
            "width": 30,
            "height": 30,
            "properties": {
                "state": False,
                "on_color": "#00FF00",
                "off_color": "#808080",
                "text": "",
                "text_color": "#000000",
                "font_size": 10,
                "font_bold": False,
                "font_italic": False,
                "font_underline": False,
                "text_h_align": "center",
                "text_v_align": "middle",
                "shape": "circle",
                "on_image": "",
                "off_image": "",
                "use_image": False,
                "border": True,
                "border_color": "#000000",
                "border_width": 1
            },
            "variables": [
                {
                    "variable_name": f"I{byte}.{bit}",
                    "variable_type": "read",
                    "address": f"I{byte}.{bit}",
                    "description": f"输入点 I{byte}.{bit}"
                }
            ]
        })

# Output section title
output_start_y = start_y + 6 * spacing_y + 50
screen_objects.append({
    "obj_type": "label",
    "x": 50,
    "y": output_start_y,
    "width": 200,
    "height": 40,
    "properties": {
        "text": "输出点 (Q0.0 - Q5.7)",
        "color": "#000000",
        "background_color": "",
        "font_size": 20,
        "font_bold": True,
        "font_italic": False,
        "font_underline": False,
        "text_h_align": "left",
        "text_v_align": "middle",
        "border": False,
        "display_format": "{}",
        "unit": "",
        "precision": 2,
        "font_family": "Microsoft YaHei",
        "text_color": "#FF0000"
    },
    "variables": []
})

# Create output indicators
output_start_y += 50
for byte in range(6):  # Q0 - Q5
    for bit in range(8):  # .0 - .7
        x = start_x + bit * spacing_x
        y = output_start_y + byte * spacing_y
        
        # Label
        screen_objects.append({
            "obj_type": "label",
            "x": x,
            "y": y,
            "width": 60,
            "height": 20,
            "properties": {
                "text": f"Q{byte}.{bit}",
                "color": "#000000",
                "background_color": "",
                "font_size": 12,
                "font_bold": False,
                "font_italic": False,
                "font_underline": False,
                "text_h_align": "center",
                "text_v_align": "middle",
                "border": False,
                "display_format": "{}",
                "unit": "",
                "precision": 2,
                "font_family": "Microsoft YaHei",
                "text_color": "#000000"
            },
            "variables": []
        })
        
        # Indicator light
        screen_objects.append({
            "obj_type": "light",
            "x": x + 15,
            "y": y + 25,
            "width": 30,
            "height": 30,
            "properties": {
                "state": False,
                "on_color": "#FF0000",
                "off_color": "#808080",
                "text": "",
                "text_color": "#000000",
                "font_size": 10,
                "font_bold": False,
                "font_italic": False,
                "font_underline": False,
                "text_h_align": "center",
                "text_v_align": "middle",
                "shape": "circle",
                "on_image": "",
                "off_image": "",
                "use_image": False,
                "border": True,
                "border_color": "#000000",
                "border_width": 1
            },
            "variables": [
                {
                    "variable_name": f"Q{byte}.{bit}",
                    "variable_type": "read",
                    "address": f"Q{byte}.{bit}",
                    "description": f"输出点 Q{byte}.{bit}"
                }
            ]
        })

# Create new screen
new_screen = {
    "name": "IO监控画面",
    "number": 2,
    "is_main": False,
    "resolution": {
        "width": 1920,
        "height": 1080
    },
    "background_color": "#f0f0f0",
    "objects": screen_objects
}

# Add screen to project
print("Adding IO monitor screen...")
project['hmi_screens'].append(new_screen)

# Save project
print("Saving project...")
with open(project_path, 'w', encoding='utf-8') as f:
    json.dump(project, f, indent=2, ensure_ascii=False)

print(f"\n✓ IO monitor screen created successfully!")
print(f"  - Added {len(io_tags)} IO tags")
print(f"  - Created 'IO监控画面' with {len(screen_objects)} objects")
print(f"  - Input indicators: I0.0-I5.7 (green)")
print(f"  - Output indicators: Q0.0-Q5.7 (red)")
