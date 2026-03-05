"""
异步通信协调器 - 使用 asyncio + 线程池实现非阻塞通信
"""
import asyncio
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, Any, List, Dict
from dataclasses import dataclass
from datetime import datetime
import time


class AsyncCommCoordinator:
    """
    异步通信协调器
    使用 asyncio 事件循环 + 线程池执行通信操作
    """
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._executor: Optional[ThreadPoolExecutor] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._future_queue: queue.Queue = queue.Queue()
        self._results: Dict[str, Any] = {}
        self._lock = threading.Lock()
        
    def start(self):
        """启动异步通信协调器"""
        if self._running:
            return
            
        self._running = True
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._thread = threading.Thread(target=self._event_loop_thread, daemon=True)
        self._thread.start()
        
        # 给事件循环一点启动时间
        time.sleep(0.1)
        
    def stop(self):
        """停止异步通信协调器"""
        self._running = False
        
        if self._loop:
            # 提交停止任务到事件循环
            future = asyncio.run_coroutine_threadsafe(self._stop_loop(), self._loop)
            try:
                future.result(timeout=2.0)
            except Exception:
                pass
                
        if self._executor:
            self._executor.shutdown(wait=False)
            
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            
    async def _stop_loop(self):
        """停止事件循环"""
        # 取消所有待处理的任务
        tasks = [t for t in asyncio.all_tasks(self._loop) if t is not asyncio.current_task(self._loop)]
        for task in tasks:
            task.cancel()
            
        # 等待一小段时间让任务完成取消
        await asyncio.sleep(0.1)
        
    def _event_loop_thread(self):
        """事件循环线程"""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()
        except Exception as e:
            print(f"AsyncCommCoordinator: Event loop error: {e}")
        finally:
            if self._loop:
                self._loop.close()
                
    def submit(self, func: Callable, *args, **kwargs) -> asyncio.Future:
        """
        提交同步函数到线程池执行
        
        Args:
            func: 要执行的同步函数
            *args, **kwargs: 函数参数
            
        Returns:
            asyncio.Future: 异步任务
        """
        if not self._running or not self._loop:
            raise RuntimeError("AsyncCommCoordinator is not running")
            
        return asyncio.run_coroutine_threadsafe(
            self._loop.run_in_executor(self._executor, func, *args, **kwargs),
            self._loop
        )
        
    async def submit_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        异步提交函数执行
        
        Args:
            func: 要执行的函数（可以是同步或异步）
            *args, **kwargs: 函数参数
            
        Returns:
            函数执行结果
        """
        if not self._running or not self._loop:
            raise RuntimeError("AsyncCommCoordinator is not running")
            
        return await self._loop.run_in_executor(self._executor, func, *args, **kwargs)
        
    def submit_to_queue(self, task_id: str, func: Callable, *args, **kwargs):
        """
        提交任务到队列（用于需要顺序执行的操作）
        
        Args:
            task_id: 任务ID
            func: 要执行的函数
            *args, **kwargs: 函数参数
        """
        self._future_queue.put((task_id, func, args, kwargs))
        
    def process_queue(self):
        """处理队列中的任务"""
        while not self._future_queue.empty():
            try:
                task_id, func, args, kwargs = self._future_queue.get_nowait()
                try:
                    result = func(*args, **kwargs)
                    with self._lock:
                        self._results[task_id] = result
                except Exception as e:
                    with self._lock:
                        self._results[task_id] = e
            except queue.Empty:
                break
                
    def get_result(self, task_id: str, timeout: float = 5.0) -> Any:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            timeout: 超时时间
            
        Returns:
            任务结果或 None
        """
        start_time = time.time()
        while True:
            with self._lock:
                if task_id in self._results:
                    result = self._results.pop(task_id)
                    if isinstance(result, Exception):
                        raise result
                    return result
                    
            if time.time() - start_time > timeout:
                return None
                
            time.sleep(0.01)
            
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
        
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'running': self._running,
            'queue_size': self._future_queue.qsize(),
            'executor_active': self._executor._work_queue.qsize() if self._executor else 0
        }


# 全局实例
async_comm_coordinator = AsyncCommCoordinator()


def async_run(coroutine):
    """
    在异步协调器中运行协程
    
    Args:
        coroutine: 协程对象
        
    Returns:
        协程结果
    """
    if not async_comm_coordinator.is_running():
        raise RuntimeError("AsyncCommCoordinator is not running")
        
    future = async_comm_coordinator.submit(lambda: coroutine)
    return future.result()
