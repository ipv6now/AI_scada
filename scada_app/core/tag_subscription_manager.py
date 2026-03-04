"""
Tag Subscription Manager - 管理需要实时轮询的变量集合

实现按需轮询：只轮询当前需要的变量，减少数据流量
"""
from typing import Set, Dict, List, Optional, Callable
from enum import Enum
import threading


class SubscriptionType(Enum):
    """订阅类型"""
    HMI = "hmi"           # 当前HMI画面
    ALARM = "alarm"       # 报警监控
    LOG = "log"           # 历史日志
    MANUAL = "manual"     # 手动/调试


class TagSubscriptionManager:
    """
    变量订阅管理器 - 单例模式
    
    管理哪些变量需要实时轮询：
    - 当前HMI画面绑定的变量
    - 报警规则中使用的变量
    - 日志组态中配置的变量
    - 手动添加的调试变量
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        
        # 按订阅类型分组的变量集合
        # {SubscriptionType: Set[tag_name]}
        self._subscriptions: Dict[SubscriptionType, Set[str]] = {
            sub_type: set() for sub_type in SubscriptionType
        }
        
        # 变更回调函数列表
        self._callbacks: List[Callable[[Set[str]], None]] = []
        
        # 线程锁
        self._lock = threading.RLock()
        
        print("TagSubscriptionManager initialized")
    
    def subscribe(self, tag_names: List[str], sub_type: SubscriptionType):
        """
        订阅变量
        
        Args:
            tag_names: 变量名列表
            sub_type: 订阅类型
        """
        with self._lock:
            old_active = self.get_active_tags()
            
            for tag_name in tag_names:
                self._subscriptions[sub_type].add(tag_name)
            
            new_active = self.get_active_tags()
            
            # 如果有变化，通知回调
            if old_active != new_active:
                self._notify_callbacks(new_active)
                
        print(f"Subscribed {len(tag_names)} tags for {sub_type.value}")
    
    def unsubscribe(self, tag_names: List[str], sub_type: SubscriptionType):
        """
        取消订阅变量
        
        Args:
            tag_names: 变量名列表
            sub_type: 订阅类型
        """
        with self._lock:
            old_active = self.get_active_tags()
            
            for tag_name in tag_names:
                self._subscriptions[sub_type].discard(tag_name)
            
            new_active = self.get_active_tags()
            
            # 如果有变化，通知回调
            if old_active != new_active:
                self._notify_callbacks(new_active)
                
        print(f"Unsubscribed {len(tag_names)} tags from {sub_type.value}")
    
    def unsubscribe_all(self, sub_type: SubscriptionType):
        """
        取消某类型的所有订阅
        
        Args:
            sub_type: 订阅类型
        """
        with self._lock:
            old_active = self.get_active_tags()
            
            count = len(self._subscriptions[sub_type])
            self._subscriptions[sub_type].clear()
            
            new_active = self.get_active_tags()
            
            if old_active != new_active:
                self._notify_callbacks(new_active)
                
        print(f"Unsubscribed all {count} tags from {sub_type.value}")
    
    def get_active_tags(self) -> Set[str]:
        """
        获取所有需要实时轮询的变量
        
        Returns:
            活跃变量名集合
        """
        with self._lock:
            active = set()
            for tags in self._subscriptions.values():
                active.update(tags)
            return active
    
    def get_subscription_info(self) -> Dict[str, int]:
        """
        获取订阅统计信息
        
        Returns:
            各类型订阅数量
        """
        with self._lock:
            return {
                sub_type.value: len(tags) 
                for sub_type, tags in self._subscriptions.items()
            }
    
    def register_callback(self, callback: Callable[[Set[str]], None]):
        """
        注册活跃变量变更回调
        
        Args:
            callback: 回调函数，接收新的活跃变量集合
        """
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable[[Set[str]], None]):
        """
        注销回调
        
        Args:
            callback: 回调函数
        """
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
    
    def _notify_callbacks(self, active_tags: Set[str]):
        """通知所有回调"""
        for callback in self._callbacks:
            try:
                callback(active_tags)
            except Exception as e:
                print(f"Error in subscription callback: {e}")
    
    def is_tag_active(self, tag_name: str) -> bool:
        """
        检查变量是否处于活跃状态
        
        Args:
            tag_name: 变量名
            
        Returns:
            是否活跃
        """
        with self._lock:
            for tags in self._subscriptions.values():
                if tag_name in tags:
                    return True
            return False
    
    def clear_all(self):
        """清空所有订阅"""
        with self._lock:
            for sub_type in self._subscriptions:
                self._subscriptions[sub_type].clear()
            self._notify_callbacks(set())
        print("All subscriptions cleared")


# 全局实例
tag_subscription_manager = TagSubscriptionManager()
