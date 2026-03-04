"""
数据存储管理器 - 统一管理CSV、SQLite、SQL Server三种存储方式
"""
import csv
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class LogEntry:
    """日志条目数据类"""
    timestamp: datetime
    tag_name: str
    value: Any
    quality: str = "GOOD"


class BaseStorage:
    """存储基类"""
    
    def write_logs(self, logs: List[LogEntry]) -> bool:
        """写入日志条目"""
        raise NotImplementedError
    
    def query_logs(self, tag_name: str, start_time: datetime, end_time: datetime, limit: int = 1000) -> List[Dict[str, Any]]:
        """查询日志条目"""
        raise NotImplementedError
    
    def cleanup_old_data(self, retention_days: int) -> int:
        """清理旧数据"""
        raise NotImplementedError


class CSVStorage(BaseStorage):
    """CSV文件存储"""
    
    def __init__(self, base_dir: str = "data_logs"):
        self.base_dir = base_dir
        self._ensure_base_dir()
    
    def _ensure_base_dir(self):
        """确保基础目录存在"""
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
    
    def _get_file_path(self, date: datetime) -> str:
        """获取文件路径"""
        date_str = date.strftime("%Y-%m-%d")
        return os.path.join(self.base_dir, f"data_logs_{date_str}.csv")
    
    def write_logs(self, logs: List[LogEntry]) -> bool:
        """写入日志到CSV文件"""
        if not logs:
            return True
        
        try:
            file_path = self._get_file_path(logs[0].timestamp)
            file_exists = os.path.exists(file_path)
            
            # Use utf-8-sig for Excel compatibility (UTF-8 with BOM)
            encoding = 'utf-8-sig'
            
            with open(file_path, 'a', newline='', encoding=encoding) as f:
                writer = csv.writer(f)
                
                if not file_exists:
                    writer.writerow(['timestamp', 'tag_name', 'value', 'quality'])
                
                for entry in logs:
                    writer.writerow([
                        entry.timestamp.isoformat(),
                        entry.tag_name,
                        str(entry.value),
                        entry.quality
                    ])
            
            return True
        except Exception as e:
            print(f"CSV storage error: {e}")
            return False
    
    def query_logs(self, tag_name: str, start_time: datetime, end_time: datetime, limit: int = 1000) -> List[Dict[str, Any]]:
        """查询CSV日志"""
        results = []
        
        try:
            current_date = start_time.date()
            end_date = end_time.date()
            
            while current_date <= end_date:
                file_path = os.path.join(self.base_dir, f"data_logs_{current_date.strftime('%Y-%m-%d')}.csv")
                
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            try:
                                ts = datetime.fromisoformat(row['timestamp'])
                                if start_time <= ts <= end_time and row['tag_name'] == tag_name:
                                    results.append({
                                        'timestamp': ts,
                                        'tag_name': row['tag_name'],
                                        'tag_value': row['value'],
                                        'quality': row['quality']
                                    })
                                    
                                    if len(results) >= limit:
                                        return results
                            except:
                                pass
                
                # Use timedelta to safely increment date
                from datetime import timedelta
                current_date = current_date + timedelta(days=1)
            
            return results
        except Exception as e:
            print(f"CSV query error: {e}")
            return []
    
    def cleanup_old_data(self, retention_days: int) -> int:
        """清理旧CSV文件"""
        deleted_count = 0
        try:
            from datetime import timedelta
            cutoff_date = datetime.now().date() - timedelta(days=retention_days)
            
            if os.path.exists(self.base_dir):
                for filename in os.listdir(self.base_dir):
                    if filename.startswith("data_logs_") and filename.endswith(".csv"):
                        try:
                            date_str = filename[10:-4]
                            file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                            if file_date < cutoff_date:
                                file_path = os.path.join(self.base_dir, filename)
                                os.remove(file_path)
                                deleted_count += 1
                        except:
                            pass
            
            return deleted_count
        except Exception as e:
            print(f"CSV cleanup error: {e}")
            return 0


class SQLiteStorage(BaseStorage):
    """SQLite数据库存储"""
    
    def __init__(self, db_path: str = "data_logs.db"):
        self.db_path = db_path
        self._initialize_database()
    
    def _initialize_database(self):
        """初始化数据库表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    tag_name TEXT NOT NULL,
                    tag_value TEXT NOT NULL,
                    quality TEXT NOT NULL DEFAULT 'GOOD'
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_data_logs_timestamp ON data_logs(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_data_logs_tag_name ON data_logs(tag_name)
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"SQLite init error: {e}")
    
    def write_logs(self, logs: List[LogEntry]) -> bool:
        """写入日志到SQLite"""
        if not logs:
            return True
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for entry in logs:
                cursor.execute("""
                    INSERT INTO data_logs (timestamp, tag_name, tag_value, quality)
                    VALUES (?, ?, ?, ?)
                """, (
                    entry.timestamp.isoformat(),
                    entry.tag_name,
                    str(entry.value),
                    entry.quality
                ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"SQLite storage error: {e}")
            return False
    
    def query_logs(self, tag_name: str, start_time: datetime, end_time: datetime, limit: int = 1000) -> List[Dict[str, Any]]:
        """查询SQLite日志"""
        results = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT timestamp, tag_name, tag_value, quality
                FROM data_logs
                WHERE tag_name = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (tag_name, start_time.isoformat(), end_time.isoformat(), limit))
            
            for row in cursor.fetchall():
                results.append({
                    'timestamp': datetime.fromisoformat(row[0]),
                    'tag_name': row[1],
                    'tag_value': row[2],
                    'quality': row[3]
                })
            
            conn.close()
            return results
        except Exception as e:
            print(f"SQLite query error: {e}")
            return []
    
    def cleanup_old_data(self, retention_days: int) -> int:
        """清理旧SQLite数据"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM data_logs
                WHERE timestamp < ?
            """, (cutoff_date.isoformat(),))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            return deleted_count
        except Exception as e:
            print(f"SQLite cleanup error: {e}")
            return 0


class SQLServerStorage(BaseStorage):
    """SQL Server存储（使用现有sql_server_manager）"""
    
    def __init__(self):
        from scada_app.core.sql_server_manager import sql_server_manager
        self.sql_manager = sql_server_manager
        self._connection_attempted = False
        self._last_connect_time = 0
        self._connect_interval = 60
    
    def _ensure_connection(self) -> bool:
        """确保数据库已连接"""
        import time
        current_time = time.time()
        
        if self.sql_manager.connection:
            return True
        
        if self._connection_attempted:
            if current_time - self._last_connect_time < self._connect_interval:
                return False
        
        self._connection_attempted = True
        self._last_connect_time = current_time
        try:
            if self.sql_manager.connect():
                return True
            else:
                return False
        except Exception:
            return False
    
    def write_logs(self, logs: List[LogEntry]) -> bool:
        """写入日志到SQL Server"""
        if not logs:
            return True
        
        if not self._ensure_connection():
            return False
        
        try:
            success_count = 0
            for entry in logs:
                if self.sql_manager.log_data(
                    tag_name=entry.tag_name,
                    tag_value=entry.value,
                    tag_type=self._get_tag_type(entry.value),
                    quality=192 if entry.quality == "GOOD" else 0
                ):
                    success_count += 1
            return success_count > 0
        except Exception:
            return False
    
    def _get_tag_type(self, value) -> str:
        """根据值类型返回标签类型"""
        if isinstance(value, bool):
            return "bool"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "float"
        else:
            return "string"
    
    def query_logs(self, tag_name: str, start_time: datetime, end_time: datetime, limit: int = 1000) -> List[Dict[str, Any]]:
        """查询SQL Server日志"""
        if not self._ensure_connection():
            return []
        return self.sql_manager.query_log_data(tag_name, start_time, end_time, limit)
    
    def cleanup_old_data(self, retention_days: int) -> int:
        """清理旧SQL Server数据"""
        if not self._ensure_connection():
            return 0
        return self.sql_manager.cleanup_old_data(retention_days)


class DataStorageManager:
    """统一数据存储管理器"""
    
    STORAGE_CSV = "csv"
    STORAGE_SQLITE = "sqlite"
    STORAGE_SQLSERVER = "sqlserver"
    
    def __init__(self, storage_type: str = STORAGE_SQLITE):
        self.storage_type = storage_type
        self._storage = self._create_storage(storage_type)
    
    def _create_storage(self, storage_type: str) -> BaseStorage:
        """创建存储实例"""
        if storage_type == self.STORAGE_CSV:
            return CSVStorage()
        elif storage_type == self.STORAGE_SQLITE:
            return SQLiteStorage()
        elif storage_type == self.STORAGE_SQLSERVER:
            return SQLServerStorage()
        else:
            return SQLiteStorage()
    
    def set_storage_type(self, storage_type: str):
        """切换存储类型"""
        self.storage_type = storage_type
        self._storage = self._create_storage(storage_type)
    
    def write_logs(self, logs: List[LogEntry]) -> bool:
        """写入日志"""
        return self._storage.write_logs(logs)
    
    def query_logs(self, tag_name: str, start_time: datetime, end_time: datetime, limit: int = 1000) -> List[Dict[str, Any]]:
        """查询日志"""
        return self._storage.query_logs(tag_name, start_time, end_time, limit)
    
    def cleanup_old_data(self, retention_days: int) -> int:
        """清理旧数据"""
        return self._storage.cleanup_old_data(retention_days)


# 单例实例
data_storage_manager = DataStorageManager()
