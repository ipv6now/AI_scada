"""
Data Manager - Manages SCADA data including tags, history, and alarms
Optimized with connection pooling and batch writes
"""
import sqlite3
import threading
import time
from datetime import datetime
from enum import Enum
from collections import OrderedDict

from ..architecture import DataType, TagType


class Tag:
    def __init__(self, name, tag_type, data_type, address=None, description="", plc_connection="", bit_offset=None):
        self.name = name
        self.tag_type = tag_type
        self.data_type = data_type
        self.address = address.upper() if address else address
        self.description = description
        self.plc_connection = plc_connection
        self.bit_offset = bit_offset  # 位偏移 (0-15 for 16-bit, 0-31 for 32-bit)
        self.value = None
        self.timestamp = None
        self.quality = "GOOD"
        
    def update_value(self, value):
        self.value = value
        self.timestamp = datetime.now()


class ConnectionPool:
    """SQLite connection pool for thread-safe database access"""
    
    def __init__(self, db_path, pool_size=5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._pool = []
        self._lock = threading.Lock()
        self._connection_count = 0
        
    def get_connection(self):
        """Get a connection from the pool"""
        with self._lock:
            if self._pool:
                return self._pool.pop()
            elif self._connection_count < self.pool_size:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=10000")
                self._connection_count += 1
                return conn
            else:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                return conn
    
    def return_connection(self, conn):
        """Return a connection to the pool"""
        with self._lock:
            if len(self._pool) < self.pool_size:
                self._pool.append(conn)
            else:
                try:
                    conn.close()
                    self._connection_count -= 1
                except:
                    pass
    
    def close_all(self):
        """Close all connections in the pool"""
        with self._lock:
            for conn in self._pool:
                try:
                    conn.close()
                except:
                    pass
            self._pool.clear()
            self._connection_count = 0


class LRUCache:
    """LRU Cache for image caching"""
    
    def __init__(self, max_size=100):
        self._cache = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None
    
    def set(self, key, value):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self._max_size:
                    self._cache.popitem(last=False)
            self._cache[key] = value
    
    def clear(self):
        with self._lock:
            self._cache.clear()
    
    def get_stats(self):
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total * 100 if total > 0 else 0
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.1f}%"
            }


class DataManager:
    def __init__(self, db_path="scada_data.db"):
        self.db_path = db_path
        self.tags = {}
        self.tag_history = {}
        self.alarms = []
        self.callbacks = {}
        
        self._connection_pool = ConnectionPool(db_path)
        self._pending_writes = {}
        self._write_lock = threading.Lock()
        self._batch_write_interval = 0.1
        self._last_batch_write = time.time()
        
        self._tag_value_cache = {}
        self._cache_lock = threading.Lock()
        
        self.init_database()
        
    def _get_connection(self):
        return self._connection_pool.get_connection()
    
    def _return_connection(self, conn):
        self._connection_pool.return_connection(conn)
        
    def init_database(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    tag_type TEXT,
                    data_type TEXT,
                    address TEXT,
                    description TEXT,
                    last_value TEXT,
                    last_update TIMESTAMP,
                    plc_connection TEXT DEFAULT ""
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tag_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_name TEXT,
                    value TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    quality TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_tag_history_name_time 
                ON tag_history(tag_name, timestamp DESC)
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alarms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_name TEXT,
                    alarm_type TEXT,
                    message TEXT,
                    active BOOLEAN,
                    acknowledged BOOLEAN,
                    priority TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
        finally:
            self._return_connection(conn)
        
    def add_tag(self, tag):
        self.tags[tag.name] = tag
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO tags (name, tag_type, data_type, address, description, plc_connection, last_value, last_update)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (tag.name, tag.tag_type.value, tag.data_type.value, tag.address, 
                  tag.description, tag.plc_connection, str(tag.value) if tag.value is not None else None, 
                  tag.timestamp))
            conn.commit()
        finally:
            self._return_connection(conn)
        
    def update_tag_value(self, tag_name, value, quality="GOOD"):
        if tag_name in self.tags:
            tag = self.tags[tag_name]
            old_value = tag.value
            tag.update_value(value)
            tag.quality = quality
            
            with self._cache_lock:
                self._tag_value_cache[tag_name] = value
            
            with self._write_lock:
                self._pending_writes[tag_name] = (str(value), tag.timestamp)
            
            current_time = time.time()
            if current_time - self._last_batch_write >= self._batch_write_interval:
                self._flush_pending_writes()
            
            if old_value != value and tag_name in self.callbacks:
                for callback in self.callbacks[tag_name]:
                    try:
                        callback(tag_name, value, old_value)
                    except Exception as e:
                        print(f"Callback error for {tag_name}: {e}")
    
    def _flush_pending_writes(self):
        if not self._pending_writes:
            return
            
        with self._write_lock:
            writes = self._pending_writes.copy()
            self._pending_writes.clear()
            self._last_batch_write = time.time()
        
        if not writes:
            return
            
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.executemany(
                'UPDATE tags SET last_value=?, last_update=? WHERE name=?',
                [(v, t, n) for n, (v, t) in writes.items()]
            )
            conn.commit()
        except Exception as e:
            print(f"Batch write error: {e}")
        finally:
            self._return_connection(conn)
    
    def flush(self):
        self._flush_pending_writes()
                    
    def register_callback(self, tag_name, callback):
        if tag_name not in self.callbacks:
            self.callbacks[tag_name] = []
        self.callbacks[tag_name].append(callback)
        
    def get_tag_value(self, tag_name):
        with self._cache_lock:
            if tag_name in self._tag_value_cache:
                return self._tag_value_cache[tag_name]
        
        if tag_name in self.tags:
            return self.tags[tag_name].value
        return None
    
    def update_tag(self, tag_name, value, quality="GOOD"):
        self.update_tag_value(tag_name, value, quality)
        return True
        
    def get_tag_history(self, tag_name, start_time=None, end_time=None, limit=1000):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            if start_time and end_time:
                cursor.execute('''
                    SELECT value, timestamp, quality FROM tag_history 
                    WHERE tag_name=? AND timestamp BETWEEN ? AND ?
                    ORDER BY timestamp DESC LIMIT ?
                ''', (tag_name, start_time, end_time, limit))
            else:
                cursor.execute('''
                    SELECT value, timestamp, quality FROM tag_history 
                    WHERE tag_name=? 
                    ORDER BY timestamp DESC LIMIT ?
                ''', (tag_name, limit))
                
            return cursor.fetchall()
        finally:
            self._return_connection(conn)
        
    def raise_alarm(self, tag_name, alarm_type, message, priority="MEDIUM"):
        alarm = {
            'tag_name': tag_name,
            'alarm_type': alarm_type,
            'message': message,
            'active': True,
            'acknowledged': False,
            'priority': priority,
            'timestamp': datetime.now()
        }
        
        self.alarms.append(alarm)
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO alarms (tag_name, alarm_type, message, active, acknowledged, priority)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (tag_name, alarm_type, message, True, False, priority))
            conn.commit()
        finally:
            self._return_connection(conn)
        
    def acknowledge_alarm(self, alarm_id):
        for alarm in self.alarms:
            if alarm.get('id') == alarm_id:
                alarm['acknowledged'] = True
                break
                
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('UPDATE alarms SET acknowledged=? WHERE id=?', (True, alarm_id))
            conn.commit()
        finally:
            self._return_connection(conn)
        
    def get_active_alarms(self):
        return [alarm for alarm in self.alarms if alarm['active'] and not alarm['acknowledged']]
    
    def close(self):
        self._flush_pending_writes()
        self._connection_pool.close_all()
    
    def __del__(self):
        try:
            self.close()
        except:
            pass


image_cache = LRUCache(max_size=200)


def get_image_cache():
    return image_cache
