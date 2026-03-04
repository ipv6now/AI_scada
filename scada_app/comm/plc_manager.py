"""
PLC Manager - Handles PLC connections and communications
"""
from enum import Enum


class SimulatedHandler:
    """Simulated PLC handler for testing without real PLC"""
    
    def __init__(self, data_manager=None):
        self.data_manager = data_manager
        self._tags = {}
    
    def read_tag(self, tag_name):
        """Read tag value from data manager or local cache"""
        if self.data_manager and hasattr(self.data_manager, 'get_tag_value'):
            return self.data_manager.get_tag_value(tag_name)
        return self._tags.get(tag_name, 0)
    
    def write_tag(self, tag_name, value):
        """Write tag value to data manager and local cache"""
        self._tags[tag_name] = value
        if self.data_manager and hasattr(self.data_manager, 'update_tag_value'):
            self.data_manager.update_tag_value(tag_name, value)
            print(f"SimulatedHandler: Wrote {tag_name} = {value}")
        return True
    
    def disconnect(self):
        """Disconnect (no-op for simulated)"""
        pass


class PLCProtocol(Enum):
    MODBUS_TCP = "Modbus TCP"
    MODBUS_RTU = "Modbus RTU"
    OPC_UA = "OPC UA"
    SIEMENS_S7 = "Siemens S7"
    GENERIC = "Generic"
    SIMULATED = "Simulated"


class PLCConnection:
    def __init__(self, name, protocol, address, port=502, slave_id=1, extra_params=None, data_manager=None):
        self.name = name
        self.protocol = protocol
        self.address = address
        self.port = port
        self.slave_id = slave_id
        self.extra_params = extra_params or {}
        self.connected = False
        self.tags = []
        self.handler = None  # Protocol-specific handler
        self.data_manager = data_manager  # Reference to data manager for read-after-write
        
        # Write rate limiter for this connection
        from .write_rate_limiter import WriteRateLimiter
        self._write_limiter = WriteRateLimiter(
            min_interval_ms=extra_params.get('write_min_interval_ms', 200),
            batch_window_ms=extra_params.get('write_batch_window_ms', 100)
        )
        self._write_limiter.set_write_executor(self._execute_write)
        self._write_limiter.start()
        
    def connect(self, max_retries=1, retry_delay=0.5):
        """Connect to the PLC with error handling and retry mechanism
        
        Args:
            max_retries: Number of retry attempts (default 1 for faster startup)
            retry_delay: Delay between retries in seconds
        """
        import time
        
        # Ensure write rate limiter is running
        if hasattr(self, '_write_limiter') and not self._write_limiter.is_processing():
            self._write_limiter.start()
            print(f"WriteRateLimiter restarted for {self.name}")
        
        retries = 0
        while retries < max_retries:
            try:
                if self.protocol == PLCProtocol.SIEMENS_S7:
                    # Import new S7 driver
                    from .s7_driver import S7Driver, S7ConnectionConfig
                    # Prepare connection configuration
                    config = S7ConnectionConfig(
                        ip_address=self.address,
                        rack=self.extra_params.get('rack', 0),
                        slot=self.extra_params.get('slot', 1),
                        port=self.port,
                        connection_name=self.name
                    )
                    self.handler = S7Driver(config)
                    self.connected = self.handler.connect()
                elif self.protocol in [PLCProtocol.MODBUS_TCP, PLCProtocol.MODBUS_RTU]:
                    # Import modbus handler
                    from .modbus_handler import create_modbus_handler
                    protocol_str = "tcp" if self.protocol == PLCProtocol.MODBUS_TCP else "rtu"
                    params = {
                        'address': self.address,
                        'port': self.port,
                        'protocol': protocol_str,
                        'slave_id': self.slave_id
                    }
                    # Add RTU serial parameters for Modbus RTU
                    if self.protocol == PLCProtocol.MODBUS_RTU:
                        params['baudrate'] = self.extra_params.get('baudrate', 9600)
                        params['databits'] = self.extra_params.get('databits', 8)
                        params['parity'] = self.extra_params.get('parity', 'N')
                        params['stopbits'] = self.extra_params.get('stopbits', 1)
                    self.handler = create_modbus_handler(params)
                    self.connected = self.handler.connect()
                elif self.protocol == PLCProtocol.OPC_UA:
                    # Import OPC-UA handler
                    from .opcua_handler import create_opcua_handler
                    params = {
                        'address': self.address,
                        'port': self.port
                    }
                    self.handler = create_opcua_handler(params)
                    self.connected = self.handler.connect()
                elif self.protocol == PLCProtocol.SIMULATED:
                    # Create simulated handler for testing
                    self.handler = SimulatedHandler(self.data_manager)
                    self.connected = True
                    print(f"Connected to simulated PLC: {self.name}")
                else:
                    # For generic protocol or unknown protocols
                    print(f"Connecting to {self.name} at {self.address}:{self.port}")
                    self.connected = True
                
                if self.connected:
                    return True
                else:
                    retries += 1
                    if retries < max_retries:
                        print(f"Connection failed, retrying {retries}/{max_retries}...")
                        time.sleep(retry_delay)
            except Exception as e:
                print(f"Error connecting to {self.name}: {str(e)}")
                retries += 1
                if retries < max_retries:
                    print(f"Retrying {retries}/{max_retries}...")
                    time.sleep(retry_delay)
        
        self.connected = False
        print(f"Failed to connect to {self.name} after {max_retries} attempts")
        return False
        
    def disconnect(self):
        """Disconnect from the PLC with error handling"""
        try:
            if self.handler and hasattr(self.handler, 'disconnect'):
                self.handler.disconnect()
        except Exception as e:
            print(f"Error disconnecting from {self.name}: {str(e)}")
        finally:
            self.connected = False
            print(f"Disconnected from {self.name}")
        
    def _get_tag_address(self, tag_name):
        """Convert tag name to address for Modbus protocols"""
        if self.protocol in [PLCProtocol.MODBUS_TCP, PLCProtocol.MODBUS_RTU]:
            if self.data_manager and hasattr(self.data_manager, 'tags'):
                tag = self.data_manager.tags.get(tag_name)
                if tag and hasattr(tag, 'address') and tag.address:
                    return tag.address
        return tag_name
    
    def read_tag(self, tag_name):
        """Read a tag value from the PLC with error handling and auto-reconnect"""
        try:
            if not self.connected:
                print(f"PLC {self.name} not connected, attempting to reconnect...")
                if not self.connect(max_retries=2, retry_delay=0.5):
                    return None
            
            # Convert tag name to address for Modbus
            read_address = self._get_tag_address(tag_name)
            if read_address != tag_name:
                print(f"PLCConnection.read_tag: Converted tag '{tag_name}' to address '{read_address}'")
                
            if self.protocol == PLCProtocol.SIMULATED and self.handler:
                return self.handler.read_tag(tag_name)
            elif self.handler and hasattr(self.handler, 'read_tag'):
                result = self.handler.read_tag(read_address)
                # If read failed (returned None), mark as disconnected and try to reconnect
                if result is None:
                    print(f"Read failed for {tag_name} (address: {read_address}), connection may be lost. Attempting to reconnect...")
                    self.connected = False
                    if self.connect(max_retries=2, retry_delay=0.5):
                        # Retry read after reconnection
                        if self.handler and hasattr(self.handler, 'read_tag'):
                            return self.handler.read_tag(read_address)
                return result
            # Placeholder implementation for other protocols
            return 0
        except Exception as e:
            print(f"Error reading tag {tag_name} from {self.name}: {str(e)}")
            # Mark as disconnected on error
            self.connected = False
            # Try to reconnect
            print(f"Attempting to reconnect to {self.name}...")
            if self.connect(max_retries=2, retry_delay=0.5):
                # Retry read after reconnection
                try:
                    if self.handler and hasattr(self.handler, 'read_tag'):
                        return self.handler.read_tag(read_address)
                except Exception as e2:
                    print(f"Error reading tag after reconnection: {str(e2)}")
            return None
    
    def write_tag(self, tag_name, value, bit_offset=None):
        """Write a value to a tag in the PLC with rate limiting and error handling
        
        Args:
            tag_name: Tag name to write
            value: Value to write
            bit_offset: Optional bit offset for register bit writing (0-15)
        """
        # Store bit_offset for use in _execute_write
        self._pending_bit_offset = bit_offset
        # Use write rate limiter to queue the write
        return self._write_limiter.queue_write(tag_name, value)
    
    def _execute_write(self, tag_name, value):
        """Actually execute the write (called by WriteRateLimiter)"""
        # Use communication coordinator to wait for polling to complete
        from .communication_coordinator import coordinator
        
        # Get bit_offset from pending write or tag configuration
        pending_bit_offset = getattr(self, '_pending_bit_offset', None)
        
        print(f"PLCConnection._execute_write: {tag_name} = {value}, bit_offset={pending_bit_offset}, protocol={self.protocol}, connected={self.connected}")
        
        def do_write():
            try:
                if not self.connected:
                    print(f"PLC {self.name} not connected, attempting to reconnect...")
                    if not self.connect(max_retries=2, retry_delay=0.5):
                        return False
                
                # Get the actual address for Modbus protocol
                write_address = tag_name
                bit_offset = pending_bit_offset  # Use bit_offset from parameter first
                if self.protocol in [PLCProtocol.MODBUS_TCP, PLCProtocol.MODBUS_RTU]:
                    # For Modbus, we need to convert tag name to address
                    if self.data_manager and hasattr(self.data_manager, 'tags'):
                        tag = self.data_manager.tags.get(tag_name)
                        if tag and hasattr(tag, 'address') and tag.address:
                            write_address = tag.address
                            # Only use tag's bit_offset if not provided as parameter
                            if bit_offset is None:
                                bit_offset = getattr(tag, 'bit_offset', None)
                            print(f"PLCConnection: Converted tag '{tag_name}' to address '{write_address}', bit_offset={bit_offset}")
                        elif tag:
                            print(f"PLCConnection: Warning - Tag '{tag_name}' has no address, using tag name")
                        else:
                            print(f"PLCConnection: Warning - Tag '{tag_name}' not found in data_manager, using tag name as address")
                    else:
                        print(f"PLCConnection: Warning - No data_manager available for tag '{tag_name}'")
                
                if self.protocol == PLCProtocol.SIMULATED and self.handler:
                    print(f"PLCConnection: Using SIMULATED handler for {tag_name}")
                    result = self.handler.write_tag(tag_name, value)
                    if result:
                        self._read_after_write(tag_name)
                    return result
                elif self.handler and hasattr(self.handler, 'write_tag'):
                    print(f"PLCConnection: Using handler.write_tag for {write_address} (original tag: {tag_name})")
                    # Pass bit_offset for Modbus register bit writing
                    if bit_offset is not None:
                        result = self.handler.write_tag(write_address, value, bit_offset=bit_offset)
                    else:
                        result = self.handler.write_tag(write_address, value)
                    # If write failed, determine if it's a connection issue or communication busy
                    if not result:
                        # Check if the handler has specific error information
                        # For S7 connections, we want to distinguish between "Job pending" and actual disconnections
                        if self.handler and hasattr(self.handler, 'last_error'):
                            last_error = self.handler.last_error
                            # If it's a job pending error, don't mark as disconnected, just return False
                            if last_error and ('job pending' in str(last_error).lower() or 'cli' in str(last_error).lower()):
                                print(f"Job pending for {tag_name}, not marking as disconnected (error: {last_error})")
                                return False
                        # For other failures, mark as disconnected and try to reconnect
                        print(f"Write failed for {tag_name}, connection may be lost. Attempting to reconnect...")
                        self.connected = False
                        if self.connect(max_retries=2, retry_delay=0.5):
                            # Retry write after reconnection
                            if self.handler and hasattr(self.handler, 'write_tag'):
                                if bit_offset is not None:
                                    result = self.handler.write_tag(write_address, value, bit_offset=bit_offset)
                                else:
                                    result = self.handler.write_tag(write_address, value)
                                if result:
                                    self._read_after_write(tag_name)
                                return result
                    else:
                        # Write succeeded, read back the value
                        self._read_after_write(tag_name)
                    return result
                # Placeholder implementation for other protocols
                print(f"Writing {value} to {tag_name}")
                return True
            except Exception as e:
                # Check if this is a "Job pending" type error which indicates communication busy, not disconnection
                error_str = str(e).lower()
                if 'job pending' in error_str or 'cli' in error_str:
                    print(f"Job pending error for {tag_name}, not marking as disconnected")
                    return False
                else:
                    print(f"Error writing tag {tag_name} to {self.name}: {str(e)}")
                    # Mark as disconnected on real errors (not communication busy)
                    self.connected = False
                    # Try to reconnect
                    print(f"Attempting to reconnect to {self.name}...")
                    if self.connect(max_retries=2, retry_delay=0.5):
                        # Retry write after reconnection
                        try:
                            if self.handler and hasattr(self.handler, 'write_tag'):
                                if bit_offset is not None:
                                    result = self.handler.write_tag(write_address, value, bit_offset=bit_offset)
                                else:
                                    result = self.handler.write_tag(write_address, value)
                                if result:
                                    self._read_after_write(tag_name)
                                return result
                        except Exception as e2:
                            print(f"Error writing tag after reconnection: {str(e2)}")
                    return False
        
        # Execute write through coordinator to ensure it waits for polling
        return coordinator.execute_write_operation(do_write)
    
    def _read_after_write(self, tag_name):
        """Read back the value after a successful write to verify and update data manager"""
        if not self.data_manager:
            return
        
        try:
            # Small delay to allow PLC to process the write
            import time
            time.sleep(0.05)  # 50ms delay
            
            # Read the value back
            read_value = self.read_tag(tag_name)
            if read_value is not None:
                # Update data manager with the read value
                self.data_manager.update_tag_value(tag_name, read_value)
                print(f"Read-after-write: {tag_name} = {read_value}")
        except Exception as e:
            print(f"Error reading back {tag_name} after write: {e}")
    
    def get_write_stats(self):
        """Get write rate limiter statistics"""
        return self._write_limiter.get_stats()
    
    def disconnect(self):
        """Disconnect from the PLC with error handling"""
        try:
            # Stop write rate limiter
            if hasattr(self, '_write_limiter'):
                self._write_limiter.stop()
            
            if self.handler and hasattr(self.handler, 'disconnect'):
                self.handler.disconnect()
        except Exception as e:
            print(f"Error disconnecting from {self.name}: {str(e)}")
        finally:
            self.connected = False
            print(f"Disconnected from {self.name}")
        

class PLCManager:
    def __init__(self, data_manager=None):
        self.connections = {}
        self.active_connections = []
        self.data_manager = data_manager  # Reference to data manager for read-after-write
        self._last_empty_warning_time = 0  # Track last warning time
        self._warning_interval = 10  # Minimum seconds between warnings
        self._connection_attempts = 0  # Track connection attempts
    
    def set_data_manager(self, data_manager):
        """Set the data manager reference"""
        self.data_manager = data_manager
        # Update existing connections
        for conn in self.connections.values():
            conn.data_manager = data_manager
        
    def add_connection(self, plc_conn):
        """Add a new PLC connection"""
        # Set data manager on the connection if available
        if self.data_manager:
            plc_conn.data_manager = self.data_manager
        self.connections[plc_conn.name] = plc_conn
        
    def remove_connection(self, name):
        """Remove a PLC connection"""
        if name in self.connections:
            del self.connections[name]
            
    def connect_all(self, async_mode=True):
        """Connect to all configured PLCs
        
        Args:
            async_mode: If True, connect in background thread without blocking
        """
        if async_mode:
            # Start connection in background thread
            import threading
            thread = threading.Thread(target=self._connect_all_sync, daemon=True)
            thread.start()
        else:
            # Synchronous connection (blocking)
            self._connect_all_sync()
    
    def _connect_all_sync(self):
        """Synchronous connection to all PLCs (internal use)"""
        self.active_connections.clear()
        for name, conn in self.connections.items():
            print(f"Attempting to connect to PLC: {name} at {conn.address}")
            if conn.connect():
                self.active_connections.append(conn)
                print(f"Successfully connected to PLC: {name}")
            else:
                print(f"Failed to connect to PLC: {name}")
                
    def disconnect_all(self):
        """Disconnect from all PLCs"""
        for conn in self.active_connections:
            conn.disconnect()
        self.active_connections.clear()
        
    def get_connection(self, name):
        """Get a specific connection by name"""
        try:
            return self.connections.get(name)
        except Exception as e:
            print(f"Error getting connection {name}: {str(e)}")
            return None
        
    def scan_tags(self, plc_name):
        """Scan for available tags in a PLC"""
        # Placeholder implementation
        return []
    
    def _should_log_empty_warning(self) -> bool:
        """Check if we should log the empty connections warning (throttle logging)"""
        import time
        current_time = time.time()
        if current_time - self._last_empty_warning_time >= self._warning_interval:
            self._last_empty_warning_time = current_time
            return True
        return False
    
    def write_tag(self, tag_name, value, bit_offset=None):
        """Write a tag value to the appropriate PLC
        
        Args:
            tag_name: Tag name to write
            value: Value to write
            bit_offset: Optional bit offset for register bit writing (0-15)
        """
        try:
            print(f"PLCManager.write_tag: {tag_name} = {value}, bit_offset={bit_offset}")
            
            # Check if active_connections is empty
            if not self.active_connections:
                # Only log warning periodically to avoid spam
                if self._should_log_empty_warning():
                    print(f"PLCManager: No active connections, trying all connections...")
                    print(f"PLCManager: Available connections: {list(self.connections.keys())}")
                
                if not self.connections:
                    if self._should_log_empty_warning():
                        print(f"PLCManager: No connections configured!")
                    return False
                
                for conn_name, conn in self.connections.items():
                    try:
                        # Try to connect if not already connected
                        if hasattr(conn, 'connected') and not conn.connected:
                            if not conn.connect(max_retries=1, retry_delay=0.5):
                                continue
                        
                        # Try to write with bit_offset if provided
                        if bit_offset is not None and hasattr(conn, 'write_tag'):
                            result = conn.write_tag(tag_name, value, bit_offset)
                        else:
                            result = conn.write_tag(tag_name, value)
                        if result:
                            print(f"PLCManager: Successfully wrote {tag_name} = {value} to {conn_name}")
                            # Add to active connections
                            if conn not in self.active_connections:
                                self.active_connections.append(conn)
                            return True
                    except Exception as e:
                        print(f"PLCManager: Error writing to {conn_name}: {e}")
                        continue
            else:
                # Try to write to all active connections
                for conn in self.active_connections:
                    try:
                        # Try to write with bit_offset if provided
                        if bit_offset is not None and hasattr(conn, 'write_tag'):
                            result = conn.write_tag(tag_name, value, bit_offset)
                        else:
                            result = conn.write_tag(tag_name, value)
                        if result:
                            return True
                    except Exception as e:
                        print(f"PLCManager: Error writing to {conn.name}: {e}")
                        continue
            
            return False
            
        except Exception as e:
            print(f"PLCManager: Error writing tag {tag_name}: {e}")
            return False
    
    def read_tag(self, tag_name):
        """Read a tag value from the appropriate PLC"""
        try:
            # Check if active_connections is empty
            if not self.active_connections:
                # Only log warning periodically to avoid spam
                if self._should_log_empty_warning():
                    print(f"PLCManager: No active connections, trying all connections...")
                
                # If no active connections, try all configured connections
                for conn_name, conn in self.connections.items():
                    if hasattr(conn, 'connected') and conn.connected:
                        try:
                            value = conn.read_tag(tag_name)
                            if value is not None:
                                # Add to active connections
                                if conn not in self.active_connections:
                                    self.active_connections.append(conn)
                                return value
                        except Exception as e:
                            if self._should_log_empty_warning():
                                print(f"PLCManager: Error reading from {conn_name}: {e}")
                            continue
            else:
                # Try to read from all active connections
                for conn in self.active_connections:
                    try:
                        value = conn.read_tag(tag_name)
                        if value is not None:
                            return value
                    except Exception as e:
                        print(f"PLCManager: Error reading from {conn.name}: {e}")
                        continue
            
            return None
            
        except Exception as e:
            print(f"PLCManager: Error reading tag {tag_name}: {e}")
            return None
    
    def read_tags_batch(self, tag_list):
        """
        批量读取多个变量值
        
        Args:
            tag_list: 变量地址列表
            
        Returns:
            Dict[str, Any]: 变量地址到值的字典
        """
        results = {}
        
        if not tag_list:
            return results
        
        try:
            # 找到第一个支持批量读取的连接
            batch_conn = None
            for conn in self.active_connections:
                if hasattr(conn, 'handler') and conn.handler:
                    if hasattr(conn.handler, 'read_tags_batch'):
                        batch_conn = conn
                        break
            
            # 如果没有找到，尝试所有连接
            if not batch_conn:
                for conn in self.connections.values():
                    if hasattr(conn, 'handler') and conn.handler:
                        if hasattr(conn.handler, 'read_tags_batch'):
                            batch_conn = conn
                            if conn not in self.active_connections:
                                self.active_connections.append(conn)
                            break
            
            # 如果找到支持批量读取的连接，使用批量读取
            if batch_conn:
                try:
                    batch_results = batch_conn.handler.read_tags_batch(tag_list)
                    results.update(batch_results)
                    return results
                except Exception as e:
                    print(f"PLCManager: Batch read failed, falling back to individual reads: {e}")
            
            # 回退到逐个读取
            for tag_address in tag_list:
                try:
                    value = self.read_tag(tag_address)
                    results[tag_address] = value
                except Exception as e2:
                    print(f"PLCManager: Error reading {tag_address}: {e2}")
                    results[tag_address] = None
            
            return results
            
        except Exception as e:
            print(f"PLCManager: Error in batch read: {e}")
            # 如果批量读取失败，回退到逐个读取
            for tag_address in tag_list:
                try:
                    results[tag_address] = self.read_tag(tag_address)
                except Exception as e2:
                    print(f"PLCManager: Error reading {tag_address}: {e2}")
                    results[tag_address] = None
            return results