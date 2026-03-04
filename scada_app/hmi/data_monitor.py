"""
Real-time Data Monitoring Module for SCADA Application
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLabel, QPushButton,
                             QSplitter, QTextEdit)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor, QBrush
import time
from datetime import datetime


class DataMonitorWidget(QWidget):
    def __init__(self, data_manager, plc_manager):
        super().__init__()
        self.data_manager = data_manager
        self.plc_manager = plc_manager
        
        # Timer for periodic updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.update_interval = 1000  # Update every second
        
        # Track subscribed tags for on-demand polling
        self._subscribed_tags = []
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Table for tag values
        self.tag_table = QTableWidget()
        self.tag_table.setColumnCount(5)
        self.tag_table.setHorizontalHeaderLabels(["标签名称", "值", "质量", "时间戳", "描述"])
        
        # Configure header - stretch all columns
        header = self.tag_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.tag_table)
        
        # Control buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)
        
        self.start_btn = QPushButton("开始监控")
        self.start_btn.setFixedHeight(28)
        self.start_btn.clicked.connect(self.start_monitoring)
        btn_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止监控")
        self.stop_btn.setFixedHeight(28)
        self.stop_btn.clicked.connect(self.stop_monitoring)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Initialize tag table
        self.populate_tag_table()
        
    def populate_tag_table(self):
        """Populate the tag table with tags from the data manager"""
        # Get tags from data manager instead of using hardcoded samples
        tags = list(self.data_manager.tags.values())
        
        self.tag_table.setRowCount(len(tags))
        
        for row, tag in enumerate(tags):
            # Tag Name
            name_item = QTableWidgetItem(tag.name)
            self.tag_table.setItem(row, 0, name_item)
            
            # Value - show actual value from data manager or placeholder
            # Format value based on data type
            if tag.value is not None:
                if hasattr(tag, 'data_type'):
                    from scada_app.architecture import DataType
                    if tag.data_type in [DataType.INT, DataType.DINT]:
                        try:
                            value = str(int(float(tag.value)))
                        except (ValueError, TypeError):
                            value = str(tag.value)
                    elif tag.data_type == DataType.REAL:
                        try:
                            value = f"{float(tag.value):.2f}"
                        except (ValueError, TypeError):
                            value = str(tag.value)
                    elif tag.data_type == DataType.BOOL:
                        value = "True" if tag.value else "False"
                    else:
                        value = str(tag.value)
                else:
                    value = str(tag.value)
            else:
                value = "N/A"
            value_item = QTableWidgetItem(value)
            self.tag_table.setItem(row, 1, value_item)
            
            # Quality
            quality_item = QTableWidgetItem(tag.quality)
            if tag.quality == "GOOD":
                quality_item.setBackground(QBrush(QColor(200, 255, 200)))  # Light green
            else:
                quality_item.setBackground(QBrush(QColor(255, 200, 200)))  # Light red
            self.tag_table.setItem(row, 2, quality_item)
            
            # Timestamp
            timestamp = tag.timestamp.strftime("%H:%M:%S") if tag.timestamp else "N/A"
            time_item = QTableWidgetItem(timestamp)
            self.tag_table.setItem(row, 3, time_item)
            
            # Description
            desc_item = QTableWidgetItem(tag.description)
            self.tag_table.setItem(row, 4, desc_item)
                
    def update_data(self):
        """Update the displayed data"""
        # Refresh the entire tag table to reflect current values from data manager
        self.populate_tag_table()
            
    def start_monitoring(self):
        """Start the monitoring timer"""
        self.timer.start(self.update_interval)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # Subscribe all tags for on-demand polling
        self._subscribe_all_tags()
        
    def stop_monitoring(self):
        """Stop the monitoring timer"""
        self.timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # Unsubscribe all tags
        self._unsubscribe_all_tags()
        
    def set_update_interval(self, interval_ms):
        """Set the update interval in milliseconds"""
        self.update_interval = interval_ms
        if self.timer.isActive():
            self.timer.stop()
            self.timer.start(interval_ms)
    
    def _subscribe_all_tags(self):
        """Subscribe all tags for on-demand polling"""
        from scada_app.core.tag_subscription_manager import tag_subscription_manager, SubscriptionType
        
        # Get all tag names from data manager
        tag_names = list(self.data_manager.tags.keys())
        
        if tag_names:
            # Save the list of tags we subscribed
            self._subscribed_tags = tag_names.copy()
            tag_subscription_manager.subscribe(tag_names, SubscriptionType.MANUAL)
            print(f"DataMonitor: Subscribed {len(tag_names)} tags for monitoring")
    
    def _unsubscribe_all_tags(self):
        """Unsubscribe only the tags we subscribed"""
        from scada_app.core.tag_subscription_manager import tag_subscription_manager, SubscriptionType
        
        if self._subscribed_tags:
            tag_subscription_manager.unsubscribe(self._subscribed_tags, SubscriptionType.MANUAL)
            print(f"DataMonitor: Unsubscribed {len(self._subscribed_tags)} tags")
            self._subscribed_tags = []


class TagMonitor:
    """Backend class to handle tag monitoring logic
    
    Note: This class no longer polls PLCs directly. 
    Data polling is handled by DataPoller. This class only reads from DataManager.
    """
    def __init__(self, data_manager, plc_manager):
        self.data_manager = data_manager
        self.plc_manager = plc_manager
        self.monitoring = False
        # Polling timer is kept for UI refresh, but no PLC communication
        self.polling_timer = QTimer()
        self.polling_timer.timeout.connect(self.refresh_display)
        
    def start_monitoring(self, interval_ms=1000):
        """Start monitoring - only refreshes UI from DataManager"""
        self.monitoring = True
        self.polling_timer.start(interval_ms)
        
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        self.polling_timer.stop()
        
    def refresh_display(self):
        """Refresh display from DataManager (no PLC communication)"""
        # Data is already being polled by DataPoller
        # This method just triggers UI refresh if needed
        pass
        
    def simulate_tag_reading(self, tag_name):
        """Simulate reading a tag value from PLC"""
        import random
        
        if "STATUS" in tag_name.upper():
            return random.choice([True, False])
        elif "POSITION" in tag_name.upper():
            return random.randint(0, 100)
        elif "SPEED" in tag_name.upper():
            return random.randint(0, 3000)
        elif "LEVEL" in tag_name.upper():
            return round(random.uniform(0, 100), 2)
        elif "TEMP" in tag_name.upper():
            return round(random.uniform(20, 40), 2)
        else:
            return random.randint(0, 100)
            
    def add_tag_to_monitor(self, tag_name, plc_name, address):
        """Add a tag to the monitoring list"""
        # Register tag in data manager
        from scada_app.core.data_manager import Tag, TagType, DataType
        
        # Determine tag type based on name
        if any(word in tag_name.upper() for word in ['INTERNAL', 'MEM', 'LOCAL']):
            tag_type = TagType.INTERNAL
        else:
            tag_type = TagType.PLC
            
        # Determine data type based on name
        data_type = DataType.INT
        if any(word in tag_name.upper() for word in ['STATUS', 'ALARM', 'FAULT']):
            data_type = DataType.BOOL
        elif any(word in tag_name.upper() for word in ['TEMP', 'LEVEL', 'PRESSURE', 'FLOW']):
            data_type = DataType.REAL
            
        tag = Tag(tag_name, tag_type, data_type, address)
        self.data_manager.add_tag(tag)
        
        # Add to PLC connection's tag list
        plc_conn = self.plc_manager.get_connection(plc_name)
        if plc_conn:
            plc_conn.tags.append(tag_name)