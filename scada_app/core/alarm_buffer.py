"""
报警缓冲区模块
实现类似WinCC的报警缓冲区功能
- FIFO队列存储
- 溢出处理
- 多种报警类型支持
- 手动清除功能
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Set
from enum import Enum
import threading
import json


class AlarmBufferType(Enum):
    """报警缓冲区类型"""
    DISCRETE = "discrete"  # 离散量报警
    ANALOG = "analog"      # 模拟量报警
    SYSTEM = "system"      # 系统报警
    CONTROLLER = "controller"  # 控制器报警


@dataclass
class AlarmBufferEntry:
    """报警缓冲区条目"""
    alarm_id: str
    tag_name: str
    alarm_type: str
    alarm_type_name: str
    message: str
    timestamp: datetime
    status: str  # 活动、已确认、已恢复
    recover_time: Optional[datetime] = None
    acknowledge_time: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    buffer_type: AlarmBufferType = AlarmBufferType.DISCRETE
    priority: int = 0  # 优先级，0最低
    
    def to_dict(self):
        """转换为字典"""
        return {
            'alarm_id': self.alarm_id,
            'tag_name': self.tag_name,
            'alarm_type': self.alarm_type,
            'alarm_type_name': self.alarm_type_name,
            'message': self.message,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'status': self.status,
            'recover_time': self.recover_time.isoformat() if self.recover_time else None,
            'acknowledge_time': self.acknowledge_time.isoformat() if self.acknowledge_time else None,
            'acknowledged_by': self.acknowledged_by,
            'buffer_type': self.buffer_type.value,
            'priority': self.priority
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建"""
        return cls(
            alarm_id=data.get('alarm_id', ''),
            tag_name=data.get('tag_name', ''),
            alarm_type=data.get('alarm_type', ''),
            alarm_type_name=data.get('alarm_type_name', ''),
            message=data.get('message', ''),
            timestamp=datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else datetime.now(),
            status=data.get('status', '活动'),
            recover_time=datetime.fromisoformat(data['recover_time']) if data.get('recover_time') else None,
            acknowledge_time=datetime.fromisoformat(data['acknowledge_time']) if data.get('acknowledge_time') else None,
            acknowledged_by=data.get('acknowledged_by'),
            buffer_type=AlarmBufferType(data.get('buffer_type', 'discrete')),
            priority=data.get('priority', 0)
        )


class AlarmBuffer:
    """报警缓冲区（FIFO队列）"""
    
    def __init__(self, max_size: int = 1000, overflow_percent: float = 0.1):
        """
        初始化报警缓冲区
        
        Args:
            max_size: 最大容量
            overflow_percent: 溢出时清除百分比（0.1表示清除10%）
        """
        self.max_size = max_size
        self.overflow_percent = overflow_percent
        self._buffer: List[AlarmBufferEntry] = []
        self._lock = threading.Lock()
        self._callbacks = []
        
        # 统计信息
        self._total_added = 0
        self._total_removed = 0
        self._overflow_count = 0
    
    def add_alarm(self, entry: AlarmBufferEntry) -> bool:
        """
        添加报警到缓冲区
        
        Args:
            entry: 报警条目
            
        Returns:
            是否成功添加
        """
        with self._lock:
            # 检查是否溢出
            if len(self._buffer) >= self.max_size:
                self._handle_overflow()
            
            # 添加到缓冲区
            self._buffer.append(entry)
            self._total_added += 1
            
            # 触发回调
            self._trigger_callbacks(entry, 'add')
            
            return True
    
    def _handle_overflow(self):
        """处理溢出"""
        # 计算需要删除的数量
        remove_count = int(self.max_size * self.overflow_percent)
        remove_count = max(1, remove_count)  # 至少删除1个
        
        # 删除最旧的报警
        removed = self._buffer[:remove_count]
        self._buffer = self._buffer[remove_count:]
        
        self._total_removed += len(removed)
        self._overflow_count += 1
        
        # 触发回调
        for entry in removed:
            self._trigger_callbacks(entry, 'overflow')
    
    def get_alarms(self, 
                   alarm_types: Optional[Set[str]] = None,
                   status: Optional[str] = None,
                   limit: Optional[int] = None,
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None) -> List[AlarmBufferEntry]:
        """
        获取报警列表
        
        Args:
            alarm_types: 报警类型筛选
            status: 状态筛选
            limit: 数量限制
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            报警列表
        """
        with self._lock:
            result = self._buffer.copy()
        
        # 筛选
        if alarm_types:
            result = [a for a in result if a.alarm_type_name in alarm_types]
        
        if status:
            result = [a for a in result if a.status == status]
        
        if start_time:
            result = [a for a in result if a.timestamp >= start_time]
        
        if end_time:
            result = [a for a in result if a.timestamp <= end_time]
        
        # 限制数量
        if limit:
            result = result[:limit]
        
        return result
    
    def get_alarm_by_id(self, alarm_id: str) -> Optional[AlarmBufferEntry]:
        """根据ID获取报警（返回最新的条目）"""
        with self._lock:
            latest_entry = None
            latest_time = None
            for entry in self._buffer:
                if entry.alarm_id == alarm_id:
                    if latest_time is None or entry.timestamp > latest_time:
                        latest_entry = entry
                        latest_time = entry.timestamp
            return latest_entry
    
    def update_alarm(self, alarm_id: str, **kwargs):
        """更新报警（更新所有相同alarm_id的条目）"""
        with self._lock:
            updated_entries = []
            for entry in self._buffer:
                if entry.alarm_id == alarm_id:
                    for key, value in kwargs.items():
                        if hasattr(entry, key):
                            setattr(entry, key, value)
                    updated_entries.append(entry)
            
            # 触发回调（只触发一次）
            if updated_entries:
                for entry in updated_entries:
                    self._trigger_callbacks(entry, 'update')
    
    def acknowledge_alarm(self, alarm_id: str, user: str):
        """确认报警"""
        self.update_alarm(
            alarm_id,
            status='已确认',
            acknowledge_time=datetime.now(),
            acknowledged_by=user
        )
    
    def recover_alarm(self, alarm_id: str):
        """恢复报警"""
        self.update_alarm(
            alarm_id,
            status='已恢复',
            recover_time=datetime.now()
        )
    
    def clear_alarm(self, alarm_id: str):
        """清除单个报警"""
        with self._lock:
            for i, entry in enumerate(self._buffer):
                if entry.alarm_id == alarm_id:
                    removed = self._buffer.pop(i)
                    self._total_removed += 1
                    self._trigger_callbacks(removed, 'remove')
                    break
    
    def clear_alarms(self, 
                     alarm_types: Optional[Set[str]] = None,
                     status: Optional[str] = None):
        """清除报警"""
        with self._lock:
            if alarm_types is None and status is None:
                # 清除所有
                removed = self._buffer.copy()
                self._buffer.clear()
            else:
                # 筛选清除
                if alarm_types:
                    self._buffer = [a for a in self._buffer if a.alarm_type_name not in alarm_types]
                if status:
                    self._buffer = [a for a in self._buffer if a.status != status]
                removed = []
            
            self._total_removed += len(removed)
            for entry in removed:
                self._trigger_callbacks(entry, 'remove')
    
    def clear_all(self):
        """清除所有报警"""
        self.clear_alarms()
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            active_count = sum(1 for a in self._buffer if a.status == '活动')
            acknowledged_count = sum(1 for a in self._buffer if a.status == '已确认')
            recovered_count = sum(1 for a in self._buffer if a.status == '已恢复')
            
            return {
                'total_count': len(self._buffer),
                'active_count': active_count,
                'acknowledged_count': acknowledged_count,
                'recovered_count': recovered_count,
                'max_size': self.max_size,
                'total_added': self._total_added,
                'total_removed': self._total_removed,
                'overflow_count': self._overflow_count,
                'usage_percent': len(self._buffer) / self.max_size * 100 if self.max_size > 0 else 0
            }
    
    def register_callback(self, callback):
        """注册回调函数"""
        self._callbacks.append(callback)
    
    def unregister_callback(self, callback):
        """注销回调函数"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _trigger_callbacks(self, entry: AlarmBufferEntry, action: str):
        """触发回调"""
        for callback in self._callbacks:
            try:
                callback(entry, action)
            except Exception as e:
                print(f"报警缓冲区回调错误: {e}")
    
    def export_to_json(self) -> str:
        """导出为JSON"""
        with self._lock:
            data = [entry.to_dict() for entry in self._buffer]
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def import_from_json(self, json_str: str):
        """从JSON导入"""
        data = json.loads(json_str)
        with self._lock:
            self._buffer = [AlarmBufferEntry.from_dict(item) for item in data]
    
    def __len__(self):
        """获取当前数量"""
        with self._lock:
            return len(self._buffer)
    
    def __repr__(self):
        return f"AlarmBuffer(size={len(self)}/{self.max_size})"


class AlarmBufferManager:
    """报警缓冲区管理器"""
    
    def __init__(self):
        self._buffers: Dict[str, AlarmBuffer] = {}
        self._default_buffer = None
        self._lock = threading.Lock()
    
    def create_buffer(self, 
                      name: str,
                      max_size: int = 1000,
                      overflow_percent: float = 0.1) -> AlarmBuffer:
        """
        创建报警缓冲区
        
        Args:
            name: 缓冲区名称
            max_size: 最大容量
            overflow_percent: 溢出百分比
            
        Returns:
            报警缓冲区
        """
        with self._lock:
            if name in self._buffers:
                return self._buffers[name]
            
            buffer = AlarmBuffer(max_size, overflow_percent)
            self._buffers[name] = buffer
            
            # 设置为默认缓冲区
            if self._default_buffer is None:
                self._default_buffer = buffer
            
            return buffer
    
    def get_buffer(self, name: str) -> Optional[AlarmBuffer]:
        """获取报警缓冲区"""
        with self._lock:
            return self._buffers.get(name)
    
    def get_default_buffer(self) -> AlarmBuffer:
        """获取默认缓冲区"""
        if self._default_buffer is None:
            self.create_buffer('default')
        return self._default_buffer
    
    def remove_buffer(self, name: str):
        """移除报警缓冲区"""
        with self._lock:
            if name in self._buffers:
                del self._buffers[name]
                if self._default_buffer and self._default_buffer == self._buffers.get(name):
                    self._default_buffer = None
    
    def list_buffers(self) -> List[str]:
        """列出所有缓冲区名称"""
        with self._lock:
            return list(self._buffers.keys())
    
    def get_all_statistics(self) -> Dict[str, Dict]:
        """获取所有缓冲区的统计信息"""
        with self._lock:
            return {name: buffer.get_statistics() 
                    for name, buffer in self._buffers.items()}


# 全局报警缓冲区管理器
alarm_buffer_manager = AlarmBufferManager()
