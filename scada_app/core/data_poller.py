"""
Data Poller - Synchronizes data between PLCs and DataManager

Optimized for on-demand polling: only polls active tags (HMI, Alarm, Log)
"""
import time
import threading
from threading import Thread, Event
from PyQt5.QtCore import QTimer
from datetime import datetime
from scada_app.architecture import DataType
from scada_app.comm.communication_coordinator import coordinator
from scada_app.core.tag_subscription_manager import tag_subscription_manager


class DataPoller:
    def __init__(self, data_manager, plc_manager):
        self.data_manager = data_manager
        self.plc_manager = plc_manager
        self.polling_active = False
        self.polling_thread = None
        self.stop_event = Event()
        self.poll_interval = 500  # milliseconds (reduced from 1000ms for faster reconnect)
        
        # Track active tags for on-demand polling
        self._active_tags: set = set()
        self._subscription_callback = None
        
        # Track recently written tags to prevent flickering
        self._recent_writes: dict = {}  # tag_name -> timestamp
        self._write_lock = threading.Lock()
        self._write_protect_duration = 0.2  # 200ms protection after write
        
        # Track read failures for each tag
        self._read_failures: dict = {}  # tag_name -> (first_failure_time, last_failure_time, failure_count)
        self._failure_lock = threading.Lock()
        self._failure_timeout = 10  # seconds - after this time, show error indicator
        self._error_indicator = "👿"  # Error indicator for failed reads
        
        # Register for subscription changes
        self._register_subscription_callback()
        
    def _register_subscription_callback(self):
        """Register callback for tag subscription changes"""
        def on_subscription_changed(active_tags):
            self._active_tags = active_tags
            print(f"DataPoller: Active tags changed, now polling {len(active_tags)} tags")
        
        self._subscription_callback = on_subscription_changed
        tag_subscription_manager.register_callback(on_subscription_changed)
        # Initialize with current active tags
        self._active_tags = tag_subscription_manager.get_active_tags()
        
    def unregister(self):
        """Unregister from subscription manager"""
        if self._subscription_callback:
            tag_subscription_manager.unregister_callback(self._subscription_callback)
    
    def mark_recent_write(self, tag_name: str):
        """Mark a tag as recently written to prevent polling from overwriting it"""
        with self._write_lock:
            self._recent_writes[tag_name] = time.time()
    
    def _is_recently_written(self, tag_name: str) -> bool:
        """Check if a tag was recently written (within protection duration)"""
        with self._write_lock:
            if tag_name in self._recent_writes:
                elapsed = time.time() - self._recent_writes[tag_name]
                if elapsed < self._write_protect_duration:
                    return True
                else:
                    # Remove expired entry
                    del self._recent_writes[tag_name]
            return False
    
    def _record_read_failure(self, tag_name: str):
        """Record a read failure for a tag"""
        with self._failure_lock:
            current_time = time.time()
            if tag_name in self._read_failures:
                first_time, last_time, count = self._read_failures[tag_name]
                self._read_failures[tag_name] = (first_time, current_time, count + 1)
            else:
                self._read_failures[tag_name] = (current_time, current_time, 1)
                print(f"[DataPoller] First read failure for tag: {tag_name}")
    
    def _record_read_success(self, tag_name: str):
        """Clear read failure record when read succeeds"""
        with self._failure_lock:
            if tag_name in self._read_failures:
                del self._read_failures[tag_name]
                print(f"[DataPoller] Read succeeded for tag: {tag_name}, cleared failure record")
    
    def _check_failure_timeout(self, tag_name: str) -> bool:
        """Check if a tag has been failing for longer than the timeout"""
        with self._failure_lock:
            if tag_name in self._read_failures:
                first_time, last_time, count = self._read_failures[tag_name]
                elapsed = time.time() - first_time
                if elapsed >= self._failure_timeout:
                    return True
            return False
    
    def _update_failed_tags(self):
        """Update tags that have been failing for too long with error indicator"""
        with self._failure_lock:
            current_time = time.time()
            for tag_name, (first_time, last_time, count) in list(self._read_failures.items()):
                elapsed = current_time - first_time
                if elapsed >= self._failure_timeout:
                    # Update the tag value with error indicator
                    if tag_name in self.data_manager.tags:
                        tag = self.data_manager.tags[tag_name]
                        if tag.value != self._error_indicator:
                            print(f"[DataPoller] Tag {tag_name} read failed for {elapsed:.1f}s, setting error indicator 👿")
                            self.data_manager.update_tag_value(tag_name, self._error_indicator, quality="BAD")
                    else:
                        print(f"[DataPoller] Tag {tag_name} not found in data_manager.tags")
                else:
                    # Debug: print progress towards timeout
                    if int(elapsed) % 2 == 0 and int(elapsed) > 0:  # Print every 2 seconds
                        print(f"[DataPoller] Tag {tag_name} read failed for {elapsed:.1f}s, will show 👿 in {self._failure_timeout - elapsed:.1f}s")
        
    def start_polling(self):
        """Start the polling thread"""
        if not self.polling_active:
            self.stop_event.clear()
            self.polling_thread = Thread(target=self._poll_loop, daemon=True)
            self.polling_active = True
            self.polling_thread.start()
            
    def stop_polling(self):
        """Stop the polling thread"""
        self.polling_active = False
        self.stop_event.set()
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=2)  # Wait up to 2 seconds for thread to finish
            
    def _poll_loop(self):
        """Main polling loop running in separate thread"""
        while self.polling_active and not self.stop_event.is_set():
            try:
                # Check if there are active writes, and wait for them to complete if needed
                coordinator.wait_for_write_completion(timeout=0.1)  # Wait up to 100ms for writes to complete
                
                # Only poll if no active writes
                if coordinator.can_poll():
                    # Mark polling as started
                    coordinator.start_polling()
                    try:
                        self._poll_plc_data()
                    finally:
                        # Mark polling as ended
                        coordinator.end_polling()
                
                # Wait for the specified interval or stop event
                if self.stop_event.wait(timeout=self.poll_interval / 1000.0):
                    break  # Stop event was set, exit loop
            except Exception as e:
                print(f"Error in polling loop: {str(e)}")
                # Still wait for the interval or stop event before continuing
                if self.stop_event.wait(timeout=self.poll_interval / 1000.0):
                    break
                    
    def _poll_plc_data(self):
        """Poll data from all connected PLCs and update DataManager using batch read
        
        On-demand polling: only polls active tags (HMI, Alarm, Log)
        """
        # Get active tags from subscription manager
        active_tags = self._active_tags if self._active_tags else set()
        
        # If no active tags, skip polling
        if not active_tags:
            return
        
        # Update tags that have been failing for too long
        self._update_failed_tags()
        
        # Group active tags by PLC connection for batch reading
        tags_by_plc = {}
        for tag_name in active_tags:
            if tag_name in self.data_manager.tags:
                tag = self.data_manager.tags[tag_name]
                if tag.plc_connection:
                    if tag.plc_connection not in tags_by_plc:
                        tags_by_plc[tag.plc_connection] = []
                    tags_by_plc[tag.plc_connection].append((tag_name, tag))
        
        # Batch read for each PLC connection
        for plc_name, tag_list in tags_by_plc.items():
            plc_conn = self.plc_manager.get_connection(plc_name)
            if not plc_conn or not plc_conn.connected:
                # PLC not connected, record failures for all tags
                for tag_name, tag in tag_list:
                    self._record_read_failure(tag_name)
                continue
            
            try:
                # Check if handler supports batch read
                if hasattr(plc_conn, 'handler') and plc_conn.handler and \
                   hasattr(plc_conn.handler, 'read_tags_batch'):
                    # Use batch read with data type information
                    # Build list of (address, data_type) tuples
                    address_type_list = []
                    seen_addresses = set()  # Track unique addresses to avoid duplicates
                    for _, tag in tag_list:
                        if tag.address:
                            # Address is already normalized to uppercase in Tag class
                            if tag.address not in seen_addresses:
                                seen_addresses.add(tag.address)
                                # Get data type from tag, default to REAL for DBD addresses
                                data_type = "REAL" if hasattr(tag, 'data_type') and tag.data_type and tag.data_type.name == "REAL" else "DWORD"
                                address_type_list.append((tag.address, data_type))
                    
                    if address_type_list:
                        results = plc_conn.handler.read_tags_batch(address_type_list)
                        # Update values in data manager
                        for tag_name, tag in tag_list:
                            # Skip recently written tags to prevent flickering
                            if self._is_recently_written(tag_name):
                                continue
                            if tag.address in results:
                                value = results[tag.address]
                                if value is not None:
                                    # Always update with full register value
                                    # DO NOT extract bit value here - Tag.value must store complete register value
                                    # Bit extraction is done at control level (in HMI controls)
                                    self.data_manager.update_tag_value(tag_name, value)
                                    # Clear failure record on successful read
                                    self._record_read_success(tag_name)
                                else:
                                    # Record failure when value is None
                                    self._record_read_failure(tag_name)
                            else:
                                # Record failure when address not in results
                                self._record_read_failure(tag_name)
                else:
                    # Fall back to individual reads
                    for tag_name, tag in tag_list:
                        # Skip recently written tags to prevent flickering
                        if self._is_recently_written(tag_name):
                            continue
                        try:
                            value = self._read_from_plc(plc_conn, tag)
                            if value is not None:
                                # Always update with full register value
                                # DO NOT extract bit value here - Tag.value must store complete register value
                                # Bit extraction is done at control level (in HMI controls)
                                self.data_manager.update_tag_value(tag_name, value)
                                # Clear failure record on successful read
                                self._record_read_success(tag_name)
                            else:
                                # Record failure when value is None
                                self._record_read_failure(tag_name)
                        except Exception as e:
                            plc_conn_name = getattr(plc_conn, 'name', 'Unknown')
                            print(f"Error reading tag {tag_name} from PLC {plc_conn_name}: {str(e)}")
                            # Record read failure
                            self._record_read_failure(tag_name)
                            
                            # Check if this is a connection error and attempt to reconnect
                            if "connection" in str(e).lower() or "timeout" in str(e).lower() or "reset" in str(e).lower():
                                print(f"Attempting to reconnect to {plc_conn_name}...")
                                try:
                                    if hasattr(plc_conn, 'connect'):
                                        # Force reconnection with cleanup
                                        if hasattr(plc_conn, 'disconnect'):
                                            plc_conn.disconnect()
                                        if plc_conn.connect(max_retries=3, retry_delay=1.0):
                                            print(f"Successfully reconnected to {plc_conn_name}")
                                        else:
                                            print(f"Failed to reconnect to {plc_conn_name}")
                                except Exception as reconnect_error:
                                    print(f"Error during reconnection to {plc_conn_name}: {reconnect_error}")
            except Exception as e:
                    print(f"Error in batch read from PLC {plc_name}: {str(e)}")
                    
                    # Check if this is a connection error and attempt to reconnect
                    if "connection" in str(e).lower() or "timeout" in str(e).lower() or "reset" in str(e).lower():
                        print(f"Attempting to reconnect to {plc_name}...")
                        try:
                            if hasattr(plc_conn, 'connect'):
                                # Force reconnection with cleanup
                                if hasattr(plc_conn, 'disconnect'):
                                    plc_conn.disconnect()
                                if plc_conn.connect(max_retries=3, retry_delay=1.0):
                                    print(f"Successfully reconnected to {plc_name}")
                                else:
                                    print(f"Failed to reconnect to {plc_name}")
                        except Exception as reconnect_error:
                            print(f"Error during reconnection to {plc_name}: {reconnect_error}")
                    
                    # Fall back to individual reads
                    for tag_name, tag in tag_list:
                        # Skip recently written tags to prevent flickering
                        if self._is_recently_written(tag_name):
                            continue
                        try:
                            value = self._read_from_plc(plc_conn, tag)
                            if value is not None:
                                self.data_manager.update_tag_value(tag_name, value)
                                # Clear failure record on successful read
                                self._record_read_success(tag_name)
                            else:
                                # Record failure when value is None
                                self._record_read_failure(tag_name)
                        except Exception as e2:
                            print(f"Error reading tag {tag_name}: {str(e2)}")
                            # Record read failure
                            self._record_read_failure(tag_name)
                            
                            # Check if this is a connection error and attempt to reconnect
                            if "connection" in str(e2).lower() or "timeout" in str(e2).lower() or "reset" in str(e2).lower():
                                print(f"Attempting to reconnect to {plc_name}...")
                                try:
                                    if hasattr(plc_conn, 'connect'):
                                        # Force reconnection with cleanup
                                        if hasattr(plc_conn, 'disconnect'):
                                            plc_conn.disconnect()
                                        if plc_conn.connect(max_retries=3, retry_delay=1.0):
                                            print(f"Successfully reconnected to {plc_name}")
                                        else:
                                            print(f"Failed to reconnect to {plc_name}")
                                except Exception as reconnect_error:
                                    print(f"Error during reconnection to {plc_name}: {reconnect_error}")
                        
    def _read_from_plc(self, plc_conn, tag):
        """Read a value from PLC based on tag configuration"""
        if not hasattr(tag, 'address') or not tag.address:
            return None
            
        try:
            # Parse address format - expecting something like "DB1.DBX0.0", "DB1.DBD10", "DB1.DBB10", etc.
            # Also support M addresses like "M0.5", "M10.0", etc.
            # Also support Modbus addresses like "40001", "00001", etc.
            # Also support lowercase versions like "db10010.dbd40"
            address_parts = tag.address.split('.')
            
            if len(address_parts) >= 1:
                first_part = address_parts[0].upper()  # e.g., "DB1", "M0", etc.
                
                # Check for Modbus addresses (40001, 30001, 10001, 00001 format)
                if first_part.isdigit() and len(first_part) == 5:
                    # Modbus address format
                    prefix = first_part[0]
                    offset = int(first_part[1:]) - 1  # Modbus addresses are 1-based
                    
                    if plc_conn.handler and hasattr(plc_conn.handler, 'read_tag'):
                        # Check if this is a float/real type that needs 2 registers
                        if hasattr(tag, 'data_type') and tag.data_type and tag.data_type.name in ['REAL', 'FLOAT']:
                            # Read as 32-bit float (2 registers)
                            if hasattr(plc_conn.handler, 'read_float'):
                                value = plc_conn.handler.read_float(tag.address)
                            else:
                                value = plc_conn.handler.read_tag(tag.address)
                        else:
                            value = plc_conn.handler.read_tag(tag.address)
                        
                        # Apply bit offset if specified (for accessing individual bits)
                        if value is not None and hasattr(tag, 'bit_offset') and tag.bit_offset is not None:
                            bit_pos = tag.bit_offset
                            if isinstance(value, int) and 0 <= bit_pos < 32:
                                return bool((value >> bit_pos) & 1)
                        
                        return value
                    return None
                
                # Check for M addresses (Merker/Memory addresses)
                if first_part.startswith('M'):
                    # Handle all M address formats: M0.5, MB0, MW0, MD0
                    try:
                        # Handle M<byte>.<bit> format (e.g., M0.5)
                        if len(address_parts) == 2:
                            # Format: M<byte>.<bit> e.g., M0.5
                            byte_part = first_part[1:]  # Remove 'M' prefix
                            start_byte = int(byte_part)
                            bit_offset = int(address_parts[1])
                            
                            if plc_conn.handler:
                                bool_value = plc_conn.handler.read_merkers_bit(start_byte, bit_offset)
                                return bool(bool_value)
                        else:
                            # Handle MB, MW, MD formats
                            if first_part.startswith('MB'):
                                # Format: MB<byte> e.g., MB0
                                byte_part = first_part[2:]  # Remove 'MB' prefix
                                start_byte = int(byte_part)
                                
                                if plc_conn.handler:
                                    return plc_conn.handler.read_merkers_byte(start_byte)
                            elif first_part.startswith('MW'):
                                # Format: MW<byte> e.g., MW0
                                byte_part = first_part[2:]  # Remove 'MW' prefix
                                start_byte = int(byte_part)
                                
                                if plc_conn.handler:
                                    return plc_conn.handler.read_merkers_int(start_byte)
                            elif first_part.startswith('MD'):
                                # Format: MD<byte> e.g., MD0
                                byte_part = first_part[2:]  # Remove 'MD' prefix
                                start_byte = int(byte_part)
                                
                                if plc_conn.handler:
                                    # For MD, we need to read 4 bytes and convert to float
                                    # This is a placeholder, actual implementation depends on handler
                                    return plc_conn.handler.read_merkers_int(start_byte)  # Temporary
                            else:
                                # Format: M<byte> without bit, treated as byte
                                byte_part = first_part[1:]  # Remove 'M' prefix
                                start_byte = int(byte_part)
                                
                                if plc_conn.handler:
                                    return plc_conn.handler.read_merkers_byte(start_byte)
                    except ValueError:
                        print(f"Invalid M address format: {tag.address}")
                        return None
                
                # Check for I (Input) addresses
                elif first_part.startswith('I'):
                    try:
                        if len(address_parts) == 2:
                            # Format: I<byte>.<bit> e.g., I0.0
                            byte_part = first_part[1:]  # Remove 'I' prefix
                            start_byte = int(byte_part)
                            bit_offset = int(address_parts[1])
                            
                            if plc_conn.handler:
                                data = plc_conn.handler.read_inputs(start_byte, 1)
                                return bool((data[0] >> bit_offset) & 1)
                        else:
                            # Format: IB, IW, ID
                            if first_part.startswith('IB'):
                                start_byte = int(first_part[2:])
                                if plc_conn.handler:
                                    data = plc_conn.handler.read_inputs(start_byte, 1)
                                    return data[0]
                            elif first_part.startswith('IW'):
                                start_byte = int(first_part[2:])
                                if plc_conn.handler:
                                    data = plc_conn.handler.read_inputs(start_byte, 2)
                                    return int.from_bytes(data, byteorder='big', signed=True)
                            elif first_part.startswith('ID'):
                                start_byte = int(first_part[2:])
                                if plc_conn.handler:
                                    data = plc_conn.handler.read_inputs(start_byte, 4)
                                    return int.from_bytes(data, byteorder='big', signed=True)
                            else:
                                # Just I<byte>
                                start_byte = int(first_part[1:])
                                if plc_conn.handler:
                                    data = plc_conn.handler.read_inputs(start_byte, 1)
                                    return data[0]
                    except ValueError:
                        print(f"Invalid I address format: {tag.address}")
                        return None
                
                # Check for Q (Output) addresses
                elif first_part.startswith('Q'):
                    try:
                        if len(address_parts) == 2:
                            # Format: Q<byte>.<bit> e.g., Q0.0
                            byte_part = first_part[1:]  # Remove 'Q' prefix
                            start_byte = int(byte_part)
                            bit_offset = int(address_parts[1])
                            
                            if plc_conn.handler:
                                data = plc_conn.handler.read_outputs(start_byte, 1)
                                return bool((data[0] >> bit_offset) & 1)
                        else:
                            # Format: QB, QW, QD
                            if first_part.startswith('QB'):
                                start_byte = int(first_part[2:])
                                if plc_conn.handler:
                                    data = plc_conn.handler.read_outputs(start_byte, 1)
                                    return data[0]
                            elif first_part.startswith('QW'):
                                start_byte = int(first_part[2:])
                                if plc_conn.handler:
                                    data = plc_conn.handler.read_outputs(start_byte, 2)
                                    return int.from_bytes(data, byteorder='big', signed=True)
                            elif first_part.startswith('QD'):
                                start_byte = int(first_part[2:])
                                if plc_conn.handler:
                                    data = plc_conn.handler.read_outputs(start_byte, 4)
                                    return int.from_bytes(data, byteorder='big', signed=True)
                            else:
                                # Just Q<byte>
                                start_byte = int(first_part[1:])
                                if plc_conn.handler:
                                    data = plc_conn.handler.read_outputs(start_byte, 1)
                                    return data[0]
                    except ValueError:
                        print(f"Invalid Q address format: {tag.address}")
                        return None
                
                elif len(address_parts) >= 2:
                    # Original DB address handling
                    db_part = first_part
                    addr_part = '.'.join(address_parts[1:]).upper()  # e.g., "DBX0.0" or "DBD10"
                    
                    # Extract DB number - handle various formats like DB1, DB10010, etc.
                    if db_part.startswith('DB'):
                        try:
                            db_number = int(db_part[2:])  # Extract number after 'DB'
                        except ValueError:
                            print(f"Invalid DB address format: {db_part}")
                            return None
                    else:
                        # If it doesn't start with DB, try to parse as just a number
                        try:
                            db_number = int(db_part)
                        except ValueError:
                            print(f"Invalid DB address format: {db_part}")
                            return None
                    
                    if addr_part.startswith('DBX'):  # Boolean/bit
                        # Format: DBX<byte>.<bit> e.g., DBX0.0
                        byte_bit_parts = addr_part.replace('DBX', '').split('.')
                        if len(byte_bit_parts) == 2:
                            start_byte = int(byte_bit_parts[0])
                            bit_offset = int(byte_bit_parts[1])
                            
                            if plc_conn.handler:
                                return plc_conn.handler.read_bool(db_number, start_byte, bit_offset)
                                
                    elif addr_part.startswith('DBB'):  # Byte
                        # Format: DBB<byte> e.g., DBB10
                        start_byte = int(addr_part.replace('DBB', ''))
                        
                        if plc_conn.handler:
                            raw_value = plc_conn.handler.client.db_read(db_number, start_byte, 1)
                            return raw_value[0]  # Return the byte value
                            
                    elif addr_part.startswith('DBW'):  # Word (16-bit integer)
                        # Format: DBW<start_byte> e.g., DBW10
                        start_byte = int(addr_part.replace('DBW', ''))
                        
                        if plc_conn.handler:
                            return plc_conn.handler.read_int(db_number, start_byte)
                            
                    elif addr_part.startswith('DBD'):  # DWord (32-bit integer/real)
                        # Format: DBD<start_byte> e.g., DBD10
                        start_byte = int(addr_part.replace('DBD', ''))
                        
                        if tag.data_type == DataType.REAL:
                            # Handle as REAL (float)
                            if plc_conn.handler:
                                return plc_conn.handler.read_real(db_number, start_byte)
                        else:
                            # Handle as DINT (32-bit integer)
                            if plc_conn.handler:
                                return plc_conn.handler.read_dword(db_number, start_byte)
                                
        except Exception as e:
            # Safe way to get tag name and address
            tag_name_safe = getattr(tag, 'name', 'Unknown Tag')
            tag_address_safe = getattr(tag, 'address', 'Unknown Address')
            print(f"Error parsing address {tag_address_safe} for tag {tag_name_safe}: {str(e)}")
            return None
            
        return None
        
    def set_poll_interval(self, interval_ms):
        """Set the polling interval in milliseconds"""
        self.poll_interval = interval_ms