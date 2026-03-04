"""
System Monitor Dialog for SCADA System
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
    QTabWidget, QTableWidget, QTableWidgetItem, QComboBox,
    QPushButton, QSplitter, QGroupBox, QFormLayout, QWidget
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from scada_app.core.logger import logger
from scada_app.core.system_monitor import system_monitor
import psutil
import datetime
import os
import time


class SystemMonitorDialog(QDialog):
    """System monitor dialog for displaying system status and logs"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统监控 - SCADA监控系统")
        self.setGeometry(200, 100, 800, 600)
        self.setMinimumSize(600, 400)
        self.init_ui()
        self.start_refresh_timer()
    
    def init_ui(self):
        """Initialize the system monitor UI"""
        main_layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("系统监控中心")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        
        # System status tab
        self.system_status_tab = self.create_system_status_tab()
        self.tab_widget.addTab(self.system_status_tab, "系统状态")
        
        # Log viewer tab
        self.log_viewer_tab = self.create_log_viewer_tab()
        self.tab_widget.addTab(self.log_viewer_tab, "日志查看")
        
        # Application stats tab
        self.app_stats_tab = self.create_app_stats_tab()
        self.tab_widget.addTab(self.app_stats_tab, "应用统计")
        
        main_layout.addWidget(self.tab_widget)
        
        # Close button
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.reject)
        main_layout.addWidget(close_button)
    
    def create_system_status_tab(self):
        """Create system status tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # System resource group
        resource_group = QGroupBox("系统资源使用")
        resource_layout = QFormLayout()
        
        # CPU usage
        self.cpu_label = QLabel("0%")
        resource_layout.addRow("CPU 使用率:", self.cpu_label)
        
        # Memory usage
        self.memory_label = QLabel("0%")
        resource_layout.addRow("内存 使用率:", self.memory_label)
        
        # Disk usage
        self.disk_label = QLabel("0%")
        resource_layout.addRow("磁盘 使用率:", self.disk_label)
        
        # Network usage
        self.network_label = QLabel("发送: 0 B, 接收: 0 B")
        resource_layout.addRow("网络 流量:", self.network_label)
        
        # System uptime
        self.uptime_label = QLabel("0 天 00:00:00")
        resource_layout.addRow("系统 运行时间:", self.uptime_label)
        
        resource_group.setLayout(resource_layout)
        layout.addWidget(resource_group)
        
        # System info group
        info_group = QGroupBox("系统信息")
        info_layout = QFormLayout()
        
        # OS info
        import platform
        os_info = f"{platform.system()} {platform.release()}"
        self.os_label = QLabel(os_info)
        info_layout.addRow("操作系统:", self.os_label)
        
        # Python version
        import sys
        python_info = f"Python {sys.version.split()[0]}"
        self.python_label = QLabel(python_info)
        info_layout.addRow("Python 版本:", self.python_label)
        
        # CPU info
        cpu_info = f"{psutil.cpu_count()} 核心"
        self.cpu_info_label = QLabel(cpu_info)
        info_layout.addRow("CPU 信息:", self.cpu_info_label)
        
        # Memory info
        memory = psutil.virtual_memory()
        memory_info = f"{memory.total / (1024**3):.2f} GB"
        self.memory_info_label = QLabel(memory_info)
        info_layout.addRow("内存 总量:", self.memory_info_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        widget.setLayout(layout)
        return widget
    
    def create_log_viewer_tab(self):
        """Create log viewer tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Log file selector
        log_layout = QHBoxLayout()
        log_label = QLabel("日志文件:")
        self.log_combo = QComboBox()
        self.refresh_log_files()
        log_layout.addWidget(log_label)
        log_layout.addWidget(self.log_combo)
        
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.refresh_log_files)
        log_layout.addWidget(refresh_button)
        
        layout.addLayout(log_layout)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 10))
        layout.addWidget(self.log_text)
        
        # Load log file when selected
        self.log_combo.currentIndexChanged.connect(self.load_log_file)
        
        widget.setLayout(layout)
        return widget
    
    def create_app_stats_tab(self):
        """Create application statistics tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Application stats group
        app_group = QGroupBox("应用统计")
        app_layout = QFormLayout()
        
        # PLC connections
        self.plc_connections_label = QLabel("0")
        app_layout.addRow("PLC 连接数:", self.plc_connections_label)
        
        # Active tags
        self.active_tags_label = QLabel("0")
        app_layout.addRow("活跃 变量数:", self.active_tags_label)
        
        # Polling rate
        self.polling_rate_label = QLabel("0.0 Hz")
        app_layout.addRow("轮询 频率:", self.polling_rate_label)
        
        # Errors count
        self.errors_label = QLabel("0")
        app_layout.addRow("错误 计数:", self.errors_label)
        
        # Warnings count
        self.warnings_label = QLabel("0")
        app_layout.addRow("警告 计数:", self.warnings_label)
        
        app_group.setLayout(app_layout)
        layout.addWidget(app_group)
        
        widget.setLayout(layout)
        return widget
    
    def start_refresh_timer(self):
        """Start the refresh timer"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_stats)
        self.timer.start(1000)  # Refresh every second
    
    def refresh_stats(self):
        """Refresh system statistics"""
        try:
            # Update system stats
            stats = system_monitor.get_current_stats()
            system_stats = stats.get('system', {})
            
            # CPU usage
            cpu_percent = system_stats.get('cpu_percent', 0)
            self.cpu_label.setText(f"{cpu_percent:.1f}%")
            # Set color based on usage
            if cpu_percent > 80:
                self.cpu_label.setStyleSheet("color: red")
            elif cpu_percent > 50:
                self.cpu_label.setStyleSheet("color: orange")
            else:
                self.cpu_label.setStyleSheet("color: green")
            
            # Memory usage
            memory_percent = system_stats.get('memory_percent', 0)
            self.memory_label.setText(f"{memory_percent:.1f}%")
            if memory_percent > 80:
                self.memory_label.setStyleSheet("color: red")
            elif memory_percent > 50:
                self.memory_label.setStyleSheet("color: orange")
            else:
                self.memory_label.setStyleSheet("color: green")
            
            # Disk usage
            disk_percent = system_stats.get('disk_percent', 0)
            self.disk_label.setText(f"{disk_percent:.1f}%")
            if disk_percent > 80:
                self.disk_label.setStyleSheet("color: red")
            elif disk_percent > 50:
                self.disk_label.setStyleSheet("color: orange")
            else:
                self.disk_label.setStyleSheet("color: green")
            
            # Network usage
            network_sent = system_stats.get('network_sent', 0)
            network_recv = system_stats.get('network_recv', 0)
            self.network_label.setText(f"发送: {self.format_bytes(network_sent)}, 接收: {self.format_bytes(network_recv)}")
            
            # System uptime
            uptime = system_stats.get('uptime', 0)
            if uptime > 0:
                uptime_seconds = int(time.time() - uptime)
                days = uptime_seconds // (24 * 3600)
                hours = (uptime_seconds % (24 * 3600)) // 3600
                minutes = (uptime_seconds % 3600) // 60
                seconds = uptime_seconds % 60
                self.uptime_label.setText(f"{days} 天 {hours:02d}:{minutes:02d}:{seconds:02d}")
            
            # Update application stats
            app_stats = stats.get('application', {})
            self.plc_connections_label.setText(str(app_stats.get('plc_connections', 0)))
            self.active_tags_label.setText(str(app_stats.get('active_tags', 0)))
            self.polling_rate_label.setText(f"{app_stats.get('polling_rate', 0):.1f} Hz")
            self.errors_label.setText(str(app_stats.get('errors_count', 0)))
            self.warnings_label.setText(str(app_stats.get('warnings_count', 0)))
            
        except Exception as e:
            logger.error(f"Error refreshing stats: {str(e)}")
    
    def refresh_log_files(self):
        """Refresh log files in combobox"""
        log_files = logger.get_log_files()
        self.log_combo.clear()
        for log_file in log_files:
            self.log_combo.addItem(os.path.basename(log_file), log_file)
    
    def load_log_file(self):
        """Load selected log file into text area"""
        if self.log_combo.currentIndex() >= 0:
            log_file = self.log_combo.currentData()
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self.log_text.setText(content)
                # Scroll to end
                self.log_text.moveCursor(self.log_text.textCursor().End)
            except Exception as e:
                self.log_text.setText(f"Error loading log file: {str(e)}")
    
    def format_bytes(self, bytes_value):
        """Format bytes to human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"
    
    def start_refresh_timer(self):
        """Start the refresh timer"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_stats)
        self.refresh_timer.start(1000)  # Refresh every second
    
    def closeEvent(self, event):
        """Handle close event"""
        self.refresh_timer.stop()
        event.accept()


# Import time for uptime calculation
import time
