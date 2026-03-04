"""
SQL Server Database Manager for HMI Data Logging
Handles connection, table creation, and data operations for SQL Server
使用 pymssql 纯 Python 驱动，无需 ODBC
"""
try:
    import pymssql
    PYMSSQL_AVAILABLE = True
except ImportError:
    PYMSSQL_AVAILABLE = False
    pymssql = None

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class SQLServerManager:
    """SQL Server database manager for HMI data logging"""

    def __init__(self, server: str = "localhost", database: str = "HMI_DataLogging",
                 username: str = "sa", password: str = "", port: int = 1433):
        self.server = server
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.connection = None
        self._lock = threading.Lock()
        self._last_connection_time = 0
        self._connection_retry_interval = 30
        self._last_error_time = 0
        self._error_backoff = 60

    def _is_connection_healthy(self) -> bool:
        """Check if connection is still healthy"""
        if not self.connection:
            return False
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            return False

    def _should_retry_connection(self) -> bool:
        """Check if we should attempt to reconnect based on backoff"""
        current_time = time.time()
        if current_time - self._last_error_time < self._error_backoff:
            return False
        return True

    def _parse_server(self) -> tuple:
        """Parse server string to handle port and instance"""
        server = self.server
        port = self.port

        # Handle server\instance format
        if '\\' in server:
            # Named instance, pymssql will use default port
            pass
        elif ',' in server:
            # Format: server,port
            parts = server.split(',')
            server = parts[0]
            try:
                port = int(parts[1])
            except:
                pass
        elif ':' in server:
            # Format: server:port
            parts = server.split(':')
            server = parts[0]
            try:
                port = int(parts[1])
            except:
                pass

        return server, port

    def connect(self) -> bool:
        """Establish connection to SQL Server using pymssql"""
        if not PYMSSQL_AVAILABLE:
            logger.error("pymssql module is not installed. Please install it with: pip install pymssql")
            return False

        try:
            # Close existing connection if any
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
                self.connection = None

            # Parse server and port
            server, port = self._parse_server()

            # Build connection parameters
            conn_params = {
                'server': server,
                'user': self.username,
                'password': self.password,
                'charset': 'utf8',
                'login_timeout': 10,
                'timeout': 30
            }

            # Only add port for non-named instances
            if '\\' not in server:
                conn_params['port'] = port

            # Only add database if specified (for initial connection might be master)
            if self.database:
                conn_params['database'] = self.database

            logger.info(f"Connecting to SQL Server: {server}:{port if '\\' not in server else 'default'}/{self.database}")

            # First ensure database exists
            if self.database:
                self._ensure_database_exists()
            
            # Connect using pymssql
            self.connection = pymssql.connect(**conn_params)

            logger.info(f"Connected to SQL Server: {server}/{self.database}")
            
            # Initialize database tables
            self.initialize_database()
            
            return True
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to connect to SQL Server: {error_msg}")

            # Provide helpful error messages
            if "20009" in error_msg or "unavailable" in error_msg.lower():
                logger.error("Connection troubleshooting tips:")
                logger.error("1. Ensure SQL Server TCP/IP protocol is enabled in SQL Server Configuration Manager")
                logger.error("2. Check if SQL Server Browser service is running (for named instances)")
                logger.error("3. Verify firewall allows port 1433 (or your custom port)")
                logger.error("4. Try using IP address instead of hostname")
                logger.error("5. For named instances, use format: server\\instance or specify port directly")

            return False

    def disconnect(self):
        """Close database connection"""
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
            self.connection = None
            logger.info("Disconnected from SQL Server")

    def _ensure_database_exists(self) -> bool:
        """Ensure database exists, create if not"""
        try:
            # Parse server and port
            server, port = self._parse_server()

            # Build connection parameters for master database
            conn_params = {
                'server': server,
                'user': self.username,
                'password': self.password,
                'database': 'master',
                'charset': 'utf8',
                'login_timeout': 10
            }

            # Only add port for non-named instances
            if '\\' not in server:
                conn_params['port'] = port

            # Connect to master database first
            conn = pymssql.connect(**conn_params)
            cursor = conn.cursor()

            # Check if database exists
            cursor.execute(
                "SELECT name FROM sys.databases WHERE name = %s",
                (self.database,)
            )

            if not cursor.fetchone():
                # Create database
                cursor.execute(f"CREATE DATABASE [{self.database}]")
                conn.commit()
                logger.info(f"Created database: {self.database}")

            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to ensure database exists: {e}")
            return False

    def initialize_database(self) -> bool:
        """Initialize database tables if they don't exist"""
        try:
            if not self.connection:
                logger.warning("No connection for database initialization")
                return False

            cursor = self.connection.cursor()

            # Check if tables exist first
            cursor.execute("SELECT COUNT(*) FROM sysobjects WHERE name='logging_rules' AND xtype='U'")
            if cursor.fetchone()[0] > 0:
                logger.info("Database tables already exist")
                return True

            # Create tables
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='logging_rules' AND xtype='U')
                CREATE TABLE logging_rules (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    tag_name NVARCHAR(255) NOT NULL,
                    sample_rate FLOAT NOT NULL,
                    storage_duration_days INT NOT NULL,
                    storage_location NVARCHAR(50) NOT NULL,
                    enabled BIT NOT NULL DEFAULT 1,
                    created_at DATETIME2 DEFAULT GETDATE(),
                    updated_at DATETIME2 DEFAULT GETDATE()
                )
            """)

            # Create data_logs table
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='data_logs' AND xtype='U')
                CREATE TABLE data_logs (
                    id BIGINT IDENTITY(1,1) PRIMARY KEY,
                    tag_name NVARCHAR(255) NOT NULL,
                    tag_value NVARCHAR(MAX) NOT NULL,
                    tag_type NVARCHAR(50) NOT NULL,
                    timestamp DATETIME2 NOT NULL DEFAULT GETDATE(),
                    quality INT NOT NULL DEFAULT 192,
                    rule_id INT NULL
                )
            """)

            # Create indexes for better performance
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_data_logs_timestamp')
                CREATE INDEX idx_data_logs_timestamp ON data_logs(timestamp)
            """)

            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_data_logs_tag_name')
                CREATE INDEX idx_data_logs_tag_name ON data_logs(tag_name)
            """)

            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_data_logs_tag_timestamp')
                CREATE INDEX idx_data_logs_tag_timestamp ON data_logs(tag_name, timestamp)
            """)

            try:
                self.connection.commit()
                logger.info("Database tables initialized successfully")
            except Exception as commit_err:
                logger.warning(f"Commit warning (tables may already exist): {commit_err}")
                # Try to rollback and continue
                try:
                    self.connection.rollback()
                except:
                    pass
            
            return True

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            # Try to rollback on error
            try:
                if self.connection:
                    self.connection.rollback()
            except:
                pass
            return False

    def save_logging_rule(self, rule: Dict[str, Any]) -> int:
        """Save a logging rule to database and return rule ID"""
        try:
            if not self.connection:
                if not self.connect():
                    return -1

            cursor = self.connection.cursor()

            # Check if rule already exists
            cursor.execute(
                "SELECT id FROM logging_rules WHERE tag_name = %s",
                (rule['tag_name'],)
            )

            existing_rule = cursor.fetchone()

            if existing_rule:
                cursor.execute("""
                    UPDATE logging_rules
                    SET sample_rate = %s, storage_duration_days = %s,
                        storage_location = %s, enabled = %s,
                        updated_at = GETDATE()
                    WHERE id = %s
                """, (rule['sample_rate'], rule['storage_duration_days'],
                      rule['storage_location'], rule['enabled'], existing_rule[0]))
                rule_id = existing_rule[0]
            else:
                cursor.execute("""
                    INSERT INTO logging_rules
                    (tag_name, sample_rate, storage_duration_days, storage_location, enabled)
                    VALUES (%s, %s, %s, %s, %s)
                """, (rule['tag_name'], rule['sample_rate'],
                      rule['storage_duration_days'], rule['storage_location'],
                      rule['enabled']))

                cursor.execute("SELECT SCOPE_IDENTITY()")
                rule_id = cursor.fetchone()[0]

            self.connection.commit()
            logger.info(f"Saved logging rule for tag: {rule['tag_name']}, ID: {rule_id}")
            return rule_id

        except Exception as e:
            logger.error(f"Failed to save logging rule: {e}")
            return -1

    def load_logging_rules(self) -> List[Dict[str, Any]]:
        """Load all logging rules from database"""
        try:
            if not self.connection:
                if not self.connect():
                    return []

            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT id, tag_name, sample_rate, storage_duration_days,
                       storage_location, enabled, created_at, updated_at
                FROM logging_rules
                ORDER BY tag_name
            """)

            rules = []
            for row in cursor.fetchall():
                rule = {
                    'id': row[0],
                    'tag_name': row[1],
                    'sample_rate': row[2],
                    'storage_duration_days': row[3],
                    'storage_location': row[4],
                    'enabled': bool(row[5]),
                    'created_at': row[6],
                    'updated_at': row[7]
                }
                rules.append(rule)

            logger.info(f"Loaded {len(rules)} logging rules from database")
            return rules

        except Exception as e:
            logger.error(f"Failed to load logging rules: {e}")
            return []

    def delete_logging_rule(self, rule_id: int) -> bool:
        """Delete a logging rule from database"""
        try:
            if not self.connection:
                if not self.connect():
                    return False

            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM logging_rules WHERE id = %s", (rule_id,))
            self.connection.commit()

            logger.info(f"Deleted logging rule ID: {rule_id}")
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to delete logging rule: {e}")
            return False

    def log_data(self, tag_name: str, tag_value: Any, tag_type: str = "float",
                 rule_id: Optional[int] = None, quality: int = 192) -> bool:
        """Log data to database"""
        with self._lock:
            if not self._should_retry_connection():
                return False
            
            try:
                if not self.connection or not self._is_connection_healthy():
                    if not self.connect():
                        self._last_error_time = time.time()
                        return False
                
                if not self.connection:
                    return False

                cursor = self.connection.cursor()
                cursor.execute("""
                    INSERT INTO data_logs (tag_name, tag_value, tag_type, rule_id, quality)
                    VALUES (%s, %s, %s, %s, %s)
                """, (tag_name, str(tag_value), tag_type, rule_id, quality))

                self.connection.commit()
                return True

            except Exception as e:
                error_str = str(e)
                logger.error(f"Failed to log data for tag {tag_name}: {e}")
                
                if 'Unknown error' in error_str or 'connection' in error_str.lower() or 'dead' in error_str.lower():
                    self.connection = None
                    self._last_error_time = time.time()
                
                return False

    def query_log_data(self, tag_name: str, start_time: datetime,
                      end_time: datetime, limit: int = 1000) -> List[Dict[str, Any]]:
        """Query logged data for a specific tag and time range"""
        with self._lock:
            try:
                if not self.connection or not self._is_connection_healthy():
                    if not self.connect():
                        return []

                cursor = self.connection.cursor()
                cursor.execute("""
                    SELECT TOP %s id, tag_name, tag_value, tag_type, timestamp, quality
                    FROM data_logs
                    WHERE tag_name = %s AND timestamp BETWEEN %s AND %s
                    ORDER BY timestamp DESC
                """, (limit, tag_name, start_time, end_time))

                data = []
                for row in cursor.fetchall():
                    record = {
                        'id': row[0],
                        'tag_name': row[1],
                        'tag_value': row[2],
                        'tag_type': row[3],
                        'timestamp': row[4],
                        'quality': row[5]
                    }
                    data.append(record)

                return data

            except Exception as e:
                logger.error(f"Failed to query data for tag {tag_name}: {e}")
                self.connection = None
                return []

    def cleanup_old_data(self, retention_days: int = 30) -> int:
        """Clean up data older than retention_days"""
        with self._lock:
            try:
                if not self.connection or not self._is_connection_healthy():
                    if not self.connect():
                        return 0

                cutoff_date = datetime.now() - timedelta(days=retention_days)
                cursor = self.connection.cursor()
                cursor.execute("""
                    DELETE FROM data_logs
                    WHERE timestamp < %s
                """, (cutoff_date,))

                deleted_count = cursor.rowcount
                
                try:
                    self.connection.commit()
                    if deleted_count > 0:
                        logger.info(f"Cleaned up {deleted_count} old records (older than {retention_days} days)")
                except Exception as commit_err:
                    logger.warning(f"Cleanup commit warning: {commit_err}")
                    try:
                        self.connection.rollback()
                    except:
                        pass
                
                return deleted_count

            except Exception as e:
                logger.error(f"Failed to cleanup old data: {e}")
                self.connection = None
                return 0

    def cleanup_old_data_for_tag(self, tag_name: str, retention_days: int) -> int:
        """Clean up old data for a specific tag"""
        with self._lock:
            try:
                if not self.connection or not self._is_connection_healthy():
                    if not self.connect():
                        return 0

                cutoff_date = datetime.now() - timedelta(days=retention_days)
                cursor = self.connection.cursor()
                cursor.execute("""
                    DELETE FROM data_logs
                    WHERE tag_name = %s AND timestamp < %s
                """, (tag_name, cutoff_date))

                deleted_count = cursor.rowcount
                
                try:
                    self.connection.commit()
                    if deleted_count > 0:
                        logger.info(f"Cleaned up {deleted_count} old records for tag {tag_name} (older than {retention_days} days)")
                except Exception as commit_err:
                    logger.warning(f"Cleanup commit warning: {commit_err}")
                    try:
                        self.connection.rollback()
                    except:
                        pass
                
                return deleted_count

            except Exception as e:
                logger.error(f"Failed to cleanup old data for tag {tag_name}: {e}")
                self.connection = None
                return 0


# Singleton instance for global access
sql_server_manager = SQLServerManager()
