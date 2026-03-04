"""
System Monitor for SCADA System
"""
import time
import datetime
from threading import Thread, Event
from typing import Dict, List, Optional
from scada_app.core.logger import logger

# Try to import psutil, but handle gracefully if not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False
    logger.warning("psutil library not available. System monitoring will be limited.")


class SystemMonitor:
    """System monitor for tracking system resources and application performance"""
    def __init__(self, update_interval: int = 5):
        self.update_interval = update_interval  # seconds
        self.monitoring_active = False
        self.monitoring_thread = None
        self.stop_event = Event()
        self.system_stats = {
            'cpu_percent': 0.0,
            'memory_percent': 0.0,
            'disk_percent': 0.0,
            'network_sent': 0,
            'network_recv': 0,
            'uptime': 0,
            'timestamp': datetime.datetime.now()
        }
        self.application_stats = {
            'plc_connections': 0,
            'active_tags': 0,
            'polling_rate': 0.0,
            'errors_count': 0,
            'warnings_count': 0
        }
        self.history = []
        self.max_history = 1000  # Keep last 1000 data points
    
    def start_monitoring(self):
        """Start the system monitoring thread"""
        if not self.monitoring_active:
            self.stop_event.clear()
            self.monitoring_thread = Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_active = True
            self.monitoring_thread.start()
            logger.info("System monitoring started")
    
    def stop_monitoring(self):
        """Stop the system monitoring thread"""
        if self.monitoring_active:
            self.monitoring_active = False
            self.stop_event.set()
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5)
            logger.info("System monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active and not self.stop_event.is_set():
            try:
                self._collect_system_stats()
                self._collect_application_stats()
                self._update_history()
                # Wait for the specified interval or stop event
                if self.stop_event.wait(timeout=self.update_interval):
                    break
            except Exception as e:
                logger.exception(f"Error in monitoring loop: {str(e)}")
                # Still wait for the interval or stop event before continuing
                if self.stop_event.wait(timeout=self.update_interval):
                    break
    
    def _collect_system_stats(self):
        """Collect system resource usage statistics"""
        try:
            if not PSUTIL_AVAILABLE:
                # Set default values when psutil is not available
                self.system_stats['cpu_percent'] = 0.0
                self.system_stats['memory_percent'] = 0.0
                self.system_stats['disk_percent'] = 0.0
                self.system_stats['network_sent'] = 0
                self.system_stats['network_recv'] = 0
                self.system_stats['uptime'] = 0
                self.system_stats['timestamp'] = datetime.datetime.now()
                return
                
            # CPU usage
            self.system_stats['cpu_percent'] = psutil.cpu_percent(interval=0.1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.system_stats['memory_percent'] = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            self.system_stats['disk_percent'] = disk.percent
            
            # Network usage
            net_io = psutil.net_io_counters()
            self.system_stats['network_sent'] = net_io.bytes_sent
            self.system_stats['network_recv'] = net_io.bytes_recv
            
            # Uptime
            self.system_stats['uptime'] = psutil.boot_time()
            
            # Timestamp
            self.system_stats['timestamp'] = datetime.datetime.now()
        except Exception as e:
            logger.exception(f"Error collecting system stats: {str(e)}")
            # Set safe defaults on error
            self.system_stats['cpu_percent'] = 0.0
            self.system_stats['memory_percent'] = 0.0
            self.system_stats['disk_percent'] = 0.0
            self.system_stats['network_sent'] = 0
            self.system_stats['network_recv'] = 0
            self.system_stats['uptime'] = 0
            self.system_stats['timestamp'] = datetime.datetime.now()
    
    def _collect_application_stats(self):
        """Collect application-specific statistics"""
        try:
            # These values will be updated by the application
            # Placeholder for now
            pass
        except Exception as e:
            logger.exception(f"Error collecting application stats: {str(e)}")
    
    def _update_history(self):
        """Update the history with current stats"""
        try:
            current_stats = {
                'system': self.system_stats.copy(),
                'application': self.application_stats.copy(),
                'timestamp': datetime.datetime.now()
            }
            self.history.append(current_stats)
            # Limit history size
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]
        except Exception as e:
            logger.exception(f"Error updating history: {str(e)}")
    
    def get_current_stats(self) -> Dict:
        """Get current system and application statistics"""
        return {
            'system': self.system_stats.copy(),
            'application': self.application_stats.copy(),
            'timestamp': datetime.datetime.now()
        }
    
    def get_history(self, limit: Optional[int] = None) -> List:
        """Get historical statistics"""
        if limit:
            return self.history[-limit:]
        return self.history.copy()
    
    def update_application_stats(self, **kwargs):
        """Update application-specific statistics"""
        self.application_stats.update(kwargs)
    
    def increment_error_count(self):
        """Increment error count"""
        self.application_stats['errors_count'] += 1
    
    def increment_warning_count(self):
        """Increment warning count"""
        self.application_stats['warnings_count'] += 1


# Create a global system monitor instance
system_monitor = SystemMonitor()
