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
    """报警状态"""
    tag_name: str
    alarm_type: str
    status: AlarmStatus
    alarm_type_name: str  # 改为报警类型名称
    message: str
    alarm_id: Optional[str] = None  # 直接存储报警ID
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
    def __init__(self, data_manager, plc_manager, config_manager=None):
        self.data_manager = data_manager
        self.plc_manager = plc_manager
        self.config_manager = config_manager
        self.running = False
        self.services_thread = None
        
        # Configuration
        self.check_interval = 1  # seconds
        self.alarm_callbacks = []
        self.logging_rules = []
        self.alarm_rules = []
        
        # Load alarm rules from config manager if available
        self._load_alarm_rules_from_config()
        
        # Alarm state management
        self._alarm_states: Dict[str, AlarmState] = {}
        self._tag_states: Dict[str, dict] = {}  # 存储标签状态历史
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
                # 不输出未启用规则的调试信息
                continue
            
            if rule.tag_name in self.data_manager.tags:
                tag = self.data_manager.tags[rule.tag_name]
                value = tag.value
                
                if value is None:
                    # 不输出值为None的调试信息
                    continue
                
                # 处理位偏移
                original_value = value
                if hasattr(rule, 'bit_offset') and rule.bit_offset is not None:
                    try:
                        # 提取指定位的值
                        if isinstance(value, (int, float)):
                            bit_value = (int(value) >> rule.bit_offset) & 1
                            value = bit_value
                            alarm_key = f"{rule.tag_name}_{rule.alarm_type}_{rule.condition}_bit{rule.bit_offset}"
                        else:
                            alarm_key = f"{rule.tag_name}_{rule.alarm_type}_{rule.condition}"
                    except (ValueError, TypeError) as e:
                        alarm_key = f"{rule.tag_name}_{rule.alarm_type}_{rule.condition}"
                else:
                    alarm_key = f"{rule.tag_name}_{rule.alarm_type}_{rule.condition}"
                
                # Handle different alarm types
                if rule.alarm_type == "限值" or rule.alarm_type == "LIMIT":
                    self._check_limit_alarm(rule, alarm_key, value, current_time)
                elif rule.alarm_type == "状态变化":
                    self._check_state_change_alarm(rule, alarm_key, value, current_time)
                elif rule.alarm_type == "变化率":
                    self._check_rate_alarm(rule, alarm_key, value, current_time)
            else:
                # 不输出变量不存在的调试信息
                pass
        
        # Check for alarm recovery
        self._check_alarm_recovery(current_time)
    
    def _check_limit_alarm(self, rule, alarm_key: str, value: float, current_time: datetime):
        """检查限值报警"""
        is_triggered = False
        
        # 支持中英文条件
        if (rule.condition == "HIGH" or rule.condition == "高") and value > rule.threshold:
            is_triggered = True
            print(f"[ALARM DEBUG] 限值报警触发: {alarm_key}, 值={value} > 阈值={rule.threshold}")
        elif (rule.condition == "LOW" or rule.condition == "低") and value < rule.threshold:
            is_triggered = True
            print(f"[ALARM DEBUG] 限值报警触发: {alarm_key}, 值={value} < 阈值={rule.threshold}")
        elif (rule.condition == "HIGH_HIGH" or rule.condition == "很高") and value > rule.threshold:
            is_triggered = True
            print(f"[ALARM DEBUG] 限值报警触发: {alarm_key}, 值={value} > 阈值={rule.threshold}")
        elif (rule.condition == "LOW_LOW" or rule.condition == "很低") and value < rule.threshold:
            is_triggered = True
            print(f"[ALARM DEBUG] 限值报警触发: {alarm_key}, 值={value} < 阈值={rule.threshold}")
        else:
            # 不输出未触发报警的调试信息
            pass
        
        with self._alarm_lock:
            existing_state = self._alarm_states.get(alarm_key)
            
            if is_triggered:
                # Check deadband to prevent chattering
                if existing_state and existing_state.status in [AlarmStatus.ACTIVE, AlarmStatus.ACKNOWLEDGED]:
                    # Already in alarm state, update last trigger time
                    existing_state.last_trigger_time = current_time
                    existing_state.trigger_count += 1
                    print(f"[ALARM DEBUG] 限值报警更新: {alarm_key}, 触发次数={existing_state.trigger_count}")
                else:
                    # New alarm or recovered alarm
                    if existing_state and existing_state.status == AlarmStatus.RECOVERED:
                        # Re-trigger after recovery
                        existing_state.status = AlarmStatus.ACTIVE
                        existing_state.last_trigger_time = current_time
                        existing_state.trigger_count += 1
                        print(f"[ALARM DEBUG] 限值报警重新触发: {alarm_key}, 恢复后重新报警")
                    else:
                        # Brand new alarm
                        new_state = AlarmState(
                            tag_name=rule.tag_name,
                            alarm_type=f"{rule.alarm_type}_{rule.condition}",
                            status=AlarmStatus.ACTIVE,
                            alarm_type_name=rule.alarm_type_name,  # 改为报警类型名称
                            message=rule.message,
                            alarm_id=rule.alarm_id,  # 直接设置报警ID
                            first_trigger_time=current_time,
                            last_trigger_time=current_time
                        )
                        self._alarm_states[alarm_key] = new_state
                        print(f"[ALARM DEBUG] 限值报警新触发: {alarm_key}, 报警类型={rule.alarm_type_name}, 消息={rule.message}")
                    
                    # Trigger alarm notification
                    self._trigger_alarm_notification(
                        rule.tag_name,
                        f"{rule.alarm_type}_{rule.condition}",
                        rule.message,
                        rule.alarm_type_name,  # 改为报警类型名称
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
                            rule.alarm_type_name,  # 改为报警类型名称
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
    
    def _check_state_change_alarm(self, rule, alarm_key: str, value: float, current_time: datetime):
        """检查状态变化报警（开关量报警）"""
        is_triggered = False
        
        # 获取当前值的历史状态
        if alarm_key not in self._tag_states:
            self._tag_states[alarm_key] = {
                'last_value': value,
                'last_change_time': current_time
            }
            print(f"[ALARM DEBUG] 状态变化报警初始化: {alarm_key}, 初始值={value}")
        
        last_value = self._tag_states[alarm_key]['last_value']
        
        # 检查状态变化条件
        if rule.condition == "假变真" and last_value == 0 and value == 1:
            is_triggered = True
            print(f"[ALARM DEBUG] 状态变化报警触发: {alarm_key}, 假变真 (0→1)")
        elif rule.condition == "真变假" and last_value == 1 and value == 0:
            is_triggered = True
            print(f"[ALARM DEBUG] 状态变化报警触发: {alarm_key}, 真变假 (1→0)")
        elif rule.condition == "变化" and last_value != value:
            is_triggered = True
            print(f"[ALARM DEBUG] 状态变化报警触发: {alarm_key}, 值变化 ({last_value}→{value})")
        else:
            # 不输出未触发报警的调试信息
            pass
        
        # 更新历史状态
        if last_value != value:
            self._tag_states[alarm_key]['last_value'] = value
            self._tag_states[alarm_key]['last_change_time'] = current_time
            print(f"[ALARM DEBUG] 状态变化报警更新历史: {alarm_key}, 新值={value}")
        
        with self._alarm_lock:
            existing_state = self._alarm_states.get(alarm_key)
            
            if is_triggered:
                if existing_state and existing_state.status in [AlarmStatus.ACTIVE, AlarmStatus.ACKNOWLEDGED]:
                    # 已经处于报警状态，更新最后触发时间
                    existing_state.last_trigger_time = current_time
                    existing_state.trigger_count += 1
                    print(f"[ALARM DEBUG] 状态变化报警更新: {alarm_key}, 触发次数={existing_state.trigger_count}")
                else:
                    # 新报警或恢复后重新触发
                    if existing_state and existing_state.status == AlarmStatus.RECOVERED:
                        # 恢复后重新触发
                        existing_state.status = AlarmStatus.ACTIVE
                        existing_state.last_trigger_time = current_time
                        existing_state.trigger_count += 1
                        print(f"[ALARM DEBUG] 状态变化报警重新触发: {alarm_key}, 恢复后重新报警")
                    else:
                        # 全新报警
                        new_state = AlarmState(
                            tag_name=rule.tag_name,
                            alarm_type=f"{rule.alarm_type}_{rule.condition}",
                            status=AlarmStatus.ACTIVE,
                            alarm_type_name=rule.alarm_type_name,  # 改为报警类型名称
                            message=rule.message,
                            alarm_id=rule.alarm_id,  # 直接设置报警ID
                            first_trigger_time=current_time,
                            last_trigger_time=current_time
                        )
                        self._alarm_states[alarm_key] = new_state
                        print(f"[ALARM DEBUG] 状态变化报警新触发: {alarm_key}, 报警类型={rule.alarm_type_name}, 消息={rule.message}")
                    
                    # 触发报警通知
                    self._trigger_alarm_notification(
                        rule.tag_name,
                        f"{rule.alarm_type}_{rule.condition}",
                        rule.message,
                        rule.alarm_type_name,  # 改为报警类型名称
                        is_new=True
                    )
            else:
                # 未触发 - 检查是否需要标记为恢复
                if existing_state and existing_state.status in [AlarmStatus.ACTIVE, AlarmStatus.ACKNOWLEDGED]:
                    # 对于状态变化报警，根据条件检查恢复
                    if (rule.condition == "FALSE_TO_TRUE" or rule.condition == "假变真") and value == 0:
                        # 假变真报警，当值变为0时恢复
                        existing_state.status = AlarmStatus.RECOVERED
                        existing_state.recover_time = current_time
                        print(f"[ALARM DEBUG] 状态变化报警恢复: {alarm_key}, 真变假 (1→0)")
                        
                        # 触发恢复通知
                        self._trigger_alarm_notification(
                            rule.tag_name,
                            f"{rule.alarm_type}_{rule.condition}_RECOVERED",
                            f"{rule.message} - 已恢复",
                            rule.alarm_type_name,  # 改为报警类型名称
                            is_recovery=True
                        )
                    elif (rule.condition == "TRUE_TO_FALSE" or rule.condition == "真变假") and value == 1:
                        # 真变假报警，当值变为1时恢复
                        existing_state.status = AlarmStatus.RECOVERED
                        existing_state.recover_time = current_time
                        print(f"[ALARM DEBUG] 状态变化报警恢复: {alarm_key}, 假变真 (0→1)")
                        
                        # 触发恢复通知
                        self._trigger_alarm_notification(
                            rule.tag_name,
                            f"{rule.alarm_type}_{rule.condition}_RECOVERED",
                            f"{rule.message} - 已恢复",
                            rule.alarm_type_name,  # 改为报警类型名称
                            is_recovery=True
                        )
    
    def _check_rate_alarm(self, rule, alarm_key: str, value: float, current_time: datetime):
        """检查变化率报警"""
        is_triggered = False
        
        # 获取历史值用于计算变化率
        if alarm_key not in self._tag_states:
            self._tag_states[alarm_key] = {
                'last_value': value,
                'last_time': current_time,
                'rate': 0.0
            }
            print(f"[ALARM DEBUG] 变化率报警初始化: {alarm_key}, 初始值={value}")
        
        last_value = self._tag_states[alarm_key]['last_value']
        last_time = self._tag_states[alarm_key]['last_time']
        
        # 计算变化率（单位：每秒）
        time_diff = (current_time - last_time).total_seconds()
        if time_diff > 0:
            rate = (value - last_value) / time_diff
            self._tag_states[alarm_key]['rate'] = rate
            
            print(f"[ALARM DEBUG] 变化率计算: {alarm_key}, 上次值={last_value}, 当前值={value}, 时间差={time_diff:.2f}s, 变化率={rate:.4f}/s")
            
            # 检查变化率条件
            if rule.condition == "正" and rate > rule.threshold:
                is_triggered = True
                print(f"[ALARM DEBUG] 变化率报警触发: {alarm_key}, 正变化率 {rate:.4f}/s > 阈值={rule.threshold}")
            elif rule.condition == "负" and rate < -rule.threshold:
                is_triggered = True
                print(f"[ALARM DEBUG] 变化率报警触发: {alarm_key}, 负变化率 {rate:.4f}/s < 阈值={-rule.threshold}")
            else:
                # 不输出未触发报警的调试信息
                pass
        else:
            # 不输出时间差为0的调试信息
            pass
        
        # 更新历史状态
        self._tag_states[alarm_key]['last_value'] = value
        self._tag_states[alarm_key]['last_time'] = current_time
        
        with self._alarm_lock:
            existing_state = self._alarm_states.get(alarm_key)
            
            if is_triggered:
                if existing_state and existing_state.status in [AlarmStatus.ACTIVE, AlarmStatus.ACKNOWLEDGED]:
                    # 已经处于报警状态，更新最后触发时间
                    existing_state.last_trigger_time = current_time
                    existing_state.trigger_count += 1
                    print(f"[ALARM DEBUG] 变化率报警更新: {alarm_key}, 触发次数={existing_state.trigger_count}")
                else:
                    # 新报警或恢复后重新触发
                    if existing_state and existing_state.status == AlarmStatus.RECOVERED:
                        # 恢复后重新触发
                        existing_state.status = AlarmStatus.ACTIVE
                        existing_state.last_trigger_time = current_time
                        existing_state.trigger_count += 1
                        print(f"[ALARM DEBUG] 变化率报警重新触发: {alarm_key}, 恢复后重新报警")
                    else:
                        # 全新报警
                        new_state = AlarmState(
                            tag_name=rule.tag_name,
                            alarm_type=f"{rule.alarm_type}_{rule.condition}",
                            status=AlarmStatus.ACTIVE,
                            alarm_type_name=rule.alarm_type_name,  # 改为报警类型名称
                            message=rule.message,
                            alarm_id=rule.alarm_id,  # 直接设置报警ID
                            first_trigger_time=current_time,
                            last_trigger_time=current_time
                        )
                        self._alarm_states[alarm_key] = new_state
                        print(f"[ALARM DEBUG] 变化率报警新触发: {alarm_key}, 报警类型={rule.alarm_type_name}, 消息={rule.message}")
                    
                    # 触发报警通知
                    self._trigger_alarm_notification(
                        rule.tag_name,
                        f"{rule.alarm_type}_{rule.condition}",
                        rule.message,
                        rule.alarm_type_name,  # 改为报警类型名称
                        is_new=True
                    )
            else:
                # 未触发 - 检查是否需要标记为恢复
                if existing_state and existing_state.status in [AlarmStatus.ACTIVE, AlarmStatus.ACKNOWLEDGED]:
                    # 检查是否超出死区
                    if abs(self._tag_states[alarm_key]['rate']) < abs(rule.threshold) * 0.8:
                        existing_state.status = AlarmStatus.RECOVERED
                        existing_state.recover_time = current_time
                        
                        # 通知恢复
                        self._trigger_alarm_notification(
                            rule.tag_name,
                            f"{rule.alarm_type}_{rule.condition}_RECOVERED",
                            f"{rule.message} - 已恢复",
                            rule.alarm_type_name,  # 改为报警类型名称
                            is_recovery=True
                        )
    
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
                                     alarm_type_name: str = "中", is_new: bool = False, 
                                     is_recovery: bool = False):
        """触发报警通知"""
        if is_new:
            print(f"🚨 NEW ALARM [{alarm_type_name}]: {alarm_type} - {message}")
        elif is_recovery:
            print(f"✅ ALARM RECOVERED [{alarm_type_name}]: {alarm_type} - {message}")
        else:
            print(f"🔔 ALARM [{alarm_type_name}]: {alarm_type} - {message}")
        
        # Add to data manager alarms
        self.data_manager.raise_alarm(tag_name, alarm_type, message, alarm_type_name)
        
        # Execute callbacks
        for callback in self.alarm_callbacks:
            try:
                callback(tag_name, alarm_type, message, alarm_type_name, is_new, is_recovery)
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
    
    def _load_alarm_rules_from_config(self):
        """Load alarm rules from config manager"""
        if not self.config_manager:
            return
        
        if hasattr(self.config_manager, 'alarm_rules') and self.config_manager.alarm_rules:
            try:
                # Convert dictionary rules to AlarmRule objects
                from scada_app.hmi.alarm_config_new import AlarmRule
                alarm_rules = []
                # 为报警规则生成唯一的报警ID（如果不存在）
                used_alarm_ids = set()
                next_alarm_id = 1
                
                for rule_data in self.config_manager.alarm_rules:
                    # 调试输出：检查配置数据中的alarm_id
                    print(f"[DEBUG] 加载报警规则: tag={rule_data.get('tag_name')}, alarm_id={rule_data.get('alarm_id')}")
                    
                    # 获取或生成报警ID
                    alarm_id = rule_data.get('alarm_id')
                    if alarm_id is None:
                        # 自动生成唯一的报警ID
                        while next_alarm_id in used_alarm_ids:
                            next_alarm_id += 1
                        alarm_id = next_alarm_id
                        next_alarm_id += 1
                        print(f"[DEBUG] 为规则自动生成报警ID: {alarm_id}")
                    
                    used_alarm_ids.add(alarm_id)
                    
                    rule = AlarmRule(
                        tag_name=rule_data.get('tag_name', ''),
                        alarm_type=rule_data.get('alarm_type', '状态变化'),
                        condition=rule_data.get('condition', '假变真'),
                        threshold=rule_data.get('threshold', 0.0),
                        message=rule_data.get('message', ''),
                        enabled=rule_data.get('enabled', True),
                        alarm_type_name=rule_data.get('alarm_type_name', rule_data.get('priority', '中')),  # 兼容旧数据
                        bit_offset=rule_data.get('bit_offset', None),
                        alarm_id=alarm_id  # 使用生成或已有的报警ID
                    )
                    alarm_rules.append(rule)
                
                self.alarm_rules = alarm_rules
                print(f"[ALARM] 从配置管理器加载 {len(alarm_rules)} 条报警规则")
            except Exception as e:
                print(f"[ALARM] 从配置管理器加载报警规则失败: {e}")
    
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
