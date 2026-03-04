"""
Communication Coordinator - Manages priority between write operations and polling
Ensures write operations wait for polling to complete to prevent communication conflicts
"""
import threading
import time
from threading import Lock, Condition
from queue import Queue, Empty


class CommunicationCoordinator:
    def __init__(self):
        self.write_queue = Queue()
        self.write_lock = Lock()
        self.poll_condition = Condition()
        self.write_condition = Condition()
        self.active_writes = 0
        self.active_polls = 0
        self.pending_writes = 0
        self._stop_flag = False
        
    def execute_write_operation(self, func, *args, **kwargs):
        """
        Execute a write operation, waiting for any active polling to complete first
        This prevents communication conflicts by ensuring only one operation at a time
        """
        # Wait for active polling to complete
        self._wait_for_poll_completion(timeout=2.0)
        
        with self.write_lock:
            self.active_writes += 1
            
        try:
            # Execute the write operation
            result = func(*args, **kwargs)
            return result
        finally:
            with self.write_lock:
                self.active_writes -= 1
                # Notify that a write operation has completed
                with self.poll_condition:
                    self.poll_condition.notify_all()
    
    def start_polling(self):
        """Mark that polling is starting"""
        with self.write_lock:
            self.active_polls += 1
    
    def end_polling(self):
        """Mark that polling has ended"""
        with self.write_lock:
            self.active_polls -= 1
            # Notify waiting writes that polling is done
            with self.write_condition:
                self.write_condition.notify_all()
    
    def can_poll(self):
        """Check if polling is allowed (no active writes)"""
        with self.write_lock:
            return self.active_writes == 0
    
    def can_write(self):
        """Check if writing is allowed (no active polls)"""
        with self.write_lock:
            return self.active_polls == 0
    
    def wait_for_write_completion(self, timeout=1.0):
        """Wait for active writes to complete before polling"""
        with self.poll_condition:
            start_time = time.time()
            while self.active_writes > 0 and (time.time() - start_time) < timeout:
                self.poll_condition.wait(timeout=0.01)  # Wait 10ms between checks
    
    def _wait_for_poll_completion(self, timeout=2.0):
        """Wait for active polling to complete before writing"""
        with self.write_condition:
            start_time = time.time()
            while self.active_polls > 0 and (time.time() - start_time) < timeout:
                self.write_condition.wait(timeout=0.01)  # Wait 10ms between checks
    
    def get_write_queue_size(self):
        """Get the number of pending write operations"""
        return self.write_queue.qsize()
    
    def stop_coordination(self):
        """Stop the coordination mechanism"""
        self._stop_flag = True
        with self.poll_condition:
            self.poll_condition.notify_all()
        with self.write_condition:
            self.write_condition.notify_all()


# Global coordinator instance
coordinator = CommunicationCoordinator()
