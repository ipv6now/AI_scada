"""
Logger module for SCADA System - 异步日志实现

优化功能：
1. 使用 QueueHandler 实现异步日志
2. 批量写入提高性能
3. 自动日志轮转
"""
import logging
import logging.handlers
import os
import datetime
import queue
import threading
import time
from typing import Optional


class AsyncLogHandler(logging.Handler):
    """异步日志处理器 - 使用队列实现非阻塞日志写入"""
    
    def __init__(self, handler: logging.Handler, max_queue_size: int = 1000):
        super().__init__()
        self.handler = handler
        self.queue = queue.Queue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._process_logs, daemon=True)
        self._worker_thread.start()
        
    def emit(self, record):
        """将日志记录放入队列"""
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            # Queue is full, drop the oldest message
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(record)
            except queue.Empty:
                pass
    
    def _process_logs(self):
        """后台线程处理日志队列"""
        while not self._stop_event.is_set():
            try:
                record = self.queue.get(timeout=0.1)
                self.handler.emit(record)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing log: {e}")
    
    def close(self):
        """关闭处理器 - 等待队列处理完成"""
        self._stop_event.set()
        # Process remaining logs
        while not self.queue.empty():
            try:
                record = self.queue.get_nowait()
                self.handler.emit(record)
            except queue.Empty:
                break
            except Exception:
                break
        self.handler.close()
        super().close()


class BatchFileHandler(logging.Handler):
    """批量文件日志处理器"""
    
    def __init__(self, filename: str, batch_size: int = 50, flush_interval: float = 2.0):
        super().__init__()
        self.filename = filename
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.buffer = []
        self.last_flush = time.time()
        self._lock = threading.Lock()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    def emit(self, record):
        """添加日志记录到缓冲区"""
        with self._lock:
            self.buffer.append(self.format(record))
            
            # Check if we need to flush
            if len(self.buffer) >= self.batch_size:
                self._flush()
            elif time.time() - self.last_flush >= self.flush_interval:
                self._flush()
    
    def _flush(self):
        """将缓冲区写入文件"""
        if not self.buffer:
            return
        
        try:
            with open(self.filename, 'a', encoding='utf-8') as f:
                f.write('\n'.join(self.buffer) + '\n')
            self.buffer.clear()
            self.last_flush = time.time()
        except Exception as e:
            print(f"Error writing to log file: {e}")
    
    def close(self):
        """关闭处理器 - 刷新剩余日志"""
        with self._lock:
            self._flush()
        super().close()


class Logger:
    """Logger class for SCADA system - 异步实现"""
    
    def __init__(self, log_dir: str = None, async_mode: bool = True):
        self.log_dir = log_dir or os.path.join(os.path.dirname(__file__), "..", "logs")
        self.async_mode = async_mode
        self.logger = None
        self._handlers = []
        self._init_logger()
    
    def _init_logger(self):
        """Initialize the logger with async handlers"""
        # Create logs directory if it doesn't exist
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger("SCADA")
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Create file handler with rotation
        log_file = os.path.join(
            self.log_dir, 
            f"scada_{datetime.datetime.now().strftime('%Y-%m-%d')}.log"
        )
        
        if self.async_mode:
            # Use batch file handler for better performance
            file_handler = BatchFileHandler(log_file, batch_size=50, flush_interval=2.0)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            
            # Wrap with async handler
            async_handler = AsyncLogHandler(file_handler, max_queue_size=2000)
            async_handler.setLevel(logging.INFO)
            self.logger.addHandler(async_handler)
            self._handlers.append(async_handler)
            
            # Console handler (also async)
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(formatter)
            async_console = AsyncLogHandler(console_handler, max_queue_size=500)
            async_console.setLevel(logging.DEBUG)
            self.logger.addHandler(async_console)
            self._handlers.append(async_console)
        else:
            # Synchronous mode for debugging
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10 MB per file
                backupCount=5
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            self._handlers.append(file_handler)
            
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            self._handlers.append(console_handler)
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message"""
        if self.logger:
            self.logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message"""
        if self.logger:
            self.logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message"""
        if self.logger:
            self.logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message"""
        if self.logger:
            self.logger.error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Log critical message"""
        if self.logger:
            self.logger.critical(message, *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs):
        """Log exception message"""
        if self.logger:
            self.logger.exception(message, *args, **kwargs)
    
    def shutdown(self):
        """关闭日志系统 - 确保所有日志都被写入"""
        for handler in self._handlers:
            handler.close()
        logging.shutdown()
    
    def get_log_files(self):
        """Get list of log files in the log directory"""
        try:
            if os.path.exists(self.log_dir):
                log_files = []
                for filename in os.listdir(self.log_dir):
                    if filename.endswith('.log'):
                        log_files.append(os.path.join(self.log_dir, filename))
                return sorted(log_files, reverse=True)  # Most recent first
            return []
        except Exception as e:
            print(f"Error getting log files: {e}")
            return []


# Global logger instance
logger = Logger()


def get_logger() -> Logger:
    """Get the global logger instance"""
    return logger
