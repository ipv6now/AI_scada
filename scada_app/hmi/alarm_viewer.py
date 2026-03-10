"""
报警查看器对话框 - 显示活动和历史报警
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QGroupBox, QComboBox, QCheckBox, QDateTimeEdit, 
                             QMessageBox, QWidget, QSplitter, QScrollArea)
from PyQt5.QtCore import Qt, QSortFilterProxyModel, QDateTime, QTimer
from PyQt5.QtGui import QColor, QFont
from datetime import datetime
from scada_app.core.alarm_type_manager import alarm_type_manager


class AlarmViewerDialog(QDialog):
    """Dialog for viewing and managing alarms"""
    def __init__(self, parent=None, data_manager=None, system_service_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.system_service_manager = system_service_manager
        self.setWindowTitle("报警监控")
        self.setGeometry(200, 200, 1000, 700)
        
        # 设置为无模态窗口，允许同时操作主窗口
        self.setModal(False)
        # 设置窗口标志，允许最小化和关闭
        self.setWindowFlags(Qt.Window)
        
        self.init_ui()
        self.start_refresh_timer()
    
    def init_ui(self):
        """Initialize the UI"""
        main_layout = QVBoxLayout()
        
        # Header with filters
        filter_layout = QHBoxLayout()
        
        # 报警类型筛选器
        alarm_type_label = QLabel("报警类型:")
        filter_layout.addWidget(alarm_type_label)
        
        self.alarm_type_combo = QComboBox()
        # 获取所有启用的报警类型
        alarm_type_names = ["全部"] + alarm_type_manager.get_alarm_type_names()
        self.alarm_type_combo.addItems(alarm_type_names)
        self.alarm_type_combo.currentTextChanged.connect(self.filter_alarms)
        filter_layout.addWidget(self.alarm_type_combo)
        
        # Status filter
        status_label = QLabel("状态:")
        filter_layout.addWidget(status_label)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["全部", "活动", "已确认", "已清除"])
        self.status_combo.currentTextChanged.connect(self.filter_alarms)
        filter_layout.addWidget(self.status_combo)
        
        # Tag filter
        tag_label = QLabel("标签:")
        filter_layout.addWidget(tag_label)
        
        self.tag_combo = QComboBox()
        self.tag_combo.addItem("全部")
        if self.data_manager:
            for tag_name in self.data_manager.tags.keys():
                self.tag_combo.addItem(tag_name)
        self.tag_combo.currentTextChanged.connect(self.filter_alarms)
        filter_layout.addWidget(self.tag_combo)
        
        # Time range filter
        time_label = QLabel("时间范围:")
        filter_layout.addWidget(time_label)
        
        self.time_combo = QComboBox()
        self.time_combo.addItems(["全部", "过去1小时", "过去24小时", "过去7天", "过去30天"])
        self.time_combo.currentTextChanged.connect(self.filter_alarms)
        filter_layout.addWidget(self.time_combo)
        
        # Refresh button
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_alarms)
        filter_layout.addWidget(self.refresh_btn)
        
        filter_layout.addStretch()
        main_layout.addLayout(filter_layout)
        
        # Alarm table
        self.alarm_table = QTableWidget()
        self.alarm_table.setColumnCount(8)
        self.alarm_table.setHorizontalHeaderLabels(["报警ID", "标签", "类型", "消息", "报警类型", "状态", "触发时间", "恢复时间"])
        self.alarm_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.alarm_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.alarm_table.itemClicked.connect(self.on_alarm_selected)
        main_layout.addWidget(self.alarm_table, 1)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self.ack_btn = QPushButton("确认选中")
        self.ack_btn.clicked.connect(self.acknowledge_selected)
        self.ack_btn.setEnabled(False)
        action_layout.addWidget(self.ack_btn)
        
        self.ack_all_btn = QPushButton("确认全部")
        self.ack_all_btn.clicked.connect(self.acknowledge_all)
        action_layout.addWidget(self.ack_all_btn)
        
        self.clear_btn = QPushButton("清除选中")
        self.clear_btn.clicked.connect(self.clear_selected)
        self.clear_btn.setEnabled(False)
        action_layout.addWidget(self.clear_btn)
        
        self.clear_all_btn = QPushButton("清除全部")
        self.clear_all_btn.clicked.connect(self.clear_all)
        action_layout.addWidget(self.clear_all_btn)
        
        action_layout.addStretch()
        main_layout.addLayout(action_layout)
        
        # Status bar
        self.status_bar = QLabel("就绪")
        main_layout.addWidget(self.status_bar)
        
        self.setLayout(main_layout)
        
        # Load alarms
        self.refresh_alarms()
    
    def start_refresh_timer(self):
        """Start the refresh timer"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_alarms)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
    
    def stop_refresh_timer(self):
        """Stop the refresh timer"""
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
    
    def refresh_alarms(self):
        """Refresh the alarm list"""
        if not self.data_manager and not self.system_service_manager:
            return
        
        # Update status
        self.status_bar.setText("正在刷新报警...")
        
        # Clear current table
        self.alarm_table.setRowCount(0)
        
        # Get all alarms from system service manager if available
        alarms = []
        if self.system_service_manager:
            try:
                # 获取所有报警历史，包括已恢复的报警
                all_alarms = self.system_service_manager.get_alarm_history(limit=200)  # 获取最近200条报警
                for alarm_state in all_alarms:
                    # 直接使用报警状态中的alarm_id，无需复杂匹配
                    alarm_id = alarm_state.alarm_id
                    
                    alarm = {
                        'tag_name': alarm_state.tag_name,
                        'alarm_type': alarm_state.alarm_type,
                        'message': alarm_state.message,
                        'priority': alarm_state.alarm_type_name,  # 使用alarm_type_name
                        'alarm_type_name': alarm_state.alarm_type_name,  # 添加alarm_type_name字段
                        'status': "已恢复" if alarm_state.status.name == 'RECOVERED' else \
                                 "已确认" if alarm_state.status.name == 'ACKNOWLEDGED' else "活动",
                        'acknowledged': alarm_state.status.name == 'ACKNOWLEDGED',
                        'recovered': alarm_state.status.name == 'RECOVERED',
                        'timestamp': alarm_state.first_trigger_time,
                        'recovery_time': alarm_state.recover_time,
                        'alarm_id': alarm_id
                    }
                    alarms.append(alarm)
                print(f"[ALARM VIEWER] 从系统服务管理器获取 {len(all_alarms)} 条报警（包括已恢复的）")
            except Exception as e:
                print(f"[ALARM VIEWER] 从系统服务管理器获取报警失败: {e}")
                # Fallback to data manager
                if self.data_manager:
                    alarms = self.data_manager.alarms
        elif self.data_manager:
            # Fallback to data manager
            for alarm in self.data_manager.alarms:
                # 转换数据管理器中的报警格式
                status = "活动"
                if alarm.get('acknowledged', False):
                    status = "已确认"
                elif not alarm.get('active', True):
                    status = "已恢复"
                
                converted_alarm = {
                    'tag_name': alarm.get('tag_name', ''),
                    'alarm_type': alarm.get('alarm_type', ''),
                    'message': alarm.get('message', ''),
                    'priority': alarm.get('priority', '中'),
                    'alarm_type_name': alarm.get('alarm_type_name', alarm.get('priority', '中')),  # 兼容旧数据
                    'status': status,
                    'acknowledged': alarm.get('acknowledged', False),
                    'recovered': not alarm.get('active', True),
                    'timestamp': alarm.get('timestamp', datetime.now()),
                    'recovery_time': None,  # 数据管理器中没有恢复时间
                    'alarm_id': None  # 数据管理器中没有报警ID
                }
                alarms.append(converted_alarm)
        
        # Filter alarms based on current filters
        filtered_alarms = self._filter_alarms(alarms)
        
        # Populate table
        for i, alarm in enumerate(filtered_alarms):
            self.alarm_table.insertRow(i)
            
            # Alarm ID
            alarm_id = alarm.get('alarm_id', '')
            alarm_id_item = QTableWidgetItem(str(alarm_id) if alarm_id is not None else '')
            self.alarm_table.setItem(i, 0, alarm_id_item)
            
            # Tag name
            tag_item = QTableWidgetItem(alarm['tag_name'])
            self.alarm_table.setItem(i, 1, tag_item)
            
            # Alarm type
            type_item = QTableWidgetItem(alarm['alarm_type'])
            self.alarm_table.setItem(i, 2, type_item)
            
            # Message
            msg_item = QTableWidgetItem(alarm['message'])
            self.alarm_table.setItem(i, 3, msg_item)
            
            # 报警类型
            alarm_type_name = alarm.get('alarm_type_name', alarm.get('priority', '中'))  # 兼容旧数据
            alarm_type_item = QTableWidgetItem(alarm_type_name)
            
            # 使用报警类型管理器设置颜色
            alarm_type = alarm_type_manager.get_alarm_type_by_display_name(alarm_type_name)
            if alarm_type:
                fg_color = alarm_type_manager.get_qcolor_from_hex(alarm_type.foreground_color)
                bg_color = alarm_type_manager.get_qcolor_from_hex(alarm_type.background_color)
                alarm_type_item.setForeground(fg_color)
                alarm_type_item.setBackground(bg_color)
            
            self.alarm_table.setItem(i, 4, alarm_type_item)
            
            # Status
            status_item = QTableWidgetItem(alarm['status'])
            if alarm['status'] == "活动":
                status_item.setFont(QFont("Arial", 10, QFont.Bold))
                status_item.setBackground(QColor(255, 220, 220))
            elif alarm['status'] == "已恢复":
                status_item.setForeground(QColor(100, 100, 100))
            self.alarm_table.setItem(i, 5, status_item)
            
            # Timestamp
            timestamp_item = QTableWidgetItem(alarm['timestamp'].strftime("%Y-%m-%d %H:%M:%S"))
            self.alarm_table.setItem(i, 6, timestamp_item)
            
            # Recovery time if applicable
            if alarm.get('recovered', False) and alarm.get('recovery_time'):
                recovery_item = QTableWidgetItem(alarm['recovery_time'].strftime("%Y-%m-%d %H:%M:%S"))
                self.alarm_table.setItem(i, 7, recovery_item)
        
        # Update status
        self.status_bar.setText(f"显示 {len(filtered_alarms)} 条报警")
    
    def _filter_alarms(self, alarms):
        """Filter alarms based on current filter settings"""
        alarm_type_filter = self.alarm_type_combo.currentText()
        status_filter = self.status_combo.currentText()
        tag_filter = self.tag_combo.currentText()
        time_filter = self.time_combo.currentText()
        
        filtered = []
        
        for alarm in alarms:
            # 报警类型筛选
            if alarm_type_filter != "全部":
                alarm_type_name = alarm.get('alarm_type_name', alarm.get('priority', '中'))  # 兼容旧数据
                if alarm_type_name != alarm_type_filter:
                    continue
            
            # Status filter
            if status_filter == "活动" and (alarm['acknowledged'] or alarm.get('recovered', False)):
                continue
            elif status_filter == "已确认" and not alarm['acknowledged']:
                continue
            elif status_filter == "已清除" and not alarm.get('recovered', False):
                continue
            
            # Tag filter
            if tag_filter != "全部" and alarm['tag_name'] != tag_filter:
                continue
            
            # Time filter
            if time_filter != "全部":
                time_diff = now - alarm['timestamp']
                if time_filter == "过去1小时" and time_diff.total_seconds() > 3600:
                    continue
                elif time_filter == "过去24小时" and time_diff.total_seconds() > 86400:
                    continue
                elif time_filter == "过去7天" and time_diff.total_seconds() > 604800:
                    continue
                elif time_filter == "过去30天" and time_diff.total_seconds() > 2592000:
                    continue
            
            filtered.append(alarm)
        
        # Sort by timestamp (newest first)
        filtered.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return filtered
    
    def filter_alarms(self):
        """Filter alarms based on current filter settings"""
        self.refresh_alarms()
    
    def on_alarm_selected(self, item):
        """Handle alarm selection"""
        row = item.row()
        status_item = self.alarm_table.item(row, 4)
        
        # Enable/disable buttons based on status
        if status_item.text() == "活动":
            self.ack_btn.setEnabled(True)
        else:
            self.ack_btn.setEnabled(False)
        
        self.clear_btn.setEnabled(True)
    
    def acknowledge_selected(self):
        """Acknowledge selected alarm"""
        selected_rows = set()
        for item in self.alarm_table.selectedItems():
            selected_rows.add(item.row())
        
        for row in selected_rows:
            tag_item = self.alarm_table.item(row, 0)
            time_item = self.alarm_table.item(row, 5)
            
            if tag_item and time_item:
                tag_name = tag_item.text()
                timestamp_str = time_item.text()
                
                # Find the alarm in the data manager
                for i, alarm in enumerate(self.data_manager.alarms):
                    if alarm['tag_name'] == tag_name and \
                       alarm['timestamp'].strftime("%Y-%m-%d %H:%M:%S") == timestamp_str:
                        # Acknowledge the alarm
                        alarm['acknowledged'] = True
                        # Update the status in the table
                        status_item = QTableWidgetItem("已确认")
                        self.alarm_table.setItem(row, 4, status_item)
                        break
        
        QMessageBox.information(self, "成功", f"已确认 {len(selected_rows)} 条报警")
        self.ack_btn.setEnabled(False)
    
    def acknowledge_all(self):
        """Acknowledge all active alarms"""
        active_alarms = [alarm for alarm in self.data_manager.alarms if not alarm['acknowledged']]
        
        for alarm in active_alarms:
            alarm['acknowledged'] = True
        
        QMessageBox.information(self, "成功", f"已确认 {len(active_alarms)} 条报警")
        self.refresh_alarms()
    
    def clear_selected(self):
        """Clear selected alarm"""
        selected_rows = set()
        for item in self.alarm_table.selectedItems():
            selected_rows.add(item.row())
        
        # For now, we'll just remove it from the in-memory list
        # In a real implementation, we would also remove it from the database
        removed_count = 0
        for row in sorted(selected_rows, reverse=True):
            tag_item = self.alarm_table.item(row, 0)
            time_item = self.alarm_table.item(row, 5)
            
            if tag_item and time_item:
                tag_name = tag_item.text()
                timestamp_str = time_item.text()
                
                # Find the alarm in the data manager
                for i, alarm in enumerate(self.data_manager.alarms):
                    if alarm['tag_name'] == tag_name and \
                       alarm['timestamp'].strftime("%Y-%m-%d %H:%M:%S") == timestamp_str:
                        # Remove the alarm
                        self.data_manager.alarms.pop(i)
                        removed_count += 1
                        break
        
        QMessageBox.information(self, "成功", f"已清除 {removed_count} 条报警")
        self.refresh_alarms()
        self.clear_btn.setEnabled(False)
    
    def clear_all(self):
        """Clear all alarms"""
        reply = QMessageBox.question(
            self, "确认", "确定要清除所有报警吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # For now, we'll just clear the in-memory list
            # In a real implementation, we would also remove all alarms from the database
            self.data_manager.alarms.clear()
            QMessageBox.information(self, "成功", "已清除所有报警")
            self.refresh_alarms()
    
    def closeEvent(self, event):
        """Handle dialog close event"""
        self.stop_refresh_timer()
        event.accept()