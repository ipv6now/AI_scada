"""
实时报警显示控件 - 支持按类别筛选和高级属性配置
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QCheckBox, QGroupBox,
                             QPushButton, QScrollArea, QFrame, QComboBox,
                             QMessageBox, QDialog, QFormLayout, QSpinBox,
                             QTableWidget, QTableWidgetItem, QDateTimeEdit, QDateEdit, QTimeEdit)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QBrush
from datetime import datetime
from scada_app.core.alarm_type_manager import alarm_type_manager


class AlarmDisplayWidget(QWidget):
    """实时报警显示控件"""
    
    # 信号：当报警状态变化时发出
    alarm_status_changed = pyqtSignal()
    
    def __init__(self, parent=None, data_manager=None, system_service_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.system_service_manager = system_service_manager
        
        # 配置属性
        self.visible_alarm_types = set()  # 可见的报警类型
        self.max_display_count = 9999       # 最大显示数量
        self.display_mode = 'current'      # 显示模式：current/buffer/history
        self._is_query_mode = False  # 是否在查询模式
        
        # 初始化UI
        self.init_ui()
        
        # 更新标题
        self._update_title()
        
        # 启动定时器（使用CoarseTimer，适合UI刷新）
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_alarms)
        self.refresh_timer.start(2000)  # 每2秒刷新一次
    
    def set_data_manager(self, data_manager):
        """设置数据管理器"""
        self.data_manager = data_manager
    
    def set_system_service_manager(self, system_service_manager):
        """设置系统服务管理器"""
        self.system_service_manager = system_service_manager
        
        # 初始化可见报警类型（默认显示所有）
        self.visible_alarm_types = set(alarm_type_manager.get_alarm_type_names())
    
    def init_ui(self):
        """初始化界面"""
        main_layout = QVBoxLayout()
        
        # 标题栏
        title_layout = QHBoxLayout()
        
        self.title_label = QLabel("实时报警")
        self.title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_layout.addWidget(self.title_label)
        
        title_layout.addStretch()
        
        main_layout.addLayout(title_layout)
        
        # 报警列表（使用表格形式）
        self.alarm_table = QTableWidget()
        self.alarm_table.setAlternatingRowColors(False)  # 禁用交替行颜色，使用报警类型颜色
        self.alarm_table.setColumnCount(6)
        self.alarm_table.setHorizontalHeaderLabels(["报警ID", "报警类型", "报警信息", "触发时间", "确认/恢复时间", "状态"])
        self.alarm_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.alarm_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #cccccc;
                border-radius: 3px;
            }
            QTableWidget::item:selected {
                background-color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #e0e0e0;
                padding: 5px;
                border: 1px solid #cccccc;
                font-weight: bold;
            }
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.alarm_table.horizontalHeader().setStretchLastSection(True)
        self.alarm_table.setColumnWidth(0, 60)   # 报警ID
        self.alarm_table.setColumnWidth(1, 80)   # 报警类型
        self.alarm_table.setColumnWidth(2, 200)  # 报警信息
        main_layout.addWidget(self.alarm_table)
        
        # 按钮栏
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.query_btn = QPushButton("查询")
        self.query_btn.setFixedWidth(80)
        self.query_btn.clicked.connect(self.show_query_dialog)
        button_layout.addWidget(self.query_btn)
        
        self.exit_query_btn = QPushButton("退出查询")
        self.exit_query_btn.setFixedWidth(100)
        self.exit_query_btn.clicked.connect(self.exit_query_mode)
        self.exit_query_btn.setVisible(False)  # 默认隐藏
        button_layout.addWidget(self.exit_query_btn)
        
        self.acknowledge_selected_btn = QPushButton("确认选中")
        self.acknowledge_selected_btn.setFixedWidth(100)
        self.acknowledge_selected_btn.clicked.connect(self.acknowledge_selected_alarm)
        button_layout.addWidget(self.acknowledge_selected_btn)
        
        self.acknowledge_all_btn = QPushButton("全部确认")
        self.acknowledge_all_btn.setFixedWidth(100)
        self.acknowledge_all_btn.clicked.connect(self.acknowledge_all_alarms)
        button_layout.addWidget(self.acknowledge_all_btn)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
        # 设置最小尺寸
        self.setMinimumSize(600, 300)
    
    def refresh_alarms(self):
        """刷新报警列表"""
        if not self.data_manager and not self.system_service_manager:
            return
        
        # 如果在查询模式，不自动刷新
        if self._is_query_mode:
            return
        
        # 更新标题
        self._update_title()
        
        # 获取报警数据
        alarms = self.get_current_alarms()
        
        # 应用筛选
        filtered_alarms = self.filter_alarms(alarms)
        
        # 限制显示数量
        display_alarms = filtered_alarms[:self.max_display_count]
        
        # 更新表格（不清空，只更新数据）
        self._update_table(display_alarms)
        
        # 更新状态
        self.update_status(len(display_alarms), len(filtered_alarms))
    
    def get_current_alarms(self):
        """获取当前报警数据"""
        alarms = []
        
        if not self.system_service_manager:
            return alarms
        
        try:
            # 根据显示模式获取报警
            if self.display_mode == 'current':
                # 当前报警状态：只显示活动或已确认的报警（从报警管理器获取）
                from scada_app.core.system_service_manager import AlarmStatus
                all_alarms = self.system_service_manager.get_active_alarms()
                
                for alarm_state in all_alarms:
                    is_active = alarm_state.status == AlarmStatus.ACTIVE
                    alarm = {
                        'tag_name': alarm_state.tag_name,
                        'alarm_type': alarm_state.alarm_type,
                        'message': alarm_state.message,
                        'alarm_type_name': alarm_state.alarm_type_name,
                        'alarm_id': alarm_state.alarm_id,
                        'status': '活动' if is_active else '已确认',
                        'timestamp': alarm_state.first_trigger_time,
                        'recover_time': alarm_state.recover_time,
                        'is_active': is_active
                    }
                    alarms.append(alarm)
            
            elif self.display_mode == 'buffer':
                # 报警缓冲区：显示缓冲区中的所有报警
                buffer_alarms = self.system_service_manager.get_alarm_buffer_alarms(
                    alarm_types=self.visible_alarm_types,
                    limit=self.max_display_count
                )
                
                for entry in buffer_alarms:
                    is_active = entry.status == '活动'
                    alarm = {
                        'tag_name': entry.tag_name,
                        'alarm_type': entry.alarm_type,
                        'message': entry.message,
                        'alarm_type_name': entry.alarm_type_name,
                        'alarm_id': entry.alarm_id,
                        'status': entry.status,
                        'timestamp': entry.timestamp,
                        'recover_time': entry.recover_time,
                        'is_active': is_active
                    }
                    alarms.append(alarm)
            
            elif self.display_mode == 'history':
                # 报警记录：显示数据库中的历史报警
                all_alarms = self.system_service_manager.get_alarm_history(limit=self.max_display_count)
                
                for alarm_state in all_alarms:
                    from scada_app.core.system_service_manager import AlarmStatus
                    status_map = {
                        AlarmStatus.ACTIVE: '活动',
                        AlarmStatus.ACKNOWLEDGED: '已确认',
                        AlarmStatus.RECOVERED: '已恢复'
                    }
                    is_active = alarm_state.status == AlarmStatus.ACTIVE
                    alarm = {
                        'tag_name': alarm_state.tag_name,
                        'alarm_type': alarm_state.alarm_type,
                        'message': alarm_state.message,
                        'alarm_type_name': alarm_state.alarm_type_name,
                        'alarm_id': alarm_state.alarm_id,
                        'status': status_map.get(alarm_state.status, '未知'),
                        'timestamp': alarm_state.first_trigger_time,
                        'recover_time': alarm_state.recover_time,
                        'is_active': is_active
                    }
                    alarms.append(alarm)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
        
        return alarms
    
    def filter_alarms(self, alarms):
        """筛选报警"""
        filtered = []
        
        for alarm in alarms:
            # 按报警类型筛选
            alarm_type_name = alarm.get('alarm_type_name', '中')
            if self.visible_alarm_types and alarm_type_name not in self.visible_alarm_types:
                continue
            
            filtered.append(alarm)
        
        # 按时间排序（最新的在前）
        filtered.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return filtered
    
    def _update_table(self, alarms):
        """更新表格数据"""
        # 禁用更新以防止重绘
        self.alarm_table.setUpdatesEnabled(False)
        
        # 状态映射
        from scada_app.core.system_service_manager import AlarmStatus
        status_map = {
            AlarmStatus.ACTIVE: '活动',
            AlarmStatus.ACKNOWLEDGED: '已确认',
            AlarmStatus.RECOVERED: '已恢复'
        }
        
        # 根据显示模式隐藏/显示恢复时间列
        if self.display_mode == 'current':
            self.alarm_table.setColumnHidden(4, True)  # 隐藏恢复时间列
        else:
            self.alarm_table.setColumnHidden(4, False)  # 显示恢复时间列
        
        # 保存滚动位置
        sb = self.alarm_table.verticalScrollBar()
        scroll_pos = sb.value() if sb else 0
        
        current_rows = self.alarm_table.rowCount()
        new_rows = len(alarms)
        
        # 只在缓冲区和历史模式下设置最小行数，当前报警模式不设置
        if self.display_mode != 'current' and new_rows < 20:
            new_rows = 20
        
        # 在缓冲区和历史模式下，只增加行数，不减少行数
        if self.display_mode != 'current':
            if current_rows < new_rows:
                self.alarm_table.setRowCount(new_rows)
        else:
            # 当前报警模式下，直接设置行数
            if current_rows != new_rows:
                self.alarm_table.setRowCount(new_rows)
        
        # 更新每个单元格
        for row, alarm in enumerate(alarms):
            # 判断alarm是字典还是AlarmState对象
            if hasattr(alarm, 'alarm_type_name'):
                # AlarmState对象
                alarm_type_name = alarm.alarm_type_name
                alarm_id = alarm.alarm_id
                message = alarm.message
                timestamp = alarm.last_trigger_time
                recover_time = alarm.recover_time
                status = status_map.get(alarm.status, '未知')
            else:
                # 字典
                alarm_type_name = alarm.get('alarm_type_name', '中')
                alarm_id = alarm.get('alarm_id', '')
                message = alarm.get('message', '')
                timestamp = alarm.get('timestamp')
                recover_time = alarm.get('recover_time')
                status = alarm.get('status', '活动')
            
            # 获取报警类型颜色配置
            alarm_type = alarm_type_manager.get_alarm_type_by_display_name(alarm_type_name)
            
            # 解析颜色
            if alarm_type:
                bg_color = alarm_type_manager.get_qcolor_from_hex(alarm_type.background_color)
                fg_color = alarm_type_manager.get_qcolor_from_hex(alarm_type.foreground_color)
            else:
                bg_color = QColor(255,255, 200)  # 默认背景色
                fg_color = QColor(0, 0, 0)  # 默认前景色
            
            # 报警ID
            id_item = QTableWidgetItem(str(alarm_id) if alarm_id is not None else '')
            id_item.setData(Qt.BackgroundRole, bg_color)
            id_item.setData(Qt.ForegroundRole, fg_color)
            self.alarm_table.setItem(row, 0, id_item)
            
            # 报警类型
            type_item = QTableWidgetItem(alarm_type_name)
            type_item.setData(Qt.BackgroundRole, bg_color)
            type_item.setData(Qt.ForegroundRole, fg_color)
            self.alarm_table.setItem(row, 1, type_item)
            
            # 报警信息
            msg_item = QTableWidgetItem(message)
            msg_item.setData(Qt.BackgroundRole, bg_color)
            msg_item.setData(Qt.ForegroundRole, fg_color)
            self.alarm_table.setItem(row, 2, msg_item)
            
            # 触发时间
            if timestamp:
                if isinstance(timestamp, str):
                    time_str = timestamp
                else:
                    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                time_str = ''
            time_item = QTableWidgetItem(time_str)
            time_item.setData(Qt.BackgroundRole, bg_color)
            time_item.setData(Qt.ForegroundRole, fg_color)
            self.alarm_table.setItem(row, 3, time_item)
            
            # 恢复时间
            if recover_time:
                if isinstance(recover_time, str):
                    recover_str = recover_time
                else:
                    recover_str = recover_time.strftime("%Y-%m-%d %H:%M:%S")
            else:
                recover_str = ''
            recover_item = QTableWidgetItem(recover_str)
            recover_item.setData(Qt.BackgroundRole, bg_color)
            recover_item.setData(Qt.ForegroundRole, fg_color)
            self.alarm_table.setItem(row, 4, recover_item)
            
            # 状态
            status_item = QTableWidgetItem(status)
            status_item.setData(Qt.BackgroundRole, bg_color)
            status_item.setData(Qt.ForegroundRole, fg_color)
            self.alarm_table.setItem(row, 5, status_item)
        
        # 只在当前报警模式下清除多余的行
        if self.display_mode == 'current':
            for row in range(len(alarms), self.alarm_table.rowCount()):
                for col in range(6):
                    item = self.alarm_table.item(row, col)
                    if item:
                        item.setText('')
                    else:
                        self.alarm_table.setItem(row, col, QTableWidgetItem(''))
        
        # 恢复滚动位置
        if sb and scroll_pos > 0:
            sb.setValue(scroll_pos)
        
        # 重新启用更新
        self.alarm_table.setUpdatesEnabled(True)
    
    def update_status(self, display_count, total_count):
        """更新状态显示"""
        pass
    
    def _update_title(self):
        """更新标题显示"""
        if self.display_mode == 'current':
            self.title_label.setText("实时报警")
        elif self.display_mode == 'buffer':
            self.title_label.setText("报警缓冲区")
        elif self.display_mode == 'history':
            self.title_label.setText("报警历史记录")
    
    def open_config_dialog(self):
        """打开配置对话框"""
        try:
            dialog = AlarmDisplayConfigDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                # 应用配置
                self.apply_config(dialog.get_config())
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "错误", f"打开配置对话框失败: {str(e)}")
    
    def apply_config(self, config):
        """应用配置"""
        self.visible_alarm_types = config.get('visible_alarm_types', set())
        self.max_display_count = config.get('max_display_count', 9999)
        self.display_mode = config.get('display_mode', 'current')
        
        # 退出查询模式
        self._is_query_mode = False
        
        # 更新标题
        self._update_title()
        
        # 立即刷新显示
        self.refresh_alarms()
    
    def acknowledge_selected_alarm(self):
        """确认选中的报警"""
        if not self.system_service_manager:
            QMessageBox.warning(self, "错误", "系统服务管理器未初始化")
            return
        
        # 获取选中的行
        selected_rows = set()
        selection_model = self.alarm_table.selectionModel()
        if selection_model:
            selected_indexes = selection_model.selectedIndexes()
            for index in selected_indexes:
                selected_rows.add(index.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "提示", "请先选择要确认的报警")
            return
        
        # 确认选中的报警
        acknowledged_count = 0
        for row in selected_rows:
            alarm_id_item = self.alarm_table.item(row, 0)
            if alarm_id_item:
                alarm_id = alarm_id_item.text()
                if alarm_id and alarm_id != '':
                    success = self.system_service_manager.acknowledge_alarm(alarm_id)
                    if success:
                        acknowledged_count += 1
        
        if acknowledged_count > 0:
            self.refresh_alarms()
        else:
            QMessageBox.warning(self, "提示", "没有可确认的报警")
    
    def acknowledge_all_alarms(self):
        """确认所有报警"""
        if not self.system_service_manager:
            QMessageBox.warning(self, "错误", "系统服务管理器未初始化")
            return
        
        # 获取所有活动报警
        active_alarms = self.system_service_manager.get_active_alarms()
        
        if not active_alarms:
            QMessageBox.information(self, "提示", "没有可确认的报警")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self, 
            "确认", 
            f"确定要确认所有 {len(active_alarms)} 条报警吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            acknowledged_count = 0
            from scada_app.core.system_service_manager import AlarmStatus
            for alarm_state in active_alarms:
                if alarm_state.status == AlarmStatus.ACTIVE:
                    success = self.system_service_manager.acknowledge_alarm(alarm_state.alarm_id)
                    if success:
                        acknowledged_count += 1
            
            if acknowledged_count > 0:
                QMessageBox.information(self, "成功", f"已确认 {acknowledged_count} 条报警")
                self.refresh_alarms()
    
    def get_config(self):
        """获取当前配置"""
        return {
            'visible_alarm_types': self.visible_alarm_types,
            'max_display_count': self.max_display_count,
            'display_mode': self.display_mode
        }
    
    def show_query_dialog(self):
        """显示查询对话框"""
        try:
            # 检查是否有选中的报警
            selected_alarm_id = self.get_selected_alarm_id()
            
            dialog = AlarmQueryDialog(self, selected_alarm_id)
            if dialog.exec_() == QDialog.Accepted:
                query_params = dialog.get_query_params()
                self.query_alarms(query_params)
        except Exception as e:
            QMessageBox.critical(self, "查询错误", f"查询报警时发生错误：{str(e)}")
            import traceback
            traceback.print_exc()
    
    def query_alarms(self, query_params):
        """查询报警"""
        try:
            if not self.system_service_manager:
                QMessageBox.warning(self, "错误", "系统服务管理器未初始化")
                return
            
            # 进入查询模式
            self._is_query_mode = True
            
            # 查询报警
            alarms = self.system_service_manager.query_alarms(query_params)
            
            # 更新表格
            self._update_table(alarms)
            
            # 更新标题
            self.title_label.setText(f"查询结果 ({len(alarms)} 条)")
            
            # 显示退出查询按钮
            self.exit_query_btn.setVisible(True)
        except Exception as e:
            QMessageBox.critical(self, "查询错误", f"查询报警时发生错误：{str(e)}")
            import traceback
            traceback.print_exc()
    
    def exit_query_mode(self):
        """退出查询模式"""
        # 退出查询模式
        self._is_query_mode = False
        
        # 隐藏退出查询按钮
        self.exit_query_btn.setVisible(False)
        
        # 立即刷新显示
        self.refresh_alarms()
    
    def get_selected_alarm_id(self):
        """获取选中的报警ID"""
        try:
            selected_items = self.alarm_table.selectedItems()
            if not selected_items:
                return None
            
            # 获取选中行的报警ID（第0列）
            selected_row = self.alarm_table.currentRow()
            if selected_row < 0:
                return None
            
            alarm_id_item = self.alarm_table.item(selected_row, 0)
            if alarm_id_item:
                return alarm_id_item.text()
            
            return None
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None


class AlarmDisplayConfigDialog(QDialog):
    """报警显示配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.type_checkboxes = {}  # 初始化为空字典，防止访问错误
        self.setWindowTitle("报警显示配置")
        self.setModal(True)
        self.setMinimumSize(400, 500)
        
        try:
            self.init_ui()
            self.load_current_config()
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 报警类型筛选
        alarm_type_group = QGroupBox("显示报警类型")
        alarm_type_layout = QVBoxLayout()
        
        # 全选/全不选按钮
        select_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self.select_all_types)
        select_layout.addWidget(self.select_all_btn)
        
        self.select_none_btn = QPushButton("全不选")
        self.select_none_btn.clicked.connect(self.select_no_types)
        select_layout.addWidget(self.select_none_btn)
        
        select_layout.addStretch()
        alarm_type_layout.addLayout(select_layout)
        
        # 报警类型复选框
        self.type_checkboxes = {}
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 获取所有报警类型
        alarm_type_names = alarm_type_manager.get_alarm_type_names()
        
        for type_name in alarm_type_names:
            checkbox = QCheckBox(type_name)
            self.type_checkboxes[type_name] = checkbox
            scroll_layout.addWidget(checkbox)
        
        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(150)
        alarm_type_layout.addWidget(scroll_area)
        
        alarm_type_group.setLayout(alarm_type_layout)
        layout.addWidget(alarm_type_group)
        
        # 显示设置
        display_group = QGroupBox("显示设置")
        display_layout = QFormLayout()
        
        # 显示模式
        self.display_mode_combo = QComboBox()
        self.display_mode_combo.addItems(["当前报警状态", "报警缓冲区", "报警记录"])
        display_layout.addRow("显示模式:", self.display_mode_combo)
        
        self.max_count_spin = QSpinBox()
        self.max_count_spin.setRange(1, 9999)
        self.max_count_spin.setValue(50)
        display_layout.addRow("最大显示数量:", self.max_count_spin)
        
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.apply_btn = QPushButton("应用")
        self.apply_btn.clicked.connect(self.apply_config)
        button_layout.addWidget(self.apply_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_current_config(self):
        """加载当前配置"""
        if self.parent_widget:
            config = self.parent_widget.get_config()
            
            # 报警类型
            visible_types = config.get('visible_alarm_types', set())
            for type_name, checkbox in self.type_checkboxes.items():
                checkbox.setChecked(type_name in visible_types)
            
            # 显示设置
            display_mode = config.get('display_mode', 'current')
            mode_map = {
                'current': '当前报警状态',
                'buffer': '报警缓冲区',
                'history': '报警记录'
            }
            mode_index = self.display_mode_combo.findText(mode_map.get(display_mode, '当前报警状态'))
            if mode_index >= 0:
                self.display_mode_combo.setCurrentIndex(mode_index)
            
            self.max_count_spin.setValue(config.get('max_display_count', 50))
    
    def select_all_types(self):
        """选择所有报警类型"""
        for checkbox in self.type_checkboxes.values():
            checkbox.setChecked(True)
    
    def select_no_types(self):
        """取消选择所有报警类型"""
        for checkbox in self.type_checkboxes.values():
            checkbox.setChecked(False)
    
    def apply_config(self):
        """应用配置"""
        if self.parent_widget:
            self.parent_widget.apply_config(self.get_config())
    
    def get_config(self):
        """获取配置"""
        visible_types = set()
        for type_name, checkbox in self.type_checkboxes.items():
            if checkbox.isChecked():
                visible_types.add(type_name)
        
        # 转换显示模式
        mode_text = self.display_mode_combo.currentText()
        mode_map = {
            '当前报警状态': 'current',
            '报警缓冲区': 'buffer',
            '报警记录': 'history'
        }
        display_mode = mode_map.get(mode_text, 'current')
        
        return {
            'visible_alarm_types': visible_types,
            'max_display_count': self.max_count_spin.value(),
            'auto_scroll': self.auto_scroll_check.isChecked(),
            'show_timestamp': self.show_timestamp_check.isChecked(),
            'show_alarm_type': self.show_type_check.isChecked(),
            'show_alarm_id': self.show_id_check.isChecked(),
            'show_tag_name': self.show_tag_check.isChecked(),
            'display_mode': display_mode
        }


class AlarmQueryDialog(QDialog):
    """报警查询对话框"""
    
    def __init__(self, parent=None, selected_alarm_id=None):
        super().__init__(parent)
        self.selected_alarm_id = selected_alarm_id
        self.setWindowTitle("报警查询")
        self.setModal(True)
        self.setFixedWidth(400)
        
        self.init_ui()
        
        # 如果有选中的报警ID，自动填充并切换到报警ID查询
        if self.selected_alarm_id:
            try:
                self.alarm_id_edit.setValue(int(self.selected_alarm_id))
                self.query_type_combo.setCurrentIndex(1)  # 切换到按报警ID查询
            except (ValueError, TypeError):
                pass
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 查询方式
        query_type_layout = QHBoxLayout()
        query_type_layout.addWidget(QLabel("查询方式："))
        
        self.query_type_combo = QComboBox()
        self.query_type_combo.addItems(["按时间段查询", "按报警ID查询"])
        self.query_type_combo.currentIndexChanged.connect(self.on_query_type_changed)
        query_type_layout.addWidget(self.query_type_combo)
        
        layout.addLayout(query_type_layout)
        
        # 时间段查询控件
        self.time_query_widget = QWidget()
        time_query_layout = QFormLayout()
        
        self.start_date_edit = QDateTimeEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_date_edit.setDateTime(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
        time_query_layout.addRow("开始时间：", self.start_date_edit)
        
        self.end_date_edit = QDateTimeEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_date_edit.setDateTime(datetime.now())
        time_query_layout.addRow("结束时间：", self.end_date_edit)
        
        self.time_query_widget.setLayout(time_query_layout)
        layout.addWidget(self.time_query_widget)
        
        # 报警ID查询控件
        self.alarm_id_widget = QWidget()
        alarm_id_layout = QFormLayout()
        
        self.alarm_id_edit = QSpinBox()
        self.alarm_id_edit.setRange(0, 999999)
        self.alarm_id_edit.setPrefix("报警ID: ")
        alarm_id_layout.addRow("报警ID：", self.alarm_id_edit)
        
        self.alarm_id_widget.setLayout(alarm_id_layout)
        self.alarm_id_widget.setVisible(False)
        layout.addWidget(self.alarm_id_widget)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.query_button = QPushButton("查询")
        self.query_button.clicked.connect(self.accept)
        button_layout.addWidget(self.query_button)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def on_query_type_changed(self, index):
        """查询方式改变"""
        if index == 0:  # 按时间段查询
            self.time_query_widget.setVisible(True)
            self.alarm_id_widget.setVisible(False)
        else:  # 按报警ID查询
            self.time_query_widget.setVisible(False)
            self.alarm_id_widget.setVisible(True)
    
    def get_query_params(self):
        """获取查询参数"""
        query_type = self.query_type_combo.currentIndex()
        
        if query_type == 0:  # 按时间段查询
            return {
                'type': 'time_range',
                'start_time': self.start_date_edit.dateTime().toPyDateTime(),
                'end_time': self.end_date_edit.dateTime().toPyDateTime()
            }
        else:  # 按报警ID查询
            return {
                'type': 'alarm_id',
                'alarm_id': str(self.alarm_id_edit.value())
            }


if __name__ == "__main__":
    """测试代码"""
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 创建测试控件
    widget = AlarmDisplayWidget()
    widget.show()
    
    sys.exit(app.exec_())