"""
HMI 数据日志查看器
允许用户查询和查看来自 SQL Server 的日志数据
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QPushButton, QLineEdit, QComboBox, QLabel, 
                             QDialogButtonBox, QGroupBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QSpinBox, QCheckBox,
                             QTextEdit, QMessageBox, QDoubleSpinBox, QDateTimeEdit,
                             QTabWidget, QWidget, QSplitter)
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtGui import QFont
import sys
import os

# Add the project root to Python path for module imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from scada_app.core.sql_server_manager import sql_server_manager
from scada_app.core.data_manager import DataManager
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class DataLogViewer(QDialog):
    """Data Log Viewer dialog for querying and viewing logged data"""
    
    def __init__(self, parent=None, data_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setWindowTitle("数据日志查看器")
        self.setGeometry(200, 200, 1200, 700)
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("数据日志查看器")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Query Configuration
        query_group = QGroupBox("查询配置")
        query_layout = QFormLayout()
        
        # Tag selection
        self.tag_combo = QComboBox()
        if self.data_manager:
            for tag_name in self.data_manager.tags.keys():
                self.tag_combo.addItem(tag_name)
        query_layout.addRow("标签名称:", self.tag_combo)
        
        # Time range
        time_layout = QHBoxLayout()
        
        # Start time (default: 1 day ago)
        self.start_time_edit = QDateTimeEdit()
        self.start_time_edit.setDateTime(QDateTime.currentDateTime().addDays(-1))
        self.start_time_edit.setCalendarPopup(True)
        time_layout.addWidget(QLabel("从:"))
        time_layout.addWidget(self.start_time_edit)
        
        # End time (default: now)
        self.end_time_edit = QDateTimeEdit()
        self.end_time_edit.setDateTime(QDateTime.currentDateTime())
        self.end_time_edit.setCalendarPopup(True)
        time_layout.addWidget(QLabel("到:"))
        time_layout.addWidget(self.end_time_edit)
        
        query_layout.addRow("时间范围:", time_layout)
        
        # Query buttons
        btn_layout = QHBoxLayout()
        
        self.query_btn = QPushButton("查询数据")
        self.query_btn.clicked.connect(self.query_data)
        btn_layout.addWidget(self.query_btn)
        
        self.export_btn = QPushButton("导出为CSV")
        self.export_btn.clicked.connect(self.export_to_csv)
        btn_layout.addWidget(self.export_btn)
        
        self.clear_btn = QPushButton("清除结果")
        self.clear_btn.clicked.connect(self.clear_results)
        btn_layout.addWidget(self.clear_btn)
        
        btn_layout.addStretch()
        
        # Quick time range buttons
        quick_btn_layout = QHBoxLayout()
        
        self.last_hour_btn = QPushButton("最近1小时")
        self.last_hour_btn.clicked.connect(lambda: self.set_time_range(hours=1))
        quick_btn_layout.addWidget(self.last_hour_btn)
        
        self.last_day_btn = QPushButton("最近1天")
        self.last_day_btn.clicked.connect(lambda: self.set_time_range(days=1))
        quick_btn_layout.addWidget(self.last_day_btn)
        
        self.last_week_btn = QPushButton("最近1周")
        self.last_week_btn.clicked.connect(lambda: self.set_time_range(weeks=1))
        quick_btn_layout.addWidget(self.last_week_btn)
        
        self.last_month_btn = QPushButton("最近1月")
        self.last_month_btn.clicked.connect(lambda: self.set_time_range(months=1))
        quick_btn_layout.addWidget(self.last_month_btn)
        
        btn_layout.addLayout(quick_btn_layout)
        
        query_layout.addRow("", btn_layout)
        
        query_group.setLayout(query_layout)
        layout.addWidget(query_group)
        
        # Results display
        results_group = QGroupBox("查询结果")
        results_layout = QVBoxLayout()
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "时间戳", "标签名称", "数值", "类型", "质量", "ID"
        ])
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        
        # Statistics
        stats_layout = QHBoxLayout()
        self.record_count_label = QLabel("记录数: 0")
        self.time_range_label = QLabel("时间范围: -")
        self.value_stats_label = QLabel("数值统计: -")
        
        stats_layout.addWidget(self.record_count_label)
        stats_layout.addWidget(self.time_range_label)
        stats_layout.addWidget(self.value_stats_label)
        stats_layout.addStretch()
        
        results_layout.addLayout(stats_layout)
        results_layout.addWidget(self.results_table)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # Bottom buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Close
        )
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def set_time_range(self, hours=0, days=0, weeks=0, months=0):
        """Set time range based on quick buttons"""
        end_time = QDateTime.currentDateTime()
        start_time = end_time.addSecs(-(hours * 3600 + days * 86400 + weeks * 604800))
        
        if months > 0:
            start_time = end_time.addMonths(-months)
        
        self.start_time_edit.setDateTime(start_time)
        self.end_time_edit.setDateTime(end_time)
    
    def query_data(self):
        """Query data from database based on current settings"""
        try:
            if not sql_server_manager.connection:
                QMessageBox.warning(self, "错误", "未连接到数据库！")
                return
            
            tag_name = self.tag_combo.currentText()
            if not tag_name:
                QMessageBox.warning(self, "错误", "请选择标签名称！")
                return
            
            start_time = self.start_time_edit.dateTime().toPyDateTime()
            end_time = self.end_time_edit.dateTime().toPyDateTime()
            
            if start_time >= end_time:
                QMessageBox.warning(self, "错误", "开始时间必须早于结束时间！")
                return
            
            # Query data from database
            data = sql_server_manager.query_log_data(tag_name, start_time, end_time)
            
            # Display results
            self.display_results(data)
            
            # Update statistics
            self.update_statistics(data)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"查询失败: {str(e)}")
    
    def display_results(self, data):
        """Display query results in the table"""
        self.results_table.setRowCount(len(data))
        
        for row, record in enumerate(data):
            # Timestamp
            timestamp_item = QTableWidgetItem(record['timestamp'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
            self.results_table.setItem(row, 0, timestamp_item)
            
            # Tag Name
            tag_item = QTableWidgetItem(record['tag_name'])
            self.results_table.setItem(row, 1, tag_item)
            
            # Value
            value_item = QTableWidgetItem(str(record['tag_value']))
            self.results_table.setItem(row, 2, value_item)
            
            # Type
            type_item = QTableWidgetItem(record['tag_type'])
            self.results_table.setItem(row, 3, type_item)
            
            # Quality
            quality_text = "良好" if record['quality'] == 192 else "不良"
            quality_item = QTableWidgetItem(quality_text)
            self.results_table.setItem(row, 4, quality_item)
            
            # ID
            id_item = QTableWidgetItem(str(record['id']))
            self.results_table.setItem(row, 5, id_item)
        
        # Auto-resize columns
        self.results_table.resizeColumnsToContents()
    
    def update_statistics(self, data):
        """Update statistics based on query results"""
        if not data:
            self.record_count_label.setText("Records: 0")
            self.time_range_label.setText("Time Range: -")
            self.value_stats_label.setText("Value Stats: -")
            return
        
        # Record count
        self.record_count_label.setText(f"Records: {len(data)}")
        
        # Time range
        timestamps = [record['timestamp'] for record in data]
        min_time = min(timestamps)
        max_time = max(timestamps)
        time_range = max_time - min_time
        
        self.time_range_label.setText(
            f"Time Range: {min_time.strftime('%H:%M:%S')} - {max_time.strftime('%H:%M:%S')} "
            f"({time_range.total_seconds():.1f}s)"
        )
        
        # Value statistics (for numeric values)
        try:
            values = [float(record['tag_value']) for record in data 
                     if self.is_numeric(record['tag_value'])]
            
            if values:
                avg_val = sum(values) / len(values)
                min_val = min(values)
                max_val = max(values)
                self.value_stats_label.setText(
                    f"Value Stats: Avg={avg_val:.3f}, Min={min_val:.3f}, Max={max_val:.3f}"
                )
            else:
                self.value_stats_label.setText("Value Stats: Non-numeric data")
        except:
            self.value_stats_label.setText("Value Stats: Error calculating")
    
    def is_numeric(self, value):
        """Check if value can be converted to float"""
        try:
            float(value)
            return True
        except ValueError:
            return False
    
    def export_to_csv(self):
        """Export current results to CSV file"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            import csv
            
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export to CSV", "", "CSV Files (*.csv)"
            )
            
            if not filename:
                return
            
            if not filename.endswith('.csv'):
                filename += '.csv'
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                header = ["时间戳", "标签名称", "数值", "类型", "质量", "ID"]
                writer.writerow(header)
                
                # Write data
                for row in range(self.results_table.rowCount()):
                    row_data = []
                    for col in range(self.results_table.columnCount()):
                        item = self.results_table.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            
            QMessageBox.information(self, "成功", f"数据已导出到 {filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
    
    def clear_results(self):
        """Clear query results"""
        self.results_table.setRowCount(0)
        self.record_count_label.setText("Records: 0")
        self.time_range_label.setText("Time Range: -")
        self.value_stats_label.setText("Value Stats: -")


class RealTimeDataLogger:
    """Real-time data logging service that runs in background"""
    
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
        self.logging_rules = []
        self.last_logged = {}  # Track last logging time for each tag
        self.running = False
        
    def start_logging(self):
        """Start the real-time logging service"""
        if not sql_server_manager.connection:
            logger.error("Cannot start logging: Not connected to database")
            return False
        
        self.running = True
        logger.info("Real-time data logging started")
        return True
    
    def stop_logging(self):
        """Stop the real-time logging service"""
        self.running = False
        logger.info("Real-time data logging stopped")
    
    def set_logging_rules(self, rules):
        """Set the logging rules to use"""
        self.logging_rules = rules
        self.last_logged = {}
        
    def process_data(self):
        """Process data for logging (should be called periodically)"""
        if not self.running or not self.logging_rules:
            return
        
        current_time = datetime.now()
        
        for rule in self.logging_rules:
            if not rule.enabled:
                continue
            
            tag_name = rule.tag_name
            
            # Check if it's time to log this tag
            last_time = self.last_logged.get(tag_name)
            if last_time and (current_time - last_time).total_seconds() < rule.sample_rate:
                continue
            
            # Get current tag value
            tag_value = self.data_manager.get_tag_value(tag_name)
            if tag_value is not None:
                # Log the data
                success = sql_server_manager.log_data(
                    tag_name=tag_name,
                    tag_value=tag_value,
                    tag_type=self._get_tag_type(tag_value),
                    rule_id=rule.rule_id
                )
                
                if success:
                    self.last_logged[tag_name] = current_time
                    logger.debug(f"Logged {tag_name} = {tag_value}")
    
    def _get_tag_type(self, value):
        """Determine the type of the tag value"""
        if isinstance(value, (int, float)):
            return "numeric"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, str):
            return "string"
        else:
            return "unknown"


# Global instance for real-time logging
real_time_logger = RealTimeDataLogger(None)