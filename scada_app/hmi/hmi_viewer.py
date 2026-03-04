"""
HMI Viewer - Runtime view for HMI screens
Displays HMI screens with live data updates
"""
import json
import math
import os
import threading
import time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsEllipseItem,
    QGraphicsPolygonItem, QGraphicsPathItem, QGraphicsLineItem,
    QGraphicsPixmapItem, QComboBox, QLabel, QMessageBox, QInputDialog, QPushButton,
    QGraphicsItem, QApplication
)
from PyQt5.QtCore import Qt, QTimer, QPointF, pyqtSignal, QObject
from PyQt5.QtGui import QPen, QBrush, QColor, QFont, QPainterPath, QPolygonF, QPainter, QPixmap

# Import HMI object classes from designer
from .hmi_designer import (
    HMIButton, HMILabel, HMIGauge, HMISwitch, HMILight,
    HMIPictureBox, HMIPictureList, HMITrendChart, HMIHistoryTrend, HMITableView, 
    HMIProgressBar, HMIInputField,
    HMICheckBox, HMIDropdown, HMIAlarmDisplay,
    HMITextArea, HMITextList, HMILine, HMIRectangle, HMICircle,
    HMIClock
)


class TrendDataManager:
    """Global trend data manager - shared across all trend charts"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.data_history = {}
        self.max_data_points = 86400
        self.max_file_data_hours = 24
        self.max_file_size_mb = 10
        self.data_file_path = None
        self.last_save_time = 0
        self.subscribed_vars = set()
    
    def initialize(self, project_path):
        """Initialize with project path"""
        if project_path:
            data_dir = os.path.join(os.path.dirname(project_path), 'trend_data')
            os.makedirs(data_dir, exist_ok=True)
            self.data_file_path = os.path.join(data_dir, 'trend_data.json')
            self.load_data_from_file()
    
    def subscribe_var(self, var_name):
        """Subscribe a variable for trend tracking"""
        if var_name:
            self.subscribed_vars.add(var_name)
            if var_name not in self.data_history:
                self.data_history[var_name] = []
    
    def add_data_point(self, var_name, timestamp, value):
        """Add a data point for a variable"""
        if var_name not in self.data_history:
            self.data_history[var_name] = []
        
        self.data_history[var_name].append((timestamp, value))
        
        cutoff_time = timestamp - (self.max_file_data_hours * 3600 * 1000)
        if len(self.data_history[var_name]) > self.max_data_points:
            self.data_history[var_name] = [
                p for p in self.data_history[var_name] if p[0] > cutoff_time
            ]
    
    def get_data_for_timespan(self, var_name, time_span):
        """Get data points for a variable within time span"""
        current_time = time.time() * 1000
        cutoff_time = current_time - (time_span * 1000)
        
        if var_name not in self.data_history:
            return []
        
        return [(ts, val) for ts, val in self.data_history[var_name] if ts >= cutoff_time]
    
    def get_all_data_for_timespan(self, time_span):
        """Get all data within time span"""
        current_time = time.time() * 1000
        cutoff_time = current_time - (time_span * 1000)
        
        result = {}
        for var_name, data_points in self.data_history.items():
            filtered = [(ts, val) for ts, val in data_points if ts >= cutoff_time]
            if filtered:
                result[var_name] = filtered
        return result
    
    def load_data_from_file(self):
        """Load historical data from JSON file"""
        if not self.data_file_path or not os.path.exists(self.data_file_path):
            return
        
        try:
            file_size = os.path.getsize(self.data_file_path)
            if file_size > self.max_file_size_mb * 1024 * 1024:
                print(f"TrendDataManager: File large ({file_size / 1024 / 1024:.1f}MB), will compress")
            
            with open(self.data_file_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            current_time = time.time() * 1000
            cutoff_time = current_time - (self.max_file_data_hours * 3600 * 1000)
            
            total_points = 0
            for var_name, data_points in saved_data.items():
                filtered_points = [
                    (ts, val) for ts, val in data_points 
                    if ts > cutoff_time
                ]
                if len(filtered_points) > self.max_data_points:
                    step = len(filtered_points) // self.max_data_points
                    filtered_points = filtered_points[::step][:self.max_data_points]
                
                if filtered_points:
                    self.data_history[var_name] = filtered_points
                    total_points += len(filtered_points)
            
            print(f"TrendDataManager: Loaded {total_points} points, {len(self.data_history)} variables")
        except Exception as e:
            print(f"TrendDataManager: Error loading data: {e}")
    
    def save_data_to_file(self):
        """Save current data to JSON file"""
        if not self.data_file_path:
            return
        
        try:
            current_time = time.time() * 1000
            cutoff_time = current_time - (self.max_file_data_hours * 3600 * 1000)
            
            data_to_save = {}
            total_points = 0
            for var_name, data_points in self.data_history.items():
                filtered_points = [
                    [ts, val] for ts, val in data_points 
                    if ts > cutoff_time
                ]
                if len(filtered_points) > self.max_data_points:
                    step = len(filtered_points) // self.max_data_points
                    filtered_points = filtered_points[::step][:self.max_data_points]
                
                if filtered_points:
                    data_to_save[var_name] = filtered_points
                    total_points += len(filtered_points)
            
            temp_path = self.data_file_path + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f)
            
            file_size = os.path.getsize(temp_path)
            if file_size > self.max_file_size_mb * 1024 * 1024:
                for var_name in data_to_save:
                    if len(data_to_save[var_name]) > self.max_data_points // 2:
                        data_to_save[var_name] = data_to_save[var_name][::2]
                
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data_to_save, f)
                file_size = os.path.getsize(temp_path)
            
            if os.path.exists(self.data_file_path):
                os.remove(self.data_file_path)
            os.rename(temp_path, self.data_file_path)
            
            self.last_save_time = current_time
            print(f"TrendDataManager: Saved {total_points} points ({file_size / 1024:.1f}KB)")
        except Exception as e:
            print(f"TrendDataManager: Error saving data: {e}")
    
    def update_from_data_manager(self, data_manager):
        """Update trend data from data manager"""
        current_time = time.time() * 1000
        
        for var_name in self.subscribed_vars:
            value = data_manager.get_tag_value(var_name)
            if value is None:
                continue
            
            try:
                value = float(value)
            except (ValueError, TypeError):
                continue
            
            self.add_data_point(var_name, current_time, value)
        
        if current_time - self.last_save_time >= 3600 * 1000:
            self.save_data_to_file()


class HMIClockRuntime(HMIClock):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the clock in runtime mode with live updates"""
        import datetime
        
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
            
            # Get current time
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
            
            # Draw second hand
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
            now = datetime.datetime.now()
            
            # Format date and time
            display_text = ""
            
            if self.properties.get('show_date', True):
                date_format = self.properties.get('date_format', 'YYYY-MM-DD')
                # Simple format conversion
                formatted_date = now.strftime(date_format.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d'))
                display_text += formatted_date + "\n"
            
            if self.properties.get('show_time', True):
                show_seconds = self.properties.get('show_seconds', True)
                time_format = self.properties.get('time_format', 'HH:MM:SS')
                
                # If show_seconds is False, ensure we don't show seconds
                if not show_seconds:
                    # Remove seconds part from format
                    if time_format.endswith(':SS'):
                        time_format = time_format[:-3]
                    elif time_format.endswith('SS'):
                        time_format = time_format[:-2]
                    # Also handle cases where seconds might be in the middle
                    if ':SS:' in time_format:
                        time_format = time_format.replace(':SS:', ':')
                
                # Convert format to strftime format
                strftime_format = time_format.replace('HH', '%H').replace('MM', '%M').replace('SS', '%S')
                # If show_seconds is False but format still contains seconds, use appropriate format
                if not show_seconds and '%S' in strftime_format:
                    strftime_format = strftime_format.replace(':%S', '')
                
                formatted_time = now.strftime(strftime_format)
                display_text += formatted_time
            
            # Create text item
            font = QFont()
            font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
            font.setPointSize(self.properties.get('font_size', 12))
            font.setBold(self.properties.get('font_bold', False))
            font.setItalic(self.properties.get('font_italic', False))
            font.setUnderline(self.properties.get('font_underline', False))
            
            text_item = QGraphicsTextItem(display_text.strip())
            text_item.setFont(font)
            text_item.setDefaultTextColor(QColor(self.properties.get('text_color', '#000000')))
            
            # Position text
            text_rect = text_item.boundingRect()
            text_x = self.x + (self.width - text_rect.width()) / 2
            text_y = self.y + (self.height - text_rect.height()) / 2
            text_item.setPos(text_x, text_y)
            text_item.setZValue(self.z_value + 1)
            scene.addItem(text_item)


class HMIButtonRuntime(HMIButton):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the button in runtime mode with click handling"""
        # Draw button rectangle
        rect_item = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        
        # 设置item标志以接收鼠标事件
        rect_item.setAcceptHoverEvents(True)
        rect_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        rect_item.setFlag(QGraphicsItem.ItemIsFocusable, True)
        
        # Determine color based on state and bound variable
        color = QColor(self.properties.get('off_color', '#CCCCCC'))
        if self.variables and data_manager:
            bound_var = self.variables[0]
            value = data_manager.get_tag_value(bound_var.variable_name)
            if value is not None:
                # Handle bit offset if specified
                bit_offset = getattr(bound_var, 'bit_offset', None)
                if bit_offset is not None and isinstance(value, (int, float)):
                    value = (int(value) >> int(bit_offset)) & 1
                if value:
                    color = QColor(self.properties.get('on_color', '#4CAF50'))
        
        rect_item.setBrush(QBrush(color))
        pen = QPen(Qt.black)
        pen.setWidth(1)
        rect_item.setPen(pen)
        
        # Store references for the click handler
        rect_item.hmi_object = self
        rect_item.hmi_scene = scene  # Store scene reference with different name to avoid conflict
        
        import time  # Import time for tracking last operation time
        
        # Add click event handler
        def mouse_press_handler(event):
            # Get the button object
            button_obj = rect_item.hmi_object
            if not button_obj:
                return
            
            action_type = button_obj.properties.get('action_type', 'custom')
            operation = button_obj.properties.get('variable_operation', '置位')
            
            # Prevent multiple rapid clicks for momentary operations
            current_time = time.time()
            if hasattr(rect_item, 'last_momentary_time'):
                # Minimum interval of 100ms between momentary operations to prevent flooding
                if current_time - rect_item.last_momentary_time < 0.1 and operation == '点动':
                    print(f"Button: Too fast click, ignoring press")
                    return
            
            # Handle variable operations - use target_variable from properties
            if action_type == '变量操作' and data_manager:
                var_name = button_obj.properties.get('target_variable', '')
                if not var_name:
                    print(f"Button: No target variable set")
                    return
                
                # Get bit_offset from variable binding
                bit_offset = None
                if button_obj.variables:
                    bound_var = button_obj.variables[0]
                    bit_offset = getattr(bound_var, 'bit_offset', None)
                
                try:
                    current_value = data_manager.get_tag_value(var_name)
                    
                    if operation == '置位':
                        new_value = True
                        data_manager.update_tag(var_name, new_value)
                        print(f"Button: Set {var_name} to True")
                    elif operation == '复位':
                        new_value = False
                        data_manager.update_tag(var_name, new_value)
                        print(f"Button: Reset {var_name} to False")
                    elif operation == '取反':
                        # For bit offset, toggle only the specific bit
                        if bit_offset is not None:
                            # Read current raw value from data manager
                            current_raw_value = data_manager.get_tag_value(var_name)
                            print(f"Button: Read {var_name} = {current_raw_value}, bit_offset={bit_offset}")
                            
                            # If current value is boolean or we don't have a value, read from PLC
                            if current_raw_value is None or isinstance(current_raw_value, bool):
                                # Read latest value from PLC
                                plc_value = data_manager.read_tag_value(var_name)
                                if plc_value is not None:
                                    current_raw_value = plc_value
                                    print(f"Button: Read from PLC: {var_name} = {current_raw_value}")
                            
                            if current_raw_value is not None:
                                current_int = int(current_raw_value)
                                current_bit = (current_int >> int(bit_offset)) & 1
                                new_bit = 1 - current_bit
                                new_value = bool(new_bit)
                                print(f"Button: Toggle bit {bit_offset} of {var_name} from {current_bit} to {new_bit} (register: {current_int} -> will update)")
                            else:
                                new_value = True
                                print(f"Button: No value available, toggling to {new_value}")
                        else:
                            new_value = not bool(current_value) if current_value is not None else True
                        data_manager.update_tag(var_name, new_value)
                        print(f"Button: Toggle {var_name} to {new_value}")
                    elif operation == '置1':
                        new_value = 1
                        data_manager.update_tag(var_name, new_value)
                        print(f"Button: Set {var_name} to 1")
                    elif operation == '置0':
                        new_value = 0
                        data_manager.update_tag(var_name, new_value)
                        print(f"Button: Reset {var_name} to 0")
                    elif operation == '加1':
                        new_value = (current_value + 1) if current_value is not None else 1
                        data_manager.update_tag(var_name, new_value)
                        print(f"Button: Increment {var_name} to {new_value}")
                    elif operation == '减1':
                        new_value = (current_value - 1) if current_value is not None else -1
                        data_manager.update_tag(var_name, new_value)
                        print(f"Button: Decrement {var_name} to {new_value}")
                    elif operation == '点动':
                        # 点动操作：按下时置位，松开时复位
                        print(f"Button: Momentary press - setting {var_name} to True")
                        
                        # 更新本地数据管理器
                        data_manager.update_tag(var_name, True)
                        
                        # 写入PLC
                        if hasattr(rect_item, 'hmi_scene') and hasattr(rect_item.hmi_scene, 'plc_manager'):
                            plc_manager = rect_item.hmi_scene.plc_manager
                            if plc_manager:
                                try:
                                    plc_manager.write_tag(var_name, True)
                                    print(f"Button: Wrote {var_name} = True to PLC")
                                except Exception as e:
                                    print(f"Button: Error writing to PLC: {e}")
                        
                        # 标记为点动操作，松开时需要复位
                        rect_item._momentary_var_name = var_name
                        rect_item._momentary_active = True
                        rect_item._momentary_data_manager = data_manager
                        
                        new_value = None  # 设置为None以避免后续重复写入
                    else:
                        new_value = None
                    
                    # Write to PLC if plc_manager is available (skip for momentary operation as it's handled by pulse generator)
                    if operation != '点动' and new_value is not None and hasattr(rect_item, 'hmi_scene') and hasattr(rect_item.hmi_scene, 'plc_manager'):
                        plc_manager = rect_item.hmi_scene.plc_manager
                        if plc_manager:
                            try:
                                # Write to PLC with bit_offset if specified
                                if bit_offset is not None:
                                    plc_manager.write_tag(var_name, new_value, bit_offset)
                                    print(f"Button: Wrote bit {bit_offset} = {new_value} to {var_name}")
                                else:
                                    plc_manager.write_tag(var_name, new_value)
                                    print(f"Button: Wrote {var_name} = {new_value} to PLC")
                            except Exception as e:
                                print(f"Button: Error writing to PLC: {e}")
                except Exception as e:
                    print(f"Button: Error updating variable {var_name}: {e}")
                    
            # Handle screen navigation
            elif action_type == '画面跳转':
                item_scene = rect_item.scene()
                if item_scene:
                    views = item_scene.views()
                    if views:
                        view = views[0]
                        widget = view
                        while widget:
                            if hasattr(widget, 'load_screen_by_name') and hasattr(widget, 'load_screen_by_number'):
                                target_screen = button_obj.properties.get('target_screen', '')
                                target_screen_number = button_obj.properties.get('target_screen_number', 0)
                                
                                if target_screen:
                                    widget.load_screen_by_name(target_screen)
                                elif target_screen_number > 0:
                                    widget.load_screen_by_number(target_screen_number)
                                break
                            widget = widget.parent() if hasattr(widget, 'parent') else None
        
        rect_item.mousePressEvent = mouse_press_handler
        
        # Add mouse release handler for momentary operation
        def mouse_release_handler(event):
            # Check if this is a momentary operation that needs reset
            if hasattr(rect_item, '_momentary_active') and rect_item._momentary_active:
                var_name = rect_item._momentary_var_name
                dm = getattr(rect_item, '_momentary_data_manager', data_manager)
                
                # Get bit_offset
                bit_offset = None
                if button_obj.variables:
                    bound_var = button_obj.variables[0]
                    bit_offset = getattr(bound_var, 'bit_offset', None)
                
                print(f"Button: Momentary release - resetting {var_name} to False, bit_offset={bit_offset}")
                
                # 更新本地数据管理器
                if dm:
                    dm.update_tag(var_name, False)
                
                # 写入 PLC
                if hasattr(rect_item, 'hmi_scene') and hasattr(rect_item.hmi_scene, 'plc_manager'):
                    plc_manager = rect_item.hmi_scene.plc_manager
                    if plc_manager:
                        try:
                            if bit_offset is not None:
                                plc_manager.write_tag(var_name, False, bit_offset)
                                print(f"Button: Wrote bit {bit_offset} = False to {var_name}")
                            else:
                                plc_manager.write_tag(var_name, False)
                                print(f"Button: Wrote {var_name} = False to PLC")
                        except Exception as e:
                            print(f"Button: Error writing to PLC: {e}")
                
                # 清除标记
                rect_item._momentary_active = False
            # 调用父类的事件处理
            QGraphicsRectItem.mouseReleaseEvent(rect_item, event)
        
        rect_item.mouseReleaseEvent = mouse_release_handler
        
        # 添加场景级别的鼠标松开事件处理（作为备份）
        def scene_mouse_release_handler(event):
            # 检查是否有活动的点动操作
            if hasattr(rect_item, '_momentary_active') and rect_item._momentary_active:
                var_name = rect_item._momentary_var_name
                dm = getattr(rect_item, '_momentary_data_manager', data_manager)
                
                # Get bit_offset
                bit_offset = None
                if button_obj.variables:
                    bound_var = button_obj.variables[0]
                    bit_offset = getattr(bound_var, 'bit_offset', None)
                
                print(f"Button: Scene mouse release - resetting {var_name} to False, bit_offset={bit_offset}")
                
                # 更新本地数据管理器
                if dm:
                    dm.update_tag(var_name, False)
                
                # 写入 PLC
                if hasattr(rect_item, 'hmi_scene') and hasattr(rect_item.hmi_scene, 'plc_manager'):
                    plc_manager = rect_item.hmi_scene.plc_manager
                    if plc_manager:
                        try:
                            if bit_offset is not None:
                                plc_manager.write_tag(var_name, False, bit_offset)
                                print(f"Button: Wrote bit {bit_offset} = False to {var_name}")
                            else:
                                plc_manager.write_tag(var_name, False)
                                print(f"Button: Wrote {var_name} = False to PLC")
                        except Exception as e:
                            print(f"Button: Error writing to PLC: {e}")
                        except Exception as e:
                            print(f"Button: Error writing to PLC: {e}")
                
                # 清除标记
                rect_item._momentary_active = False
        
        # 存储场景事件处理器引用
        rect_item._scene_mouse_release_handler = scene_mouse_release_handler
        
        # 如果场景已经有事件处理器列表，添加到列表中
        if not hasattr(scene, '_momentary_release_handlers'):
            scene._momentary_release_handlers = []
        scene._momentary_release_handlers.append(scene_mouse_release_handler)
        
        scene.addItem(rect_item)
        
        text_item = QGraphicsTextItem(self.properties.get('text', 'Button'))
        font = QFont()
        font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(self.properties.get('font_size', 10))
        font.setBold(self.properties.get('font_bold', False))
        font.setItalic(self.properties.get('font_italic', False))
        font.setUnderline(self.properties.get('font_underline', False))
        text_item.setFont(font)
        text_item.setDefaultTextColor(QColor(self.properties.get('text_color', '#000000')))
        
        text_rect = text_item.boundingRect()
        text_x = self.x + (self.width - text_rect.width()) / 2
        text_y = self.y + (self.height - text_rect.height()) / 2
        text_item.setPos(text_x, text_y)
        
        scene.addItem(text_item)


class HMILabelRuntime(HMILabel):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the label in runtime mode with dynamic data"""
        # If there's a bound variable, update text with its value
        display_text = self.properties.get('text', 'Label')
        
        if self.variables and data_manager:
            # Get the first bound variable's value
            bound_var = self.variables[0]
            value = data_manager.get_tag_value(bound_var.variable_name)
            if value is not None:
                # Apply format if specified
                fmt = self.properties.get('display_format', '{}')
                unit = self.properties.get('unit', '')
                precision = self.properties.get('precision', 2)
                
                try:
                    if isinstance(value, (int, float)):
                        if isinstance(value, float):
                            display_text = f"{fmt.format(round(value, precision))}{unit}"
                        else:
                            display_text = f"{fmt.format(value)}{unit}"
                    else:
                        display_text = f"{fmt.format(value)}{unit}"
                except (ValueError, TypeError, KeyError):
                    # If format fails, just show the value with unit
                    if isinstance(value, float):
                        display_text = f"{round(value, precision)}{unit}"
                    else:
                        display_text = f"{value}{unit}"
        
        # Create container for the label
        rect_item = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        
        # Check for background color first
        bg_color = self.properties.get('background_color', '')
        if bg_color:
            rect_item.setBrush(QBrush(QColor(bg_color)))
            if self.properties.get('border', False):
                pen = QPen(Qt.black)
                pen.setWidth(1)
                rect_item.setPen(pen)
            else:
                rect_item.setPen(QPen(Qt.NoPen))
        elif self.properties.get('border', False):
            color = QColor(self.properties.get('color', '#FFFFFF'))
            rect_item.setBrush(QBrush(color))
            pen = QPen(Qt.black)
            pen.setWidth(1)
            rect_item.setPen(pen)
        else:
            pen = QPen(Qt.NoPen)
            rect_item.setPen(pen)
            rect_item.setBrush(QBrush(Qt.NoBrush))
        
        scene.addItem(rect_item)
        
        text_item = QGraphicsTextItem(display_text)
        font = QFont()
        font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(self.properties.get('font_size', 10))
        font.setBold(self.properties.get('font_bold', False))
        font.setItalic(self.properties.get('font_italic', False))
        font.setUnderline(self.properties.get('font_underline', False))
        text_item.setFont(font)
        text_item.setDefaultTextColor(QColor(self.properties.get('text_color', '#000000')))
        
        text_rect = text_item.boundingRect()
        text_x = self.x + (self.width - text_rect.width()) / 2
        text_y = self.y + (self.height - text_rect.height()) / 2
        text_item.setPos(text_x, text_y)
        
        scene.addItem(text_item)
        
    def update_from_data_manager(self, data_manager):
        """Update the label based on data from the data manager"""
        # Redraw to update with new data
        self.scene = data_manager.parent() if hasattr(data_manager, 'parent') else None
        # For runtime, we rely on periodic refresh rather than direct updates


class HMISwitchRuntime(HMISwitch):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the switch in runtime mode with data updates"""
        # Update state based on bound variable if available
        if self.variables and data_manager:
            bound_var = self.variables[0]
            value = data_manager.get_tag_value(bound_var.variable_name)
            if value is not None:
                # Handle bit offset if specified
                bit_offset = getattr(bound_var, 'bit_offset', None)
                if bit_offset is not None and isinstance(value, (int, float)):
                    value = (int(value) >> int(bit_offset)) & 1
                
                if isinstance(value, bool):
                    self.properties['state'] = value
                elif isinstance(value, (int, float)):
                    self.properties['state'] = bool(value)
        
        # Draw outer rectangle
        rect_item = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        
        # Determine color based on state
        color = QColor(self.properties.get('on_color', '#4CAF50') if self.properties['state'] 
                      else self.properties.get('off_color', '#CCCCCC'))
        rect_item.setBrush(QBrush(color))
        pen = QPen(Qt.black)
        pen.setWidth(1)
        rect_item.setPen(pen)
        scene.addItem(rect_item)
        
        text = self.properties.get('on_text', '开') if self.properties['state'] else self.properties.get('off_text', '关')
        text_item = QGraphicsTextItem(text)
        font = QFont()
        font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(self.properties.get('font_size', 10))
        font.setBold(self.properties.get('font_bold', False))
        font.setItalic(self.properties.get('font_italic', False))
        font.setUnderline(self.properties.get('font_underline', False))
        text_item.setFont(font)
        text_item.setDefaultTextColor(QColor(self.properties.get('text_color', '#FFFFFF')))
        
        text_rect = text_item.boundingRect()
        text_x = self.x + (self.width - text_rect.width()) / 2
        text_y = self.y + (self.height - text_rect.height()) / 2
        text_item.setPos(text_x, text_y)
        
        scene.addItem(text_item)
        
        # Add click handler to toggle switch
        if self.variables and data_manager:
            rect_item.hmi_object = self
            rect_item.data_manager = data_manager
            rect_item.hmi_scene = scene
            
            def mouse_press_handler(event):
                switch_obj = rect_item.hmi_object
                dm = rect_item.data_manager
                if switch_obj and dm and switch_obj.variables:
                    bound_var = switch_obj.variables[0]
                    var_name = bound_var.variable_name
                    bit_offset = getattr(bound_var, 'bit_offset', None)
                    
                    try:
                        # Read current raw value from data manager
                        current_raw_value = dm.get_tag_value(var_name)
                        print(f"Switch: Read {var_name} = {current_raw_value}, bit_offset={bit_offset}")
                        
                        # Extract bit value if bit_offset is specified
                        if bit_offset is not None:
                            # For bit operations, we need the integer register value
                            # If current value is boolean or we don't have a value, read from PLC
                            if current_raw_value is None or isinstance(current_raw_value, bool):
                                # Read latest value from PLC
                                plc_value = dm.read_tag_value(var_name)
                                if plc_value is not None:
                                    current_raw_value = plc_value
                                    print(f"Switch: Read from PLC: {var_name} = {current_raw_value}")
                            
                            if current_raw_value is not None:
                                current_bit = (int(current_raw_value) >> int(bit_offset)) & 1
                                current_value = bool(current_bit)
                                print(f"Switch: Extracted bit {bit_offset} = {current_bit} from {current_raw_value}")
                            else:
                                current_value = False
                                print(f"Switch: No value available, using False")
                        else:
                            current_value = bool(current_raw_value) if current_raw_value is not None else False
                            print(f"Switch: Using value = {current_value}")
                        
                        # Toggle the state
                        new_value = not current_value
                        
                        # Update data manager
                        dm.update_tag(var_name, new_value)
                        print(f"Switch: Toggled {var_name} bit {bit_offset} from {current_value} to {new_value}")
                        
                        # Write to PLC with bit_offset if specified
                        if hasattr(rect_item, 'hmi_scene') and hasattr(rect_item.hmi_scene, 'plc_manager'):
                            plc_manager = rect_item.hmi_scene.plc_manager
                            if plc_manager:
                                try:
                                    if bit_offset is not None:
                                        # For bit offset, we need to read-modify-write
                                        plc_manager.write_tag(var_name, new_value, bit_offset)
                                        print(f"Switch: Wrote bit {bit_offset} = {new_value} to {var_name}")
                                    else:
                                        plc_manager.write_tag(var_name, new_value)
                                        print(f"Switch: Wrote {var_name} = {new_value} to PLC")
                                except Exception as e:
                                    print(f"Switch: Error writing to PLC: {e}")
                    except Exception as e:
                        print(f"Switch: Error toggling variable {var_name}: {e}")
            
            rect_item.mousePressEvent = mouse_press_handler
        
    def update_from_data_manager(self, data_manager):
        """Update the switch based on data from the data manager"""
        # This will be called periodically to update the display
        pass


class HMILightRuntime(HMILight):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the light in runtime mode with data updates"""
        # Update state based on bound variable if available
        if self.variables and data_manager:
            bound_var = self.variables[0]
            value = data_manager.get_tag_value(bound_var.variable_name)
            if value is not None:
                # Handle bit offset if specified
                bit_offset = getattr(bound_var, 'bit_offset', None)
                if bit_offset is not None and isinstance(value, (int, float)):
                    # Extract bit value
                    value = (int(value) >> int(bit_offset)) & 1
                
                if isinstance(value, bool):
                    self.properties['state'] = value
                elif isinstance(value, (int, float)):
                    self.properties['state'] = bool(value)
        
        state = self.properties.get('state', False)
        use_image = self.properties.get('use_image', False)
        
        if use_image:
            self._draw_runtime_with_image(scene, state)
        else:
            self._draw_runtime_with_color(scene, state)
    
    def _draw_runtime_with_color(self, scene, state):
        """Draw light with color fill in runtime"""
        shape = self.properties.get('shape', 'circle')
        border = self.properties.get('border', True)
        border_color = self.properties.get('border_color', '#000000')
        border_width = self.properties.get('border_width', 1)
        
        # Determine color based on state
        if state:
            color = QColor(self.properties.get('on_color', '#00FF00'))
        else:
            color = QColor(self.properties.get('off_color', '#808080'))
        
        pen = QPen(QColor(border_color))
        pen.setWidth(border_width)
        brush = QBrush(color)
        
        if shape == 'circle':
            item = QGraphicsEllipseItem(self.x, self.y, self.width, self.height)
        elif shape == 'square':
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
        item.setZValue(1)
        scene.addItem(item)
    
    def _draw_runtime_with_image(self, scene, state):
        """Draw light with image in runtime"""
        # Load images if not loaded
        if self.on_pixmap is None or self.off_pixmap is None:
            self.load_images()
        
        pixmap = self.on_pixmap if state else self.off_pixmap
        
        if pixmap and not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(self.width, self.height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x_offset = (self.width - scaled_pixmap.width()) / 2
            y_offset = (self.height - scaled_pixmap.height()) / 2
            pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
            pixmap_item.setPos(self.x + x_offset, self.y + y_offset)
            pixmap_item.setZValue(1)
            scene.addItem(pixmap_item)
        else:
            # Fallback to color if image not available
            self._draw_runtime_with_color(scene, state)
        
    def update_from_data_manager(self, data_manager):
        """Update the light based on data from the data manager"""
        # This will be called periodically to update the display
        pass


class HMIGaugeRuntime(HMIGauge):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the gauge in runtime mode with data updates"""
        import math
        
        # Update value based on bound variable if available
        if self.variables and data_manager:
            bound_var = self.variables[0]
            value = data_manager.get_tag_value(bound_var.variable_name)
            if value is not None:
                try:
                    self.properties['value'] = float(value)
                except (ValueError, TypeError):
                    pass
        
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
            scale_text = QGraphicsTextItem(str(int(scale_value)))
            font = QFont()
            font.setPointSize(8)
            scale_text.setFont(font)
            scale_text.setDefaultTextColor(QColor('#000000'))
            
            # Position text outside the tick marks with proper arc alignment
            text_radius = radius + 20
            text_x = center_x + text_radius * math.cos(rad)
            text_y = center_y - text_radius * math.sin(rad)
            
            # Get text dimensions
            text_rect = scale_text.boundingRect()
            text_w = text_rect.width()
            text_h = text_rect.height()
            
            # Center the text on its position
            scale_text.setPos(text_x - text_w / 2, text_y - text_h / 2)
            scene.addItem(scale_text)
        
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
        
    def update_from_data_manager(self, data_manager):
        """Update the gauge based on data from the data manager"""
        # This will be called periodically to update the display
        pass


class HMIPictureBoxRuntime(HMIPictureBox):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the picture box in runtime mode"""
        image_path = self.properties.get('image_path', '')
        
        if not self.pixmap and image_path:
            self.load_image(image_path)
        
        if self.pixmap and not self.pixmap.isNull():
            if self.properties.get('keep_aspect_ratio', True):
                scaled_pixmap = self.pixmap.scaled(self.width, self.height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x_offset = (self.width - scaled_pixmap.width()) / 2
                y_offset = (self.height - scaled_pixmap.height()) / 2
            else:
                scaled_pixmap = self.pixmap.scaled(self.width, self.height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                x_offset = 0
                y_offset = 0
            
            pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
            pixmap_item.setPos(self.x + x_offset, self.y + y_offset)
            scene.addItem(pixmap_item)
        else:
            rect_item = QGraphicsRectItem(self.x, self.y, self.width, self.height)
            rect_item.setBrush(QBrush(QColor("#E0E0E0")))
            pen = QPen(Qt.black)
            pen.setWidth(1)
            rect_item.setPen(pen)
            scene.addItem(rect_item)
            
            text_item = QGraphicsTextItem("[图片]")
            text_item.setDefaultTextColor(Qt.gray)
            font = QFont()
            font.setPointSize(10)
            text_item.setFont(font)
            text_rect = text_item.boundingRect()
            text_x = self.x + (self.width - text_rect.width()) / 2
            text_y = self.y + (self.height - text_rect.height()) / 2
            text_item.setPos(text_x, text_y)
            scene.addItem(text_item)


class HMIPictureListRuntime(HMIPictureList):
    """图形列表运行时控件 - 根据变量值显示不同的图片"""
    
    def __init__(self, x=0, y=0, width=100, height=100):
        super().__init__(x, y, width, height)
        self.current_value = None
    
    def load_image(self, image_path):
        """加载图片（使用全局缓存）"""
        from ..core.data_manager import get_image_cache
        cache = get_image_cache()
        
        if not image_path:
            return None
        
        cached = cache.get(image_path)
        if cached:
            return cached
        
        if os.path.exists(image_path):
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
    
    def update_value(self, value):
        """更新当前值"""
        self.current_value = value
    
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """在运行时绘制图形列表"""
        bg_color = QColor(self.properties.get('bg_color', '#EEEEEE'))
        border_visible = self.properties.get('border_visible', True)
        border_color = QColor(self.properties.get('border_color', '#000000'))
        border_width = self.properties.get('border_width', 1)
        keep_aspect_ratio = self.properties.get('keep_aspect_ratio', True)
        
        if self.variables and self.variables[0].variable_name:
            var_name = self.variables[0].variable_name
            if data_manager and hasattr(data_manager, 'tags'):
                tag = data_manager.tags.get(var_name)
                if tag:
                    self.current_value = tag.value
        
        image_path = ''
        if self.current_value is not None:
            image_path = self.get_image_for_value(self.current_value)
        
        if not image_path:
            image_path = self.properties.get('default_image', '')
        
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
            pen = QPen(border_color, border_width) if border_visible else Qt.NoPen
            bg_rect.setPen(pen)
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


class HMITrendChartRuntime(HMITrendChart):
    def __init__(self, x=0, y=0, width=300, height=200):
        super().__init__(x, y, width, height)
        self.time_span = 3600
        self.trend_manager = TrendDataManager()
        self._last_data_hash = None
        self._cached_pixmap = None
        self._last_update_time = 0
        self._update_interval = 1.0

    def subscribe_variables(self):
        """Subscribe all bound variables to trend manager"""
        for var_binding in self.variables:
            if var_binding.variable_name:
                self.trend_manager.subscribe_var(var_binding.variable_name)

    def zoom_in(self):
        """Zoom in - decrease time span"""
        if self.time_span > 60:
            self.time_span = max(60, int(self.time_span * 0.5))
            self.properties['time_span'] = self.time_span
            self._cached_pixmap = None

    def zoom_out(self):
        """Zoom out - increase time span"""
        if self.time_span < 86400:
            self.time_span = min(86400, int(self.time_span * 2))
            self.properties['time_span'] = self.time_span
            self._cached_pixmap = None
    
    def _compute_data_hash(self, chart_data):
        """计算数据哈希，用于检测变化"""
        import hashlib
        hash_str = ""
        for var_name in sorted(chart_data.keys()):
            data = chart_data[var_name]
            if data:
                hash_str += f"{var_name}:{len(data)}:{data[-1][0] if data else 0}:"
        return hashlib.md5(hash_str.encode()).hexdigest()

    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw trend chart in runtime mode using matplotlib with real time axis"""
        import time
        current_time = time.time()
        
        if self._cached_pixmap and (current_time - self._last_update_time) < self._update_interval:
            from PyQt5.QtWidgets import QGraphicsPixmapItem
            pixmap_item = QGraphicsPixmapItem(self._cached_pixmap)
            pixmap_item.setPos(self.x, self.y)
            pixmap_item._hmi_object_id = id(self)
            scene.addItem(pixmap_item)
            return
        
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            from datetime import datetime, timedelta
            
            self.time_span = self.properties.get('time_span', 3600)
            
            chart_data = self.trend_manager.get_all_data_for_timespan(self.time_span)
            
            new_hash = self._compute_data_hash(chart_data)
            if self._cached_pixmap and new_hash == self._last_data_hash:
                from PyQt5.QtWidgets import QGraphicsPixmapItem
                pixmap_item = QGraphicsPixmapItem(self._cached_pixmap)
                pixmap_item.setPos(self.x, self.y)
                pixmap_item._hmi_object_id = id(self)
                scene.addItem(pixmap_item)
                return
            
            self._last_data_hash = new_hash
            
            bg_color = self.properties.get('bg_color', '#FFFFFF')
            border_color = self.properties.get('border_color', '#000000')
            border_width = self.properties.get('border_width', 1)
            title = self.properties.get('title', '趋势图')
            title_visible = self.properties.get('title_visible', True)
            title_color = self.properties.get('title_color', '#000000')
            title_font_size = self.properties.get('title_font_size', 12)
            grid_visible = self.properties.get('grid_visible', True)
            grid_color = self.properties.get('grid_color', '#E0E0E0')
            line_width = self.properties.get('line_width', 2)
            show_legend = self.properties.get('show_legend', True)
            y_min = self.properties.get('y_min', 0)
            y_max = self.properties.get('y_max', 100)
            y_auto_scale = self.properties.get('y_auto_scale', True)
            
            colors = ['#FF0000', '#00AA00', '#0000FF', '#FF00FF', '#AAAA00', '#00AAAA', '#FF8000', '#8000FF']
            
            dpi = 100
            fig_width = self.width / dpi
            fig_height = self.height / dpi
            
            fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
            fig.patch.set_facecolor(bg_color)
            ax.set_facecolor(bg_color)
            
            if title_visible and title:
                ax.set_title(title, fontsize=title_font_size, color=title_color, fontname='Microsoft YaHei')
            
            now = datetime.now()
            start_time = now - timedelta(seconds=self.time_span)
            ax.set_xlim(start_time, now)
            
            if y_auto_scale:
                all_values = []
                for var_binding in self.variables:
                    if var_binding.variable_name:
                        data_points = chart_data.get(var_binding.variable_name, [])
                        all_values.extend([p[1] for p in data_points])
                if all_values:
                    y_min = min(all_values) * 0.9
                    y_max = max(all_values) * 1.1
                    if y_min == y_max:
                        y_min -= 1
                        y_max += 1
            
            ax.set_ylim(y_min, y_max)
            
            if grid_visible:
                ax.grid(True, linestyle='--', color=grid_color, linewidth=0.5)
            
            ax.set_xlabel('时间', fontsize=self.properties.get('axis_font_size', 9))
            ax.set_ylabel('值', fontsize=self.properties.get('axis_font_size', 9))
            ax.tick_params(axis='both', labelsize=8)
            
            for spine in ax.spines.values():
                spine.set_edgecolor(border_color)
                spine.set_linewidth(border_width)
            
            import matplotlib.dates as mdates
            if self.time_span <= 60:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            elif self.time_span <= 3600:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            else:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
            
            fig.autofmt_xdate()
            
            legend_labels = []
            for idx, var_binding in enumerate(self.variables[:8]):
                if not var_binding.variable_name:
                    continue
                
                data_points = chart_data.get(var_binding.variable_name, [])
                if len(data_points) < 1:
                    continue
                
                x_data = [datetime.fromtimestamp(p[0] / 1000) for p in data_points]
                y_data = [p[1] for p in data_points]
                
                color = colors[idx % len(colors)]
                ax.plot(x_data, y_data, color=color, linewidth=line_width, marker=None)
                legend_labels.append(var_binding.variable_name)
            
            if show_legend and legend_labels:
                ax.legend(legend_labels, loc='upper right', fontsize=8, framealpha=0.8)
            
            time_span_str = self._format_time_span(self.time_span)
            ax.text(0.02, 0.98, f'时间跨度: {time_span_str}', transform=ax.transAxes,
                   fontsize=8, verticalalignment='top', 
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
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
            
            self._cached_pixmap = pixmap
            self._last_update_time = current_time
            
            plt.close(fig)
            
            from PyQt5.QtWidgets import QGraphicsPixmapItem
            pixmap_item = QGraphicsPixmapItem(pixmap)
            pixmap_item.setPos(self.x, self.y)
            pixmap_item.setZValue(self.z_value)
            pixmap_item.hmi_object = self
            scene.addItem(pixmap_item)
            
        except ImportError:
            self._draw_fallback(scene)
        except Exception as e:
            print(f"TrendChartRuntime draw error: {e}")
            self._draw_fallback(scene)
    
    def _format_time_span(self, seconds):
        """Format time span as human readable string"""
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            return f"{seconds // 60}分钟"
        elif seconds < 86400:
            return f"{seconds // 3600}小时"
        else:
            return f"{seconds // 86400}天"
    
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
        scene.addItem(rect)
        
        if title_visible and title:
            title_item = QGraphicsTextItem(title)
            title_item.setFont(QFont('Microsoft YaHei', self.properties.get('title_font_size', 12)))
            title_item.setDefaultTextColor(QColor(self.properties.get('title_color', '#000000')))
            title_item.setPos(self.x + 10, self.y + 5)
            scene.addItem(title_item)
        
        placeholder = QGraphicsTextItem("[matplotlib未安装]")
        placeholder.setFont(QFont('Microsoft YaHei', 10))
        placeholder.setDefaultTextColor(QColor('#999999'))
        ph_rect = placeholder.boundingRect()
        placeholder.setPos(self.x + (self.width - ph_rect.width()) / 2,
                          self.y + (self.height - ph_rect.height()) / 2)
        scene.addItem(placeholder)


class HMIHistoryTrendRuntime(HMIHistoryTrend):
    def __init__(self, x=0, y=0, width=400, height=300):
        super().__init__(x, y, width, height)
        self.selected_tags = []
        self.start_time = None
        self.end_time = None
        self.chart_data = {}
        self._parent_widget = None
        self._data_manager = None
        self._scene = None
        self._widgets = []
        
        # Zoom and pan state
        self._zoom_level = 1.0
        self._pan_offset_x = 0
        self._pan_offset_y = 0
        self._original_time_range = None
        
        # Cursor/ruler state
        self._show_cursor = False
        self._cursor_x = None
        self._cursor_value = None
        self._cursor_dragging = False


class CursorDragRect(QGraphicsRectItem):
    """Custom rect item for cursor positioning - click to move cursor"""
    def __init__(self, parent_trend):
        super().__init__()
        self.parent_trend = parent_trend
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
    
    def mousePressEvent(self, event):
        """Handle mouse click to move cursor"""
        if event.button() == Qt.LeftButton and self.parent_trend._show_cursor:
            self.parent_trend._update_cursor_position(event.pos())
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move while pressed"""
        if self.parent_trend._show_cursor:
            self.parent_trend._update_cursor_position(event.pos())
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        event.accept()
    
    def hoverMoveEvent(self, event):
        """Handle hover - do nothing, cursor only moves on click"""
        pass


class HMIHistoryTrendRuntime(HMIHistoryTrend):
    def __init__(self, x=0, y=0, width=400, height=300):
        super().__init__(x, y, width, height)
        self.selected_tags = []
        self.start_time = None
        self.end_time = None
        self.chart_data = {}
        self._parent_widget = None
        self._data_manager = None
        self._scene = None
        self._widgets = []
        
        # Zoom and pan state
        self._zoom_level = 1.0
        self._pan_offset_x = 0
        self._pan_offset_y = 0
        self._original_time_range = None
        
        # Cursor/ruler state
        self._show_cursor = False
        self._cursor_x = None
        self._cursor_value = None
        self._cursor_dragging = False
        self._cursor_time = None
    
    def _get_logged_tags(self):
        """Get list of tags that have logging rules configured"""
        logged_tags = set()
        
        try:
            from scada_app.core.config_manager import ConfigurationManager
            
            config_manager = None
            
            if hasattr(self, '_config_manager_ref') and self._config_manager_ref:
                config_manager = self._config_manager_ref
            
            if not config_manager:
                from scada_app.hmi.main_window import MainWindow
                main_windows = [w for w in QApplication.topLevelWidgets() if isinstance(w, MainWindow)]
                if main_windows:
                    config_manager = main_windows[0].config_manager
            
            if config_manager:
                rules_data = []
                if hasattr(config_manager, 'logging_rules'):
                    rules_data = config_manager.logging_rules
                elif hasattr(config_manager, 'get_logging_rules'):
                    rules_data = config_manager.get_logging_rules()
                
                for rule in rules_data:
                    tag_name = rule.get('tag_name', '') if isinstance(rule, dict) else getattr(rule, 'tag_name', '')
                    if tag_name:
                        logged_tags.add(tag_name)
        except Exception as e:
            print(f"HistoryTrend: Error getting logged tags: {e}")
        
        return list(logged_tags)
    
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw history trend chart in runtime mode with embedded controls"""
        self._parent_widget = parent_widget
        self._data_manager = data_manager
        self._scene = scene
        
        # Clear widgets list for new scene
        self._widgets = []
        
        bg_color = self.properties.get('bg_color', '#FFFFFF')
        border_color = self.properties.get('border_color', '#000000')
        border_width = self.properties.get('border_width', 1)
        title = self.properties.get('title', '历史趋势图')
        title_visible = self.properties.get('title_visible', True)
        
        # Control panel height (1 row)
        control_height = 35
        
        # Draw main background
        rect = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        rect.setBrush(QBrush(QColor(bg_color)))
        if border_width > 0:
            pen = QPen(QColor(border_color))
            pen.setWidth(border_width)
            rect.setPen(pen)
        else:
            rect.setPen(QPen(Qt.NoPen))
        rect.setZValue(self.z_value)
        rect.hmi_object = self
        scene.addItem(rect)
        
        # Draw control panel background
        control_rect = QGraphicsRectItem(self.x, self.y, self.width, control_height)
        control_rect.setBrush(QBrush(QColor('#F5F5F5')))
        control_rect.setPen(QPen(QColor('#E0E0E0')))
        control_rect.setZValue(self.z_value + 10)
        scene.addItem(control_rect)
        
        # Create embedded controls
        self._create_controls(scene, control_height)
        
        # Create interactive area for cursor dragging
        chart_area_x = self.x + 55
        chart_area_y = self.y + control_height + 10
        chart_area_width = self.width - 55 - 80
        chart_area_height = self.height - control_height - 10 - 35
        
        if chart_area_width > 0 and chart_area_height > 0:
            # Create transparent interactive rect for cursor dragging
            self._cursor_area = CursorDragRect(self)
            self._cursor_area.setRect(chart_area_x, chart_area_y, chart_area_width, chart_area_height)
            self._cursor_area.setZValue(self.z_value + 10)
            
            # Store chart area bounds
            self._chart_area_bounds = (chart_area_x, chart_area_y, chart_area_width, chart_area_height)
            
            scene.addItem(self._cursor_area)
        
        # Draw chart area - only if we have data and not in refresh cycle
        # HistoryTrend shows historical data, doesn't need frequent refresh
        if self.chart_data and not getattr(self, '_skip_chart_draw', False):
            self._draw_chart(scene, control_height)
        elif title_visible and title and not self.chart_data:
            # Show placeholder in chart area
            placeholder = QGraphicsTextItem("选择变量和时间后点击查询")
            placeholder.setFont(QFont('Microsoft YaHei', 10))
            placeholder.setDefaultTextColor(QColor('#999999'))
            ph_rect = placeholder.boundingRect()
            placeholder.setPos(self.x + (self.width - ph_rect.width()) / 2,
                              self.y + control_height + (self.height - control_height - ph_rect.height()) / 2)
            placeholder.setZValue(self.z_value + 1)
            scene.addItem(placeholder)
    
    def _create_controls(self, scene, control_height):
        """Create embedded control widgets"""
        from PyQt5.QtWidgets import QPushButton, QComboBox, QLabel, QGraphicsProxyWidget, QDateTimeEdit
        from PyQt5.QtCore import QDateTime
        from datetime import datetime, timedelta
        
        # Get font size from properties
        control_font_size = self.properties.get('control_font_size', 11)
        font_style = f"font-size: {control_font_size}px;"
        
        row1_y = self.y + 5
        x_pos = self.x + 5
        
        # === Row 1: Time selectors and Variable selector ===
        # Start time
        start_label = QLabel("起始:")
        start_label.setStyleSheet(f"{font_style} background: transparent;")
        start_proxy = QGraphicsProxyWidget()
        start_proxy.setWidget(start_label)
        start_proxy.setPos(x_pos, row1_y + 3)
        start_proxy.setZValue(self.z_value + 15)
        scene.addItem(start_proxy)
        self._widgets.append(start_proxy)
        x_pos += 30
        
        self._start_time_edit = QDateTimeEdit()
        self._start_time_edit.setFixedSize(130, 22)
        self._start_time_edit.setStyleSheet(font_style)
        self._start_time_edit.setCalendarPopup(True)
        self._start_time_edit.setDisplayFormat("MM-dd HH:mm")
        if self.start_time:
            self._start_time_edit.setDateTime(QDateTime.fromString(
                self.start_time.strftime('%Y-%m-%d %H:%M:%S'), 
                'yyyy-MM-dd HH:mm:ss'))
        else:
            self._start_time_edit.setDateTime(QDateTime.currentDateTime().addSecs(-3600))
        
        # Override mousePressEvent to pause refresh when clicking
        self._start_time_edit.mousePressEvent = self._make_mouse_press_event(self._start_time_edit)
        
        start_time_proxy = QGraphicsProxyWidget()
        start_time_proxy.setWidget(self._start_time_edit)
        start_time_proxy.setPos(x_pos, row1_y)
        start_time_proxy.setZValue(self.z_value + 15)
        scene.addItem(start_time_proxy)
        self._widgets.append(start_time_proxy)
        x_pos += 135
        
        # End time
        end_label = QLabel("结束:")
        end_label.setStyleSheet(f"{font_style} background: transparent;")
        end_proxy = QGraphicsProxyWidget()
        end_proxy.setWidget(end_label)
        end_proxy.setPos(x_pos, row1_y + 3)
        end_proxy.setZValue(self.z_value + 15)
        scene.addItem(end_proxy)
        self._widgets.append(end_proxy)
        x_pos += 30
        
        self._end_time_edit = QDateTimeEdit()
        self._end_time_edit.setFixedSize(130, 22)
        self._end_time_edit.setStyleSheet(font_style)
        self._end_time_edit.setCalendarPopup(True)
        self._end_time_edit.setDisplayFormat("MM-dd HH:mm")
        if self.end_time:
            self._end_time_edit.setDateTime(QDateTime.fromString(
                self.end_time.strftime('%Y-%m-%d %H:%M:%S'), 
                'yyyy-MM-dd HH:mm:ss'))
        else:
            self._end_time_edit.setDateTime(QDateTime.currentDateTime())
        
        # Override mousePressEvent to pause refresh when clicking
        self._end_time_edit.mousePressEvent = self._make_mouse_press_event(self._end_time_edit)
        
        end_time_proxy = QGraphicsProxyWidget()
        end_time_proxy.setWidget(self._end_time_edit)
        end_time_proxy.setPos(x_pos, row1_y)
        end_time_proxy.setZValue(self.z_value + 15)
        scene.addItem(end_time_proxy)
        self._widgets.append(end_time_proxy)
        x_pos += 135
        
        # Variable selector (moved to row 1)
        var_label = QLabel("变量:")
        var_label.setStyleSheet(f"{font_style} background: transparent;")
        var_proxy = QGraphicsProxyWidget()
        var_proxy.setWidget(var_label)
        var_proxy.setPos(x_pos, row1_y + 3)
        var_proxy.setZValue(self.z_value + 15)
        scene.addItem(var_proxy)
        self._widgets.append(var_proxy)
        x_pos += 30
        
        var_combo = QComboBox()
        var_combo.setFixedSize(150, 22)
        var_combo.setStyleSheet(font_style)
        
        logged_tags = self._get_logged_tags()
        var_combo.addItem("-- 选择变量 --")
        for tag in sorted(logged_tags):
            var_combo.addItem(tag)
            if tag in self.selected_tags:
                var_combo.setCurrentText(tag)
        
        var_combo.currentTextChanged.connect(self._on_var_changed)
        
        # Pause refresh when dropdown is open
        var_combo.showPopup = self._make_show_popup(var_combo)
        var_combo.hidePopup = self._make_hide_popup(var_combo)
        
        var_proxy = QGraphicsProxyWidget()
        var_proxy.setWidget(var_combo)
        var_proxy.setPos(x_pos, row1_y)
        var_proxy.setZValue(self.z_value + 15)
        scene.addItem(var_proxy)
        self._widgets.append(var_proxy)
        self._var_combo = var_combo
        x_pos += 155
        
        # Quick time buttons in row 1
        quick_times = [("1h", -3600), ("6h", -21600), ("1d", -86400), ("1w", -604800)]
        for text, secs in quick_times:
            btn = QPushButton(text)
            btn.setFixedSize(28, 22)
            btn.setStyleSheet(f"{font_style} padding: 0px;")
            btn.clicked.connect(lambda checked, s=secs: self._set_quick_time(s))
            
            proxy = QGraphicsProxyWidget()
            proxy.setWidget(btn)
            proxy.setPos(x_pos, row1_y)
            proxy.setZValue(self.z_value + 15)
            scene.addItem(proxy)
            self._widgets.append(proxy)
            x_pos += 30
        
        # Query button in row 1
        query_btn = QPushButton("查询")
        query_btn.setFixedSize(50, 22)
        query_btn.setStyleSheet(f"background-color: #4CAF50; color: white; {font_style}")
        query_btn.clicked.connect(self._do_query)
        
        query_proxy = QGraphicsProxyWidget()
        query_proxy.setWidget(query_btn)
        query_proxy.setPos(x_pos, row1_y)
        query_proxy.setZValue(self.z_value + 15)
        scene.addItem(query_proxy)
        self._widgets.append(query_proxy)
        x_pos += 55
        
        # Clear button in row 1
        clear_btn = QPushButton("清除")
        clear_btn.setFixedSize(50, 22)
        clear_btn.setStyleSheet(f"background-color: #f44336; color: white; {font_style}")
        clear_btn.clicked.connect(self._clear_chart)
        
        clear_proxy = QGraphicsProxyWidget()
        clear_proxy.setWidget(clear_btn)
        clear_proxy.setPos(x_pos, row1_y)
        clear_proxy.setZValue(self.z_value + 15)
        scene.addItem(clear_proxy)
        self._widgets.append(clear_proxy)
        
        # === Zoom, Pan, Cursor buttons at bottom right ===
        # Control panel height (1 row)
        control_height = 35
        
        # Button positions at bottom right
        btn_y = self.y + self.height - 25
        btn_start_x = self.x + self.width - 350
        
        # Zoom in button
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(25, 22)
        zoom_in_btn.setStyleSheet(f"{font_style}")
        zoom_in_btn.setToolTip("放大")
        zoom_in_btn.clicked.connect(self._zoom_in)
        zoom_in_proxy = QGraphicsProxyWidget()
        zoom_in_proxy.setWidget(zoom_in_btn)
        zoom_in_proxy.setPos(btn_start_x, btn_y)
        zoom_in_proxy.setZValue(self.z_value + 15)
        scene.addItem(zoom_in_proxy)
        self._widgets.append(zoom_in_proxy)
        btn_start_x += 28
        
        # Zoom out button
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setFixedSize(25, 22)
        zoom_out_btn.setStyleSheet(f"{font_style}")
        zoom_out_btn.setToolTip("缩小")
        zoom_out_btn.clicked.connect(self._zoom_out)
        zoom_out_proxy = QGraphicsProxyWidget()
        zoom_out_proxy.setWidget(zoom_out_btn)
        zoom_out_proxy.setPos(btn_start_x, btn_y)
        zoom_out_proxy.setZValue(self.z_value + 15)
        scene.addItem(zoom_out_proxy)
        self._widgets.append(zoom_out_proxy)
        btn_start_x += 28
        
        # Reset zoom button
        reset_btn = QPushButton("重置")
        reset_btn.setFixedSize(40, 22)
        reset_btn.setStyleSheet(f"{font_style}")
        reset_btn.setToolTip("重置缩放")
        reset_btn.clicked.connect(self._reset_zoom)
        reset_proxy = QGraphicsProxyWidget()
        reset_proxy.setWidget(reset_btn)
        reset_proxy.setPos(btn_start_x, btn_y)
        reset_proxy.setZValue(self.z_value + 15)
        scene.addItem(reset_proxy)
        self._widgets.append(reset_proxy)
        btn_start_x += 45
        
        # Pan left button
        pan_left_btn = QPushButton("◀")
        pan_left_btn.setFixedSize(25, 22)
        pan_left_btn.setStyleSheet(f"{font_style}")
        pan_left_btn.setToolTip("左移")
        pan_left_btn.clicked.connect(self._pan_left)
        pan_left_proxy = QGraphicsProxyWidget()
        pan_left_proxy.setWidget(pan_left_btn)
        pan_left_proxy.setPos(btn_start_x, btn_y)
        pan_left_proxy.setZValue(self.z_value + 15)
        scene.addItem(pan_left_proxy)
        self._widgets.append(pan_left_proxy)
        btn_start_x += 28
        
        # Pan right button
        pan_right_btn = QPushButton("▶")
        pan_right_btn.setFixedSize(25, 22)
        pan_right_btn.setStyleSheet(f"{font_style}")
        pan_right_btn.setToolTip("右移")
        pan_right_btn.clicked.connect(self._pan_right)
        pan_right_proxy = QGraphicsProxyWidget()
        pan_right_proxy.setWidget(pan_right_btn)
        pan_right_proxy.setPos(btn_start_x, btn_y)
        pan_right_proxy.setZValue(self.z_value + 15)
        scene.addItem(pan_right_proxy)
        self._widgets.append(pan_right_proxy)
        btn_start_x += 33
        
        # Cursor/Ruler toggle button
        self._cursor_btn = QPushButton("标尺")
        self._cursor_btn.setFixedSize(40, 22)
        self._cursor_btn.setStyleSheet(f"{font_style}")
        self._cursor_btn.setToolTip("显示/隐藏标尺")
        self._cursor_btn.clicked.connect(self._toggle_cursor)
        cursor_proxy = QGraphicsProxyWidget()
        cursor_proxy.setWidget(self._cursor_btn)
        cursor_proxy.setPos(btn_start_x, btn_y)
        cursor_proxy.setZValue(self.z_value + 15)
        scene.addItem(cursor_proxy)
        self._widgets.append(cursor_proxy)
    
    def _make_show_popup(self, combo):
        """Create a showPopup method that pauses refresh"""
        original_showPopup = combo.__class__.showPopup
        def showPopup():
            self._pause_parent_refresh(True)
            original_showPopup(combo)
        return showPopup
    
    def _make_hide_popup(self, combo):
        """Create a hidePopup method that resumes refresh"""
        original_hidePopup = combo.__class__.hidePopup
        def hidePopup():
            original_hidePopup(combo)
            self._pause_parent_refresh(False)
        return hidePopup
    
    def _make_mouse_press_event(self, time_edit):
        """Create a mousePressEvent that pauses refresh for QDateTimeEdit"""
        original_mousePressEvent = time_edit.__class__.mousePressEvent
        def mousePressEvent(event):
            self._pause_parent_refresh(True)
            original_mousePressEvent(time_edit, event)
            # Start a timer to resume refresh after a delay
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(3000, lambda: self._pause_parent_refresh(False))
        return mousePressEvent
    
    def _pause_parent_refresh(self, pause):
        """Pause or resume parent widget refresh"""
        if self._parent_widget and hasattr(self._parent_widget, '_pause_refresh'):
            self._parent_widget._pause_refresh = pause
    
    def _on_var_changed(self, var_name):
        """Handle variable selection change"""
        if var_name and var_name != "-- 选择变量 --":
            if var_name not in self.selected_tags:
                self.selected_tags.append(var_name)
                print(f"HistoryTrend: Added variable {var_name}, selected: {self.selected_tags}")
    
    def _set_quick_time(self, secs):
        """Set quick time range"""
        from PyQt5.QtCore import QDateTime
        end_dt = QDateTime.currentDateTime()
        start_dt = end_dt.addSecs(secs)
        
        if hasattr(self, '_start_time_edit'):
            self._start_time_edit.setDateTime(start_dt)
        if hasattr(self, '_end_time_edit'):
            self._end_time_edit.setDateTime(end_dt)
        
        self.end_time = end_dt.toPyDateTime()
        self.start_time = start_dt.toPyDateTime()
        print(f"HistoryTrend: Time range set to {self.start_time} - {self.end_time}")
    
    def _do_query(self):
        """Execute query"""
        from datetime import datetime, timedelta
        
        if not self.selected_tags:
            print("HistoryTrend: No variables selected")
            return
        
        # Get time from editors
        if hasattr(self, '_start_time_edit') and hasattr(self, '_end_time_edit'):
            self.start_time = self._start_time_edit.dateTime().toPyDateTime()
            self.end_time = self._end_time_edit.dateTime().toPyDateTime()
        
        if not self.start_time or not self.end_time:
            self.end_time = datetime.now()
            self.start_time = self.end_time - timedelta(hours=1)
        
        if self.start_time >= self.end_time:
            print("HistoryTrend: Start time must be before end time")
            return
        
        self._query_data_from_db()
    
    def _update_cursor_position(self, scene_pos):
        """Update cursor position based on mouse position"""
        from datetime import timedelta
        
        if not hasattr(self, '_chart_area_bounds'):
            return
        
        chart_area_x, chart_area_y, chart_area_width, chart_area_height = self._chart_area_bounds
        
        # Clamp position to chart area
        x = max(chart_area_x, min(scene_pos.x(), chart_area_x + chart_area_width))
        
        # Calculate time at cursor position
        if self.start_time and self.end_time:
            total_duration = (self.end_time - self.start_time).total_seconds()
            zoomed_duration = total_duration / self._zoom_level
            
            # Calculate center time
            center_time = self.start_time + timedelta(seconds=total_duration / 2)
            
            # Apply pan offset
            pan_seconds = self._pan_offset_x * (total_duration / chart_area_width) / self._zoom_level
            
            # Calculate new time range
            new_start = center_time - timedelta(seconds=zoomed_duration / 2) + timedelta(seconds=pan_seconds)
            new_end = center_time + timedelta(seconds=zoomed_duration / 2) + timedelta(seconds=pan_seconds)
            
            # Calculate cursor time based on x position
            ratio = (x - chart_area_x) / chart_area_width
            cursor_time = new_start + (new_end - new_start) * ratio
            
            self._cursor_x = x
            self._cursor_time = cursor_time
            self._redraw_chart()
    
    def _clear_chart(self):
        """Clear chart data"""
        self.selected_tags = []
        self.chart_data = {}
        print("HistoryTrend: Cleared")
    
    def _zoom_in(self):
        """Zoom in"""
        self._zoom_level = min(self._zoom_level * 1.2, 10.0)
        print(f"HistoryTrend: Zoom in to {self._zoom_level:.2f}")
        self._redraw_chart()
    
    def _zoom_out(self):
        """Zoom out"""
        self._zoom_level = max(self._zoom_level / 1.2, 0.1)
        print(f"HistoryTrend: Zoom out to {self._zoom_level:.2f}")
        self._redraw_chart()
    
    def _reset_zoom(self):
        """Reset zoom and pan"""
        self._zoom_level = 1.0
        self._pan_offset_x = 0
        self._pan_offset_y = 0
        print("HistoryTrend: Reset zoom")
        self._redraw_chart()
    
    def _pan_left(self):
        """Pan left"""
        self._pan_offset_x -= 50
        print(f"HistoryTrend: Pan left, offset={self._pan_offset_x}")
        self._redraw_chart()
    
    def _pan_right(self):
        """Pan right"""
        self._pan_offset_x += 50
        print(f"HistoryTrend: Pan right, offset={self._pan_offset_x}")
        self._redraw_chart()
    
    def _toggle_cursor(self):
        """Toggle cursor/ruler display"""
        self._show_cursor = not self._show_cursor
        if hasattr(self, '_cursor_btn'):
            self._cursor_btn.setStyleSheet(f"background-color: {'#2196F3' if self._show_cursor else 'transparent'}; color: white;")
        self._redraw_chart()
    
    def _redraw_chart(self):
        """Redraw chart with current zoom and pan"""
        if not self.chart_data:
            print("HistoryTrend: No chart data to redraw")
            return
        
        if not hasattr(self, '_scene') or not self._scene:
            print("HistoryTrend: No scene available")
            return
        
        print(f"HistoryTrend: Redrawing chart with zoom={self._zoom_level:.2f}, pan={self._pan_offset_x}")
        
        # Remove old chart items from scene (but not cursor area or controls)
        items_to_remove = []
        for item in self._scene.items():
            if hasattr(item, 'zValue'):
                z = item.zValue()
                # Remove chart items (z=2,3,4) but keep controls (z=15) and cursor area (z=10)
                if z > self.z_value + 1 and z < self.z_value + 10:
                    items_to_remove.append(item)
        
        for item in items_to_remove:
            self._scene.removeItem(item)
        
        # Redraw chart
        self._draw_chart(self._scene, control_height=35)
        
        # Force scene update
        self._scene.update()
        
        # Request parent widget to refresh if available
        if self._parent_widget and hasattr(self._parent_widget, 'refresh_display'):
            # Don't call refresh_display to avoid full refresh, just update scene
            pass
    
    def _query_data_from_db(self):
        """Query historical data from database"""
        from scada_app.core.sql_server_manager import sql_server_manager
        
        if not sql_server_manager.connection:
            try:
                if not sql_server_manager.connect():
                    print("HistoryTrend: Failed to connect to database")
                    return
            except Exception as e:
                print(f"HistoryTrend: Database connection error: {e}")
                return
        
        self.chart_data = {}
        
        for tag_name in self.selected_tags:
            try:
                data = sql_server_manager.query_log_data(
                    tag_name, 
                    self.start_time, 
                    self.end_time,
                    limit=5000
                )
                
                if data:
                    points = []
                    for record in data:
                        try:
                            ts = record['timestamp']
                            if isinstance(ts, str):
                                from datetime import datetime
                                ts = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S.%f')
                            val = float(record['tag_value'])
                            points.append((ts.timestamp() * 1000, val))
                        except (ValueError, TypeError, KeyError):
                            continue
                    
                    points.sort(key=lambda x: x[0])
                    self.chart_data[tag_name] = points
                    print(f"HistoryTrend: Loaded {len(points)} points for {tag_name}")
            except Exception as e:
                print(f"HistoryTrend: Error querying {tag_name}: {e}")
    
    def _draw_chart(self, scene, control_height=35):
        """Draw chart with matplotlib"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            from datetime import datetime, timedelta
            
            bg_color = self.properties.get('bg_color', '#FFFFFF')
            grid_visible = self.properties.get('grid_visible', True)
            grid_color = self.properties.get('grid_color', '#E0E0E0')
            line_width = self.properties.get('line_width', 2)
            show_legend = self.properties.get('show_legend', True)
            y_min = self.properties.get('y_min', 0)
            y_max = self.properties.get('y_max', 100)
            y_auto_scale = self.properties.get('y_auto_scale', True)
            
            colors = ['#FF0000', '#00AA00', '#0000FF', '#FF00FF', '#AAAA00', '#00AAAA', '#FF8000', '#8000FF']
            
            margin_left = 55
            margin_right = 80
            margin_top = 10
            margin_bottom = 35
            
            chart_x = self.x + margin_left
            chart_y = self.y + control_height + margin_top
            chart_width = self.width - margin_left - margin_right
            chart_height = self.height - control_height - margin_top - margin_bottom
            
            if chart_width <= 0 or chart_height <= 0:
                return
            
            # Apply zoom to time range
            if self.start_time and self.end_time:
                total_duration = (self.end_time - self.start_time).total_seconds()
                zoomed_duration = total_duration / self._zoom_level
                
                # Calculate center time
                center_time = self.start_time + timedelta(seconds=total_duration / 2)
                
                # Apply pan offset (in seconds)
                pan_seconds = self._pan_offset_x * (total_duration / chart_width) / self._zoom_level
                
                # Calculate new time range
                new_start = center_time - timedelta(seconds=zoomed_duration / 2) + timedelta(seconds=pan_seconds)
                new_end = center_time + timedelta(seconds=zoomed_duration / 2) + timedelta(seconds=pan_seconds)
            else:
                new_start = self.start_time
                new_end = self.end_time
            
            dpi = 100
            fig_width = chart_width / dpi
            fig_height = chart_height / dpi
            
            fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
            fig.patch.set_facecolor(bg_color)
            ax.set_facecolor(bg_color)
            
            # Filter data based on zoomed time range
            filtered_data = {}
            all_values = []
            
            for tag_name, points in self.chart_data.items():
                filtered_points = []
                for p in points:
                    ts = p[0] / 1000  # Convert to seconds
                    if new_start and new_end:
                        ts_dt = datetime.fromtimestamp(ts)
                        if new_start <= ts_dt <= new_end:
                            filtered_points.append(p)
                            all_values.append(p[1])
                    else:
                        filtered_points.append(p)
                        all_values.append(p[1])
                filtered_data[tag_name] = filtered_points
            
            if y_auto_scale and all_values:
                y_min = min(all_values) * 0.9
                y_max = max(all_values) * 1.1
                if y_min == y_max:
                    y_min -= 1
                    y_max += 1
            
            ax.set_ylim(y_min, y_max)
            
            if grid_visible:
                ax.grid(True, linestyle='--', color=grid_color, linewidth=0.5)
            
            ax.tick_params(axis='both', labelsize=7)
            
            import matplotlib.dates as mdates
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
            
            legend_labels = []
            for idx, (tag_name, points) in enumerate(filtered_data.items()):
                if not points:
                    continue
                
                x_data = [datetime.fromtimestamp(p[0] / 1000) for p in points]
                y_data = [p[1] for p in points]
                
                color = colors[idx % len(colors)]
                ax.plot(x_data, y_data, color=color, linewidth=line_width, marker=None)
                legend_labels.append(tag_name)
            
            if show_legend and legend_labels:
                ax.legend(legend_labels, loc='upper right', fontsize=6, framealpha=0.8)
            
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
            pixmap_item.setPos(chart_x, chart_y)
            pixmap_item.setZValue(self.z_value + 2)
            scene.addItem(pixmap_item)
            
            # Draw cursor/ruler if enabled
            if self._show_cursor and filtered_data:
                self._draw_cursor(scene, chart_x, chart_y, chart_width, chart_height, 
                                  new_start, new_end, y_min, y_max, filtered_data, colors)
            
            # Show time range 
            # 在图表底部显示当前缩放/平移后的时间范围
            if new_start and new_end:
                # 格式化时间范围字符串，例如 "12-25 14:30 ~ 12-25 15:30"
                time_range_text = f"{new_start.strftime('%m-%d %H:%M')} ~ {new_end.strftime('%m-%d %H:%M')}"
                # 创建文本图元用于显示时间范围
                time_label = QGraphicsTextItem(time_range_text)
                # 设置字体为微软雅黑，字号10
                time_label.setFont(QFont('Microsoft YaHei', 10))
                # 设置文字颜色为浅灰色 (#666666)
                time_label.setDefaultTextColor(QColor('#000000'))
                # 定位到图表左下角附近，x偏移100，y距离底部25像素
                time_label.setPos(self.x + 100, self.y + self.height - 25)
                # 设置Z值确保显示在图表上方但低于控件
                time_label.setZValue(self.z_value + 3)
                # 将时间范围标签添加到场景中
                scene.addItem(time_label)
            
        except ImportError:
            print("HistoryTrend: matplotlib not installed")
        except Exception as e:
            print(f"HistoryTrend: Error drawing chart: {e}")
    
    def _draw_cursor(self, scene, chart_x, chart_y, chart_width, chart_height,
                     start_time, end_time, y_min, y_max, filtered_data, colors):
        """Draw cursor/ruler line with value display"""
        try:
            # Use stored cursor position
            cursor_x = self._cursor_x if self._cursor_x else chart_x + chart_width / 2
            
            # Draw cursor line
            cursor_line = QGraphicsLineItem(cursor_x, chart_y, cursor_x, chart_y + chart_height)
            cursor_line.setPen(QPen(QColor('#FF0000'), 1, Qt.DashLine))
            cursor_line.setZValue(self.z_value + 4)
            scene.addItem(cursor_line)
            
            # Calculate time at cursor position
            if start_time and end_time and self._cursor_time:
                cursor_time = self._cursor_time
                
                # Find values at cursor time for each tag
                value_texts = []
                for idx, (tag_name, points) in enumerate(filtered_data.items()):
                    if not points:
                        continue
                    
                    # Find closest point to cursor time
                    cursor_ts = cursor_time.timestamp() * 1000
                    closest_point = min(points, key=lambda p: abs(p[0] - cursor_ts))
                    value_texts.append(f"{tag_name}: {closest_point[1]:.2f}")
                
                # Display values
                if value_texts:
                    value_text = "\n".join(value_texts[:4])
                    cursor_label = QGraphicsTextItem(value_text)
                    cursor_label.setFont(QFont('Microsoft YaHei', 8))
                    cursor_label.setDefaultTextColor(QColor('#FF0000'))
                    
                    # Position label
                    label_x = cursor_x + 5
                    if label_x + 100 > chart_x + chart_width:
                        label_x = cursor_x - 105
                    
                    cursor_label.setPos(label_x, chart_y + 5)
                    cursor_label.setZValue(self.z_value + 4)
                    scene.addItem(cursor_label)
                
                # Display cursor time
                time_text = cursor_time.strftime('%m-%d %H:%M:%S')
                time_label = QGraphicsTextItem(time_text)
                time_label.setFont(QFont('Microsoft YaHei', 7))
                time_label.setDefaultTextColor(QColor('#FF0000'))
                time_label.setPos(cursor_x - 35, chart_y + chart_height + 2)
                time_label.setZValue(self.z_value + 4)
                scene.addItem(time_label)
                
        except Exception as e:
            print(f"HistoryTrend: Error drawing cursor: {e}")


class HMITableViewRuntime(HMITableView):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the table view in runtime mode"""
        # Draw border
        border_item = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        pen = QPen(Qt.black)
        pen.setWidth(1)
        border_item.setPen(pen)
        border_item.setBrush(QBrush(QColor("#F5F5F5")))
        scene.addItem(border_item)
        
        # Draw title
        title_text = QGraphicsTextItem(self.properties.get('title', 'Data Table'))
        title_text.setDefaultTextColor(Qt.black)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        title_text.setFont(font)
        title_text.setPos(self.x + 10, self.y + 5)
        scene.addItem(title_text)
        
        # Draw placeholder for table
        # In a real implementation, this would render actual table data
        table_placeholder = QGraphicsTextItem("DATA TABLE")
        table_placeholder.setDefaultTextColor(Qt.black)
        font = QFont()
        font.setPointSize(8)
        table_placeholder.setFont(font)
        
        text_rect = table_placeholder.boundingRect()
        text_x = self.x + (self.width - text_rect.width()) / 2
        text_y = self.y + (self.height - text_rect.height()) / 2
        table_placeholder.setPos(text_x, text_y)
        
        scene.addItem(table_placeholder)
        
    def update_from_data_manager(self, data_manager):
        """Update the table view based on data from the data manager"""
        pass


class HMIProgressBarRuntime(HMIProgressBar):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the progress bar in runtime mode with dynamic data"""
        # Get value from bound variable
        value = 0
        min_val = self.properties.get('min_value', 0)
        max_val = self.properties.get('max_value', 100)
        
        if self.variables and data_manager:
            bound_var = self.variables[0]
            var_value = data_manager.get_tag_value(bound_var.variable_name)
            if var_value is not None:
                try:
                    value = float(var_value)
                    # Clamp value to range
                    value = max(min_val, min(max_val, value))
                except (ValueError, TypeError):
                    value = min_val
        
        # Draw background
        bg_item = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        bg_item.setBrush(QBrush(QColor("#E0E0E0")))
        bg_item.setPen(QPen(Qt.NoPen))
        bg_item.setZValue(self.z_value)
        scene.addItem(bg_item)
        
        # Draw progress fill
        if max_val > min_val:
            progress = (value - min_val) / (max_val - min_val)
            fill_width = self.width * progress
            
            fill_item = QGraphicsRectItem(self.x, self.y, fill_width, self.height)
            fill_color = QColor(self.properties.get('fill_color', '#4CAF50'))
            fill_item.setBrush(QBrush(fill_color))
            fill_item.setPen(QPen(Qt.NoPen))
            fill_item.setZValue(self.z_value + 1)
            scene.addItem(fill_item)
        
        # Draw border
        border_item = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        pen = QPen(Qt.black)
        pen.setWidth(1)
        border_item.setPen(pen)
        border_item.setBrush(QBrush(Qt.NoBrush))
        border_item.setZValue(self.z_value + 2)
        scene.addItem(border_item)
        
        # Draw value text
        if self.properties.get('show_value', True):
            precision = self.properties.get('precision', 0)
            if precision > 0:
                text = f"{value:.{precision}f}"
            else:
                text = f"{int(value)}"
            
            unit = self.properties.get('unit', '')
            if unit:
                text += f" {unit}"
            
            text_item = QGraphicsTextItem(text)
            text_item.setDefaultTextColor(Qt.black)
            font = QFont()
            font.setPointSize(self.properties.get('font_size', 10))
            text_item.setFont(font)
            
            # Center text
            text_rect = text_item.boundingRect()
            text_x = self.x + (self.width - text_rect.width()) / 2
            text_y = self.y + (self.height - text_rect.height()) / 2
            text_item.setPos(text_x, text_y)
            text_item.setZValue(self.z_value + 3)
            scene.addItem(text_item)


class HMIInputFieldRuntime(HMIInputField):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the input field in runtime mode with interactive input"""
        # Get current value
        value = ""
        
        if self.variables and data_manager:
            bound_var = self.variables[0]
            var_value = data_manager.get_tag_value(bound_var.variable_name)
            if var_value is not None:
                value = str(var_value)
        
        # Draw background
        bg_item = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        bg_color = QColor(self.properties.get('bg_color', '#FFFFFF'))
        bg_item.setBrush(QBrush(bg_color))
        pen = QPen(Qt.black)
        pen.setWidth(1)
        bg_item.setPen(pen)
        scene.addItem(bg_item)
        
        # Draw text
        text_item = QGraphicsTextItem(value if value else self.properties.get('placeholder', ''))
        text_color = QColor(self.properties.get('text_color', '#000000'))
        text_item.setDefaultTextColor(text_color)
        font = QFont()
        font.setPointSize(self.properties.get('font_size', 10))
        text_item.setFont(font)
        text_item.setPos(self.x + 5, self.y + (self.height - 15) / 2)
        
        scene.addItem(text_item)
        
        # Add click handler for input
        if self.variables and data_manager:
            bg_item.hmi_object = self
            bg_item.data_manager = data_manager
            bg_item.text_item = text_item
            bg_item.hmi_scene = scene  # Store scene reference for PLC access
            
            def mouse_press_handler(event):
                obj = bg_item.hmi_object
                dm = bg_item.data_manager

                if obj.variables:
                    bound_var = obj.variables[0]
                    var_name = bound_var.variable_name

                    current_value = dm.get_tag_value(var_name)
                    if current_value is None:
                        current_value = ""

                    # Determine input type based on tag data type
                    input_type = obj.properties.get('input_type', 'text')
                    tag = dm.tags.get(var_name)
                    if tag and hasattr(tag, 'data_type'):
                        from scada_app.architecture import DataType
                        if tag.data_type in [DataType.INT, DataType.DINT]:
                            input_type = 'int'
                        elif tag.data_type == DataType.REAL:
                            input_type = 'real'
                        elif tag.data_type == DataType.BOOL:
                            input_type = 'bool'

                    if input_type in ['number', 'real']:
                        try:
                            current_num = float(current_value) if current_value else 0
                            new_value, ok = QInputDialog.getDouble(
                                None, "输入数值", f"{var_name}:",
                                current_num, -999999, 999999, 2
                            )
                        except (ValueError, TypeError):
                            new_value, ok = QInputDialog.getDouble(
                                None, "输入数值", f"{var_name}:",
                                0, -999999, 999999, 2
                            )
                    elif input_type == 'int':
                        try:
                            current_num = int(current_value) if current_value else 0
                            new_value, ok = QInputDialog.getInt(
                                None, "输入整数", f"{var_name}:",
                                current_num, -999999, 999999
                            )
                        except (ValueError, TypeError):
                            new_value, ok = QInputDialog.getInt(
                                None, "输入整数", f"{var_name}:",
                                0, -999999, 999999
                            )
                    else:
                        new_value, ok = QInputDialog.getText(
                            None, "输入文本", f"{var_name}:",
                            text=str(current_value)
                        )

                    if ok:
                        try:
                            dm.update_tag(var_name, new_value)
                            print(f"InputField: Updated {var_name} to {new_value}")
                            
                            # 写入PLC
                            if hasattr(bg_item, 'hmi_scene') and hasattr(bg_item.hmi_scene, 'plc_manager'):
                                plc_manager = bg_item.hmi_scene.plc_manager
                                if plc_manager:
                                    try:
                                        plc_manager.write_tag(var_name, new_value)
                                        print(f"InputField: Wrote {var_name} = {new_value} to PLC")
                                    except Exception as e:
                                        print(f"InputField: Error writing to PLC: {e}")
                        except Exception as e:
                            print(f"InputField: Error updating {var_name}: {e}")
            
            bg_item.mousePressEvent = mouse_press_handler


class HMICheckBoxRuntime(HMICheckBox):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the checkbox in runtime mode with interactive toggle"""
        # Get current state
        checked = False
        
        if self.variables and data_manager:
            bound_var = self.variables[0]
            var_value = data_manager.get_tag_value(bound_var.variable_name)
            if var_value is not None:
                # Handle bit offset if specified
                bit_offset = getattr(bound_var, 'bit_offset', None)
                if bit_offset is not None and isinstance(var_value, (int, float)):
                    var_value = (int(var_value) >> int(bit_offset)) & 1
                checked = bool(var_value)
        
        # Draw checkbox box
        box_size = min(self.width, self.height) - 4
        box_x = self.x + 2
        box_y = self.y + (self.height - box_size) / 2
        
        box_item = QGraphicsRectItem(box_x, box_y, box_size, box_size)
        box_item.setBrush(QBrush(QColor("#FFFFFF")))
        pen = QPen(Qt.black)
        pen.setWidth(1)
        box_item.setPen(pen)
        scene.addItem(box_item)
        
        # Draw check mark if checked
        if checked:
            check_path = QPainterPath()
            check_path.moveTo(box_x + 3, box_y + box_size / 2)
            check_path.lineTo(box_x + box_size / 3, box_y + box_size - 3)
            check_path.lineTo(box_x + box_size - 3, box_y + 3)
            
            check_item = QGraphicsPathItem(check_path)
            check_pen = QPen(QColor("#4CAF50"))
            check_pen.setWidth(2)
            check_item.setPen(check_pen)
            scene.addItem(check_item)
        
        # Draw label
        label_text = self.properties.get('label', 'Check')
        text_item = QGraphicsTextItem(label_text)
        text_item.setDefaultTextColor(Qt.black)
        font = QFont()
        font.setPointSize(self.properties.get('font_size', 10))
        text_item.setFont(font)
        text_item.setPos(box_x + box_size + 5, self.y + (self.height - 15) / 2)
        scene.addItem(text_item)
        
        # Add click handler
        if self.variables and data_manager:
            box_item.hmi_object = self
            box_item.data_manager = data_manager
            box_item.hmi_scene = scene
            
            def mouse_press_handler(event):
                obj = box_item.hmi_object
                dm = box_item.data_manager
                
                if obj.variables:
                    bound_var = obj.variables[0]
                    var_name = bound_var.variable_name
                    bit_offset = getattr(bound_var, 'bit_offset', None)
                    
                    try:
                        # Read current raw value
                        current_raw_value = dm.get_tag_value(var_name)
                        
                        # Extract bit value if bit_offset is specified
                        if bit_offset is not None:
                            if current_raw_value is None or isinstance(current_raw_value, bool):
                                plc_value = dm.read_tag_value(var_name)
                                if plc_value is not None:
                                    current_raw_value = plc_value
                            
                            if current_raw_value is not None:
                                current_bit = (int(current_raw_value) >> int(bit_offset)) & 1
                                current_value = bool(current_bit)
                            else:
                                current_value = False
                        else:
                            current_value = bool(current_raw_value) if current_raw_value is not None else False
                        
                        new_value = not current_value
                        dm.update_tag(var_name, new_value)
                        print(f"CheckBox: Toggled {var_name} bit {bit_offset} to {new_value}")
                        
                        # Write to PLC
                        if hasattr(box_item, 'hmi_scene') and hasattr(box_item.hmi_scene, 'plc_manager'):
                            plc_manager = box_item.hmi_scene.plc_manager
                            if plc_manager:
                                try:
                                    if bit_offset is not None:
                                        plc_manager.write_tag(var_name, new_value, bit_offset)
                                        print(f"CheckBox: Wrote bit {bit_offset} = {new_value} to {var_name}")
                                    else:
                                        plc_manager.write_tag(var_name, new_value)
                                        print(f"CheckBox: Wrote {var_name} = {new_value} to PLC")
                                except Exception as e:
                                    print(f"CheckBox: Error writing to PLC: {e}")
                    except Exception as e:
                        print(f"CheckBox: Error toggling {var_name}: {e}")
            
            box_item.mousePressEvent = mouse_press_handler


class HMIDropdownRuntime(HMIDropdown):
    # Class-level storage for persistent widgets across redraws
    _widget_registry = {}
    
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the dropdown in runtime mode with embedded QComboBox"""
        from PyQt5.QtWidgets import QGraphicsProxyWidget
        
        # Generate unique key for this dropdown instance
        widget_key = f"dropdown_{id(self)}"
        
        # Get options with new value-text mapping format
        items = self.properties.get('items', [
            {'value': '0', 'text': 'Item 1'},
            {'value': '1', 'text': 'Item 2'},
            {'value': '2', 'text': 'Item 3'}
        ])
        
        # Extract display texts from value-text mapping
        options = []
        # Bind mode is always 'value' for dropdown (removed index mode as per user request)
        bind_mode = 'value'
        
        if isinstance(items, list) and items:
            for item in items:
                if isinstance(item, dict):
                    options.append(item.get('text', ''))
                else:
                    options.append(str(item))
        else:
            options = ['Item 1', 'Item 2', 'Item 3']
        
        # Get current value from data manager
        current_index = 0
        current_val = None
        
        if self.variables and data_manager:
            bound_var = self.variables[0]
            var_name = bound_var.variable_name
            try:
                current_val = data_manager.get_tag_value(var_name)
                # Handle bit offset if specified
                bit_offset = getattr(bound_var, 'bit_offset', None)
                if bit_offset is not None and isinstance(current_val, (int, float)):
                    current_val = (int(current_val) >> int(bit_offset)) & 1
            except:
                current_val = None
            
            # Find current index by matching the value (always use value mode)
            if isinstance(items, list) and items and current_val is not None:
                found = False
                for idx, item in enumerate(items):
                    if isinstance(item, dict) and str(item.get('value', '')) == str(current_val):
                        current_index = idx
                        found = True
                        break
                if not found:
                    print(f"Dropdown Warning: Value '{current_val}' not found in items, defaulting to index 0")
                    current_index = 0
        
        # Check if we already have a persistent widget for this dropdown
        proxy = None
        combo = None
        
        if widget_key in HMIDropdownRuntime._widget_registry:
            try:
                # Try to reuse existing widget
                proxy = HMIDropdownRuntime._widget_registry[widget_key]
                combo = proxy.widget()
                
                # Check if the proxy is still valid (not deleted)
                if proxy.scene() is None:
                    # Add back to scene if it was removed
                    scene.addItem(proxy)
                
                # Update position and size
                proxy.setPos(self.x, self.y)
                combo.setFixedSize(int(self.width), int(self.height))
                
                # Update options if changed (only if not currently open)
                if not combo.view().isVisible():
                    # Get current selection before updating
                    old_index = combo.currentIndex()
                    old_text = combo.currentText() if old_index >= 0 else ""
                    
                    combo.blockSignals(True)
                    combo.clear()
                    combo.addItems(options)
                    
                    # Try to restore selection based on current variable value
                    # current_index is calculated from data_manager value
                    if 0 <= current_index < len(options):
                        combo.setCurrentIndex(current_index)
                    elif old_index >= 0 and old_index < len(options):
                        # Fallback to old index if current_index is invalid
                        combo.setCurrentIndex(old_index)
                    elif old_text:
                        # Try to find by text
                        idx = combo.findText(old_text)
                        if idx >= 0:
                            combo.setCurrentIndex(idx)
                    combo.blockSignals(False)
            except RuntimeError:
                # Object was deleted, remove from registry and create new one
                del HMIDropdownRuntime._widget_registry[widget_key]
                proxy = None
                combo = None
        
        if proxy is None:
            # Create new QComboBox
            combo = QComboBox()
            combo.addItems(options)
            combo.setCurrentIndex(current_index)
            
            # Set font
            font = QFont()
            font.setPointSize(self.properties.get('font_size', 10))
            font.setBold(self.properties.get('font_bold', False))
            font.setItalic(self.properties.get('font_italic', False))
            font.setUnderline(self.properties.get('font_underline', False))
            combo.setFont(font)
            
            # Set size to match the control
            combo.setFixedSize(int(self.width), int(self.height))
            
            # Create proxy widget to embed in graphics scene
            proxy = QGraphicsProxyWidget()
            proxy.setWidget(combo)
            proxy.setPos(self.x, self.y)
            proxy.setZValue(100)  # Ensure it's on top
            scene.addItem(proxy)
            
            # Store in registry
            HMIDropdownRuntime._widget_registry[widget_key] = proxy
            
            # Handle dropdown popup show/hide to pause/resume refresh
            if parent_widget:
                # Store original methods
                original_show_popup = combo.showPopup
                original_hide_popup = combo.hidePopup
                
                def on_popup_shown():
                    parent_widget._pause_refresh = True
                    print("Dropdown: Pausing refresh")
                    original_show_popup()
                
                def on_popup_hidden():
                    original_hide_popup()
                    parent_widget._pause_refresh = False
                    print("Dropdown: Resuming refresh")
                
                # Override methods
                combo.showPopup = on_popup_shown
                combo.hidePopup = on_popup_hidden
            
            # Handle selection change
            def on_current_index_changed(index):
                if index < 0 or index >= len(options):
                    return
                
                # Find the corresponding value for the selected text
                selected_index = index
                new_value = options[index]
                
                if isinstance(items, list) and items and selected_index < len(items):
                    item = items[selected_index]
                    if isinstance(item, dict):
                        new_value = item.get('value', str(selected_index))
                    else:
                        new_value = str(selected_index)
                else:
                    new_value = str(selected_index)
                
                # Convert to number if possible
                try:
                    numeric_value = float(new_value)
                    if numeric_value.is_integer():
                        new_value = int(numeric_value)
                except ValueError:
                    pass
                
                # Update variable if bound
                if self.variables and data_manager:
                    try:
                        bound_var = self.variables[0]
                        var_name = bound_var.variable_name
                        bit_offset = getattr(bound_var, 'bit_offset', None)
                        
                        data_manager.update_tag(var_name, new_value)
                        print(f"Dropdown: Selected {var_name} = {new_value}, bit_offset={bit_offset}")
                        
                        # Write to PLC with bit_offset if specified
                        if hasattr(proxy, 'hmi_scene') and hasattr(proxy.hmi_scene, 'plc_manager'):
                            plc_manager = proxy.hmi_scene.plc_manager
                            if plc_manager:
                                try:
                                    if bit_offset is not None:
                                        plc_manager.write_tag(var_name, new_value, bit_offset)
                                        print(f"Dropdown: Wrote bit {bit_offset} = {new_value} to {var_name}")
                                    else:
                                        plc_manager.write_tag(var_name, new_value)
                                        print(f"Dropdown: Wrote {var_name} = {new_value} to PLC")
                                except Exception as e:
                                    print(f"Dropdown: Error writing to PLC: {e}")
                    except Exception as e:
                        print(f"Dropdown: Error setting variable: {e}")
            
            combo.currentIndexChanged.connect(on_current_index_changed)
        
        # Store references on proxy for access
        proxy.hmi_object = self
        proxy.data_manager = data_manager
        proxy.parent_widget = parent_widget
        proxy.hmi_scene = scene


class HMIAlarmDisplayRuntime(HMIAlarmDisplay):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the alarm display in runtime mode"""
        # Draw background
        bg_item = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        bg_item.setBrush(QBrush(QColor("#FFFFFF")))
        pen = QPen(Qt.black)
        pen.setWidth(1)
        bg_item.setPen(pen)
        scene.addItem(bg_item)
        
        # Draw title
        title_text = QGraphicsTextItem("报警显示")
        title_text.setDefaultTextColor(Qt.black)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        title_text.setFont(font)
        title_text.setPos(self.x + 5, self.y + 5)
        scene.addItem(title_text)
        
        # Draw alarm list placeholder
        # In a real implementation, this would show actual alarms from an alarm manager
        alarm_placeholder = QGraphicsTextItem("[报警列表]")
        alarm_placeholder.setDefaultTextColor(Qt.gray)
        font = QFont()
        font.setPointSize(9)
        alarm_placeholder.setFont(font)
        alarm_placeholder.setPos(self.x + 5, self.y + 30)
        scene.addItem(alarm_placeholder)


class HMITextAreaRuntime(HMITextArea):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the text area in runtime mode"""
        # Get text content
        text_content = self.properties.get('text', '')
        
        if self.variables and data_manager:
            bound_var = self.variables[0]
            var_value = data_manager.get_tag_value(bound_var.variable_name)
            if var_value is not None:
                text_content = str(var_value)
        
        # Draw background
        bg_item = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        bg_color = QColor(self.properties.get('bg_color', '#FFFFFF'))
        bg_item.setBrush(QBrush(bg_color))
        pen = QPen(Qt.black)
        pen.setWidth(1)
        bg_item.setPen(pen)
        scene.addItem(bg_item)
        
        # Draw text (truncated if too long)
        max_chars = self.properties.get('max_chars', 500)
        if len(text_content) > max_chars:
            text_content = text_content[:max_chars] + "..."
        
        # Simple text display (multi-line support would need more complex handling)
        text_item = QGraphicsTextItem(text_content)
        text_color = QColor(self.properties.get('text_color', '#000000'))
        text_item.setDefaultTextColor(text_color)
        font = QFont()
        font.setPointSize(self.properties.get('font_size', 10))
        text_item.setFont(font)
        text_item.setTextWidth(self.width - 10)
        text_item.setPos(self.x + 5, self.y + 5)
        scene.addItem(text_item)


class HMITextListRuntime(HMITextList):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the text list in runtime mode with value-text mapping"""
        # Get items list with value-text mapping
        items = self.properties.get('items', [])
        # Bind mode is always 'value' for text list (removed index mode)
        display_mode = self.properties.get('display_mode', 'list')
        
        # Get current variable value if bound
        current_var_value = None
        if self.variables and data_manager:
            bound_var = self.variables[0]
            current_var_value = data_manager.get_tag_value(bound_var.variable_name)
        
        # Determine which item to highlight based on variable value (always use value mode)
        selected_idx = -1
        if current_var_value is not None:
            var_str = str(current_var_value)
            # Find item with matching value
            for i, item in enumerate(items):
                if isinstance(item, dict):
                    if item.get('value') == var_str:
                        selected_idx = i
                        break
                else:
                    # Old format fallback
                    if str(i) == var_str:
                        selected_idx = i
                        break
        
        # Draw background
        bg = QGraphicsRectItem(self.x, self.y, self.width, self.height)
        bg.setBrush(QBrush(QColor(self.properties.get('background_color', '#FFFFFF'))))
        if self.properties.get('show_border', True):
            bg.setPen(QPen(QColor(self.properties.get('border_color', '#999999'))))
        else:
            bg.setPen(QPen(Qt.NoPen))
        scene.addItem(bg)
        
        # Get colors and font
        text_color = QColor(self.properties.get('text_color', '#000000'))
        selected_color = QColor(self.properties.get('selected_color', '#2196F3'))
        
        font = QFont()
        font.setFamily(self.properties.get('font_family', 'Microsoft YaHei'))
        font.setPointSize(self.properties.get('font_size', 11))
        
        if display_mode == 'single':
            # Single line display mode - show only the matched item text
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
            scene.addItem(text_item)
        else:
            # List display mode - show all items
            item_height = self.properties.get('item_height', 25)
            
            y_offset = self.y + 2
            for i, item in enumerate(items):
                if y_offset + item_height > self.y + self.height:
                    break
                
                # Get display text (support both dict and string format)
                if isinstance(item, dict):
                    display_text = item.get('text', '')
                    item_value = item.get('value', str(i))
                else:
                    display_text = str(item)
                    item_value = str(i)
                
                # Draw item background if selected (matching variable value)
                if i == selected_idx:
                    item_bg = QGraphicsRectItem(self.x + 2, y_offset, self.width - 4, item_height)
                    item_bg.setBrush(QBrush(selected_color))
                    item_bg.setPen(QPen(Qt.NoPen))
                    scene.addItem(item_bg)
                
                # Draw item text
                text_item = QGraphicsTextItem(display_text)
                text_item.setFont(font)
                if i == selected_idx:
                    text_item.setDefaultTextColor(QColor('#FFFFFF'))
                else:
                    text_item.setDefaultTextColor(text_color)
                text_item.setPos(self.x + 8, y_offset + 2)
                scene.addItem(text_item)
                
                y_offset += item_height
        
        # Add click handler for item selection (if not read-only and in list mode)
        if not self.properties.get('read_only', False) and display_mode == 'list':
            bg.hmi_object = self
            bg.data_manager = data_manager
            bg.items = items
            bg.bind_mode = 'value'
            
            def mouse_press_handler(event):
                obj = bg.hmi_object
                dm = bg.data_manager
                local_items = bg.items
                local_bind_mode = bg.bind_mode
                
                # Calculate which item was clicked
                click_y = event.pos().y() - obj.y
                item_h = obj.properties.get('item_height', 25)
                clicked_idx = int((click_y - 2) / item_h)
                
                if 0 <= clicked_idx < len(local_items):
                    # Update selected index
                    obj.properties['selected_index'] = clicked_idx
                    
                    # If bound to variable, update the variable with selected item value
                    if obj.variables and dm:
                        bound_var = obj.variables[0]
                        var_name = bound_var.variable_name
                        
                        # Get the value to write based on bind mode
                        selected_item = local_items[clicked_idx]
                        if local_bind_mode == 'value' and isinstance(selected_item, dict):
                            value_to_write = selected_item.get('value', str(clicked_idx))
                        else:
                            # Index mode or old format
                            value_to_write = str(clicked_idx)
                        
                        try:
                            dm.update_tag(var_name, value_to_write)
                            print(f"TextList: Set {var_name} to {value_to_write}")
                        except Exception as e:
                            print(f"TextList: Error updating {var_name}: {e}")
            
            bg.mousePressEvent = mouse_press_handler


class HMILineRuntime(HMILine):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the line in runtime mode"""
        line = QGraphicsLineItem(
            self.properties.get('x1', self.x), 
            self.properties.get('y1', self.y),
            self.properties.get('x2', self.x + self.width), 
            self.properties.get('y2', self.y + self.height)
        )
        pen = QPen(QColor(self.properties.get('color', '#000000')))
        pen.setWidth(self.properties.get('line_width', 2))
        line.setPen(pen)
        line.setZValue(self.z_value)
        scene.addItem(line)


class HMIRectangleRuntime(HMIRectangle):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the rectangle in runtime mode"""
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


class HMICircleRuntime(HMICircle):
    def draw_runtime(self, scene, data_manager, parent_widget=None):
        """Draw the circle/ellipse in runtime mode"""
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


class HMIViewer(QWidget):
    """HMI Viewer widget for displaying HMI screens at runtime"""
    
    data_updated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.data_manager = None
        self.plc_manager = None
        self.project_data = None
        self.project_path = None
        self.current_screen_index = -1
        self.hmi_objects = []
        self.refresh_timer = None
        
        self._persistent_widgets = {}
        
        self._pause_refresh = False
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create graphics scene and view
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 1000, 600)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        # Center the view alignment
        self.view.setAlignment(Qt.AlignCenter)
        # Remove the frame border around the view
        self.view.setFrameStyle(QGraphicsView.NoFrame)
        
        # 安装事件过滤器以捕获鼠标松开事件
        self.view.viewport().installEventFilter(self)
        
        layout.addWidget(self.view)
        
        self.setLayout(layout)
        
        # Store fullscreen state
        self.is_fullscreen = False
        
        # Set window title with fullscreen hint
        self.update_window_title()
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        window = self.window()
        if not window:
            return
        
        if self.is_fullscreen:
            window.showNormal()
            self.is_fullscreen = False
            self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        else:
            window.showFullScreen()
            self.is_fullscreen = True
            self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.update_window_title()
    
    def update_window_title(self):
        """Update window title with fullscreen hint"""
        window = self.window()
        if window:
            base_title = "HMI 运行系统"
            if self.is_fullscreen:
                window.setWindowTitle(f"{base_title} - 全屏模式 (F11退出)")
            else:
                window.setWindowTitle(f"{base_title} - (F11全屏)")
    
    def keyPressEvent(self, event):
        """Handle key press events - F11 to toggle fullscreen, +/- to zoom trend charts"""
        if event.key() == Qt.Key_F11:
            self.toggle_fullscreen()
        elif event.key() in [Qt.Key_Plus, Qt.Key_Equal, Qt.Key_Minus]:
            for obj in self.hmi_objects:
                if hasattr(obj, 'zoom_in') and hasattr(obj, 'zoom_out'):
                    if event.key() in [Qt.Key_Plus, Qt.Key_Equal]:
                        obj.zoom_in()
                    elif event.key() == Qt.Key_Minus:
                        obj.zoom_out()
            self._redraw_scene()
        else:
            super().keyPressEvent(event)
    
    def eventFilter(self, obj, event):
        """事件过滤器 - 处理鼠标松开事件以支持点动功能"""
        from PyQt5.QtCore import QEvent
        if event.type() == QEvent.MouseButtonRelease:
            # 检查场景中是否有活动的点动操作
            if hasattr(self.scene, '_momentary_release_handlers'):
                for handler in self.scene._momentary_release_handlers:
                    try:
                        handler(event)
                    except Exception as e:
                        print(f"Error in momentary release handler: {e}")
        return super().eventFilter(obj, event)
    
    def set_managers(self, data_manager, plc_manager):
        """Set the data and PLC managers"""
        self.data_manager = data_manager
        self.plc_manager = plc_manager
    
    def load_hmi_project(self, hmi_file):
        """Load an HMI project file"""
        try:
            self.project_path = hmi_file
            
            with open(hmi_file, 'r', encoding='utf-8') as f:
                self.project_data = json.load(f)
            
            # Initialize trend data manager
            self.trend_manager = TrendDataManager()
            self.trend_manager.initialize(hmi_file)
            
            # Load the main screen or first screen
            main_screen_index = 0
            screens = self.project_data.get('hmi_screens', [])
            for i, screen in enumerate(screens):
                if screen.get('is_main', False):
                    main_screen_index = i
                    break
            
            self.load_screen_by_index(main_screen_index)
            print(f"HMI project loaded: {len(screens)} screens")
            
        except Exception as e:
            print(f"Error loading HMI project: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load HMI project:\n{e}")
    
    def load_screen_by_index(self, index):
        """Load a screen by its index"""
        if not self.project_data or index < 0 or index >= len(self.project_data.get('hmi_screens', [])):
            return
        
        # Unsubscribe old screen's tags
        self._unsubscribe_current_tags()
        
        self.current_screen_index = index
        screen_data = self.project_data['hmi_screens'][index]
        
        # Clear current objects
        self.hmi_objects = []
        
        # Create HMI objects from screen data
        for obj_data in screen_data.get('objects', []):
            hmi_obj = self.create_object_from_data(obj_data)
            if hmi_obj:
                self.hmi_objects.append(hmi_obj)
        
        # Subscribe new screen's tags
        self._subscribe_current_tags()
        
        # Refresh display
        self.refresh_display()
    
    def _subscribe_current_tags(self):
        """Subscribe tags for current screen"""
        from scada_app.core.tag_subscription_manager import tag_subscription_manager, SubscriptionType
        
        # Collect all variable names from current screen
        tag_names = []
        for obj in self.hmi_objects:
            if hasattr(obj, 'variables') and obj.variables:
                for var in obj.variables:
                    if var.variable_name:
                        tag_names.append(var.variable_name)
        
        if tag_names:
            tag_subscription_manager.subscribe(tag_names, SubscriptionType.HMI)
            print(f"HMI: Subscribed {len(tag_names)} tags for screen {self.current_screen_index}")
    
    def _unsubscribe_current_tags(self):
        """Unsubscribe tags for current screen"""
        from scada_app.core.tag_subscription_manager import tag_subscription_manager, SubscriptionType
        
        # Unsubscribe all HMI tags
        tag_subscription_manager.unsubscribe_all(SubscriptionType.HMI)
    
    def load_screen_by_name(self, screen_name):
        """Load a screen by its name"""
        if not self.project_data:
            return
        
        for i, screen in enumerate(self.project_data.get('hmi_screens', [])):
            if screen.get('name') == screen_name:
                self.load_screen_by_index(i)
                return
    
    def load_screen_by_number(self, screen_number):
        """Load a screen by its number"""
        if not self.project_data:
            return
        
        for i, screen in enumerate(self.project_data.get('hmi_screens', [])):
            if screen.get('number') == screen_number:
                self.load_screen_by_index(i)
                return
    
    def create_object_from_data(self, obj_data):
        """Create an HMI object from JSON data"""
        obj_type = obj_data.get('obj_type', '')
        
        # Map object types to their runtime classes
        runtime_classes = {
            'button': HMIButtonRuntime,
            'label': HMILabelRuntime,
            'gauge': HMIGaugeRuntime,
            'switch': HMISwitchRuntime,
            'light': HMILightRuntime,
            'picture': HMIPictureBoxRuntime,
            'picture_list': HMIPictureListRuntime,
            'trend_chart': HMITrendChartRuntime,
            'history_trend': HMIHistoryTrendRuntime,
            'table_view': HMITableViewRuntime,
            'progress': HMIProgressBarRuntime,
            'input': HMIInputFieldRuntime,
            'checkbox': HMICheckBoxRuntime,
            'dropdown': HMIDropdownRuntime,
            'textarea': HMITextAreaRuntime,
            'text_list': HMITextListRuntime,
            'alarm_display': HMIAlarmDisplayRuntime,
            'line': HMILineRuntime,
            'rectangle': HMIRectangleRuntime,
            'circle': HMICircleRuntime,
            'clock': HMIClockRuntime,
        }
        
        if obj_type in runtime_classes:
            obj_class = runtime_classes[obj_type]
            obj = obj_class()
            obj.x = obj_data.get('x', 0)
            obj.y = obj_data.get('y', 0)
            obj.width = obj_data.get('width', 100)
            obj.height = obj_data.get('height', 50)
            obj.properties = obj_data.get('properties', {})
            
            if 'visibility' in obj_data:
                obj.visibility = obj_data['visibility'].copy()
            
            # Restore variables
            for var_data in obj_data.get('variables', []):
                obj.add_variable_binding(
                    var_data.get('variable_name', ''),
                    var_data.get('variable_type', 'read'),
                    var_data.get('address', ''),
                    var_data.get('description', ''),
                    var_data.get('bit_offset', None)
                )
            
            # Subscribe trend chart variables to global manager
            if obj_type == 'trend_chart' and hasattr(obj, 'subscribe_variables'):
                obj.subscribe_variables()
            
            return obj
        
        return None
    
    def refresh_display(self):
        """Refresh the display with current data values from DataManager
        
        Note: Data polling is handled by DataPoller. This method only redraws the scene
        using data already available in DataManager.
        """
        if self.scene:
            if self._pause_refresh:
                return
            
            self._redraw_scene()
    
    def save_all_trend_data(self):
        """Save all trend chart data to files"""
        if hasattr(self, 'trend_manager'):
            self.trend_manager.save_data_to_file()
    
    def cleanup(self):
        """Cleanup resources before closing"""
        self.save_all_trend_data()
    
    def _redraw_scene(self):
        """重绘场景"""
        if not self.scene:
            return
        
        # Store references in scene for access by objects
        self.scene.data_manager = self.data_manager
        self.scene.plc_manager = self.plc_manager
        
        # Update trend data manager with new data
        if hasattr(self, 'trend_manager') and self.data_manager:
            self.trend_manager.update_from_data_manager(self.data_manager)
        
        # Save HistoryTrend states before clearing scene
        history_trend_states = []
        for obj in self.hmi_objects:
            if hasattr(obj, 'obj_type') and obj.obj_type == 'history_trend':
                state = {
                    'obj': obj,
                    '_zoom_level': getattr(obj, '_zoom_level', 1.0),
                    '_pan_offset_x': getattr(obj, '_pan_offset_x', 0),
                    '_pan_offset_y': getattr(obj, '_pan_offset_y', 0),
                    '_show_cursor': getattr(obj, '_show_cursor', False),
                    '_cursor_x': getattr(obj, '_cursor_x', None),
                    '_cursor_time': getattr(obj, '_cursor_time', None),
                    'chart_data': getattr(obj, 'chart_data', {}),
                    'selected_tags': getattr(obj, 'selected_tags', []),
                    'start_time': getattr(obj, 'start_time', None),
                    'end_time': getattr(obj, 'end_time', None),
                    '_start_time_value': getattr(obj, '_start_time_edit', None),
                    '_end_time_value': getattr(obj, '_end_time_edit', None),
                }
                # Save actual datetime values from time editors if they exist
                if hasattr(obj, '_start_time_edit') and obj._start_time_edit:
                    state['_start_time_value'] = obj._start_time_edit.dateTime().toPyDateTime()
                if hasattr(obj, '_end_time_edit') and obj._end_time_edit:
                    state['_end_time_value'] = obj._end_time_edit.dateTime().toPyDateTime()
                history_trend_states.append(state)
        
        # Clear scene and redraw all objects with current data
        self.scene.clear()
        
        # Get current screen resolution and background color
        resolution = {'width': 1000, 'height': 600}
        background_color = '#F0F0F0'  # Default background color
        if self.project_data and 'hmi_screens' in self.project_data:
            screens = self.project_data['hmi_screens']
            if self.current_screen_index >= 0 and self.current_screen_index < len(screens):
                screen = screens[self.current_screen_index]
                resolution = screen.get('resolution', resolution)
                background_color = screen.get('background_color', '#F0F0F0')
        
        # Update scene rect to match current resolution
        self.scene.setSceneRect(0, 0, resolution['width'], resolution['height'])
        
        # Draw background with screen's background color
        bg = QGraphicsRectItem(0, 0, resolution['width'], resolution['height'])
        bg.setBrush(QBrush(QColor(background_color)))
        bg.setPen(QPen(Qt.NoPen))
        self.scene.addItem(bg)
        
        # Redraw all objects with current data
        for i, obj in enumerate(self.hmi_objects):
            obj.z_value = i * 10
            # Check visibility before drawing
            if hasattr(obj, 'check_visibility'):
                if not obj.check_visibility(self.data_manager):
                    continue
            obj.draw_runtime(self.scene, self.data_manager, self)
        
        # Restore HistoryTrend states after redraw
        for state in history_trend_states:
            obj = state['obj']
            obj._zoom_level = state['_zoom_level']
            obj._pan_offset_x = state['_pan_offset_x']
            obj._pan_offset_y = state['_pan_offset_y']
            obj._show_cursor = state['_show_cursor']
            obj._cursor_x = state['_cursor_x']
            obj._cursor_time = state['_cursor_time']
            obj.chart_data = state['chart_data']
            obj.selected_tags = state['selected_tags']
            obj.start_time = state['start_time']
            obj.end_time = state['end_time']
            # Set flag to prevent recursive redraw
            obj._is_restoring_state = True
            # Restore time editor values
            if state['_start_time_value'] and hasattr(obj, '_start_time_edit') and obj._start_time_edit:
                from PyQt5.QtCore import QDateTime
                obj._start_time_edit.setDateTime(QDateTime(state['_start_time_value']))
            if state['_end_time_value'] and hasattr(obj, '_end_time_edit') and obj._end_time_edit:
                from PyQt5.QtCore import QDateTime
                obj._end_time_edit.setDateTime(QDateTime(state['_end_time_value']))
            # Clear flag
            obj._is_restoring_state = False
            # Note: Don't redraw chart here - HistoryTrend shows historical data
            # and doesn't need frequent refresh. Chart will be redrawn only on user actions.
    
    def _batch_read_variables(self):
        """批量读取变量值 - 已弃用
        
        Note: 数据轮询现在由DataPoller统一处理。此方法保留仅用于兼容性，
        实际不执行任何操作。
        """
        # Data polling is handled by DataPoller
        pass
    
    def start_refresh(self, interval_ms=None):
        """Start automatic refresh timer - 自适应刷新间隔"""
        # 根据变量数量计算刷新间隔
        if interval_ms is None:
            interval_ms = self._calculate_refresh_interval()
        
        if self.refresh_timer is None:
            self.refresh_timer = QTimer(self)
            self.refresh_timer.timeout.connect(self.refresh_display)
        self.refresh_timer.start(interval_ms)
        print(f"HMI刷新已启动，间隔: {interval_ms}ms")
    
    def _calculate_refresh_interval(self):
        """根据变量数量计算最优刷新间隔"""
        # 收集所有变量
        all_tags = set()
        for obj in self.hmi_objects:
            if hasattr(obj, 'variables') and obj.variables:
                for var in obj.variables:
                    if var.variable_name:
                        all_tags.add(var.variable_name)
        
        tag_count = len(all_tags)
        
        # 根据变量数量调整刷新间隔
        # 基础间隔500ms，每10个变量增加100ms
        if tag_count == 0:
            return 1000  # 默认1秒
        elif tag_count <= 10:
            return 500   # 变量少，刷新快
        elif tag_count <= 50:
            return 800   # 中等数量
        elif tag_count <= 100:
            return 1000  # 较多变量
        else:
            return 1500  # 大量变量，降低刷新频率避免过载
    
    def stop_refresh(self):
        """Stop automatic refresh timer"""
        if self.refresh_timer:
            self.refresh_timer.stop()
            self.refresh_timer = None
            print("HMIViewer: Refresh timer stopped")
