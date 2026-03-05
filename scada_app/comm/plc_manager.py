"""
PLC Manager - Handles PLC connections and communications
"""
from enum import Enum
import asyncio
import threading
from typing import Optional, Union, Any
from concurrent.futures import ThreadPoolExecutor
import time
from datetime import datetime

# Global write rate limiter - shared across all PLC connections
_global_write_limiter = None
_global_write_limiter_lock = threading.Lock()


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


# 异步包装函数
def _async_plc_read_sync(handler, tag_name: str) -> Optional[Any]:
    """同步读取函数（用于在线程池中执行）"""
    return handler.read_tag(tag_name)


def _async_plc_write_sync(handler, tag_name: str, value: Any, bit_offset: Optional[int]) -> bool:
    """同步写入函数（用于在线程池中执行）"""
    return handler.write_tag(tag_name, value, bit_offset)


# 异步方法
async def async_plc_read(handler, tag_name: str) -> Optional[Any]:
    """
    异步读取 PLC 标签值
    
    Args:
        handler: PLC handler 实例
        tag_name: 标签名
        
    Returns:
        标签值或 None
    """
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    result = await loop.run_in_executor(executor, _async_plc_read_sync, handler, tag_name)
    executor.shutdown(wait=False)
    return result


async def async_plc_write(handler, tag_name: str, value: Any, bit_offset: Optional[int] = None) -> bool:
    """
    异步写入 PLC 标签值
    
    Args:
        handler: PLC handler 实例
        tag_name: 标签名
        value: 要写入的值
        bit_offset: 位偏移（可选）
        
    Returns:
        True if successful, False otherwise
    """
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    result = await loop.run_in_executor(executor, _async_plc_write_sync, handler, tag_name, value, bit_offset)
    executor.shutdown(wait=False)
    return result


class PLCProtocol(Enum):
    MODBUS_TCP = "Modbus TCP"
    MODBUS_RTU = "Modbus RTU"
    OPC_UA = "OPC UA"
    SIEMENS_S7 = "Siemens S7"
    GENERIC = "Generic"
    SIMULATED = "Simulated"


class PLCConnection:
    def __init__(self, name, protocol, address, port=None, slave_id=1, extra_params=None, data_manager=None):
        self.name = name
        self.protocol = protocol
        self.address = address
        
        # Set default port based on protocol
        if port is None:
            if protocol == PLCProtocol.SIEMENS_S7:
                self.port = 102  # S7 default port
            else:
                self.port = 502  # Modbus default port
        else:
            self.port = port
            
        self.slave_id = slave_id
        self.extra_params = extra_params or {}
        self.connected = False
        self.tags = []
        self.handler = None  # Protocol-specific handler
        self.data_manager = data_manager  # Reference to data manager for read-after-write
        
        # Use global write rate limiter shared across all connections
        from .write_rate_limiter import WriteRateLimiter
        global _global_write_limiter
        
        with _global_write_limiter_lock:
            if _global_write_limiter is None:
                _global_write_limiter = WriteRateLimiter()
                _global_write_limiter.start()
                print(f"Global WriteRateLimiter initialized (min_interval={WriteRateLimiter.MIN_INTERVAL_MS}ms)")
        
        # Each connection should have its own WriteRateLimiter instance
        self._write_limiter = WriteRateLimiter()
        self._write_limiter.set_write_executor(self._execute_write)
        self._write_limiter.start()
        
    def connect(self, max_retries=1, retry_delay=0.5):
        """Connect to the PLC with error handling and retry mechanism
        
        Args:
            max_retries: Number of retry attempts (default 1 for faster startup)
            retry_delay: Delay between retries in seconds
        """
        import time
        
        # Global write rate limiter is already started during initialization
        # No need to restart it here
        
        # Disconnect existing handler if any (for reconnection)
        if self.handler:
            try:
                if hasattr(self.handler, 'disconnect'):
                    self.handler.disconnect()
                elif hasattr(self.handler, '_cleanup'):
                    self.handler._cleanup()
            except Exception as e:
                print(f"Error disconnecting existing handler for {self.name}: {e}")
            self.connected = False
        
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
                        # Exponential backoff: 1s, 2s, 4s, etc.
                        delay = retry_delay * (2 ** (retries - 1))
                        print(f"Connection failed, retrying {retries}/{max_retries} in {delay}s...")
                        time.sleep(delay)
            except Exception as e:
                print(f"Error connecting to {self.name}: {str(e)}")
                retries += 1
                if retries < max_retries:
                    # Exponential backoff: 1s, 2s, 4s, etc.
                    delay = retry_delay * (2 ** (retries - 1))
                    print(f"Retrying {retries}/{max_retries} in {delay}s...")
                    time.sleep(delay)
        
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
    
    def _show_write_error(self, tag_name, value, error_msg):
        """Show write error message to user"""
        # You can implement UI notification here
        # For example, using QMessageBox or custom notification system
        try:
            # Try to show message box if running in GUI mode
            from PyQt5.QtWidgets import QMessageBox, QApplication
            from PyQt5.QtCore import QTimer
            
            # Check if there's an active QApplication instance
            app = QApplication.instance()
            if app is None:
                return
            
            # Try to get the main window to update status bar
            main_window = None
            for widget in app.topLevelWidgets():
                if hasattr(widget, 'status_bar') and hasattr(widget, 'showMessage'):
                    main_window = widget
                    break
            
            # Update status bar with error message
            if main_window:
                status_msg = f"写入错误: {tag_name} = {value} ({error_msg})"
                main_window.status_bar.showMessage(status_msg, 5000)  # Show for 5 seconds
            
            def show_error_dialog():
                try:
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Warning)
                    msg.setWindowTitle("写入错误")
                    msg.setText(f"写入操作失败")
                    msg.setInformativeText(f"标签: {tag_name}\n值: {value}\n错误: {error_msg}")
                    msg.setStandardButtons(QMessageBox.Ok)
                    msg.exec_()
                except Exception:
                    pass
            
            # Use QTimer to show message box in main thread
            QTimer.singleShot(0, show_error_dialog)
            
        except Exception:
            pass
    
    def read_tag(self, tag_name):
        """Read a tag value from the PLC with error handling and auto-reconnect"""
        try:
            if not self.connected:
                current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{current_time}] PLC {self.name} not connected, attempting to reconnect...")
                # Use faster reconnect with fewer retries to prevent UI blocking
                if not self.connect(max_retries=1, retry_delay=0.2):
                    return None
            
            # Convert tag name to address for Modbus
            read_address = self._get_tag_address(tag_name)
                
            if self.protocol == PLCProtocol.SIMULATED and self.handler:
                return self.handler.read_tag(tag_name)
            elif self.handler and hasattr(self.handler, 'read_tag'):
                result = self.handler.read_tag(read_address)
                # If read failed (returned None), mark as disconnected and try to reconnect
                if result is None:
                    self.connected = False
                    # Use faster reconnect with fewer retries to prevent UI blocking
                    if self.connect(max_retries=1, retry_delay=0.2):
                        # Retry read after reconnection
                        if self.handler and hasattr(self.handler, 'read_tag'):
                            return self.handler.read_tag(read_address)
                return result
            # Placeholder implementation for other protocols
            return 0
        except Exception:
            # Mark as disconnected on error
            self.connected = False
            # Try to reconnect
            # Use faster reconnect with fewer retries to prevent UI blocking
            if self.connect(max_retries=1, retry_delay=0.2):
                # Retry read after reconnection
                try:
                    if self.handler and hasattr(self.handler, 'read_tag'):
                        return self.handler.read_tag(read_address)
                except Exception:
                    pass
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
        from datetime import datetime
        
        # Get bit_offset from pending write or tag configuration
        pending_bit_offset = getattr(self, '_pending_bit_offset', None)
        
        def do_write():
            # Create local copies of variables that might be modified
            local_write_address = tag_name
            local_bit_offset = pending_bit_offset
            local_value = value
            
            try:
                if not self.connected:
                    if not self.connect(max_retries=2, retry_delay=0.5):
                        # Show error message for connection failure
                        self._show_write_error(tag_name, local_value, f"Failed to connect to {self.name}")
                        return True  # Discard write but don't block
                
                # Get the actual address for all protocols
                local_write_address = tag_name
                local_bit_offset = pending_bit_offset  # Use bit_offset from parameter first
                
                # For all protocols, try to get address from tag configuration
                if self.data_manager and hasattr(self.data_manager, 'tags'):
                    tag = self.data_manager.tags.get(tag_name)
                    if tag and hasattr(tag, 'address') and tag.address:
                        local_write_address = tag.address
                        # Only use tag's bit_offset if not provided as parameter
                        if local_bit_offset is None:
                            local_bit_offset = getattr(tag, 'bit_offset', None)
                        
                        # Check if this is a word address with bit offset - convert to bit address for S7
                        if (self.protocol == PLCProtocol.SIEMENS_S7 and 
                            local_bit_offset is not None and 
                            local_bit_offset >= 0 and 
                            local_write_address.startswith(('MW', 'DBW', 'IW', 'QW'))):
                            # For word addresses with bit offset, we need to read-modify-write the entire word
                            # to avoid data inconsistency when the tag only monitors the word address
                            try:
                                # Read the current value of the word
                                current_value = self.read_tag(tag_name)
                                if current_value is None:
                                    # Show error message for read failure
                                    self._show_write_error(tag_name, local_value, "Failed to read current value for read-modify-write")
                                    return True  # Discard write but don't block
                                
                                # Convert to integer for bit manipulation
                                if isinstance(current_value, bool):
                                    int_value = 1 if current_value else 0
                                else:
                                    int_value = int(current_value)
                                
                                # Modify the specific bit
                                if local_value:
                                    # Set the bit
                                    new_value = int_value | (1 << local_bit_offset)
                                else:
                                    # Clear the bit
                                    new_value = int_value & ~(1 << local_bit_offset)
                                
                                # Write the modified value back to the word address
                                local_write_address = tag.address  # Use original word address
                                local_value = new_value  # Use modified value
                                local_bit_offset = None  # Clear bit_offset since we're writing the whole word
                                
                            except Exception as e:
                                # Show error message for read-modify-write exception
                                self._show_write_error(tag_name, local_value, f"Read-modify-write error: {e}")
                                return True  # Discard write but don't block
                    elif tag:
                        pass  # Tag has no address, using tag name
                    else:
                        pass  # Tag not found, using tag name as address
                else:
                    pass  # No data_manager available
                
                if self.protocol == PLCProtocol.SIMULATED and self.handler:
                    result = self.handler.write_tag(tag_name, value)
                    if result:
                        self._read_after_write(tag_name)
                    return result
                elif self.handler and hasattr(self.handler, 'write_tag'):
                    
                    # Try to write with bit_offset if provided
                    try:
                        if local_bit_offset is not None:
                            result = self.handler.write_tag(local_write_address, local_value, bit_offset=local_bit_offset)
                        else:
                            result = self.handler.write_tag(local_write_address, local_value)
                        
                        if result:
                            # Write succeeded, read back the value
                            self._mark_recent_write(tag_name)
                            self._read_after_write(tag_name)
                            return True
                        else:
                            # Write failed, get error information and show error message
                            error_msg = "Unknown error"
                            if self.handler and hasattr(self.handler, 'last_error') and self.handler.last_error:
                                error_msg = self.handler.last_error
                            
                            current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                            print(f"[{current_time}] Write failed for {tag_name}: {error_msg}")
                            
                            # Show error message to user (you can implement UI notification here)
                            self._show_write_error(tag_name, local_value, error_msg)
                            
                            # Return True to discard the write but not block subsequent writes
                            return True
                            
                    except Exception as e:
                        # Exception during write, show error and discard
                        # Show error message to user
                        self._show_write_error(tag_name, local_value, str(e))
                        
                        # Return True to discard the write but not block subsequent writes
                        return True
                # Placeholder implementation for other protocols
                return True
            except Exception as e:
                # Check if this is a "Job pending" type error which indicates communication busy, not disconnection
                error_str = str(e).lower()
                if 'job pending' in error_str or 'cli' in error_str:
                    return False
                else:
                    # Mark as disconnected on real errors (not communication busy)
                    self.connected = False
                    # Try to reconnect
                    # Use faster reconnect with fewer retries to prevent UI blocking
                    if self.connect(max_retries=1, retry_delay=0.2):
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
                        except Exception:
                            pass
                    return False
        
        # Execute write through coordinator to ensure it waits for polling
        return coordinator.execute_write_operation(do_write)
    
    def _mark_recent_write(self, tag_name: str):
        """Mark a tag as recently written to prevent data polling from overwriting it"""
        # Get the data poller from data_manager if available
        if self.data_manager and hasattr(self.data_manager, 'data_poller') and self.data_manager.data_poller:
            try:
                self.data_manager.data_poller.mark_recent_write(tag_name)
                current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{current_time}] Marked {tag_name} as recently written")
            except Exception as e:
                current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{current_time}] Error marking recent write for {tag_name}: {e}")
    
    def _read_after_write(self, tag_name):
        """Read back the value after a successful write to verify and update data manager"""
        if not self.data_manager:
            return
        
        try:
            # Small delay to allow PLC to process the write (use shorter delay to prevent blocking)
            import time
            time.sleep(0.01)  # Reduced from 50ms to 10ms
            
            # Read the value back
            read_value = self.read_tag(tag_name)
            if read_value is not None:
                # Always update data manager with the full register value
                # DO NOT extract bit value here - Tag.value must store the complete register value
                # Bit extraction is done at the control level (in HMI controls)
                self.data_manager.update_tag_value(tag_name, read_value)
        except Exception:
            pass
    
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
        except Exception:
            pass
        finally:
            self.connected = False
        

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
        failed_connections = []
        
        for name, conn in self.connections.items():
            print(f"Attempting to connect to PLC: {name} at {conn.address}")
            if conn.connect(max_retries=3, retry_delay=1.0):
                self.active_connections.append(conn)
                print(f"Successfully connected to PLC: {name}")
            else:
                print(f"Failed to connect to PLC: {name}")
                failed_connections.append(conn)
        
        # Start background reconnection thread for failed connections
        if failed_connections:
            self._start_background_reconnect(failed_connections)
    
    def _start_background_reconnect(self, connections):
        """Start background thread to reconnect failed connections"""
        import threading
        import time
        
        def reconnect_worker():
            retry_count = 0
            max_retries = 60  # Try for up to 5 minutes (60 * 5s = 300s)
            
            while retry_count < max_retries and connections:
                time.sleep(5)  # Wait 5 seconds between reconnection attempts
                
                # Try to reconnect each failed connection
                for conn in list(connections):
                    if conn in self.active_connections:
                        # Already connected, remove from list
                        connections.remove(conn)
                        continue
                    
                    try:
                        print(f"[Background] Attempting to reconnect to PLC: {conn.name}")
                        if conn.connect(max_retries=1, retry_delay=0.5):
                            self.active_connections.append(conn)
                            connections.remove(conn)
                            print(f"[Background] Successfully reconnected to PLC: {conn.name}")
                        else:
                            print(f"[Background] Failed to reconnect to PLC: {conn.name}")
                    except Exception as e:
                        print(f"[Background] Error reconnecting to PLC {conn.name}: {e}")
                
                retry_count += 1
            
            if connections:
                print(f"[Background] Stopped reconnection attempts for: {[c.name for c in connections]}")
        
        # Start reconnection thread
        reconnect_thread = threading.Thread(target=reconnect_worker, daemon=True)
        reconnect_thread.start()
        print(f"[Background] Started reconnection thread for {[c.name for c in connections]}")
                
    def disconnect_all(self):
        """Disconnect from all PLCs"""
        for conn in self.active_connections:
            conn.disconnect()
        self.active_connections.clear()
        
        # Stop global write rate limiter
        global _global_write_limiter
        with _global_write_limiter_lock:
            if _global_write_limiter is not None:
                _global_write_limiter.stop()
                _global_write_limiter = None
                print("Global WriteRateLimiter stopped")
        
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
            # Get the tag's PLC connection from data manager
            target_connection = None
            if self.data_manager and hasattr(self.data_manager, 'tags'):
                tag = self.data_manager.tags.get(tag_name)
                if tag and hasattr(tag, 'plc_connection') and tag.plc_connection:
                    target_connection = tag.plc_connection
            
            # If we have a target connection, try to write to it first
            if target_connection and target_connection in self.connections:
                conn = self.connections[target_connection]
                try:
                    # Try to connect if not already connected
                    if hasattr(conn, 'connected') and not conn.connected:
                        if not conn.connect(max_retries=3, retry_delay=1.0):
                            # Show error message for connection failure
                            if hasattr(conn, '_show_write_error'):
                                conn._show_write_error(tag_name, value, f"Failed to connect to {target_connection}")
                            return True  # Discard write but return success to avoid blocking
                        else:
                            # Add to active connections
                            if conn not in self.active_connections:
                                self.active_connections.append(conn)
                    
                    # Try to write with bit_offset if provided
                    if bit_offset is not None and hasattr(conn, 'write_tag'):
                        result = conn.write_tag(tag_name, value, bit_offset)
                    else:
                        result = conn.write_tag(tag_name, value)
                    
                    # WriteRateLimiter returns True immediately when queued
                    if result:
                        return True
                    else:
                        # Show error message for write queue failure
                        if hasattr(conn, '_show_write_error'):
                            conn._show_write_error(tag_name, value, f"Failed to queue write to {target_connection}")
                        return True  # Discard write but return success to avoid blocking
                        
                except Exception as e:
                    current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{current_time}] PLCManager: Error writing to target connection {target_connection}: {e}")
                    return False
            
            # If no target connection or target connection failed, try all connections
            current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{current_time}] PLCManager: Trying all connections for {tag_name}")
            
            # Check if active_connections is empty
            if not self.active_connections:
                # Only log warning periodically to avoid spam
                if self._should_log_empty_warning():
                    current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{current_time}] PLCManager: No active connections, trying all connections...")
                    current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{current_time}] PLCManager: Available connections: {list(self.connections.keys())}")
                
                if not self.connections:
                    if self._should_log_empty_warning():
                        current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{current_time}] PLCManager: No connections configured!")
                    return False
                
                for conn_name, conn in self.connections.items():
                    try:
                        # Skip target connection if we already tried it
                        if target_connection and conn_name == target_connection:
                            continue
                            
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
                            current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                            print(f"[{current_time}] PLCManager: Successfully wrote {tag_name} = {value} to {conn_name}")
                            # Add to active connections
                            if conn not in self.active_connections:
                                self.active_connections.append(conn)
                            return True
                    except Exception as e:
                        current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{current_time}] PLCManager: Error writing to {conn_name}: {e}")
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
                        current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{current_time}] PLCManager: Error writing to {conn.name}: {e}")
                        continue
            
            return False
            
        except Exception as e:
            current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{current_time}] PLCManager: Error writing tag {tag_name}: {e}")
            return False
    
    def read_tag(self, tag_name):
        """Read a tag value from the appropriate PLC"""
        try:
            # Check if active_connections is empty
            if not self.active_connections:
                # Only log warning periodically to avoid spam
                if self._should_log_empty_warning():
                    current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{current_time}] PLCManager: No active connections, trying all connections...")
                
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
                                current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                                print(f"[{current_time}] PLCManager: Error reading from {conn_name}: {e}")
                            continue
            else:
                # Try to read from all active connections
                for conn in self.active_connections:
                    try:
                        value = conn.read_tag(tag_name)
                        if value is not None:
                            return value
                    except Exception as e:
                        current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{current_time}] PLCManager: Error reading from {conn.name}: {e}")
                        continue
            
            return None
            
        except Exception as e:
            current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{current_time}] PLCManager: Error reading tag {tag_name}: {e}")
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