"""
Siemens S7 Connection Manager
Improved connection management with better error handling and reconnection logic
"""

import snap7
import time
import logging
from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class S7ConnectionConfig:
    """S7 connection configuration"""
    ip_address: str
    rack: int = 0
    slot: int = 1
    timeout: int = 5000  # Connection timeout in ms
    retry_interval: int = 5  # Retry interval in seconds
    max_retries: int = 3  # Maximum retry attempts
    

class S7Connection:
    """Enhanced S7 PLC connection manager"""
    
    def __init__(self, config: S7ConnectionConfig):
        self.config = config
        self.client: Optional[snap7.client.Client] = None
        self.is_connected = False
        self.connection_time = None
        self.retry_count = 0
        self.logger = logging.getLogger(f"S7Connection_{config.ip_address}")
        
    def connect(self) -> bool:
        """Establish connection to S7 PLC"""
        try:
            if self.is_connected:
                self.logger.info("Already connected to PLC")
                return True
                
            self.logger.info(f"Connecting to S7 PLC at {self.config.ip_address}")
            
            # Create client if not exists
            if not self.client:
                self.client = snap7.client.Client()
            
            # Note: snap7 Client doesn't have set_connection_timeout method
            # The timeout is handled internally by the library
            
            # Attempt connection
            self.client.connect(self.config.ip_address, self.config.rack, self.config.slot)
            
            # Verify connection
            if self.client.get_connected():
                self.is_connected = True
                self.connection_time = time.time()
                self.retry_count = 0
                self.logger.info("Successfully connected to S7 PLC")
                return True
            else:
                self.logger.error("Failed to establish connection")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Disconnect from S7 PLC"""
        try:
            if self.client and self.is_connected:
                self.client.disconnect()
                self.is_connected = False
                self.connection_time = None
                self.logger.info("Disconnected from S7 PLC")
        except Exception as e:
            self.logger.error(f"Error during disconnect: {str(e)}")
        finally:
            self.client = None
    
    def reconnect(self) -> bool:
        """Attempt to reconnect to PLC"""
        if self.retry_count >= self.config.max_retries:
            self.logger.error("Maximum retry attempts reached")
            return False
            
        self.logger.info(f"Attempting reconnection (attempt {self.retry_count + 1})")
        
        # Disconnect first if needed
        if self.client:
            try:
                self.client.disconnect()
            except:
                pass
        
        # Wait before retry
        time.sleep(self.config.retry_interval)
        
        # Attempt connection
        success = self.connect()
        if not success:
            self.retry_count += 1
            
        return success
    
    def check_connection(self) -> bool:
        """Check if connection is still active"""
        try:
            if not self.client:
                return False
                
            # Check connection status
            is_connected = self.client.get_connected()
            
            if not is_connected and self.is_connected:
                self.logger.warning("Connection lost")
                self.is_connected = False
                
            return is_connected
            
        except Exception as e:
            self.logger.error(f"Error checking connection: {str(e)}")
            self.is_connected = False
            return False
    
    def ensure_connection(self) -> bool:
        """Ensure connection is active, reconnect if needed"""
        if self.is_connected and self.check_connection():
            return True
            
        # If connection is lost or not connected, attempt to reconnect
        return self.reconnect()
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
    
    @property
    def connection_duration(self) -> Optional[float]:
        """Get connection duration in seconds"""
        if self.connection_time:
            return time.time() - self.connection_time
        return None