"""
Configuration Manager for SCADA Application
Handles saving and loading of configuration data
"""
import json
import os
from datetime import datetime


class ConfigurationManager:
    def __init__(self, data_manager=None, plc_manager=None):
        self.data_manager = data_manager
        self.plc_manager = plc_manager
        self.config_file = None
        self.last_saved = None
        self.logging_rules = []  # Data logging rules
        self.storage_type = "sqlite"  # Global storage type: csv, sqlite, sqlserver
        self.poll_interval = 1000  # Data polling interval in milliseconds
        self.variable_groups = {}  # Variable groups: {group_name: [tag_names]}
        self.recent_variables = []  # Recently used variables for quick access
        
    def save_configuration(self, file_path=None):
        """Save the current configuration to a file"""
        if file_path is None:
            file_path = self.config_file or "scada_config.json"

        config_data = {
            "version": "1.3",
            "saved_at": datetime.now().isoformat(),
            "plc_connections": {},
            "variables": {},
            "hmi_objects": [],
            "logging_configs": [],
            "sql_server_config": {},
            "storage_type": self.storage_type,
            "poll_interval": self.poll_interval,
            "variable_groups": self.variable_groups,
            "recent_variables": self.recent_variables
        }

        # Save PLC connections
        if self.plc_manager:
            for name, conn in self.plc_manager.connections.items():
                conn_data = {
                    "name": conn.name,
                    "protocol": conn.protocol.value,
                    "address": conn.address,
                    "port": conn.port
                }
                # Add extra parameters if they exist
                if hasattr(conn, 'extra_params') and conn.extra_params:
                    conn_data.update(conn.extra_params)

                config_data["plc_connections"][name] = conn_data

        # Save variables/tags
        if self.data_manager:
            for name, tag in self.data_manager.tags.items():
                config_data["variables"][name] = {
                    "name": tag.name,
                    "tag_type": tag.tag_type.value,
                    "data_type": tag.data_type.value,
                    "address": tag.address,
                    "description": tag.description,
                    "plc_connection": tag.plc_connection,
                    "value": tag.value,
                    "timestamp": tag.timestamp.isoformat() if tag.timestamp else None
                }

        # Save logging configs with deduplication
        if hasattr(self, 'logging_rules') and self.logging_rules:
            unique_rules = []
            seen_tags = set()
            for rule in self.logging_rules:
                tag_name = rule.get('tag_name')
                if tag_name and tag_name not in seen_tags:
                    unique_rules.append(rule)
                    seen_tags.add(tag_name)
            config_data["logging_configs"] = unique_rules

        # Save SQL Server config
        try:
            from scada_app.core.sql_server_manager import sql_server_manager
            import base64
            encoded_password = base64.b64encode(sql_server_manager.password.encode()).decode() if sql_server_manager.password else ""
            config_data["sql_server_config"] = {
                "server": sql_server_manager.server,
                "database": sql_server_manager.database,
                "username": sql_server_manager.username,
                "password": encoded_password,
                "port": getattr(sql_server_manager, 'port', 1433)
            }
        except Exception as e:
            print(f"Error saving SQL Server config: {e}")

        # TODO: Save HMI objects when implemented

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            self.config_file = file_path
            self.last_saved = datetime.now()
            return True
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return False
    
    def load_configuration(self, file_path=None):
        """Load configuration from a file"""
        if file_path is None:
            file_path = self.config_file
        
        if not file_path or not os.path.exists(file_path):
            print(f"Configuration file does not exist: {file_path}")
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Load PLC connections
            if self.plc_manager and "plc_connections" in config_data:
                self.plc_manager.connections = {}
                for name, conn_data in config_data["plc_connections"].items():
                    from scada_app.comm.plc_manager import PLCConnection, PLCProtocol
                    protocol = PLCProtocol(conn_data["protocol"])
                    
                    # Extract extra parameters if they exist
                    extra_params = {}
                    if 'rack' in conn_data:
                        extra_params['rack'] = conn_data['rack']
                    if 'slot' in conn_data:
                        extra_params['slot'] = conn_data['slot']
                    
                    conn = PLCConnection(
                        name=conn_data["name"],
                        protocol=protocol,
                        address=conn_data["address"],
                        port=conn_data["port"],
                        extra_params=extra_params
                    )
                    # Don't restore connection state initially
                    conn.connected = False
                    self.plc_manager.add_connection(conn)
            
            # Load variables/tags
            if self.data_manager and "variables" in config_data:
                self.data_manager.tags = {}
                from scada_app.core.data_manager import Tag, TagType, DataType
                
                # Mapping for backward compatibility with old tag types
                tag_type_mapping = {
                    'INPUT': 'PLC',
                    'OUTPUT': 'PLC',
                    'MEMORY': 'INTERNAL',
                    'CALCULATED': 'INTERNAL'
                }
                
                for name, tag_data in config_data["variables"].items():
                    # Convert old tag types to new ones
                    old_tag_type = tag_data["tag_type"]
                    new_tag_type = tag_type_mapping.get(old_tag_type, old_tag_type)
                    
                    tag_type = TagType(new_tag_type)
                    data_type = DataType(tag_data["data_type"])
                    timestamp = None
                    if tag_data["timestamp"]:
                        from datetime import datetime
                        timestamp = datetime.fromisoformat(tag_data["timestamp"])
                    
                    tag = Tag(
                        name=tag_data["name"],
                        tag_type=tag_type,
                        data_type=data_type,
                        address=tag_data["address"],
                        description=tag_data["description"],
                        plc_connection=tag_data.get("plc_connection", "")
                    )
                    tag.value = tag_data["value"]
                    tag.timestamp = timestamp
                    self.data_manager.add_tag(tag)
            
            # Load logging configs with deduplication
            if "logging_configs" in config_data:
                unique_rules = []
                seen_tags = set()
                for rule in config_data["logging_configs"]:
                    tag_name = rule.get('tag_name')
                    if tag_name and tag_name not in seen_tags:
                        unique_rules.append(rule)
                        seen_tags.add(tag_name)
                self.logging_rules = unique_rules

            # Load storage type
            if "storage_type" in config_data:
                self.storage_type = config_data["storage_type"]
                try:
                    from scada_app.core.data_storage_manager import data_storage_manager
                    data_storage_manager.set_storage_type(self.storage_type)
                except Exception as e:
                    print(f"Error setting storage type: {e}")

            # Load poll interval
            if "poll_interval" in config_data:
                self.poll_interval = config_data["poll_interval"]

            # Load variable groups
            if "variable_groups" in config_data:
                self.variable_groups = config_data["variable_groups"]

            # Load recent variables
            if "recent_variables" in config_data:
                self.recent_variables = config_data["recent_variables"]

            # Load SQL Server config
            if "sql_server_config" in config_data:
                sql_config = config_data["sql_server_config"]
                try:
                    from scada_app.core.sql_server_manager import sql_server_manager
                    import base64
                    sql_server_manager.server = sql_config.get('server', 'localhost')
                    sql_server_manager.database = sql_config.get('database', 'HMI_DataLogging')
                    sql_server_manager.username = sql_config.get('username', 'sa')
                    sql_server_manager.port = sql_config.get('port', 1433)
                    # Decode password
                    encoded_password = sql_config.get('password', '')
                    if encoded_password:
                        try:
                            sql_server_manager.password = base64.b64decode(encoded_password.encode()).decode()
                        except:
                            sql_server_manager.password = ''
                    print(f"Loaded SQL Server config: {sql_server_manager.server}/{sql_server_manager.database}")
                except Exception as e:
                    print(f"Error loading SQL Server config: {e}")

            self.config_file = file_path
            return True
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return False

    def has_unsaved_changes(self):
        """Check if there are unsaved changes"""
        if self.last_saved is None:
            return self.config_file is not None  # New file that hasn't been saved
        
        # In a real implementation, you'd track changes more precisely
        # For now, we'll just say there are changes if last_saved is older than now
        return True  # Always report changes for simplicity