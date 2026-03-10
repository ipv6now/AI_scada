"""
HMI Designer - Visual design tool for HMI screens
Industrial SCADA System - Human Machine Interface Designer

Features:
- Visual design of HMI screens with drag-and-drop interface
- Support for 20+ control types (buttons, gauges, charts, inputs, etc.)
- Variable binding to PLC tags
- Multi-screen management
- Undo/Redo functionality
- Copy/Paste/Duplicate controls
- Alignment and distribution tools
- Layer management
- Grid snapping
- Property editing with real-time preview
"""
import json
import copy
import math
import os
from typing import List, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsEllipseItem,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsPolygonItem,
    QGraphicsItem, QComboBox, QSpinBox, QColorDialog, QFontDialog,
    QCheckBox, QFrame, QLineEdit, QGroupBox, QHeaderView, QTableWidget,
    QTableWidgetItem, QTextEdit, QFileDialog, QMessageBox, QWidget,
    QTabWidget, QListWidget, QMenuBar, QMenu, QAction, QInputDialog,
    QGraphicsPathItem, QTreeWidget, QTreeWidgetItem, QSplitter, QScrollArea,
    QGraphicsPixmapItem, QApplication, QDialogButtonBox, QFormLayout, QRadioButton
)
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt5.QtGui import (
    QPen, QBrush, QColor, QFont, QPainter, QPainterPath,
    QKeySequence, QPolygonF, QCursor, QPixmap
)
from PyQt5.QtCore import QMimeData

from scada_app.hmi.variable_selector import SmartVariableComboBox


class VariableBinding:
    """Variable binding for HMI objects"""
    def __init__(self, variable_name='', variable_type='read', address='', description='', bit_offset=None):
        self.variable_name = variable_name
        self.variable_type = variable_type
        self.address = address
        self.description = description
        self.bit_offset = bit_offset  # 位偏移 (0-15 for 16-bit, 0-31 for 32-bit)


class HMIScreen:
    """HMI Screen class"""
    def __init__(self, name='Untitled', number=0, resolution=None):
        self.name = name
        self.number = number
        self.resolution = resolution or {'width': 1000, 'height': 600}
        self.is_main = False
        self.objects = []
        self.background_color = '#FFFFFF'  # Default white background


class HMIObject:
    """Base class for HMI objects"""
    _z_value_counter = 0  # Class-level counter for unique z-values
    
    def __init__(self, obj_type, x, y, width, height):
        self.obj_type = obj_type
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.properties = {}
        self.variables = []
        # Assign a unique base z-value for this object instance
        HMIObject._z_value_counter += 10
        self.z_value = HMIObject._z_value_counter
        # Visibility control properties
        self.visibility = {
            'control_variable': '',
            'condition': 'equal',
            'compare_value': '1',
            'show_when_true': True
        }
    
    def add_variable_binding(self, variable_name, variable_type, address, description='', bit_offset=None):
        var = VariableBinding(variable_name, variable_type, address, description, bit_offset)
        self.variables.append(var)
    
    def remove_variable_binding(self, index):
        if 0 <= index < len(self.variables):
            del self.variables[index]
    
    def bring_to_front(self):
        """Bring this object to the front by increasing its z-value"""
        HMIObject._z_value_counter += 10
        self.z_value = HMIObject._z_value_counter
    
    def send_to_back(self):
        """Send this object to the back - not implemented as it would require reordering all objects"""
        pass
    
    def check_visibility(self, data_manager=None):
        """Check if object should be visible based on control variable
        
        逻辑：
        - 如果没有组态控制变量， → 始终显示
        - 如果组态了控制变量和条件
        → 根据条件判断，显示或隐藏
        """
        var_name = self.visibility.get('control_variable', '')
        
        if not var_name:
            return True
        
        if not data_manager:
            return True
        
        var_value = None
        if hasattr(data_manager, 'get_tag_value'):
            var_value = data_manager.get_tag_value(var_name)
        elif hasattr(data_manager, 'tags'):
            tag = data_manager.tags.get(var_name)
            if tag:
                var_value = tag.value
        
        if var_value is None:
            return True
        
        # Apply bit offset if specified
        bit_offset = self.visibility.get('bit_offset', None)
        if bit_offset is not None and isinstance(var_value, (int, float)):
            bit_pos = int(bit_offset)
            if 0 <= bit_pos < 32:
                var_value = bool((int(var_value) >> bit_pos) & 1)
        
        condition = self.visibility.get('condition', 'equal')
        compare_value = self.visibility.get('compare_value', '1')
        
        if 'show_when_true' in self.visibility:
            show_when_true = self.visibility.get('show_when_true', True)
        elif 'hide_when_false' in self.visibility:
            show_when_true = not self.visibility.get('hide_when_false', True)
        else:
            show_when_true = True
        
        try:
            if isinstance(var_value, bool):
                if isinstance(compare_value, str):
                    compare_lower = compare_value.lower().strip()
                    if compare_lower in ('true', '1', 'yes', 'on'):
                        compare_val = True
                    elif compare_lower in ('false', '0', 'no', 'off', ''):
                        compare_val = False
                    else:
                        compare_val = bool(int(compare_value)) if compare_value else False
                else:
                    compare_val = bool(compare_value)
            elif isinstance(var_value, (int, float)):
                compare_val = float(compare_value) if compare_value else 0
            else:
                compare_val = str(compare_value)
        except Exception:
            compare_val = compare_value
        
        result = False
        if condition == 'equal':
            result = var_value == compare_val
        elif condition == 'not_equal':
            result = var_value != compare_val
        elif condition == 'greater':
            result = var_value > compare_val
        elif condition == 'less':
            result = var_value < compare_val
        elif condition == 'greater_equal':
            result = var_value >= compare_val
        elif condition == 'less_equal':
            result = var_value <= compare_val
        elif condition == 'not_zero':
            result = bool(var_value)
        elif condition == 'is_zero':
            result = not bool(var_value)
        
        final_result = result if show_when_true else not result
        
        return final_result


class HMIClock(HMIObject):
    def __init__(self, x=0, y=0, width=100, height=100):
        super().__init__('clock', x, y, width, height)
        self.properties = {
            'show_date': True,
            'show_time': True,
            'show_seconds': True,
            'date_format': 'YYYY-MM-DD',
            'time_format': 'HH:MM:SS',
            'font_family': 'Microsoft YaHei',
            'font_size': 12,
            'font_bold': False,
            'font_italic': False,
            'font_underline': False,
            'text_color': '#000000',
            'background_color': '#FFFFFF',
            'border_color': '#000000',
            'border_width': 1,
            'show_border': True,
            'clock_style': 'digital'  # digital or analog
        }
    
    def draw(self, scene):
        # Draw background
        bg = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        bg.setBrush(QBrush(QColor(self.properties.get('background_color', '#FFFFFF'))))
        
        if self.properties.get('show_border', True):
            border_width = self.properties.get('border_width', 1)
            bg.setPen(QPen(QColor(self.properties.get('border_color', '#000000')), border_width))
        else:
            bg.setPen(QPen(Qt.NoPen))
        
        bg.setZValue(self.z_value)
        scene.addItem(bg)
        
        # Draw clock based on style
        clock_style = self.properties.get('clock_style', 'digital')
        
        if clock_style == 'analog':
            # Draw analog clock face
            center_x = self.x + self.width / 2
            center_y = self.y + self.height / 2
            radius = min(self.width, self.height) / 2 - 5
            
            # Draw clock circle
            clock_face = QGraphicsEllipseItem(center_x - radius, center_y - radius, radius * 2, radius * 2)
            clock_face.setPen(QPen(Qt.black, 2))
            clock_face.setBrush(QBrush(Qt.white))
            clock_face.setZValue(self.z_value + 1)
            scene.addItem(clock_face)
            
            # Draw hour markers
            for i in range(12):
                angle = math.radians(i * 30)
                start_x = center_x + math.cos(angle) * (radius - 10)
                start_y = center_y + math.sin(angle) * (radius - 10)
                end_x = center_x + math.cos(angle) * radius
                end_y = center_y + math.sin(angle) * radius
                marker = QGraphicsLineItem(start_x, start_y, end_x, end_y)
                marker.setPen(QPen(Qt.black, 2))
                marker.setZValue(self.z_value + 2)
                scene.addItem(marker)
            
            # Draw clock hands
            import datetime
            now = datetime.datetime.now()
            hour = now.hour % 12
            minute = now.minute
            second = now.second
            
            # Draw hour hand
            hour_angle = math.radians((hour * 30) + (minute * 0.5))
            hour_hand = QGraphicsLineItem(center_x, center_y, 
                                        center_x + math.cos(hour_angle) * (radius - 30),
                                        center_y + math.sin(hour_angle) * (radius - 30))
            hour_hand.setPen(QPen(Qt.black, 4))
            hour_hand.setZValue(self.z_value + 3)
            scene.addItem(hour_hand)
            
            # Draw minute hand
            minute_angle = math.radians(minute * 6)
            minute_hand = QGraphicsLineItem(center_x, center_y, 
                                        center_x + math.cos(minute_angle) * (radius - 20),
                                        center_y + math.sin(minute_angle) * (radius - 20))
            minute_hand.setPen(QPen(Qt.black, 2))
            minute_hand.setZValue(self.z_value + 3)
            scene.addItem(minute_hand)
            
            # Draw second hand if enabled
            if self.properties.get('show_seconds', True):
                second_angle = math.radians(second * 6)
                second_hand = QGraphicsLineItem(center_x, center_y, 
                                            center_x + math.cos(second_angle) * (radius - 15),
                                            center_y + math.sin(second_angle) * (radius - 15))
                second_hand.setPen(QPen(Qt.red, 1))
                second_hand.setZValue(self.z_value + 3)
                scene.addItem(second_hand)
            
            # Draw center dot
            center_dot = QGraphicsEllipseItem(center_x - 3, center_y - 3, 6, 6)
            center_dot.setBrush(QBrush(Qt.black))
            center_dot.setPen(QPen(Qt.black))
            center_dot.setZValue(self.z_value + 4)
            scene.addItem(center_dot)
        else:
            # Digital clock
            import datetime
            now = datetime.datetime.now()
            
            font = QFont()
            font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
            font.setPointSize(self.properties.get('font_size', 12))
            font.setBold(self.properties.get('font_bold', False))
            font.setItalic(self.properties.get('font_italic', False))
            font.setUnderline(self.properties.get('font_underline', False))
            
            # Format date and time based on properties
            display_text = ""
            
            if self.properties.get('show_date', True):
                date_format = self.properties.get('date_format', 'YYYY-MM-DD')
                formatted_date = now.strftime(date_format.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d'))
                display_text += formatted_date + "\n"
            
            if self.properties.get('show_time', True):
                time_format = self.properties.get('time_format', 'HH:MM:SS')
                if not self.properties.get('show_seconds', True):
                    time_format = time_format.replace(':SS', '')
                formatted_time = now.strftime(time_format.replace('HH', '%H').replace('MM', '%M').replace('SS', '%S'))
                display_text += formatted_time
            
            text_item = QGraphicsTextItem(display_text.strip() if display_text else '12:00')
            text_item.setFont(font)
            text_item.setDefaultTextColor(QColor(self.properties.get('text_color', '#000000')))
            
            # Position text
            text_rect = text_item.boundingRect()
            text_x = self.x + (self.width - text_rect.width()) / 2
            text_y = self.y + (self.height - text_rect.height()) / 2
            text_item.setPos(text_x, text_y)
            text_item.setZValue(self.z_value + 1)
            scene.addItem(text_item)


class HMIButton(HMIObject):
    def __init__(self, x=0, y=0, width=80, height=40, text='Button'):
        super().__init__('button', x, y, width, height)
        self.properties = {
            'text': text,
            'color': '#4CAF50',
            'on_color': '#4CAF50',
            'off_color': '#CCCCCC',
            'font_size': 10,
            'font_bold': False,
            'font_italic': False,
            'font_underline': False,
            'text_h_align': 'center',
            'text_v_align': 'middle',
            'action_type': 'custom',
            'variable_operation': '置位',
            'set_value': 1,
            'reset_value': 0,
            'target_screen': '',
            'target_screen_number': 0
        }
    
    def draw(self, scene):
        rect = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        rect.setBrush(QBrush(QColor(self.properties.get('color', '#4CAF50'))))
        rect.setPen(QPen(Qt.black))
        rect.setZValue(self.z_value)
        scene.addItem(rect)
        
        text_content = self.properties.get('text', 'Button')
        font = QFont()
        font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(self.properties.get('font_size', 10))
        font.setBold(self.properties.get('font_bold', False))
        font.setItalic(self.properties.get('font_italic', False))
        font.setUnderline(self.properties.get('font_underline', False))
        
        # Create text item first to get actual bounding rect
        text = QGraphicsTextItem(text_content)
        text.setFont(font)
        text.setDefaultTextColor(QColor(self.properties.get('text_color', '#000000')))
        text.setZValue(self.z_value + 1)
        
        # Get actual text dimensions from bounding rect
        text_rect = text.boundingRect()
        text_width = text_rect.width()
        text_height = text_rect.height()
        
        h_align = self.properties.get('text_h_align', 'center')
        v_align = self.properties.get('text_v_align', 'middle')
        
        # Calculate center of button
        center_x = self.x + self.width / 2
        center_y = self.y + self.height / 2
        
        # Horizontal alignment - center text around the calculated point
        if h_align == 'left':
            text_x = self.x + 3
        elif h_align == 'right':
            text_x = self.x + self.width - text_width - 3
        else:  # center
            text_x = center_x - text_width / 2
        
        # Vertical alignment - center text around the calculated point
        if v_align == 'top':
            text_y = self.y + 3
        elif v_align == 'bottom':
            text_y = self.y + self.height - text_height - 3
        else:  # middle
            text_y = center_y - text_height / 2
        
        text.setPos(text_x, text_y)
        scene.addItem(text)


class HMILabel(HMIObject):
    def __init__(self, x=0, y=0, width=100, height=30, text='Label'):
        super().__init__('label', x, y, width, height)
        self.properties = {
            'text': text,
            'color': '#000000',
            'background_color': '',  # Empty means transparent
            'font_size': 10,
            'font_bold': False,
            'font_italic': False,
            'font_underline': False,
            'text_h_align': 'left',
            'text_v_align': 'middle',
            'border': False,
            'display_format': '{}',
            'unit': '',
            'precision': 2
        }
    
    def draw(self, scene):
        # Draw background if color is specified
        bg_color = self.properties.get('background_color', '')
        if bg_color:
            bg_rect = QGraphicsRectItem(self.x, self.y, self.width, self.height)
            bg_rect.setBrush(QBrush(QColor(bg_color)))
            if self.properties.get('border', False):
                bg_rect.setPen(QPen(Qt.black))
            else:
                bg_rect.setPen(QPen(Qt.NoPen))
            bg_rect.setZValue(self.z_value)
            scene.addItem(bg_rect)
        elif self.properties.get('border', False):
            # Only draw border if no background
            rect = QGraphicsRectItem(self.x, self.y, self.width, self.height)
            rect.setPen(QPen(Qt.black))
            rect.setZValue(self.z_value)
            scene.addItem(rect)
        
        # Get text content and append unit if exists
        text_content = self.properties.get('text', 'Label')
        unit = self.properties.get('unit', '')
        if unit:
            text_content = f"{text_content}{unit}"
        
        font = QFont()
        font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(self.properties.get('font_size', 10))
        font.setBold(self.properties.get('font_bold', False))
        font.setItalic(self.properties.get('font_italic', False))
        font.setUnderline(self.properties.get('font_underline', False))
        
        # Create text item first to get actual bounding rect
        text = QGraphicsTextItem(text_content)
        text.setFont(font)
        text.setDefaultTextColor(QColor(self.properties.get('text_color', '#000000')))
        text.setZValue(self.z_value + 1)
        
        # Get actual text dimensions from bounding rect
        text_rect = text.boundingRect()
        text_width = text_rect.width()
        text_height = text_rect.height()
        
        h_align = self.properties.get('text_h_align', 'left')
        v_align = self.properties.get('text_v_align', 'middle')
        
        # Calculate center of label
        center_x = self.x + self.width / 2
        center_y = self.y + self.height / 2
        
        # Horizontal alignment - center text around the calculated point
        if h_align == 'left':
            text_x = self.x + 3
        elif h_align == 'right':
            text_x = self.x + self.width - text_width - 3
        else:  # center
            text_x = center_x - text_width / 2
        
        # Vertical alignment - center text around the calculated point
        if v_align == 'top':
            text_y = self.y + 3
        elif v_align == 'bottom':
            text_y = self.y + self.height - text_height - 3
        else:  # middle
            text_y = center_y - text_height / 2
        
        text.setPos(text_x, text_y)
        scene.addItem(text)


class HMIGauge(HMIObject):
    def __init__(self, x=0, y=0, width=80, height=80, min_val=0, max_val=100):
        super().__init__('gauge', x, y, width, height)
        self.properties = {
            'min_val': min_val,
            'max_val': max_val,
            'value': 50,
            'color': '#2196F3'
        }
    
    def draw(self, scene):
        import math
        size = min(self.width, self.height)
        center_x = self.x + size // 2
        center_y = self.y + size // 2
        radius = size // 2 - 5
        
        # Draw background circle
        bg_ellipse = QGraphicsEllipseItem(center_x - radius, center_y - radius, radius * 2, radius * 2)
        bg_ellipse.setBrush(QBrush(QColor('#FFFFFF')))
        bg_ellipse.setPen(QPen(Qt.black))
        scene.addItem(bg_ellipse)
        
        # Draw scale marks and values
        min_val = self.properties.get('min_val', 0)
        max_val = self.properties.get('max_val', 100)
        value = self.properties.get('value', 50)
        
        # Angle range: 225° (bottom-left, min) to -45°/315° (bottom-right, max)
        # This creates a 270° arc going counter-clockwise from bottom-left to bottom-right through the top
        start_angle = 225  # Bottom-left (0 value)
        end_angle = -45    # Bottom-right (max value), equivalent to 315°
        angle_range = end_angle - start_angle  # -45 - 225 = -270° (counter-clockwise)
        
        for i in range(11):
            angle = start_angle + (i * angle_range / 10)
            rad = math.radians(angle)
            
            # Outer point
            x1 = center_x + radius * math.cos(rad)
            y1 = center_y - radius * math.sin(rad)
            
            # Inner point
            x2 = center_x + (radius - 10) * math.cos(rad)
            y2 = center_y - (radius - 10) * math.sin(rad)
            
            line = QGraphicsLineItem(x1, y1, x2, y2)
            line.setPen(QPen(Qt.black))
            scene.addItem(line)
            
            # Draw scale value text
            scale_value = min_val + (max_val - min_val) * i / 10
            value_text = QGraphicsTextItem(str(int(scale_value)))
            font = QFont()
            font.setPointSize(8)
            value_text.setFont(font)
            value_text.setDefaultTextColor(QColor('#000000'))
            
            # Position text outside the tick marks with proper arc alignment
            text_radius = radius + 20
            text_x = center_x + text_radius * math.cos(rad)
            text_y = center_y - text_radius * math.sin(rad)
            
            # Get text dimensions
            text_rect = value_text.boundingRect()
            text_w = text_rect.width()
            text_h = text_rect.height()
            
            # Center the text on its position
            value_text.setPos(text_x - text_w / 2, text_y - text_h / 2)
            scene.addItem(value_text)
        
        # Draw needle
        ratio = (value - min_val) / (max_val - min_val) if max_val > min_val else 0.5
        ratio = max(0, min(1, ratio))
        needle_angle = start_angle + ratio * angle_range
        needle_rad = math.radians(needle_angle)
        
        needle_x = center_x + (radius - 15) * math.cos(needle_rad)
        needle_y = center_y - (radius - 15) * math.sin(needle_rad)
        
        needle = QGraphicsLineItem(center_x, center_y, needle_x, needle_y)
        needle.setPen(QPen(QColor('#FF0000'), 2))
        scene.addItem(needle)
        
        # Draw center circle
        center_circle = QGraphicsEllipseItem(center_x - 5, center_y - 5, 10, 10)
        center_circle.setBrush(QBrush(QColor('#000000')))
        center_circle.setPen(QPen(Qt.NoPen))
        scene.addItem(center_circle)
        
        # Draw current value text at bottom
        current_value_text = QGraphicsTextItem(str(int(value)))
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        current_value_text.setFont(font)
        current_value_text.setDefaultTextColor(QColor('#000000'))
        text_rect = current_value_text.boundingRect()
        current_value_text.setPos(center_x - text_rect.width() / 2, center_y + radius / 3)
        scene.addItem(current_value_text)


class HMISwitch(HMIObject):
    def __init__(self, x=0, y=0, width=60, height=30, state=False):
        super().__init__('switch', x, y, width, height)
        self.properties = {
            'state': state,
            'on_color': '#4CAF50',
            'off_color': '#CCCCCC',
            'on_text': '开',
            'off_text': '关',
            'text_color': '#FFFFFF',
            'font_size': 10,
            'font_bold': False,
            'font_italic': False,
            'font_underline': False,
            'text_h_align': 'center',
            'text_v_align': 'middle'
        }
    
    def draw(self, scene):
        is_on = self.properties.get('state', False)
        color = self.properties.get('on_color', '#4CAF50') if is_on else self.properties.get('off_color', '#CCCCCC')
        text_content = self.properties.get('on_text', '开') if is_on else self.properties.get('off_text', '关')
        
        # Draw switch background
        rect = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        rect.setBrush(QBrush(QColor(color)))
        rect.setPen(QPen(Qt.black))
        rect.setZValue(self.z_value)
        scene.addItem(rect)
        
        # Prepare font
        font = QFont()
        font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(self.properties.get('font_size', 10))
        font.setBold(self.properties.get('font_bold', False))
        font.setItalic(self.properties.get('font_italic', False))
        font.setUnderline(self.properties.get('font_underline', False))
        
        # Create text item first to get actual bounding rect
        text_item = QGraphicsTextItem(text_content)
        text_item.setDefaultTextColor(QColor(self.properties.get('text_color', '#FFFFFF')))
        text_item.setFont(font)
        text_item.setZValue(self.z_value + 1)
        
        # Get actual text dimensions from bounding rect
        text_rect = text_item.boundingRect()
        text_width = text_rect.width()
        text_height = text_rect.height()
        
        h_align = self.properties.get('text_h_align', 'center')
        v_align = self.properties.get('text_v_align', 'middle')
        
        # Calculate center of switch
        center_x = self.x + self.width / 2
        center_y = self.y + self.height / 2
        
        # Horizontal alignment - center text around the calculated point
        if h_align == 'left':
            text_x = self.x + 3
        elif h_align == 'right':
            text_x = self.x + self.width - text_width - 3
        else:  # center
            text_x = center_x - text_width / 2
        
        # Vertical alignment - center text around the calculated point
        if v_align == 'top':
            text_y = self.y + 3
        elif v_align == 'bottom':
            text_y = self.y + self.height - text_height - 3
        else:  # middle
            text_y = center_y - text_height / 2
        
        text_item.setPos(text_x, text_y)
        scene.addItem(text_item)


class HMILight(HMIObject):
    def __init__(self, x=0, y=0, width=30, height=30, state=False):
        super().__init__('light', x, y, width, height)
        self.properties = {
            'state': state,
            'on_color': '#00FF00',  # 开启状态颜色 - 默认绿色
            'off_color': '#808080',  # 关闭状态颜色 - 默认灰色
            'text': '',  # 指示灯文本
            'text_color': '#000000',  # 文本颜色
            'font_size': 10,  # 字体大小
            'font_bold': False,
            'font_italic': False,
            'font_underline': False,
            'text_h_align': 'center',  # 文本水平对齐: left, center, right
            'text_v_align': 'middle',  # 文本垂直对齐: top, middle, bottom
            'shape': 'circle',  # 形状: circle, square, rectangle
            'on_image': '',  # 开启状态图片路径
            'off_image': '',  # 关闭状态图片路径
            'use_image': False,  # 是否使用图片
            'border': True,  # 是否显示边框
            'border_color': '#000000',  # 边框颜色
            'border_width': 1  # 边框宽度
        }
        self.on_pixmap = None  # 开启状态图片
        self.off_pixmap = None  # 关闭状态图片
    
    def __deepcopy__(self, memo):
        """Custom deepcopy that excludes QPixmap"""
        # Create new instance without calling __init__
        new_obj = HMILight.__new__(HMILight)
        memo[id(self)] = new_obj
        
        # Copy basic attributes
        new_obj.obj_type = self.obj_type
        new_obj.x = self.x
        new_obj.y = self.y
        new_obj.width = self.width
        new_obj.height = self.height
        new_obj.properties = copy.deepcopy(self.properties, memo)
        new_obj.variables = copy.deepcopy(self.variables, memo)
        new_obj.visibility = copy.deepcopy(self.visibility, memo)
        new_obj.z_value = self.z_value
        
        # Don't copy pixmaps, they will be loaded on demand in draw()
        new_obj.on_pixmap = None
        new_obj.off_pixmap = None
        
        return new_obj
    
    def load_images(self):
        """Load on/off state images with caching"""
        from ..core.data_manager import get_image_cache
        cache = get_image_cache()
        
        on_image_path = self.properties.get('on_image', '')
        off_image_path = self.properties.get('off_image', '')
        
        if on_image_path and os.path.exists(on_image_path):
            cached = cache.get(on_image_path)
            if cached:
                self.on_pixmap = cached
            else:
                self.on_pixmap = QPixmap(on_image_path)
                cache.set(on_image_path, self.on_pixmap)
        if off_image_path and os.path.exists(off_image_path):
            cached = cache.get(off_image_path)
            if cached:
                self.off_pixmap = cached
            else:
                self.off_pixmap = QPixmap(off_image_path)
                cache.set(off_image_path, self.off_pixmap)
    
    def draw(self, scene):
        state = self.properties.get('state', False)
        use_image = self.properties.get('use_image', False)
        
        if use_image:
            self._draw_with_image(scene, state)
        else:
            self._draw_with_color(scene, state)
        
        # Draw text if exists
        text = self.properties.get('text', '')
        if text:
            self._draw_text(scene, text)
    
    def _draw_with_color(self, scene, state):
        """Draw light with color fill"""
        color = self.properties.get('on_color', '#00FF00') if state else self.properties.get('off_color', '#808080')
        shape = self.properties.get('shape', 'circle')
        border = self.properties.get('border', True)
        border_color = self.properties.get('border_color', '#000000')
        border_width = self.properties.get('border_width', 1)
        
        pen = QPen(QColor(border_color))
        pen.setWidth(border_width)
        brush = QBrush(QColor(color))
        
        if shape == 'circle':
            # Draw circle
            item = QGraphicsEllipseItem(self.x, self.y, self.width, self.height)
        elif shape == 'square':
            # Draw square (use smaller dimension)
            size = min(self.width, self.height)
            x_offset = (self.width - size) / 2
            y_offset = (self.height - size) / 2
            item = QGraphicsRectItem(self.x + x_offset, self.y + y_offset, size, size)
        else:  # rectangle
            item = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        
        item.setBrush(brush)
        if border:
            item.setPen(pen)
        else:
            item.setPen(QPen(Qt.NoPen))
        item.setZValue(self.z_value)
        scene.addItem(item)
    
    def _draw_with_image(self, scene, state):
        """Draw light with image"""
        # Load images if not loaded
        if self.on_pixmap is None or self.off_pixmap is None:
            self.load_images()
        
        pixmap = self.on_pixmap if state else self.off_pixmap
        
        if pixmap and not pixmap.isNull():
            # Scale image to fit
            scaled_pixmap = pixmap.scaled(self.width, self.height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # Center the image
            x_offset = (self.width - scaled_pixmap.width()) / 2
            y_offset = (self.height - scaled_pixmap.height()) / 2
            pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
            pixmap_item.setPos(self.x + x_offset, self.y + y_offset)
            pixmap_item.setZValue(self.z_value)
            scene.addItem(pixmap_item)
        else:
            # Fallback to color if image not available
            self._draw_with_color(scene, state)
    
    def _draw_text(self, scene, text):
        """Draw text on the light"""
        text_color = self.properties.get('text_color', '#000000')
        font_size = self.properties.get('font_size', 10)
        font_bold = self.properties.get('font_bold', False)
        font_italic = self.properties.get('font_italic', False)
        font_underline = self.properties.get('font_underline', False)
        h_align = self.properties.get('text_h_align', 'center')
        v_align = self.properties.get('text_v_align', 'middle')
        
        text_item = QGraphicsTextItem(str(text))
        text_item.setDefaultTextColor(QColor(text_color))
        
        font = QFont()
        font.setPointSize(font_size)
        font.setBold(font_bold)
        font.setItalic(font_italic)
        font.setUnderline(font_underline)
        text_item.setFont(font)
        
        # Set Z value to ensure text is drawn on top
        text_item.setZValue(self.z_value + 1)
        
        # Calculate text position based on alignment
        text_rect = text_item.boundingRect()
        
        # Horizontal alignment
        if h_align == 'left':
            text_x = self.x + 2
        elif h_align == 'right':
            text_x = self.x + self.width - text_rect.width() - 2
        else:  # center
            text_x = self.x + (self.width - text_rect.width()) / 2
        
        # Vertical alignment
        if v_align == 'top':
            text_y = self.y + 2
        elif v_align == 'bottom':
            text_y = self.y + self.height - text_rect.height() - 2
        else:  # middle
            text_y = self.y + (self.height - text_rect.height()) / 2
        
        text_item.setPos(text_x, text_y)
        scene.addItem(text_item)


class HMIPictureBox(HMIObject):
    def __init__(self, x=0, y=0, width=100, height=100, image_path=''):
        super().__init__('picture', x, y, width, height)
        self.properties = {
            'image_path': image_path,
            'keep_aspect_ratio': True
        }
        self.pixmap = None
        if image_path:
            self.load_image(image_path)
    
    def __deepcopy__(self, memo):
        """Custom deepcopy that excludes QPixmap"""
        # Create new instance without calling __init__
        new_obj = HMIPictureBox.__new__(HMIPictureBox)
        memo[id(self)] = new_obj
        
        # Copy basic attributes
        new_obj.obj_type = self.obj_type
        new_obj.x = self.x
        new_obj.y = self.y
        new_obj.width = self.width
        new_obj.height = self.height
        new_obj.properties = copy.deepcopy(self.properties, memo)
        new_obj.variables = copy.deepcopy(self.variables, memo)
        new_obj.visibility = copy.deepcopy(self.visibility, memo)
        new_obj.z_value = self.z_value
        
        # Don't copy pixmap, it will be loaded on demand in draw()
        new_obj.pixmap = None
        
        return new_obj
    
    def load_image(self, image_path):
        """Load image from file path with caching"""
        from ..core.data_manager import get_image_cache
        cache = get_image_cache()
        
        if image_path and os.path.exists(image_path):
            cached = cache.get(image_path)
            if cached:
                self.pixmap = cached
            else:
                self.pixmap = QPixmap(image_path)
                cache.set(image_path, self.pixmap)
            self.properties['image_path'] = image_path
            return True
        return False
    
    def draw(self, scene):
        image_path = self.properties.get('image_path', '')
        
        # Try to load image if not loaded
        if not self.pixmap and image_path:
            self.load_image(image_path)
        
        if self.pixmap and not self.pixmap.isNull():
            # Draw the image
            if self.properties.get('keep_aspect_ratio', True):
                # Scale while keeping aspect ratio
                scaled_pixmap = self.pixmap.scaled(self.width, self.height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                # Center the image
                x_offset = (self.width - scaled_pixmap.width()) / 2
                y_offset = (self.height - scaled_pixmap.height()) / 2
                pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
                pixmap_item.setPos(self.x + x_offset, self.y + y_offset)
            else:
                # Stretch to fit
                scaled_pixmap = self.pixmap.scaled(self.width, self.height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
                pixmap_item.setPos(self.x, self.y)
            
            scene.addItem(pixmap_item)
        else:
            # Draw placeholder if no image
            bg_rect = QGraphicsRectItem(self.x, self.y, self.width, self.height)
            bg_rect.setBrush(QBrush(QColor('#EEEEEE')))
            bg_rect.setPen(QPen(Qt.black))
            scene.addItem(bg_rect)
            
            # Draw placeholder text
            text = QGraphicsTextItem("No Image")
            text.setDefaultTextColor(Qt.gray)
            font = QFont()
            font.setPointSize(10)
            text.setFont(font)
            text.setPos(self.x + 10, self.y + (self.height - 20) / 2)
            scene.addItem(text)


class HMIPictureList(HMIObject):
    """图形列表控件 - 根据变量值显示不同的图片"""
    
    def __init__(self, x=0, y=0, width=100, height=100):
        super().__init__('picture_list', x, y, width, height)
        self.properties = {
            'name': '图形列表',
            'keep_aspect_ratio': True,
            'border_visible': True,
            'border_color': '#000000',
            'border_width': 1,
            'bg_color': '#EEEEEE',
            'default_image': '',
            'state_images': [],
            'value_type': 'integer',
            'show_value_label': False,
            'value_label_position': 'bottom'
        }
        self.pixmaps = {}
        self.current_value = None
    
    def __deepcopy__(self, memo):
        new_obj = HMIPictureList.__new__(HMIPictureList)
        memo[id(self)] = new_obj
        
        new_obj.obj_type = self.obj_type
        new_obj.x = self.x
        new_obj.y = self.y
        new_obj.width = self.width
        new_obj.height = self.height
        new_obj.properties = copy.deepcopy(self.properties, memo)
        new_obj.variables = copy.deepcopy(self.variables, memo)
        new_obj.visibility = copy.deepcopy(self.visibility, memo)
        new_obj.pixmaps = {}
        new_obj.current_value = None
        new_obj.z_value = self.z_value
        
        return new_obj
    
    def load_image(self, image_path):
        """加载图片（带缓存）"""
        from ..core.data_manager import get_image_cache
        cache = get_image_cache()
        
        if image_path and os.path.exists(image_path):
            cached = cache.get(image_path)
            if cached:
                return cached
            pixmap = QPixmap(image_path)
            cache.set(image_path, pixmap)
            return pixmap
        return None
    
    def get_image_for_value(self, value):
        """根据值获取对应的图片路径"""
        state_images = self.properties.get('state_images', [])
        value_type = self.properties.get('value_type', 'integer')
        
        try:
            if value_type == 'integer':
                compare_val = int(float(value)) if value is not None else 0
            elif value_type == 'float':
                compare_val = float(value) if value is not None else 0.0
            elif value_type == 'bool':
                compare_val = bool(value) if value is not None else False
            else:
                compare_val = str(value) if value is not None else ''
        except (ValueError, TypeError):
            compare_val = value
        
        for state in state_images:
            state_value = state.get('value')
            compare_type = state.get('compare_type', 'equal')
            
            try:
                if value_type == 'integer':
                    state_val = int(float(state_value)) if state_value != '' else None
                elif value_type == 'float':
                    state_val = float(state_value) if state_value != '' else None
                elif value_type == 'bool':
                    state_val = bool(int(float(state_value))) if state_value != '' else None
                else:
                    state_val = str(state_value)
            except (ValueError, TypeError):
                state_val = state_value
            
            if compare_type == 'equal' and compare_val == state_val:
                return state.get('image_path', '')
            elif compare_type == 'greater' and compare_val > state_val:
                return state.get('image_path', '')
            elif compare_type == 'less' and compare_val < state_val:
                return state.get('image_path', '')
            elif compare_type == 'greater_equal' and compare_val >= state_val:
                return state.get('image_path', '')
            elif compare_type == 'less_equal' and compare_val <= state_val:
                return state.get('image_path', '')
            elif compare_type == 'not_equal' and compare_val != state_val:
                return state.get('image_path', '')
        
        return self.properties.get('default_image', '')
    
    def draw(self, scene):
        bg_color = QColor(self.properties.get('bg_color', '#EEEEEE'))
        border_visible = self.properties.get('border_visible', True)
        border_color = QColor(self.properties.get('border_color', '#000000'))
        border_width = self.properties.get('border_width', 1)
        keep_aspect_ratio = self.properties.get('keep_aspect_ratio', True)
        
        image_path = ''
        if self.current_value is not None:
            image_path = self.get_image_for_value(self.current_value)
        
        if not image_path:
            image_path = self.properties.get('default_image', '')
        
        pixmap = None
        if image_path:
            pixmap = self.load_image(image_path)
        
        if pixmap and not pixmap.isNull():
            if keep_aspect_ratio:
                scaled_pixmap = pixmap.scaled(self.width - 4, self.height - 4, 
                                              Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x_offset = (self.width - scaled_pixmap.width()) / 2
                y_offset = (self.height - scaled_pixmap.height()) / 2
                pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
                pixmap_item.setPos(self.x + x_offset, self.y + y_offset)
            else:
                scaled_pixmap = pixmap.scaled(self.width - 4, self.height - 4, 
                                              Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
                pixmap_item.setPos(self.x + 2, self.y + 2)
            scene.addItem(pixmap_item)
        else:
            bg_rect = QGraphicsRectItem(self.x, self.y, self.width, self.height)
            bg_rect.setBrush(QBrush(bg_color))
            if border_visible:
                bg_rect.setPen(QPen(border_color, border_width))
            else:
                bg_rect.setPen(QPen(Qt.NoPen))
            scene.addItem(bg_rect)
            
            text = QGraphicsTextItem("图形列表")
            text.setDefaultTextColor(Qt.gray)
            font = QFont()
            font.setPointSize(10)
            text.setFont(font)
            text_rect = text.boundingRect()
            text.setPos(self.x + (self.width - text_rect.width()) / 2, 
                       self.y + (self.height - text_rect.height()) / 2)
            scene.addItem(text)
        
        if border_visible:
            border_rect = QGraphicsRectItem(self.x, self.y, self.width, self.height)
            border_rect.setPen(QPen(border_color, border_width))
            border_rect.setBrush(QBrush(Qt.NoBrush))
            scene.addItem(border_rect)
        
        show_value_label = self.properties.get('show_value_label', False)
        if show_value_label and self.current_value is not None:
            value_label_position = self.properties.get('value_label_position', 'bottom')
            value_text = QGraphicsTextItem(str(self.current_value))
            value_text.setDefaultTextColor(Qt.black)
            font = QFont()
            font.setPointSize(9)
            value_text.setFont(font)
            
            text_rect = value_text.boundingRect()
            if value_label_position == 'bottom':
                value_text.setPos(self.x + (self.width - text_rect.width()) / 2, 
                                 self.y + self.height + 2)
            elif value_label_position == 'top':
                value_text.setPos(self.x + (self.width - text_rect.width()) / 2, 
                                 self.y - text_rect.height() - 2)
            elif value_label_position == 'left':
                value_text.setPos(self.x - text_rect.width() - 2, 
                                 self.y + (self.height - text_rect.height()) / 2)
            else:
                value_text.setPos(self.x + self.width + 2, 
                                 self.y + (self.height - text_rect.height()) / 2)
            
            scene.addItem(value_text)


class HMITrendChart(HMIObject):
    def __init__(self, x=0, y=0, width=300, height=200):
        super().__init__('trend_chart', x, y, width, height)
        self.properties = {
            'title': '趋势图',
            'title_color': '#000000',
            'title_font_size': 12,
            'title_visible': True,
            'bg_color': '#FFFFFF',
            'grid_color': '#E0E0E0',
            'grid_visible': True,
            'border_color': '#000000',
            'border_width': 1,
            'x_axis_label': '时间',
            'y_axis_label': '值',
            'axis_color': '#000000',
            'axis_font_size': 9,
            'y_min': 0,
            'y_max': 100,
            'y_auto_scale': True,
            'time_span': 3600,
            'update_interval': 1000,
            'line_width': 2,
            'show_legend': True,
            'legend_position': 'top',
            'pen_styles': [],
            'variables': []
        }
        self.data_history = {}
        self.max_data_points = 3600
    
    def draw(self, scene):
        """Draw trend chart preview in designer using matplotlib"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            
            bg_color = self.properties.get('bg_color', '#FFFFFF')
            border_color = self.properties.get('border_color', '#000000')
            border_width = self.properties.get('border_width', 1)
            title = self.properties.get('title', '趋势图')
            title_visible = self.properties.get('title_visible', True)
            title_color = self.properties.get('title_color', '#000000')
            title_font_size = self.properties.get('title_font_size', 12)
            grid_visible = self.properties.get('grid_visible', True)
            grid_color = self.properties.get('grid_color', '#E0E0E0')
            y_min = self.properties.get('y_min', 0)
            y_max = self.properties.get('y_max', 100)
            time_span = self.properties.get('time_span', 60)
            line_width = self.properties.get('line_width', 2)
            show_legend = self.properties.get('show_legend', True)
            
            dpi = 100
            fig_width = self.width / dpi
            fig_height = self.height / dpi
            
            fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
            fig.patch.set_facecolor(bg_color)
            ax.set_facecolor(bg_color)
            
            if title_visible and title:
                ax.set_title(title, fontsize=title_font_size, color=title_color, fontname='Microsoft YaHei')
            
            ax.set_xlim(0, time_span)
            ax.set_ylim(y_min, y_max)
            
            if grid_visible:
                ax.grid(True, linestyle='--', color=grid_color, linewidth=0.5)
            
            ax.set_xlabel('时间 (秒)', fontsize=self.properties.get('axis_font_size', 9))
            ax.set_ylabel('值', fontsize=self.properties.get('axis_font_size', 9))
            
            ax.tick_params(axis='both', labelsize=8)
            
            for spine in ax.spines.values():
                spine.set_edgecolor(border_color)
                spine.set_linewidth(border_width)
            
            ax.text(0.5, 0.5, '[趋势图预览]', transform=ax.transAxes,
                   ha='center', va='center', fontsize=10, color='#999999')
            
            plt.tight_layout()
            
            canvas = FigureCanvasAgg(fig)
            canvas.draw()
            
            import io
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=dpi, facecolor=bg_color, edgecolor='none')
            buf.seek(0)
            
            from PyQt5.QtGui import QPixmap, QImage
            qimg = QImage.fromData(buf.getvalue())
            pixmap = QPixmap.fromImage(qimg)
            
            plt.close(fig)
            
            from PyQt5.QtWidgets import QGraphicsPixmapItem
            pixmap_item = QGraphicsPixmapItem(pixmap)
            pixmap_item.setPos(self.x, self.y)
            pixmap_item.setZValue(self.z_value)
            scene.addItem(pixmap_item)
            
        except ImportError:
            self._draw_fallback(scene)
        except Exception as e:
            print(f"TrendChart draw error: {e}")
            self._draw_fallback(scene)
    
    def _draw_fallback(self, scene):
        """Fallback drawing without matplotlib"""
        bg_color = self.properties.get('bg_color', '#FFFFFF')
        border_color = self.properties.get('border_color', '#000000')
        border_width = self.properties.get('border_width', 1)
        title = self.properties.get('title', '趋势图')
        title_visible = self.properties.get('title_visible', True)
        
        rect = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        rect.setBrush(QBrush(QColor(bg_color)))
        if border_width > 0:
            pen = QPen(QColor(border_color))
            pen.setWidth(border_width)
            rect.setPen(pen)
        else:
            rect.setPen(QPen(Qt.NoPen))
        rect.setZValue(self.z_value)
        scene.addItem(rect)
        
        if title_visible and title:
            title_item = QGraphicsTextItem(title)
            title_font = QFont()
            title_font.setFamily('Microsoft YaHei')
            title_font.setPointSize(self.properties.get('title_font_size', 12))
            title_font.setBold(True)
            title_item.setFont(title_font)
            title_item.setDefaultTextColor(QColor(self.properties.get('title_color', '#000000')))
            title_item.setPos(self.x + 10, self.y + 5)
            title_item.setZValue(self.z_value + 1)
            scene.addItem(title_item)
        
        placeholder = QGraphicsTextItem("[趋势图预览]")
        placeholder.setFont(QFont('Microsoft YaHei', 10))
        placeholder.setDefaultTextColor(QColor('#999999'))
        ph_rect = placeholder.boundingRect()
        placeholder.setPos(self.x + (self.width - ph_rect.width()) / 2,
                          self.y + (self.height - ph_rect.height()) / 2)
        placeholder.setZValue(self.z_value + 1)
        scene.addItem(placeholder)


class HMIHistoryTrend(HMIObject):
    def __init__(self, x=0, y=0, width=400, height=300):
        super().__init__('history_trend', x, y, width, height)
        self.properties = {
            'title': '历史趋势图',
            'title_color': '#000000',
            'title_font_size': 12,
            'title_visible': True,
            'bg_color': '#FFFFFF',
            'grid_color': '#E0E0E0',
            'grid_visible': True,
            'border_color': '#000000',
            'border_width': 1,
            'y_min': 0,
            'y_max': 100,
            'y_auto_scale': True,
            'line_width': 2,
            'show_legend': True,
            'control_font_size': 11,
            'default_time_range': '1h',
            'variables': []
        }
    
    def draw(self, scene):
        bg_color = self.properties.get('bg_color', '#FFFFFF')
        border_color = self.properties.get('border_color', '#000000')
        border_width = self.properties.get('border_width', 1)
        title = self.properties.get('title', '历史趋势图')
        title_visible = self.properties.get('title_visible', True)
        
        rect = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        rect.setBrush(QBrush(QColor(bg_color)))
        if border_width > 0:
            pen = QPen(QColor(border_color))
            pen.setWidth(border_width)
            rect.setPen(pen)
        else:
            rect.setPen(QPen(Qt.NoPen))
        rect.setZValue(self.z_value)
        scene.addItem(rect)
        
        if title_visible and title:
            title_item = QGraphicsTextItem(title)
            title_font = QFont()
            title_font.setFamily('Microsoft YaHei')
            title_font.setPointSize(self.properties.get('title_font_size', 12))
            title_font.setBold(True)
            title_item.setFont(title_font)
            title_item.setDefaultTextColor(QColor(self.properties.get('title_color', '#000000')))
            title_item.setPos(self.x + 10, self.y + 5)
            title_item.setZValue(self.z_value + 1)
            scene.addItem(title_item)
        
        placeholder = QGraphicsTextItem("[历史趋势图 - 运行时查询]")
        placeholder.setFont(QFont('Microsoft YaHei', 10))
        placeholder.setDefaultTextColor(QColor('#999999'))
        ph_rect = placeholder.boundingRect()
        placeholder.setPos(self.x + (self.width - ph_rect.width()) / 2,
                          self.y + (self.height - ph_rect.height()) / 2)
        placeholder.setZValue(self.z_value + 1)
        scene.addItem(placeholder)


class HMITableView(HMIObject):
    def __init__(self, x=0, y=0, width=300, height=200):
        super().__init__('table_view', x, y, width, height)
        self.properties = {}
    
    def draw(self, scene):
        rect = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        rect.setBrush(QBrush(QColor('#FFFFFF')))
        rect.setPen(QPen(Qt.black))
        scene.addItem(rect)


class HMIProgressBar(HMIObject):
    def __init__(self, x=0, y=0, width=200, height=30, value=50, min_val=0, max_val=100):
        super().__init__('progress', x, y, width, height)
        self.properties = {
            'value': value,
            'min_val': min_val,
            'max_val': max_val,
            'orientation': 'horizontal',  # horizontal or vertical
            'bar_color': '#4CAF50',  # 进度条颜色
            'bg_color': '#EEEEEE',  # 背景颜色
            'border_color': '#000000',  # 边框颜色
            'border_width': 1,  # 边框宽度
            'show_value': True,  # 是否显示数值
            'show_percentage': False,  # 是否显示百分比
            'text_color': '#000000',  # 文字颜色
            'font_size': 10,  # 字体大小
            'font_bold': False,
            'font_italic': False,
            'font_underline': False,
            'text_position': 'center',  # 文字位置: center, left, right, top, bottom
            'border_radius': 0,  # 圆角半径
            'bar_gradient': False  # 是否使用渐变效果
        }

    def draw(self, scene):
        # Get properties
        value = self.properties.get('value', 50)
        min_val = self.properties.get('min_val', 0)
        max_val = self.properties.get('max_val', 100)
        orientation = self.properties.get('orientation', 'horizontal')
        bar_color = self.properties.get('bar_color', '#4CAF50')
        bg_color = self.properties.get('bg_color', '#EEEEEE')
        border_color = self.properties.get('border_color', '#000000')
        border_width = self.properties.get('border_width', 1)
        border_radius = self.properties.get('border_radius', 0)

        # Calculate progress ratio
        ratio = (value - min_val) / (max_val - min_val) if max_val > min_val else 0
        ratio = max(0, min(1, ratio))  # Clamp between 0 and 1

        # Draw background
        if border_radius > 0:
            # Use path for rounded rectangle
            from PyQt5.QtGui import QPainterPath
            path = QPainterPath()
            path.addRoundedRect(self.x, self.y, self.width, self.height, border_radius, border_radius)
            bg_item = QGraphicsPathItem(path)
        else:
            bg_item = QGraphicsRectItem(self.x, self.y, self.width, self.height)

        bg_item.setBrush(QBrush(QColor(bg_color)))
        if border_width > 0:
            pen = QPen(QColor(border_color))
            pen.setWidth(border_width)
            bg_item.setPen(pen)
        else:
            bg_item.setPen(QPen(Qt.NoPen))
        bg_item.setZValue(self.z_value)  # Use object's z_value
        scene.addItem(bg_item)

        # Draw progress bar
        if orientation == 'horizontal':
            bar_width = self.width * ratio
            if bar_width > 0:
                if border_radius > 0:
                    # Simplified rounded bar for horizontal
                    bar_item = QGraphicsRectItem(self.x, self.y, bar_width, self.height)
                else:
                    bar_item = QGraphicsRectItem(self.x, self.y, bar_width, self.height)
        else:  # vertical
            bar_height = self.height * ratio
            if bar_height > 0:
                bar_y = self.y + self.height - bar_height
                if border_radius > 0:
                    bar_item = QGraphicsRectItem(self.x, bar_y, self.width, bar_height)
                else:
                    bar_item = QGraphicsRectItem(self.x, bar_y, self.width, bar_height)

        if ratio > 0:
            # Check if gradient is enabled
            if self.properties.get('bar_gradient', False):
                from PyQt5.QtGui import QLinearGradient
                if orientation == 'horizontal':
                    gradient = QLinearGradient(self.x, self.y, self.x + self.width, self.y)
                else:
                    gradient = QLinearGradient(self.x, self.y + self.height, self.x, self.y)
                gradient.setColorAt(0, QColor(bar_color))
                gradient.setColorAt(1, QColor(bar_color).lighter(150))
                bar_item.setBrush(QBrush(gradient))
            else:
                bar_item.setBrush(QBrush(QColor(bar_color)))
            bar_item.setPen(QPen(Qt.NoPen))
            bar_item.setZValue(self.z_value + 1)  # Slightly higher than background
            scene.addItem(bar_item)

        # Draw value text if enabled
        if self.properties.get('show_value', True) or self.properties.get('show_percentage', False):
            self._draw_text(scene, value, ratio)

    def _draw_text(self, scene, value, ratio):
        """Draw value or percentage text on progress bar"""
        show_value = self.properties.get('show_value', True)
        show_percentage = self.properties.get('show_percentage', False)
        text_color = self.properties.get('text_color', '#000000')
        font_size = self.properties.get('font_size', 10)
        text_position = self.properties.get('text_position', 'center')

        # Format text
        if show_percentage:
            text = f"{int(ratio * 100)}%"
        elif show_value:
            text = str(value)
        else:
            return

        text_item = QGraphicsTextItem(text)
        text_item.setDefaultTextColor(QColor(text_color))

        font = QFont()
        font.setPointSize(font_size)
        font.setBold(self.properties.get('font_bold', False))
        font.setItalic(self.properties.get('font_italic', False))
        font.setUnderline(self.properties.get('font_underline', False))
        text_item.setFont(font)

        # Calculate text position
        text_rect = text_item.boundingRect()

        if text_position == 'center':
            text_x = self.x + (self.width - text_rect.width()) / 2
            text_y = self.y + (self.height - text_rect.height()) / 2
        elif text_position == 'left':
            text_x = self.x + 5
            text_y = self.y + (self.height - text_rect.height()) / 2
        elif text_position == 'right':
            text_x = self.x + self.width - text_rect.width() - 5
            text_y = self.y + (self.height - text_rect.height()) / 2
        elif text_position == 'top':
            text_x = self.x + (self.width - text_rect.width()) / 2
            text_y = self.y - text_rect.height() - 2
        elif text_position == 'bottom':
            text_x = self.x + (self.width - text_rect.width()) / 2
            text_y = self.y + self.height + 2
        else:
            text_x = self.x + (self.width - text_rect.width()) / 2
            text_y = self.y + (self.height - text_rect.height()) / 2

        text_item.setPos(text_x, text_y)
        text_item.setZValue(self.z_value + 2)  # Ensure text is on top
        scene.addItem(text_item)


class HMILine(HMIObject):
    def __init__(self, x1=0, y1=0, x2=100, y2=0):
        super().__init__('line', x1, y1, abs(x2-x1), abs(y2-y1))
        self.properties = {
            'x1': x1,
            'y1': y1,
            'x2': x2,
            'y2': y2,
            'color': '#000000',
            'line_width': 2
        }
    
    def draw(self, scene):
        line = QGraphicsLineItem(
            self.properties['x1'], 
            self.properties['y1'],
            self.properties['x2'], 
            self.properties['y2']
        )
        pen = QPen(QColor(self.properties.get('color', '#000000')))
        pen.setWidth(self.properties.get('line_width', 2))
        line.setPen(pen)
        line.setZValue(self.z_value)
        scene.addItem(line)
        
        # Draw endpoint handles (small circles) for visual feedback
        handle_radius = 5
        x1 = self.properties['x1']
        y1 = self.properties['y1']
        x2 = self.properties['x2']
        y2 = self.properties['y2']
        
        # Start point handle
        start_handle = QGraphicsEllipseItem(x1 - handle_radius, y1 - handle_radius, 
                                       handle_radius * 2, handle_radius * 2)
        start_handle.setBrush(QBrush(QColor('#2196F3')))
        start_handle.setPen(QPen(Qt.black, 1))
        start_handle.setZValue(self.z_value + 1)
        scene.addItem(start_handle)
        
        # End point handle
        end_handle = QGraphicsEllipseItem(x2 - handle_radius, y2 - handle_radius, 
                                     handle_radius * 2, handle_radius * 2)
        end_handle.setBrush(QBrush(QColor('#FF5722')))
        end_handle.setPen(QPen(Qt.black, 1))
        end_handle.setZValue(self.z_value + 1)
        scene.addItem(end_handle)


class HMIRectangle(HMIObject):
    def __init__(self, x=0, y=0, width=100, height=60):
        super().__init__('rectangle', x, y, width, height)
        self.properties = {
            'color': '#000000',
            'line_width': 2,
            'filled': False,
            'fill_color': '#FFFFFF'
        }
    
    def draw(self, scene):
        rect = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        if self.properties.get('filled', False):
            rect.setBrush(QBrush(QColor(self.properties.get('fill_color', '#FFFFFF'))))
        
        line_width = self.properties.get('line_width', 2)
        if line_width > 0:
            pen = QPen(QColor(self.properties.get('color', '#000000')))
            pen.setWidth(line_width)
            rect.setPen(pen)
        else:
            rect.setPen(QPen(Qt.NoPen))
        
        rect.setZValue(self.z_value)
        scene.addItem(rect)


class HMICircle(HMIObject):
    def __init__(self, x=0, y=0, radius=50):
        super().__init__('circle', x-radius, y-radius, radius*2, radius*2)
        self.properties = {
            'color': '#000000',
            'line_width': 2,
            'filled': False,
            'fill_color': '#FFFFFF'
        }
    
    def draw(self, scene):
        ellipse = QGraphicsEllipseItem(self.x, self.y, self.width, self.height)
        if self.properties.get('filled', False):
            ellipse.setBrush(QBrush(QColor(self.properties.get('fill_color', '#FFFFFF'))))
        
        line_width = self.properties.get('line_width', 2)
        if line_width > 0:
            pen = QPen(QColor(self.properties.get('color', '#000000')))
            pen.setWidth(line_width)
            ellipse.setPen(pen)
        else:
            ellipse.setPen(QPen(Qt.NoPen))
        
        ellipse.setZValue(self.z_value)
        scene.addItem(ellipse)


class HMISlider(HMIObject):
    """Slider control for analog values"""
    def __init__(self, x=0, y=0, width=200, height=30):
        super().__init__('slider', x, y, width, height)
        self.properties = {
            'min_value': 0,
            'max_value': 100,
            'current_value': 50,
            'orientation': 'horizontal',
            'show_value': True,
            'decimal_places': 0
        }
    
    def draw(self, scene):
        # Draw track
        track = QGraphicsRectItem(self.x, self.y + self.height//3, self.width, self.height//3)
        track.setBrush(QBrush(QColor('#CCCCCC')))
        track.setPen(QPen(Qt.NoPen))
        scene.addItem(track)
        
        # Draw fill
        ratio = (self.properties['current_value'] - self.properties['min_value']) / \
                (self.properties['max_value'] - self.properties['min_value'])
        fill_width = int(self.width * ratio)
        fill = QGraphicsRectItem(self.x, self.y + self.height//3, fill_width, self.height//3)
        fill.setBrush(QBrush(QColor('#4CAF50')))
        fill.setPen(QPen(Qt.NoPen))
        scene.addItem(fill)
        
        # Draw handle
        handle_x = self.x + fill_width - 5
        handle = QGraphicsRectItem(handle_x, self.y, 10, self.height)
        handle.setBrush(QBrush(QColor('#2196F3')))
        handle.setPen(QPen(Qt.black))
        scene.addItem(handle)
        
        # Draw value text
        if self.properties.get('show_value', True):
            value_text = f"{self.properties['current_value']:.{self.properties.get('decimal_places', 0)}f}"
            text = QGraphicsTextItem(value_text)
            text.setPos(self.x + self.width + 5, self.y)
            scene.addItem(text)


class HMIKnob(HMIObject):
    """Rotary knob control"""
    def __init__(self, x=0, y=0, size=80):
        super().__init__('knob', x, y, size, size)
        self.properties = {
            'min_value': 0,
            'max_value': 100,
            'current_value': 50,
            'start_angle': -135,
            'end_angle': 135,
            'show_value': True,
            'decimal_places': 1
        }
    
    def draw(self, scene):
        size = min(self.width, self.height)
        center_x = self.x + size // 2
        center_y = self.y + size // 2
        radius = size // 2 - 5
        
        # Draw background arc
        path = QPainterPath()
        start_angle = self.properties['start_angle']
        span = self.properties['end_angle'] - start_angle
        path.arcMoveTo(center_x - radius, center_y - radius, radius*2, radius*2, -start_angle)
        path.arcTo(center_x - radius, center_y - radius, radius*2, radius*2, -start_angle, -span)
        
        # Draw value arc
        ratio = (self.properties['current_value'] - self.properties['min_value']) / \
                (self.properties['max_value'] - self.properties['min_value'])
        value_span = span * ratio
        
        value_path = QPainterPath()
        value_path.arcMoveTo(center_x - radius, center_y - radius, radius*2, radius*2, -start_angle)
        value_path.arcTo(center_x - radius, center_y - radius, radius*2, radius*2, -start_angle, -value_span)
        
        # Draw center circle
        center_circle = QGraphicsEllipseItem(center_x - 8, center_y - 8, 16, 16)
        center_circle.setBrush(QBrush(QColor('#333333')))
        scene.addItem(center_circle)
        
        # Draw value text
        if self.properties.get('show_value', True):
            value_text = f"{self.properties['current_value']:.{self.properties.get('decimal_places', 1)}f}"
            text = QGraphicsTextItem(value_text)
            text.setPos(center_x - 20, center_y + radius + 5)
            scene.addItem(text)


class HMIInputField(HMIObject):
    """Text input field"""
    def __init__(self, x=0, y=0, width=150, height=30):
        super().__init__('input', x, y, width, height)
        self.properties = {
            'text': '',
            'placeholder': 'Enter value...',
            'font_size': 12,
            'font_bold': False,
            'font_italic': False,
            'font_underline': False,
            'border_color': '#999999',
            'background_color': '#FFFFFF',
            'text_color': '#000000',
            'password_mode': False,
            'numeric_only': False
        }
    
    def draw(self, scene):
        # Draw background
        bg = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        bg.setBrush(QBrush(QColor(self.properties.get('background_color', '#FFFFFF'))))
        bg.setPen(QPen(QColor(self.properties.get('border_color', '#999999'))))
        scene.addItem(bg)
        
        # Draw text
        text = self.properties.get('text', '')
        if self.properties.get('password_mode', False):
            text = '*' * len(text)
        if not text:
            text = self.properties.get('placeholder', '')
            text_item = QGraphicsTextItem(text)
            text_item.setDefaultTextColor(QColor('#999999'))
        else:
            text_item = QGraphicsTextItem(text)
            text_item.setDefaultTextColor(QColor(self.properties.get('text_color', '#000000')))
        
        font = QFont()
        font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(self.properties.get('font_size', 12))
        font.setBold(self.properties.get('font_bold', False))
        font.setItalic(self.properties.get('font_italic', False))
        font.setUnderline(self.properties.get('font_underline', False))
        text_item.setFont(font)
        text_item.setPos(self.x + 5, self.y + 5)
        scene.addItem(text_item)


class HMICheckBox(HMIObject):
    """Checkbox control"""
    def __init__(self, x=0, y=0, width=120, height=25):
        super().__init__('checkbox', x, y, width, height)
        self.properties = {
            'text': 'CheckBox',
            'checked': False,
            'font_size': 10,
            'font_bold': False,
            'font_italic': False,
            'font_underline': False,
            'text_color': '#000000'
        }
    
    def draw(self, scene):
        box_size = min(self.height - 4, 20)
        
        # Draw checkbox box
        box = QGraphicsRectItem(self.x, self.y + (self.height - box_size)//2, box_size, box_size)
        box.setBrush(QBrush(QColor('#FFFFFF')))
        box.setPen(QPen(Qt.black))
        scene.addItem(box)
        
        # Draw checkmark if checked
        if self.properties.get('checked', False):
            check = QGraphicsRectItem(self.x + 4, self.y + (self.height - box_size)//2 + 4, 
                                     box_size - 8, box_size - 8)
            check.setBrush(QBrush(QColor('#4CAF50')))
            check.setPen(QPen(Qt.NoPen))
            scene.addItem(check)
        
        # Draw text
        text = QGraphicsTextItem(self.properties.get('text', 'CheckBox'))
        font = QFont()
        font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(self.properties.get('font_size', 10))
        font.setBold(self.properties.get('font_bold', False))
        font.setItalic(self.properties.get('font_italic', False))
        font.setUnderline(self.properties.get('font_underline', False))
        text.setFont(font)
        text.setDefaultTextColor(QColor(self.properties.get('text_color', '#000000')))
        text.setPos(self.x + box_size + 8, self.y + (self.height - box_size)//2)
        scene.addItem(text)


class HMIRadioButton(HMIObject):
    """Radio button control"""
    def __init__(self, x=0, y=0, width=120, height=25):
        super().__init__('radio', x, y, width, height)
        self.properties = {
            'text': 'RadioButton',
            'selected': False,
            'font_size': 10,
            'font_bold': False,
            'font_italic': False,
            'font_underline': False,
            'text_color': '#000000',
            'group': 'default'
        }
    
    def draw(self, scene):
        circle_size = min(self.height - 4, 20)
        
        # Draw outer circle
        outer = QGraphicsEllipseItem(self.x, self.y + (self.height - circle_size)//2, 
                                     circle_size, circle_size)
        outer.setBrush(QBrush(QColor('#FFFFFF')))
        outer.setPen(QPen(Qt.black))
        scene.addItem(outer)
        
        # Draw inner circle if selected
        if self.properties.get('selected', False):
            inner = QGraphicsEllipseItem(self.x + 5, self.y + (self.height - circle_size)//2 + 5, 
                                        circle_size - 10, circle_size - 10)
            inner.setBrush(QBrush(QColor('#2196F3')))
            inner.setPen(QPen(Qt.NoPen))
            scene.addItem(inner)
        
        # Draw text
        text = QGraphicsTextItem(self.properties.get('text', 'RadioButton'))
        font = QFont()
        font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(self.properties.get('font_size', 10))
        font.setBold(self.properties.get('font_bold', False))
        font.setItalic(self.properties.get('font_italic', False))
        font.setUnderline(self.properties.get('font_underline', False))
        text.setFont(font)
        text.setDefaultTextColor(QColor(self.properties.get('text_color', '#000000')))
        text.setPos(self.x + circle_size + 8, self.y + (self.height - circle_size)//2)
        scene.addItem(text)


class HMIDropdown(HMIObject):
    """Dropdown/ComboBox control"""
    def __init__(self, x=0, y=0, width=150, height=30):
        super().__init__('dropdown', x, y, width, height)
        self.properties = {
            'items': [
                {'value': '0', 'text': 'Item 1'},
                {'value': '1', 'text': 'Item 2'},
                {'value': '2', 'text': 'Item 3'}
            ],
            'selected_index': 0,
            'bind_mode': 'index',
            'font_size': 11,
            'font_bold': False,
            'font_italic': False,
            'font_underline': False,
            'background_color': '#FFFFFF',
            'border_color': '#999999'
        }
    
    def draw(self, scene):
        # Draw background
        bg = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        bg.setBrush(QBrush(QColor(self.properties.get('background_color', '#FFFFFF'))))
        bg.setPen(QPen(QColor(self.properties.get('border_color', '#999999'))))
        scene.addItem(bg)
        
        # Draw selected text with value-text mapping support
        items = self.properties.get('items', [{'value': '0', 'text': 'Item 1'}, {'value': '1', 'text': 'Item 2'}, {'value': '2', 'text': 'Item 3'}])
        selected_idx = self.properties.get('selected_index', 0)
        bind_mode = self.properties.get('bind_mode', 'index')
        
        if bind_mode == 'value':
            # Value mode: find text by value
            target_value = self.properties.get('target_variable', '')
            text_str = ''
            for item in items:
                if isinstance(item, dict) and item.get('value', '') == str(target_value):
                    text_str = item.get('text', '')
                    break
        else:
            # Index mode: display text by index
            if 0 <= selected_idx < len(items):
                item = items[selected_idx]
                if isinstance(item, dict):
                    text_str = item.get('text', f'Item {selected_idx+1}')
                else:
                    text_str = str(item)
            else:
                text_str = ''
        
        text = QGraphicsTextItem(text_str)
        font = QFont()
        font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(self.properties.get('font_size', 11))
        font.setBold(self.properties.get('font_bold', False))
        font.setItalic(self.properties.get('font_italic', False))
        font.setUnderline(self.properties.get('font_underline', False))
        text.setFont(font)
        text.setPos(self.x + 5, self.y + 5)
        scene.addItem(text)
        
        # Draw dropdown arrow
        arrow_x = self.x + self.width - 20
        arrow_y = self.y + self.height // 2
        
        arrow = QGraphicsPolygonItem(QPolygonF([
            QPointF(arrow_x, arrow_y - 3),
            QPointF(arrow_x + 10, arrow_y - 3),
            QPointF(arrow_x + 5, arrow_y + 5)
        ]))
        arrow.setBrush(QBrush(QColor('#666666')))
        arrow.setPen(QPen(Qt.NoPen))
        scene.addItem(arrow)


class HMIAlarmDisplay(HMIObject):
    """Alarm display panel"""
    def __init__(self, x=0, y=0, width=400, height=200):
        super().__init__('alarm_display', x, y, width, height)
        self.properties = {
            'max_alarms': 10,
            'show_acknowledged': True,
            'font_size': 10,
            'font_bold': False,
            'font_italic': False,
            'font_underline': False,
            'background_color': '#FFFFFF',
            'header_color': '#333333',
            'alarm_color': '#FF4444',
            'warning_color': '#FFAA00',
            # 高级属性
            'visible_alarm_types': ['危急', '高', '中', '低', '信息', '警告', '错误'],
            'max_display_count': 50,
            'auto_scroll': True,
            'show_timestamp': True,
            'show_alarm_type': True
        }
    
    def draw(self, scene):
        # Draw background
        bg = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        bg.setBrush(QBrush(QColor(self.properties.get('background_color', '#FFFFFF'))))
        bg.setPen(QPen(Qt.black))
        scene.addItem(bg)
        
        # Draw header
        header_height = 25
        header = QGraphicsRectItem(self.x, self.y, self.width, header_height)
        header.setBrush(QBrush(QColor(self.properties.get('header_color', '#333333'))))
        header.setPen(QPen(Qt.NoPen))
        scene.addItem(header)
        
        # Header text
        header_text = QGraphicsTextItem("Alarm Display")
        header_text.setDefaultTextColor(QColor('#FFFFFF'))
        
        header_font = QFont()
        header_font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        header_font.setPointSize(self.properties.get('font_size', 10))
        header_font.setBold(self.properties.get('font_bold', False))
        header_font.setItalic(self.properties.get('font_italic', False))
        header_font.setUnderline(self.properties.get('font_underline', False))
        header_text.setFont(header_font)
        
        header_text.setPos(self.x + 5, self.y + 2)
        scene.addItem(header_text)
        
        # Sample alarm rows
        row_height = 25
        y_offset = self.y + header_height + 5
        
        sample_alarms = [
            ('10:30:45', 'High Temperature', 'Active'),
            ('10:25:12', 'Low Pressure', 'Acknowledged'),
            ('10:20:00', 'Motor Fault', 'Active')
        ]
        
        for time_str, message, status in sample_alarms:
            if y_offset + row_height > self.y + self.height:
                break
            
            alarm_font = QFont()
            alarm_font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
            alarm_font.setPointSize(self.properties.get('font_size', 10))
            alarm_font.setBold(self.properties.get('font_bold', False))
            alarm_font.setItalic(self.properties.get('font_italic', False))
            alarm_font.setUnderline(self.properties.get('font_underline', False))
                
            # Time
            time_item = QGraphicsTextItem(time_str)
            time_item.setFont(alarm_font)
            time_item.setPos(self.x + 5, y_offset)
            scene.addItem(time_item)
            
            # Message
            msg_item = QGraphicsTextItem(message)
            msg_item.setFont(alarm_font)
            msg_item.setPos(self.x + 80, y_offset)
            scene.addItem(msg_item)
            
            # Status indicator
            status_color = QColor(self.properties.get('alarm_color', '#FF4444')) if status == 'Active' else QColor('#888888')
            status_rect = QGraphicsRectItem(self.x + self.width - 80, y_offset + 5, 10, 10)
            status_rect.setBrush(QBrush(status_color))
            status_rect.setPen(QPen(Qt.NoPen))
            scene.addItem(status_rect)
            
            # Status text
            status_text = QGraphicsTextItem(status)
            status_text.setFont(alarm_font)
            status_text.setPos(self.x + self.width - 65, y_offset)
            scene.addItem(status_text)
            
            y_offset += row_height


class HMITextArea(HMIObject):
    """Multi-line text area"""
    def __init__(self, x=0, y=0, width=300, height=150):
        super().__init__('textarea', x, y, width, height)
        self.properties = {
            'text': '',
            'placeholder': 'Enter text...',
            'font_size': 11,
            'font_bold': False,
            'font_italic': False,
            'font_underline': False,
            'background_color': '#FFFFFF',
            'border_color': '#999999',
            'text_color': '#000000',
            'read_only': False,
            'word_wrap': True
        }
    
    def draw(self, scene):
        # Draw background
        bg = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        bg.setBrush(QBrush(QColor(self.properties.get('background_color', '#FFFFFF'))))
        bg.setPen(QPen(QColor(self.properties.get('border_color', '#999999'))))
        scene.addItem(bg)
        
        # Draw text (simplified - just first line for preview)
        text = self.properties.get('text', '')
        if not text:
            text = self.properties.get('placeholder', '')
            text_item = QGraphicsTextItem(text[:50] + ('...' if len(text) > 50 else ''))
            text_item.setDefaultTextColor(QColor('#999999'))
        else:
            text_item = QGraphicsTextItem(text[:50] + ('...' if len(text) > 50 else ''))
            text_item.setDefaultTextColor(QColor(self.properties.get('text_color', '#000000')))
        
        font = QFont()
        font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(self.properties.get('font_size', 11))
        font.setBold(self.properties.get('font_bold', False))
        font.setItalic(self.properties.get('font_italic', False))
        font.setUnderline(self.properties.get('font_underline', False))
        text_item.setFont(font)
        text_item.setPos(self.x + 5, self.y + 5)
        scene.addItem(text_item)


class HMITextList(HMIObject):
    """Text list control for displaying a list of text items with value mapping"""
    def __init__(self, x=0, y=0, width=200, height=150):
        super().__init__('text_list', x, y, width, height)
        self.properties = {
            'items': [
                {'value': '0', 'text': '停止'},
                {'value': '1', 'text': '运行'},
                {'value': '2', 'text': '故障'},
                {'value': '3', 'text': '维护'}
            ],
            'selected_index': -1,
            'font_size': 11,
            'font_bold': False,
            'font_italic': False,
            'font_underline': False,
            'background_color': '#FFFFFF',
            'border_color': '#999999',
            'text_color': '#000000',
            'selected_color': '#2196F3',
            'hover_color': '#E3F2FD',
            'item_height': 25,
            'show_border': True,
            'read_only': False,
            'bind_mode': 'index',  # 'index' or 'value' - how to map variable to item
            'display_mode': 'list',  # 'list' or 'single' - list shows all items, single shows only matched item
            'default_text': ''  # Text to show when no item matches in single mode
        }

    def draw(self, scene):
        # Draw background
        bg = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        bg.setBrush(QBrush(QColor(self.properties.get('background_color', '#FFFFFF'))))
        if self.properties.get('show_border', True):
            bg.setPen(QPen(QColor(self.properties.get('border_color', '#999999'))))
        else:
            bg.setPen(QPen(Qt.NoPen))
        bg.setZValue(self.z_value)
        scene.addItem(bg)

        # Get display mode
        display_mode = self.properties.get('display_mode', 'list')
        items = self.properties.get('items', [])
        selected_idx = self.properties.get('selected_index', -1)
        text_color = QColor(self.properties.get('text_color', '#000000'))
        selected_color = QColor(self.properties.get('selected_color', '#2196F3'))

        font = QFont()
        font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(self.properties.get('font_size', 11))
        font.setBold(self.properties.get('font_bold', False))
        font.setItalic(self.properties.get('font_italic', False))
        font.setUnderline(self.properties.get('font_underline', False))

        if display_mode == 'single':
            # Single line display mode - show only the selected/matched item
            display_text = self.properties.get('default_text', '')
            
            # Find the text to display based on selected index
            if 0 <= selected_idx < len(items):
                item = items[selected_idx]
                if isinstance(item, dict):
                    display_text = item.get('text', '')
                else:
                    display_text = str(item)
            
            # Draw background for single mode (highlighted)
            item_bg = QGraphicsRectItem(self.x + 2, self.y + 2, self.width - 4, self.height - 4)
            item_bg.setBrush(QBrush(selected_color))
            item_bg.setPen(QPen(Qt.NoPen))
            item_bg.setZValue(self.z_value + 1)
            scene.addItem(item_bg)
            
            # Draw text centered
            text_item = QGraphicsTextItem(display_text)
            text_item.setFont(font)
            text_item.setDefaultTextColor(QColor('#FFFFFF'))
            # Center text vertically and horizontally
            text_rect = text_item.boundingRect()
            text_x = self.x + (self.width - text_rect.width()) / 2
            text_y = self.y + (self.height - text_rect.height()) / 2
            text_item.setPos(text_x, text_y)
            text_item.setZValue(self.z_value + 2)
            scene.addItem(text_item)
        else:
            # List display mode - show all items
            item_height = self.properties.get('item_height', 25)
            hover_color = QColor(self.properties.get('hover_color', '#E3F2FD'))

            y_offset = self.y + 2
            for i, item in enumerate(items):
                if y_offset + item_height > self.y + self.height:
                    break

                # Get item text (support both old format and new format)
                if isinstance(item, dict):
                    item_text = item.get('text', '')
                else:
                    item_text = str(item)

                # Draw item background if selected
                if i == selected_idx:
                    item_bg = QGraphicsRectItem(self.x + 2, y_offset, self.width - 4, item_height)
                    item_bg.setBrush(QBrush(selected_color))
                    item_bg.setPen(QPen(Qt.NoPen))
                    item_bg.setZValue(self.z_value + 1)
                    scene.addItem(item_bg)

                # Draw item text
                text_item = QGraphicsTextItem(str(item_text))
                text_item.setFont(font)
                if i == selected_idx:
                    text_item.setDefaultTextColor(QColor('#FFFFFF'))
                else:
                    text_item.setDefaultTextColor(text_color)
                text_item.setPos(self.x + 8, y_offset + 2)
                text_item.setZValue(self.z_value + 2)
                scene.addItem(text_item)

                y_offset += item_height


class HMIDesigner(QDialog):
    """HMI Designer dialog"""
    def __init__(self, data_manager=None, main_window=None):
        super().__init__()
        self.setWindowTitle("HMI设计")
        self.setGeometry(100, 100, 1400, 900)
        self.setMinimumSize(1200, 700)
        
        self.data_manager = data_manager
        self.main_window = main_window
        self.config_manager = getattr(main_window, 'config_manager', None) if main_window else None
        self.current_tool = "select"
        self.screens = []
        self.current_screen_index = -1
        self.objects = []
        self.selected_object = None
        self.selected_objects = []  # For multi-selection
        self.current_file = None
        self.show_grid = True
        self.grid_size = 10
        self.multi_select_mode = False
        
        # Rubber band selection attributes
        self.rubber_band_start = None
        self.rubber_band_end = None
        self.rubber_band_active = False
        self.rubber_band_item = None
        
        # Global resolution setting
        self.global_resolution = {'width': 1000, 'height': 600}
        
        # Undo/Redo stacks with maximum history limit
        self.max_undo_steps = 50
        self.undo_stack = []
        self.redo_stack = []
        
        # Clipboard for copy/paste
        self.clipboard = None
        self.clipboard_offset = 0
        
        # Performance optimization: Delayed refresh mechanism
        self._refresh_pending = False
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._do_delayed_refresh)
        
        # Performance optimization: Cache for graphics items
        self._graphics_items_cache = {}
        self._scene_needs_full_refresh = True
        
        # Flag to prevent property changes during panel update
        self._updating_properties_panel = False
        
        # Initialize UI after all attributes are set
        self.init_ui()
        
        # Create default screen
        if not self.screens:
            self.on_new_screen()
    
    def set_config_manager(self, config_manager):
        """Set the config manager reference"""
        self.config_manager = config_manager
        # Update variable selectors if they exist
        if hasattr(self, 'target_var_combo') and self.target_var_combo:
            self.target_var_combo.set_config_manager(config_manager)
        if hasattr(self, 'avail_var_combo') and self.avail_var_combo:
            self.avail_var_combo.set_config_manager(config_manager)
    
    def create_menu_bar(self):
        """Create the menu bar with Edit menu for copy/paste"""
        menubar = QMenuBar(self)
        
        # Edit menu
        edit_menu = menubar.addMenu('编辑')
        
        # Cut action
        cut_action = QAction('剪切', self)
        cut_action.setShortcut(QKeySequence.Cut)
        cut_action.triggered.connect(self.cut_selected_object)
        edit_menu.addAction(cut_action)
        
        # Copy action
        copy_action = QAction('复制', self)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self.copy_selected_object)
        edit_menu.addAction(copy_action)
        
        # Paste action
        paste_action = QAction('粘贴', self)
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.triggered.connect(self.paste_object)
        edit_menu.addAction(paste_action)
        
        edit_menu.addSeparator()
        
        # Duplicate action
        duplicate_action = QAction('Duplicate', self)
        duplicate_action.setShortcut('Ctrl+D')
        duplicate_action.triggered.connect(self.duplicate_selected_object)
        edit_menu.addAction(duplicate_action)
        
        # Delete action
        delete_action = QAction('删除', self)
        delete_action.setShortcut(QKeySequence.Delete)
        delete_action.triggered.connect(self.delete_selected_object)
        edit_menu.addAction(delete_action)
        
        edit_menu.addSeparator()
        
        # Undo/Redo actions
        undo_action = QAction('撤销', self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self.undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction('重做', self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.triggered.connect(self.redo)
        edit_menu.addAction(redo_action)
        
        # View menu
        view_menu = menubar.addMenu('视图')
        
        # Toggle grid action
        grid_action = QAction('显示网格', self)
        grid_action.setCheckable(True)
        grid_action.setChecked(True)
        grid_action.triggered.connect(self.toggle_grid)
        view_menu.addAction(grid_action)
        
        # Resolution settings
        resolution_menu = view_menu.addMenu('画面分辨率')
        
        # Standard resolutions
        standard_resolutions = [
            ("800x600", 800, 600),
            ("1024x768", 1024, 768),
            ("1280x720", 1280, 720),
            ("1366x768", 1366, 768),
            ("1440x900", 1440, 900),
            ("1920x1080", 1920, 1080)
        ]
        
        for name, width, height in standard_resolutions:
            resolution_action = QAction(name, self)
            resolution_action.triggered.connect(lambda checked, w=width, h=height: self.set_global_resolution(w, h))
            resolution_menu.addAction(resolution_action)
        
        # Custom resolution
        custom_action = QAction('自定义分辨率...', self)
        custom_action.triggered.connect(self.show_custom_resolution_dialog)
        resolution_menu.addAction(custom_action)
        
        # Layout menu
        layout_menu = menubar.addMenu('布局')
        
        align_menu = layout_menu.addMenu('对齐')
        
        align_left_action = QAction('左对齐', self)
        align_left_action.triggered.connect(lambda: self.align_selected('left'))
        align_menu.addAction(align_left_action)
        
        align_center_action = QAction('水平居中', self)
        align_center_action.triggered.connect(lambda: self.align_selected('center'))
        align_menu.addAction(align_center_action)
        
        align_right_action = QAction('右对齐', self)
        align_right_action.triggered.connect(lambda: self.align_selected('right'))
        align_menu.addAction(align_right_action)
        
        align_menu.addSeparator()
        
        align_top_action = QAction('顶部对齐', self)
        align_top_action.triggered.connect(lambda: self.align_selected('top'))
        align_menu.addAction(align_top_action)
        
        align_middle_action = QAction('垂直居中', self)
        align_middle_action.triggered.connect(lambda: self.align_selected('middle'))
        align_menu.addAction(align_middle_action)
        
        align_bottom_action = QAction('底部对齐', self)
        align_bottom_action.triggered.connect(lambda: self.align_selected('bottom'))
        align_menu.addAction(align_bottom_action)
        
        align_menu.addSeparator()
        
        # 均布功能
        distribute_h_action = QAction('水平均布', self)
        distribute_h_action.triggered.connect(lambda: self.distribute_selected('horizontal'))
        align_menu.addAction(distribute_h_action)
        
        distribute_v_action = QAction('垂直均布', self)
        distribute_v_action.triggered.connect(lambda: self.distribute_selected('vertical'))
        align_menu.addAction(distribute_v_action)
    
    def toggle_grid(self):
        """Toggle grid display"""
        self.show_grid = not self.show_grid
        self.refresh_screen_display()
    
    def set_global_resolution(self, width, height):
        """Set global screen resolution for all screens"""
        # Update global resolution
        self.global_resolution = {'width': width, 'height': height}
        
        # Update all screens (create a copy for each screen to avoid shared reference)
        for screen in self.screens:
            if hasattr(screen, 'resolution'):
                screen.resolution = self.global_resolution.copy()
        
        # Update current scene
        self.scene.setSceneRect(0, 0, width, height)
        self.refresh_screen_display()
        
        print(f"Global resolution set to {width}x{height}")
    
    def show_custom_resolution_dialog(self):
        """Show custom resolution dialog"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("自定义画面分辨率")
        
        layout = QVBoxLayout()
        
        # Width setting
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("宽度:"))
        width_spin = QSpinBox()
        width_spin.setRange(640, 2560)
        width_spin.setValue(self.global_resolution.get('width', 1000) if hasattr(self, 'global_resolution') else 1000)
        width_layout.addWidget(width_spin)
        layout.addLayout(width_layout)
        
        # Height setting
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("高度:"))
        height_spin = QSpinBox()
        height_spin.setRange(480, 1440)
        height_spin.setValue(self.global_resolution.get('height', 600) if hasattr(self, 'global_resolution') else 600)
        height_layout.addWidget(height_spin)
        layout.addLayout(height_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(lambda: (self.set_global_resolution(width_spin.value(), height_spin.value()), dialog.accept()))
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def create_toolbar(self):
        """Create the toolbar with quick access buttons"""
        from PyQt5.QtWidgets import QToolBar, QButtonGroup, QToolButton
        from PyQt5.QtGui import QIcon
        from PyQt5.QtCore import QSize
        
        toolbar = QToolBar('Main Toolbar', self)
        toolbar.setMovable(False)
        
        # Get icons directory
        import os
        icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources', 'icons')
        
        # === Alignment Tools ===
        toolbar.addWidget(QLabel("对齐: "))
        
        align_buttons = [
            ("align_left.png", "left", "左对齐"),
            ("align_center.png", "center", "水平居中"),
            ("align_right.png", "right", "右对齐"),
            ("align_top.png", "top", "顶部对齐"),
            ("align_middle.png", "middle", "垂直居中"),
            ("align_bottom.png", "bottom", "底部对齐")
        ]
        for icon_file, align_type, tooltip in align_buttons:
            btn = QToolButton()
            btn.setFixedSize(28, 28)
            btn.setToolTip(tooltip)
            icon_path = os.path.join(icons_dir, icon_file)
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(20, 20))
            btn.clicked.connect(lambda checked, t=align_type: self.align_selected(t))
            toolbar.addWidget(btn)
        
        toolbar.addSeparator()
        
        # === Distribute Tools ===
        toolbar.addWidget(QLabel("均布: "))
        
        btn_distribute_h = QToolButton()
        btn_distribute_h.setFixedSize(28, 28)
        btn_distribute_h.setToolTip("水平均布")
        icon_path = os.path.join(icons_dir, "distribute_h.png")
        if os.path.exists(icon_path):
            btn_distribute_h.setIcon(QIcon(icon_path))
            btn_distribute_h.setIconSize(QSize(20, 20))
        btn_distribute_h.clicked.connect(lambda: self.distribute_selected('horizontal'))
        toolbar.addWidget(btn_distribute_h)
        
        btn_distribute_v = QToolButton()
        btn_distribute_v.setFixedSize(28, 28)
        btn_distribute_v.setToolTip("垂直均布")
        icon_path = os.path.join(icons_dir, "distribute_v.png")
        if os.path.exists(icon_path):
            btn_distribute_v.setIcon(QIcon(icon_path))
            btn_distribute_v.setIconSize(QSize(20, 20))
        btn_distribute_v.clicked.connect(lambda: self.distribute_selected('vertical'))
        toolbar.addWidget(btn_distribute_v)
        
        toolbar.addSeparator()
        
        # === Layer Management ===
        toolbar.addWidget(QLabel("图层: "))
        
        btn_bring_front = QPushButton("置顶")
        btn_bring_front.setFixedSize(40, 24)
        btn_bring_front.clicked.connect(self.bring_to_front)
        toolbar.addWidget(btn_bring_front)
        
        btn_send_back = QPushButton("置底")
        btn_send_back.setFixedSize(40, 24)
        btn_send_back.clicked.connect(self.send_to_back)
        toolbar.addWidget(btn_send_back)
        
        btn_raise = QPushButton("上移")
        btn_raise.setFixedSize(40, 24)
        btn_raise.clicked.connect(self.raise_object)
        toolbar.addWidget(btn_raise)
        
        btn_lower = QPushButton("下移")
        btn_lower.setFixedSize(40, 24)
        btn_lower.clicked.connect(self.lower_object)
        toolbar.addWidget(btn_lower)
        
        toolbar.addSeparator()
        
        # === Undo/Redo ===
        btn_undo = QPushButton("撤销")
        btn_undo.setFixedSize(40, 24)
        btn_undo.setShortcut("Ctrl+Z")
        btn_undo.clicked.connect(self.undo)
        toolbar.addWidget(btn_undo)
        
        btn_redo = QPushButton("重做")
        btn_redo.setFixedSize(40, 24)
        btn_redo.setShortcut("Ctrl+Y")
        btn_redo.clicked.connect(self.redo)
        toolbar.addWidget(btn_redo)
        
        return toolbar
    
    def init_ui(self):
        """Initialize the UI"""
        main_layout = QVBoxLayout()
        
        # Add toolbar
        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)
        
        # Create main splitter for resizable panels
        
        # Horizontal splitter for left, center, and right panels
        h_splitter = QSplitter(Qt.Horizontal)
        
        # Left panel: Screens management and alignment tools
        left_panel = self.create_left_panel()
        h_splitter.addWidget(left_panel)
        
        # Central area with graphics view
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 1000, 600)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.NoDrag)
        # Enable scroll bars for large scenes
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.view.mousePressEvent = self.on_canvas_click
        self.view.mouseMoveEvent = self.on_canvas_mouse_move
        self.view.mouseReleaseEvent = self.on_canvas_mouse_release
        self.view.mouseDoubleClickEvent = self.on_canvas_double_click
        self.view.wheelEvent = self.on_canvas_wheel
        self.view.keyPressEvent = self.on_key_press
        self.view.setFocusPolicy(Qt.StrongFocus)
        
        # Zoom state
        self.current_zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        
        # Drag and resize state
        self.dragging = False
        self.resizing = False
        self.drag_start_pos = None
        self.drag_start_obj_pos = None
        self.resize_handle = None
        self.resize_start_rect = None
        
        # Line endpoint dragging state
        self.dragging_line_endpoint = None  # None, 'start', or 'end'
        self.line_start_pos = None  # Store initial line endpoints
        
        # Add grid
        self.draw_grid()
        
        # Create vertical splitter for center canvas and properties panel
        center_v_splitter = QSplitter(Qt.Vertical)
        center_v_splitter.setHandleWidth(5)
        
        # Add canvas to center vertical splitter
        center_v_splitter.addWidget(self.view)
        
        # Bottom panel: Properties panel
        self.props_panel = self.create_properties_panel()
        center_v_splitter.addWidget(self.props_panel)
        
        h_splitter.addWidget(center_v_splitter)
        h_splitter.setStretchFactor(1, 1)
        
        # Right panel: Control buttons
        right_panel = self.create_right_panel()
        h_splitter.addWidget(right_panel)
        
        main_layout.addWidget(h_splitter, 4)
        
        self.setLayout(main_layout)
        
        # Initially hide property content since no object is selected
        self._hide_all_property_content()
    
    def create_left_panel(self):
        """Create the left panel with screen management and alignment tools"""
        frame = QFrame()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scroll area for left panel content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Create container widget for scroll area
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        
        # Screen management section
        screens_group = QGroupBox("画面管理")
        screens_layout = QVBoxLayout()
        
        # Screen list
        self.screen_list = QListWidget()
        self.screen_list.currentRowChanged.connect(self.switch_screen)
        self.screen_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.screen_list.customContextMenuRequested.connect(self.show_screen_context_menu)
        screens_layout.addWidget(self.screen_list)
        
        # New screen controls
        new_screen_layout = QHBoxLayout()
        self.new_screen_name = QLineEdit()
        self.new_screen_name.setPlaceholderText("画面名称")
        # 阻止回车键触发按钮
        self.new_screen_name.returnPressed.connect(lambda: None)
        new_screen_layout.addWidget(self.new_screen_name)
        
        btn_new_screen = QPushButton("新建")
        btn_new_screen.setDefault(False)
        btn_new_screen.setFocusPolicy(Qt.NoFocus)
        btn_new_screen.clicked.connect(self.on_new_screen)
        new_screen_layout.addWidget(btn_new_screen)
        screens_layout.addLayout(new_screen_layout)
        

        
        screens_group.setLayout(screens_layout)
        scroll_layout.addWidget(screens_group)
        
        # Grid toggle
        self.grid_checkbox = QCheckBox("显示网格")
        self.grid_checkbox.setChecked(self.show_grid)
        self.grid_checkbox.stateChanged.connect(self.toggle_grid)
        scroll_layout.addWidget(self.grid_checkbox)
        
        scroll_layout.addStretch()
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        frame.setLayout(layout)
        return frame
    
    def create_tool_button(self, text, tooltip, tool_name, color="#4CAF50"):
        """Create a square tool button with icon-like appearance"""
        btn = QPushButton(text)
        btn.setFixedSize(40, 40)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: black;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                font-family: "Microsoft YaHei", "微软雅黑";
            }}
            QPushButton:hover {{
                background-color: {color}DD;
            }}
            QPushButton:pressed {{
                background-color: {color}AA;
            }}
        """)
        btn.clicked.connect(lambda: self.set_tool(tool_name))
        return btn
    
    def create_right_panel(self):
        """Create the right panel with icon buttons"""
        from PyQt5.QtWidgets import QGridLayout, QScrollArea
        
        frame = QFrame()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        title_label = QLabel("控件工具")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
        # Create scroll area for tools
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumHeight(400)
        
        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)
        tools_layout.setSpacing(15)
        
        # Basic controls section
        basic_label = QLabel("基础控件")
        basic_label.setStyleSheet("font-weight: bold; color: #333;")
        tools_layout.addWidget(basic_label)
        
        basic_grid = QGridLayout()
        basic_grid.setSpacing(5)
        basic_controls = [
            ("按钮", "按钮", "button", "#4CAF50"),
            ("标签", "标签", "label", "#2196F3"),
            ("仪表", "仪表", "gauge", "#FF9800"),
            ("开关", "开关", "switch", "#9C27B0"),
            ("灯", "指示灯", "light", "#F44336"),
            ("图片", "图片", "picture", "#795548"),
            ("图列", "图形列表", "picture_list", "#8BC34A"),
        ]
        for i, (text, tooltip, tool, color) in enumerate(basic_controls):
            btn = self.create_tool_button(text, tooltip, tool, color)
            basic_grid.addWidget(btn, i // 3, i % 3)
        tools_layout.addLayout(basic_grid)
        
        # Display controls section
        display_label = QLabel("显示控件")
        display_label.setStyleSheet("font-weight: bold; color: #333; margin-top: 5px;")
        tools_layout.addWidget(display_label)
        
        display_grid = QGridLayout()
        display_grid.setSpacing(5)
        display_controls = [
            ("趋势", "趋势图", "trend_chart", "#607D8B"),
            ("历史", "历史趋势图", "history_trend", "#455A64"),
            ("表格", "数据表", "table_view", "#607D8B"),
            ("进度", "进度条", "progress", "#009688"),
            ("报警", "报警", "alarm_display", "#E91E63"),
            ("时钟", "时钟", "clock", "#9C27B0"),
        ]
        for i, (text, tooltip, tool, color) in enumerate(display_controls):
            btn = self.create_tool_button(text, tooltip, tool, color)
            display_grid.addWidget(btn, i // 3, i % 3)
        tools_layout.addLayout(display_grid)
        
        # Input controls section
        input_label = QLabel("输入控件")
        input_label.setStyleSheet("font-weight: bold; color: #333; margin-top: 5px;")
        tools_layout.addWidget(input_label)
        
        input_grid = QGridLayout()
        input_grid.setSpacing(5)
        input_controls = [
            ("输入", "输入框", "input", "#FFC107"),
            ("复选", "复选框", "checkbox", "#FF5722"),
            ("下拉", "下拉框", "dropdown", "#FF9800"),
            ("文本", "文本域", "textarea", "#795548"),
            ("列表", "文本列表", "text_list", "#00BCD4"),
        ]
        for i, (text, tooltip, tool, color) in enumerate(input_controls):
            btn = self.create_tool_button(text, tooltip, tool, color)
            input_grid.addWidget(btn, i // 3, i % 3)
        tools_layout.addLayout(input_grid)
        
        # Graphics tools section
        graphics_label = QLabel("图形工具")
        graphics_label.setStyleSheet("font-weight: bold; color: #333; margin-top: 5px;")
        tools_layout.addWidget(graphics_label)
        
        graphics_grid = QGridLayout()
        graphics_grid.setSpacing(5)
        graphics_controls = [
            ("直线", "直线", "line", "#9E9E9E"),
            ("矩形", "矩形", "rectangle", "#9E9E9E"),
            ("圆形", "圆形", "circle", "#9E9E9E"),
        ]
        for i, (text, tooltip, tool, color) in enumerate(graphics_controls):
            btn = self.create_tool_button(text, tooltip, tool, color)
            graphics_grid.addWidget(btn, i // 3, i % 3)
        tools_layout.addLayout(graphics_grid)
        
        tools_layout.addStretch()
        scroll.setWidget(tools_widget)
        layout.addWidget(scroll)
        
        layout.addStretch()
        
        frame.setLayout(layout)
        return frame
    
    def update_status_bar(self):
        """Update the status bar with selected object information and zoom level"""
        if not self.main_window or not hasattr(self.main_window, 'status_bar'):
            return
        
        # Build status text parts
        parts = []
        
        # Add zoom level
        zoom_percent = int(self.current_zoom * 100)
        parts.append(f"缩放: {zoom_percent}%")
        
        # Add object info if selected
        if self.selected_object:
            obj_type = self.selected_object.obj_type
            obj_name = self.selected_object.properties.get('text', obj_type)
            x = self.selected_object.x
            y = self.selected_object.y
            width = self.selected_object.width
            height = self.selected_object.height
            parts.append(f"已选择: {obj_type} ({obj_name}) - 位置: ({x}, {y}) - 大小: {width}x{height}")
        else:
            parts.append("未选择对象")
        
        status_text = " | ".join(parts)
        self.main_window.status_bar.showMessage(status_text)
    
    def create_properties_panel(self):
        """Create the properties panel with WinCC-style layout"""
        frame = QFrame()
        layout = QVBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Tab widget for organizing properties
        self.props_tab_widget = QTabWidget()
        
        # Tab 1: Basic Properties - With resizable splitter layout
        basic_tab = QWidget()
        basic_main_layout = QVBoxLayout()
        basic_main_layout.setSpacing(5)
        basic_main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create vertical splitter for basic properties
        self.basic_splitter = QSplitter(Qt.Vertical)
        
        # Create common properties (position, size, text, font)
        self._create_common_properties_with_splitter()
        
        # Create control-specific property groups
        self._create_control_specific_properties_with_splitter()
        
        # Set stretch factors for splitter - all groups at top with no extra stretch
        for i in range(self.basic_splitter.count()):
            self.basic_splitter.setStretchFactor(i, 0)
        
        basic_main_layout.addWidget(self.basic_splitter)
        basic_main_layout.setAlignment(Qt.AlignTop)
        basic_tab.setLayout(basic_main_layout)
        self.props_tab_widget.addTab(basic_tab, "基本属性")
        
        # Tab 2: Variable Binding - With resizable splitter layout
        var_tab = QWidget()
        var_main_layout = QVBoxLayout()
        var_main_layout.setSpacing(5)
        var_main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create horizontal splitter for variable binding
        self.var_splitter = QSplitter(Qt.Horizontal)
        
        # Variable binding - simplified single variable selection
        var_bind_group = QGroupBox("变量绑定")
        var_bind_layout = QHBoxLayout()
        var_bind_layout.setSpacing(5)
        var_bind_layout.setContentsMargins(5, 5, 5, 5)
        
        var_bind_layout.addWidget(QLabel("绑定变量:"))
        self.avail_var_combo = SmartVariableComboBox(self, self.data_manager, self.config_manager)
        self.avail_var_combo.setMinimumWidth(200)
        self.avail_var_combo.variableSelected.connect(self.on_variable_binding_change)
        var_bind_layout.addWidget(self.avail_var_combo)
        
        self.clear_var_btn = QPushButton("清除")
        self.clear_var_btn.setFixedWidth(50)
        self.clear_var_btn.clicked.connect(self.clear_variable_binding)
        var_bind_layout.addWidget(self.clear_var_btn)
        
        var_bind_layout.addStretch()
        var_bind_group.setLayout(var_bind_layout)
        var_main_layout.addWidget(var_bind_group)
        
        # Bound variable info display
        self.var_info_group = QGroupBox("变量信息")
        var_info_layout = QFormLayout()
        var_info_layout.setSpacing(5)
        var_info_layout.setContentsMargins(5, 5, 5, 5)
        
        self.var_name_label = QLabel("-")
        self.var_type_label = QLabel("-")
        self.var_addr_label = QLabel("-")
        var_info_layout.addRow("变量名:", self.var_name_label)
        var_info_layout.addRow("类型:", self.var_type_label)
        var_info_layout.addRow("地址:", self.var_addr_label)
        
        # Bit offset for accessing individual bits
        bit_offset_layout = QHBoxLayout()
        self.bit_offset_spin = QSpinBox()
        self.bit_offset_spin.setRange(-1, 31)
        self.bit_offset_spin.setValue(-1)
        self.bit_offset_spin.setSpecialValueText("无")
        self.bit_offset_spin.setToolTip("设置位偏移以访问变量的某一位 (-1=无, 0-31=位位置)")
        self.bit_offset_spin.valueChanged.connect(self.on_bit_offset_changed)
        bit_offset_layout.addWidget(self.bit_offset_spin)
        bit_offset_layout.addStretch()
        var_info_layout.addRow("位偏移:", bit_offset_layout)
        
        self.var_info_group.setLayout(var_info_layout)
        var_main_layout.addWidget(self.var_info_group)
        
        var_main_layout.addStretch()
        var_tab.setLayout(var_main_layout)
        self.props_tab_widget.addTab(var_tab, "变量绑定")
        
        # Tab 3: Animation/Visibility Control
        anim_tab = QWidget()
        anim_main_layout = QVBoxLayout()
        anim_main_layout.setSpacing(5)
        anim_main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Visibility control group
        self.visibility_group = QGroupBox("可见性控制")
        visibility_layout = QVBoxLayout()
        visibility_layout.setSpacing(5)
        visibility_layout.setContentsMargins(5, 5, 5, 5)
        
        # Control variable selection
        var_row = QHBoxLayout()
        var_row.addWidget(QLabel("控制变量:"))
        self.visibility_var_combo = SmartVariableComboBox(self, self.data_manager, self.config_manager)
        self.visibility_var_combo.setMinimumWidth(200)
        self.visibility_var_combo.variableSelected.connect(self.on_visibility_variable_change)
        var_row.addWidget(self.visibility_var_combo)
        
        self.clear_visibility_var_btn = QPushButton("清除")
        self.clear_visibility_var_btn.setFixedWidth(50)
        self.clear_visibility_var_btn.clicked.connect(self.clear_visibility_variable)
        var_row.addWidget(self.clear_visibility_var_btn)
        var_row.addStretch()
        visibility_layout.addLayout(var_row)
        
        # Bit offset for visibility control variable
        bit_row = QHBoxLayout()
        bit_row.addWidget(QLabel("位偏移:"))
        self.visibility_bit_offset_spin = QSpinBox()
        self.visibility_bit_offset_spin.setRange(-1, 31)
        self.visibility_bit_offset_spin.setValue(-1)
        self.visibility_bit_offset_spin.setSpecialValueText("无")
        self.visibility_bit_offset_spin.setToolTip("设置位偏移以访问变量的某一位 (-1=无, 0-31=位位置)")
        self.visibility_bit_offset_spin.valueChanged.connect(self.on_visibility_bit_offset_change)
        bit_row.addWidget(self.visibility_bit_offset_spin)
        bit_row.addStretch()
        visibility_layout.addLayout(bit_row)
        
        # Condition selection
        cond_row = QHBoxLayout()
        cond_row.addWidget(QLabel("条件:"))
        self.visibility_condition_combo = QComboBox()
        self.visibility_condition_combo.addItems([
            "等于", "不等于", "大于", "小于", "大于等于", "小于等于", "非零", "为零"
        ])
        self.visibility_condition_combo.currentTextChanged.connect(self.on_visibility_settings_change)
        cond_row.addWidget(self.visibility_condition_combo)
        
        cond_row.addWidget(QLabel("比较值:"))
        self.visibility_compare_edit = QLineEdit()
        self.visibility_compare_edit.setPlaceholderText("比较值")
        self.visibility_compare_edit.setMaximumWidth(100)
        self.visibility_compare_edit.textChanged.connect(self.on_visibility_settings_change)
        cond_row.addWidget(self.visibility_compare_edit)
        cond_row.addStretch()
        visibility_layout.addLayout(cond_row)
        
        # Show/Hide behavior - Radio buttons
        behavior_row = QHBoxLayout()
        behavior_row.addWidget(QLabel("行为:"))
        self.show_when_true_radio = QRadioButton("条件满足时显示")
        self.show_when_true_radio.setChecked(True)
        self.show_when_true_radio.toggled.connect(self.on_visibility_settings_change)
        behavior_row.addWidget(self.show_when_true_radio)
        
        self.hide_when_true_radio = QRadioButton("条件满足时隐藏")
        self.hide_when_true_radio.toggled.connect(self.on_visibility_settings_change)
        behavior_row.addWidget(self.hide_when_true_radio)
        behavior_row.addStretch()
        visibility_layout.addLayout(behavior_row)
        
        self.visibility_group.setLayout(visibility_layout)
        anim_main_layout.addWidget(self.visibility_group)
        
        # Visibility status display
        self.visibility_status_group = QGroupBox("可见性状态")
        status_layout = QFormLayout()
        status_layout.setSpacing(5)
        status_layout.setContentsMargins(5, 5, 5, 5)
        
        self.visibility_status_label = QLabel("始终可见")
        self.visibility_status_label.setStyleSheet("font-weight: bold;")
        status_layout.addRow("当前状态:", self.visibility_status_label)
        
        self.visibility_status_group.setLayout(status_layout)
        anim_main_layout.addWidget(self.visibility_status_group)
        
        anim_main_layout.addStretch()
        anim_tab.setLayout(anim_main_layout)
        self.props_tab_widget.addTab(anim_tab, "动画")
        
        # Tab 4: Advanced Properties - With resizable splitter layout
        adv_tab = QWidget()
        adv_main_layout = QVBoxLayout()
        adv_main_layout.setSpacing(5)
        adv_main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create vertical splitter for advanced properties
        self.adv_splitter = QSplitter(Qt.Vertical)
        
        # Create advanced property groups
        self._create_advanced_properties_with_splitter()
        
        # Set stretch factors for splitter - all groups at top with no extra stretch
        for i in range(self.adv_splitter.count()):
            self.adv_splitter.setStretchFactor(i, 0)
        
        adv_main_layout.addWidget(self.adv_splitter)
        adv_main_layout.setAlignment(Qt.AlignTop)
        adv_tab.setLayout(adv_main_layout)
        self.props_tab_widget.addTab(adv_tab, "高级属性")
        
        # Add tab widget to scroll area for scrolling support
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.props_tab_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Add scroll area to main layout
        layout.addWidget(scroll_area)
        
        frame.setLayout(layout)
        return frame
    
    def _create_common_properties_with_splitter(self):
        """Create common properties with resizable splitter layout"""
        # === Group 1: Position and Size ===
        pos_size_group = QGroupBox("位置和大小")
        pos_size_layout = QHBoxLayout()
        pos_size_layout.setSpacing(2)
        pos_size_layout.setContentsMargins(3, 2, 3, 2)
        
        # X, Y, W, H in one row
        pos_size_layout.addWidget(QLabel("X:"))
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 5000)
        self.x_spin.setFixedWidth(50)
        self.x_spin.valueChanged.connect(self.on_position_change)
        pos_size_layout.addWidget(self.x_spin)
        
        pos_size_layout.addWidget(QLabel("Y:"))
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 5000)
        self.y_spin.setFixedWidth(50)
        self.y_spin.valueChanged.connect(self.on_position_change)
        pos_size_layout.addWidget(self.y_spin)
        
        pos_size_layout.addWidget(QLabel("W:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(10, 5000)
        self.width_spin.setFixedWidth(50)
        self.width_spin.valueChanged.connect(self.on_size_change)
        pos_size_layout.addWidget(self.width_spin)
        
        pos_size_layout.addWidget(QLabel("H:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(10, 5000)
        self.height_spin.setFixedWidth(50)
        self.height_spin.valueChanged.connect(self.on_size_change)
        pos_size_layout.addWidget(self.height_spin)
        
        pos_size_layout.addStretch()
        pos_size_group.setLayout(pos_size_layout)
        pos_size_group.setMaximumHeight(60)
        self.basic_splitter.addWidget(pos_size_group)
        
        # === Group 2: Text Content ===
        self.text_group = QGroupBox("文本内容")
        text_layout = QHBoxLayout()
        text_layout.setSpacing(5)
        text_layout.setContentsMargins(5, 5, 5, 5)
        
        self.text_edit = QLineEdit()
        self.text_edit.editingFinished.connect(self.on_property_change)
        text_layout.addWidget(self.text_edit)
        
        self.border_checkbox = QCheckBox("边框")
        self.border_checkbox.stateChanged.connect(self.on_property_change)
        text_layout.addWidget(self.border_checkbox)
        
        text_layout.addWidget(QLabel("背景:"))
        self.label_bg_color_button = QPushButton("选择")
        self.label_bg_color_button.setFixedWidth(50)
        self.label_bg_color_button.clicked.connect(self.choose_label_background_color)
        text_layout.addWidget(self.label_bg_color_button)
        
        text_layout.addWidget(QLabel("水平:"))
        self.text_h_align_combo = QComboBox()
        self.text_h_align_combo.addItems(["左对齐", "居中", "右对齐"])
        self.text_h_align_combo.setFixedWidth(70)
        self.text_h_align_combo.currentTextChanged.connect(self.on_property_change)
        text_layout.addWidget(self.text_h_align_combo)
        
        text_layout.addWidget(QLabel("垂直:"))
        self.text_v_align_combo = QComboBox()
        self.text_v_align_combo.addItems(["顶部", "居中", "底部"])
        self.text_v_align_combo.setFixedWidth(70)
        self.text_v_align_combo.currentTextChanged.connect(self.on_property_change)
        text_layout.addWidget(self.text_v_align_combo)
        
        text_layout.addStretch()
        self.text_group.setLayout(text_layout)
        self.text_group.setMaximumHeight(60)
        self.basic_splitter.addWidget(self.text_group)
        
        # === Group 3: Font Settings ===
        font_group = QGroupBox("字体设置")
        font_layout = QHBoxLayout()
        font_layout.setSpacing(2)
        font_layout.setContentsMargins(3, 2, 3, 2)
        
        font_layout.addWidget(QLabel("字体:"))
        self.font_family_combo = QComboBox()
        self.font_family_combo.setFixedWidth(200)
        self.font_family_combo.currentTextChanged.connect(self.on_property_change)
        from PyQt5.QtGui import QFontDatabase
        font_db = QFontDatabase()
        self.font_family_combo.addItems(font_db.families())
        font_layout.addWidget(self.font_family_combo)
        
        font_layout.addWidget(QLabel("大小:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setFixedWidth(60)
        self.font_size_spin.valueChanged.connect(self.on_property_change)
        font_layout.addWidget(self.font_size_spin)
        
        font_layout.addSpacing(10)
        
        self.font_bold_checkbox = QCheckBox("粗体")
        self.font_bold_checkbox.stateChanged.connect(self.on_property_change)
        font_layout.addWidget(self.font_bold_checkbox)
        
        self.font_italic_checkbox = QCheckBox("斜体")
        self.font_italic_checkbox.stateChanged.connect(self.on_property_change)
        font_layout.addWidget(self.font_italic_checkbox)
        
        self.font_underline_checkbox = QCheckBox("下划线")
        self.font_underline_checkbox.stateChanged.connect(self.on_property_change)
        font_layout.addWidget(self.font_underline_checkbox)
        
        font_layout.addSpacing(10)
        
        font_layout.addWidget(QLabel("颜色:"))
        self.text_color_button = QPushButton("选择")
        self.text_color_button.setFixedWidth(60)
        self.text_color_button.clicked.connect(self.choose_text_color)
        font_layout.addWidget(self.text_color_button)
        
        font_layout.addStretch()
        font_group.setLayout(font_layout)
        font_group.setMaximumHeight(60)
        self.basic_splitter.addWidget(font_group)
    
    def _create_control_specific_properties_with_splitter(self):
        """Create control-specific property groups with resizable splitter layout"""
        # === Group 4: Action Settings (merged variable operation and screen navigation) ===
        self.var_op_group = QGroupBox("动作设置")
        var_op_layout = QHBoxLayout()
        var_op_layout.setSpacing(2)
        var_op_layout.setContentsMargins(2, 2 , 2, 2)
        
        var_op_layout.addWidget(QLabel("动作:"))
        self.var_operation_combo = QComboBox()
        self.var_operation_combo.addItems(["无", "置位", "复位", "取反", "置1", "置0", "加1", "减1", "点动", "画面跳转"])
        self.var_operation_combo.currentTextChanged.connect(self.on_action_type_change)
        self.var_operation_combo.setFixedWidth(80)
        var_op_layout.addWidget(self.var_operation_combo)
        
        # Screen navigation widgets (shown when "画面跳转" is selected)
        self.screen_nav_label = QLabel("画面:")
        var_op_layout.addWidget(self.screen_nav_label)
        
        self.target_screen_combo = QComboBox()
        self.target_screen_combo.setEditable(True)
        self.target_screen_combo.setFixedWidth(100)
        self.target_screen_combo.currentTextChanged.connect(self.on_property_change)
        var_op_layout.addWidget(self.target_screen_combo)
        
        self.screen_num_label = QLabel("编号:")
        var_op_layout.addWidget(self.screen_num_label)
        
        self.target_screen_number_spin = QSpinBox()
        self.target_screen_number_spin.setRange(0, 999)
        self.target_screen_number_spin.setFixedWidth(50)
        self.target_screen_number_spin.valueChanged.connect(self.on_property_change)
        var_op_layout.addWidget(self.target_screen_number_spin)
        
        refresh_screen_btn = QPushButton("⟳")
        refresh_screen_btn.setFixedSize(20, 20)
        refresh_screen_btn.setToolTip("刷新画面")
        refresh_screen_btn.clicked.connect(self.refresh_target_screens)
        var_op_layout.addWidget(refresh_screen_btn)
        
        var_op_layout.addStretch()
        self.var_op_group.setLayout(var_op_layout)
        self.var_op_group.setMaximumHeight(60)
        self.basic_splitter.addWidget(self.var_op_group)
        
        # Store reference to screen navigation widgets for showing/hiding
        self.screen_nav_widgets = [
            self.screen_nav_label, self.target_screen_combo,
            self.screen_num_label, self.target_screen_number_spin, refresh_screen_btn
        ]
        
        # Variable selection widgets (shown when variable operation is selected)
        # Note: Variable binding is now handled by variables[0] in variable binding tab
        self.var_op_widgets = []
        
        # === Group 7: Switch Text Settings ===
        self.switch_text_group = QGroupBox("开关文本")
        switch_text_layout = QHBoxLayout()
        switch_text_layout.setSpacing(5)
        switch_text_layout.setContentsMargins(5, 5, 5, 5)
        
        switch_text_layout.addWidget(QLabel("开启:"))
        self.switch_on_text_edit = QLineEdit()
        self.switch_on_text_edit.setFixedWidth(80)
        self.switch_on_text_edit.editingFinished.connect(self.on_property_change)
        switch_text_layout.addWidget(self.switch_on_text_edit)
        
        switch_text_layout.addWidget(QLabel("关闭:"))
        self.switch_off_text_edit = QLineEdit()
        self.switch_off_text_edit.setFixedWidth(80)
        self.switch_off_text_edit.editingFinished.connect(self.on_property_change)
        switch_text_layout.addWidget(self.switch_off_text_edit)
        
        switch_text_layout.addWidget(QLabel("颜色:"))
        self.switch_text_color_button = QPushButton("选择")
        self.switch_text_color_button.setFixedWidth(50)
        self.switch_text_color_button.clicked.connect(self.choose_switch_text_color)
        switch_text_layout.addWidget(self.switch_text_color_button)
        
        switch_text_layout.addStretch()
        self.switch_text_group.setLayout(switch_text_layout)
        self.switch_text_group.setMaximumHeight(60)
        self.basic_splitter.addWidget(self.switch_text_group)
        
        # === Group 8: Range Settings ===
        self.range_group = QGroupBox("数值范围")
        range_layout = QHBoxLayout()
        range_layout.setSpacing(2)
        range_layout.setContentsMargins(3, 2, 3, 2)
        
        range_layout.addWidget(QLabel("最小:"))
        self.min_val_spin = QSpinBox()
        self.min_val_spin.setRange(-999999, 999999)
        self.min_val_spin.setFixedWidth(60)
        self.min_val_spin.valueChanged.connect(self.on_property_change)
        range_layout.addWidget(self.min_val_spin)
        
        range_layout.addWidget(QLabel("最大:"))
        self.max_val_spin = QSpinBox()
        self.max_val_spin.setRange(-999999, 999999)
        self.max_val_spin.setFixedWidth(60)
        self.max_val_spin.valueChanged.connect(self.on_property_change)
        range_layout.addWidget(self.max_val_spin)
        
        range_layout.addWidget(QLabel("默认:"))
        self.default_val_spin = QSpinBox()
        self.default_val_spin.setRange(-999999, 999999)
        self.default_val_spin.setFixedWidth(60)
        self.default_val_spin.valueChanged.connect(self.on_property_change)
        range_layout.addWidget(self.default_val_spin)
        
        range_layout.addStretch()
        self.range_group.setLayout(range_layout)
        self.range_group.setMaximumHeight(60)
        self.basic_splitter.addWidget(self.range_group)
        
        # === Group 9: Checkbox/Radio Values ===
        self.checkbox_group = QGroupBox("选项值")
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setSpacing(2)
        checkbox_layout.setContentsMargins(3, 2, 3, 2)
        
        checkbox_layout.addWidget(QLabel("选中:"))
        self.checked_val_spin = QSpinBox()
        self.checked_val_spin.setRange(-999999, 999999)
        self.checked_val_spin.setFixedWidth(60)
        self.checked_val_spin.valueChanged.connect(self.on_property_change)
        checkbox_layout.addWidget(self.checked_val_spin)
        
        checkbox_layout.addWidget(QLabel("未选:"))
        self.unchecked_val_spin = QSpinBox()
        self.unchecked_val_spin.setRange(-999999, 999999)
        self.unchecked_val_spin.setFixedWidth(60)
        self.unchecked_val_spin.valueChanged.connect(self.on_property_change)
        checkbox_layout.addWidget(self.unchecked_val_spin)
        
        checkbox_layout.addStretch()
        self.checkbox_group.setLayout(checkbox_layout)
        self.checkbox_group.setMaximumHeight(60)
        self.basic_splitter.addWidget(self.checkbox_group)
    
    def _create_advanced_properties_with_splitter(self):
        """Create advanced property groups with resizable splitter layout"""
        # === Group 1: Clock Settings ===
        self.clock_settings_group = QGroupBox("时钟设置")
        clock_layout = QVBoxLayout()
        clock_layout.setSpacing(5)
        clock_layout.setContentsMargins(5, 5, 5, 5)
        
        # Clock style selection
        clock_style_layout = QHBoxLayout()
        clock_style_layout.addWidget(QLabel("时钟样式:"))
        self.clock_style_combo = QComboBox()
        self.clock_style_combo.addItems(["数字", "模拟"])
        self.clock_style_combo.setFixedWidth(100)
        self.clock_style_combo.currentTextChanged.connect(self.on_clock_style_changed)
        clock_style_layout.addWidget(self.clock_style_combo)
        clock_style_layout.addStretch()
        clock_layout.addLayout(clock_style_layout)
        
        # Display options
        display_options_layout = QHBoxLayout()
        self.clock_show_date_checkbox = QCheckBox("显示日期")
        self.clock_show_date_checkbox.stateChanged.connect(self.on_clock_property_change)
        display_options_layout.addWidget(self.clock_show_date_checkbox)
        
        self.clock_show_time_checkbox = QCheckBox("显示时间")
        self.clock_show_time_checkbox.stateChanged.connect(self.on_clock_property_change)
        display_options_layout.addWidget(self.clock_show_time_checkbox)
        
        self.clock_show_seconds_checkbox = QCheckBox("显示秒")
        self.clock_show_seconds_checkbox.stateChanged.connect(self.on_clock_property_change)
        display_options_layout.addWidget(self.clock_show_seconds_checkbox)
        clock_layout.addLayout(display_options_layout)
        
        # Date format
        date_format_layout = QHBoxLayout()
        date_format_layout.addWidget(QLabel("日期格式:"))
        self.clock_date_format_edit = QLineEdit()
        self.clock_date_format_edit.setPlaceholderText("YYYY-MM-DD")
        self.clock_date_format_edit.editingFinished.connect(self.on_clock_property_change)
        date_format_layout.addWidget(self.clock_date_format_edit)
        clock_layout.addLayout(date_format_layout)
        
        # Time format
        time_format_layout = QHBoxLayout()
        time_format_layout.addWidget(QLabel("时间格式:"))
        self.clock_time_format_edit = QLineEdit()
        self.clock_time_format_edit.setPlaceholderText("HH:MM:SS")
        self.clock_time_format_edit.editingFinished.connect(self.on_clock_property_change)
        time_format_layout.addWidget(self.clock_time_format_edit)
        clock_layout.addLayout(time_format_layout)
        
        # Color settings
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("背景色:"))
        self.clock_bg_color_button = QPushButton("选择")
        self.clock_bg_color_button.setFixedWidth(60)
        self.clock_bg_color_button.clicked.connect(self.choose_clock_bg_color)
        color_layout.addWidget(self.clock_bg_color_button)
        
        color_layout.addWidget(QLabel("边框色:"))
        self.clock_border_color_button = QPushButton("选择")
        self.clock_border_color_button.setFixedWidth(60)
        self.clock_border_color_button.clicked.connect(self.choose_clock_border_color)
        color_layout.addWidget(self.clock_border_color_button)
        clock_layout.addLayout(color_layout)
        
        # Border settings
        border_layout = QHBoxLayout()
        self.clock_show_border_checkbox = QCheckBox("显示边框")
        self.clock_show_border_checkbox.stateChanged.connect(self.on_clock_property_change)
        border_layout.addWidget(self.clock_show_border_checkbox)
        
        border_layout.addWidget(QLabel("边框宽度:"))
        self.clock_border_width_spin = QSpinBox()
        self.clock_border_width_spin.setRange(0, 10)
        self.clock_border_width_spin.setValue(1)
        self.clock_border_width_spin.setFixedWidth(50)
        self.clock_border_width_spin.valueChanged.connect(self.on_clock_property_change)
        border_layout.addWidget(self.clock_border_width_spin)
        clock_layout.addLayout(border_layout)
        
        self.clock_settings_group.setLayout(clock_layout)
        self.clock_settings_group.setMaximumHeight(200)
        self.adv_splitter.addWidget(self.clock_settings_group)
        
        # === Group 2: Dropdown Options (Value-Text Mapping) ===
        self.dropdown_options_group = QGroupBox("下拉框选项 (值-文本映射)")
        dropdown_options_layout = QVBoxLayout()
        dropdown_options_layout.setSpacing(5)
        dropdown_options_layout.setContentsMargins(5, 5, 5, 5)
        
        # Note: Bind mode is always 'value' for dropdown
        # Removed bind mode selection UI as per user request
        
        # Table widget for dropdown items with value-text mapping
        self.dropdown_table = QTableWidget()
        self.dropdown_table.setColumnCount(2)
        self.dropdown_table.setHorizontalHeaderLabels(["变量值", "显示文本"])
        self.dropdown_table.horizontalHeader().setStretchLastSection(True)
        self.dropdown_table.setMinimumHeight(100)
        self.dropdown_table.setMaximumHeight(150)
        self.dropdown_table.itemChanged.connect(self.on_dropdown_item_changed)
        dropdown_options_layout.addWidget(self.dropdown_table)
        
        # Buttons for add/remove
        dropdown_btn_layout = QHBoxLayout()
        self.dropdown_add_btn = QPushButton("+ 添加")
        self.dropdown_add_btn.setFixedWidth(60)
        self.dropdown_add_btn.clicked.connect(self.on_dropdown_add_item)
        dropdown_btn_layout.addWidget(self.dropdown_add_btn)
        
        self.dropdown_remove_btn = QPushButton("- 删除")
        self.dropdown_remove_btn.setFixedWidth(60)
        self.dropdown_remove_btn.clicked.connect(self.on_dropdown_remove_item)
        dropdown_btn_layout.addWidget(self.dropdown_remove_btn)
        
        dropdown_btn_layout.addStretch()
        dropdown_options_layout.addLayout(dropdown_btn_layout)
        
        self.dropdown_options_group.setLayout(dropdown_options_layout)
        self.dropdown_options_group.setMaximumHeight(200)
        self.adv_splitter.addWidget(self.dropdown_options_group)
        
        # === Group 3: Text List Options ===
        self.text_list_group = QGroupBox("文本列表项 (值-文本映射)")
        text_list_layout = QVBoxLayout()
        text_list_layout.setSpacing(5)
        text_list_layout.setContentsMargins(5, 5, 5, 5)
        
        # Display mode selection
        display_mode_layout = QHBoxLayout()
        display_mode_layout.addWidget(QLabel("显示模式:"))
        self.text_list_display_mode_combo = QComboBox()
        self.text_list_display_mode_combo.addItems(["列表模式", "单行模式"])
        self.text_list_display_mode_combo.setFixedWidth(100)
        self.text_list_display_mode_combo.currentTextChanged.connect(self.on_text_list_display_mode_changed)
        display_mode_layout.addWidget(self.text_list_display_mode_combo)
        display_mode_layout.addStretch()
        text_list_layout.addLayout(display_mode_layout)
        
        # Note: Bind mode is always 'value' for text list (removed index mode selection)
        
        # Table widget for list items with value-text mapping
        self.text_list_table = QTableWidget()
        self.text_list_table.setColumnCount(2)
        self.text_list_table.setHorizontalHeaderLabels(["变量值", "显示文本"])
        self.text_list_table.horizontalHeader().setStretchLastSection(True)
        self.text_list_table.setMinimumHeight(100)
        self.text_list_table.setMaximumHeight(150)
        self.text_list_table.itemChanged.connect(self.on_text_list_item_changed)
        text_list_layout.addWidget(self.text_list_table)
        
        # Buttons for add/remove
        btn_layout = QHBoxLayout()
        self.text_list_add_btn = QPushButton("+ 添加")
        self.text_list_add_btn.setFixedWidth(60)
        self.text_list_add_btn.clicked.connect(self.on_text_list_add_item)
        btn_layout.addWidget(self.text_list_add_btn)
        
        self.text_list_remove_btn = QPushButton("- 删除")
        self.text_list_remove_btn.setFixedWidth(60)
        self.text_list_remove_btn.clicked.connect(self.on_text_list_remove_item)
        btn_layout.addWidget(self.text_list_remove_btn)
        
        btn_layout.addStretch()
        text_list_layout.addLayout(btn_layout)
        
        # Additional settings
        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("行高:"))
        self.text_list_item_height_spin = QSpinBox()
        self.text_list_item_height_spin.setRange(15, 50)
        self.text_list_item_height_spin.setValue(25)
        self.text_list_item_height_spin.setFixedWidth(50)
        self.text_list_item_height_spin.valueChanged.connect(self.on_property_change)
        settings_layout.addWidget(self.text_list_item_height_spin)
        
        settings_layout.addWidget(QLabel("选中:"))
        self.text_list_selected_spin = QSpinBox()
        self.text_list_selected_spin.setRange(-1, 999)
        self.text_list_selected_spin.setValue(-1)
        self.text_list_selected_spin.setFixedWidth(50)
        self.text_list_selected_spin.setSpecialValueText("无")
        self.text_list_selected_spin.valueChanged.connect(self.on_property_change)
        settings_layout.addWidget(self.text_list_selected_spin)
        
        settings_layout.addStretch()
        text_list_layout.addLayout(settings_layout)
        
        # Default text for single mode
        default_text_layout = QHBoxLayout()
        default_text_layout.addWidget(QLabel("默认文本:"))
        self.text_list_default_text_edit = QLineEdit()
        self.text_list_default_text_edit.setPlaceholderText("无匹配时显示")
        self.text_list_default_text_edit.editingFinished.connect(self.on_text_list_default_text_changed)
        default_text_layout.addWidget(self.text_list_default_text_edit)
        text_list_layout.addLayout(default_text_layout)
        
        self.text_list_group.setLayout(text_list_layout)
        self.text_list_group.setMaximumHeight(250)
        self.adv_splitter.addWidget(self.text_list_group)
        
        # === Group 3: Button Colors ===
        self.button_colors_group = QGroupBox("按钮颜色")
        color_state_layout = QHBoxLayout()
        color_state_layout.setSpacing(2)
        color_state_layout.setContentsMargins(3, 2, 3, 2)
        
        color_state_layout.addWidget(QLabel("开启:"))
        self.on_color_button = QPushButton("选择")
        self.on_color_button.setFixedWidth(50)
        self.on_color_button.clicked.connect(lambda: self.choose_color_for_state('on'))
        color_state_layout.addWidget(self.on_color_button)
        
        color_state_layout.addWidget(QLabel("关闭:"))
        self.off_color_button = QPushButton("选择")
        self.off_color_button.setFixedWidth(50)
        self.off_color_button.clicked.connect(lambda: self.choose_color_for_state('off'))
        color_state_layout.addWidget(self.off_color_button)
        
        color_state_layout.addStretch()
        self.button_colors_group.setLayout(color_state_layout)
        self.button_colors_group.setMaximumHeight(60)
        self.adv_splitter.addWidget(self.button_colors_group)
        
        # === Group 4: Label Format ===
        self.label_format_group = QGroupBox("显示格式")
        format_layout = QHBoxLayout()
        format_layout.setSpacing(2)
        format_layout.setContentsMargins(3, 2, 3, 2)
        
        format_layout.addWidget(QLabel("格式:"))
        self.format_edit = QLineEdit()
        self.format_edit.setFixedWidth(70)
        self.format_edit.setPlaceholderText("{:.2f}")
        self.format_edit.editingFinished.connect(self.on_property_change)
        format_layout.addWidget(self.format_edit)
        
        format_layout.addWidget(QLabel("单位:"))
        self.unit_edit = QLineEdit()
        self.unit_edit.setFixedWidth(50)
        self.unit_edit.editingFinished.connect(self.on_property_change)
        format_layout.addWidget(self.unit_edit)
        
        format_layout.addWidget(QLabel("精度:"))
        self.precision_spin = QSpinBox()
        self.precision_spin.setRange(0, 6)
        self.precision_spin.setFixedWidth(45)
        self.precision_spin.valueChanged.connect(self.on_property_change)
        format_layout.addWidget(self.precision_spin)
        
        format_layout.addStretch()
        self.label_format_group.setLayout(format_layout)
        self.label_format_group.setMaximumHeight(60)
        self.adv_splitter.addWidget(self.label_format_group)
        
        # === Group 5: Graphics Properties ===
        self.graphics_group = QGroupBox("图形属性")
        graphics_layout = QHBoxLayout()
        graphics_layout.setSpacing(2)
        graphics_layout.setContentsMargins(3, 2, 3, 2)
        
        graphics_layout.addWidget(QLabel("线宽:"))
        self.line_width_spin = QSpinBox()
        self.line_width_spin.setRange(0, 20)
        self.line_width_spin.setFixedWidth(45)
        self.line_width_spin.valueChanged.connect(self.on_property_change)
        graphics_layout.addWidget(self.line_width_spin)
        
        graphics_layout.addWidget(QLabel("线条:"))
        self.line_color_button = QPushButton("选择")
        self.line_color_button.setFixedWidth(45)
        self.line_color_button.clicked.connect(self.choose_line_color)
        graphics_layout.addWidget(self.line_color_button)
        
        self.filled_checkbox = QCheckBox("填充")
        self.filled_checkbox.stateChanged.connect(self.on_property_change)
        graphics_layout.addWidget(self.filled_checkbox)
        
        graphics_layout.addWidget(QLabel("填充:"))
        self.fill_color_button = QPushButton("选择")
        self.fill_color_button.setFixedWidth(45)
        self.fill_color_button.clicked.connect(self.choose_fill_color)
        graphics_layout.addWidget(self.fill_color_button)
        
        graphics_layout.addStretch()
        self.graphics_group.setLayout(graphics_layout)
        self.graphics_group.setMaximumHeight(60)
        self.adv_splitter.addWidget(self.graphics_group)
        
        # === Group 6: Light Properties ===
        self.light_group = QGroupBox("指示灯属性")
        light_layout = QVBoxLayout()
        light_layout.setSpacing(3)
        light_layout.setContentsMargins(3, 2, 3, 2)
        
        # Row 1: Shape and text (compact layout)
        light_row1 = QHBoxLayout()
        light_row1.setSpacing(1)
        light_row1.setContentsMargins(2, 2, 2, 2)
        
        light_row1.addWidget(QLabel("形状:"))
        self.light_shape_combo = QComboBox()
        self.light_shape_combo.addItems(["圆形", "方形", "矩形"])
        self.light_shape_combo.setFixedWidth(55)
        self.light_shape_combo.currentTextChanged.connect(self.on_light_shape_change)
        light_row1.addWidget(self.light_shape_combo)

        light_row1.addSpacing(5)
        light_row1.addWidget(QLabel("文字颜色:"))
        self.light_text_color_button = QPushButton("选择")
        self.light_text_color_button.setFixedWidth(35)
        self.light_text_color_button.clicked.connect(self.choose_light_text_color)
        light_row1.addWidget(self.light_text_color_button)

        light_row1.addStretch()
        light_layout.addLayout(light_row1)
        
        # Row 2: Colors for on/off states (compact layout)
        light_row2 = QHBoxLayout()
        light_row2.setSpacing(1)
        light_row2.setContentsMargins(2, 2, 2, 2)

        light_row2.addWidget(QLabel("开启颜色:"))
        self.light_on_color_button = QPushButton("选择")
        self.light_on_color_button.setFixedWidth(35)
        self.light_on_color_button.clicked.connect(lambda: self.choose_light_color('on'))
        light_row2.addWidget(self.light_on_color_button)

        light_row2.addSpacing(5)
        light_row2.addWidget(QLabel("关闭颜色:"))
        self.light_off_color_button = QPushButton("选择")
        self.light_off_color_button.setFixedWidth(35)
        self.light_off_color_button.clicked.connect(lambda: self.choose_light_color('off'))
        light_row2.addWidget(self.light_off_color_button)

        light_row2.addSpacing(5)
        self.light_border_checkbox = QCheckBox("边框")
        self.light_border_checkbox.stateChanged.connect(self.on_property_change)
        light_row2.addWidget(self.light_border_checkbox)

        light_row2.addStretch()
        light_layout.addLayout(light_row2)
        
        # Row 3: Image checkbox
        light_row3 = QHBoxLayout()
        light_row3.setSpacing(3)
        light_row3.setContentsMargins(2, 2, 2, 2)
        
        self.light_use_image_checkbox = QCheckBox("使用图片")
        self.light_use_image_checkbox.stateChanged.connect(self.on_light_use_image_change)
        light_row3.addWidget(self.light_use_image_checkbox)
        light_row3.addStretch()
        
        light_layout.addLayout(light_row3)
        
        # Row 4: On image
        light_row4 = QHBoxLayout()
        light_row4.setSpacing(2)
        light_row4.addWidget(QLabel("开启图片:"))
        light_row4.addWidget(QLabel("开启:"))
        self.light_on_image_edit = QLineEdit()
        self.light_on_image_edit.setReadOnly(True)
        self.light_on_image_edit.setFixedWidth(100)
        self.light_on_image_edit.setPlaceholderText("无图片")
        light_row4.addWidget(self.light_on_image_edit)
        
        self.light_on_image_btn = QPushButton("浏览...")
        self.light_on_image_btn.setFixedWidth(45)
        self.light_on_image_btn.clicked.connect(lambda: self.browse_light_image('on'))
        light_row4.addWidget(self.light_on_image_btn)
        light_row4.addStretch()
        
        light_layout.addLayout(light_row4)
        
        # Row 5: Off image
        light_row5 = QHBoxLayout()
        light_row5.setSpacing(2)
        light_row5.setContentsMargins(2, 2, 2, 2)       
        light_row5.addWidget(QLabel("关闭图片:"))   
        light_row5.addWidget(QLabel("关闭:"))
        self.light_off_image_edit = QLineEdit()
        self.light_off_image_edit.setReadOnly(True)
        self.light_off_image_edit.setFixedWidth(100)
        self.light_off_image_edit.setPlaceholderText("无图片")
        light_row5.addWidget(self.light_off_image_edit)
        
        self.light_off_image_btn = QPushButton("浏览...")
        self.light_off_image_btn.setFixedWidth(45)
        self.light_off_image_btn.clicked.connect(lambda: self.browse_light_image('off'))
        light_row5.addWidget(self.light_off_image_btn)
        light_row5.addStretch()
        
        light_layout.addLayout(light_row5)
        
        light_layout.addStretch()
        self.light_group.setLayout(light_layout)
        self.light_group.setMaximumHeight(200)
        self.adv_splitter.addWidget(self.light_group)
        
        # === Group 7: Picture Properties ===
        self.picture_group = QGroupBox("图片属性")
        picture_layout = QHBoxLayout()
        picture_layout.setSpacing(2)
        picture_layout.setContentsMargins(3, 2, 3, 2)
        
        self.image_path_edit = QLineEdit()
        self.image_path_edit.setReadOnly(True)
        self.image_path_edit.setPlaceholderText("无图片")
        picture_layout.addWidget(self.image_path_edit)
        
        self.browse_image_btn = QPushButton("浏览...")
        self.browse_image_btn.setFixedWidth(50)
        self.browse_image_btn.clicked.connect(self.browse_image)
        picture_layout.addWidget(self.browse_image_btn)
        
        self.clear_image_btn = QPushButton("清除")
        self.clear_image_btn.setFixedWidth(40)
        self.clear_image_btn.clicked.connect(self.clear_image)
        picture_layout.addWidget(self.clear_image_btn)
        
        self.keep_aspect_checkbox = QCheckBox("保持比例")
        self.keep_aspect_checkbox.setChecked(True)
        self.keep_aspect_checkbox.stateChanged.connect(self.on_property_change)
        picture_layout.addWidget(self.keep_aspect_checkbox)
        
        picture_layout.addStretch()
        self.picture_group.setLayout(picture_layout)
        self.picture_group.setMaximumHeight(60)
        self.adv_splitter.addWidget(self.picture_group)
        
        # === Group 7b: Picture List Properties ===
        self.picture_list_group = QGroupBox("图形列表属性")
        picture_list_layout = QVBoxLayout()
        picture_list_layout.setSpacing(5)
        picture_list_layout.setContentsMargins(5, 5, 5, 5)
        
        pl_row1 = QHBoxLayout()
        pl_row1.addWidget(QLabel("值类型:"))
        self.pl_value_type_combo = QComboBox()
        self.pl_value_type_combo.addItems(["整数", "浮点数", "布尔", "字符串"])
        self.pl_value_type_combo.setCurrentText("整数")
        self.pl_value_type_combo.currentTextChanged.connect(self.on_picture_list_value_type_change)
        pl_row1.addWidget(self.pl_value_type_combo)
        pl_row1.addStretch()
        picture_list_layout.addLayout(pl_row1)
        
        pl_row2 = QHBoxLayout()
        self.pl_keep_aspect_cb = QCheckBox("保持图片比例")
        self.pl_keep_aspect_cb.setChecked(True)
        self.pl_keep_aspect_cb.stateChanged.connect(self.on_property_change)
        pl_row2.addWidget(self.pl_keep_aspect_cb)
        
        self.pl_show_border_cb = QCheckBox("显示边框")
        self.pl_show_border_cb.setChecked(True)
        self.pl_show_border_cb.stateChanged.connect(self.on_property_change)
        pl_row2.addWidget(self.pl_show_border_cb)
        
        self.pl_show_value_cb = QCheckBox("显示值")
        self.pl_show_value_cb.stateChanged.connect(self.on_property_change)
        pl_row2.addWidget(self.pl_show_value_cb)
        pl_row2.addStretch()
        picture_list_layout.addLayout(pl_row2)
        
        pl_row3 = QHBoxLayout()
        pl_row3.addWidget(QLabel("默认图片:"))
        self.pl_default_image_edit = QLineEdit()
        self.pl_default_image_edit.setReadOnly(True)
        self.pl_default_image_edit.setPlaceholderText("无匹配时显示")
        pl_row3.addWidget(self.pl_default_image_edit)
        self.pl_browse_default_btn = QPushButton("...")
        self.pl_browse_default_btn.setFixedWidth(30)
        self.pl_browse_default_btn.clicked.connect(self.browse_picture_list_default_image)
        pl_row3.addWidget(self.pl_browse_default_btn)
        picture_list_layout.addLayout(pl_row3)
        
        pl_row4 = QHBoxLayout()
        pl_row4.addWidget(QLabel("状态图片列表:"))
        pl_row4.addStretch()
        self.pl_add_state_btn = QPushButton("+")
        self.pl_add_state_btn.setFixedSize(24, 24)
        self.pl_add_state_btn.clicked.connect(self.add_picture_list_state)
        pl_row4.addWidget(self.pl_add_state_btn)
        picture_list_layout.addLayout(pl_row4)
        
        self.pl_states_table = QTableWidget()
        self.pl_states_table.setColumnCount(4)
        self.pl_states_table.setHorizontalHeaderLabels(["值", "条件", "图片", "操作"])
        self.pl_states_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.pl_states_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.pl_states_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.pl_states_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.pl_states_table.setMaximumHeight(150)
        self.pl_states_table.cellChanged.connect(self.on_pl_states_table_changed)
        picture_list_layout.addWidget(self.pl_states_table)
        
        self.picture_list_group.setLayout(picture_list_layout)
        self.picture_list_group.setMaximumHeight(250)
        self.adv_splitter.addWidget(self.picture_list_group)
        
        # === Group 8: Alarm Display Properties ===
        self.alarm_display_group = QGroupBox("报警显示设置")
        alarm_display_layout = QVBoxLayout()
        alarm_display_layout.setSpacing(5)
        alarm_display_layout.setContentsMargins(5, 5, 5, 5)
        
        # Display settings
        display_settings_layout = QHBoxLayout()
        
        display_settings_layout.addWidget(QLabel("最大显示数量:"))
        self.alarm_max_count_spin = QSpinBox()
        self.alarm_max_count_spin.setRange(1, 200)
        self.alarm_max_count_spin.setValue(50)
        self.alarm_max_count_spin.valueChanged.connect(self.on_property_change)
        display_settings_layout.addWidget(self.alarm_max_count_spin)
        
        display_settings_layout.addStretch()
        alarm_display_layout.addLayout(display_settings_layout)
        
        # Checkbox options
        checkbox_layout = QHBoxLayout()
        
        self.alarm_auto_scroll_checkbox = QCheckBox("自动滚动")
        self.alarm_auto_scroll_checkbox.setChecked(True)
        self.alarm_auto_scroll_checkbox.stateChanged.connect(self.on_property_change)
        checkbox_layout.addWidget(self.alarm_auto_scroll_checkbox)
        
        self.alarm_show_timestamp_checkbox = QCheckBox("显示时间戳")
        self.alarm_show_timestamp_checkbox.setChecked(True)
        self.alarm_show_timestamp_checkbox.stateChanged.connect(self.on_property_change)
        checkbox_layout.addWidget(self.alarm_show_timestamp_checkbox)
        
        self.alarm_show_type_checkbox = QCheckBox("显示报警类型")
        self.alarm_show_type_checkbox.setChecked(True)
        self.alarm_show_type_checkbox.stateChanged.connect(self.on_property_change)
        checkbox_layout.addWidget(self.alarm_show_type_checkbox)
        
        checkbox_layout.addStretch()
        alarm_display_layout.addLayout(checkbox_layout)
        
        # Visible alarm types
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("显示报警类型:"))
        type_layout.addStretch()
        
        self.alarm_select_all_btn = QPushButton("全选")
        self.alarm_select_all_btn.setFixedWidth(50)
        self.alarm_select_all_btn.clicked.connect(self.select_all_alarm_types)
        type_layout.addWidget(self.alarm_select_all_btn)
        
        self.alarm_select_none_btn = QPushButton("全不选")
        self.alarm_select_none_btn.setFixedWidth(50)
        self.alarm_select_none_btn.clicked.connect(self.select_no_alarm_types)
        type_layout.addWidget(self.alarm_select_none_btn)
        
        alarm_display_layout.addLayout(type_layout)
        
        # Alarm type checkboxes
        self.alarm_type_checkboxes = {}
        alarm_types_layout = QVBoxLayout()
        
        # Get alarm types from alarm type manager
        try:
            from scada_app.core.alarm_type_manager import alarm_type_manager
            alarm_type_names = alarm_type_manager.get_alarm_type_names()
            
            for type_name in alarm_type_names:
                checkbox = QCheckBox(type_name)
                checkbox.setChecked(True)
                checkbox.stateChanged.connect(self.on_property_change)
                self.alarm_type_checkboxes[type_name] = checkbox
                alarm_types_layout.addWidget(checkbox)
        except Exception as e:
            print(f"Warning: Could not load alarm types: {e}")
            # Fallback to default types
            default_types = ['危急', '高', '中', '低', '信息', '警告', '错误']
            for type_name in default_types:
                checkbox = QCheckBox(type_name)
                checkbox.setChecked(True)
                checkbox.stateChanged.connect(self.on_property_change)
                self.alarm_type_checkboxes[type_name] = checkbox
                alarm_types_layout.addWidget(checkbox)
        
        alarm_types_layout.addStretch()
        alarm_display_layout.addLayout(alarm_types_layout)
        
        self.alarm_display_group.setLayout(alarm_display_layout)
        self.alarm_display_group.setMaximumHeight(250)
        self.adv_splitter.addWidget(self.alarm_display_group)

        # === Group 8: Progress Bar Properties ===
        self.progress_group = QGroupBox("进度条属性")
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(3)
        progress_layout.setContentsMargins(3, 2, 3, 2)

        # Row 1: Orientation and colors
        progress_row1 = QHBoxLayout()
        progress_row1.setSpacing(1)
        progress_row1.setContentsMargins(0, 0, 0, 0)

        progress_row1.addWidget(QLabel("方向:"))
        self.progress_orientation_combo = QComboBox()
        self.progress_orientation_combo.addItems(["水平", "垂直"])
        self.progress_orientation_combo.setFixedWidth(55)
        self.progress_orientation_combo.currentTextChanged.connect(self.on_progress_orientation_change)
        progress_row1.addWidget(self.progress_orientation_combo)

        progress_row1.addSpacing(5)
        progress_row1.addWidget(QLabel("进度:"))
        self.progress_bar_color_button = QPushButton("选择")
        self.progress_bar_color_button.setFixedWidth(35)
        self.progress_bar_color_button.clicked.connect(self.choose_progress_bar_color)
        progress_row1.addWidget(self.progress_bar_color_button)

        progress_row1.addSpacing(3)
        progress_row1.addWidget(QLabel("背景:"))
        self.progress_bg_color_button = QPushButton("选择")
        self.progress_bg_color_button.setFixedWidth(35)
        self.progress_bg_color_button.clicked.connect(self.choose_progress_bg_color)
        progress_row1.addWidget(self.progress_bg_color_button)

        progress_row1.addStretch()
        progress_layout.addLayout(progress_row1)

        # Row 2: Border settings
        progress_row2 = QHBoxLayout()
        progress_row2.setSpacing(1)
        progress_row2.setContentsMargins(0, 0, 0, 0)

        progress_row2.addWidget(QLabel("边框:"))
        self.progress_border_color_button = QPushButton("颜色")
        self.progress_border_color_button.setFixedWidth(35)
        self.progress_border_color_button.clicked.connect(self.choose_progress_border_color)
        progress_row2.addWidget(self.progress_border_color_button)

        progress_row2.addSpacing(3)
        progress_row2.addWidget(QLabel("宽度:"))
        self.progress_border_width_spin = QSpinBox()
        self.progress_border_width_spin.setRange(0, 10)
        self.progress_border_width_spin.setFixedWidth(40)
        self.progress_border_width_spin.valueChanged.connect(self.on_property_change)
        progress_row2.addWidget(self.progress_border_width_spin)

        progress_row2.addSpacing(5)
        progress_row2.addWidget(QLabel("圆角:"))
        self.progress_border_radius_spin = QSpinBox()
        self.progress_border_radius_spin.setRange(0, 50)
        self.progress_border_radius_spin.setFixedWidth(40)
        self.progress_border_radius_spin.valueChanged.connect(self.on_property_change)
        progress_row2.addWidget(self.progress_border_radius_spin)

        progress_row2.addStretch()
        progress_layout.addLayout(progress_row2)

        # Row 3: Text display options
        progress_row3 = QHBoxLayout()
        progress_row3.setSpacing(1)
        progress_row3.setContentsMargins(0, 0, 0, 0)

        self.progress_show_value_checkbox = QCheckBox("显示值")
        self.progress_show_value_checkbox.stateChanged.connect(self.on_property_change)
        progress_row3.addWidget(self.progress_show_value_checkbox)

        self.progress_show_percentage_checkbox = QCheckBox("百分比")
        self.progress_show_percentage_checkbox.stateChanged.connect(self.on_property_change)
        progress_row3.addWidget(self.progress_show_percentage_checkbox)

        progress_row3.addSpacing(5)
        progress_row3.addWidget(QLabel("颜色:"))
        self.progress_text_color_button = QPushButton("选择")
        self.progress_text_color_button.setFixedWidth(35)
        self.progress_text_color_button.clicked.connect(self.choose_progress_text_color)
        progress_row3.addWidget(self.progress_text_color_button)

        progress_row3.addStretch()
        progress_layout.addLayout(progress_row3)

        # Row 4: Text position and font
        progress_row4 = QHBoxLayout()
        progress_row4.setSpacing(1)
        progress_row4.setContentsMargins(0, 0, 0, 0)

        progress_row4.addWidget(QLabel("位置:"))
        self.progress_text_position_combo = QComboBox()
        self.progress_text_position_combo.addItems(["居中", "左侧", "右侧", "顶部", "底部"])
        self.progress_text_position_combo.setFixedWidth(55)
        self.progress_text_position_combo.currentTextChanged.connect(self.on_progress_text_position_change)
        progress_row4.addWidget(self.progress_text_position_combo)

        progress_row4.addSpacing(5)
        progress_row4.addWidget(QLabel("字号:"))
        self.progress_font_size_spin = QSpinBox()
        self.progress_font_size_spin.setRange(6, 72)
        self.progress_font_size_spin.setFixedWidth(40)
        self.progress_font_size_spin.valueChanged.connect(self.on_property_change)
        progress_row4.addWidget(self.progress_font_size_spin)

        self.progress_gradient_checkbox = QCheckBox("渐变")
        self.progress_gradient_checkbox.stateChanged.connect(self.on_property_change)
        progress_row4.addWidget(self.progress_gradient_checkbox)

        progress_row4.addStretch()
        progress_layout.addLayout(progress_row4)

        progress_layout.addStretch()
        self.progress_group.setLayout(progress_layout)
        self.progress_group.setMaximumHeight(150)
        self.adv_splitter.addWidget(self.progress_group)

        # === Group 9: Trend Chart Properties ===
        self.trend_group = QGroupBox("趋势图属性")
        trend_layout = QVBoxLayout()
        trend_layout.setSpacing(3)
        trend_layout.setContentsMargins(3, 2, 3, 2)

        # Row 1: Title
        trend_row1 = QHBoxLayout()
        trend_row1.setSpacing(1)
        trend_row1.setContentsMargins(0, 0, 0, 0)

        trend_row1.addWidget(QLabel("标题:"))
        self.trend_title_edit = QLineEdit()
        self.trend_title_edit.setPlaceholderText("趋势图标题")
        self.trend_title_edit.textChanged.connect(self.on_property_change)
        trend_row1.addWidget(self.trend_title_edit)

        self.trend_title_visible_checkbox = QCheckBox("显示")
        self.trend_title_visible_checkbox.setChecked(True)
        self.trend_title_visible_checkbox.stateChanged.connect(self.on_property_change)
        trend_row1.addWidget(self.trend_title_visible_checkbox)

        trend_row1.addWidget(QLabel("颜色:"))
        self.trend_title_color_button = QPushButton("选择")
        self.trend_title_color_button.setFixedWidth(35)
        self.trend_title_color_button.clicked.connect(self.choose_trend_title_color)
        trend_row1.addWidget(self.trend_title_color_button)

        trend_layout.addLayout(trend_row1)

        # Row 2: Y-Axis range
        trend_row2 = QHBoxLayout()
        trend_row2.setSpacing(1)
        trend_row2.setContentsMargins(0, 0, 0, 0)

        trend_row2.addWidget(QLabel("Y轴:"))
        trend_row2.addWidget(QLabel("最小:"))
        self.trend_y_min_spin = QSpinBox()
        self.trend_y_min_spin.setRange(-99999, 99999)
        self.trend_y_min_spin.setFixedWidth(55)
        self.trend_y_min_spin.valueChanged.connect(self.on_property_change)
        trend_row2.addWidget(self.trend_y_min_spin)

        trend_row2.addWidget(QLabel("最大:"))
        self.trend_y_max_spin = QSpinBox()
        self.trend_y_max_spin.setRange(-99999, 99999)
        self.trend_y_max_spin.setValue(100)
        self.trend_y_max_spin.setFixedWidth(55)
        self.trend_y_max_spin.valueChanged.connect(self.on_property_change)
        trend_row2.addWidget(self.trend_y_max_spin)

        self.trend_auto_scale_checkbox = QCheckBox("自动")
        self.trend_auto_scale_checkbox.setChecked(True)
        self.trend_auto_scale_checkbox.stateChanged.connect(self.on_property_change)
        trend_row2.addWidget(self.trend_auto_scale_checkbox)

        trend_row2.addStretch()
        trend_layout.addLayout(trend_row2)

        # Row 3: Time span and update interval
        trend_row3 = QHBoxLayout()
        trend_row3.setSpacing(1)
        trend_row3.setContentsMargins(0, 0, 0, 0)

        trend_row3.addWidget(QLabel("时间跨度:"))
        self.trend_time_span_spin = QSpinBox()
        self.trend_time_span_spin.setRange(60, 86400)
        self.trend_time_span_spin.setValue(3600)
        self.trend_time_span_spin.setSuffix(" 秒")
        self.trend_time_span_spin.setFixedWidth(70)
        self.trend_time_span_spin.valueChanged.connect(self.on_property_change)
        trend_row3.addWidget(self.trend_time_span_spin)

        trend_row3.addSpacing(5)
        trend_row3.addWidget(QLabel("更新:"))
        self.trend_update_interval_spin = QSpinBox()
        self.trend_update_interval_spin.setRange(100, 10000)
        self.trend_update_interval_spin.setValue(1000)
        self.trend_update_interval_spin.setSuffix(" ms")
        self.trend_update_interval_spin.setFixedWidth(70)
        self.trend_update_interval_spin.valueChanged.connect(self.on_property_change)
        trend_row3.addWidget(self.trend_update_interval_spin)

        trend_row3.addStretch()
        trend_layout.addLayout(trend_row3)

        # Row 4: Colors
        trend_row4 = QHBoxLayout()
        trend_row4.setSpacing(1)
        trend_row4.setContentsMargins(0, 0, 0, 0)

        trend_row4.addWidget(QLabel("背景:"))
        self.trend_bg_color_button = QPushButton("选择")
        self.trend_bg_color_button.setFixedWidth(35)
        self.trend_bg_color_button.clicked.connect(self.choose_trend_bg_color)
        trend_row4.addWidget(self.trend_bg_color_button)

        trend_row4.addSpacing(3)
        trend_row4.addWidget(QLabel("网格:"))
        self.trend_grid_color_button = QPushButton("选择")
        self.trend_grid_color_button.setFixedWidth(35)
        self.trend_grid_color_button.clicked.connect(self.choose_trend_grid_color)
        trend_row4.addWidget(self.trend_grid_color_button)

        self.trend_grid_visible_checkbox = QCheckBox("显示网格")
        self.trend_grid_visible_checkbox.setChecked(True)
        self.trend_grid_visible_checkbox.stateChanged.connect(self.on_property_change)
        trend_row4.addWidget(self.trend_grid_visible_checkbox)

        trend_row4.addStretch()
        trend_layout.addLayout(trend_row4)

        # Row 5: Line settings
        trend_row5 = QHBoxLayout()
        trend_row5.setSpacing(1)
        trend_row5.setContentsMargins(0, 0, 0, 0)

        trend_row5.addWidget(QLabel("线宽:"))
        self.trend_line_width_spin = QSpinBox()
        self.trend_line_width_spin.setRange(1, 10)
        self.trend_line_width_spin.setValue(2)
        self.trend_line_width_spin.setFixedWidth(40)
        self.trend_line_width_spin.valueChanged.connect(self.on_property_change)
        trend_row5.addWidget(self.trend_line_width_spin)

        trend_row5.addSpacing(5)
        self.trend_show_legend_checkbox = QCheckBox("显示图例")
        self.trend_show_legend_checkbox.setChecked(True)
        self.trend_show_legend_checkbox.stateChanged.connect(self.on_property_change)
        trend_row5.addWidget(self.trend_show_legend_checkbox)

        trend_row5.addStretch()
        trend_layout.addLayout(trend_row5)

        # Row 6: Variable bindings for trend chart
        trend_var_row = QHBoxLayout()
        trend_var_row.setSpacing(1)
        trend_var_row.setContentsMargins(0, 0, 0, 0)

        trend_var_row.addWidget(QLabel("变量:"))
        self.trend_var_combo = SmartVariableComboBox(self, self.data_manager, self.config_manager)
        self.trend_var_combo.setMinimumWidth(150)
        trend_var_row.addWidget(self.trend_var_combo)

        self.trend_add_var_btn = QPushButton("添加")
        self.trend_add_var_btn.setFixedWidth(45)
        self.trend_add_var_btn.clicked.connect(self.add_trend_variable)
        trend_var_row.addWidget(self.trend_add_var_btn)

        self.trend_remove_var_btn = QPushButton("删除")
        self.trend_remove_var_btn.setFixedWidth(45)
        self.trend_remove_var_btn.clicked.connect(self.remove_trend_variable)
        trend_var_row.addWidget(self.trend_remove_var_btn)

        trend_var_row.addStretch()
        trend_layout.addLayout(trend_var_row)

        # Row 7: Bound variables list
        self.trend_vars_list = QListWidget()
        self.trend_vars_list.setMaximumHeight(60)
        self.trend_vars_list.itemClicked.connect(self.on_trend_var_selected)
        trend_layout.addWidget(self.trend_vars_list)

        trend_layout.addStretch()
        self.trend_group.setLayout(trend_layout)
        self.trend_group.setMaximumHeight(300)
        self.adv_splitter.addWidget(self.trend_group)

        # === Group 10: History Trend Chart Properties ===
        self.history_trend_group = QGroupBox("历史趋势图属性")
        htrend_layout = QVBoxLayout()
        htrend_layout.setSpacing(3)
        htrend_layout.setContentsMargins(3, 2, 3, 2)

        # Row 1: Title
        htrend_row1 = QHBoxLayout()
        htrend_row1.setSpacing(1)
        htrend_row1.setContentsMargins(0, 0, 0, 0)

        htrend_row1.addWidget(QLabel("标题:"))
        self.htrend_title_edit = QLineEdit()
        self.htrend_title_edit.setPlaceholderText("历史趋势图")
        self.htrend_title_edit.textChanged.connect(self.on_property_change)
        htrend_row1.addWidget(self.htrend_title_edit)

        self.htrend_title_visible_checkbox = QCheckBox("显示")
        self.htrend_title_visible_checkbox.setChecked(True)
        self.htrend_title_visible_checkbox.stateChanged.connect(self.on_property_change)
        htrend_row1.addWidget(self.htrend_title_visible_checkbox)

        htrend_row1.addWidget(QLabel("颜色:"))
        self.htrend_title_color_button = QPushButton("选择")
        self.htrend_title_color_button.setFixedWidth(35)
        self.htrend_title_color_button.clicked.connect(self.choose_htrend_title_color)
        htrend_row1.addWidget(self.htrend_title_color_button)

        htrend_layout.addLayout(htrend_row1)

        # Row 2: Font size
        htrend_row2 = QHBoxLayout()
        htrend_row2.setSpacing(1)
        htrend_row2.setContentsMargins(0, 0, 0, 0)

        htrend_row2.addWidget(QLabel("标题字号:"))
        self.htrend_title_font_spin = QSpinBox()
        self.htrend_title_font_spin.setRange(8, 24)
        self.htrend_title_font_spin.setValue(12)
        self.htrend_title_font_spin.setFixedWidth(50)
        self.htrend_title_font_spin.valueChanged.connect(self.on_property_change)
        htrend_row2.addWidget(self.htrend_title_font_spin)

        htrend_row2.addWidget(QLabel("控件字号:"))
        self.htrend_control_font_spin = QSpinBox()
        self.htrend_control_font_spin.setRange(8, 18)
        self.htrend_control_font_spin.setValue(11)
        self.htrend_control_font_spin.setFixedWidth(50)
        self.htrend_control_font_spin.valueChanged.connect(self.on_property_change)
        htrend_row2.addWidget(self.htrend_control_font_spin)

        htrend_row2.addStretch()
        htrend_layout.addLayout(htrend_row2)

        # Row 3: Y-Axis range
        htrend_row3 = QHBoxLayout()
        htrend_row3.setSpacing(1)
        htrend_row3.setContentsMargins(0, 0, 0, 0)

        htrend_row3.addWidget(QLabel("Y轴:"))
        htrend_row3.addWidget(QLabel("最小:"))
        self.htrend_y_min_spin = QSpinBox()
        self.htrend_y_min_spin.setRange(-99999, 99999)
        self.htrend_y_min_spin.setFixedWidth(55)
        self.htrend_y_min_spin.valueChanged.connect(self.on_property_change)
        htrend_row3.addWidget(self.htrend_y_min_spin)

        htrend_row3.addWidget(QLabel("最大:"))
        self.htrend_y_max_spin = QSpinBox()
        self.htrend_y_max_spin.setRange(-99999, 99999)
        self.htrend_y_max_spin.setValue(100)
        self.htrend_y_max_spin.setFixedWidth(55)
        self.htrend_y_max_spin.valueChanged.connect(self.on_property_change)
        htrend_row3.addWidget(self.htrend_y_max_spin)

        self.htrend_auto_scale_checkbox = QCheckBox("自动")
        self.htrend_auto_scale_checkbox.setChecked(True)
        self.htrend_auto_scale_checkbox.stateChanged.connect(self.on_property_change)
        htrend_row3.addWidget(self.htrend_auto_scale_checkbox)

        htrend_row3.addStretch()
        htrend_layout.addLayout(htrend_row3)

        # Row 4: Colors
        htrend_row4 = QHBoxLayout()
        htrend_row4.setSpacing(1)
        htrend_row4.setContentsMargins(0, 0, 0, 0)

        htrend_row4.addWidget(QLabel("背景:"))
        self.htrend_bg_color_button = QPushButton("选择")
        self.htrend_bg_color_button.setFixedWidth(35)
        self.htrend_bg_color_button.clicked.connect(self.choose_htrend_bg_color)
        htrend_row4.addWidget(self.htrend_bg_color_button)

        htrend_row4.addWidget(QLabel("网格:"))
        self.htrend_grid_color_button = QPushButton("选择")
        self.htrend_grid_color_button.setFixedWidth(35)
        self.htrend_grid_color_button.clicked.connect(self.choose_htrend_grid_color)
        htrend_row4.addWidget(self.htrend_grid_color_button)

        self.htrend_grid_visible_checkbox = QCheckBox("显示网格")
        self.htrend_grid_visible_checkbox.setChecked(True)
        self.htrend_grid_visible_checkbox.stateChanged.connect(self.on_property_change)
        htrend_row4.addWidget(self.htrend_grid_visible_checkbox)

        htrend_row4.addStretch()
        htrend_layout.addLayout(htrend_row4)

        # Row 5: Line settings
        htrend_row5 = QHBoxLayout()
        htrend_row5.setSpacing(1)
        htrend_row5.setContentsMargins(0, 0, 0, 0)

        htrend_row5.addWidget(QLabel("线宽:"))
        self.htrend_line_width_spin = QSpinBox()
        self.htrend_line_width_spin.setRange(1, 10)
        self.htrend_line_width_spin.setValue(2)
        self.htrend_line_width_spin.setFixedWidth(50)
        self.htrend_line_width_spin.valueChanged.connect(self.on_property_change)
        htrend_row5.addWidget(self.htrend_line_width_spin)

        self.htrend_show_legend_checkbox = QCheckBox("显示图例")
        self.htrend_show_legend_checkbox.setChecked(True)
        self.htrend_show_legend_checkbox.stateChanged.connect(self.on_property_change)
        htrend_row5.addWidget(self.htrend_show_legend_checkbox)

        htrend_row5.addStretch()
        htrend_layout.addLayout(htrend_row5)

        # Row 6: Border
        htrend_row6 = QHBoxLayout()
        htrend_row6.setSpacing(1)
        htrend_row6.setContentsMargins(0, 0, 0, 0)

        htrend_row6.addWidget(QLabel("边框色:"))
        self.htrend_border_color_button = QPushButton("选择")
        self.htrend_border_color_button.setFixedWidth(35)
        self.htrend_border_color_button.clicked.connect(self.choose_htrend_border_color)
        htrend_row6.addWidget(self.htrend_border_color_button)

        htrend_row6.addWidget(QLabel("边框宽:"))
        self.htrend_border_width_spin = QSpinBox()
        self.htrend_border_width_spin.setRange(0, 10)
        self.htrend_border_width_spin.setValue(1)
        self.htrend_border_width_spin.setFixedWidth(50)
        self.htrend_border_width_spin.valueChanged.connect(self.on_property_change)
        htrend_row6.addWidget(self.htrend_border_width_spin)

        htrend_row6.addStretch()
        htrend_layout.addLayout(htrend_row6)

        htrend_layout.addStretch()
        self.history_trend_group.setLayout(htrend_layout)
        self.history_trend_group.setMaximumHeight(250)
        self.adv_splitter.addWidget(self.history_trend_group)

    def draw_grid(self):
        """Draw grid on the scene"""
        if not self.show_grid:
            return
        
        pen = QPen(QColor('#E0E0E0'))
        pen.setWidth(1)
        
        scene_rect = self.scene.sceneRect()
        
        # Draw vertical lines
        for x in range(0, int(scene_rect.width()), self.grid_size):
            line = self.scene.addLine(x, 0, x, int(scene_rect.height()), pen)
        
        # Draw horizontal lines
        for y in range(0, int(scene_rect.height()), self.grid_size):
            line = self.scene.addLine(0, y, int(scene_rect.width()), y, pen)
    
    def toggle_grid(self, state):
        """Toggle grid display"""
        self.show_grid = state == Qt.Checked
        self._scene_needs_full_refresh = True
        self.refresh_screen_display()
    
    def set_tool(self, tool):
        """Set the current tool"""
        self.current_tool = tool
        print(f"Tool set to: {tool}")
    
    def on_canvas_click(self, event):
        """Handle canvas click events"""
        # Check if inline editor is active and clicked outside of it
        if hasattr(self, 'inline_editor') and self.inline_editor:
            # Check if click is inside the editor
            editor_rect = self.inline_editor.geometry()
            if not editor_rect.contains(event.pos()):
                # Clicked outside, finish editing
                self.finish_inline_text_edit()
        
        pos = self.view.mapToScene(event.pos())
        x, y = int(pos.x()), int(pos.y())
        
        if self.current_tool == "button":
            self.save_state()
            obj = HMIButton(x=x-40, y=y-20)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "label":
            self.save_state()
            obj = HMILabel(x=x-50, y=y-15)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "gauge":
            self.save_state()
            obj = HMIGauge(x=x-40, y=y-40)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "switch":
            self.save_state()
            obj = HMISwitch(x=x-30, y=y-15)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "light":
            self.save_state()
            obj = HMILight(x=x-15, y=y-15, width=30, height=30)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "picture":
            self.save_state()
            obj = HMIPictureBox(x=x-50, y=y-50, width=100, height=100)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "picture_list":
            self.save_state()
            obj = HMIPictureList(x=x-50, y=y-50, width=100, height=100)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "trend_chart":
            self.save_state()
            obj = HMITrendChart(x=x-150, y=y-100, width=300, height=200)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "history_trend":
            self.save_state()
            obj = HMIHistoryTrend(x=x-200, y=y-150, width=400, height=300)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "table_view":
            self.save_state()
            obj = HMITableView(x=x-150, y=y-100, width=300, height=200)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "progress":
            self.save_state()
            obj = HMIProgressBar(x=x-100, y=y-15, width=200, height=30, value=50)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "line":
            self.save_state()
            obj = HMILine(x1=x, y1=y, x2=x+100, y2=y)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "rectangle":
            self.save_state()
            obj = HMIRectangle(x=x-50, y=y-30, width=100, height=60)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "circle":
            self.save_state()
            obj = HMICircle(x=x-50, y=y-50, radius=50)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "input":
            self.save_state()
            obj = HMIInputField(x=x-75, y=y-15)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "checkbox":
            self.save_state()
            obj = HMICheckBox(x=x-60, y=y-12)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "dropdown":
            self.save_state()
            obj = HMIDropdown(x=x-75, y=y-15)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "textarea":
            self.save_state()
            obj = HMITextArea(x=x-150, y=y-75)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "text_list":
            self.save_state()
            obj = HMITextList(x=x-100, y=y-75)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "alarm_display":
            self.save_state()
            obj = HMIAlarmDisplay(x=x-200, y=y-100)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "clock":
            self.save_state()
            obj = HMIClock(x=x-50, y=y-50, width=100, height=100)
            self.objects.append(obj)
            obj.draw(self.scene)
            self.current_tool = "select"
        elif self.current_tool == "select":
            # Check if we should start rubber band selection
            # If Ctrl or Shift is not pressed and no object is under cursor, start rubber band
            clicked_obj = None
            for obj in reversed(self.objects):  # Check from top to bottom
                if obj.obj_type == 'line':
                    # Special hit detection for lines
                    x1 = obj.properties.get('x1', obj.x)
                    y1 = obj.properties.get('y1', obj.y)
                    x2 = obj.properties.get('x2', obj.x + obj.width)
                    y2 = obj.properties.get('y2', obj.y + obj.height)
                    
                    # Calculate distance from point (x,y) to line segment (x1,y1)-(x2,y2)
                    def distance_to_line(x0, y0, x1, y1, x2, y2):
                        A = x0 - x1
                        B = y0 - y1
                        C = x2 - x1
                        D = y2 - y1
                        
                        dot = A * C + B * D
                        len_sq = C * C + D * D
                        param = -1
                        if len_sq != 0:
                            param = dot / len_sq
                        
                        xx, yy = 0, 0
                        if param < 0:
                            xx, yy = x1, y1
                        elif param > 1:
                            xx, yy = x2, y2
                        else:
                            xx = x1 + param * C
                            yy = y1 + param * D
                        
                        dx = x0 - xx
                        dy = y0 - yy
                        return (dx * dx + dy * dy) ** 0.5
                    
                    # Check if distance is within tolerance (5 pixels)
                    if distance_to_line(x, y, x1, y1, x2, y2) <= 5:
                        clicked_obj = obj
                        break
                else:
                    # Regular rectangle hit detection for other objects
                    if (obj.x <= x <= obj.x + obj.width and 
                        obj.y <= y <= obj.y + obj.height):
                        clicked_obj = obj
                        break
            
            # If Ctrl or Shift is pressed, handle individual object selection
            if event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier):
                if clicked_obj:
                    if clicked_obj in self.selected_objects:
                        self.selected_objects.remove(clicked_obj)
                    else:
                        self.selected_objects.append(clicked_obj)
                    # Update primary selection
                    if self.selected_objects:
                        self.selected_object = self.selected_objects[-1]  # Last selected becomes primary
                    else:
                        self.selected_object = None
                    # Force full refresh to update selection boxes
                    self.force_full_refresh()
                    self.update_properties_panel()
                else:
                    # Clicked on empty area with modifier - don't clear selection
                    pass
            elif clicked_obj:
                # Check if clicked object is already selected
                if clicked_obj not in self.selected_objects:
                    # Not selected, so clear selection and select this object
                    self.selected_objects = [clicked_obj]
                    self.select_object(clicked_obj)
                    # Force full refresh to clear old selection boxes
                    self.force_full_refresh()
                else:
                    # Already selected, keep current selection
                    # Update primary selection to the clicked object
                    self.selected_object = clicked_obj
                    # Update properties panel to reflect the newly selected object
                    self.update_properties_panel()
                
                # Check if clicking on line endpoints for line objects
                handle_size = 10
                if clicked_obj.obj_type == 'line':
                    x1 = clicked_obj.properties.get('x1', clicked_obj.x)
                    y1 = clicked_obj.properties.get('y1', clicked_obj.y)
                    x2 = clicked_obj.properties.get('x2', clicked_obj.x + clicked_obj.width)
                    y2 = clicked_obj.properties.get('y2', clicked_obj.y + clicked_obj.height)
                    
                    # Check if clicking near start point
                    if abs(x - x1) <= handle_size and abs(y - y1) <= handle_size:
                        self.save_state()
                        self.dragging_line_endpoint = 'start'
                        self.line_start_pos = (x1, y1, x2, y2)
                        self.dragging = False
                        self.resizing = False
                        # Prevent scene from deselecting
                        event.setAccepted(True)
                        return
                    # Check if clicking near end point
                    elif abs(x - x2) <= handle_size and abs(y - y2) <= handle_size:
                        self.save_state()
                        self.dragging_line_endpoint = 'end'
                        self.line_start_pos = (x1, y1, x2, y2)
                        self.dragging = False
                        self.resizing = False
                        # Prevent scene from deselecting
                        event.setAccepted(True)
                        return
                    else:
                        # Start dragging the whole line
                        self.save_state()
                        self.dragging = True
                        self.drag_start_pos = (x, y)
                        self.drag_start_obj_pos = (clicked_obj.x, clicked_obj.y)
                        self.dragging_line_endpoint = None
                else:
                    # Start dragging
                    self.save_state()
                    self.dragging = True
                    self.drag_start_pos = (x, y)
                    # Use the first selected object as reference for multi-select drag
                    if self.selected_objects:
                        first_obj = self.selected_objects[0]
                        self.drag_start_obj_pos = (first_obj.x, first_obj.y)
                        # Store initial positions of all selected objects for relative positioning
                        self.drag_start_positions = {}
                        for obj in self.selected_objects:
                            self.drag_start_positions[obj] = (obj.x, obj.y)
                    else:
                        self.drag_start_obj_pos = (clicked_obj.x, clicked_obj.y)
                    
                    # Check if clicking on resize handle
                    handle_size = 8
                    resize_handle = None
                    
                    # Check bottom-right corner
                    if (clicked_obj.x + clicked_obj.width - handle_size <= x <= clicked_obj.x + clicked_obj.width and
                        clicked_obj.y + clicked_obj.height - handle_size <= y <= clicked_obj.y + clicked_obj.height):
                        resize_handle = 'br'
                    # Check bottom-left corner
                    elif (clicked_obj.x <= x <= clicked_obj.x + handle_size and
                        clicked_obj.y + clicked_obj.height - handle_size <= y <= clicked_obj.y + clicked_obj.height):
                        resize_handle = 'bl'
                    # Check top-right corner
                    elif (clicked_obj.x + clicked_obj.width - handle_size <= x <= clicked_obj.x + clicked_obj.width and
                        clicked_obj.y <= y <= clicked_obj.y + handle_size):
                        resize_handle = 'tr'
                    # Check top-left corner
                    elif (clicked_obj.x <= x <= clicked_obj.x + handle_size and
                        clicked_obj.y <= y <= clicked_obj.y + handle_size):
                        resize_handle = 'tl'
                    # Check right edge middle
                    elif (clicked_obj.x + clicked_obj.width - handle_size <= x <= clicked_obj.x + clicked_obj.width and
                        clicked_obj.y + clicked_obj.height / 2 - handle_size <= y <= clicked_obj.y + clicked_obj.height / 2 + handle_size):
                        resize_handle = 'r'
                    # Check left edge middle
                    elif (clicked_obj.x <= x <= clicked_obj.x + handle_size and
                        clicked_obj.y + clicked_obj.height / 2 - handle_size <= y <= clicked_obj.y + clicked_obj.height / 2 + handle_size):
                        resize_handle = 'l'
                    # Check bottom edge middle
                    elif (clicked_obj.x + clicked_obj.width / 2 - handle_size <= x <= clicked_obj.x + clicked_obj.width / 2 + handle_size and
                        clicked_obj.y + clicked_obj.height - handle_size <= y <= clicked_obj.y + clicked_obj.height):
                        resize_handle = 'b'
                    # Check top edge middle
                    elif (clicked_obj.x + clicked_obj.width / 2 - handle_size <= x <= clicked_obj.x + clicked_obj.width / 2 + handle_size and
                        clicked_obj.y <= y <= clicked_obj.y + handle_size):
                        resize_handle = 't'
                    
                    if resize_handle:
                        self.resizing = True
                        self.dragging = False  # Not dragging, resizing instead
                        self.resize_handle = resize_handle
                        self.resize_start_rect = (clicked_obj.x, clicked_obj.y, clicked_obj.width, clicked_obj.height)
            else:
                # No object clicked - start rubber band selection
                self.rubber_band_start = (x, y)
                self.rubber_band_end = (x, y)
                self.rubber_band_active = True
                self.dragging = False  # Don't drag when rubber banding
                
                # Clear selection if no modifier key is pressed
                if not (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
                    self.selected_objects = []
                    self.selected_object = None
                    # Force full refresh to clear old selection boxes
                    self.force_full_refresh()
                    self.update_properties_panel()
    
    def on_canvas_wheel(self, event):
        """Handle mouse wheel event for zooming with Ctrl key"""
        if event.modifiers() & Qt.ControlModifier:
            # Get the mouse position in scene coordinates before zoom
            mouse_pos = self.view.mapToScene(event.pos())
            
            # Calculate zoom factor based on wheel direction
            delta = event.angleDelta().y()
            zoom_factor = 1.15 if delta > 0 else 0.87
            
            # Calculate new zoom level
            new_zoom = self.current_zoom * zoom_factor
            
            # Clamp zoom level
            if new_zoom < self.min_zoom:
                new_zoom = self.min_zoom
                zoom_factor = new_zoom / self.current_zoom
            elif new_zoom > self.max_zoom:
                new_zoom = self.max_zoom
                zoom_factor = new_zoom / self.current_zoom
            
            # Apply zoom
            self.view.scale(zoom_factor, zoom_factor)
            self.current_zoom = new_zoom
            
            # Update status bar with zoom percentage
            self.update_status_bar()
            
            event.accept()
        else:
            # Pass to default handler for normal scrolling
            event.ignore()
    
    def on_canvas_double_click(self, event):
        """Handle double click for inline text editing"""
        pos = self.view.mapToScene(event.pos())
        x, y = int(pos.x()), int(pos.y())
        
        # Find clicked object
        clicked_obj = None
        for obj in reversed(self.objects):
            if obj.obj_type == 'line':
                # Line hit detection
                x1 = obj.properties.get('x1', obj.x)
                y1 = obj.properties.get('y1', obj.y)
                x2 = obj.properties.get('x2', obj.x + obj.width)
                y2 = obj.properties.get('y2', obj.y + obj.height)
                
                def distance_to_line(px, py, x1, y1, x2, y2):
                    A = px - x1
                    B = py - y1
                    C = x2 - x1
                    D = y2 - y1
                    
                    dot = A * C + B * D
                    len_sq = C * C + D * D
                    
                    if len_sq == 0:
                        return (A * A + B * B) ** 0.5
                    
                    param = max(0, min(1, dot / len_sq))
                    xx = x1 + param * C
                    yy = y1 + param * D
                    
                    dx = px - xx
                    dy = py - yy
                    return (dx * dx + dy * dy) ** 0.5
                
                if distance_to_line(x, y, x1, y1, x2, y2) <= 5:
                    clicked_obj = obj
                    break
            else:
                if (obj.x <= x <= obj.x + obj.width and 
                    obj.y <= y <= obj.y + obj.height):
                    clicked_obj = obj
                    break
        
        if clicked_obj and clicked_obj.obj_type in ['label', 'button']:
            # Start inline text editing
            self.start_inline_text_edit(clicked_obj, event.pos())
        else:
            # Call default handler
            super(QGraphicsView, self.view).mouseDoubleClickEvent(event)
    
    def start_inline_text_edit(self, obj, view_pos):
        """Start inline text editing for an object"""
        from PyQt5.QtWidgets import QLineEdit
        
        # Create line edit widget
        self.inline_editor = QLineEdit(self.view.viewport())
        self.inline_editor.setText(obj.properties.get('text', ''))
        
        # Position the editor over the object
        scene_pos = self.view.mapFromScene(obj.x, obj.y)
        editor_x = scene_pos.x()
        editor_y = scene_pos.y()
        editor_width = int(obj.width * self.current_zoom)
        editor_height = int(obj.height * self.current_zoom)
        
        self.inline_editor.setGeometry(editor_x, editor_y, editor_width, editor_height)
        
        # Style the editor to match the object
        font = QFont()
        font.setFamily(obj.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(int(obj.properties.get('font_size', 10) * self.current_zoom))
        self.inline_editor.setFont(font)
        
        text_color = obj.properties.get('text_color', '#000000')
        bg_color = obj.properties.get('background_color', '#FFFFFF')
        self.inline_editor.setStyleSheet(f"""
            QLineEdit {{
                color: {text_color};
                background-color: {bg_color};
                border: 2px solid #2196F3;
                padding: 2px;
            }}
        """)
        
        # Store reference to object being edited
        self.inline_editor_obj = obj
        
        # Connect signals
        self.inline_editor.editingFinished.connect(self.finish_inline_text_edit)
        self.inline_editor.returnPressed.connect(self.finish_inline_text_edit)
        
        # Show and focus
        self.inline_editor.show()
        self.inline_editor.setFocus()
        self.inline_editor.selectAll()
    
    def finish_inline_text_edit(self):
        """Finish inline text editing"""
        if hasattr(self, 'inline_editor') and self.inline_editor:
            new_text = self.inline_editor.text()
            if self.inline_editor_obj:
                self.save_state()
                self.inline_editor_obj.properties['text'] = new_text
                self.force_full_refresh()
                self.update_properties_panel()
            
            self.inline_editor.deleteLater()
            self.inline_editor = None
            self.inline_editor_obj = None
    
    def on_canvas_mouse_move(self, event):
        """Handle mouse move for dragging, resizing and rubber band selection"""
        pos = self.view.mapToScene(event.pos())
        x, y = int(pos.x()), int(pos.y())
        
        # Handle line endpoint dragging
        if self.dragging_line_endpoint and self.selected_object and self.selected_object.obj_type == 'line':
            x1, y1, x2, y2 = self.line_start_pos
            
            # Apply grid snapping if enabled
            if self.show_grid and self.grid_size > 0:
                x = round(x / self.grid_size) * self.grid_size
                y = round(y / self.grid_size) * self.grid_size
            
            if self.dragging_line_endpoint == 'start':
                # Update start point
                self.selected_object.properties['x1'] = x
                self.selected_object.properties['y1'] = y
                # Update bounding box
                new_x = min(x, x2)
                new_y = min(y, y2)
                self.selected_object.x = new_x
                self.selected_object.y = new_y
                self.selected_object.width = abs(x2 - x)
                self.selected_object.height = abs(y2 - y)
            elif self.dragging_line_endpoint == 'end':
                # Update end point
                self.selected_object.properties['x2'] = x
                self.selected_object.properties['y2'] = y
                # Update bounding box
                x1 = self.selected_object.properties.get('x1', 0)
                y1 = self.selected_object.properties.get('y1', 0)
                new_x = min(x1, x)
                new_y = min(y1, y)
                self.selected_object.x = new_x
                self.selected_object.y = new_y
                self.selected_object.width = abs(x - x1)
                self.selected_object.height = abs(y - y1)
            
            # Optimize: Only update selection boxes during drag, not full refresh
            self._update_selection_boxes_only()
            # Force full refresh to update line display
            self.force_full_refresh()
        elif self.rubber_band_active and self.rubber_band_start:
            # Update rubber band selection
            self.rubber_band_end = (x, y)
            self.update_rubber_band()
        elif self.selected_objects and self.dragging and not self.resizing:
            # Dragging object(s) with grid snapping
            dx = x - self.drag_start_pos[0]
            dy = y - self.drag_start_pos[1]
            
            # Apply movement to all selected objects
            for i, obj in enumerate(self.selected_objects):
                if hasattr(self, 'drag_start_positions') and obj in self.drag_start_positions:
                    # Use stored initial positions for relative positioning
                    start_x, start_y = self.drag_start_positions[obj]
                    new_x = start_x + dx
                    new_y = start_y + dy
                else:
                    # Fallback to original method if no stored positions
                    if i == 0:  # First object uses the stored drag start position
                        new_x = self.drag_start_obj_pos[0] + dx
                        new_y = self.drag_start_obj_pos[1] + dy
                    else:  # Other objects maintain relative positions
                        first_obj = self.selected_objects[0]
                        rel_x = obj.x - first_obj.x
                        rel_y = obj.y - first_obj.y
                        new_x = (self.drag_start_obj_pos[0] + dx) + rel_x
                        new_y = (self.drag_start_obj_pos[1] + dy) + rel_y
                
                # Apply grid snapping if enabled
                if self.show_grid and self.grid_size > 0:
                    new_x = round(new_x / self.grid_size) * self.grid_size
                    new_y = round(new_y / self.grid_size) * self.grid_size
                
                # Keep object within canvas bounds
                resolution = self._get_current_resolution()
                canvas_width = resolution.get('width', 1000)
                canvas_height = resolution.get('height', 600)
                new_x = max(0, min(new_x, canvas_width - obj.width))
                new_y = max(0, min(new_y, canvas_height - obj.height))
                
                # Calculate position delta for line objects
                if obj.obj_type == 'line':
                    x_delta = new_x - obj.x
                    y_delta = new_y - obj.y
                    # Update line endpoints
                    if 'x1' in obj.properties:
                        obj.properties['x1'] += x_delta
                    if 'y1' in obj.properties:
                        obj.properties['y1'] += y_delta
                    if 'x2' in obj.properties:
                        obj.properties['x2'] += x_delta
                    if 'y2' in obj.properties:
                        obj.properties['y2'] += y_delta
                
                obj.x = new_x
                obj.y = new_y
            
            # Force full refresh to update all objects including lines
            self.force_full_refresh()
        elif self.selected_object and self.resizing and len(self.selected_objects) <= 1:
            # Resizing single object with grid snapping
            # Only allow resizing when a single object is selected (the primary one)
            dx = x - self.drag_start_pos[0]
            dy = y - self.drag_start_pos[1]
            start_x, start_y, start_width, start_height = self.resize_start_rect
            
            new_x = start_x
            new_y = start_y
            new_width = start_width
            new_height = start_height
            
            # Handle different resize handles
            if self.resize_handle == 'br':  # Bottom-right corner
                new_width = max(20, start_width + dx)
                new_height = max(20, start_height + dy)
            elif self.resize_handle == 'bl':  # Bottom-left corner
                new_width = max(20, start_width - dx)
                new_height = max(20, start_height + dy)
                new_x = start_x + dx
            elif self.resize_handle == 'tr':  # Top-right corner
                new_width = max(20, start_width + dx)
                new_height = max(20, start_height - dy)
                new_y = start_y + dy
            elif self.resize_handle == 'tl':  # Top-left corner
                new_width = max(20, start_width - dx)
                new_height = max(20, start_height - dy)
                new_x = start_x + dx
                new_y = start_y + dy
            elif self.resize_handle == 'r':  # Right edge
                new_width = max(20, start_width + dx)
            elif self.resize_handle == 'l':  # Left edge
                new_width = max(20, start_width - dx)
                new_x = start_x + dx
            elif self.resize_handle == 'b':  # Bottom edge
                new_height = max(20, start_height + dy)
            elif self.resize_handle == 't':  # Top edge
                new_height = max(20, start_height - dy)
                new_y = start_y + dy
            
            # Apply grid snapping if enabled
            if self.show_grid and self.grid_size > 0:
                new_x = round(new_x / self.grid_size) * self.grid_size
                new_y = round(new_y / self.grid_size) * self.grid_size
                new_width = round(new_width / self.grid_size) * self.grid_size
                new_height = round(new_height / self.grid_size) * self.grid_size
            
            # Update object position and size
            self.selected_object.x = new_x
            self.selected_object.y = new_y
            self.selected_object.width = new_width
            self.selected_object.height = new_height
            # Optimize: Only update selection boxes during resize, not full refresh
            self._update_selection_boxes_only()
    
    def update_rubber_band(self):
        """Update the rubber band rectangle"""
        if not self.rubber_band_start or not self.rubber_band_end:
            return
        
        # Remove previous rubber band item if exists
        if self.rubber_band_item and self.rubber_band_item in self.scene.items():
            self.scene.removeItem(self.rubber_band_item)
        
        start_x, start_y = self.rubber_band_start
        end_x, end_y = self.rubber_band_end
        
        # Calculate rectangle coordinates
        x = min(start_x, end_x)
        y = min(start_y, end_y)
        width = abs(end_x - start_x)
        height = abs(end_y - start_y)
        
        # Create rubber band rectangle
        pen = QPen(QColor(51, 153, 255), 2)
        pen.setStyle(Qt.DashLine)
        brush = QBrush(QColor(51, 153, 255, 50))  # Semi-transparent blue
        
        self.rubber_band_item = self.scene.addRect(x, y, width, height, pen, brush)
    
    def on_canvas_mouse_release(self, event):
        """Handle mouse release"""
        if self.rubber_band_active:
            # Complete rubber band selection
            self.complete_rubber_band_selection()
            self.rubber_band_active = False
            self.rubber_band_start = None
            self.rubber_band_end = None
            
            # Remove rubber band visual
            if self.rubber_band_item and self.rubber_band_item in self.scene.items():
                self.scene.removeItem(self.rubber_band_item)
                self.rubber_band_item = None
            
            # Update properties panel based on current selection
            if self.selected_objects:
                # Set the last selected object as primary for property editing
                self.selected_object = self.selected_objects[-1]
            else:
                self.selected_object = None
            self.update_properties_panel()
        elif self.dragging_line_endpoint:
            # Complete line endpoint dragging
            self.dragging_line_endpoint = None
            self.line_start_pos = None
            self.update_properties_panel()
            # Force full refresh after line endpoint drag completes
            self.force_full_refresh()
        elif self.dragging or self.resizing:
            self.dragging = False
            self.resizing = False
            self.drag_start_pos = None
            self.drag_start_obj_pos = None
            if hasattr(self, 'drag_start_positions'):
                delattr(self, 'drag_start_positions')
            self.resize_start_rect = None
            self.resize_handle = None
            self.update_properties_panel()
            # Force full refresh after drag/resize completes
            self.force_full_refresh()
    
    def complete_rubber_band_selection(self):
        """Complete the rubber band selection and select objects within the rectangle"""
        if not self.rubber_band_start or not self.rubber_band_end:
            return
        
        # Get the rubber band rectangle bounds
        start_x, start_y = self.rubber_band_start
        end_x, end_y = self.rubber_band_end
        
        rubber_rect_x = min(start_x, end_x)
        rubber_rect_y = min(start_y, end_y)
        rubber_rect_width = abs(end_x - start_x)
        rubber_rect_height = abs(end_y - start_y)
        
        # Create a QRectF for intersection testing
        rubber_rect = QRectF(rubber_rect_x, rubber_rect_y, rubber_rect_width, rubber_rect_height)
        
        # Find all objects that intersect with the rubber band rectangle
        newly_selected = []
        for obj in self.objects:
            if obj.obj_type == 'line':
                # Special intersection detection for lines
                x1 = obj.properties.get('x1', obj.x)
                y1 = obj.properties.get('y1', obj.y)
                x2 = obj.properties.get('x2', obj.x + obj.width)
                y2 = obj.properties.get('y2', obj.y + obj.height)
                
                # Check if line segment intersects with rubber band rectangle
                # Simplified: check if either endpoint is inside the rectangle
                # or if line intersects any rectangle edge
                def point_in_rect(x, y, rect):
                    return rect.contains(QPointF(x, y))
                
                def line_intersects_rect(x1, y1, x2, y2, rect):
                    # Check if either endpoint is inside
                    if point_in_rect(x1, y1, rect) or point_in_rect(x2, y2, rect):
                        return True
                    
                    # Check intersection with rectangle edges
                    rect_left = rect.left()
                    rect_top = rect.top()
                    rect_right = rect.right()
                    rect_bottom = rect.bottom()
                    
                    # Check intersection with each edge
                    edges = [
                        (rect_left, rect_top, rect_right, rect_top),    # Top edge
                        (rect_right, rect_top, rect_right, rect_bottom), # Right edge
                        (rect_left, rect_bottom, rect_right, rect_bottom), # Bottom edge
                        (rect_left, rect_top, rect_left, rect_bottom)     # Left edge
                    ]
                    
                    for edge_x1, edge_y1, edge_x2, edge_y2 in edges:
                        # Calculate line intersection
                        def ccw(A, B, C):
                            return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])
                        
                        A = (x1, y1)
                        B = (x2, y2)
                        C = (edge_x1, edge_y1)
                        D = (edge_x2, edge_y2)
                        
                        if ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D):
                            return True
                    
                    return False
                
                if line_intersects_rect(x1, y1, x2, y2, rubber_rect):
                    newly_selected.append(obj)
            else:
                # Regular rectangle intersection for other objects
                obj_rect = QRectF(obj.x, obj.y, obj.width, obj.height)
                if rubber_rect.intersects(obj_rect):
                    newly_selected.append(obj)
        
        # Note: We can't access event modifiers here since this is called from mouse release
        # Instead, we'll always replace the selection with the rubber band result
        # If users want to add to selection, they should use Ctrl+click on individual items
        self.selected_objects = newly_selected
        
        # Update primary selection
        if self.selected_objects:
            self.selected_object = self.selected_objects[-1]  # Last selected becomes primary
        else:
            self.selected_object = None
            
        # Refresh display to show new selection
        self.refresh_screen_display()
    
    def draw_selection_box(self):
        """Draw selection box around selected object(s)"""
        if not self.selected_objects:
            return
        
        # Draw selection boxes for all selected objects
        for obj in self.selected_objects:
            # Draw selection rectangle
            pen = QPen(Qt.blue)
            pen.setStyle(Qt.DashLine)
            pen.setWidth(2)
            
            # Selection box
            selection_rect = QGraphicsRectItem(obj.x - 2, obj.y - 2, obj.width + 4, obj.height + 4)
            selection_rect.setPen(pen)
            selection_rect.setBrush(QBrush(Qt.NoBrush))
            selection_rect._is_selection_box = True  # Mark for optimization
            self.scene.addItem(selection_rect)
        
        # Draw resize handles only for the primary selected object
        if self.selected_object:
            obj = self.selected_object
            handle_size = 8
            
            # Bottom-right corner
            handle_br = QGraphicsRectItem(
                obj.x + obj.width - handle_size,
                obj.y + obj.height - handle_size,
                handle_size,
                handle_size
            )
            handle_br.setPen(QPen(Qt.blue))
            handle_br.setBrush(QBrush(Qt.blue))
            handle_br._is_selection_box = True  # Mark for optimization
            self.scene.addItem(handle_br)
            
            # Bottom-left corner
            handle_bl = QGraphicsRectItem(
                obj.x,
                obj.y + obj.height - handle_size,
                handle_size,
                handle_size
            )
            handle_bl.setPen(QPen(Qt.blue))
            handle_bl.setBrush(QBrush(Qt.blue))
            handle_bl._is_selection_box = True  # Mark for optimization
            self.scene.addItem(handle_bl)
            
            # Top-right corner
            handle_tr = QGraphicsRectItem(
                obj.x + obj.width - handle_size,
                obj.y,
                handle_size,
                handle_size
            )
            handle_tr.setPen(QPen(Qt.blue))
            handle_tr.setBrush(QBrush(Qt.blue))
            handle_tr._is_selection_box = True  # Mark for optimization
            self.scene.addItem(handle_tr)
            
            # Top-left corner
            handle_tl = QGraphicsRectItem(
                obj.x,
                obj.y,
                handle_size,
                handle_size
            )
            handle_tl.setPen(QPen(Qt.blue))
            handle_tl.setBrush(QBrush(Qt.blue))
            handle_tl._is_selection_box = True  # Mark for optimization
            self.scene.addItem(handle_tl)
            
            # Middle of right edge
            handle_r = QGraphicsRectItem(
                obj.x + obj.width - handle_size,
                obj.y + obj.height / 2 - handle_size / 2,
                handle_size,
                handle_size
            )
            handle_r.setPen(QPen(Qt.blue))
            handle_r.setBrush(QBrush(Qt.blue))
            handle_r._is_selection_box = True  # Mark for optimization
            self.scene.addItem(handle_r)
            
            # Middle of left edge
            handle_l = QGraphicsRectItem(
                obj.x,
                obj.y + obj.height / 2 - handle_size / 2,
                handle_size,
                handle_size
            )
            handle_l.setPen(QPen(Qt.blue))
            handle_l.setBrush(QBrush(Qt.blue))
            handle_l._is_selection_box = True  # Mark for optimization
            self.scene.addItem(handle_l)
            
            # Middle of bottom edge
            handle_b = QGraphicsRectItem(
                obj.x + obj.width / 2 - handle_size / 2,
                obj.y + obj.height - handle_size,
                handle_size,
                handle_size
            )
            handle_b.setPen(QPen(Qt.blue))
            handle_b.setBrush(QBrush(Qt.blue))
            handle_b._is_selection_box = True  # Mark for optimization
            self.scene.addItem(handle_b)
            
            # Middle of top edge
            handle_t = QGraphicsRectItem(
                obj.x + obj.width / 2 - handle_size / 2,
                obj.y,
                handle_size,
                handle_size
            )
            handle_t.setPen(QPen(Qt.blue))
            handle_t.setBrush(QBrush(Qt.blue))
            handle_t._is_selection_box = True  # Mark for optimization
            self.scene.addItem(handle_t)
    
    def select_object(self, obj):
        """Select an object"""
        self.selected_object = obj
        self.update_properties_panel()
    
    def _hide_all_property_content(self):
        """Hide all property panel content when no object is selected"""
        # Hide the tab widget
        if hasattr(self, 'props_tab_widget'):
            self.props_tab_widget.setVisible(False)
    
    def _show_all_property_content(self):
        """Show all property panel content when object(s) are selected"""
        # Show the tab widget
        if hasattr(self, 'props_tab_widget'):
            self.props_tab_widget.setVisible(True)
    
    def update_properties_panel(self):
        """Update the properties panel based on selected object(s)"""
        # Set flag to prevent property changes during panel update
        self._updating_properties_panel = True
        
        try:
            # Update status bar with selected object information
            self.update_status_bar()
            
            # Hide all property content if no objects selected
            if not self.selected_objects:
                self._hide_all_property_content()
                return
            
            # Show property content when objects are selected
            self._show_all_property_content()
            
            # Check if multiple objects are selected
            if len(self.selected_objects) > 1:
                # Multiple objects selected
                
                # Show common properties that can be edited for multiple objects
                # For multiple selection, we'll show a simplified interface
                first_obj = self.selected_objects[0]
                self._block_signals_and_update(self.x_spin, int(first_obj.x))
                self._block_signals_and_update(self.y_spin, int(first_obj.y))
                self._block_signals_and_update(self.width_spin, int(first_obj.width))
                self._block_signals_and_update(self.height_spin, int(first_obj.height))
                self._block_signals_and_update(self.font_size_spin, first_obj.properties.get('font_size', 10))
                
                # Update text - show combined information as placeholder
                self.text_edit.blockSignals(True)
                self.text_edit.clear()
                self.text_edit.setPlaceholderText(f"已选{len(self.selected_objects)}个对象")
                self.text_edit.setEnabled(False)
                self.text_edit.blockSignals(False)
                
                # Show appropriate UI elements for multi-selection
                if first_obj.obj_type == 'label':
                    self.border_checkbox.setVisible(True)
                else:
                    self.border_checkbox.setVisible(False)
                
                # Hide action group for multi-selection since it might vary between objects
                if hasattr(self, 'var_op_group'):
                    self.var_op_group.setVisible(False)
                
                # Update advanced properties for multi-selection
                self.update_advanced_properties()
            
                # Update variable info display
                self.update_variable_info_display()
                
                # Update visibility panel
                self.update_visibility_panel()
            else:
                # Single object selected - make sure it exists
                if not self.selected_object:
                    return
                
                # Single object selected
                obj = self.selected_object
                obj_type = obj.obj_type.capitalize()
                
                props = obj.properties
                
                # Update position and size
                self._block_signals_and_update(self.x_spin, int(obj.x))
                self._block_signals_and_update(self.y_spin, int(obj.y))
                self._block_signals_and_update(self.width_spin, int(obj.width))
                self._block_signals_and_update(self.height_spin, int(obj.height))
                
                # Update basic properties
                self.text_edit.setEnabled(True)
                self.text_edit.setPlaceholderText("")
                self._block_text_signals_and_update(self.text_edit, props.get('text', ''))
                self._block_signals_and_update(self.font_size_spin, props.get('font_size', 10))
                
                # Update font family
                self.font_family_combo.blockSignals(True)
                font_family = props.get('font_family', 'Microsoft YaHei')
                idx = self.font_family_combo.findText(font_family)
                if idx >= 0:
                    self.font_family_combo.setCurrentIndex(idx)
                else:
                    self.font_family_combo.setEditText(font_family)
                self.font_family_combo.blockSignals(False)
                
                # Update font style checkboxes
                self.font_bold_checkbox.blockSignals(True)
                self.font_bold_checkbox.setChecked(props.get('font_bold', False))
                self.font_bold_checkbox.blockSignals(False)
                
                self.font_italic_checkbox.blockSignals(True)
                self.font_italic_checkbox.setChecked(props.get('font_italic', False))
                self.font_italic_checkbox.blockSignals(False)
                
                self.font_underline_checkbox.blockSignals(True)
                self.font_underline_checkbox.setChecked(props.get('font_underline', False))
                self.font_underline_checkbox.blockSignals(False)
                
                # Update text color button
                text_color = props.get('text_color', '#000000')
                self.text_color_button.setStyleSheet(f"background-color: {text_color}; color: black;")
                
                # Update text alignment
                h_align = props.get('text_h_align', 'center')
                v_align = props.get('text_v_align', 'middle')
                h_align_map = {"left": "左对齐", "center": "居中", "right": "右对齐"}
                v_align_map = {"top": "顶部", "middle": "居中", "bottom": "底部"}
                
                self.text_h_align_combo.blockSignals(True)
                self.text_h_align_combo.setCurrentText(h_align_map.get(h_align, "居中"))
                self.text_h_align_combo.blockSignals(False)
                
                self.text_v_align_combo.blockSignals(True)
                self.text_v_align_combo.setCurrentText(v_align_map.get(v_align, "居中"))
                self.text_v_align_combo.blockSignals(False)
                
                # Update border checkbox and background color for label
                if obj.obj_type == 'label':
                    self.border_checkbox.blockSignals(True)
                    self.border_checkbox.setChecked(props.get('border', False))
                    self.border_checkbox.blockSignals(False)
                    self.border_checkbox.setVisible(True)
                    
                    # Update background color button
                    bg_color = props.get('background_color', '')
                    if bg_color:
                        self.label_bg_color_button.setStyleSheet(f"background-color: {bg_color}; color: black;")
                    else:
                        self.label_bg_color_button.setStyleSheet("")
                    self.label_bg_color_button.setVisible(True)
                else:
                    self.border_checkbox.setVisible(False)
                    self.label_bg_color_button.setVisible(False)
                
                # Configure property visibility based on control type
                self._configure_property_visibility(obj.obj_type)
                
                # Update action settings for buttons and switches
                if obj.obj_type in ['button', 'switch']:
                    # Update switch text settings
                    if obj.obj_type == 'switch':
                        self.switch_on_text_edit.blockSignals(True)
                        self.switch_on_text_edit.setText(props.get('on_text', '开'))
                        self.switch_on_text_edit.blockSignals(False)
                        
                        self.switch_off_text_edit.blockSignals(True)
                        self.switch_off_text_edit.setText(props.get('off_text', '关'))
                        self.switch_off_text_edit.blockSignals(False)
                        
                        text_color = props.get('text_color', '#FFFFFF')
                        self.switch_text_color_button.setStyleSheet(f"background-color: {text_color}; color: black;")
                    
                    # Get action type first (needed for on_action_type_change)
                    action_type = props.get('action_type', '无')
                    
                    # Map action_type to combo text
                    if action_type == '画面跳转':
                        action_text = '画面跳转'
                    elif action_type == 'custom' or action_type == '无':
                        action_text = '无'
                    else:
                        # Variable operation
                        action_text = '变量操作'
                    
                    # Update action combo (动作: 无/变量操作/画面跳转)
                    if hasattr(self, 'action_combo'):
                        self.action_combo.blockSignals(True)
                        
                        idx = self.action_combo.findText(action_text)
                        if idx >= 0:
                            self.action_combo.setCurrentIndex(idx)
                        self.action_combo.blockSignals(False)
                    
                    # Update action operation combo (操作: 置位/复位/取反等)
                    if hasattr(self, 'var_operation_combo'):
                        self.var_operation_combo.blockSignals(True)
                        var_operation = props.get('variable_operation', '置位')
                        
                        idx = self.var_operation_combo.findText(var_operation)
                        if idx >= 0:
                            self.var_operation_combo.setCurrentIndex(idx)
                        self.var_operation_combo.blockSignals(False)
                    
                    # Show/hide relevant widgets based on action type
                    # Pass update_property=False to avoid modifying the object during panel update
                    self.on_action_type_change(action_text, update_property=False)
                    
                    # Refresh and set target screen
                    if hasattr(self, 'target_screen_combo'):
                        self.refresh_target_screens()
                        self.target_screen_combo.blockSignals(True)
                        target_screen = props.get('target_screen', '')
                        if target_screen:
                            idx = self.target_screen_combo.findText(target_screen)
                            if idx >= 0:
                                self.target_screen_combo.setCurrentIndex(idx)
                            else:
                                self.target_screen_combo.setEditText(target_screen)
                        self.target_screen_combo.blockSignals(False)
                    
                    # Update target screen number
                    if hasattr(self, 'target_screen_number_spin'):
                        self.target_screen_number_spin.blockSignals(True)
                        self.target_screen_number_spin.setValue(props.get('target_screen_number', 0))
                        self.target_screen_number_spin.blockSignals(False)
                
                elif obj.obj_type == 'dropdown':
                    # Dropdown properties are now handled in update_advanced_properties
                    pass
                
                elif obj.obj_type in ['input', 'gauge']:
                    # Update range settings
                    self.min_val_spin.blockSignals(True)
                    self.min_val_spin.setValue(props.get('min_val', 0))
                    self.min_val_spin.blockSignals(False)
                    
                    self.max_val_spin.blockSignals(True)
                    self.max_val_spin.setValue(props.get('max_val', 100))
                    self.max_val_spin.blockSignals(False)
                    
                    self.default_val_spin.blockSignals(True)
                    self.default_val_spin.setValue(props.get('value', 0))
                    self.default_val_spin.blockSignals(False)
                
                elif obj.obj_type == 'checkbox':
                    # Update checkbox settings
                    self.checked_val_spin.blockSignals(True)
                    self.checked_val_spin.setValue(props.get('checked_value', 1))
                    self.checked_val_spin.blockSignals(False)
                    
                    self.unchecked_val_spin.blockSignals(True)
                    self.unchecked_val_spin.setValue(props.get('unchecked_value', 0))
                    self.unchecked_val_spin.blockSignals(False)
                
                # Update advanced properties
                self.update_advanced_properties()
                
                # Update variable info display
                self.update_variable_info_display()
                
                # Update visibility panel
                self.update_visibility_panel()
        finally:
            # Clear flag after panel update is complete
            self._updating_properties_panel = False
    
    def _configure_property_visibility(self, obj_type):
        """Configure which property groups are visible based on control type"""
        # Hide all control-specific groups first
        self.var_op_group.setVisible(False)
        self.dropdown_options_group.setVisible(False)
        self.range_group.setVisible(False)
        self.checkbox_group.setVisible(False)
        self.text_group.setVisible(True)  # Text group is visible by default
        self.switch_text_group.setVisible(False)  # Hide switch text group by default
        self.text_list_group.setVisible(False)  # Hide text list group by default
        
        # Hide all advanced groups
        self.dropdown_options_group.setVisible(False)
        self.text_list_group.setVisible(False)
        self.button_colors_group.setVisible(False)
        self.label_format_group.setVisible(False)
        self.graphics_group.setVisible(False)
        self.light_group.setVisible(False)
        self.picture_group.setVisible(False)
        self.picture_list_group.setVisible(False)
        self.progress_group.setVisible(False)
        self.trend_group.setVisible(False)
        self.history_trend_group.setVisible(False)
        
        # Show groups based on control type
        if obj_type == 'button':
            self.var_op_group.setVisible(True)
            self.button_colors_group.setVisible(True)
        elif obj_type == 'switch':
            # Switch shows color settings and text settings
            self.button_colors_group.setVisible(True)
            self.switch_text_group.setVisible(True)
        elif obj_type == 'dropdown':
            # Dropdown options in advanced properties
            self.dropdown_options_group.setVisible(True)
        elif obj_type == 'gauge':
            self.range_group.setVisible(True)
        elif obj_type == 'input':
            self.range_group.setVisible(True)
            self.text_group.setVisible(False)  # Input doesn't need text content
        elif obj_type == 'checkbox':
            self.checkbox_group.setVisible(True)
        elif obj_type == 'label':
            self.label_format_group.setVisible(True)
            self.border_checkbox.setVisible(True)
        elif obj_type in ['line', 'rectangle', 'circle']:
            self.graphics_group.setVisible(True)
            self.text_group.setVisible(False)  # Graphics don't need text
        elif obj_type == 'light':
            self.light_group.setVisible(True)
            self.text_group.setVisible(True)  # Light uses text_group for text input
        elif obj_type == 'picture':
            self.picture_group.setVisible(True)
        elif obj_type == 'picture_list':
            self.picture_list_group.setVisible(True)
            self.text_group.setVisible(False)
        elif obj_type == 'progress':
            self.range_group.setVisible(True)
            self.progress_group.setVisible(True)
        elif obj_type == 'trend_chart':
            self.trend_group.setVisible(True)
        elif obj_type == 'history_trend':
            self.history_trend_group.setVisible(True)
        elif obj_type == 'text_list':
            # Text list properties are shown in advanced tab
            pass

    def update_text_list_properties(self):
        """Update text list properties panel"""
        if not self.selected_object or self.selected_object.obj_type != 'text_list':
            return
        
        props = self.selected_object.properties
        
        # Block signals to prevent triggering updates
        self.text_list_table.blockSignals(True)
        self.text_list_item_height_spin.blockSignals(True)
        self.text_list_selected_spin.blockSignals(True)
        self.text_list_display_mode_combo.blockSignals(True)
        self.text_list_default_text_edit.blockSignals(True)
        
        # Update display mode
        display_mode = props.get('display_mode', 'list')
        self.text_list_display_mode_combo.setCurrentText("列表模式" if display_mode == 'list' else "单行模式")
        
        # Bind mode is always 'value' for text list (removed index mode selection)
        # Ensure bind_mode is set to 'value' if not already set
        if 'bind_mode' not in props:
            props['bind_mode'] = 'value'
        
        # Update table with items (support both old and new format)
        items = props.get('items', [])
        self.text_list_table.setRowCount(len(items))
        for i, item in enumerate(items):
            if isinstance(item, dict):
                # New format: {'value': '0', 'text': '停止'}
                value_item = QTableWidgetItem(item.get('value', str(i)))
                text_item = QTableWidgetItem(item.get('text', ''))
            else:
                # Old format: just a string
                value_item = QTableWidgetItem(str(i))
                text_item = QTableWidgetItem(str(item))
            self.text_list_table.setItem(i, 0, value_item)
            self.text_list_table.setItem(i, 1, text_item)
        
        # Update settings
        self.text_list_item_height_spin.setValue(props.get('item_height', 25))
        self.text_list_selected_spin.setValue(props.get('selected_index', -1))
        self.text_list_default_text_edit.setText(props.get('default_text', ''))
        
        # Unblock signals
        self.text_list_table.blockSignals(False)
        self.text_list_item_height_spin.blockSignals(False)
        self.text_list_selected_spin.blockSignals(False)
        self.text_list_display_mode_combo.blockSignals(False)
        self.text_list_default_text_edit.blockSignals(False)

    def on_text_list_item_changed(self, item):
        """Handle text list table item change"""
        if not self.selected_object or self.selected_object.obj_type != 'text_list':
            return
        
        # Get all items from table (value-text pairs)
        items = []
        for row in range(self.text_list_table.rowCount()):
            value_item = self.text_list_table.item(row, 0)
            text_item = self.text_list_table.item(row, 1)
            value = value_item.text() if value_item else str(row)
            text = text_item.text() if text_item else ''
            items.append({'value': value, 'text': text})
        
        self.selected_object.properties['items'] = items
        self.save_state()
        self.force_full_refresh()

    def on_text_list_bind_mode_changed(self, text):
        """Handle text list bind mode change"""
        if not self.selected_object or self.selected_object.obj_type != 'text_list':
            return
        
        bind_mode = 'index' if text == "索引模式" else 'value'
        self.selected_object.properties['bind_mode'] = bind_mode
        self.save_state()

    def on_text_list_display_mode_changed(self, text):
        """Handle text list display mode change"""
        if not self.selected_object or self.selected_object.obj_type != 'text_list':
            return
        
        display_mode = 'list' if text == "列表模式" else 'single'
        self.selected_object.properties['display_mode'] = display_mode
        self.save_state()
        self.force_full_refresh()

    def on_text_list_default_text_changed(self):
        """Handle text list default text change"""
        if not self.selected_object or self.selected_object.obj_type != 'text_list':
            return
        
        default_text = self.text_list_default_text_edit.text()
        self.selected_object.properties['default_text'] = default_text
        self.save_state()
        self.force_full_refresh()

    def on_text_list_add_item(self):
        """Add a new item to text list"""
        if not self.selected_object or self.selected_object.obj_type != 'text_list':
            return
        
        row_count = self.text_list_table.rowCount()
        self.text_list_table.insertRow(row_count)
        
        # Add value and text columns
        value_item = QTableWidgetItem(str(row_count))
        text_item = QTableWidgetItem(f'Item {row_count}')
        self.text_list_table.setItem(row_count, 0, value_item)
        self.text_list_table.setItem(row_count, 1, text_item)
        
        # Update properties
        items = self.selected_object.properties.get('items', [])
        items.append({'value': str(row_count), 'text': f'Item {row_count}'})
        self.selected_object.properties['items'] = items
        self.save_state()
        self.force_full_refresh()

    def on_text_list_remove_item(self):
        """Remove selected item from text list"""
        if not self.selected_object or self.selected_object.obj_type != 'text_list':
            return
        
        current_row = self.text_list_table.currentRow()
        if current_row >= 0:
            self.text_list_table.removeRow(current_row)
            
            # Update properties
            items = self.selected_object.properties.get('items', [])
            if current_row < len(items):
                items.pop(current_row)
                self.selected_object.properties['items'] = items
                self.save_state()
                self.force_full_refresh()

    # === Dropdown Event Handlers ===
    def on_dropdown_item_changed(self, item):
        """Handle dropdown table item change"""
        if not self.selected_object or self.selected_object.obj_type != 'dropdown':
            return
        
        # Get all items from table (value-text pairs)
        items = []
        for row in range(self.dropdown_table.rowCount()):
            value_item = self.dropdown_table.item(row, 0)
            text_item = self.dropdown_table.item(row, 1)
            value = value_item.text() if value_item else str(row)
            text = text_item.text() if text_item else ''
            items.append({'value': value, 'text': text})
        
        self.selected_object.properties['items'] = items
        self.save_state()
        self.force_full_refresh()
    
    def on_dropdown_bind_mode_changed(self, text):
        """Handle dropdown bind mode change"""
        if not self.selected_object or self.selected_object.obj_type != 'dropdown':
            return
        
        bind_mode = 'index' if text == "索引模式" else 'value'
        self.selected_object.properties['bind_mode'] = bind_mode
        self.save_state()
    
    def on_dropdown_add_item(self):
        """Add new item to dropdown"""
        if not self.selected_object or self.selected_object.obj_type != 'dropdown':
            return
        
        current_row_count = self.dropdown_table.rowCount()
        self.dropdown_table.blockSignals(True)
        self.dropdown_table.setRowCount(current_row_count + 1)
        
        value_item = QTableWidgetItem(str(current_row_count))
        text_item = QTableWidgetItem(f'Item {current_row_count + 1}')
        
        self.dropdown_table.setItem(current_row_count, 0, value_item)
        self.dropdown_table.setItem(current_row_count, 1, text_item)
        self.dropdown_table.blockSignals(False)
        
        # Update properties
        items = self.selected_object.properties.get('items', [])
        items.append({'value': str(current_row_count), 'text': f'Item {current_row_count + 1}'})
        self.selected_object.properties['items'] = items
        self.save_state()
        self.force_full_refresh()
    
    def on_dropdown_remove_item(self):
        """Remove selected item from dropdown"""
        if not self.selected_object or self.selected_object.obj_type != 'dropdown':
            return
        
        current_row = self.dropdown_table.currentRow()
        if current_row >= 0:
            self.dropdown_table.removeRow(current_row)
            
            # Update properties
            items = self.selected_object.properties.get('items', [])
            if current_row < len(items):
                items.pop(current_row)
                self.selected_object.properties['items'] = items
                self.save_state()
                self.force_full_refresh()

    def update_advanced_properties(self):
        """Update advanced properties specific to object type"""
        if not self.selected_object:
            return
        
        obj_type = self.selected_object.obj_type
        props = self.selected_object.properties
        
        # Update button-specific advanced properties
        if obj_type in ['button', 'switch']:
            self.on_color_button.blockSignals(True)
            self.off_color_button.blockSignals(True)
            
            self.on_color_button.setStyleSheet(f"background-color: {props.get('on_color', '#4CAF50')}; color: black;")
            self.off_color_button.setStyleSheet(f"background-color: {props.get('off_color', '#CCCCCC')}; color: black;")
            
            self.on_color_button.blockSignals(False)
            self.off_color_button.blockSignals(False)
        
        # Update label-specific advanced properties
        if obj_type == 'label':
            self.format_edit.blockSignals(True)
            self.unit_edit.blockSignals(True)
            self.precision_spin.blockSignals(True)
            
            self.format_edit.setText(props.get('display_format', '{}'))
            self.unit_edit.setText(props.get('unit', ''))
            self.precision_spin.setValue(props.get('precision', 2))
            
            self.format_edit.blockSignals(False)
            self.unit_edit.blockSignals(False)
            self.precision_spin.blockSignals(False)
        
        # Update graphics-specific advanced properties
        if obj_type in ['line', 'rectangle', 'circle']:
            self.line_width_spin.blockSignals(True)
            self.line_width_spin.setValue(props.get('line_width', 2))
            self.line_width_spin.blockSignals(False)
            
            self.line_color_button.blockSignals(True)
            self.line_color_button.setStyleSheet(f"background-color: {props.get('color', '#000000')}; color: black;")
            self.line_color_button.blockSignals(False)
            
            if obj_type in ['rectangle', 'circle']:
                self.filled_checkbox.blockSignals(True)
                self.filled_checkbox.setChecked(props.get('filled', False))
                self.filled_checkbox.blockSignals(False)
                
                self.fill_color_button.blockSignals(True)
                self.fill_color_button.setStyleSheet(f"background-color: {props.get('fill_color', '#FFFFFF')}; color: black;")
                self.fill_color_button.blockSignals(False)
        
        # Update picture-specific advanced properties
        if obj_type == 'picture':
            self.image_path_edit.blockSignals(True)
            self.image_path_edit.setText(props.get('image_path', ''))
            self.image_path_edit.blockSignals(False)
            
            self.keep_aspect_checkbox.blockSignals(True)
            self.keep_aspect_checkbox.setChecked(props.get('keep_aspect_ratio', True))
            self.keep_aspect_checkbox.blockSignals(False)
        
        # Update picture list-specific advanced properties
        if obj_type == 'picture_list':
            value_type = props.get('value_type', 'integer')
            type_map = {'integer': '整数', 'float': '浮点数', 'bool': '布尔', 'string': '字符串'}
            self.pl_value_type_combo.blockSignals(True)
            self.pl_value_type_combo.setCurrentText(type_map.get(value_type, '整数'))
            self.pl_value_type_combo.blockSignals(False)
            
            self.pl_keep_aspect_cb.blockSignals(True)
            self.pl_keep_aspect_cb.setChecked(props.get('keep_aspect_ratio', True))
            self.pl_keep_aspect_cb.blockSignals(False)
            
            self.pl_show_border_cb.blockSignals(True)
            self.pl_show_border_cb.setChecked(props.get('border_visible', True))
            self.pl_show_border_cb.blockSignals(False)
            
            self.pl_show_value_cb.blockSignals(True)
            self.pl_show_value_cb.setChecked(props.get('show_value_label', False))
            self.pl_show_value_cb.blockSignals(False)
            
            self.pl_default_image_edit.blockSignals(True)
            self.pl_default_image_edit.setText(props.get('default_image', ''))
            self.pl_default_image_edit.blockSignals(False)
            
            self.update_picture_list_states_table()
        
        # Update light-specific advanced properties
        if obj_type == 'light':
            # Shape
            self.light_shape_combo.blockSignals(True)
            shape_map = {'circle': '圆形', 'square': '方形', 'rectangle': '矩形'}
            self.light_shape_combo.setCurrentText(shape_map.get(props.get('shape', 'circle'), '圆形'))
            self.light_shape_combo.blockSignals(False)
            
            # Text color (text is now in basic properties text_edit)
            self.light_text_color_button.blockSignals(True)
            text_color = props.get('text_color', '#000000')
            self.light_text_color_button.setStyleSheet(f"background-color: {text_color}; color: {'white' if text_color.lower() > '#888888' else 'black'};")
            self.light_text_color_button.blockSignals(False)
            
            # On/Off colors
            self.light_on_color_button.blockSignals(True)
            on_color = props.get('on_color', '#00FF00')
            self.light_on_color_button.setStyleSheet(f"background-color: {on_color}; color: {'white' if on_color.lower() > '#888888' else 'black'};")
            self.light_on_color_button.blockSignals(False)
            
            self.light_off_color_button.blockSignals(True)
            off_color = props.get('off_color', '#808080')
            self.light_off_color_button.setStyleSheet(f"background-color: {off_color}; color: {'white' if off_color.lower() > '#888888' else 'black'};")
            self.light_off_color_button.blockSignals(False)
            
            # Border
            self.light_border_checkbox.blockSignals(True)
            self.light_border_checkbox.setChecked(props.get('border', True))
            self.light_border_checkbox.blockSignals(False)
            
            # Use image
            self.light_use_image_checkbox.blockSignals(True)
            use_image = props.get('use_image', False)
            self.light_use_image_checkbox.setChecked(use_image)
            self.light_use_image_checkbox.blockSignals(False)
            
            # Enable/disable image controls
            self.light_on_image_edit.setEnabled(use_image)
            self.light_on_image_btn.setEnabled(use_image)
            self.light_off_image_edit.setEnabled(use_image)
            self.light_off_image_btn.setEnabled(use_image)
            
            # Image paths
            self.light_on_image_edit.blockSignals(True)
            on_image = props.get('on_image', '')
            self.light_on_image_edit.setText(os.path.basename(on_image) if on_image else '')
            self.light_on_image_edit.blockSignals(False)
            
            self.light_off_image_edit.blockSignals(True)
            off_image = props.get('off_image', '')
            self.light_off_image_edit.setText(os.path.basename(off_image) if off_image else '')
            self.light_off_image_edit.blockSignals(False)

        # Update progress bar-specific advanced properties
        if obj_type == 'progress':
            # Orientation
            self.progress_orientation_combo.blockSignals(True)
            orientation_map = {'horizontal': '水平', 'vertical': '垂直'}
            self.progress_orientation_combo.setCurrentText(orientation_map.get(props.get('orientation', 'horizontal'), '水平'))
            self.progress_orientation_combo.blockSignals(False)

            # Colors
            self.progress_bar_color_button.blockSignals(True)
            bar_color = props.get('bar_color', '#4CAF50')
            self.progress_bar_color_button.setStyleSheet(f"background-color: {bar_color}; color: black;")
            self.progress_bar_color_button.blockSignals(False)

            self.progress_bg_color_button.blockSignals(True)
            bg_color = props.get('bg_color', '#EEEEEE')
            self.progress_bg_color_button.setStyleSheet(f"background-color: {bg_color}; color: black;")
            self.progress_bg_color_button.blockSignals(False)

            self.progress_border_color_button.blockSignals(True)
            border_color = props.get('border_color', '#000000')
            self.progress_border_color_button.setStyleSheet(f"background-color: {border_color}; color: black;")
            self.progress_border_color_button.blockSignals(False)

            self.progress_text_color_button.blockSignals(True)
            text_color = props.get('text_color', '#000000')
            self.progress_text_color_button.setStyleSheet(f"background-color: {text_color}; color: black;")
            self.progress_text_color_button.blockSignals(False)

            # Border settings
            self.progress_border_width_spin.blockSignals(True)
            self.progress_border_width_spin.setValue(props.get('border_width', 1))
            self.progress_border_width_spin.blockSignals(False)

            self.progress_border_radius_spin.blockSignals(True)
            self.progress_border_radius_spin.setValue(props.get('border_radius', 0))
            self.progress_border_radius_spin.blockSignals(False)

            # Text display options
            self.progress_show_value_checkbox.blockSignals(True)
            self.progress_show_value_checkbox.setChecked(props.get('show_value', True))
            self.progress_show_value_checkbox.blockSignals(False)

            self.progress_show_percentage_checkbox.blockSignals(True)
            self.progress_show_percentage_checkbox.setChecked(props.get('show_percentage', False))
            self.progress_show_percentage_checkbox.blockSignals(False)

            # Text position
            self.progress_text_position_combo.blockSignals(True)
            position_map = {'center': '居中', 'left': '左侧', 'right': '右侧', 'top': '顶部', 'bottom': '底部'}
            self.progress_text_position_combo.setCurrentText(position_map.get(props.get('text_position', 'center'), '居中'))
            self.progress_text_position_combo.blockSignals(False)

            # Font size
            self.progress_font_size_spin.blockSignals(True)
            self.progress_font_size_spin.setValue(props.get('font_size', 10))
            self.progress_font_size_spin.blockSignals(False)

            # Gradient
            self.progress_gradient_checkbox.blockSignals(True)
            self.progress_gradient_checkbox.setChecked(props.get('bar_gradient', False))
            self.progress_gradient_checkbox.blockSignals(False)
        
        # Update trend chart-specific advanced properties
        if obj_type == 'trend_chart':
            self.trend_title_edit.blockSignals(True)
            self.trend_title_edit.setText(props.get('title', '趋势图'))
            self.trend_title_edit.blockSignals(False)

            self.trend_title_visible_checkbox.blockSignals(True)
            self.trend_title_visible_checkbox.setChecked(props.get('title_visible', True))
            self.trend_title_visible_checkbox.blockSignals(False)

            self.trend_title_color_button.blockSignals(True)
            title_color = props.get('title_color', '#000000')
            self.trend_title_color_button.setStyleSheet(f"background-color: {title_color}; color: white;")
            self.trend_title_color_button.blockSignals(False)

            self.trend_y_min_spin.blockSignals(True)
            self.trend_y_min_spin.setValue(props.get('y_min', 0))
            self.trend_y_min_spin.blockSignals(False)

            self.trend_y_max_spin.blockSignals(True)
            self.trend_y_max_spin.setValue(props.get('y_max', 100))
            self.trend_y_max_spin.blockSignals(False)

            self.trend_auto_scale_checkbox.blockSignals(True)
            self.trend_auto_scale_checkbox.setChecked(props.get('y_auto_scale', True))
            self.trend_auto_scale_checkbox.blockSignals(False)

            self.trend_time_span_spin.blockSignals(True)
            self.trend_time_span_spin.setValue(props.get('time_span', 3600))
            self.trend_time_span_spin.blockSignals(False)

            self.trend_update_interval_spin.blockSignals(True)
            self.trend_update_interval_spin.setValue(props.get('update_interval', 1000))
            self.trend_update_interval_spin.blockSignals(False)

            self.trend_bg_color_button.blockSignals(True)
            bg_color = props.get('bg_color', '#FFFFFF')
            self.trend_bg_color_button.setStyleSheet(f"background-color: {bg_color}; color: black;")
            self.trend_bg_color_button.blockSignals(False)

            self.trend_grid_color_button.blockSignals(True)
            grid_color = props.get('grid_color', '#E0E0E0')
            self.trend_grid_color_button.setStyleSheet(f"background-color: {grid_color}; color: black;")
            self.trend_grid_color_button.blockSignals(False)

            self.trend_grid_visible_checkbox.blockSignals(True)
            self.trend_grid_visible_checkbox.setChecked(props.get('grid_visible', True))
            self.trend_grid_visible_checkbox.blockSignals(False)

            self.trend_line_width_spin.blockSignals(True)
            self.trend_line_width_spin.setValue(props.get('line_width', 2))
            self.trend_line_width_spin.blockSignals(False)

            self.trend_show_legend_checkbox.blockSignals(True)
            self.trend_show_legend_checkbox.setChecked(props.get('show_legend', True))
            self.trend_show_legend_checkbox.blockSignals(False)
            
            # Update trend chart variables list
            self.update_trend_vars_list()
        
        # Update history trend chart-specific advanced properties
        if obj_type == 'history_trend':
            self.htrend_title_edit.blockSignals(True)
            self.htrend_title_edit.setText(props.get('title', '历史趋势图'))
            self.htrend_title_edit.blockSignals(False)

            self.htrend_title_visible_checkbox.blockSignals(True)
            self.htrend_title_visible_checkbox.setChecked(props.get('title_visible', True))
            self.htrend_title_visible_checkbox.blockSignals(False)

            self.htrend_title_color_button.blockSignals(True)
            title_color = props.get('title_color', '#000000')
            self.htrend_title_color_button.setStyleSheet(f"background-color: {title_color}; color: white;")
            self.htrend_title_color_button.blockSignals(False)

            self.htrend_title_font_spin.blockSignals(True)
            self.htrend_title_font_spin.setValue(props.get('title_font_size', 12))
            self.htrend_title_font_spin.blockSignals(False)

            self.htrend_control_font_spin.blockSignals(True)
            self.htrend_control_font_spin.setValue(props.get('control_font_size', 11))
            self.htrend_control_font_spin.blockSignals(False)

            self.htrend_y_min_spin.blockSignals(True)
            self.htrend_y_min_spin.setValue(props.get('y_min', 0))
            self.htrend_y_min_spin.blockSignals(False)

            self.htrend_y_max_spin.blockSignals(True)
            self.htrend_y_max_spin.setValue(props.get('y_max', 100))
            self.htrend_y_max_spin.blockSignals(False)

            self.htrend_auto_scale_checkbox.blockSignals(True)
            self.htrend_auto_scale_checkbox.setChecked(props.get('y_auto_scale', True))
            self.htrend_auto_scale_checkbox.blockSignals(False)

            self.htrend_bg_color_button.blockSignals(True)
            bg_color = props.get('bg_color', '#FFFFFF')
            self.htrend_bg_color_button.setStyleSheet(f"background-color: {bg_color}; color: black;")
            self.htrend_bg_color_button.blockSignals(False)

            self.htrend_grid_color_button.blockSignals(True)
            grid_color = props.get('grid_color', '#E0E0E0')
            self.htrend_grid_color_button.setStyleSheet(f"background-color: {grid_color}; color: black;")
            self.htrend_grid_color_button.blockSignals(False)

            self.htrend_grid_visible_checkbox.blockSignals(True)
            self.htrend_grid_visible_checkbox.setChecked(props.get('grid_visible', True))
            self.htrend_grid_visible_checkbox.blockSignals(False)

            self.htrend_line_width_spin.blockSignals(True)
            self.htrend_line_width_spin.setValue(props.get('line_width', 2))
            self.htrend_line_width_spin.blockSignals(False)

            self.htrend_show_legend_checkbox.blockSignals(True)
            self.htrend_show_legend_checkbox.setChecked(props.get('show_legend', True))
            self.htrend_show_legend_checkbox.blockSignals(False)

            self.htrend_border_color_button.blockSignals(True)
            border_color = props.get('border_color', '#000000')
            self.htrend_border_color_button.setStyleSheet(f"background-color: {border_color}; color: black;")
            self.htrend_border_color_button.blockSignals(False)

            self.htrend_border_width_spin.blockSignals(True)
            self.htrend_border_width_spin.setValue(props.get('border_width', 1))
            self.htrend_border_width_spin.blockSignals(False)
        
        # Update dropdown-specific advanced properties
        if obj_type == 'dropdown':
            self.dropdown_options_group.setVisible(True)
            # Update dropdown options table
            items = props.get('items', [{'value': '0', 'text': 'Item 1'}, {'value': '1', 'text': 'Item 2'}, {'value': '2', 'text': 'Item 3'}])
            self.dropdown_table.blockSignals(True)
            self.dropdown_table.setRowCount(len(items))
            
            for row, item in enumerate(items):
                if isinstance(item, dict):
                    value_item = QTableWidgetItem(str(item.get('value', str(row))))
                    text_item = QTableWidgetItem(str(item.get('text', f'Item {row+1}')))
                else:
                    value_item = QTableWidgetItem(str(row))
                    text_item = QTableWidgetItem(str(item))
                
                self.dropdown_table.setItem(row, 0, value_item)
                self.dropdown_table.setItem(row, 1, text_item)
            
            self.dropdown_table.blockSignals(False)
            
            # Bind mode is always 'value' for dropdown (removed UI selection)
            # Ensure bind_mode is set to 'value' if not already set
            if 'bind_mode' not in props:
                props['bind_mode'] = 'value'
        else:
            self.dropdown_options_group.setVisible(False)
        
        # Update text list-specific advanced properties
        if obj_type == 'text_list':
            self.text_list_group.setVisible(True)
            self.update_text_list_properties()
        else:
            self.text_list_group.setVisible(False)
        
        # Update clock-specific advanced properties
        if obj_type == 'clock':
            self.clock_settings_group.setVisible(True)
            
            props = self.selected_object.properties
            
            # Block signals to prevent triggering updates
            self.clock_style_combo.blockSignals(True)
            self.clock_show_date_checkbox.blockSignals(True)
            self.clock_show_time_checkbox.blockSignals(True)
            self.clock_show_seconds_checkbox.blockSignals(True)
            self.clock_date_format_edit.blockSignals(True)
            self.clock_time_format_edit.blockSignals(True)
            self.clock_show_border_checkbox.blockSignals(True)
            self.clock_border_width_spin.blockSignals(True)
            
            # Update clock style
            clock_style = props.get('clock_style', 'digital')
            self.clock_style_combo.setCurrentText("数字" if clock_style == 'digital' else "模拟")
            
            # Update display options
            self.clock_show_date_checkbox.setChecked(props.get('show_date', True))
            self.clock_show_time_checkbox.setChecked(props.get('show_time', True))
            self.clock_show_seconds_checkbox.setChecked(props.get('show_seconds', True))
            
            # Update formats
            self.clock_date_format_edit.setText(props.get('date_format', 'YYYY-MM-DD'))
            self.clock_time_format_edit.setText(props.get('time_format', 'HH:MM:SS'))
            
            # Update border settings
            self.clock_show_border_checkbox.setChecked(props.get('show_border', True))
            self.clock_border_width_spin.setValue(props.get('border_width', 1))
            
            # Update colors
            self.clock_bg_color_button.setStyleSheet(f"background-color: {props.get('background_color', '#FFFFFF')}; color: black;")
            self.clock_border_color_button.setStyleSheet(f"background-color: {props.get('border_color', '#000000')}; color: black;")
            
            # Unblock signals
            self.clock_style_combo.blockSignals(False)
            self.clock_show_date_checkbox.blockSignals(False)
            self.clock_show_time_checkbox.blockSignals(False)
            self.clock_show_seconds_checkbox.blockSignals(False)
            self.clock_date_format_edit.blockSignals(False)
            self.clock_time_format_edit.blockSignals(False)
            self.clock_show_border_checkbox.blockSignals(False)
            self.clock_border_width_spin.blockSignals(False)
        else:
            self.clock_settings_group.setVisible(False)

    def update_variable_table(self):
        """Update the variable binding table"""
        if not self.selected_object:
            return
        
        self.var_table.setRowCount(len(self.selected_object.variables))
        
        for row, var in enumerate(self.selected_object.variables):
            self.var_table.setItem(row, 0, QTableWidgetItem(var.variable_name))
            self.var_table.setItem(row, 1, QTableWidgetItem(var.variable_type))
            self.var_table.setItem(row, 2, QTableWidgetItem(var.address))
            self.var_table.setItem(row, 3, QTableWidgetItem(var.variable_type))
    
    def on_position_change(self):
        """Handle position change"""
        if self.selected_objects:
            self.save_state()
            # Apply to all selected objects
            for obj in self.selected_objects:
                new_x = self.x_spin.value()
                new_y = self.y_spin.value()
                
                # For line objects, also update endpoints
                if obj.obj_type == 'line':
                    x_delta = new_x - obj.x
                    y_delta = new_y - obj.y
                    if 'x1' in obj.properties:
                        obj.properties['x1'] += x_delta
                    if 'y1' in obj.properties:
                        obj.properties['y1'] += y_delta
                    if 'x2' in obj.properties:
                        obj.properties['x2'] += x_delta
                    if 'y2' in obj.properties:
                        obj.properties['y2'] += y_delta
                
                obj.x = new_x
                obj.y = new_y
            self.force_full_refresh()
    
    def on_size_change(self):
        """Handle size change"""
        if self.selected_objects:
            self.save_state()
            # Apply to all selected objects
            for obj in self.selected_objects:
                obj.width = self.width_spin.value()
                obj.height = self.height_spin.value()
                
                # For line objects, update endpoints based on new size
                if obj.obj_type == 'line':
                    # Scale endpoints proportionally
                    if obj.width > 0 and obj.height > 0:
                        old_width = abs(obj.properties.get('x2', obj.x + obj.width) - obj.properties.get('x1', obj.x))
                        old_height = abs(obj.properties.get('y2', obj.y + obj.height) - obj.properties.get('y1', obj.y))
                        if old_width > 0 and old_height > 0:
                            scale_x = obj.width / old_width
                            scale_y = obj.height / old_height
                            x1 = obj.properties.get('x1', obj.x)
                            y1 = obj.properties.get('y1', obj.y)
                            obj.properties['x2'] = x1 + (obj.properties.get('x2', obj.x + obj.width) - x1) * scale_x
                            obj.properties['y2'] = y1 + (obj.properties.get('y2', obj.y + obj.height) - y1) * scale_y
            self.force_full_refresh()
    
    def on_property_change(self):
        """Handle property change"""
        # Skip if we're currently updating the properties panel
        if self._updating_properties_panel:
            return
        
        if self.selected_objects:
            self.save_state()
            # Apply to all selected objects
            for obj in self.selected_objects:
                # Text properties (for controls that support text)
                if obj.obj_type not in ['input', 'line', 'rectangle', 'circle', 'gauge']:
                    obj.properties['text'] = self.text_edit.text()
                    obj.properties['font_size'] = self.font_size_spin.value()
                    obj.properties['font_family'] = self.font_family_combo.currentText()
                    obj.properties['font_bold'] = self.font_bold_checkbox.isChecked()
                    obj.properties['font_italic'] = self.font_italic_checkbox.isChecked()
                    obj.properties['font_underline'] = self.font_underline_checkbox.isChecked()
                    # Text alignment properties
                    h_align_map = {"左对齐": "left", "居中": "center", "右对齐": "right"}
                    v_align_map = {"顶部": "top", "居中": "middle", "底部": "bottom"}
                    obj.properties['text_h_align'] = h_align_map.get(self.text_h_align_combo.currentText(), "center")
                    obj.properties['text_v_align'] = v_align_map.get(self.text_v_align_combo.currentText(), "middle")
                
                if obj.obj_type == 'label':
                    obj.properties['border'] = self.border_checkbox.isChecked()
                    obj.properties['display_format'] = self.format_edit.text()
                    obj.properties['unit'] = self.unit_edit.text()
                    obj.properties['precision'] = self.precision_spin.value()
                
                if obj.obj_type == 'button':
                    # Only update action properties for the primary selected object
                    # to avoid changing all selected buttons' navigation settings
                    if obj == self.selected_object:
                        obj.properties['target_screen'] = self.target_screen_combo.currentText()
                        obj.properties['target_screen_number'] = self.target_screen_number_spin.value()
                        
                        # Handle action type from action_combo (动作: 无/变量操作/画面跳转)
                        if hasattr(self, 'action_combo'):
                            action_text = self.action_combo.currentText()
                            if action_text == "画面跳转":
                                obj.properties['action_type'] = '画面跳转'
                            elif action_text == "无":
                                obj.properties['action_type'] = 'custom'
                            else:
                                obj.properties['action_type'] = '变量操作'
                        
                        # Handle variable operation from var_operation_combo (操作: 置位/复位/取反等)
                        if hasattr(self, 'var_operation_combo'):
                            obj.properties['variable_operation'] = self.var_operation_combo.currentText()
                
                if obj.obj_type == 'switch':
                    # Switch only needs text settings
                    obj.properties['on_text'] = self.switch_on_text_edit.text()
                    obj.properties['off_text'] = self.switch_off_text_edit.text()
                
                # Dropdown properties are handled by dropdown_table in on_dropdown_item_changed and update_advanced_properties
                
                # Handle range properties for input/gauge
                if obj.obj_type in ['input', 'gauge']:
                    obj.properties['min_val'] = self.min_val_spin.value()
                    obj.properties['max_val'] = self.max_val_spin.value()
                    obj.properties['value'] = self.default_val_spin.value()
                
                # Handle checkbox properties
                if obj.obj_type == 'checkbox':
                    obj.properties['checked_value'] = self.checked_val_spin.value()
                    obj.properties['unchecked_value'] = self.unchecked_val_spin.value()
                
                # Handle graphics properties
                if obj.obj_type in ['line', 'rectangle', 'circle']:
                    obj.properties['line_width'] = self.line_width_spin.value()
                
                if obj.obj_type in ['rectangle', 'circle']:
                    obj.properties['filled'] = self.filled_checkbox.isChecked()
                
                # Handle picture properties
                if obj.obj_type == 'picture':
                    obj.properties['keep_aspect_ratio'] = self.keep_aspect_checkbox.isChecked()
                
                # Handle picture list properties
                if obj.obj_type == 'picture_list':
                    obj.properties['keep_aspect_ratio'] = self.pl_keep_aspect_cb.isChecked()
                    obj.properties['border_visible'] = self.pl_show_border_cb.isChecked()
                    obj.properties['show_value_label'] = self.pl_show_value_cb.isChecked()
                
                # Handle light properties
                if obj.obj_type == 'light':
                    # Text is now handled in basic properties text_edit
                    obj.properties['border'] = self.light_border_checkbox.isChecked()
                    obj.properties['use_image'] = self.light_use_image_checkbox.isChecked()

                # Handle progress bar properties
                if obj.obj_type == 'progress':
                    obj.properties['border_width'] = self.progress_border_width_spin.value()
                    obj.properties['border_radius'] = self.progress_border_radius_spin.value()
                    obj.properties['show_value'] = self.progress_show_value_checkbox.isChecked()
                    obj.properties['show_percentage'] = self.progress_show_percentage_checkbox.isChecked()
                    obj.properties['font_size'] = self.progress_font_size_spin.value()
                    obj.properties['bar_gradient'] = self.progress_gradient_checkbox.isChecked()

                # Handle trend chart properties
                if obj.obj_type == 'trend_chart':
                    obj.properties['title'] = self.trend_title_edit.text()
                    obj.properties['title_visible'] = self.trend_title_visible_checkbox.isChecked()
                    obj.properties['y_min'] = self.trend_y_min_spin.value()
                    obj.properties['y_max'] = self.trend_y_max_spin.value()
                    obj.properties['y_auto_scale'] = self.trend_auto_scale_checkbox.isChecked()
                    obj.properties['time_span'] = self.trend_time_span_spin.value()
                    obj.properties['update_interval'] = self.trend_update_interval_spin.value()
                    obj.properties['grid_visible'] = self.trend_grid_visible_checkbox.isChecked()
                    obj.properties['line_width'] = self.trend_line_width_spin.value()
                    obj.properties['show_legend'] = self.trend_show_legend_checkbox.isChecked()

                # Handle history trend chart properties
                if obj.obj_type == 'history_trend':
                    obj.properties['title'] = self.htrend_title_edit.text()
                    obj.properties['title_visible'] = self.htrend_title_visible_checkbox.isChecked()
                    obj.properties['title_font_size'] = self.htrend_title_font_spin.value()
                
                # Handle alarm display properties
                if obj.obj_type == 'alarm_display':
                    obj.properties['max_display_count'] = self.alarm_max_count_spin.value()
                    obj.properties['auto_scroll'] = self.alarm_auto_scroll_checkbox.isChecked()
                    obj.properties['show_timestamp'] = self.alarm_show_timestamp_checkbox.isChecked()
                    obj.properties['show_alarm_type'] = self.alarm_show_type_checkbox.isChecked()
                    
                    # Get visible alarm types from checkboxes
                    visible_types = []
                    for type_name, checkbox in self.alarm_type_checkboxes.items():
                        if checkbox.isChecked():
                            visible_types.append(type_name)
                    obj.properties['visible_alarm_types'] = visible_types
                    obj.properties['control_font_size'] = self.htrend_control_font_spin.value()
                    obj.properties['y_min'] = self.htrend_y_min_spin.value()
                    obj.properties['y_max'] = self.htrend_y_max_spin.value()
                    obj.properties['y_auto_scale'] = self.htrend_auto_scale_checkbox.isChecked()
                    obj.properties['grid_visible'] = self.htrend_grid_visible_checkbox.isChecked()
                    obj.properties['line_width'] = self.htrend_line_width_spin.value()
                    obj.properties['show_legend'] = self.htrend_show_legend_checkbox.isChecked()
                    obj.properties['border_width'] = self.htrend_border_width_spin.value()

                # Handle text list properties
                if obj.obj_type == 'text_list':
                    obj.properties['item_height'] = self.text_list_item_height_spin.value()
                    obj.properties['selected_index'] = self.text_list_selected_spin.value()

            # Force immediate refresh for text changes
            self.force_full_refresh()
    
    def on_action_type_change(self, text, update_property=True):
        """Handle action type change - show/hide relevant settings
        
        Args:
            text: The action type text
            update_property: Whether to update the object's property (default True)
                            Set to False when calling from update_properties_panel
        """
        # Skip if we're currently updating the properties panel
        if self._updating_properties_panel:
            return
        
        # Show/hide widgets based on action type
        if text == "画面跳转":
            # Show screen navigation
            for widget in getattr(self, 'screen_nav_widgets', []):
                widget.setVisible(True)
            if update_property and self.selected_object:
                self.selected_object.properties['action_type'] = '画面跳转'
        elif text == "无":
            # Hide all action widgets
            for widget in getattr(self, 'screen_nav_widgets', []):
                widget.setVisible(False)
            if update_property and self.selected_object:
                self.selected_object.properties['action_type'] = 'custom'
        else:
            # Variable operations - hide screen navigation
            for widget in getattr(self, 'screen_nav_widgets', []):
                widget.setVisible(False)
            if update_property and self.selected_object:
                self.selected_object.properties['action_type'] = '变量操作'
        
        # Trigger property change to save all related properties
        if update_property:
            self.on_property_change()
    
    def refresh_target_screens(self):
        """Refresh the target screen combo box"""
        # Block signals to prevent on_property_change from being triggered
        self.target_screen_combo.blockSignals(True)
        self.target_screen_combo.clear()
        for screen in self.screens:
            screen_name = screen.name if hasattr(screen, 'name') else screen.get('name', '')
            if screen_name:
                self.target_screen_combo.addItem(screen_name)
        self.target_screen_combo.blockSignals(False)
    
    def choose_color(self):
        """Open color picker for object color"""
        if self.selected_objects:
            color = QColorDialog.getColor()
            if color.isValid():
                self.save_state()
                # Apply to all selected objects
                for obj in self.selected_objects:
                    obj.properties['color'] = color.name()
                self.color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
                self.force_full_refresh()

    def choose_text_color(self):
        """Open color picker for text color"""
        if self.selected_objects:
            color = QColorDialog.getColor()
            if color.isValid():
                self.save_state()
                # Apply to all selected objects
                for obj in self.selected_objects:
                    obj.properties['text_color'] = color.name()
                self.text_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
                self.force_full_refresh()

    def choose_label_background_color(self):
        """Open color picker for label background color"""
        if self.selected_objects:
            # Get current background color for initial selection
            current_color = self.selected_objects[0].properties.get('background_color', '')
            initial_color = QColor(current_color) if current_color else QColor('#FFFFFF')
            
            color = QColorDialog.getColor(initial_color)
            if color.isValid():
                self.save_state()
                # Apply to all selected objects
                for obj in self.selected_objects:
                    if obj.obj_type == 'label':
                        obj.properties['background_color'] = color.name()
                self.label_bg_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
                self.force_full_refresh()
    
    def choose_color_for_state(self, state):
        """Choose color for button/switch state"""
        if self.selected_object and self.selected_object.obj_type in ['button', 'switch']:
            color = QColorDialog.getColor()
            if color.isValid():
                self.save_state()
                if state == 'on':
                    self.selected_object.properties['on_color'] = color.name()
                    self.on_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
                else:
                    self.selected_object.properties['off_color'] = color.name()
                    self.off_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
                self.force_full_refresh()
    
    def choose_switch_text_color(self):
        """Choose text color for switch"""
        if self.selected_object and self.selected_object.obj_type == 'switch':
            color = QColorDialog.getColor()
            if color.isValid():
                self.save_state()
                self.selected_object.properties['text_color'] = color.name()
                self.switch_text_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
                self.force_full_refresh()
    
    def choose_fill_color(self):
        """Choose fill color for graphics"""
        if self.selected_objects and self.selected_object.obj_type in ['rectangle', 'circle']:
            color = QColorDialog.getColor()
            if color.isValid():
                # Apply to all selected objects
                for obj in self.selected_objects:
                    obj.properties['fill_color'] = color.name()
                self.fill_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
                self.force_full_refresh()
    
    def choose_line_color(self):
        """Choose line color for graphics"""
        if self.selected_objects and self.selected_object.obj_type in ['line', 'rectangle', 'circle']:
            color = QColorDialog.getColor()
            if color.isValid():
                # Apply to all selected objects
                for obj in self.selected_objects:
                    obj.properties['color'] = color.name()
                self.line_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
                self.force_full_refresh()
    
    def browse_image(self):
        """Browse for an image file"""
        if not self.selected_object or self.selected_object.obj_type != 'picture':
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.svg);;所有文件 (*)")
        if file_path:
            self.selected_object.properties['image_path'] = file_path
            self.image_path_edit.setText(file_path)
            self.force_full_refresh()
    
    def browse_picture_list_default_image(self):
        """Browse for default image for picture list"""
        if not self.selected_object or self.selected_object.obj_type != 'picture_list':
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择默认图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.svg);;所有文件 (*)")
        if file_path:
            self.selected_object.properties['default_image'] = file_path
            self.pl_default_image_edit.setText(file_path)
            self.force_full_refresh()
    
    def on_picture_list_value_type_change(self, text):
        """Handle picture list value type change"""
        if not self.selected_object or self.selected_object.obj_type != 'picture_list':
            return
        
        type_map = {"整数": "integer", "浮点数": "float", "布尔": "bool", "字符串": "string"}
        self.selected_object.properties['value_type'] = type_map.get(text, 'integer')
        self.save_state()
        self.force_full_refresh()
    
    def add_picture_list_state(self):
        """Add a new state to picture list"""
        if not self.selected_object or self.selected_object.obj_type != 'picture_list':
            return
        
        state_images = self.selected_object.properties.get('state_images', [])
        state_images.append({
            'value': '0',
            'compare_type': 'equal',
            'image_path': ''
        })
        self.selected_object.properties['state_images'] = state_images
        self.update_picture_list_states_table()
        self.save_state()
    
    def update_picture_list_states_table(self):
        """Update picture list states table"""
        if not self.selected_object or self.selected_object.obj_type != 'picture_list':
            return
        
        state_images = self.selected_object.properties.get('state_images', [])
        self.pl_states_table.blockSignals(True)
        self.pl_states_table.setRowCount(len(state_images))
        
        for i, state in enumerate(state_images):
            value_item = QTableWidgetItem(str(state.get('value', '')))
            self.pl_states_table.setItem(i, 0, value_item)
            
            compare_combo = QComboBox()
            compare_combo.addItems(["等于", "大于", "小于", "大于等于", "小于等于", "不等于"])
            compare_map = {"equal": "等于", "greater": "大于", "less": "小于", 
                          "greater_equal": "大于等于", "less_equal": "小于等于", "not_equal": "不等于"}
            reverse_map = {v: k for k, v in compare_map.items()}
            compare_combo.setCurrentText(compare_map.get(state.get('compare_type', 'equal'), '等于'))
            compare_combo.currentTextChanged.connect(lambda text, row=i: self.on_pl_compare_type_change(row, text))
            self.pl_states_table.setCellWidget(i, 1, compare_combo)
            
            image_item = QTableWidgetItem(state.get('image_path', ''))
            image_item.setFlags(image_item.flags() & ~Qt.ItemIsEditable)
            self.pl_states_table.setItem(i, 2, image_item)
            
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(2, 2, 2, 2)
            btn_layout.setSpacing(2)
            
            browse_btn = QPushButton("...")
            browse_btn.setFixedSize(24, 24)
            browse_btn.clicked.connect(lambda checked, row=i: self.browse_pl_state_image(row))
            btn_layout.addWidget(browse_btn)
            
            del_btn = QPushButton("X")
            del_btn.setFixedSize(24, 24)
            del_btn.clicked.connect(lambda checked, row=i: self.delete_pl_state(row))
            btn_layout.addWidget(del_btn)
            
            btn_widget.setLayout(btn_layout)
            self.pl_states_table.setCellWidget(i, 3, btn_widget)
        
        self.pl_states_table.blockSignals(False)
    
    def on_pl_compare_type_change(self, row, text):
        """Handle compare type change"""
        if not self.selected_object or self.selected_object.obj_type != 'picture_list':
            return
        
        compare_map = {"等于": "equal", "大于": "greater", "小于": "less", 
                      "大于等于": "greater_equal", "小于等于": "less_equal", "不等于": "not_equal"}
        state_images = self.selected_object.properties.get('state_images', [])
        if row < len(state_images):
            state_images[row]['compare_type'] = compare_map.get(text, 'equal')
            self.save_state()
    
    def on_pl_states_table_changed(self, row, column):
        """Handle picture list states table cell change"""
        if not self.selected_object or self.selected_object.obj_type != 'picture_list':
            return
        
        if column == 0:
            item = self.pl_states_table.item(row, column)
            if item:
                state_images = self.selected_object.properties.get('state_images', [])
                if row < len(state_images):
                    state_images[row]['value'] = item.text()
                    self.save_state()
    
    def browse_pl_state_image(self, row):
        """Browse for state image"""
        if not self.selected_object or self.selected_object.obj_type != 'picture_list':
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.svg);;所有文件 (*)")
        if file_path:
            state_images = self.selected_object.properties.get('state_images', [])
            if row < len(state_images):
                state_images[row]['image_path'] = file_path
                self.update_picture_list_states_table()
                self.save_state()
                self.force_full_refresh()
    
    def delete_pl_state(self, row):
        """Delete a state from picture list"""
        if not self.selected_object or self.selected_object.obj_type != 'picture_list':
            return
        
        state_images = self.selected_object.properties.get('state_images', [])
        if 0 <= row < len(state_images):
            del state_images[row]
            self.selected_object.properties['state_images'] = state_images
            self.update_picture_list_states_table()
            self.save_state()
            self.force_full_refresh()
    
    def on_clock_style_changed(self, text):
        """Handle clock style change"""
        if not self.selected_object or self.selected_object.obj_type != 'clock':
            return
        
        clock_style = 'digital' if text == "数字" else "analog"
        self.selected_object.properties['clock_style'] = clock_style
        self.save_state()
        self.force_full_refresh()
    
    def on_clock_property_change(self):
        """Handle clock property changes"""
        if not self.selected_object or self.selected_object.obj_type != 'clock':
            return
        
        props = self.selected_object.properties
        
        # Update display options
        props['show_date'] = self.clock_show_date_checkbox.isChecked()
        props['show_time'] = self.clock_show_time_checkbox.isChecked()
        props['show_seconds'] = self.clock_show_seconds_checkbox.isChecked()
        
        # Update formats
        props['date_format'] = self.clock_date_format_edit.text()
        props['time_format'] = self.clock_time_format_edit.text()
        
        # Update border settings
        props['show_border'] = self.clock_show_border_checkbox.isChecked()
        props['border_width'] = self.clock_border_width_spin.value()
        
        self.save_state()
        self.force_full_refresh()
    
    def choose_clock_bg_color(self):
        """Choose clock background color"""
        if self.selected_object and self.selected_object.obj_type == 'clock':
            current_color = self.selected_object.properties.get('background_color', '#FFFFFF')
            initial_color = QColor(current_color)
            
            color = QColorDialog.getColor(initial_color)
            if color.isValid():
                self.selected_object.properties['background_color'] = color.name()
                self.clock_bg_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
                self.force_full_refresh()
    
    def choose_clock_border_color(self):
        """Choose clock border color"""
        if self.selected_object and self.selected_object.obj_type == 'clock':
            current_color = self.selected_object.properties.get('border_color', '#000000')
            initial_color = QColor(current_color)
            
            color = QColorDialog.getColor(initial_color)
            if color.isValid():
                self.selected_object.properties['border_color'] = color.name()
                self.clock_border_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
                self.force_full_refresh()
    
    def clear_image(self):
        """Clear the image from the picture object"""
        if not self.selected_object or self.selected_object.obj_type != 'picture':
            return
        
        obj = self.selected_object
        obj.properties['image_path'] = ''
        if hasattr(obj, 'pixmap'):
            obj.pixmap = None
        
        # Update the UI
        self.image_path_edit.setText('')
        self.force_full_refresh()
    
    def on_light_shape_change(self, text):
        """Handle light shape change"""
        shape_map = {
            '圆形': 'circle',
            '方形': 'square',
            '矩形': 'rectangle'
        }
        if self.selected_object and self.selected_object.obj_type == 'light':
            self.selected_object.properties['shape'] = shape_map.get(text, 'circle')
            self.force_full_refresh()
    
    def choose_light_color(self, state):
        """Choose color for light on/off state"""
        if not self.selected_object or self.selected_object.obj_type != 'light':
            return
        
        color = QColorDialog.getColor()
        if color.isValid():
            if state == 'on':
                self.selected_object.properties['on_color'] = color.name()
                self.light_on_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
            else:
                self.selected_object.properties['off_color'] = color.name()
                self.light_off_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
            self.force_full_refresh()
    
    def choose_light_text_color(self):
        """Choose text color for light"""
        if not self.selected_object or self.selected_object.obj_type != 'light':
            return
        
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_object.properties['text_color'] = color.name()
            self.light_text_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
            self.force_full_refresh()
    
    def on_light_use_image_change(self, state):
        """Handle light use image checkbox change"""
        if self.selected_object and self.selected_object.obj_type == 'light':
            self.selected_object.properties['use_image'] = (state == Qt.Checked)
            # Enable/disable image controls
            self.light_on_image_edit.setEnabled(state == Qt.Checked)
            self.light_on_image_btn.setEnabled(state == Qt.Checked)
            self.light_off_image_edit.setEnabled(state == Qt.Checked)
            self.light_off_image_btn.setEnabled(state == Qt.Checked)
            self.force_full_refresh()
    
    def browse_light_image(self, state):
        """Browse for light on/off image"""
        if not self.selected_object or self.selected_object.obj_type != 'light':
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"选择{state}状态图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*)"
        )
        
        if file_path:
            # Copy image to project images folder
            import shutil
            import time
            project_dir = os.path.dirname(self.current_file) if self.current_file else os.getcwd()
            if project_dir:
                images_dir = os.path.join(project_dir, 'images')
                os.makedirs(images_dir, exist_ok=True)
                
                # Generate unique filename
                timestamp = int(time.time() * 1000)
                filename = os.path.basename(file_path)
                name, ext = os.path.splitext(filename)
                new_filename = f"light_{state}_{timestamp}{ext}"
                dest_path = os.path.join(images_dir, new_filename)
                
                try:
                    shutil.copy2(file_path, dest_path)
                    file_path = dest_path
                    print(f"Copied image to project: {dest_path}")
                except Exception as e:
                    print(f"Error copying image: {e}")
            
            # Update the selected object
            obj = self.selected_object
            if state == 'on':
                obj.properties['on_image'] = file_path
                self.light_on_image_edit.setText(os.path.basename(file_path))
            else:
                obj.properties['off_image'] = file_path
                self.light_off_image_edit.setText(os.path.basename(file_path))
            
            # Reload images
            if hasattr(obj, 'load_images'):
                obj.load_images()
            
            self.force_full_refresh()
    
    def on_progress_orientation_change(self, text):
        """Handle progress bar orientation change"""
        if self.selected_object and self.selected_object.obj_type == 'progress':
            orientation_map = {'水平': 'horizontal', '垂直': 'vertical'}
            self.selected_object.properties['orientation'] = orientation_map.get(text, 'horizontal')
            self.force_full_refresh()

    def choose_progress_bar_color(self):
        """Choose progress bar color"""
        if not self.selected_object or self.selected_object.obj_type != 'progress':
            return
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_object.properties['bar_color'] = color.name()
            self.progress_bar_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
            self.force_full_refresh()

    def choose_progress_bg_color(self):
        """Choose progress bar background color"""
        if not self.selected_object or self.selected_object.obj_type != 'progress':
            return
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_object.properties['bg_color'] = color.name()
            self.progress_bg_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
            self.force_full_refresh()

    def choose_progress_border_color(self):
        """Choose progress bar border color"""
        if not self.selected_object or self.selected_object.obj_type != 'progress':
            return
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_object.properties['border_color'] = color.name()
            self.progress_border_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
            self.force_full_refresh()

    def choose_progress_text_color(self):
        """Choose progress bar text color"""
        if not self.selected_object or self.selected_object.obj_type != 'progress':
            return
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_object.properties['text_color'] = color.name()
            self.progress_text_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
            self.force_full_refresh()

    def on_progress_text_position_change(self, text):
        """Handle progress bar text position change"""
        if self.selected_object and self.selected_object.obj_type == 'progress':
            position_map = {'居中': 'center', '左侧': 'left', '右侧': 'right', '顶部': 'top', '底部': 'bottom'}
            self.selected_object.properties['text_position'] = position_map.get(text, 'center')
            self.force_full_refresh()

    def choose_trend_title_color(self):
        """Choose trend chart title color"""
        if not self.selected_object or self.selected_object.obj_type != 'trend_chart':
            return
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_object.properties['title_color'] = color.name()
            self.trend_title_color_button.setStyleSheet(f"background-color: {color.name()}; color: white;")
            self.force_full_refresh()

    def choose_trend_bg_color(self):
        """Choose trend chart background color"""
        if not self.selected_object or self.selected_object.obj_type != 'trend_chart':
            return
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_object.properties['bg_color'] = color.name()
            self.trend_bg_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
            self.force_full_refresh()

    def choose_trend_grid_color(self):
        """Choose trend chart grid color"""
        if not self.selected_object or self.selected_object.obj_type != 'trend_chart':
            return
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_object.properties['grid_color'] = color.name()
            self.trend_grid_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
            self.force_full_refresh()

    def choose_htrend_title_color(self):
        """Choose history trend title color"""
        if not self.selected_object or self.selected_object.obj_type != 'history_trend':
            return
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_object.properties['title_color'] = color.name()
            self.htrend_title_color_button.setStyleSheet(f"background-color: {color.name()}; color: white;")
            self.force_full_refresh()

    def choose_htrend_bg_color(self):
        """Choose history trend background color"""
        if not self.selected_object or self.selected_object.obj_type != 'history_trend':
            return
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_object.properties['bg_color'] = color.name()
            self.htrend_bg_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
            self.force_full_refresh()

    def choose_htrend_grid_color(self):
        """Choose history trend grid color"""
        if not self.selected_object or self.selected_object.obj_type != 'history_trend':
            return
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_object.properties['grid_color'] = color.name()
            self.htrend_grid_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
            self.force_full_refresh()

    def choose_htrend_border_color(self):
        """Choose history trend border color"""
        if not self.selected_object or self.selected_object.obj_type != 'history_trend':
            return
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_object.properties['border_color'] = color.name()
            self.htrend_border_color_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
            self.force_full_refresh()

    def refresh_available_variables(self):
        """Refresh the available variables from data_manager"""
        if hasattr(self, 'avail_var_combo'):
            self.avail_var_combo.set_data_manager(self.data_manager)
            self.avail_var_combo.set_config_manager(self.config_manager)
    
    def on_variable_binding_change(self, var_name):
        """Handle variable binding change - single variable mode"""
        if self.selected_object and var_name and self.data_manager:
            # Skip for trend chart - it uses its own variable binding in advanced properties
            if self.selected_object.obj_type == 'trend_chart':
                return
            
            # Clear existing bindings first (single variable mode)
            self.selected_object.variables = []
            
            tag = self.data_manager.tags.get(var_name)
            if tag:
                self.selected_object.add_variable_binding(
                    variable_name=var_name,
                    variable_type='read',
                    address=tag.address,
                    description=getattr(tag, 'description', '')
                )
                self.var_name_label.setText(var_name)
                data_type = getattr(tag, 'data_type', '-')
                self.var_type_label.setText(str(data_type) if data_type else '-')
                self.var_addr_label.setText(tag.address or '-')
            else:
                self.selected_object.add_variable_binding(
                    variable_name=var_name,
                    variable_type='read',
                    address='',
                    description=''
                )
                self.var_name_label.setText(var_name)
                self.var_type_label.setText('-')
                self.var_addr_label.setText('-')
            
            # Reset bit offset when variable changes
            self.bit_offset_spin.setValue(-1)
            
            self.save_state()
            self.force_full_refresh()
    
    def on_bit_offset_changed(self, value):
        """Handle bit offset change for variable binding"""
        if self.selected_object and self.selected_object.variables:
            # Update the first variable binding with bit offset
            var_binding = self.selected_object.variables[0]
            var_binding.bit_offset = value if value >= 0 else None
            self.save_state()

    def add_trend_variable(self):
        """Add a variable to trend chart binding list"""
        if not self.selected_object or self.selected_object.obj_type != 'trend_chart':
            return
        
        var_name = self.trend_var_combo.combo.text()
        if not var_name:
            return
        
        # Check if already bound
        for vb in self.selected_object.variables:
            if vb.variable_name == var_name:
                print(f"TrendChart: Variable '{var_name}' already bound")
                return
        
        # Limit to 8 variables for trend chart
        if len(self.selected_object.variables) >= 8:
            QMessageBox.warning(self, "提示", "最多绑定8个变量！")
            return
        
        # Get tag info if available
        address = ''
        description = ''
        if self.data_manager:
            tag = self.data_manager.tags.get(var_name)
            if tag:
                address = tag.address or ''
                description = getattr(tag, 'description', '')
        
        self.selected_object.add_variable_binding(
            variable_name=var_name,
            variable_type='read',
            address=address,
            description=description
        )
        
        print(f"TrendChart: Added variable '{var_name}' to trend chart, Total variables: {len(self.selected_object.variables)}")
        
        self.update_trend_vars_list()
        self.save_state()
        self.force_full_refresh()

    def remove_trend_variable(self):
        """Remove selected variable from trend chart binding list"""
        if not self.selected_object or self.selected_object.obj_type != 'trend_chart':
            return
        
        current_item = self.trend_vars_list.currentItem()
        if not current_item:
            return
        
        var_name = current_item.text()
        
        # Remove from variables list
        self.selected_object.variables = [
            vb for vb in self.selected_object.variables if vb.variable_name != var_name
        ]
    
    def select_all_alarm_types(self):
        """Select all alarm types"""
        for checkbox in self.alarm_type_checkboxes.values():
            checkbox.setChecked(True)
        self.on_property_change()
    
    def select_no_alarm_types(self):
        """Select no alarm types"""
        for checkbox in self.alarm_type_checkboxes.values():
            checkbox.setChecked(False)
        self.on_property_change()
        
        self.update_trend_vars_list()
        self.save_state()
        self.force_full_refresh()

    def on_trend_var_selected(self, item):
        """Handle selection in trend chart variables list"""
        pass  # Just for visual feedback

    def update_trend_vars_list(self):
        """Update the trend chart variables list widget"""
        self.trend_vars_list.clear()
        if self.selected_object and self.selected_object.obj_type == 'trend_chart':
            print(f"update_trend_vars_list: Object has {len(self.selected_object.variables)} variables")
            for vb in self.selected_object.variables:
                print(f"  - Adding to list: {vb.variable_name}")
                self.trend_vars_list.addItem(vb.variable_name)
    
    def clear_variable_binding(self):
        """Clear the variable binding"""
        if self.selected_object:
            # Skip for trend chart - it uses its own variable binding in advanced properties
            if self.selected_object.obj_type == 'trend_chart':
                return
            
            self.selected_object.variables = []
            self.avail_var_combo.combo.clear()
            self.var_name_label.setText("-")
            self.var_type_label.setText("-")
            self.var_addr_label.setText("-")
            self.save_state()
            self.force_full_refresh()
    
    def on_visibility_settings_change(self):
        """Handle visibility settings change"""
        if not self.selected_object:
            return
        
        condition_map = {
            "等于": "equal", "不等于": "not_equal", "大于": "greater", "小于": "less",
            "大于等于": "greater_equal", "小于等于": "less_equal", "非零": "not_zero", "为零": "is_zero"
        }
        
        condition_text = self.visibility_condition_combo.currentText()
        self.selected_object.visibility['condition'] = condition_map.get(condition_text, 'equal')
        self.selected_object.visibility['compare_value'] = self.visibility_compare_edit.text()
        self.selected_object.visibility['show_when_true'] = self.show_when_true_radio.isChecked()
        
        self.update_visibility_status_display()
        self.save_state()
    
    def on_visibility_variable_change(self, var_name):
        """Handle visibility control variable selection"""
        if not self.selected_object:
            return
        
        self.selected_object.visibility['control_variable'] = var_name
        # Reset bit offset when variable changes
        self.selected_object.visibility['bit_offset'] = None
        if hasattr(self, 'visibility_bit_offset_spin'):
            self.visibility_bit_offset_spin.setValue(-1)
        self.update_visibility_status_display()
        self.save_state()
    
    def on_visibility_bit_offset_change(self, value):
        """Handle visibility control bit offset change"""
        if not self.selected_object:
            return
        
        self.selected_object.visibility['bit_offset'] = value if value >= 0 else None
        self.save_state()
    
    def clear_visibility_variable(self):
        """Clear the visibility control variable"""
        if self.selected_object:
            self.selected_object.visibility['control_variable'] = ''
            self.selected_object.visibility['bit_offset'] = None
            self.visibility_var_combo.combo.clear()
            if hasattr(self, 'visibility_bit_offset_spin'):
                self.visibility_bit_offset_spin.setValue(-1)
            self.update_visibility_status_display()
            self.save_state()
    
    def update_visibility_status_display(self):
        """Update the visibility status display"""
        if not hasattr(self, 'visibility_status_label'):
            return
        
        if not self.selected_object:
            self.visibility_status_label.setText("未选择对象")
            return
        
        visibility = self.selected_object.visibility
        
        if not visibility.get('control_variable'):
            self.visibility_status_label.setText("未组态 - 始终可见")
            self.visibility_status_label.setStyleSheet("font-weight: bold; color: #008000;")
        else:
            var_name = visibility.get('control_variable', '')
            condition = visibility.get('condition', 'equal')
            compare_value = visibility.get('compare_value', '')
            show_when_true = visibility.get('show_when_true', True)
            
            condition_map = {
                "equal": "=", "not_equal": "≠", "greater": ">", "less": "<",
                "greater_equal": "≥", "less_equal": "≤", "not_zero": "≠0", "is_zero": "=0"
            }
            cond_symbol = condition_map.get(condition, '=')
            
            if condition in ['not_zero', 'is_zero']:
                status_text = f"{var_name} {cond_symbol}"
            else:
                status_text = f"{var_name} {cond_symbol} {compare_value}"
            
            behavior_text = "显示" if show_when_true else "隐藏"
            self.visibility_status_label.setText(f"{status_text} → 条件满足时{behavior_text}")
            
            if show_when_true:
                self.visibility_status_label.setStyleSheet("font-weight: bold; color: #008000;")
            else:
                self.visibility_status_label.setStyleSheet("font-weight: bold; color: #800000;")
    
    def update_visibility_panel(self):
        """Update visibility panel from selected object"""
        if not hasattr(self, 'show_when_true_radio'):
            return
        
        if not self.selected_object:
            return
        
        visibility = getattr(self.selected_object, 'visibility', {})
        
        if 'hide_when_false' in visibility and 'show_when_true' not in visibility:
            visibility['show_when_true'] = not visibility.pop('hide_when_false', True)
            if 'visible' in visibility:
                del visibility['visible']
        
        condition_reverse_map = {
            "equal": "等于", "not_equal": "不等于", "greater": "大于", "less": "小于",
            "greater_equal": "大于等于", "less_equal": "小于等于", "not_zero": "非零", "is_zero": "为零"
        }
        condition_text = condition_reverse_map.get(visibility.get('condition', 'equal'), '等于')
        
        self.visibility_condition_combo.blockSignals(True)
        self.visibility_condition_combo.setCurrentText(condition_text)
        self.visibility_condition_combo.blockSignals(False)
        
        self.visibility_compare_edit.blockSignals(True)
        self.visibility_compare_edit.setText(visibility.get('compare_value', ''))
        self.visibility_compare_edit.blockSignals(False)
        
        show_when_true = visibility.get('show_when_true', True)
        self.show_when_true_radio.blockSignals(True)
        self.show_when_true_radio.setChecked(show_when_true)
        self.show_when_true_radio.blockSignals(False)
        
        self.hide_when_true_radio.blockSignals(True)
        self.hide_when_true_radio.setChecked(not show_when_true)
        self.hide_when_true_radio.blockSignals(False)
        
        self.visibility_var_combo.combo.blockSignals(True)
        self.visibility_var_combo.combo.setText(visibility.get('control_variable', ''))
        self.visibility_var_combo.combo.blockSignals(False)
        
        # Update bit offset for visibility control
        if hasattr(self, 'visibility_bit_offset_spin'):
            self.visibility_bit_offset_spin.blockSignals(True)
            bit_offset = visibility.get('bit_offset', None)
            self.visibility_bit_offset_spin.setValue(bit_offset if bit_offset is not None else -1)
            self.visibility_bit_offset_spin.blockSignals(False)
        
        self.update_visibility_status_display()
    
    def update_variable_info_display(self):
        """Update the variable info display for the selected object"""
        if hasattr(self, 'var_name_label'):
            if self.selected_object and self.selected_object.variables:
                bound_var = self.selected_object.variables[0]
                var_name = bound_var.variable_name or "-"
                self.var_name_label.setText(var_name)
                self.var_addr_label.setText(bound_var.address or "-")
                self.avail_var_combo.combo.setText(bound_var.variable_name or "")
                # Update bit offset display
                if hasattr(self, 'bit_offset_spin'):
                    bit_offset = getattr(bound_var, 'bit_offset', None)
                    self.bit_offset_spin.setValue(bit_offset if bit_offset is not None else -1)
                # Get data type from data_manager
                if self.data_manager:
                    tag = self.data_manager.tags.get(var_name)
                    if tag:
                        data_type = getattr(tag, 'data_type', '-')
                        self.var_type_label.setText(str(data_type) if data_type else '-')
                    else:
                        self.var_type_label.setText("-")
                else:
                    self.var_type_label.setText("-")
            else:
                self.var_name_label.setText("-")
                self.var_type_label.setText("-")
                self.var_addr_label.setText("-")
                self.avail_var_combo.clear()
                if hasattr(self, 'bit_offset_spin'):
                    self.bit_offset_spin.setValue(-1)
    
    def on_new_screen(self):
        """Create a new screen"""
        name = self.new_screen_name.text() or f"画面{len(self.screens) + 1}"
        screen_number = len(self.screens) + 1
        
        # Set as main screen if it's the first screen
        is_main = len(self.screens) == 0
        
        # Use global resolution for new screen (create a copy to avoid shared reference)
        screen = HMIScreen(name=name, number=screen_number, resolution=self.global_resolution.copy())
        screen.is_main = is_main
        self.screens.append(screen)
        self.current_screen_index = len(self.screens) - 1
        self.objects = screen.objects
        self.refresh_screen_display()
        self.update_screen_list()
        self.new_screen_name.clear()
        return screen
    
    def switch_screen(self, index):
        """Switch to a different screen"""
        if 0 <= index < len(self.screens):
            self.current_screen_index = index
            screen = self.screens[self.current_screen_index]
            self.objects = screen.objects
            
            # Force full refresh when switching screens
            self._scene_needs_full_refresh = True
            
            # Update resolution settings
            if hasattr(self, 'width_spin') and hasattr(self, 'height_spin'):
                resolution = screen.resolution if hasattr(screen, 'resolution') else {'width': 1000, 'height': 600}
                # Block signals to prevent triggering on_size_change
                self.width_spin.blockSignals(True)
                self.height_spin.blockSignals(True)
                self.width_spin.setValue(resolution['width'])
                self.height_spin.setValue(resolution['height'])
                self.width_spin.blockSignals(False)
                self.height_spin.blockSignals(False)
                self.scene.setSceneRect(0, 0, resolution['width'], resolution['height'])
                # Ensure scroll bars are enabled for large scenes
                self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                self.view.update()

            self.refresh_screen_display()
    
    def update_screen_list(self):
        """Update the screen list widget"""
        self.screen_list.clear()
        for screen in self.screens:
            # Get screen name and number
            name = screen.name if hasattr(screen, 'name') else screen.get('name', 'Untitled')
            number = screen.number if hasattr(screen, 'number') else screen.get('number', 0)
            # Display format: "number name"
            display_text = f"{number} {name}"
            self.screen_list.addItem(display_text)
        
        # Set current selection
        if 0 <= self.current_screen_index < self.screen_list.count():
            self.screen_list.setCurrentRow(self.current_screen_index)
    
    def show_screen_context_menu(self, position):
        """Show context menu for screen list"""
        item = self.screen_list.itemAt(position)
        if item is None:
            return
        
        menu = QMenu()
        
        # Get the screen index
        screen_index = self.screen_list.row(item)
        
        # Add actions
        properties_action = menu.addAction("属性...")
        rename_action = menu.addAction("重命名")
        set_main_action = menu.addAction("设为主画面")
        delete_action = menu.addAction("删除")
        
        # Show menu
        action = menu.exec_(self.screen_list.viewport().mapToGlobal(position))
        
        if action == properties_action:
            self.show_screen_properties_dialog(screen_index)
        elif action == rename_action:
            self.on_rename_screen_at_index(screen_index)
        elif action == set_main_action:
            self.on_set_main_screen_at_index(screen_index)
        elif action == delete_action:
            self.on_delete_screen_at_index(screen_index)
    
    def show_screen_properties_dialog(self, screen_index):
        """Show dialog to edit screen properties"""
        if screen_index < 0 or screen_index >= len(self.screens):
            return
        
        screen = self.screens[screen_index]
        
        # Get current values
        current_name = screen.name if hasattr(screen, 'name') else screen.get('name', 'Untitled')
        current_number = screen.number if hasattr(screen, 'number') else screen.get('number', 0)
        current_resolution = screen.resolution if hasattr(screen, 'resolution') else screen.get('resolution', {'width': 1000, 'height': 600})
        current_bg = screen.background_color if hasattr(screen, 'background_color') else screen.get('background_color', '#FFFFFF')
        current_is_main = screen.is_main if hasattr(screen, 'is_main') else screen.get('is_main', False)
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("画面属性")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout()
        
        # Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("名称:"))
        name_edit = QLineEdit(current_name)
        name_layout.addWidget(name_edit)
        layout.addLayout(name_layout)
        
        # Number
        number_layout = QHBoxLayout()
        number_layout.addWidget(QLabel("编号:"))
        number_spin = QSpinBox()
        number_spin.setRange(0, 9999)
        number_spin.setValue(current_number)
        number_layout.addWidget(number_spin)
        layout.addLayout(number_layout)
        
        # Resolution
        resolution_group = QGroupBox("分辨率")
        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(QLabel("宽:"))
        width_spin = QSpinBox()
        width_spin.setRange(100, 5000)
        width_spin.setValue(current_resolution.get('width', 1000))
        resolution_layout.addWidget(width_spin)
        resolution_layout.addWidget(QLabel("高:"))
        height_spin = QSpinBox()
        height_spin.setRange(100, 5000)
        height_spin.setValue(current_resolution.get('height', 600))
        resolution_layout.addWidget(height_spin)
        resolution_group.setLayout(resolution_layout)
        layout.addWidget(resolution_group)
        
        # Background color
        bg_layout = QHBoxLayout()
        bg_layout.addWidget(QLabel("背景颜色:"))
        bg_button = QPushButton("选择")
        bg_button.setStyleSheet(f"background-color: {current_bg}; color: black;")
        selected_color = [current_bg]
        
        def choose_bg_color():
            color = QColorDialog.getColor(QColor(selected_color[0]))
            if color.isValid():
                selected_color[0] = color.name()
                bg_button.setStyleSheet(f"background-color: {color.name()}; color: black;")
        
        bg_button.clicked.connect(choose_bg_color)
        bg_layout.addWidget(bg_button)
        layout.addLayout(bg_layout)
        
        # Is main screen
        main_checkbox = QCheckBox("设为主画面")
        main_checkbox.setChecked(current_is_main)
        layout.addWidget(main_checkbox)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            # Apply changes
            if hasattr(screen, 'name'):
                screen.name = name_edit.text()
                screen.number = number_spin.value()
                screen.resolution = {'width': width_spin.value(), 'height': height_spin.value()}
                screen.background_color = selected_color[0]
                
                # Handle main screen
                if main_checkbox.isChecked():
                    for s in self.screens:
                        s.is_main = False
                    screen.is_main = True
            else:
                screen['name'] = name_edit.text()
                screen['number'] = number_spin.value()
                screen['resolution'] = {'width': width_spin.value(), 'height': height_spin.value()}
                screen['background_color'] = selected_color[0]
                
                if main_checkbox.isChecked():
                    for s in self.screens:
                        s['is_main'] = False
                    screen['is_main'] = True
            
            # Refresh display if current screen was modified
            if screen_index == self.current_screen_index:
                self.refresh_screen_display()
            
            self.update_screen_list()
    
    def on_rename_screen_at_index(self, screen_index):
        """Rename screen at specific index"""
        if screen_index < 0 or screen_index >= len(self.screens):
            return
        screen = self.screens[screen_index]
        current_name = screen.name if hasattr(screen, 'name') else screen.get('name', 'Untitled')
        new_name, ok = QInputDialog.getText(self, "重命名画面", "新名称:", text=current_name)
        if ok and new_name:
            if hasattr(screen, 'name'):
                screen.name = new_name
            else:
                screen['name'] = new_name
            self.update_screen_list()
    
    def on_set_main_screen_at_index(self, screen_index):
        """Set screen at specific index as main"""
        if screen_index < 0 or screen_index >= len(self.screens):
            return
        
        for screen in self.screens:
            if hasattr(screen, 'is_main'):
                screen.is_main = False
            else:
                screen['is_main'] = False
        
        current_screen = self.screens[screen_index]
        if hasattr(current_screen, 'is_main'):
            current_screen.is_main = True
        else:
            current_screen['is_main'] = True
        
        self.update_screen_list()
        QMessageBox.information(self, "成功", "已设为主画面")
    
    def on_delete_screen_at_index(self, screen_index):
        """Delete screen at specific index"""
        if screen_index < 0 or screen_index >= len(self.screens) or len(self.screens) <= 1:
            QMessageBox.warning(self, "警告", "至少需要保留一个画面")
            return
        
        reply = QMessageBox.question(self, "确认", "确定要删除此画面吗？",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # If deleting current screen, switch to another one first
            if screen_index == self.current_screen_index:
                new_index = 0 if screen_index > 0 else 1
                self.switch_screen(new_index)
            
            del self.screens[screen_index]
            
            # Adjust current index if needed
            if self.current_screen_index >= len(self.screens):
                self.current_screen_index = len(self.screens) - 1
            
            self.update_screen_list()
    
    def on_rename_screen(self):
        """Rename the current screen"""
        self.on_rename_screen_at_index(self.current_screen_index)
    
    def on_set_main_screen(self):
        """Set the current screen as main screen"""
        if self.current_screen_index >= 0:
            for screen in self.screens:
                if hasattr(screen, 'is_main'):
                    screen.is_main = False
                else:
                    screen['is_main'] = False
            current_screen = self.screens[self.current_screen_index]
            if hasattr(current_screen, 'is_main'):
                current_screen.is_main = True
            else:
                current_screen['is_main'] = True
            QMessageBox.information(self, "成功", "已设为主画面")
    
    def on_delete_screen(self):
        """Delete the current screen"""
        if self.current_screen_index >= 0 and len(self.screens) > 1:
            reply = QMessageBox.question(self, "确认", "确定要删除当前画面吗？",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                del self.screens[self.current_screen_index]
                self.current_screen_index = max(0, self.current_screen_index - 1)
                screen = self.screens[self.current_screen_index]
                self.objects = screen.objects if hasattr(screen, 'objects') else screen.get('objects', [])
                self.refresh_screen_display()
                self.update_screen_list()
    
    def on_resolution_change(self):
        """Handle resolution change"""
        if self.current_screen_index >= 0:
            screen = self.screens[self.current_screen_index]
            new_resolution = {
                'width': self.width_spin.value(),
                'height': self.height_spin.value()
            }
            if hasattr(screen, 'resolution'):
                screen.resolution = new_resolution
            else:
                screen['resolution'] = new_resolution
            self.scene.setSceneRect(0, 0, self.width_spin.value(), self.height_spin.value())
            # Ensure scroll bars are enabled for large scenes
            self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.view.update()
            self.refresh_screen_display()
    
    def refresh_screen_display(self):
        """Request a screen refresh with delay batching"""
        if not self._refresh_pending:
            self._refresh_pending = True
            self._refresh_timer.start(50)  # 50ms delay for batching
    
    def _do_delayed_refresh(self):
        """Perform the actual delayed refresh"""
        self._refresh_pending = False
        self._perform_screen_refresh()
    
    def _perform_screen_refresh(self):
        """Perform the actual screen refresh with optimizations"""
        if not self._scene_needs_full_refresh:
            # Only update selection boxes if full refresh not needed
            if self.selected_objects and not self.dragging and not self.resizing:
                self._update_selection_boxes_only()
            return
        
        self.scene.clear()
        self._graphics_items_cache.clear()
        
        # Get current resolution
        resolution = self._get_current_resolution()
        
        # Update scene rect
        self._update_scene_rect()
        
        # Draw canvas background color
        self._draw_canvas_background()
        
        # Draw grid
        if self.show_grid:
            self.draw_grid()
        
        # Draw all objects with caching
        # Assign z-values based on object order (later objects on top)
        for i, obj in enumerate(self.objects):
            obj.z_value = i * 10  # Each object gets a range of 10 z-levels
            obj.draw(self.scene)
        
        # Draw selection boxes for all selected objects if not dragging/resizing
        if self.selected_objects and not self.dragging and not self.resizing:
            self.draw_selection_box()
        
        self._scene_needs_full_refresh = False
    
    def _draw_canvas_background(self):
        """Draw the canvas background color"""
        # Get current screen's background color
        bg_color = '#FFFFFF'  # Default white
        if self.current_screen_index >= 0 and self.current_screen_index < len(self.screens):
            screen = self.screens[self.current_screen_index]
            bg_color = screen.background_color if hasattr(screen, 'background_color') else screen.get('background_color', '#FFFFFF')
        
        # Get canvas size
        resolution = self._get_current_resolution()
        width = resolution.get('width', 1000)
        height = resolution.get('height', 600)
        
        # Draw background rectangle
        from PyQt5.QtWidgets import QGraphicsRectItem
        from PyQt5.QtGui import QBrush, QColor
        from PyQt5.QtCore import Qt
        
        bg_rect = QGraphicsRectItem(0, 0, width, height)
        bg_rect.setBrush(QBrush(QColor(bg_color)))
        bg_rect.setPen(QPen(Qt.NoPen))  # No border
        self.scene.addItem(bg_rect)
    
    def _update_selection_boxes_only(self):
        """Update only selection boxes without full refresh"""
        # Remove old selection boxes
        for item in self.scene.items():
            if hasattr(item, '_is_selection_box'):
                self.scene.removeItem(item)
        
        # Draw new selection boxes
        if self.selected_objects:
            self.draw_selection_box()
    
    def force_full_refresh(self):
        """Force a full screen refresh"""
        self._scene_needs_full_refresh = True
        self.refresh_screen_display()
    
    def _get_current_resolution(self):
        """Helper method to get current screen resolution"""
        resolution = {'width': 1000, 'height': 600}
        if self.current_screen_index >= 0 and self.current_screen_index < len(self.screens):
            screen = self.screens[self.current_screen_index]
            resolution = screen.resolution if hasattr(screen, 'resolution') else screen.get('resolution', resolution)
        return resolution
    
    def _update_scene_rect(self):
        """Helper method to update scene rectangle"""
        resolution = self._get_current_resolution()
        self.scene.setSceneRect(0, 0, resolution['width'], resolution['height'])
        # Ensure scroll bars are enabled for large scenes
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.view.update()
        return resolution
    
    def _block_signals_and_update(self, widget, value):
        """Helper method to block signals and update widget value"""
        widget.blockSignals(True)
        widget.setValue(value)
        widget.blockSignals(False)
    
    def _block_text_signals_and_update(self, widget, text):
        """Helper method to block signals and update widget text"""
        widget.blockSignals(True)
        widget.setText(text)
        widget.blockSignals(False)
    
    def _cleanup_graphics_cache(self):
        """Clean up graphics cache to free memory"""
        if hasattr(self, '_graphics_items_cache'):
            self._graphics_items_cache.clear()
    
    def _optimize_scene_memory(self):
        """Optimize scene memory by removing unused items"""
        try:
            items = self.scene.items()
            if len(items) > 1000:  # Threshold for cleanup
                # Remove items that are no longer needed
                for item in items:
                    if not hasattr(item, '_is_selection_box'):
                        # Keep selection boxes, remove others if needed
                        pass
        except Exception as e:
            pass  # Silently handle cleanup errors
    
    def align_selected(self, align_type):
        """Align selected objects to each other"""
        if not self.selected_objects:
            return
        
        self.save_state()
        
        # Use the first selected object as reference
        reference_obj = self.selected_objects[0]
        
        for obj in self.selected_objects:
            if obj == reference_obj:
                continue  # Skip reference object
            
            # Calculate the offset for line objects
            x_offset = 0
            y_offset = 0
            
            if align_type == "left":
                x_offset = reference_obj.x - obj.x
                obj.x = reference_obj.x
            elif align_type == "center":
                new_x = reference_obj.x + (reference_obj.width - obj.width) // 2
                x_offset = new_x - obj.x
                obj.x = new_x
            elif align_type == "right":
                new_x = reference_obj.x + reference_obj.width - obj.width
                x_offset = new_x - obj.x
                obj.x = new_x
            elif align_type == "top":
                y_offset = reference_obj.y - obj.y
                obj.y = reference_obj.y
            elif align_type == "middle":
                new_y = reference_obj.y + (reference_obj.height - obj.height) // 2
                y_offset = new_y - obj.y
                obj.y = new_y
            elif align_type == "bottom":
                new_y = reference_obj.y + reference_obj.height - obj.height
                y_offset = new_y - obj.y
                obj.y = new_y
            
            # For line objects, also update x1, y1, x2, y2 properties and recalculate bounds
            if obj.obj_type == 'line':
                if 'x1' in obj.properties:
                    obj.properties['x1'] += x_offset
                if 'x2' in obj.properties:
                    obj.properties['x2'] += x_offset
                if 'y1' in obj.properties:
                    obj.properties['y1'] += y_offset
                if 'y2' in obj.properties:
                    obj.properties['y2'] += y_offset
                
                # Recalculate bounding box from endpoints
                x1 = obj.properties.get('x1', 0)
                y1 = obj.properties.get('y1', 0)
                x2 = obj.properties.get('x2', 100)
                y2 = obj.properties.get('y2', 0)
                obj.x = min(x1, x2)
                obj.y = min(y1, y2)
                obj.width = abs(x2 - x1)
                obj.height = abs(y2 - y1)
        
        # Force full refresh after alignment
        self.force_full_refresh()
        self.update_properties_panel()
    
    def distribute_selected(self, distribute_type):
        """Distribute selected objects evenly (horizontal or vertical)"""
        if len(self.selected_objects) < 3:
            QMessageBox.information(self, "提示", "均布功能需要至少选择3个对象")
            return
        
        self.save_state()
        
        # Sort objects by position
        if distribute_type == 'horizontal':
            # Sort by x position
            sorted_objects = sorted(self.selected_objects, key=lambda obj: obj.x)
        else:  # vertical
            # Sort by y position
            sorted_objects = sorted(self.selected_objects, key=lambda obj: obj.y)
        
        # Get first and last objects
        first_obj = sorted_objects[0]
        last_obj = sorted_objects[-1]
        
        if distribute_type == 'horizontal':
            # Calculate total available space
            total_width = last_obj.x + last_obj.width - first_obj.x
            total_objects_width = sum(obj.width for obj in sorted_objects)
            available_space = total_width - total_objects_width
            
            if available_space <= 0:
                QMessageBox.information(self, "提示", "对象之间没有足够的空间进行均布")
                return
            
            # Calculate spacing between objects
            num_gaps = len(sorted_objects) - 1
            spacing = available_space / num_gaps
            
            # Position objects
            current_x = first_obj.x + first_obj.width + spacing
            for obj in sorted_objects[1:-1]:  # Skip first and last
                x_offset = current_x - obj.x
                obj.x = int(current_x)
                
                # Update line object properties
                if obj.obj_type == 'line':
                    if 'x1' in obj.properties:
                        obj.properties['x1'] += x_offset
                    if 'x2' in obj.properties:
                        obj.properties['x2'] += x_offset
                    # Recalculate bounds
                    x1 = obj.properties.get('x1', 0)
                    x2 = obj.properties.get('x2', 100)
                    obj.x = min(x1, x2)
                    obj.width = abs(x2 - x1)
                
                current_x += obj.width + spacing
        else:  # vertical
            # Calculate total available space
            total_height = last_obj.y + last_obj.height - first_obj.y
            total_objects_height = sum(obj.height for obj in sorted_objects)
            available_space = total_height - total_objects_height
            
            if available_space <= 0:
                QMessageBox.information(self, "提示", "对象之间没有足够的空间进行均布")
                return
            
            # Calculate spacing between objects
            num_gaps = len(sorted_objects) - 1
            spacing = available_space / num_gaps
            
            # Position objects
            current_y = first_obj.y + first_obj.height + spacing
            for obj in sorted_objects[1:-1]:  # Skip first and last
                y_offset = current_y - obj.y
                obj.y = int(current_y)
                
                # Update line object properties
                if obj.obj_type == 'line':
                    if 'y1' in obj.properties:
                        obj.properties['y1'] += y_offset
                    if 'y2' in obj.properties:
                        obj.properties['y2'] += y_offset
                    # Recalculate bounds
                    y1 = obj.properties.get('y1', 0)
                    y2 = obj.properties.get('y2', 0)
                    obj.y = min(y1, y2)
                    obj.height = abs(y2 - y1)
                
                current_y += obj.height + spacing
        
        # Force full refresh after distribution
        self.force_full_refresh()
        self.update_properties_panel()
    
    def bring_to_front(self):
        """Bring selected object to front"""
        if self.selected_object and self.selected_object in self.objects:
            self.save_state()
            self.objects.remove(self.selected_object)
            self.objects.append(self.selected_object)
            self.force_full_refresh()
    
    def send_to_back(self):
        """Send selected object to back"""
        if self.selected_object and self.selected_object in self.objects:
            self.save_state()
            self.objects.remove(self.selected_object)
            self.objects.insert(0, self.selected_object)
            self.force_full_refresh()
    
    def raise_object(self):
        """Raise selected object one layer up"""
        if self.selected_object and self.selected_object in self.objects:
            index = self.objects.index(self.selected_object)
            if index < len(self.objects) - 1:
                self.save_state()
                # Swap with the object above
                self.objects[index], self.objects[index + 1] = self.objects[index + 1], self.objects[index]
                self.force_full_refresh()
    
    def lower_object(self):
        """Lower selected object one layer down"""
        if self.selected_object and self.selected_object in self.objects:
            index = self.objects.index(self.selected_object)
            if index > 0:
                self.save_state()
                # Swap with the object below
                self.objects[index], self.objects[index - 1] = self.objects[index - 1], self.objects[index]
                self.force_full_refresh()
    
    def save_state(self):
        """Save current state for undo"""
        import copy
        state = []
        for obj in self.objects:
            # Deep copy the object
            obj_copy = copy.deepcopy(obj)
            state.append(obj_copy)
        self.undo_stack.append(state)
        # Limit undo stack size
        if len(self.undo_stack) > self.max_undo_steps:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
    
    def undo(self):
        """Undo last action"""
        if self.undo_stack:
            # Save current state to redo stack (deep copy)
            import copy
            current_state = [copy.deepcopy(obj) for obj in self.objects]
            self.redo_stack.append(current_state)
            # Restore previous state
            previous_state = self.undo_stack.pop()
            self.objects.clear()
            self.objects.extend(previous_state)
            self.force_full_refresh()
    
    def redo(self):
        """Redo last undone action"""
        if self.redo_stack:
            # Save current state to undo stack (deep copy)
            import copy
            current_state = [copy.deepcopy(obj) for obj in self.objects]
            self.undo_stack.append(current_state)
            # Restore next state
            next_state = self.redo_stack.pop()
            self.objects.clear()
            self.objects.extend(next_state)
            self.force_full_refresh()
    
    def clear_canvas(self):
        """Clear all objects from canvas"""
        reply = QMessageBox.question(self, "确认", "确定要清空画布吗？",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.save_state()
            self.objects.clear()
            self.refresh_screen_display()
    
    def keyPressEvent(self, event):
        """Handle key press events for the entire dialog"""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            # 阻止回车键触发任何操作
            event.accept()
            return
        super().keyPressEvent(event)
    
    def on_key_press(self, event):
        """Handle key press events for the graphics view"""
        # Check if inline editor is active
        if hasattr(self, 'inline_editor') and self.inline_editor:
            if event.key() == Qt.Key_Escape:
                # Cancel editing without saving
                self.inline_editor.deleteLater()
                self.inline_editor = None
                self.inline_editor_obj = None
                event.accept()
                return
            # Let the editor handle other keys
            event.ignore()
            return
        
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            # 阻止回车键触发任何操作
            event.accept()
            return
        elif event.key() == Qt.Key_Delete and self.selected_object:
            self.delete_selected_object()
        elif event.key() == Qt.Key_Z and event.modifiers() == Qt.ControlModifier:
            self.undo()
        elif event.key() == Qt.Key_Y and event.modifiers() == Qt.ControlModifier:
            self.redo()
        elif event.key() == Qt.Key_C and event.modifiers() == Qt.ControlModifier:
            self.copy_selected_object()
        elif event.key() == Qt.Key_V and event.modifiers() == Qt.ControlModifier:
            self.paste_object()
        elif event.key() == Qt.Key_X and event.modifiers() == Qt.ControlModifier:
            self.cut_selected_object()
        elif event.key() == Qt.Key_D and event.modifiers() == Qt.ControlModifier:
            self.duplicate_selected_object()
        elif event.key() == Qt.Key_A and event.modifiers() == Qt.ControlModifier:
            self.select_all_objects()
    
    def delete_selected_object(self):
        """Delete the currently selected object(s)"""
        if self.selected_objects:
            self.save_state()
            # Handle deletion for all selected objects
            for obj in self.selected_objects[:]:  # Use slice copy to safely iterate while removing
                if obj in self.objects:
                    self.objects.remove(obj)
            
            # Clear selections after deletion
            self.selected_object = None
            self.selected_objects = []
            # Force full refresh to immediately update the display
            self.force_full_refresh()
            self.update_properties_panel()
    
    def copy_selected_object(self):
        """Copy the selected object(s) to clipboard"""
        if self.selected_objects:
            # Create a copy of all selected objects' data
            self.clipboard = []
            for obj in self.selected_objects:
                # Use deepcopy for objects to handle special cases like HMIPictureBox
                try:
                    import copy
                    obj_copy = copy.deepcopy(obj)
                    # Convert to data dict
                    obj_data = {
                        'obj_type': obj_copy.obj_type,
                        'width': obj_copy.width,
                        'height': obj_copy.height,
                        'properties': obj_copy.properties,
                        'variables': [],
                        'x': obj_copy.x,
                        'y': obj_copy.y
                    }
                    # Copy variable bindings
                    for var in obj_copy.variables:
                        obj_data['variables'].append({
                            'variable_name': var.variable_name,
                            'variable_type': var.variable_type,
                            'address': var.address,
                            'description': var.description,
                            'bit_offset': getattr(var, 'bit_offset', None)
                        })
                    self.clipboard.append(obj_data)
                except Exception as e:
                    print(f"Error copying object: {e}")
                    # Fallback to simple copy
                    obj_data = {
                        'obj_type': obj.obj_type,
                        'width': obj.width,
                        'height': obj.height,
                        'properties': obj.properties.copy(),
                        'variables': [],
                        'x': obj.x,
                        'y': obj.y
                    }
                    for var in obj.variables:
                        obj_data['variables'].append({
                            'variable_name': var.variable_name,
                            'variable_type': var.variable_type,
                            'address': var.address,
                            'description': var.description,
                            'bit_offset': getattr(var, 'bit_offset', None)
                        })
                    self.clipboard.append(obj_data)
            
            # Also save to system clipboard as JSON data
            import json
            clipboard = QApplication.clipboard()
            mime_data = QMimeData()
            mime_data.setData('application/x-hmi-objects', json.dumps(self.clipboard).encode('utf-8'))
            clipboard.setMimeData(mime_data)
            
            self.clipboard_offset = 10  # Initial offset for paste
            print(f"Copied {len(self.selected_objects)} object(s) to clipboard")
    
    def paste_object(self):
        """Paste the object(s) from clipboard at mouse cursor position"""
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        # Check system clipboard for HMI objects (last copied item)
        if mime_data.hasFormat('application/x-hmi-objects'):
            self._paste_hmi_objects_from_clipboard(mime_data)
            return
        
        # Check system clipboard for images (screenshots, etc.)
        if mime_data.hasImage():
            self._paste_image_from_clipboard(clipboard)
            return
        
        # Check for file paths (copied from file explorer)
        if mime_data.hasUrls():
            self._paste_files_from_clipboard(mime_data)
            return
        
        # Fallback to internal clipboard
        if self.clipboard:
            self._paste_internal_clipboard()
            return
        
        # Nothing to paste
        print("Clipboard is empty")
    
    def _paste_internal_clipboard(self):
        """Paste objects from internal clipboard"""
        if not self.clipboard:
            return
        
        self.save_state()
        
        # Get mouse cursor position in view coordinates
        cursor_pos = self.view.mapFromGlobal(QCursor.pos())
        scene_pos = self.view.mapToScene(cursor_pos)
        x, y = int(scene_pos.x()), int(scene_pos.y())
        
        # Handle both single object (legacy) and multiple objects (new)
        if isinstance(self.clipboard, list):
            # Multiple objects
            # Calculate offset from first object's original position
            first_obj = self.clipboard[0]
            offset_x = x - first_obj['x']
            offset_y = y - first_obj['y']
            
            new_objects = []
            for obj_data in self.clipboard:
                # Create new object with offset position
                new_obj_data = obj_data.copy()
                new_obj_data['x'] = obj_data['x'] + offset_x
                new_obj_data['y'] = obj_data['y'] + offset_y
                
                # Special handling for line objects - also update x1, y1, x2, y2
                if obj_data.get('obj_type') == 'line':
                    props = new_obj_data.get('properties', {})
                    if 'x1' in props:
                        props['x1'] = props['x1'] + offset_x
                    if 'y1' in props:
                        props['y1'] = props['y1'] + offset_y
                    if 'x2' in props:
                        props['x2'] = props['x2'] + offset_x
                    if 'y2' in props:
                        props['y2'] = props['y2'] + offset_y
                
                obj = self.create_object_from_data(new_obj_data)
                if obj:
                    self.objects.append(obj)
                    new_objects.append(obj)
            
            if new_objects:
                # Select all pasted objects
                self.selected_objects = new_objects
                self.selected_object = new_objects[-1]  # Last one as primary
                self.force_full_refresh()
                print(f"Pasted {len(new_objects)} object(s) from clipboard at ({x}, {y})")
        else:
            # Single object (legacy format)
            obj_data = self.clipboard.copy()
            
            # Calculate offset from original position
            offset_x = x - obj_data['x']
            offset_y = y - obj_data['y']
            
            obj_data['x'] = x
            obj_data['y'] = y
            
            # Special handling for line objects - also update x1, y1, x2, y2
            if obj_data.get('obj_type') == 'line':
                props = obj_data.get('properties', {})
                if 'x1' in props:
                    props['x1'] = props['x1'] + offset_x
                if 'y1' in props:
                    props['y1'] = props['y1'] + offset_y
                if 'x2' in props:
                    props['x2'] = props['x2'] + offset_x
                if 'y2' in props:
                    props['y2'] = props['y2'] + offset_y
            
            obj = self.create_object_from_data(obj_data)
            if obj:
                self.objects.append(obj)
                self.selected_object = obj
                self.selected_objects = [obj]
                self.force_full_refresh()
                print(f"Pasted {obj.obj_type} from clipboard at ({x}, {y})")
    
    def _paste_image_from_clipboard(self, clipboard):
        """Paste image from system clipboard and create a picture object"""
        image = clipboard.image()
        if image.isNull():
            return
        
        self.save_state()
        
        # Get mouse cursor position in view coordinates
        cursor_pos = self.view.mapFromGlobal(QCursor.pos())
        scene_pos = self.view.mapToScene(cursor_pos)
        x, y = int(scene_pos.x()), int(scene_pos.y())
        
        # Save the image to a temporary file in the project directory
        try:
            # Get project directory
            project_dir = os.path.dirname(self.current_file) if self.current_file else os.getcwd()
            images_dir = os.path.join(project_dir, 'images')
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)
            
            # Generate unique filename
            import time
            timestamp = int(time.time() * 1000)
            image_filename = f"pasted_image_{timestamp}.png"
            image_path = os.path.join(images_dir, image_filename)
            
            # Save the image
            image.save(image_path, 'PNG')
            print(f"Saved clipboard image to: {image_path}")
            
            # Create picture object
            width = min(image.width(), 300)  # Limit max width
            height = min(image.height(), 300)  # Limit max height
            
            # If image is too large, scale it down while maintaining aspect ratio
            if image.width() > 300 or image.height() > 300:
                scaled = image.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                width = scaled.width()
                height = scaled.height()
            
            obj = HMIPictureBox(x=x - width//2, y=y - height//2, width=width, height=height, image_path=image_path)
            self.objects.append(obj)
            self.selected_object = obj
            self.selected_objects = [obj]
            self.force_full_refresh()
            self.update_properties_panel()
            print(f"Pasted image from clipboard at ({x}, {y}), size: {width}x{height}")
            
        except Exception as e:
            print(f"Error saving clipboard image: {e}")
            # Create picture object without saving (fallback)
            obj = HMIPictureBox(x=x - 50, y=y - 50, width=100, height=100, image_path='')
            self.objects.append(obj)
            self.selected_object = obj
            self.selected_objects = [obj]
            self.force_full_refresh()
    
    def cut_selected_object(self):
        """Cut the selected object(s) to clipboard"""
        if self.selected_objects:
            self.copy_selected_object()
            self.delete_selected_object()
            print(f"Cut {len(self.selected_objects)} object(s)")
    
    def _paste_files_from_clipboard(self, mime_data):
        """Paste files from clipboard (e.g., copied from file explorer)"""
        urls = mime_data.urls()
        if not urls:
            return
        
        self.save_state()
        
        # Get mouse cursor position in view coordinates
        cursor_pos = self.view.mapFromGlobal(QCursor.pos())
        scene_pos = self.view.mapToScene(cursor_pos)
        x, y = int(scene_pos.x()), int(scene_pos.y())
        
        # Supported image formats
        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp']
        
        new_objects = []
        offset_x = 0
        offset_y = 0
        
        for url in urls:
            file_path = url.toLocalFile()
            if not file_path or not os.path.exists(file_path):
                continue
            
            # Check if it's an image file
            ext = os.path.splitext(file_path)[1].lower()
            if ext in image_extensions:
                try:
                    # Copy image to project directory
                    project_dir = os.path.dirname(self.current_file) if self.current_file else os.getcwd()
                    images_dir = os.path.join(project_dir, 'images')
                    if not os.path.exists(images_dir):
                        os.makedirs(images_dir)
                    
                    # Generate unique filename
                    import time
                    timestamp = int(time.time() * 1000)
                    filename = os.path.basename(file_path)
                    name, _ = os.path.splitext(filename)
                    new_filename = f"{name}_{timestamp}{ext}"
                    dest_path = os.path.join(images_dir, new_filename)
                    
                    # Copy the file
                    import shutil
                    shutil.copy2(file_path, dest_path)
                    print(f"Copied image to project: {dest_path}")
                    
                    # Load image to get dimensions
                    pixmap = QPixmap(dest_path)
                    if not pixmap.isNull():
                        # Limit max size
                        width = min(pixmap.width(), 300)
                        height = min(pixmap.height(), 300)
                        
                        # Scale if too large
                        if pixmap.width() > 300 or pixmap.height() > 300:
                            scaled = pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            width = scaled.width()
                            height = scaled.height()
                        
                        # Create picture object with offset for multiple images
                        obj_x = x + offset_x - width // 2
                        obj_y = y + offset_y - height // 2
                        
                        obj = HMIPictureBox(x=obj_x, y=obj_y, width=width, height=height, image_path=dest_path)
                        self.objects.append(obj)
                        new_objects.append(obj)
                        
                        # Offset next image
                        offset_x += 20
                        offset_y += 20
                        
                except Exception as e:
                    print(f"Error copying image file {file_path}: {e}")
        
        if new_objects:
            self.selected_objects = new_objects
            self.selected_object = new_objects[-1]
            self.force_full_refresh()
            self.update_properties_panel()
            print(f"Pasted {len(new_objects)} image(s) from file explorer")
        else:
            print("No valid image files found in clipboard")
    
    def _paste_hmi_objects_from_clipboard(self, mime_data):
        """Paste HMI objects from system clipboard"""
        import json
        try:
            data = mime_data.data('application/x-hmi-objects').data()
            clipboard_data = json.loads(data.decode('utf-8'))
            
            self.save_state()
            
            # Get mouse cursor position in view coordinates
            cursor_pos = self.view.mapFromGlobal(QCursor.pos())
            scene_pos = self.view.mapToScene(cursor_pos)
            x, y = int(scene_pos.x()), int(scene_pos.y())
            
            # Handle both single object (legacy) and multiple objects (new)
            if isinstance(clipboard_data, list):
                # Multiple objects
                first_obj = clipboard_data[0]
                offset_x = x - first_obj['x']
                offset_y = y - first_obj['y']
                
                new_objects = []
                for obj_data in clipboard_data:
                    new_obj_data = obj_data.copy()
                    new_obj_data['x'] = obj_data['x'] + offset_x
                    new_obj_data['y'] = obj_data['y'] + offset_y
                    
                    # Special handling for line objects
                    if obj_data.get('obj_type') == 'line':
                        props = new_obj_data.get('properties', {})
                        if 'x1' in props:
                            props['x1'] = props['x1'] + offset_x
                        if 'y1' in props:
                            props['y1'] = props['y1'] + offset_y
                        if 'x2' in props:
                            props['x2'] = props['x2'] + offset_x
                        if 'y2' in props:
                            props['y2'] = props['y2'] + offset_y
                    
                    obj = self.create_object_from_data(new_obj_data)
                    if obj:
                        self.objects.append(obj)
                        new_objects.append(obj)
                
                if new_objects:
                    self.selected_objects = new_objects
                    self.selected_object = new_objects[-1]
                    self.force_full_refresh()
                    print(f"Pasted {len(new_objects)} object(s) from clipboard at ({x}, {y})")
            else:
                # Single object (legacy format)
                obj_data = clipboard_data.copy()
                offset_x = x - obj_data['x']
                offset_y = y - obj_data['y']
                obj_data['x'] = x
                obj_data['y'] = y
                
                if obj_data.get('obj_type') == 'line':
                    props = obj_data.get('properties', {})
                    if 'x1' in props:
                        props['x1'] = props['x1'] + offset_x
                    if 'y1' in props:
                        props['y1'] = props['y1'] + offset_y
                    if 'x2' in props:
                        props['x2'] = props['x2'] + offset_x
                    if 'y2' in props:
                        props['y2'] = props['y2'] + offset_y
                
                obj = self.create_object_from_data(obj_data)
                if obj:
                    self.objects.append(obj)
                    self.selected_object = obj
                    self.selected_objects = [obj]
                    self.force_full_refresh()
                    print(f"Pasted {obj.obj_type} from clipboard at ({x}, {y})")
        except Exception as e:
            print(f"Error pasting from clipboard: {e}")
    
    def duplicate_selected_object(self):
        """Duplicate the selected object(s)"""
        if self.selected_objects:
            self.save_state()
            
            new_objects = []
            for obj in self.selected_objects:
                # Create object data with offset
                obj_data = {
                    'obj_type': obj.obj_type,
                    'x': obj.x + 20,
                    'y': obj.y + 20,
                    'width': obj.width,
                    'height': obj.height,
                    'properties': obj.properties.copy(),
                    'variables': [],
                    'visibility': getattr(obj, 'visibility', {}).copy()
                }
                
                # Copy variable bindings
                for var in obj.variables:
                    obj_data['variables'].append({
                        'variable_name': var.variable_name,
                        'variable_type': var.variable_type,
                        'address': var.address,
                        'description': var.description,
                        'bit_offset': getattr(var, 'bit_offset', None)
                    })
                
                new_obj = self.create_object_from_data(obj_data)
                if new_obj:
                    self.objects.append(new_obj)
                    new_objects.append(new_obj)
            
            if new_objects:
                # Select all duplicated objects
                self.selected_objects = new_objects
                self.selected_object = new_objects[-1]  # Last one as primary
                self.force_full_refresh()
                print(f"Duplicated {len(new_objects)} object(s)")
    
    def select_all_objects(self):
        """Select all objects on the canvas"""
        if self.objects:
            self.selected_objects = self.objects.copy()
            self.selected_object = self.objects[-1] if self.objects else None
            self.force_full_refresh()
            self.update_properties_panel()
            print(f"Selected all {len(self.selected_objects)} object(s)")
    
    def save_screen(self):
        """Save HMI screens to the project file"""
        try:
            # Find MainWindow to access project manager
            main_window = self.window()
            while main_window and not hasattr(main_window, 'project_manager'):
                main_window = main_window.parent()
            
            if main_window and hasattr(main_window, 'save_project'):
                # Call MainWindow's save_project method
                main_window.save_project()
            else:
                # Fallback: save to separate file
                self._save_screen_to_file()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存HMI项目失败: {str(e)}")
    
    def _save_screen_to_file(self):
        """Save HMI screens to a separate JSON file (fallback)"""
        try:
            if not self.current_file:
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "保存HMI项目", "", "HMI项目文件 (*.hmi);;JSON文件 (*.json)")
                if not file_path:
                    return
                self.current_file = file_path
            else:
                file_path = self.current_file
            
            project_data = {'screens': []}
            
            for screen in self.screens:
                screen_data = {
                    'name': screen.name if hasattr(screen, 'name') else screen['name'],
                    'number': screen.number if hasattr(screen, 'number') else screen.get('number', 0),
                    'is_main': screen.is_main if hasattr(screen, 'is_main') else screen.get('is_main', False),
                    'resolution': screen.resolution if hasattr(screen, 'resolution') else screen.get('resolution', {'width': 1000, 'height': 600}),
                    'background_color': screen.background_color if hasattr(screen, 'background_color') else screen.get('background_color', '#FFFFFF'),
                    'objects': []
                }
                
                objects = screen.objects if hasattr(screen, 'objects') else screen['objects']
                for obj in objects:
                    obj_data = {
                        'obj_type': obj.obj_type,
                        'x': obj.x,
                        'y': obj.y,
                        'width': obj.width,
                        'height': obj.height,
                        'properties': obj.properties,
                        'variables': []
                    }
                    
                    for var in obj.variables:
                        var_data = {
                            'variable_name': var.variable_name,
                            'variable_type': var.variable_type,
                            'address': var.address,
                            'description': var.description,
                            'bit_offset': getattr(var, 'bit_offset', None)
                        }
                        obj_data['variables'].append(var_data)
                    
                    screen_data['objects'].append(obj_data)
                
                project_data['screens'].append(screen_data)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2, ensure_ascii=False)
            
            QMessageBox.information(self, "成功", f"HMI项目已保存到 {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存HMI项目失败: {str(e)}")
    
    def load_screen(self):
        """Load HMI screens from a JSON file"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "加载HMI项目", "", "HMI文件 (*.hmi);;JSON文件 (*.json)")
            if not file_path:
                return
            
            with open(file_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            # Clear current screens
            self.screens = []
            self.current_screen_index = -1
            
            # Load screens
            for idx, screen_data in enumerate(project_data.get('screens', [])):
                # Get number from data or use index as default
                screen_number = screen_data.get('number', idx)
                screen = HMIScreen(
                    name=screen_data['name'],
                    number=screen_number
                )
                screen.is_main = screen_data.get('is_main', False)
                screen.resolution = screen_data.get('resolution', {'width': 1000, 'height': 600})
                screen.background_color = screen_data.get('background_color', '#FFFFFF')
                
                for obj_data in screen_data.get('objects', []):
                    obj = self.create_object_from_data(obj_data)
                    if obj:
                        screen.objects.append(obj)
                
                self.screens.append(screen)
            
            if self.screens:
                self.current_screen_index = 0
                self.objects = self.screens[0].objects
                self.refresh_screen_display()
                self.update_screen_list()
            
            self.current_file = file_path
            QMessageBox.information(self, "成功", f"HMI项目已加载: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载HMI项目失败: {str(e)}")
    
    def create_object_from_data(self, obj_data):
        """Create an HMI object from JSON data"""
        obj_type = obj_data.get('obj_type', '')
        x = obj_data.get('x', 0)
        y = obj_data.get('y', 0)
        width = obj_data.get('width', 100)
        height = obj_data.get('height', 50)
        properties = obj_data.get('properties', {})
        
        if obj_type == 'button':
            obj = HMIButton(x, y, width, height, properties.get('text', 'Button'))
        elif obj_type == 'label':
            obj = HMILabel(x, y, width, height, properties.get('text', 'Label'))
        elif obj_type == 'gauge':
            obj = HMIGauge(x, y, width, height, properties.get('min_val', 0), properties.get('max_val', 100))
        elif obj_type == 'switch':
            obj = HMISwitch(x, y, width, height, properties.get('state', False))
        elif obj_type == 'light':
            obj = HMILight(x, y, width, height, properties.get('state', False))
        elif obj_type == 'picture':
            obj = HMIPictureBox(x, y, width, height, properties.get('image_path', ''))
        elif obj_type == 'picture_list':
            obj = HMIPictureList(x, y, width, height)
        elif obj_type == 'trend_chart':
            obj = HMITrendChart(x, y, width, height)
        elif obj_type == 'history_trend':
            obj = HMIHistoryTrend(x, y, width, height)
        elif obj_type == 'table_view':
            obj = HMITableView(x, y, width, height)
        elif obj_type == 'progress':
            obj = HMIProgressBar(x, y, width, height, properties.get('value', 50))
        elif obj_type == 'line':
            # For line, use the properties directly since x, y, width, height are derived from x1, y1, x2, y2
            x1 = properties.get('x1', x)
            y1 = properties.get('y1', y)
            x2 = properties.get('x2', x + width)
            y2 = properties.get('y2', y + height)
            obj = HMILine(x1, y1, x2, y2)
        elif obj_type == 'rectangle':
            obj = HMIRectangle(x, y, width, height)
        elif obj_type == 'circle':
            obj = HMICircle(x + width // 2, y + height // 2, width // 2)
        elif obj_type == 'input':
            obj = HMIInputField(x, y, width, height)
        elif obj_type == 'checkbox':
            obj = HMICheckBox(x, y, width, height)
        elif obj_type == 'dropdown':
            obj = HMIDropdown(x, y, width, height)
        elif obj_type == 'textarea':
            obj = HMITextArea(x, y, width, height)
        elif obj_type == 'text_list':
            obj = HMITextList(x, y, width, height)
        elif obj_type == 'alarm_display':
            obj = HMIAlarmDisplay(x, y, width, height)
        else:
            return None
        
        obj.properties = properties
        
        # Set visibility settings if provided
        if 'visibility' in obj_data:
            obj.visibility = obj_data['visibility'].copy()
        
        for var_data in obj_data.get('variables', []):
            var = VariableBinding(
                var_data.get('variable_name', ''),
                var_data.get('variable_type', ''),
                var_data.get('address', ''),
                var_data.get('description', ''),
                var_data.get('bit_offset', None)
            )
            obj.variables.append(var)
        
        return obj
    
    def run_screen(self):
        """Run the HMI screen"""
        QMessageBox.information(self, "运行", "请在主窗口点击'运行系统'按钮来运行HMI画面")
