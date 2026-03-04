"""
System Service Manager - Coordinates all background services in the SCADA system

优化功能：
1. 报警状态管理 - 避免重复报警
2. 报警确认和恢复机制
3. 批量数据日志写入
4. 异步日志队列
"""
import threading
import time
import queue
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from scada_app.architecture import DataType


class AlarmStatus(Enum):
    """报警状态"""
    NORMAL = "normal"           # 正常状态
    ACTIVE = "active"           # 报警激活（未确认）
    ACKNOWLEDGED = "acknowledged"  # 已确认但未恢复
    RECOVERED = "recovered"     # 已恢复


@dataclass
class AlarmState:
    """报警状态记录"""
    tag_name: str
    alarm_type: str
    status: AlarmStatus
    priority: str
    message: str
    first_trigger_time: datetime = field(default_factory=datetime.now)
    last_trigger_time: datetime = field(default_factory=datetime.now)
    acknowledge_time: Optional[datetime] = None
    recover_time: Optional[datetime] = None
    trigger_count: int = 1
    acknowledged_by: Optional[str] = None


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: datetime
    tag_name: str
    value: Any
    quality: str = "GOOD"


class BatchLogWriter:
    """批量日志写入器"""
    def __init__(self, batch_size: int = 100, flush_interval: float = 5.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.log_queue: queue.Queue = queue.Queue()
        self.buffer: List[LogEntry] = []
        self.last_flush_time = time.time()
        self._lock = threading.Lock()
        self._running = False
        self._writer_thread: Optional[threading.Thread] = None
        
    def start(self):
        """启动批量写入线程"""
        self._running = True
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()
    
    def stop(self):
        """停止批量写入线程"""
        self._running = False
        # Flush remaining logs
        self._flush_buffer()
        if self._writer_thread and self._writer_thread.is_alive():
            self._writer_thread.join(timeout=2)
    
    def add_log(self, entry: LogEntry):
        """添加日志到队列"""
        self.log_queue.put(entry)
    
    def _writer_loop(self):
        """批量写入循环"""
        while self._running:
            try:
                # Try to get log entry with timeout
                entry = self.log_queue.get(timeout=0.1)
                with self._lock:
                    self.buffer.append(entry)
                    
                    # Flush if buffer is full
                    if len(self.buffer) >= self.batch_size:
                        self._flush_buffer()
            except queue.Empty:
                # Check if we need to flush due to time interval
                with self._lock:
                    if self.buffer and (time.time() - self.last_flush_time) >= self.flush_interval:
                        self._flush_buffer()
    
    def _flush_buffer(self):
        """将缓冲区数据写入存储"""
        if not self.buffer:
            return
            
        logs_to_write = self.buffer.copy()
        self.buffer.clear()
        self.last_flush_time = time.time()
        
        # Write to storage (database/file)
        try:
            self._write_to_storage(logs_to_write)
        except Exception as e:
            print(f"Error writing logs to storage: {e}")
            # Put back to buffer for retry
            with self._lock:
                self.buffer.extend(logs_to_write)
    
    def _write_to_storage(self, logs: List[LogEntry]):
        """写入到存储 - 使用统一的存储管理器"""
        if not logs:
            return

        # Import here to avoid circular import
        from scada_app.core.data_storage_manager import data_storage_manager

        try:
            data_storage_manager.write_logs(logs)
        except Exception as e:
            print(f"Storage error: {e}")


class SystemServiceManager:
    """
    Manages all background services for the SCADA system including:
    - Alarm monitoring (with state management)
    - Data logging (with batch writing)
    - Event recording
    """
    def __init__(self, data_manager, plc_manager):
        self.data_manager = data_manager
        self.plc_manager = plc_manager
        self.running = False
        self.services_thread = None
        
        # Configuration
        self.check_interval = 1  # seconds
        self.alarm_callbacks = []
        self.logging_rules = []
        self.alarm_rules = []
        
        # Alarm state management
        self._alarm_states: Dict[str, AlarmState] = {}
        self._alarm_lock = threading.Lock()
        
        # Deadband configuration to prevent chattering
        self._last_alarm_values: Dict[str, float] = {}
        self._deadband_percent = 2.0  # 2% deadband
        
        # Batch log writer
        self._log_writer = BatchLogWriter(batch_size=50, flush_interval=3.0)
        
        # Lock for data logging to prevent concurrent access
        self._logging_lock = threading.Lock()
        
        # Track last cleanup time
        self._last_cleanup_time = 0
        self._cleanup_interval = 3600  # Cleanup once per hour
        
    def start_services(self):
        """Start all background services"""
        if not self.running:
            self.running = True
            # Start batch log writer
            self._log_writer.start()
            # Start main service thread
            self.services_thread = threading.Thread(target=self._service_loop, daemon=True)
            self.services_thread.start()
    
    def stop_services(self):
        """Stop all background services"""
        self.running = False
        # Stop batch log writer
        self._log_writer.stop()
        if self.services_thread and self.services_thread.is_alive():
            self.services_thread.join(timeout=2)
        print("System services stopped")
    
    def _service_loop(self):
        """Main service loop running in background thread"""
        while self.running:
            try:
                # Check for alarms
                self._check_alarms()
                
                # Log data if rules exist
                self._check_data_logging()
                
                # Cleanup old data periodically
                self._cleanup_old_data()
                
                # Sleep for the specified interval
                time.sleep(self.check_interval)
                
            except Exception as e:
                print(f"Error in system services: {str(e)}")
                time.sleep(self.check_interval)
    
    def _cleanup_old_data(self):
        """Clean up old data based on logging rules"""
        current_time = time.time()
        
        # Only cleanup once per hour
        if current_time - self._last_cleanup_time < self._cleanup_interval:
            return
        
        try:
            from scada_app.core.data_storage_manager import data_storage_manager
            
            # Find the minimum retention days across all rules
            min_retention_days = None
            for rule in self.logging_rules:
                if not rule.get('enabled', False):
                    continue
                
                retention_days = rule.get('storage_duration_days', 30)
                if min_retention_days is None or retention_days < min_retention_days:
                    min_retention_days = retention_days
            
            if min_retention_days and min_retention_days > 0:
                deleted = data_storage_manager.cleanup_old_data(min_retention_days)
                if deleted > 0:
                    print(f"Cleaned up {deleted} old data records")
            
            self._last_cleanup_time = current_time
            
        except Exception as e:
            print(f"Error cleaning up old data: {e}")
    
    def _check_alarms(self):
        """Check for alarm conditions with state management"""
        current_time = datetime.now()
        
        # Check alarms based on configured rules
        for rule in self.alarm_rules:
            if not rule.enabled:
                continue
            
            if rule.tag_name in self.data_manager.tags:
                tag = self.data_manager.tags[rule.tag_name]
                value = tag.value
                
                if value is None:
                    continue
                
                alarm_key = f"{rule.tag_name}_{rule.alarm_type}_{rule.condition}"
                
                # Handle different alarm types
                if rule.alarm_type == "LIMIT":
                    self._check_limit_alarm(rule, alarm_key, value, current_time)
        
        # Check for alarm recovery
        self._check_alarm_recovery(current_time)
    
    def _check_limit_alarm(self, rule, alarm_key: str, value: float, current_time: datetime):
        """检查限值报警"""
        is_triggered = False
        
        if rule.condition == "HIGH" and value > rule.threshold:
            is_triggered = True
        elif rule.condition == "LOW" and value < rule.threshold:
            is_triggered = True
        elif rule.condition == "HIGH_HIGH" and value > rule.threshold:
            is_triggered = True
        elif rule.condition == "LOW_LOW" and value < rule.threshold:
            is_triggered = True
        
        with self._alarm_lock:
            existing_state = self._alarm_states.get(alarm_key)
            
            if is_triggered:
                # Check deadband to prevent chattering
                if existing_state and existing_state.status in [AlarmStatus.ACTIVE, AlarmStatus.ACKNOWLEDGED]:
                    # Already in alarm state, update last trigger time
                    existing_state.last_trigger_time = current_time
                    existing_state.trigger_count += 1
                else:
                    # New alarm or recovered alarm
                    if existing_state and existing_state.status == AlarmStatus.RECOVERED:
                        # Re-trigger after recovery
                        existing_state.status = AlarmStatus.ACTIVE
                        existing_state.last_trigger_time = current_time
                        existing_state.trigger_count += 1
                    else:
                        # Brand new alarm
                        new_state = AlarmState(
                            tag_name=rule.tag_name,
                            alarm_type=f"{rule.alarm_type}_{rule.condition}",
                            status=AlarmStatus.ACTIVE,
                            priority=rule.priority,
                            message=rule.message,
                            first_trigger_time=current_time,
                            last_trigger_time=current_time
                        )
                        self._alarm_states[alarm_key] = new_state
                    
                    # Trigger alarm notification
                    self._trigger_alarm_notification(
                        rule.tag_name,
                        f"{rule.alarm_type}_{rule.condition}",
                        rule.message,
                        rule.priority,
                        is_new=True
                    )
            else:
                # Not triggered - check if we need to mark as recovered
                if existing_state and existing_state.status in [AlarmStatus.ACTIVE, AlarmStatus.ACKNOWLEDGED]:
                    # Check deadband before marking as recovered
                    if self._is_out_of_deadband(value, rule.threshold, rule.condition):
                        existing_state.status = AlarmStatus.RECOVERED
                        existing_state.recover_time = current_time
                        
                        # Notify recovery
                        self._trigger_alarm_notification(
                            rule.tag_name,
                            f"{rule.alarm_type}_{rule.condition}_RECOVERED",
                            f"{rule.message} - 已恢复",
                            rule.priority,
                            is_recovery=True
                        )
    
    def _is_out_of_deadband(self, value: float, threshold: float, condition: str) -> bool:
        """检查是否超出死区范围"""
        deadband = abs(threshold) * (self._deadband_percent / 100.0)
        
        if "HIGH" in condition:
            return value < (threshold - deadband)
        elif "LOW" in condition:
            return value > (threshold + deadband)
        return True
    
    def _check_alarm_recovery(self, current_time: datetime):
        """检查所有报警的恢复状态"""
        with self._alarm_lock:
            # Clean up old recovered alarms (keep for 1 hour)
            keys_to_remove = []
            for key, state in self._alarm_states.items():
                if state.status == AlarmStatus.RECOVERED and state.recover_time:
                    if (current_time - state.recover_time).total_seconds() > 3600:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._alarm_states[key]
    
    def _trigger_alarm_notification(self, tag_name: str, alarm_type: str, message: str, 
                                     priority: str = "MEDIUM", is_new: bool = False, 
                                     is_recovery: bool = False):
        """触发报警通知"""
        if is_new:
            print(f"🚨 NEW ALARM [{priority}]: {alarm_type} - {message}")
        elif is_recovery:
            print(f"✅ ALARM RECOVERED [{priority}]: {alarm_type} - {message}")
        else:
            print(f"🔔 ALARM [{priority}]: {alarm_type} - {message}")
        
        # Add to data manager alarms
        self.data_manager.raise_alarm(tag_name, alarm_type, message, priority)
        
        # Execute callbacks
        for callback in self.alarm_callbacks:
            try:
                callback(tag_name, alarm_type, message, priority, is_new, is_recovery)
            except Exception as e:
                print(f"Error in alarm callback: {str(e)}")
    
    def acknowledge_alarm(self, alarm_key: str, acknowledged_by: str = "operator") -> bool:
        """确认报警
        
        Args:
            alarm_key: 报警唯一标识
            acknowledged_by: 确认人
            
        Returns:
            bool: 是否成功确认
        """
        with self._alarm_lock:
            if alarm_key in self._alarm_states:
                state = self._alarm_states[alarm_key]
                if state.status == AlarmStatus.ACTIVE:
                    state.status = AlarmStatus.ACKNOWLEDGED
                    state.acknowledge_time = datetime.now()
                    state.acknowledged_by = acknowledged_by
                    print(f"✓ Alarm {alarm_key} acknowledged by {acknowledged_by}")
                    return True
        return False
    
    def get_active_alarms(self) -> List[AlarmState]:
        """获取所有活动报警（未恢复）"""
        with self._alarm_lock:
            return [
                state for state in self._alarm_states.values()
                if state.status in [AlarmStatus.ACTIVE, AlarmStatus.ACKNOWLEDGED]
            ]
    
    def get_alarm_history(self, limit: int = 100) -> List[AlarmState]:
        """获取报警历史"""
        with self._alarm_lock:
            sorted_alarms = sorted(
                self._alarm_states.values(),
                key=lambda x: x.first_trigger_time,
                reverse=True
            )
            return sorted_alarms[:limit]
    
    def _check_data_logging(self):
        """检查数据日志 - 使用批量写入"""
        if not self.logging_rules:
            return

        current_time = time.time()
        
        with self._logging_lock:
            for rule in self.logging_rules:
                if not rule.get('enabled', False):
                    continue

                tag_name = rule.get('tag_name')
                if not tag_name:
                    continue

                if tag_name not in self.data_manager.tags:
                    continue

                tag = self.data_manager.tags[tag_name]
                if tag.value is None:
                    continue

                # Check if we should log based on sample_rate (interval)
                log_interval = rule.get('sample_rate', rule.get('interval', 1.0))
                last_logged = getattr(tag, '_last_logged', 0)

                if current_time - last_logged >= log_interval:
                    # Create log entry and add to batch writer
                    entry = LogEntry(
                        timestamp=datetime.now(),
                        tag_name=tag_name,
                        value=tag.value,
                        quality=getattr(tag, 'quality', 'GOOD')
                    )
                    self._log_writer.add_log(entry)
                    setattr(tag, '_last_logged', current_time)
    
    def add_alarm_callback(self, callback):
        """Add a callback function to be called when alarms occur"""
        self.alarm_callbacks.append(callback)
    
    def set_alarm_rules(self, rules):
        """Set alarm rules"""
        self.alarm_rules = rules
        print(f"Alarm rules updated: {len(rules)} rules")
    
    def set_logging_rules(self, rules):
        """Set data logging rules"""
        # 去重：避免重复的规则
        unique_rules = []
        seen_tags = set()
        for rule in rules:
            tag_name = rule.get('tag_name')
            if tag_name and tag_name not in seen_tags:
                unique_rules.append(rule)
                seen_tags.add(tag_name)
        
        self.logging_rules = unique_rules


# Backward compatibility
AlarmConfig = None  # Remove old class, use AlarmRule instead
