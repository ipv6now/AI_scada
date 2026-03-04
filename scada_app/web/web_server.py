"""
Web Server Module for SCADA System
Uses Flask + SocketIO for real-time web access
"""

import os
import json
import threading
import time
import socket
from datetime import datetime
from flask import Flask, render_template, jsonify, request, session
from flask_socketio import SocketIO, emit
from flask_cors import CORS


def find_available_port(start_port=8080, max_port=8100):
    """Find an available port starting from start_port"""
    for port in range(start_port, max_port + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result != 0:  # Port is available
                return port
        except:
            pass
    return None


class WebServer:
    """Web server for SCADA remote access"""
    
    def __init__(self, data_manager, plc_manager, project_manager, host='0.0.0.0', port=8080):
        self.data_manager = data_manager
        self.plc_manager = plc_manager
        self.project_manager = project_manager
        self.host = host
        self.port = port
        
        # Create Flask app
        self.app = Flask(__name__, 
                        template_folder='templates',
                        static_folder='static')
        self.app.config['SECRET_KEY'] = 'scada-secret-key-change-in-production'
        
        # Enable CORS
        CORS(self.app)
        
        # Create SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='eventlet')
        
        # Background thread for data broadcasting
        self.broadcast_thread = None
        self.running = False
        
        # Setup routes and socket events
        self._setup_routes()
        self._setup_socket_events()
    
    def _parse_screens_from_project(self, screens_data):
        """Parse screens from project file data"""
        screens = []
        for screen_data in screens_data:
            # Create a simple screen object
            class SimpleScreen:
                pass
            
            screen = SimpleScreen()
            screen.name = screen_data.get('name', 'Unknown')
            screen.number = screen_data.get('number', 1)
            screen.is_main = screen_data.get('is_main', False)
            screen.background_color = screen_data.get('background_color', '#f0f0f0')
            screen.width = screen_data.get('width', 800)
            screen.height = screen_data.get('height', 600)
            
            # Parse objects
            screen.objects = []
            for obj_data in screen_data.get('objects', []):
                class SimpleObject:
                    pass
                
                obj = SimpleObject()
                obj.name = obj_data.get('name', '')
                obj.type = obj_data.get('type', '')
                obj.x = obj_data.get('x', 0)
                obj.y = obj_data.get('y', 0)
                obj.width = obj_data.get('width', 100)
                obj.height = obj_data.get('height', 50)
                obj.properties = obj_data.get('properties', {})
                
                # Parse variables
                obj.variables = []
                for var_data in obj_data.get('variables', []):
                    class SimpleVariable:
                        pass
                    var = SimpleVariable()
                    var.name = var_data.get('name', '')
                    var.bit_offset = var_data.get('bit_offset')
                    obj.variables.append(var)
                
                screen.objects.append(obj)
            
            screens.append(screen)
        
        return screens
        
    def _setup_routes(self):
        """Setup HTTP routes"""
        
        @self.app.route('/')
        def index():
            """Main page - HMI viewer"""
            return render_template('index.html')
        
        def get_hmi_screens():
            """Helper function to get HMI screens from project manager"""
            screens = []
            if self.project_manager:
                # Try to get screens from hmi_designer
                if hasattr(self.project_manager, 'hmi_designer') and self.project_manager.hmi_designer:
                    if hasattr(self.project_manager.hmi_designer, 'screens'):
                        screens = self.project_manager.hmi_designer.screens
                        print(f"Got {len(screens)} screens from hmi_designer")
                    else:
                        print("hmi_designer has no screens attribute")
                # Fallback to hmi_screens attribute
                elif hasattr(self.project_manager, 'hmi_screens'):
                    screens = self.project_manager.hmi_screens
                    print(f"Got {len(screens)} screens from project_manager.hmi_screens")
                # Fallback: load from project file directly
                elif hasattr(self.project_manager, 'project_file') and self.project_manager.project_file:
                    try:
                        import json
                        with open(self.project_manager.project_file, 'r', encoding='utf-8') as f:
                            project_data = json.load(f)
                        if 'screens' in project_data:
                            screens = self._parse_screens_from_project(project_data['screens'])
                            print(f"Got {len(screens)} screens from project file")
                    except Exception as e:
                        print(f"Error loading screens from project file: {e}")
                else:
                    print("No screens found in project_manager")
            else:
                print("No project_manager available")
            return screens
        
        @self.app.route('/api/screens')
        def get_screens():
            """Get list of HMI screens"""
            try:
                screens = []
                hmi_screens = get_hmi_screens()
                for screen in hmi_screens:
                    screens.append({
                        'name': screen.name,
                        'number': getattr(screen, 'number', 1),
                        'is_main': getattr(screen, 'is_main', False)
                    })
                return jsonify({'success': True, 'screens': screens})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/screens/<screen_name>')
        def get_screen_data(screen_name):
            """Get HMI screen data including objects"""
            try:
                hmi_screens = get_hmi_screens()
                if not hmi_screens:
                    return jsonify({'success': False, 'error': 'No screens available'})
                
                for screen in hmi_screens:
                    if screen.name == screen_name:
                        objects = []
                        print(f"Loading screen '{screen_name}' with {len(screen.objects)} objects")
                        for obj in screen.objects:
                            obj_vars = [{
                                'name': v.variable_name,
                                'type': v.variable_type,
                                'address': v.address,
                                'bit_offset': getattr(v, 'bit_offset', None)
                            } for v in obj.variables]
                            if obj_vars:
                                print(f"  Object '{obj.obj_type}' has variables: {[v['name'] for v in obj_vars]}")
                            obj_data = {
                                'type': obj.obj_type,
                                'x': obj.x,
                                'y': obj.y,
                                'width': obj.width,
                                'height': obj.height,
                                'properties': obj.properties,
                                'variables': obj_vars,
                                'visibility': getattr(obj, 'visibility', {})
                            }
                            objects.append(obj_data)
                        
                        return jsonify({
                            'success': True,
                            'screen': {
                                'name': screen.name,
                                'number': getattr(screen, 'number', 1),
                                'width': getattr(screen, 'resolution', {}).get('width', 1000),
                                'height': getattr(screen, 'resolution', {}).get('height', 600),
                                'background_color': getattr(screen, 'background_color', '#FFFFFF'),
                                'objects': objects
                            }
                        })
                
                return jsonify({'success': False, 'error': 'Screen not found'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/tags')
        def get_tags():
            """Get all tag values"""
            try:
                tags = []
                if self.data_manager and hasattr(self.data_manager, 'tags'):
                    for name, tag in self.data_manager.tags.items():
                        tags.append({
                            'name': tag.name,
                            'value': tag.value,
                            'quality': tag.quality,
                            'timestamp': tag.timestamp.isoformat() if tag.timestamp else None,
                            'data_type': tag.data_type.value if hasattr(tag.data_type, 'value') else str(tag.data_type)
                        })
                return jsonify({'success': True, 'tags': tags})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/tags/<tag_name>')
        def get_tag_value(tag_name):
            """Get single tag value"""
            try:
                if self.data_manager and hasattr(self.data_manager, 'tags'):
                    tag = self.data_manager.tags.get(tag_name)
                    if tag:
                        return jsonify({
                            'success': True,
                            'tag': {
                                'name': tag.name,
                                'value': tag.value,
                                'quality': tag.quality,
                                'timestamp': tag.timestamp.isoformat() if tag.timestamp else None
                            }
                        })
                return jsonify({'success': False, 'error': 'Tag not found'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/write_tag', methods=['POST'])
        def write_tag():
            """Write value to a tag"""
            try:
                data = request.json
                tag_name = data.get('tag_name')
                value = data.get('value')
                bit_offset = data.get('bit_offset')
                
                if not tag_name or value is None:
                    return jsonify({'success': False, 'error': 'Missing tag_name or value'})
                
                # Write to PLC through plc_manager
                if self.plc_manager:
                    success = self.plc_manager.write_tag(tag_name, value, bit_offset)
                    return jsonify({'success': success})
                
                return jsonify({'success': False, 'error': 'PLC manager not available'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/connections')
        def get_connections():
            """Get PLC connection status"""
            try:
                connections = []
                if self.plc_manager and hasattr(self.plc_manager, 'connections'):
                    for name, conn in self.plc_manager.connections.items():
                        connections.append({
                            'name': name,
                            'protocol': conn.protocol.value if hasattr(conn.protocol, 'value') else str(conn.protocol),
                            'address': conn.address,
                            'port': conn.port,
                            'connected': conn.connected
                        })
                return jsonify({'success': True, 'connections': connections})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
    
    def _setup_socket_events(self):
        """Setup WebSocket events"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Client connected"""
            print(f"Web client connected: {request.sid}")
            emit('connected', {'message': 'Connected to SCADA server'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Client disconnected"""
            print(f"Web client disconnected: {request.sid}")
        
        @self.socketio.on('subscribe_tags')
        def handle_subscribe_tags(data):
            """Client subscribes to tag updates"""
            tag_names = data.get('tags', [])
            print(f"Client subscribed to tags: {tag_names}")
            
            # Send current tag values immediately
            if self.data_manager and hasattr(self.data_manager, 'tags'):
                tags_data = {}
                for name, tag in self.data_manager.tags.items():
                    value = tag.value if tag.value is not None else 0
                    try:
                        json.dumps(value)
                    except:
                        value = str(value)
                    
                    tags_data[name] = {
                        'value': value,
                        'quality': tag.quality if tag.quality else 'Unknown',
                        'timestamp': tag.timestamp.isoformat() if tag.timestamp else None
                    }
                
                print(f"Sending initial tag data to client: {len(tags_data)} tags")
                emit('tags_update', tags_data)
            
            emit('subscribed', {'tags': tag_names})
        
        @self.socketio.on('write_tag')
        def handle_write_tag(data):
            """Write tag value from web client"""
            try:
                tag_name = data.get('tag_name')
                value = data.get('value')
                bit_offset = data.get('bit_offset')
                
                print(f"Web write_tag: {tag_name} = {value}, bit_offset={bit_offset}")
                
                if self.plc_manager:
                    success = self.plc_manager.write_tag(tag_name, value, bit_offset)
                    emit('write_result', {'tag_name': tag_name, 'success': success})
                else:
                    emit('write_result', {'tag_name': tag_name, 'success': False, 'error': 'PLC manager not available'})
            except Exception as e:
                emit('write_result', {'tag_name': tag_name, 'success': False, 'error': str(e)})
    
    def _broadcast_data(self):
        """Background thread to broadcast tag values"""
        first_broadcast = True
        while self.running:
            try:
                if self.data_manager and hasattr(self.data_manager, 'tags'):
                    # Collect all tag values
                    tags_data = {}
                    tag_count = 0
                    for name, tag in self.data_manager.tags.items():
                        # Handle None value - convert to 0 or keep as None
                        value = tag.value
                        if value is None:
                            value = 0  # Default to 0 for display
                        
                        # Ensure value is JSON serializable
                        try:
                            json.dumps(value)
                        except (TypeError, ValueError):
                            value = str(value)
                        
                        tags_data[name] = {
                            'value': value,
                            'quality': tag.quality if tag.quality else 'Unknown',
                            'timestamp': tag.timestamp.isoformat() if tag.timestamp else None
                        }
                        tag_count += 1
                    
                    # Debug output on first broadcast
                    if first_broadcast and tag_count > 0:
                        print(f"Broadcasting {tag_count} tags: {list(tags_data.keys())[:5]}...")
                        # Print first tag details
                        first_tag_name = list(tags_data.keys())[0]
                        first_tag = tags_data[first_tag_name]
                        print(f"First tag '{first_tag_name}': value={first_tag['value']}, quality={first_tag['quality']}")
                        first_broadcast = False
                    
                    # Broadcast to all connected clients
                    self.socketio.emit('tags_update', tags_data)
                
                # Sleep for 1 second
                time.sleep(1)
            except Exception as e:
                print(f"Broadcast error: {e}")
                time.sleep(1)
    
    def start(self):
        """Start the web server"""
        self.running = True
        
        # Find available port if default is in use
        available_port = find_available_port(self.port, self.port + 20)
        if available_port is None:
            print(f"Error: No available ports found between {self.port} and {self.port + 20}")
            return
        
        if available_port != self.port:
            print(f"Port {self.port} is in use, using port {available_port} instead")
            self.port = available_port
        
        # Start broadcast thread
        self.broadcast_thread = threading.Thread(target=self._broadcast_data)
        self.broadcast_thread.daemon = True
        self.broadcast_thread.start()
        
        # Start Flask-SocketIO server
        print(f"Starting SCADA Web Server on http://{self.host}:{self.port}")
        try:
            self.socketio.run(self.app, host=self.host, port=self.port, debug=False)
        except OSError as e:
            print(f"Error starting web server: {e}")
            self.running = False
    
    def stop(self):
        """Stop the web server"""
        self.running = False
        print("Web server stopped")


# Singleton instance
_web_server = None

def start_web_server(data_manager, plc_manager, project_manager, host='0.0.0.0', port=8080):
    """Start the web server singleton"""
    global _web_server
    if _web_server is None:
        _web_server = WebServer(data_manager, plc_manager, project_manager, host, port)
        _web_server.start()
    return _web_server

def stop_web_server():
    """Stop the web server singleton"""
    global _web_server
    if _web_server:
        _web_server.stop()
        _web_server = None
