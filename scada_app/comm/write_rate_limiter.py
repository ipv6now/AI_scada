"""
Write Rate Limiter - Prevents excessive PLC write operations

Features:
- Minimum write interval: 500ms (1 write per 500ms minimum)
- Directly discard writes that are too frequent
- For momentary buttons: if press-to-release < 500ms, wait 500ms before writing release
"""
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class WriteRequest:
    """Represents a write request to PLC"""
    tag_name: str
    value: Any
    timestamp: float = field(default_factory=time.time)
    callback: Optional[Callable[[bool], None]] = None


class WriteRateLimiter:
    """
    写入限速器 - 防止过于频繁的PLC写入操作
    
    规则：
    1. 最小写入间隔：500ms（每秒最多2次）
    2. 频率过高的直接丢弃
    3. 点动按钮：如果按下到松开 < 500ms，等待500ms后再写入松开动作
    """
    
    MIN_INTERVAL_MS = 500  # Minimum 500ms between writes
    
    def __init__(self):
        """Initialize write rate limiter with 500ms minimum interval"""
        self.min_interval_ms = self.MIN_INTERVAL_MS
        
        # Write queue - stores latest value for each tag
        self._write_queue: Dict[str, WriteRequest] = {}
        self._queue_lock = threading.Lock()
        
        # Last write time for rate limiting
        self._last_write_time = 0
        self._time_lock = threading.Lock()
        
        # Processing thread
        self._processing = False
        self._process_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Write executor function (to be set by PLCConnection)
        self._write_executor: Optional[Callable[[str, Any], bool]] = None
        
        # Statistics
        self._stats = {
            'total_requests': 0,
            'discarded': 0,
            'executed': 0,
            'failed_writes': 0
        }
        self._stats_lock = threading.Lock()
        
    def set_write_executor(self, executor: Callable[[str, Any], bool]):
        """
        Set the function that actually performs the write
        
        Args:
            executor: Function(tag_name, value) -> bool
        """
        self._write_executor = executor
    
    def start(self):
        """Start the write processing thread"""
        if not self._processing:
            self._processing = True
            self._stop_event.clear()
            self._process_thread = threading.Thread(target=self._process_loop, daemon=True)
            self._process_thread.start()
    
    def stop(self):
        """Stop the write processing thread"""
        self._processing = False
        self._stop_event.set()
        if self._process_thread and self._process_thread.is_alive():
            self._process_thread.join(timeout=2)
    
    def queue_write(self, tag_name: str, value: Any, 
                    callback: Optional[Callable[[bool], None]] = None) -> bool:
        """
        Queue a write request
        
        Args:
            tag_name: Tag name to write
            value: Value to write
            callback: Optional callback function(success: bool)
            
        Returns:
            True if request accepted, False if discarded due to rate limiting
        """
        current_time = time.time()
        
        with self._time_lock:
            elapsed = (current_time - self._last_write_time) * 1000
            min_required = self.min_interval_ms
        
        # Check if we need to wait
        if elapsed < min_required:
            # Too frequent, discard
            with self._stats_lock:
                self._stats['discarded'] += 1
            return False
        
        # Request is acceptable, add to queue
        request = WriteRequest(tag_name, value, timestamp=current_time, callback=callback)
        
        with self._queue_lock:
            # Replace with new request (keep only last value)
            self._write_queue[tag_name] = request
            
            with self._stats_lock:
                self._stats['total_requests'] += 1
        
        return True
    
    def _process_loop(self):
        """Main processing loop"""
        while self._processing and not self._stop_event.is_set():
            try:
                # Collect all writes from queue
                writes = self._collect_writes()
                
                if writes:
                    # Execute writes
                    self._execute_writes(writes)
                    
                    # Update last write time
                    with self._time_lock:
                        self._last_write_time = time.time()
                        
                # Wait a short time before checking again
                time.sleep(0.05)  # 50ms check interval
                
            except Exception:
                time.sleep(0.1)  # 100ms sleep on error
    
    def _collect_writes(self) -> Dict[str, WriteRequest]:
        """
        Collect all writes from queue
        
        Returns:
            Dictionary of tag_name -> WriteRequest
        """
        with self._queue_lock:
            writes = dict(self._write_queue)
            self._write_queue.clear()
        return writes
    
    def _execute_writes(self, writes: Dict[str, WriteRequest]):
        """
        Execute writes
        
        Args:
            writes: Dictionary of tag_name -> WriteRequest
        """
        if not self._write_executor:
            return
        
        for tag_name, request in writes.items():
            try:
                success = self._write_executor(tag_name, request.value)
                
                if request.callback:
                    try:
                        request.callback(success)
                    except Exception:
                        pass
                
                if success:
                    with self._stats_lock:
                        self._stats['executed'] += 1
                else:
                    with self._stats_lock:
                        self._stats['failed_writes'] += 1
                        
            except Exception:
                with self._stats_lock:
                    self._stats['failed_writes'] += 1
                
                if request.callback:
                    try:
                        request.callback(False)
                    except Exception:
                        pass
    
    def is_processing(self) -> bool:
        """Check if the processing thread is running"""
        return self._processing
    
    def get_stats(self) -> Dict[str, int]:
        """Get write statistics"""
        with self._stats_lock:
            return self._stats.copy()
    
    def clear_stats(self):
        """Clear statistics"""
        with self._stats_lock:
            for key in self._stats:
                self._stats[key] = 0
