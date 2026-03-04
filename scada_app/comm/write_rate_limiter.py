"""
Write Rate Limiter - Prevents excessive PLC write operations

Features:
- Minimum write interval (default 100ms)
- Write queue deduplication (keep only last value for same tag)
- Batch write optimization (merge multiple writes)
"""
import threading
import time
from collections import OrderedDict
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from queue import Queue, Empty


@dataclass
class WriteRequest:
    """Represents a write request to PLC"""
    tag_name: str
    value: Any
    timestamp: float = field(default_factory=time.time)
    callback: Optional[Callable[[bool], None]] = None
    
    def __eq__(self, other):
        """Two requests are equal if they target the same tag"""
        if isinstance(other, WriteRequest):
            return self.tag_name == other.tag_name
        return False
    
    def __hash__(self):
        return hash(self.tag_name)


class WriteRateLimiter:
    """
    写入限速器 - 防止过于频繁的PLC写入操作
    
    功能：
    1. 最小写入间隔（默认100ms）
    2. 写入队列去重（同一变量只保留最后一次写入）
    3. 批量写入优化（合并多个写入为一次批量操作）
    """
    
    def __init__(self, min_interval_ms: float = 200, batch_window_ms: float = 100):
        """
        Initialize write rate limiter
        
        Args:
            min_interval_ms: Minimum interval between writes (milliseconds)
            batch_window_ms: Time window for batching writes (milliseconds)
        """
        self.min_interval_ms = min_interval_ms
        self.batch_window_ms = batch_window_ms
        
        # Write queue - OrderedDict for deduplication while maintaining order
        self._write_queue: OrderedDict[str, WriteRequest] = OrderedDict()
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
            'deduplicated': 0,
            'batched_writes': 0,
            'individual_writes': 0,
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
            print(f"WriteRateLimiter started (min_interval={self.min_interval_ms}ms, batch_window={self.batch_window_ms}ms)")
    
    def stop(self):
        """Stop the write processing thread"""
        self._processing = False
        self._stop_event.set()
        if self._process_thread and self._process_thread.is_alive():
            self._process_thread.join(timeout=2)
        print("WriteRateLimiter stopped")
    
    def queue_write(self, tag_name: str, value: Any, 
                    callback: Optional[Callable[[bool], None]] = None) -> bool:
        """
        Queue a write request
        
        Args:
            tag_name: Tag name to write
            value: Value to write
            callback: Optional callback function(success: bool)
            
        Returns:
            True if queued successfully
        """
        request = WriteRequest(tag_name, value, callback=callback)
        
        with self._queue_lock:
            # Check if tag already in queue (deduplication)
            if tag_name in self._write_queue:
                # Replace with new request (keep only last value)
                old_request = self._write_queue[tag_name]
                self._write_queue[tag_name] = request
                with self._stats_lock:
                    self._stats['deduplicated'] += 1
                print(f"WriteRateLimiter: Deduplicated write for {tag_name} "
                      f"(old={old_request.value}, new={value})")
            else:
                self._write_queue[tag_name] = request
                
            with self._stats_lock:
                self._stats['total_requests'] += 1
        
        return True
    
    def _process_loop(self):
        """Main processing loop"""
        print(f"WriteRateLimiter: Process loop started for {id(self)}")
        while self._processing and not self._stop_event.is_set():
            try:
                # Wait for minimum interval
                self._wait_for_interval()
                
                # Collect writes within batch window
                writes = self._collect_batch()
                
                if writes:
                    print(f"WriteRateLimiter: Collected {len(writes)} writes to execute")
                    # Execute writes
                    self._execute_writes(writes)
                    
                    # Update last write time
                    with self._time_lock:
                        self._last_write_time = time.time()
                        
            except Exception as e:
                print(f"WriteRateLimiter: Error in process loop: {e}")
                time.sleep(0.01)  # Short sleep on error
        print(f"WriteRateLimiter: Process loop ended for {id(self)}")
    
    def _wait_for_interval(self):
        """Wait until minimum interval has passed since last write"""
        with self._time_lock:
            elapsed = (time.time() - self._last_write_time) * 1000
            wait_time = max(0, self.min_interval_ms - elapsed)
        
        if wait_time > 0:
            # Use stop_event to allow early exit
            self._stop_event.wait(timeout=wait_time / 1000)
    
    def _collect_batch(self) -> Dict[str, WriteRequest]:
        """
        Collect writes within batch window
        
        Returns:
            Dictionary of tag_name -> WriteRequest
        """
        writes = {}
        start_time = time.time()
        
        while (time.time() - start_time) * 1000 < self.batch_window_ms:
            with self._queue_lock:
                if self._write_queue:
                    # Get all current writes
                    writes.update(self._write_queue)
                    self._write_queue.clear()
                    break
            
            # Short sleep if queue is empty
            if not writes:
                self._stop_event.wait(timeout=0.01)  # 10ms
                
        return writes
    
    def _execute_writes(self, writes: Dict[str, WriteRequest]):
        """
        Execute write requests
        
        Args:
            writes: Dictionary of tag_name -> WriteRequest
        """
        if not self._write_executor:
            print("WriteRateLimiter: No write executor set!")
            return
        
        count = len(writes)
        
        if count > 1:
            # Batch write
            print(f"WriteRateLimiter: Executing batch write of {count} tags")
            with self._stats_lock:
                self._stats['batched_writes'] += 1
        else:
            with self._stats_lock:
                self._stats['individual_writes'] += 1
        
        # Execute each write
        for tag_name, request in writes.items():
            try:
                print(f"WriteRateLimiter: Executing write {tag_name} = {request.value}")
                success = self._write_executor(tag_name, request.value)
                print(f"WriteRateLimiter: Write result for {tag_name} = {success}")
                
                if request.callback:
                    try:
                        request.callback(success)
                    except Exception as e:
                        print(f"WriteRateLimiter: Callback error for {tag_name}: {e}")
                
                if not success:
                    with self._stats_lock:
                        self._stats['failed_writes'] += 1
                        
            except Exception as e:
                print(f"WriteRateLimiter: Error writing {tag_name}: {e}")
                with self._stats_lock:
                    self._stats['failed_writes'] += 1
                
                if request.callback:
                    try:
                        request.callback(False)
                    except Exception:
                        pass
    
    def get_stats(self) -> Dict[str, int]:
        """Get write statistics"""
        with self._stats_lock:
            return self._stats.copy()
    
    def clear_stats(self):
        """Clear statistics"""
        with self._stats_lock:
            for key in self._stats:
                self._stats[key] = 0
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        with self._queue_lock:
            return len(self._write_queue)
    
    def is_processing(self) -> bool:
        """Check if processor is running"""
        return self._processing


# Global instance (optional, can be per-connection)
_global_rate_limiter: Optional[WriteRateLimiter] = None
_global_lock = threading.Lock()


def get_global_rate_limiter() -> WriteRateLimiter:
    """Get or create global rate limiter instance"""
    global _global_rate_limiter
    with _global_lock:
        if _global_rate_limiter is None:
            _global_rate_limiter = WriteRateLimiter()
        return _global_rate_limiter
