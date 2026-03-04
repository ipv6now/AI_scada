"""
Siemens S7 Protocol Driver
A modern, robust S7 PLC communication driver with comprehensive features

Features:
- Connection management with auto-reconnection
- Support for all S7 areas: DB, M, I, Q, T, C
- Batch read/write optimization
- Data type conversion
- Error handling and logging
- Thread-safe operations
"""

import snap7
import struct
import time
import threading
import logging
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Callable, Any, Tuple
from collections import defaultdict
from queue import Queue, Empty

# Import snap7 Area type for compatibility
try:
    from snap7.type import Area as Snap7Area
except ImportError:
    try:
        from snap7.types import Areas as Snap7Area
    except ImportError:
        # Fallback for older snap7 versions
        class Snap7Area:
            PE = 0x81
            PA = 0x82
            MK = 0x83
            DB = 0x84
            CT = 0x1C
            TM = 0x1D


# S7 Area constants (mapped to snap7 Area)
class S7Area(IntEnum):
    PE = 0x81  # Process Inputs (I)
    PA = 0x82  # Process Outputs (Q)
    MK = 0x83  # Merkers/Memory (M)
    DB = 0x84  # Data Block
    CT = 0x1C  # Counters
    TM = 0x1D  # Timers


def get_snap7_area(s7_area: S7Area):
    """Convert S7Area to snap7 Area enum"""
    area_map = {
        S7Area.PE: Snap7Area.PE,
        S7Area.PA: Snap7Area.PA,
        S7Area.MK: Snap7Area.MK,
        S7Area.DB: Snap7Area.DB,
        S7Area.CT: Snap7Area.CT,
        S7Area.TM: Snap7Area.TM,
    }
    return area_map.get(s7_area, Snap7Area.DB)


# S7 Word length constants
class S7WordLength(IntEnum):
    Bit = 0x01
    Byte = 0x02
    Word = 0x04
    DWord = 0x06
    Real = 0x08
    LReal = 0x0C


@dataclass
class S7Tag:
    """S7 Tag/Variable definition"""
    name: str
    area: S7Area
    db_number: int
    byte_offset: int
    bit_offset: int = 0
    data_type: str = "BOOL"  # BOOL, BYTE, WORD, DWORD, INT, DINT, REAL, LREAL
    size: int = 1
    
    def __post_init__(self):
        # Calculate size based on data type
        type_sizes = {
            "BOOL": 1,
            "BYTE": 1,
            "WORD": 2,
            "DWORD": 4,
            "INT": 2,
            "DINT": 4,
            "REAL": 4,
            "LREAL": 8,
        }
        self.size = type_sizes.get(self.data_type, 1)


@dataclass
class S7ConnectionConfig:
    """S7 Connection configuration"""
    ip_address: str
    rack: int = 0
    slot: int = 1
    port: int = 102
    timeout: int = 5000
    retry_interval: float = 5.0
    max_retries: int = 3
    auto_reconnect: bool = True
    connection_name: str = "S7_Connection"


class S7Error(Exception):
    """S7 Driver specific exception"""
    pass


class S7ConnectionError(S7Error):
    """Connection related errors"""
    pass


class S7ReadError(S7Error):
    """Read operation errors"""
    pass


class S7WriteError(S7Error):
    """Write operation errors"""
    pass


class S7Connection:
    """
    S7 Connection Manager
    Handles connection lifecycle, auto-reconnection, and error recovery
    """
    
    def __init__(self, config: S7ConnectionConfig):
        self.config = config
        self._client: Optional[snap7.client.Client] = None
        self._connected = False
        self._lock = threading.RLock()
        self._connection_time: Optional[float] = None
        self._retry_count = 0
        self._logger = logging.getLogger(f"S7Connection.{config.connection_name}")
        self._stop_reconnect = threading.Event()
        self._reconnect_thread: Optional[threading.Thread] = None
        
    @property
    def is_connected(self) -> bool:
        """Check if connection is active"""
        with self._lock:
            if self._client and self._connected:
                try:
                    return self._client.get_connected()
                except:
                    self._connected = False
                    return False
            return False
    
    @property
    def connection_time(self) -> Optional[float]:
        """Get connection timestamp"""
        return self._connection_time
    
    def connect(self) -> bool:
        """
        Establish connection to S7 PLC
        
        Returns:
            bool: True if connection successful
        """
        with self._lock:
            if self._connected and self.is_connected:
                self._logger.debug("Already connected")
                return True
            
            try:
                self._logger.info(f"Connecting to {self.config.ip_address}:{self.config.port}")
                
                # Create new client
                self._client = snap7.client.Client()
                
                # Connect to PLC
                self._client.connect(
                    self.config.ip_address,
                    self.config.rack,
                    self.config.slot,
                    self.config.port
                )
                
                # Verify connection
                if self._client.get_connected():
                    self._connected = True
                    self._connection_time = time.time()
                    self._retry_count = 0
                    self._logger.info("Connection established successfully")
                    return True
                else:
                    raise S7ConnectionError("Connection verification failed")
                    
            except Exception as e:
                self._logger.error(f"Connection failed: {e}")
                self._cleanup()
                return False
    
    def disconnect(self) -> None:
        """Disconnect from PLC and cleanup resources"""
        with self._lock:
            self._stop_reconnect.set()
            self._cleanup()
            self._logger.info("Disconnected")
    
    def _cleanup(self) -> None:
        """Internal cleanup method"""
        self._connected = False
        self._connection_time = None
        if self._client:
            try:
                self._client.disconnect()
            except:
                pass
            try:
                self._client.destroy()
            except:
                pass
            self._client = None
    
    def reconnect(self) -> bool:
        """
        Attempt to reconnect to PLC
        
        Returns:
            bool: True if reconnection successful
        """
        self._logger.info("Initiating reconnection...")
        self.disconnect()
        time.sleep(self.config.retry_interval)
        return self.connect()
    
    def auto_reconnect(self) -> None:
        """Start auto-reconnection in background thread"""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return
            
        self._stop_reconnect.clear()
        self._reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self._reconnect_thread.start()
    
    def _reconnect_loop(self) -> None:
        """Background reconnection loop"""
        while not self._stop_reconnect.is_set():
            if not self.is_connected:
                if self._retry_count < self.config.max_retries:
                    self._retry_count += 1
                    self._logger.info(f"Auto-reconnect attempt {self._retry_count}")
                    if self.connect():
                        break
                else:
                    self._logger.error("Max reconnection attempts reached")
                    break
            time.sleep(self.config.retry_interval)
    
    def execute_with_retry(self, operation: Callable, *args, **kwargs) -> Any:
        """
        Execute operation with automatic retry on failure
        
        Args:
            operation: Callable operation to execute
            *args, **kwargs: Arguments for operation
            
        Returns:
            Operation result
            
        Raises:
            S7Error: If operation fails after retries
        """
        max_attempts = self.config.max_retries + 1
        
        for attempt in range(max_attempts):
            try:
                if not self.is_connected:
                    if not self.connect():
                        raise S7ConnectionError("Not connected to PLC")
                
                return operation(*args, **kwargs)
                
            except Exception as e:
                error_str = str(e).lower()
                is_job_pending = 'job pending' in error_str or 'cli' in error_str
                
                if is_job_pending:
                    self._logger.warning(f"Job pending (attempt {attempt + 1}), waiting...")
                else:
                    self._logger.warning(f"Operation failed (attempt {attempt + 1}): {e}")
                
                if attempt < max_attempts - 1:
                    if not self.is_connected:
                        self.reconnect()
                    # Use shorter retry interval for job pending errors
                    retry_delay = 0.1 if is_job_pending else self.config.retry_interval
                    time.sleep(retry_delay)
                else:
                    raise S7Error(f"Operation failed after {max_attempts} attempts: {e}")
    
    def get_client(self) -> snap7.client.Client:
        """Get snap7 client instance"""
        with self._lock:
            if not self._client or not self.is_connected:
                raise S7ConnectionError("Not connected to PLC")
            return self._client


class S7DataConverter:
    """
    S7 Data Type Converter
    Handles conversion between Python types and S7 data formats
    """
    
    @staticmethod
    def to_bool(data: bytes, byte_index: int = 0, bit_index: int = 0) -> bool:
        """Convert byte to boolean value"""
        if byte_index >= len(data):
            raise S7ReadError(f"Byte index {byte_index} out of range")
        return bool(data[byte_index] & (1 << bit_index))
    
    @staticmethod
    def to_byte(data: bytes, index: int = 0) -> int:
        """Convert to byte value"""
        if index >= len(data):
            raise S7ReadError(f"Index {index} out of range")
        return data[index]
    
    @staticmethod
    def to_word(data: bytes, index: int = 0) -> int:
        """Convert to 16-bit unsigned integer (WORD)"""
        if index + 2 > len(data):
            raise S7ReadError(f"Not enough data for WORD at index {index}")
        return struct.unpack('>H', data[index:index+2])[0]
    
    @staticmethod
    def to_dword(data: bytes, index: int = 0) -> int:
        """Convert to 32-bit unsigned integer (DWORD)"""
        if index + 4 > len(data):
            raise S7ReadError(f"Not enough data for DWORD at index {index}")
        return struct.unpack('>I', data[index:index+4])[0]
    
    @staticmethod
    def to_int(data: bytes, index: int = 0) -> int:
        """Convert to 16-bit signed integer (INT)"""
        if index + 2 > len(data):
            raise S7ReadError(f"Not enough data for INT at index {index}")
        return struct.unpack('>h', data[index:index+2])[0]
    
    @staticmethod
    def to_dint(data: bytes, index: int = 0) -> int:
        """Convert to 32-bit signed integer (DINT)"""
        if index + 4 > len(data):
            raise S7ReadError(f"Not enough data for DINT at index {index}")
        return struct.unpack('>i', data[index:index+4])[0]
    
    @staticmethod
    def to_real(data: bytes, index: int = 0) -> float:
        """Convert to 32-bit float (REAL)"""
        if index + 4 > len(data):
            raise S7ReadError(f"Not enough data for REAL at index {index}")
        return struct.unpack('>f', data[index:index+4])[0]
    
    @staticmethod
    def to_lreal(data: bytes, index: int = 0) -> float:
        """Convert to 64-bit float (LREAL)"""
        if index + 8 > len(data):
            raise S7ReadError(f"Not enough data for LREAL at index {index}")
        return struct.unpack('>d', data[index:index+8])[0]
    
    @staticmethod
    def from_bool(value: bool, byte_index: int = 0, bit_index: int = 0) -> bytes:
        """Convert boolean to byte with bit set"""
        # Returns a single byte with the bit set/cleared
        byte_val = 0x00
        if value:
            byte_val = (1 << bit_index)
        return bytes([byte_val])
    
    @staticmethod
    def from_byte(value: int) -> bytes:
        """Convert byte value to bytes"""
        return bytes([value & 0xFF])
    
    @staticmethod
    def from_word(value: int) -> bytes:
        """Convert WORD to bytes"""
        return struct.pack('>H', value & 0xFFFF)
    
    @staticmethod
    def from_dword(value: int) -> bytes:
        """Convert DWORD to bytes"""
        return struct.pack('>I', value & 0xFFFFFFFF)
    
    @staticmethod
    def from_int(value: int) -> bytes:
        """Convert INT to bytes"""
        return struct.pack('>h', value)
    
    @staticmethod
    def from_dint(value: int) -> bytes:
        """Convert DINT to bytes"""
        return struct.pack('>i', value)
    
    @staticmethod
    def from_real(value: float) -> bytes:
        """Convert REAL to bytes"""
        return struct.pack('>f', value)
    
    @staticmethod
    def from_lreal(value: float) -> bytes:
        """Convert LREAL to bytes"""
        return struct.pack('>d', value)


class S7Driver:
    """
    Main S7 Driver Class
    Provides high-level interface for S7 PLC communication
    """
    
    # Maximum PDU size for S7 communication
    # S7-300/400: 240 bytes, S7-1200/1500: 480-960 bytes
    # Subtract 18 bytes for header overhead
    MAX_PDU_SIZE = 480
    PDU_HEADER_SIZE = 18
    MAX_DATA_SIZE = MAX_PDU_SIZE - PDU_HEADER_SIZE  # 462 bytes available for data
    
    def __init__(self, config: S7ConnectionConfig):
        self.config = config
        self.connection = S7Connection(config)
        self.converter = S7DataConverter()
        self._logger = logging.getLogger(f"S7Driver.{config.connection_name}")
        self._lock = threading.RLock()
        self.last_error: Optional[str] = None  # Store last error message
        
    def connect(self) -> bool:
        """Connect to PLC"""
        return self.connection.connect()
    
    def disconnect(self) -> None:
        """Disconnect from PLC"""
        self.connection.disconnect()
    
    @property
    def is_connected(self) -> bool:
        """Check connection status"""
        return self.connection.is_connected
    
    def read_area(self, area: S7Area, db_number: int, start: int, size: int) -> bytes:
        """
        Read raw bytes from S7 area
        
        Args:
            area: S7 memory area
            db_number: DB number (for DB area)
            start: Start byte address
            size: Number of bytes to read
            
        Returns:
            bytes: Raw data bytes
            
        Raises:
            S7ReadError: If read operation fails
        """
        def _read():
            client = self.connection.get_client()
            # Use snap7 Areas enum instead of integer value
            snap7_area = get_snap7_area(area)
            result = client.read_area(snap7_area, db_number, start, size)
            
            # Check if result is an error code (integer)
            if isinstance(result, int):
                raise S7ReadError(f"Snap7 error code: {result}")
            
            return result
        
        try:
            return self.connection.execute_with_retry(_read)
        except Exception as e:
            area_name = area.name if hasattr(area, 'name') else str(area)
            raise S7ReadError(f"Failed to read area {area_name}: {e}")
    
    def write_area(self, area: S7Area, db_number: int, start: int, data: bytes) -> None:
        """
        Write raw bytes to S7 area
        
        Args:
            area: S7 memory area
            db_number: DB number (for DB area)
            start: Start byte address
            data: Data bytes to write
            
        Raises:
            S7WriteError: If write operation fails
        """
        def _write():
            client = self.connection.get_client()
            # Use snap7 Areas enum instead of integer value
            snap7_area = get_snap7_area(area)
            result = client.write_area(snap7_area, db_number, start, data)
            
            # Check if result is an error code (integer)
            if isinstance(result, int) and result != 0:
                raise S7WriteError(f"Snap7 error code: {result}")
        
        try:
            self.connection.execute_with_retry(_write)
        except Exception as e:
            area_name = area.name if hasattr(area, 'name') else str(area)
            raise S7WriteError(f"Failed to write area {area_name}: {e}")
    
    def read_tag(self, tag: Union[S7Tag, str], data_type: str = "BOOL") -> Union[bool, int, float]:
        """
        Read a single tag value
        
        Args:
            tag: S7Tag definition or address string (e.g., "M300.0", "DB1.DBX0.0")
            data_type: Data type for string addresses (default: BOOL)
            
        Returns:
            Tag value (type depends on tag.data_type)
        """
        # Convert string address to S7Tag if needed
        if isinstance(tag, str):
            tag = parse_s7_address(tag, data_type)
        
        data = self.read_area(tag.area, tag.db_number, tag.byte_offset, tag.size)
        
        converters = {
            "BOOL": lambda d: self.converter.to_bool(d, 0, tag.bit_offset),
            "BYTE": lambda d: self.converter.to_byte(d, 0),
            "WORD": lambda d: self.converter.to_word(d, 0),
            "DWORD": lambda d: self.converter.to_dword(d, 0),
            "INT": lambda d: self.converter.to_int(d, 0),
            "DINT": lambda d: self.converter.to_dint(d, 0),
            "REAL": lambda d: self.converter.to_real(d, 0),
            "LREAL": lambda d: self.converter.to_lreal(d, 0),
        }
        
        converter = converters.get(tag.data_type)
        if not converter:
            raise S7ReadError(f"Unsupported data type: {tag.data_type}")
        
        return converter(data)
    
    def write_tag(self, tag: Union[S7Tag, str], value: Union[bool, int, float], data_type: str = "BOOL") -> bool:
        """
        Write a single tag value
        
        Args:
            tag: S7Tag definition or address string (e.g., "M300.0", "DB1.DBX0.0")
            value: Value to write
            data_type: Data type for string addresses (default: BOOL)
            
        Returns:
            True if write successful, False otherwise
        """
        try:
            # Convert string address to S7Tag if needed
            if isinstance(tag, str):
                tag = parse_s7_address(tag, data_type)
            
            converters = {
                "BOOL": lambda v: self.converter.from_bool(v, 0, tag.bit_offset),
                "BYTE": lambda v: self.converter.from_byte(v),
                "WORD": lambda v: self.converter.from_word(v),
                "DWORD": lambda v: self.converter.from_dword(v),
                "INT": lambda v: self.converter.from_int(v),
                "DINT": lambda v: self.converter.from_dint(v),
                "REAL": lambda v: self.converter.from_real(v),
                "LREAL": lambda v: self.converter.from_lreal(v),
            }
            
            converter = converters.get(tag.data_type)
            if not converter:
                self.last_error = f"Unsupported data type: {tag.data_type}"
                return False
            
            data = converter(value)
            self.write_area(tag.area, tag.db_number, tag.byte_offset, data)
            return True
            
        except Exception as e:
            self.last_error = str(e)
            return False
    
    def read_tags_batch(self, tags: List[Union[S7Tag, str, tuple]], 
                        data_type: str = "BOOL") -> Dict[str, Union[bool, int, float]]:
        """
        Read multiple tags in optimized batch operation
        
        Uses read_area to read continuous blocks of data from the same DB/area.
        
        Args:
            tags: List of S7Tag definitions, address strings, or (address, data_type) tuples
            data_type: Default data type for string addresses
            
        Returns:
            Dictionary mapping uppercase addresses to values
        """
        if not tags:
            return {}
        
        # Convert string addresses to S7Tag objects, normalizing to uppercase
        s7_tags = []
        for tag in tags:
            if isinstance(tag, str):
                s7_tag = parse_s7_address(tag, data_type)
                s7_tags.append(s7_tag)
            elif isinstance(tag, tuple) and len(tag) >= 2:
                # Handle (address, data_type) tuple from DataPoller
                original_addr = tag[0]
                tag_data_type = tag[1] if len(tag) > 1 else data_type
                s7_tag = parse_s7_address(original_addr, tag_data_type)
                s7_tags.append(s7_tag)
            else:
                s7_tags.append(tag)
        
        # Group tags by area and DB number
        groups = self._group_tags_for_batch_read(s7_tags)
        
        results = {}
        
        for group_key, group_tags in groups.items():
            try:
                area, db_number, start, size = group_key
                
                # Read continuous block using read_area
                data = self.read_area(area, db_number, start, size)
                
                # Extract individual tag values
                for tag in group_tags:
                    offset = tag.byte_offset - start
                    
                    converters = {
                        "BOOL": lambda d, o: self.converter.to_bool(d, o, tag.bit_offset),
                        "BYTE": lambda d, o: self.converter.to_byte(d, o),
                        "WORD": lambda d, o: self.converter.to_word(d, o),
                        "DWORD": lambda d, o: self.converter.to_dword(d, o),
                        "INT": lambda d, o: self.converter.to_int(d, o),
                        "DINT": lambda d, o: self.converter.to_dint(d, o),
                        "REAL": lambda d, o: self.converter.to_real(d, o),
                        "LREAL": lambda d, o: self.converter.to_lreal(d, o),
                    }
                    
                    converter = converters.get(tag.data_type)
                    # Use uppercase address as key (consistent with Tag class)
                    if converter:
                        results[tag.name] = converter(data, offset)
                    else:
                        results[tag.name] = None
                        self._logger.warning(f"Unsupported data type for tag {tag.name}: {tag.data_type}")
                        
            except Exception as e:
                self._logger.error(f"Batch read failed for group {group_key}: {e}")
                # Fall back to individual reads
                for tag in group_tags:
                    try:
                        results[tag.name] = self.read_tag(tag)
                    except Exception as e2:
                        self._logger.error(f"Individual read failed for {tag.name}: {e2}")
                        results[tag.name] = None
        
        return results
    
    def _read_multi_vars(self, tags: List[S7Tag], results: Dict) -> None:
        """
        Read multiple variables using snap7's read_multi_vars
        
        This allows reading up to 20 variables in one request regardless of address spacing.
        """
        if not self.is_connected:
            raise S7CommunicationError("Not connected to PLC")
        
        from snap7.type import S7DataItem, Area as S7AreaEnum
        import ctypes
        
        # Map S7Area to snap7 Area enum
        area_map = {
            S7Area.DB: S7AreaEnum.DB,
            S7Area.MK: S7AreaEnum.MK,
            S7Area.PE: S7AreaEnum.PE,
            S7Area.PA: S7AreaEnum.PA,
            S7Area.TM: S7AreaEnum.TM,
            S7Area.CT: S7AreaEnum.CT,
        }
        
        # Map data type to word length
        wordlen_map = {
            "BOOL": 0x01,    # S7WLBit
            "BYTE": 0x02,    # S7WLByte
            "WORD": 0x04,    # S7WLWord
            "DWORD": 0x06,   # S7WLDWord
            "INT": 0x04,     # S7WLWord
            "DINT": 0x06,    # S7WLDWord
            "REAL": 0x08,    # S7WLReal
            "LREAL": 0x0A,   # S7WLLReal
        }
        
        # Create S7DataItem array
        num_items = len(tags)
        items = (S7DataItem * num_items)()
        
        # Prepare buffers for each item
        buffers = []
        for i, tag in enumerate(tags):
            item = items[i]
            item.Area = area_map.get(tag.area, S7AreaEnum.DB)
            item.WordLen = wordlen_map.get(tag.data_type, 0x02)  # Default to byte
            item.DBNumber = tag.db_number if tag.area == S7Area.DB else 0
            item.Start = tag.byte_offset * 8 + tag.bit_offset if tag.data_type == "BOOL" else tag.byte_offset
            item.Amount = 1  # For multi-var, we read 1 element at a time
            
            # Allocate buffer based on data type
            if tag.data_type == "BOOL":
                buf_size = 1
            elif tag.data_type in ["BYTE", "BOOL"]:
                buf_size = 1
            elif tag.data_type in ["WORD", "INT"]:
                buf_size = 2
            elif tag.data_type in ["DWORD", "DINT", "REAL"]:
                buf_size = 4
            elif tag.data_type == "LREAL":
                buf_size = 8
            else:
                buf_size = 4
            
            buffer = (ctypes.c_ubyte * buf_size)()
            buffers.append(buffer)
            item.pData = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        
        # Execute multi-variable read
        result = self.connection._client.read_multi_vars(items)
        
        # Process results
        for i, tag in enumerate(tags):
            item = items[i]
            buffer = buffers[i]
            
            if item.Result == 0:  # Success
                # Convert buffer to value
                data = bytes(buffer)
                
                converters = {
                    "BOOL": lambda d: bool(d[0] & 0x01),
                    "BYTE": lambda d: d[0],
                    "WORD": lambda d: int.from_bytes(d[:2], byteorder='big'),
                    "DWORD": lambda d: int.from_bytes(d[:4], byteorder='big'),
                    "INT": lambda d: int.from_bytes(d[:2], byteorder='big', signed=True),
                    "DINT": lambda d: int.from_bytes(d[:4], byteorder='big', signed=True),
                    "REAL": lambda d: struct.unpack('>f', d[:4])[0],
                    "LREAL": lambda d: struct.unpack('>d', d[:8])[0],
                }
                
                converter = converters.get(tag.data_type)
                if converter:
                    results[tag.name] = converter(data)
                else:
                    results[tag.name] = None
            else:
                # Read failed for this item
                self._logger.error(f"Multi-var read failed for {tag.name}: error code {item.Result}")
                results[tag.name] = None
    
    def _group_tags_for_batch_read(self, tags: List[S7Tag]) -> Dict:
        """
        Group tags for efficient batch reading using read_area
        
        Groups tags by area and DB number, then packs as many tags as possible
        into each read operation without exceeding MAX_DATA_SIZE (PDU - header).
        
        Uses greedy algorithm: keep adding tags until total data size would exceed limit.
        """
        # Group by area and DB
        area_groups = defaultdict(list)
        for tag in tags:
            key = (tag.area, tag.db_number)
            area_groups[key].append(tag)
        
        result_groups = {}
        
        for (area, db_number), area_tags in area_groups.items():
            # Sort by byte offset
            sorted_tags = sorted(area_tags, key=lambda t: t.byte_offset)
            
            # Greedy packing: add tags until data size exceeds MAX_DATA_SIZE
            current_group = []
            current_data_size = 0
            group_start = None
            
            for tag in sorted_tags:
                if not current_group:
                    # Start new group
                    current_group = [tag]
                    current_data_size = tag.size
                    group_start = tag.byte_offset
                else:
                    # Check if adding this tag would exceed data limit
                    new_data_size = current_data_size + tag.size
                    
                    if new_data_size <= self.MAX_DATA_SIZE:
                        # Can fit in current group
                        current_group.append(tag)
                        current_data_size = new_data_size
                    else:
                        # Save current group and start new one
                        # Calculate span for read_area
                        group_end = max(t.byte_offset + t.size for t in current_group)
                        span = group_end - group_start
                        result_groups[(area, db_number, group_start, span)] = current_group
                        
                        # Start new group
                        current_group = [tag]
                        current_data_size = tag.size
                        group_start = tag.byte_offset
            
            # Don't forget the last group
            if current_group:
                group_end = max(t.byte_offset + t.size for t in current_group)
                span = group_end - group_start
                result_groups[(area, db_number, group_start, span)] = current_group
        
        return result_groups
    
    def write_tags_batch(self, tag_values: Dict[S7Tag, Union[bool, int, float]]) -> Dict[str, bool]:
        """
        Write multiple tags in batch
        
        Args:
            tag_values: Dictionary mapping tags to values
            
        Returns:
            Dictionary mapping tag names to success status
        """
        results = {}
        
        for tag, value in tag_values.items():
            try:
                self.write_tag(tag, value)
                results[tag.name] = True
            except Exception as e:
                self._logger.error(f"Failed to write {tag.name}: {e}")
                results[tag.name] = False
        
        return results
    
    def read_db(self, db_number: int, start: int = 0, size: int = None) -> bytes:
        """
        Read entire DB or portion of it
        
        Args:
            db_number: DB number
            start: Start byte
            size: Number of bytes (None = read up to PDU limit)
            
        Returns:
            DB data bytes
        """
        if size is None:
            size = self.MAX_PDU_SIZE
        
        return self.read_area(S7Area.DB, db_number, start, size)
    
    def write_db(self, db_number: int, start: int, data: bytes) -> None:
        """
        Write data to DB
        
        Args:
            db_number: DB number
            start: Start byte
            data: Data to write
        """
        self.write_area(S7Area.DB, db_number, start, data)
    
    def read_merkers(self, start: int, size: int) -> bytes:
        """Read from Merkers (M) area"""
        return self.read_area(S7Area.MK, 0, start, size)
    
    def write_merkers(self, start: int, data: bytes) -> None:
        """Write to Merkers (M) area"""
        self.write_area(S7Area.MK, 0, start, data)
    
    def read_inputs(self, start: int, size: int) -> bytes:
        """Read from Process Inputs (I) area"""
        return self.read_area(S7Area.PE, 0, start, size)
    
    def read_outputs(self, start: int, size: int) -> bytes:
        """Read from Process Outputs (Q) area"""
        return self.read_area(S7Area.PA, 0, start, size)
    
    # Convenience methods for data_poller compatibility
    def read_bool(self, db_number: int, byte_offset: int, bit_offset: int = 0) -> bool:
        """Read boolean value from DB"""
        data = self.read_area(S7Area.DB, db_number, byte_offset, 1)
        return self.converter.to_bool(data, 0, bit_offset)
    
    def read_real(self, db_number: int, byte_offset: int) -> float:
        """Read REAL (float) value from DB"""
        data = self.read_area(S7Area.DB, db_number, byte_offset, 4)
        return self.converter.to_real(data, 0)
    
    def read_dword(self, db_number: int, byte_offset: int) -> int:
        """Read DWORD (32-bit unsigned) value from DB"""
        data = self.read_area(S7Area.DB, db_number, byte_offset, 4)
        return self.converter.to_dword(data, 0)
    
    def read_int(self, db_number: int, byte_offset: int) -> int:
        """Read INT (16-bit signed) value from DB"""
        data = self.read_area(S7Area.DB, db_number, byte_offset, 2)
        return self.converter.to_int(data, 0)
    
    def read_dint(self, db_number: int, byte_offset: int) -> int:
        """Read DINT (32-bit signed) value from DB"""
        data = self.read_area(S7Area.DB, db_number, byte_offset, 4)
        return self.converter.to_dint(data, 0)
    
    def read_byte(self, db_number: int, byte_offset: int) -> int:
        """Read BYTE value from DB"""
        data = self.read_area(S7Area.DB, db_number, byte_offset, 1)
        return data[0]
    
    def read_word(self, db_number: int, byte_offset: int) -> int:
        """Read WORD (16-bit unsigned) value from DB"""
        data = self.read_area(S7Area.DB, db_number, byte_offset, 2)
        return self.converter.to_word(data, 0)
    
    def read_merkers_bit(self, byte_offset: int, bit_offset: int = 0) -> bool:
        """Read boolean value from M area"""
        data = self.read_area(S7Area.MK, 0, byte_offset, 1)
        return self.converter.to_bool(data, 0, bit_offset)
    
    def read_merkers_byte(self, byte_offset: int) -> int:
        """Read byte value from M area"""
        data = self.read_area(S7Area.MK, 0, byte_offset, 1)
        return data[0]
    
    def read_merkers_int(self, byte_offset: int) -> int:
        """Read INT (16-bit) value from M area"""
        data = self.read_area(S7Area.MK, 0, byte_offset, 2)
        return self.converter.to_int(data, 0)
    
    def read_merkers_dint(self, byte_offset: int) -> int:
        """Read DINT (32-bit) value from M area"""
        data = self.read_area(S7Area.MK, 0, byte_offset, 4)
        return self.converter.to_dint(data, 0)
    
    def read_merkers_real(self, byte_offset: int) -> float:
        """Read REAL (float) value from M area"""
        data = self.read_area(S7Area.MK, 0, byte_offset, 4)
        return self.converter.to_real(data, 0)
    
    def get_plc_info(self) -> Dict[str, Any]:
        """
        Get PLC information
        
        Returns:
            Dictionary with PLC information
        """
        def _get_info():
            client = self.connection.get_client()
            info = {}
            
            try:
                info['cpu_state'] = client.get_cpu_state()
            except:
                info['cpu_state'] = 'unknown'
            
            try:
                info['cpu_info'] = client.get_cpu_info()
            except:
                info['cpu_info'] = None
            
            try:
                info['connected'] = client.get_connected()
            except:
                info['connected'] = False
            
            return info
        
        try:
            return self.connection.execute_with_retry(_get_info)
        except Exception as e:
            self._logger.error(f"Failed to get PLC info: {e}")
            return {'connected': False, 'error': str(e)}


# Convenience functions for creating tags
def create_db_tag(name: str, db_number: int, byte_offset: int, bit_offset: int = 0, 
                  data_type: str = "BOOL") -> S7Tag:
    """Create a DB tag"""
    return S7Tag(name, S7Area.DB, db_number, byte_offset, bit_offset, data_type)


def create_merkers_tag(name: str, byte_offset: int, bit_offset: int = 0,
                       data_type: str = "BOOL") -> S7Tag:
    """Create a Merkers (M) tag"""
    return S7Tag(name, S7Area.MK, 0, byte_offset, bit_offset, data_type)


def create_input_tag(name: str, byte_offset: int, bit_offset: int = 0,
                     data_type: str = "BOOL") -> S7Tag:
    """Create an Input (I) tag"""
    return S7Tag(name, S7Area.PE, 0, byte_offset, bit_offset, data_type)


def create_output_tag(name: str, byte_offset: int, bit_offset: int = 0,
                      data_type: str = "BOOL") -> S7Tag:
    """Create an Output (Q) tag"""
    return S7Tag(name, S7Area.PA, 0, byte_offset, bit_offset, data_type)


def parse_s7_address(address: str, data_type: str = "BOOL") -> S7Tag:
    """
    Parse S7 address string into S7Tag
    
    Supported formats:
    - DB1.DBX0.0  -> DB 1, Byte 0, Bit 0 (BOOL)
    - DB1.DBW2    -> DB 1, Byte 2 (WORD)
    - DB1.DBD4    -> DB 1, Byte 4 (DWORD)
    - DB1.DBR6    -> DB 1, Byte 6 (REAL)
    - M0.0        -> M area, Byte 0, Bit 0
    - MW10        -> M area, Word at Byte 10
    - I0.0        -> Input, Byte 0, Bit 0
    - Q0.0        -> Output, Byte 0, Bit 0
    
    Args:
        address: Address string
        data_type: Data type (BOOL, BYTE, WORD, DWORD, INT, DINT, REAL)
        
    Returns:
        S7Tag object
    """
    address = address.strip().upper()
    
    # Parse DB addresses
    if address.startswith('DB'):
        # DB1.DBX0.0 or DB1.0.0 format
        if '.DBX' in address or '.DBW' in address or '.DBD' in address or '.DBR' in address:
            # Siemens format: DB1.DBX0.0
            parts = address.split('.')
            db_number = int(parts[0][2:])  # Remove "DB" prefix
            
            if '.DBX' in address:
                # Bit access: DB1.DBX0.0
                byte_offset = int(parts[1][3:])  # Remove "DBX"
                bit_offset = int(parts[2]) if len(parts) > 2 else 0
                return S7Tag(address, S7Area.DB, db_number, byte_offset, bit_offset, "BOOL")
            elif '.DBW' in address:
                # Word access: DB1.DBW2
                byte_offset = int(parts[1][3:])  # Remove "DBW"
                return S7Tag(address, S7Area.DB, db_number, byte_offset, 0, "WORD")
            elif '.DBD' in address:
                # DWord access: DB1.DBD4
                # Note: DBD can be used for both DWORD and REAL
                # Respect the data_type parameter if it's explicitly set to REAL
                byte_offset = int(parts[1][3:])  # Remove "DBD"
                actual_data_type = data_type if data_type == "REAL" else "DWORD"
                return S7Tag(address, S7Area.DB, db_number, byte_offset, 0, actual_data_type)
            elif '.DBR' in address:
                # Real access: DB1.DBR6
                byte_offset = int(parts[1][3:])  # Remove "DBR"
                return S7Tag(address, S7Area.DB, db_number, byte_offset, 0, "REAL")
        else:
            # Simple format: DB1.0.0
            parts = address.split('.')
            db_number = int(parts[0][2:])  # Remove "DB" prefix
            byte_offset = int(parts[1]) if len(parts) > 1 else 0
            bit_offset = int(parts[2]) if len(parts) > 2 else 0
            return S7Tag(address, S7Area.DB, db_number, byte_offset, bit_offset, data_type)
    
    # Parse M (Merkers) addresses
    elif address.startswith('M'):
        if 'MW' in address:
            # Word: MW10
            byte_offset = int(address[2:])
            return S7Tag(address, S7Area.MK, 0, byte_offset, 0, "WORD")
        elif 'MD' in address:
            # DWord: MD10
            byte_offset = int(address[2:])
            return S7Tag(address, S7Area.MK, 0, byte_offset, 0, "DWORD")
        elif 'MB' in address:
            # Byte: MB10
            byte_offset = int(address[2:])
            return S7Tag(address, S7Area.MK, 0, byte_offset, 0, "BYTE")
        else:
            # Bit: M0.0 or M10
            if '.' in address:
                parts = address[1:].split('.')
                byte_offset = int(parts[0])
                bit_offset = int(parts[1])
                return S7Tag(address, S7Area.MK, 0, byte_offset, bit_offset, "BOOL")
            else:
                byte_offset = int(address[1:])
                return S7Tag(address, S7Area.MK, 0, byte_offset, 0, data_type)
    
    # Parse I (Input) addresses
    elif address.startswith('I'):
        if '.' in address:
            parts = address[1:].split('.')
            byte_offset = int(parts[0])
            bit_offset = int(parts[1])
            return S7Tag(address, S7Area.PE, 0, byte_offset, bit_offset, "BOOL")
        else:
            byte_offset = int(address[1:])
            return S7Tag(address, S7Area.PE, 0, byte_offset, 0, data_type)
    
    # Parse Q (Output) addresses
    elif address.startswith('Q'):
        if '.' in address:
            parts = address[1:].split('.')
            byte_offset = int(parts[0])
            bit_offset = int(parts[1])
            return S7Tag(address, S7Area.PA, 0, byte_offset, bit_offset, "BOOL")
        else:
            byte_offset = int(address[1:])
            return S7Tag(address, S7Area.PA, 0, byte_offset, 0, data_type)
    
    # Unknown format, assume it's a DB address
    else:
        # Try to parse as DB address
        parts = address.split('.')
        if len(parts) >= 2:
            db_number = int(parts[0])
            byte_offset = int(parts[1])
            bit_offset = int(parts[2]) if len(parts) > 2 else 0
            return S7Tag(address, S7Area.DB, db_number, byte_offset, bit_offset, data_type)
        else:
            raise ValueError(f"Unable to parse S7 address: {address}")


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create connection configuration
    config = S7ConnectionConfig(
        ip_address="192.168.0.1",
        rack=0,
        slot=1,
        connection_name="TestConnection"
    )
    
    # Create driver instance
    driver = S7Driver(config)
    
    # Connect to PLC
    if driver.connect():
        print("Connected to PLC successfully!")
        
        try:
            # Create some tags
            tag1 = create_db_tag("Motor1_Running", 1, 0, 0, "BOOL")
            tag2 = create_db_tag("Temperature", 1, 2, 0, "REAL")
            tag3 = create_merkers_tag("System_Ready", 100, 0, "BOOL")
            
            # Read single tag
            value = driver.read_tag(tag1)
            print(f"{tag1.name} = {value}")
            
            # Read multiple tags in batch
            values = driver.read_tags_batch([tag1, tag2, tag3])
            print(f"Batch read: {values}")
            
            # Write tag
            driver.write_tag(tag1, True)
            print(f"Wrote True to {tag1.name}")
            
            # Get PLC info
            info = driver.get_plc_info()
            print(f"PLC Info: {info}")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            driver.disconnect()
            print("Disconnected from PLC")
    else:
        print("Failed to connect to PLC")
