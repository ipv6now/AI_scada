"""
OPC UA Protocol Handler for SCADA Application
"""
try:
    from opcua import Client
    import opcua.ua.uatypes as uatypes
    HAS_OPCUA = True
except ImportError:
    HAS_OPCUA = False
    print("Warning: python-opcua not installed. Install with 'pip install python-opcua'")


class OpcUaHandler:
    def __init__(self, endpoint_url="opc.tcp://localhost:4840", timeout=3):
        if not HAS_OPCUA:
            raise ImportError("python-opcua is required for OPC UA communication")
        
        self.endpoint_url = endpoint_url
        self.timeout = timeout
        self.client = None
        self.connected = False
        
    def connect(self):
        """Connect to OPC UA server"""
        try:
            self.client = Client(self.endpoint_url)
            self.client.session_timeout = self.timeout * 1000  # Convert to ms
            self.client.connect()
            self.connected = True
            return True
        except Exception as e:
            print(f"OPC UA connection error: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from OPC UA server"""
        if self.client:
            self.client.disconnect()
            self.connected = False
            
    def read_node(self, node_id):
        """Read a value from an OPC UA node"""
        if not self.connected:
            raise ConnectionError("Not connected to OPC UA server")
            
        try:
            node = self.client.get_node(node_id)
            value = node.get_value()
            return value
        except Exception as e:
            print(f"Error reading node {node_id}: {e}")
            return None
            
    def write_node(self, node_id, value):
        """Write a value to an OPC UA node"""
        if not self.connected:
            raise ConnectionError("Not connected to OPC UA server")
            
        try:
            node = self.client.get_node(node_id)
            node.set_value(value)
            return True
        except Exception as e:
            print(f"Error writing to node {node_id}: {e}")
            return False
            
    def browse_nodes(self, parent_node_id="ns=0;i=84"):
        """Browse child nodes of a given parent node"""
        if not self.connected:
            raise ConnectionError("Not connected to OPC UA server")
            
        try:
            parent_node = self.client.get_node(parent_node_id)
            children = parent_node.get_children()
            return [(child.nodeid.to_string(), child.get_browse_name().Name) for child in children]
        except Exception as e:
            print(f"Error browsing nodes under {parent_node_id}: {e}")
            return []
            
    def get_node_attributes(self, node_id):
        """Get attributes of a specific node"""
        if not self.connected:
            raise ConnectionError("Not connected to OPC UA server")
            
        try:
            node = self.client.get_node(node_id)
            attributes = {
                'display_name': node.get_display_name().Text,
                'data_type': str(node.get_data_type_as_variant_type()),
                'value': node.get_value(),
                'access_level': node.get_access_level(),
                'description': node.get_description().Text
            }
            return attributes
        except Exception as e:
            print(f"Error getting attributes for node {node_id}: {e}")
            return None

    def read_tag(self, tag_name):
        """Read a tag value (compatible with PLC manager interface)"""
        return self.read_node(tag_name)
    
    def write_tag(self, tag_name, value, bit_offset=None):
        """Write a tag value (compatible with PLC manager interface)"""
        return self.write_node(tag_name, value)


def create_opcua_handler(params):
    """Create an OPC UA handler from parameters (compatible with PLC manager)"""
    address = params.get('address', 'localhost')
    port = params.get('port', 4840)
    endpoint_url = f"opc.tcp://{address}:{port}"
    timeout = params.get('timeout', 3)
    return OpcUaHandler(endpoint_url, timeout)