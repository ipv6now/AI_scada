"""
Project Manager - Manages SCADA project configuration including connections, variables, HMI screens, and alarms
"""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


class ProjectManager:
    """
    Manages the entire SCADA project including:
    - PLC connections
    - Variables/tags
    - HMI screens
    - Alarms
    - Data logging configurations
    """
    
    def __init__(self, data_manager, plc_manager, config_manager, system_service_manager=None):
        self.data_manager = data_manager
        self.plc_manager = plc_manager
        self.config_manager = config_manager
        self.system_service_manager = system_service_manager
        self.project_file = None
        self.project_dir = None
        self.hmi_designer = None  # Reference to HMI designer for saving/loading screens
        
    def set_hmi_designer(self, hmi_designer):
        """Set reference to HMI designer for saving/loading screens"""
        self.hmi_designer = hmi_designer
        
    def save_project(self, project_file, is_save_as=False):
        """
        Save the entire project configuration to a file
        
        Args:
            project_file: Path to the project file
            is_save_as: If True, this is a "Save As" operation and resources will be copied
        """
        try:
            # Create project directory if it doesn't exist
            project_path = Path(project_file)
            new_project_dir = project_path.parent
            new_project_dir.mkdir(parents=True, exist_ok=True)
            
            # Create images directory in new location
            new_images_dir = new_project_dir / 'images'
            new_images_dir.mkdir(exist_ok=True)
            
            # If this is "Save As", copy all image resources to new location
            if is_save_as and self.project_dir and self.project_dir != new_project_dir:
                print(f"Save As: Copying resources from {self.project_dir} to {new_project_dir}")
                self._copy_project_resources(new_project_dir)
            
            # Prepare project data with updated paths
            project_data = {
                'metadata': {
                    'version': '1.7',  # Updated version for query mode and bug fixes
                    'created': datetime.now().isoformat(),
                    'modified': datetime.now().isoformat()
                },
                'connections': self._export_connections(),
                'tags': self._export_tags(),
                'hmi_screens': self._export_hmi_screens(new_project_dir),
                'alarms': self._export_alarms(),
                'logging_configs': self._export_logging_configs(),
                'sql_server_config': self._export_sql_server_config(),
                'storage_type': self._export_storage_type(),
                'poll_interval': self._export_poll_interval(),
                'variable_groups': self._export_variable_groups(),
                'alarm_types': self._export_alarm_types()  # 添加报警类型配置
            }
            
            # Save project data to JSON file
            with open(project_file, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2, ensure_ascii=False)
            
            # Update project file reference
            self.project_file = project_file
            self.project_dir = new_project_dir
            
            print(f"Project saved to {project_file}")
            return True
            
        except Exception as e:
            print(f"Error saving project: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def _copy_project_resources(self, new_project_dir):
        """Copy all project resources (images, etc.) to new project directory"""
        import shutil
        
        if not self.project_dir or not self.project_dir.exists():
            return
        
        # Copy images folder
        old_images_dir = self.project_dir / 'images'
        if old_images_dir.exists():
            new_images_dir = new_project_dir / 'images'
            new_images_dir.mkdir(exist_ok=True)
            
            for img_file in old_images_dir.iterdir():
                if img_file.is_file():
                    dest_file = new_images_dir / img_file.name
                    try:
                        shutil.copy2(img_file, dest_file)
                        print(f"  Copied: {img_file.name}")
                    except Exception as e:
                        print(f"  Error copying {img_file.name}: {e}")
        
        # Copy other resource folders if needed
        # (exports, logs, etc.)
        for folder_name in ['exports', 'logs']:
            old_folder = self.project_dir / folder_name
            if old_folder.exists():
                new_folder = new_project_dir / folder_name
                new_folder.mkdir(exist_ok=True)
                for file in old_folder.iterdir():
                    if file.is_file():
                        try:
                            shutil.copy2(file, new_folder / file.name)
                        except Exception as e:
                            print(f"  Error copying {file.name}: {e}")
    
    def load_project(self, project_file):
        """
        Load the entire project configuration from a file
        """
        try:
            if not os.path.exists(project_file):
                print(f"Project file does not exist: {project_file}")
                return False
            
            # Load project data from JSON file
            with open(project_file, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            # Set project file and directory
            project_path = Path(project_file)
            self.project_file = project_file
            self.project_dir = project_path.parent
            
            # Clear current configuration
            self._clear_current_configuration()
            
            # Import components
            self._import_connections(project_data.get('connections', []))
            self._import_tags(project_data.get('tags', []))
            self._import_hmi_screens(project_data.get('hmi_screens', []))
            self._import_alarms(project_data.get('alarms', []))
            self._import_logging_configs(project_data.get('logging_configs', []))
            self._import_sql_server_config(project_data.get('sql_server_config', {}))
            self._import_storage_type(project_data.get('storage_type'))
            self._import_poll_interval(project_data.get('poll_interval'))
            self._import_variable_groups(project_data.get('variable_groups'))
            self._import_alarm_types(project_data.get('alarm_types', {}))  # 导入报警类型配置

            # Ensure alarm rules are set to system service manager after project load
            self._set_alarm_rules_to_system_service_manager()

            print(f"Project loaded from {project_file}")
            return True
            
        except Exception as e:
            print(f"Error loading project: {str(e)}")
            return False
    
    def _export_connections(self):
        """Export PLC connections to JSON-serializable format"""
        connections = []
        for name, conn in self.plc_manager.connections.items():
            conn_data = {
                'name': conn.name,
                'protocol': conn.protocol.value,
                'address': conn.address,
                'port': conn.port,
                'slave_id': conn.slave_id,
                'extra_params': conn.extra_params
            }
            connections.append(conn_data)
        return connections
    
    def _import_connections(self, connections_data):
        """Import PLC connections from JSON data"""
        from scada_app.comm.plc_manager import PLCConnection, PLCProtocol
        
        for conn_data in connections_data:
            protocol = PLCProtocol(conn_data['protocol'])
            conn = PLCConnection(
                name=conn_data['name'],
                protocol=protocol,
                address=conn_data['address'],
                port=conn_data['port'],
                slave_id=conn_data['slave_id'],
                extra_params=conn_data.get('extra_params', {})
            )
            self.plc_manager.add_connection(conn)
    
    def _export_tags(self):
        """Export tags to JSON-serializable format"""
        tags = []
        for name, tag in self.data_manager.tags.items():
            tag_data = {
                'name': tag.name,
                'tag_type': tag.tag_type.value,
                'data_type': tag.data_type.value,
                'address': tag.address,
                'description': tag.description,
                'plc_connection': tag.plc_connection,
                'bit_offset': getattr(tag, 'bit_offset', None),
                'value': tag.value,
                'timestamp': tag.timestamp.isoformat() if tag.timestamp else None,
                'quality': tag.quality
            }
            tags.append(tag_data)
        return tags
    
    def _import_tags(self, tags_data):
        """Import tags from JSON data"""
        from scada_app.core.data_manager import Tag, TagType, DataType
        from datetime import datetime
        
        # Mapping for backward compatibility with old tag types
        tag_type_mapping = {
            'INPUT': 'PLC',
            'OUTPUT': 'PLC',
            'MEMORY': 'INTERNAL',
            'CALCULATED': 'INTERNAL'
        }
        
        for tag_data in tags_data:
            # Convert old tag types to new ones
            old_tag_type = tag_data['tag_type']
            new_tag_type = tag_type_mapping.get(old_tag_type, old_tag_type)
            
            tag = Tag(
                name=tag_data['name'],
                tag_type=TagType(new_tag_type),
                data_type=DataType(tag_data['data_type']),
                address=tag_data.get('address'),
                description=tag_data.get('description', ''),
                plc_connection=tag_data.get('plc_connection', ''),
                bit_offset=tag_data.get('bit_offset', None)
            )
            
            # Restore additional properties
            if tag_data.get('value') is not None:
                tag.value = tag_data['value']
            if tag_data.get('timestamp'):
                tag.timestamp = datetime.fromisoformat(tag_data['timestamp'])
            tag.quality = tag_data.get('quality', 'GOOD')
            
            self.data_manager.add_tag(tag)
    
    def _export_hmi_screens(self, project_dir=None):
        """Export HMI screens to JSON-serializable format
        
        Args:
            project_dir: Target project directory for calculating relative paths
        """
        # If HMI designer is available, export screens directly from it
        if self.hmi_designer and hasattr(self.hmi_designer, 'screens'):
            screens_data = []
            print(f"Exporting {len(self.hmi_designer.screens)} screens")
            for screen in self.hmi_designer.screens:
                # Handle both HMIScreen objects and dict formats
                if hasattr(screen, 'objects'):
                    objects = screen.objects
                    screen_name = screen.name if hasattr(screen, 'name') else 'Untitled'
                    screen_number = screen.number if hasattr(screen, 'number') else 0
                    screen_is_main = screen.is_main if hasattr(screen, 'is_main') else False
                    screen_resolution = screen.resolution if hasattr(screen, 'resolution') else {'width': 1000, 'height': 600}
                    screen_bg_color = screen.background_color if hasattr(screen, 'background_color') else '#FFFFFF'
                else:
                    objects = screen.get('objects', [])
                    screen_name = screen.get('name', 'Untitled')
                    screen_number = screen.get('number', 0)
                    screen_is_main = screen.get('is_main', False)
                    screen_resolution = screen.get('resolution', {'width': 1000, 'height': 600})
                    screen_bg_color = screen.get('background_color', '#FFFFFF')
                
                print(f"  Screen '{screen_name}': {len(objects)} objects")
                
                screen_data = {
                    'name': screen_name,
                    'number': screen_number,
                    'is_main': screen_is_main,
                    'resolution': screen_resolution,
                    'background_color': screen_bg_color,
                    'objects': []
                }
                
                # Export objects in the screen
                for obj in objects:
                    obj_data = {
                        'obj_type': obj.obj_type,
                        'x': obj.x,
                        'y': obj.y,
                        'width': obj.width,
                        'height': obj.height,
                        'properties': {},
                        'variables': []
                    }
                    
                    # Process properties - convert absolute image paths to relative
                    for prop_key, prop_value in obj.properties.items():
                        if prop_key == 'image_path' and prop_value and project_dir:
                            # Convert absolute path to relative path
                            try:
                                image_path = Path(prop_value)
                                if image_path.is_absolute():
                                    # Try to make it relative to project directory
                                    try:
                                        rel_path = image_path.relative_to(project_dir)
                                        obj_data['properties'][prop_key] = str(rel_path)
                                        print(f"    - Converted image path to relative: {rel_path}")
                                    except ValueError:
                                        # Path is not under project directory, copy to images folder
                                        import shutil
                                        images_dir = project_dir / 'images'
                                        images_dir.mkdir(exist_ok=True)
                                        if image_path.exists():
                                            dest_path = images_dir / image_path.name
                                            shutil.copy2(image_path, dest_path)
                                            obj_data['properties'][prop_key] = f"images/{image_path.name}"
                                            print(f"    - Copied external image to project: {image_path.name}")
                                        else:
                                            obj_data['properties'][prop_key] = prop_value
                                else:
                                    obj_data['properties'][prop_key] = prop_value
                            except Exception as e:
                                print(f"    - Error processing image path: {e}")
                                obj_data['properties'][prop_key] = prop_value
                        elif prop_key == 'default_image' and prop_value and project_dir:
                            # Handle default_image for picture_list
                            try:
                                image_path = Path(prop_value)
                                if image_path.is_absolute():
                                    try:
                                        rel_path = image_path.relative_to(project_dir)
                                        obj_data['properties'][prop_key] = str(rel_path)
                                    except ValueError:
                                        import shutil
                                        images_dir = project_dir / 'images'
                                        images_dir.mkdir(exist_ok=True)
                                        if image_path.exists():
                                            dest_path = images_dir / image_path.name
                                            shutil.copy2(image_path, dest_path)
                                            obj_data['properties'][prop_key] = f"images/{image_path.name}"
                                        else:
                                            obj_data['properties'][prop_key] = prop_value
                                else:
                                    obj_data['properties'][prop_key] = prop_value
                            except Exception as e:
                                obj_data['properties'][prop_key] = prop_value
                        elif prop_key == 'state_images' and isinstance(prop_value, list) and project_dir:
                            # Handle state_images array for picture_list
                            processed_states = []
                            import shutil
                            images_dir = project_dir / 'images'
                            images_dir.mkdir(exist_ok=True)
                            
                            for state in prop_value:
                                state_copy = state.copy()
                                if state.get('image_path'):
                                    try:
                                        image_path = Path(state['image_path'])
                                        if image_path.is_absolute():
                                            try:
                                                rel_path = image_path.relative_to(project_dir)
                                                state_copy['image_path'] = str(rel_path)
                                            except ValueError:
                                                if image_path.exists():
                                                    dest_path = images_dir / image_path.name
                                                    shutil.copy2(image_path, dest_path)
                                                    state_copy['image_path'] = f"images/{image_path.name}"
                                    except Exception as e:
                                        pass
                                processed_states.append(state_copy)
                            
                            obj_data['properties'][prop_key] = processed_states
                        else:
                            obj_data['properties'][prop_key] = prop_value
                    
                    # Export variable bindings
                    for var in obj.variables:
                        var_data = {
                            'variable_name': var.variable_name,
                            'variable_type': var.variable_type,
                            'address': var.address,
                            'description': var.description,
                            'bit_offset': getattr(var, 'bit_offset', None)
                        }
                        obj_data['variables'].append(var_data)
                    
                    # Export visibility settings
                    if hasattr(obj, 'visibility'):
                        obj_data['visibility'] = obj.visibility.copy()
                    
                    screen_data['objects'].append(obj_data)
                    
                    # Debug: print variable count for trend charts
                    if obj.obj_type == 'trend_chart':
                        print(f"    - Exported {obj.obj_type} with {len(obj.variables)} variables")
                    else:
                        print(f"    - Exported {obj.obj_type}")
                
                screens_data.append(screen_data)
            
            return screens_data
        
        # Fallback: return empty list if no HMI designer available
        print("No HMI designer available or no screens")
        return []
    
    def _import_hmi_screens(self, screens_data):
        """Import HMI screens from JSON data"""
        if not self.hmi_designer or not screens_data:
            return
        
        # Clear current screens
        self.hmi_designer.screens = []
        self.hmi_designer.screen_list.clear()
        
        # Import screens
        for idx, screen_data in enumerate(screens_data):
            from scada_app.hmi.hmi_designer import HMIScreen
            # Use index as default number if not specified
            screen_number = screen_data.get('number', idx)
            screen = HMIScreen(
                name=screen_data.get('name', 'Untitled'),
                number=screen_number,
                resolution=screen_data.get('resolution', {'width': 1000, 'height': 600})
            )
            screen.is_main = screen_data.get('is_main', False)
            screen.background_color = screen_data.get('background_color', '#FFFFFF')
            
            # Import objects
            from scada_app.hmi.hmi_designer import (
                HMIButton, HMILabel, HMIGauge, HMISwitch, HMILight,
                HMIPictureBox, HMIPictureList, HMITrendChart, HMIHistoryTrend, HMITableView, HMIProgressBar,
                HMILine, HMIRectangle, HMICircle,
                HMIInputField, HMICheckBox, HMIDropdown,
                HMITextArea, HMITextList, HMIAlarmDisplay
            )
            
            for obj_data in screen_data.get('objects', []):
                obj_type = obj_data.get('obj_type', '')
                x = obj_data.get('x', 0)
                y = obj_data.get('y', 0)
                width = obj_data.get('width', 100)
                height = obj_data.get('height', 50)
                properties = obj_data.get('properties', {})
                
                # Create object based on type
                if obj_type == 'button':
                    obj = HMIButton(x, y, width, height, properties.get('text', 'Button'))
                elif obj_type == 'label':
                    obj = HMILabel(x, y, width, height, properties.get('text', 'Label'))
                elif obj_type == 'gauge':
                    obj = HMIGauge(x, y, width, height, 
                                 properties.get('min_val', 0), 
                                 properties.get('max_val', 100))
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
                    obj = HMIProgressBar(x, y, width, height,
                                        properties.get('value', 50),
                                        properties.get('min_val', 0),
                                        properties.get('max_val', 100))
                elif obj_type == 'line':
                    obj = HMILine(properties.get('x1', x), properties.get('y1', y),
                                 properties.get('x2', x + width), properties.get('y2', y))
                elif obj_type == 'rectangle':
                    obj = HMIRectangle(x, y, width, height)
                elif obj_type == 'circle':
                    obj = HMICircle(x + width // 2, y + height // 2, width // 2)
                elif obj_type == 'input':
                    obj = HMIInputField(x, y, width, height)
                elif obj_type == 'checkbox':
                    obj = HMICheckBox(x, y, width, height)
                    obj.properties['text'] = properties.get('text', '')
                    obj.properties['checked'] = properties.get('checked', False)
                elif obj_type == 'dropdown':
                    obj = HMIDropdown(x, y, width, height)
                elif obj_type == 'textarea':
                    obj = HMITextArea(x, y, width, height, properties.get('text', ''))
                elif obj_type == 'text_list':
                    obj = HMITextList(x, y, width, height)
                elif obj_type == 'alarm_display':
                    obj = HMIAlarmDisplay(x, y, width, height)
                else:
                    continue
                
                # Set properties - resolve relative image paths to absolute paths
                for prop_key, prop_value in properties.items():
                    if prop_key == 'image_path' and prop_value:
                        # Check if it's a relative path
                        if not os.path.isabs(prop_value):
                            # Convert relative path to absolute path
                            abs_path = self.project_dir / prop_value
                            obj.properties[prop_key] = str(abs_path)
                            print(f"    - Resolved relative image path: {prop_value} -> {abs_path}")
                        else:
                            obj.properties[prop_key] = prop_value
                    elif prop_key == 'default_image' and prop_value:
                        # Handle default_image for picture_list
                        if not os.path.isabs(prop_value):
                            abs_path = self.project_dir / prop_value
                            obj.properties[prop_key] = str(abs_path)
                        else:
                            obj.properties[prop_key] = prop_value
                    elif prop_key == 'state_images' and isinstance(prop_value, list):
                        # Handle state_images array for picture_list
                        processed_states = []
                        for state in prop_value:
                            state_copy = state.copy()
                            if state.get('image_path'):
                                if not os.path.isabs(state['image_path']):
                                    abs_path = self.project_dir / state['image_path']
                                    state_copy['image_path'] = str(abs_path)
                            processed_states.append(state_copy)
                        obj.properties[prop_key] = processed_states
                    else:
                        obj.properties[prop_key] = prop_value
                
                # Import variable bindings
                for var_data in obj_data.get('variables', []):
                    from scada_app.hmi.hmi_designer import VariableBinding
                    var = VariableBinding(
                        var_data.get('variable_name', ''),
                        var_data.get('variable_type', ''),
                        var_data.get('address', ''),
                        var_data.get('description', ''),
                        var_data.get('bit_offset', None)
                    )
                    obj.variables.append(var)
                
                # Import visibility settings
                if 'visibility' in obj_data:
                    obj.visibility = obj_data['visibility'].copy()
                
                # Debug: print variable count for trend charts
                if obj_type == 'trend_chart':
                    print(f"    - Imported trend_chart with {len(obj.variables)} variables: {[v.variable_name for v in obj.variables]}")
                
                screen.objects.append(obj)
            
            self.hmi_designer.screens.append(screen)
        
        # Update screen list to show numbered names
        self.hmi_designer.update_screen_list()
        
        # Switch to first screen if available
        if self.hmi_designer.screens:
            self.hmi_designer.switch_screen(0)
    
    def _export_alarms(self):
        """Export alarm rules to project data"""
        if hasattr(self.config_manager, 'alarm_rules'):
            return self.config_manager.alarm_rules
        return []
    
    def _export_alarm_types(self):
        """Export alarm types configuration to project data"""
        try:
            from scada_app.core.alarm_type_manager import alarm_type_manager
            # 导出所有报警类型配置
            alarm_types_data = {}
            for name, alarm_type in alarm_type_manager.alarm_types.items():
                alarm_types_data[name] = {
                    'display_name': alarm_type.display_name,
                    'foreground_color': alarm_type.foreground_color,
                    'background_color': alarm_type.background_color,
                    'description': alarm_type.description,
                    'enabled': alarm_type.enabled
                }
            return alarm_types_data
        except ImportError:
            print("Warning: Alarm type manager not available")
            return {}
    
    def _import_alarms(self, alarms_data):
        """Import alarm configurations from JSON data"""
        # 导入报警规则到配置管理器
        if not hasattr(self.config_manager, 'alarm_rules'):
            self.config_manager.alarm_rules = []
        
        self.config_manager.alarm_rules.clear()
        
        for alarm_data in alarms_data:
            # 确保数据格式正确
            rule = {
                'tag_name': alarm_data.get('tag_name', ''),
                'alarm_type': alarm_data.get('alarm_type', '状态变化'),
                'condition': alarm_data.get('condition', '假变真'),
                'threshold': alarm_data.get('threshold', 0.0),
                'message': alarm_data.get('message', ''),
                'enabled': alarm_data.get('enabled', True),
                'alarm_type_name': alarm_data.get('alarm_type_name', alarm_data.get('priority', '中')),  # 兼容旧数据
                'bit_offset': alarm_data.get('bit_offset', None),
                'alarm_id': alarm_data.get('alarm_id', None)  # 添加报警ID字段
            }
            # 调试输出：显示加载的报警ID
            self.config_manager.alarm_rules.append(rule)
        
        
        # 同时设置到系统服务管理器
        try:
            from scada_app.hmi.alarm_config_new import AlarmRule
            alarm_rules = []
            for rule_data in alarms_data:
                rule = AlarmRule(
                    tag_name=rule_data.get('tag_name', ''),
                    alarm_type=rule_data.get('alarm_type', '状态变化'),
                    condition=rule_data.get('condition', '假变真'),
                    threshold=rule_data.get('threshold', 0.0),
                    message=rule_data.get('message', ''),
                    enabled=rule_data.get('enabled', True),
                    alarm_type_name=rule_data.get('alarm_type_name', rule_data.get('priority', '中')),  # 兼容旧数据
                    bit_offset=rule_data.get('bit_offset', None),
                    alarm_id=rule_data.get('alarm_id', None)  # 添加报警ID字段
                )
                # 调试输出：显示创建的AlarmRule对象的alarm_id
                alarm_rules.append(rule)
            
            # 设置到系统服务管理器
            if hasattr(self, 'system_service_manager'):
                self.system_service_manager.set_alarm_rules(alarm_rules)
            elif hasattr(self.data_manager, 'system_service_manager'):
                self.data_manager.system_service_manager.set_alarm_rules(alarm_rules)
        except Exception as e:
            print(f"Error setting alarm rules: {e}")
    
    def _set_alarm_rules_to_system_service_manager(self):
        """Set alarm rules to system service manager after project load"""
        if not hasattr(self.config_manager, 'alarm_rules') or not self.config_manager.alarm_rules:
            return
        
        try:
            from scada_app.hmi.alarm_config_new import AlarmRule
            alarm_rules = []
            for rule_data in self.config_manager.alarm_rules:
                rule = AlarmRule(
                    tag_name=rule_data.get('tag_name', ''),
                    alarm_type=rule_data.get('alarm_type', '状态变化'),
                    condition=rule_data.get('condition', '假变真'),
                    threshold=rule_data.get('threshold', 0.0),
                    message=rule_data.get('message', ''),
                    enabled=rule_data.get('enabled', True),
                    alarm_type_name=rule_data.get('alarm_type_name', rule_data.get('priority', '中')),  # 兼容旧数据
                    bit_offset=rule_data.get('bit_offset', None),
                    alarm_id=rule_data.get('alarm_id')  # 添加报警ID字段
                )
                alarm_rules.append(rule)
            
            # 设置到系统服务管理器
            if hasattr(self, 'system_service_manager'):
                self.system_service_manager.set_alarm_rules(alarm_rules)
                print(f"[PROJECT] 项目加载后设置 {len(alarm_rules)} 条报警规则到系统服务管理器")
            elif hasattr(self.data_manager, 'system_service_manager'):
                self.data_manager.system_service_manager.set_alarm_rules(alarm_rules)
                print(f"[PROJECT] 项目加载后设置 {len(alarm_rules)} 条报警规则到系统服务管理器")
            
        except Exception as e:
            print(f"[PROJECT] 项目加载后设置报警规则到系统服务管理器失败: {e}")
    
    def _export_logging_configs(self):
        """Export data logging configurations to JSON-serializable format"""
        # Export logging rules from config manager
        logging_configs = []
        if hasattr(self.config_manager, 'logging_rules'):
            logging_configs = self.config_manager.logging_rules
        return logging_configs
    
    def _import_logging_configs(self, logging_configs_data):
        """Import data logging configurations from JSON data"""
        # Set logging rules in config manager
        if hasattr(self.config_manager, 'set_logging_rules'):
            self.config_manager.set_logging_rules(logging_configs_data)
        else:
            # Store as attribute if method doesn't exist
            self.config_manager.logging_rules = logging_configs_data
    
    def _import_alarm_types(self, alarm_types_data):
        """Import alarm types configuration from project data"""
        try:
            from scada_app.core.alarm_type_manager import alarm_type_manager
            
            # 清空现有的报警类型（保留默认类型）
            # 只删除非默认的报警类型
            default_types = {"critical", "high", "medium", "low"}
            keys_to_remove = []
            for name in alarm_type_manager.alarm_types.keys():
                if name not in default_types:
                    keys_to_remove.append(name)
            
            for name in keys_to_remove:
                del alarm_type_manager.alarm_types[name]
            
            # 导入项目中的报警类型配置
            for name, type_data in alarm_types_data.items():
                try:
                    from scada_app.core.alarm_type_manager import AlarmType
                    alarm_type = AlarmType(
                        name=name,
                        display_name=type_data.get('display_name', name),
                        foreground_color=type_data.get('foreground_color', '#000000'),
                        background_color=type_data.get('background_color', '#FFFFFF'),
                        description=type_data.get('description', ''),
                        enabled=type_data.get('enabled', True)
                    )
                    alarm_type_manager.alarm_types[name] = alarm_type
                except Exception as e:
                    print(f"[PROJECT ERROR] 导入报警类型 {name} 失败: {e}")
            
            
        except ImportError:
            print("Warning: Alarm type manager not available")
        except Exception as e:
            print(f"Error importing alarm types: {e}")

    def _export_storage_type(self):
        """Export storage type to JSON-serializable format"""
        if hasattr(self.config_manager, 'storage_type'):
            return self.config_manager.storage_type
        return "sqlite"

    def _import_storage_type(self, storage_type_data):
        """Import storage type from JSON data"""
        if not storage_type_data:
            return
        
        if hasattr(self.config_manager, 'storage_type'):
            self.config_manager.storage_type = storage_type_data
        
        # Update storage manager
        try:
            from scada_app.core.data_storage_manager import data_storage_manager
            data_storage_manager.set_storage_type(storage_type_data)
        except Exception as e:
            print(f"Error setting storage type: {e}")

    def _export_poll_interval(self):
        """Export poll interval to JSON-serializable format"""
        if hasattr(self.config_manager, 'poll_interval'):
            return self.config_manager.poll_interval
        return 1000

    def _import_poll_interval(self, poll_interval_data):
        """Import poll interval from JSON data"""
        if not poll_interval_data:
            return
        
        if hasattr(self.config_manager, 'poll_interval'):
            self.config_manager.poll_interval = poll_interval_data

    def _export_variable_groups(self):
        """Export variable groups to JSON-serializable format"""
        if hasattr(self.config_manager, 'variable_groups'):
            return self.config_manager.variable_groups
        return {}

    def _import_variable_groups(self, variable_groups_data):
        """Import variable groups from JSON data"""
        if not variable_groups_data:
            variable_groups_data = {}
        
        if hasattr(self.config_manager, 'variable_groups'):
            self.config_manager.variable_groups = variable_groups_data

    def _export_sql_server_config(self):
        """Export SQL Server connection configuration to JSON-serializable format"""
        from scada_app.core.sql_server_manager import sql_server_manager
        import base64

        # Encode password with base64 (basic obfuscation, not encryption)
        password = sql_server_manager.password or ""
        encoded_password = base64.b64encode(password.encode()).decode() if password else ""

        return {
            'server': sql_server_manager.server,
            'database': sql_server_manager.database,
            'username': sql_server_manager.username,
            'password': encoded_password,
            'port': getattr(sql_server_manager, 'port', 1433)
        }

    def _import_sql_server_config(self, sql_server_config_data):
        """Import SQL Server connection configuration from JSON data"""
        if not sql_server_config_data:
            return

        from scada_app.core.sql_server_manager import sql_server_manager
        import base64

        sql_server_manager.server = sql_server_config_data.get('server', 'localhost')
        sql_server_manager.database = sql_server_config_data.get('database', 'HMI_DataLogging')
        sql_server_manager.username = sql_server_config_data.get('username', 'sa')
        sql_server_manager.port = sql_server_config_data.get('port', 1433)

        # Decode password
        encoded_password = sql_server_config_data.get('password', '')
        if encoded_password:
            try:
                sql_server_manager.password = base64.b64decode(encoded_password.encode()).decode()
            except:
                sql_server_manager.password = ""

    def _clear_current_configuration(self):
        """Clear the current project configuration"""
        # Clear connections
        self.plc_manager.connections.clear()
        self.plc_manager.active_connections.clear()
        
        # Clear tags
        self.data_manager.tags.clear()
        
        # Clear alarms (if stored separately)
        self.data_manager.alarms.clear()
    
    def get_recent_project_file(self):
        """Get the most recently used project file"""
        config_dir = Path.home() / '.scada_config'
        config_dir.mkdir(exist_ok=True)
        config_file = config_dir / 'recent_project.json'
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('recent_project')
            except:
                pass
        return None
    
    def set_recent_project_file(self, project_file):
        """Set the most recently used project file"""
        config_dir = Path.home() / '.scada_config'
        config_dir.mkdir(exist_ok=True)
        config_file = config_dir / 'recent_project.json'
        
        with open(config_file, 'w') as f:
            json.dump({'recent_project': project_file}, f)