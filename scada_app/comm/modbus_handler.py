"""
Modbus TCP/RTU Handler for HMI SCADA
支持 Modbus TCP 和 Modbus RTU 协议
"""
try:
    from pymodbus.client import ModbusTcpClient, ModbusSerialClient
    from pymodbus.exceptions import ModbusException
    PYMOSBUS_AVAILABLE = True
except ImportError:
    PYMOSBUS_AVAILABLE = False
    ModbusTcpClient = None
    ModbusSerialClient = None
    ModbusException = Exception

import struct
import threading
import asyncio
from typing import Optional, Union, Callable, Any
from concurrent.futures import ThreadPoolExecutor, Future
import time
from datetime import datetime


class ModbusHandler:
    """Modbus TCP/RTU handler for PLC communication"""
    
    # 全局线程池用于异步操作
    _executor: Optional[ThreadPoolExecutor] = None
    _executor_lock = threading.Lock()
    
    @classmethod
    def get_executor(cls) -> ThreadPoolExecutor:
        """获取线程池实例"""
        if cls._executor is None:
            with cls._executor_lock:
                if cls._executor is None:
                    cls._executor = ThreadPoolExecutor(max_workers=10)
        return cls._executor

    def __init__(self, address: str, port: int = 502, protocol: str = "tcp", slave_id: int = 1,
                 baudrate: int = 9600, databits: int = 8, parity: str = 'N', stopbits: int = 1):
        self.address = address
        self.port = port
        self.protocol = protocol.lower()
        self.slave_id = slave_id
        # RTU serial parameters
        self.baudrate = baudrate
        self.databits = databits
        self.parity = parity
        self.stopbits = stopbits
        self.client = None
        self.connected = False

    def connect(self) -> bool:
        """Connect to Modbus device"""
        if not PYMOSBUS_AVAILABLE:
            print("ModbusHandler: pymodbus not installed. Install with: pip install pymodbus")
            return False

        try:
            # Cleanup existing connection first
            if self.client:
                try:
                    self.client.close()
                except:
                    pass
                self.client = None
            
            if self.protocol == "tcp":
                self.client = ModbusTcpClient(
                    host=self.address,
                    port=self.port,
                    timeout=0.5  # Reduced from 2 to 0.5 seconds for faster failure detection
                )
            elif self.protocol == "rtu":
                # For RTU, address should be serial port like 'COM1' or '/dev/ttyUSB0'
                self.client = ModbusSerialClient(
                    port=self.address,
                    baudrate=self.baudrate,
                    bytesize=self.databits,
                    parity=self.parity,
                    stopbits=self.stopbits,
                    timeout=0.5  # Reduced from 2 to 0.5 seconds for faster failure detection
                )
            else:
                print(f"ModbusHandler: Unknown protocol {self.protocol}")
                return False

            self.connected = self.client.connect()
            if self.connected:
                print(f"ModbusHandler: Connected to {self.address}:{self.port} (slave={self.slave_id})")
            else:
                print(f"ModbusHandler: Failed to connect to {self.address}:{self.port}")
            return self.connected

        except Exception as e:
            print(f"ModbusHandler: Connection error: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from Modbus device"""
        if self.client:
            try:
                self.client.close()
            except:
                pass
        self.client = None
        self.connected = False
        print("ModbusHandler: Disconnected")
    
    def is_connected(self) -> bool:
        """Check if connection is active with verification"""
        if not self.connected or not self.client:
            return False
        
        try:
            # Try a simple read to verify connection
            # Read holding register 0 (address 40001) - this should be safe
            result = self.client.read_holding_registers(0, 1, slave=self.slave_id)
            if result is None or hasattr(result, 'isError') and result.isError():
                # Read failed, connection is broken
                self.connected = False
                return False
            return True
        except Exception as e:
            # Exception means connection is broken
            self.connected = False
            return False

    def _parse_address(self, address: str) -> tuple:
        """
        Parse Modbus address string
        支持格式:
        - 40001 (保持寄存器, 功能码 03)
        - 30001 (输入寄存器, 功能码 04)
        - 10001 (离散输入, 功能码 02)
        - 00001 (线圈, 功能码 01)
        - 4x0001 (保持寄存器)
        - 3x0001 (输入寄存器)
        - 1x0001 (离散输入)
        - 0x0001 (线圈)
        """
        address = address.strip().upper()

        # Check for prefix format (4x, 3x, 1x, 0x)
        if len(address) >= 2 and address[1] == 'X':
            prefix = address[0]
            try:
                offset = int(address[2:]) - 1  # Modbus addresses are 1-based
                return prefix, offset
            except ValueError:
                return None, None

        # Check for 5-digit format
        if len(address) == 5 and address.isdigit():
            prefix = address[0]
            try:
                offset = int(address[1:]) - 1  # Modbus addresses are 1-based
                return prefix, offset
            except ValueError:
                return None, None

        # Default to holding register (4x)
        try:
            return '4', int(address) - 1
        except ValueError:
            return None, None

    def read_tag(self, tag_name: str) -> Optional[Union[bool, int, float]]:
        """
        Read a tag value from Modbus device
        tag_name format: "40001" (holding register), "10001" (coil), etc.
        """
        if not self.connected or not self.client:
            print(f"ModbusHandler: Not connected, cannot read {tag_name}")
            return None

        try:
            prefix, offset = self._parse_address(tag_name)
            if prefix is None:
                print(f"ModbusHandler: Invalid address format: {tag_name}")
                return None

            # Coil (0x) - Function code 01
            if prefix == '0':
                result = self.client.read_coils(offset, count=1, device_id=self.slave_id)
                if result and not result.isError():
                    return result.bits[0]
                return None

            # Discrete Input (1x) - Function code 02
            elif prefix == '1':
                result = self.client.read_discrete_inputs(offset, count=1, device_id=self.slave_id)
                if result and not result.isError():
                    return result.bits[0]
                return None

            # Input Register (3x) - Function code 04
            elif prefix == '3':
                result = self.client.read_input_registers(offset, count=1, device_id=self.slave_id)
                if result and not result.isError():
                    return result.registers[0]
                return None

            # Holding Register (4x) - Function code 03
            elif prefix == '4':
                result = self.client.read_holding_registers(offset, count=1, device_id=self.slave_id)
                if result and not result.isError():
                    return result.registers[0]
                return None

            else:
                print(f"ModbusHandler: Unknown address prefix: {prefix}")
                return None

        except ModbusException as e:
            error_msg = str(e)
            print(f"ModbusHandler: Modbus error reading {tag_name}: {error_msg}")
            # Only mark as disconnected for connection errors, not for device errors
            if "Connection" in error_msg or "Socket" in error_msg or "Unreachable" in error_msg:
                self.connected = False
            return None
        except Exception as e:
            error_msg = str(e)
            print(f"ModbusHandler: Error reading {tag_name}: {error_msg}")
            # Only mark as disconnected for connection errors
            if "Connection" in error_msg or "Socket" in error_msg or "Unreachable" in error_msg:
                self.connected = False
            return None

    def write_tag(self, tag_name: str, value: Union[bool, int, float], bit_offset: int = None) -> bool:
        """
        Write a tag value to Modbus device
        支持: 线圈(0x)和保持寄存器(4x)
        
        Args:
            tag_name: 地址标签名
            value: 要写入的值
            bit_offset: 位偏移（0-15），用于写入寄存器的某一位
        """
        if not self.connected or not self.client:
            print(f"ModbusHandler: Not connected, cannot write {tag_name}")
            return False

        try:
            prefix, offset = self._parse_address(tag_name)
            if prefix is None:
                print(f"ModbusHandler: Invalid address format: {tag_name}")
                return False

            # Coil (0x) - Function code 05
            if prefix == '0':
                result = self.client.write_coil(offset, bool(value), device_id=self.slave_id)
                return result and not result.isError()

            # Holding Register (4x) - Function code 06
            elif prefix == '4':
                # If bit_offset is specified, do read-modify-write
                if bit_offset is not None and 0 <= bit_offset < 16:
                    return self._write_register_bit(offset, bit_offset, bool(value))
                
                result = self.client.write_register(offset, int(value), device_id=self.slave_id)
                return result and not result.isError()

            else:
                print(f"ModbusHandler: Cannot write to {prefix}x addresses (read-only)")
                return False

        except ModbusException as e:
            print(f"ModbusHandler: Modbus error writing {tag_name}: {e}")
            self.connected = False
            return False
        except Exception as e:
            print(f"ModbusHandler: Error writing {tag_name}: {e}")
            self.connected = False
            return False

    def _write_register_bit(self, register_offset: int, bit_offset: int, value: bool) -> bool:
        """
        Write a single bit to a holding register using read-modify-write
        
        Args:
            register_offset: 寄存器偏移地址
            bit_offset: 位偏移（0-15）
            value: 要写入的布尔值
        
        Returns:
            True if successful, False otherwise
        """
        try:
            current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{current_time}] ModbusHandler: Writing bit {bit_offset} = {value} to register {register_offset}")
            
            # Read current register value
            result = self.client.read_holding_registers(register_offset, count=1, device_id=self.slave_id)
            if not result or result.isError():
                current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{current_time}] ModbusHandler: Failed to read register {register_offset} for bit write")
                return False
            
            current_value = result.registers[0]
            current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{current_time}] ModbusHandler: Current register value: {current_value} (0x{current_value:04X})")
            
            # Modify the bit
            if value:
                # Set bit
                new_value = current_value | (1 << bit_offset)
                current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{current_time}] ModbusHandler: Setting bit {bit_offset}, new value: {new_value} (0x{new_value:04X})")
            else:
                # Clear bit
                new_value = current_value & ~(1 << bit_offset)
                current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{current_time}] ModbusHandler: Clearing bit {bit_offset}, new value: {new_value} (0x{new_value:04X})")
            
            # Write back
            write_result = self.client.write_register(register_offset, new_value, device_id=self.slave_id)
            success = write_result and not write_result.isError()
            current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{current_time}] ModbusHandler: Write result: {success}")
            return success
            
        except Exception as e:
            current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{current_time}] ModbusHandler: Error writing register bit: {e}")
            import traceback
            traceback.print_exc()
            return False

    def read_registers(self, address: str, count: int = 1) -> Optional[list]:
        """Read multiple registers with auto-reconnect on failure"""
        if not self.connected or not self.client:
            # Try to reconnect if not connected
            if not self.connect():
                return None

        try:
            prefix, offset = self._parse_address(address)
            if prefix is None:
                return None

            if prefix == '4':
                result = self.client.read_holding_registers(offset, count=count, device_id=self.slave_id)
            elif prefix == '3':
                result = self.client.read_input_registers(offset, count=count, device_id=self.slave_id)
            else:
                return None

            if result and not result.isError():
                return result.registers
            
            # Read failed, try to reconnect
            print(f"ModbusHandler: Read failed for {address}, attempting reconnect...")
            self.disconnect()
            if self.connect():
                # Retry read after reconnect
                if prefix == '4':
                    result = self.client.read_holding_registers(offset, count=count, device_id=self.slave_id)
                elif prefix == '3':
                    result = self.client.read_input_registers(offset, count=count, device_id=self.slave_id)
                if result and not result.isError():
                    return result.registers
            return None

        except Exception as e:
            print(f"ModbusHandler: Error reading registers {address}: {e}")
            # Connection error, mark as disconnected
            self.connected = False
            return None

    def read_float(self, address: str, byteorder: str = 'big', wordorder: str = 'big') -> Optional[float]:
        """
        Read 32-bit float (REAL) from two consecutive registers with auto-reconnect
        
        Args:
            address: Starting address (e.g., "40001")
            byteorder: 'big' or 'little' - byte order within each 16-bit register
            wordorder: 'big' or 'little' - word order between registers
                      'big' = AB CD (high word first)
                      'little' = CD AB (low word first)
        
        Returns:
            Float value or None if error
        """
        if not self.connected or not self.client:
            # Try to reconnect if not connected
            if not self.connect():
                return None

        try:
            prefix, offset = self._parse_address(address)
            if prefix is None:
                return None

            # Read 2 registers (4 bytes = 32 bits)
            if prefix == '4':
                result = self.client.read_holding_registers(offset, count=2, device_id=self.slave_id)
            elif prefix == '3':
                result = self.client.read_input_registers(offset, count=2, device_id=self.slave_id)
            else:
                return None

            if result and not result.isError():
                # Combine two 16-bit registers into 32-bit float
                high_word = result.registers[0]
                low_word = result.registers[1]
                
                # Pack into bytes
                if wordorder == 'big':
                    # AB CD format (high word first)
                    byte_data = struct.pack('>HH', high_word, low_word)
                else:
                    # CD AB format (low word first)
                    byte_data = struct.pack('>HH', low_word, high_word)
                
                # Unpack as float
                if byteorder == 'big':
                    value = struct.unpack('>f', byte_data)[0]
                else:
                    value = struct.unpack('<f', byte_data)[0]
                
                return value
            
            # Read failed, try to reconnect
            print(f"ModbusHandler: Read float failed for {address}, attempting reconnect...")
            self.disconnect()
            if self.connect():
                # Retry read after reconnect
                if prefix == '4':
                    result = self.client.read_holding_registers(offset, count=2, device_id=self.slave_id)
                elif prefix == '3':
                    result = self.client.read_input_registers(offset, count=2, device_id=self.slave_id)
                
                if result and not result.isError():
                    high_word = result.registers[0]
                    low_word = result.registers[1]
                    
                    if wordorder == 'big':
                        byte_data = struct.pack('>HH', high_word, low_word)
                    else:
                        byte_data = struct.pack('>HH', low_word, high_word)
                    
                    if byteorder == 'big':
                        value = struct.unpack('>f', byte_data)[0]
                    else:
                        value = struct.unpack('<f', byte_data)[0]
                    
                    return value
            return None

        except Exception as e:
            print(f"ModbusHandler: Error reading float from {address}: {e}")
            # Connection error, mark as disconnected
            self.connected = False
            return None

    def write_float(self, address: str, value: float, byteorder: str = 'big', wordorder: str = 'big') -> bool:
        """
        Write 32-bit float (REAL) to two consecutive registers
        
        Args:
            address: Starting address (e.g., "40001")
            value: Float value to write
            byteorder: 'big' or 'little' - byte order within each 16-bit register
            wordorder: 'big' or 'little' - word order between registers
        """
        if not self.connected or not self.client:
            return False

        try:
            prefix, offset = self._parse_address(address)
            if prefix is None or prefix != '4':
                print("ModbusHandler: Can only write float to holding registers (4x)")
                return False

            # Pack float into bytes
            if byteorder == 'big':
                byte_data = struct.pack('>f', value)
            else:
                byte_data = struct.pack('<f', value)
            
            # Unpack into two 16-bit words
            if wordorder == 'big':
                high_word, low_word = struct.unpack('>HH', byte_data)
            else:
                low_word, high_word = struct.unpack('>HH', byte_data)
            
            # Write both registers
            result = self.client.write_registers(offset, values=[high_word, low_word], device_id=self.slave_id)
            return result and not result.isError()

        except Exception as e:
            print(f"ModbusHandler: Error writing float to {address}: {e}")
            return False

    def write_registers(self, address: str, values: list) -> bool:
        """Write multiple registers"""
        if not self.connected or not self.client:
            return False

        try:
            prefix, offset = self._parse_address(address)
            if prefix is None or prefix != '4':
                print("ModbusHandler: Can only write to holding registers (4x)")
                return False

            result = self.client.write_registers(offset, values=values, device_id=self.slave_id)
            return result and not result.isError()

        except Exception as e:
            print(f"ModbusHandler: Error writing registers: {e}")
            return False


def create_modbus_handler(params: dict) -> ModbusHandler:
    """Factory function to create Modbus handler"""
    address = params.get('address', '127.0.0.1')
    port = params.get('port', 502)
    protocol = params.get('protocol', 'tcp')
    slave_id = params.get('slave_id', 1)
    
    # RTU serial parameters
    baudrate = params.get('baudrate', 9600)
    databits = params.get('databits', 8)
    parity = params.get('parity', 'N')
    stopbits = params.get('stopbits', 1)

    return ModbusHandler(address, port, protocol, slave_id, baudrate, databits, parity, stopbits)


# 异步包装函数
def _async_read_tag_sync(handler: ModbusHandler, tag_name: str) -> Optional[Any]:
    """同步读取函数（用于在线程池中执行）"""
    return handler.read_tag(tag_name)


def _async_write_tag_sync(handler: ModbusHandler, tag_name: str, value: Any, bit_offset: Optional[int]) -> bool:
    """同步写入函数（用于在线程池中执行）"""
    return handler.write_tag(tag_name, value, bit_offset)


# 异步方法（需要在外部调用）
async def async_read_tag(handler: ModbusHandler, tag_name: str) -> Optional[Any]:
    """
    异步读取标签值
    
    Args:
        handler: ModbusHandler 实例
        tag_name: 标签名
        
    Returns:
        标签值或 None
    """
    executor = ModbusHandler.get_executor()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, _async_read_tag_sync, handler, tag_name)
    return result


async def async_write_tag(handler: ModbusHandler, tag_name: str, value: Any, bit_offset: Optional[int] = None) -> bool:
    """
    异步写入标签值
    
    Args:
        handler: ModbusHandler 实例
        tag_name: 标签名
        value: 要写入的值
        bit_offset: 位偏移（可选）
        
    Returns:
        True if successful, False otherwise
    """
    executor = ModbusHandler.get_executor()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, _async_write_tag_sync, handler, tag_name, value, bit_offset)
    return result
