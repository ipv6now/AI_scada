"""
实时报警显示控件 - 支持按类别筛选和高级属性配置
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QListWidget, QListWidgetItem, QCheckBox, QGroupBox,
                             QPushButton, QScrollArea, QFrame, QComboBox,
                             QMessageBox, QDialog, QFormLayout, QSpinBox)
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
        self.max_display_count = 50       # 最大显示数量
        self.auto_scroll = True           # 自动滚动
        self.show_timestamp = True        # 显示时间戳
        self.show_alarm_type = True       # 显示报警类型
        self.show_alarm_id = True         # 显示报警ID
        
        # 初始化UI
        self.init_ui()
        
        # 启动定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_alarms)
        self.timer.start(1000)  # 每秒刷新一次
    
    def set_data_manager(self, data_manager):
        """设置数据管理器"""
        self.data_manager = data_manager
    
    def set_system_service_manager(self, system_service_manager):
        """设置系统服务管理器"""
        self.system_service_manager = system_service_manager
        
        # 初始化可见报警类型（默认显示所有）
        self.visible_alarm_types = set(alarm_type_manager.get_alarm_type_names())
        
        self.init_ui()
        self.start_refresh_timer()
    
    def init_ui(self):
        """初始化界面"""
        main_layout = QVBoxLayout()
        
        # 标题栏
        title_layout = QHBoxLayout()
        
        self.title_label = QLabel("实时报警")
        self.title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_layout.addWidget(self.title_label)
        
        self.status_label = QLabel("就绪")
        title_layout.addWidget(self.status_label)
        
        title_layout.addStretch()
        
        # 配置按钮
        self.config_btn = QPushButton("配置")
        self.config_btn.clicked.connect(self.open_config_dialog)
        self.config_btn.setMaximumWidth(60)
        title_layout.addWidget(self.config_btn)
        
        main_layout.addLayout(title_layout)
        
        # 报警列表
        self.alarm_list = QListWidget()
        self.alarm_list.setAlternatingRowColors(True)
        self.alarm_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #cccccc;
                border-radius: 3px;
                background-color: #f8f8f8;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #e0e0e0;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
            }
        """)
        main_layout.addWidget(self.alarm_list)
        
        # 状态栏
        self.count_label = QLabel("报警数量: 0")
        main_layout.addWidget(self.count_label)
        
        self.setLayout(main_layout)
        
        # 设置最小尺寸
        self.setMinimumSize(400, 300)
    
    def start_refresh_timer(self):
        """启动刷新定时器"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_alarms)
        self.refresh_timer.start(2000)  # 每2秒刷新一次
    
    def refresh_alarms(self):
        """刷新报警列表"""
        if not self.data_manager and not self.system_service_manager:
            return
        
        # 清空当前列表
        self.alarm_list.clear()
        
        # 获取报警数据
        alarms = self.get_current_alarms()
        
        # 应用筛选
        filtered_alarms = self.filter_alarms(alarms)
        
        # 限制显示数量
        display_alarms = filtered_alarms[:self.max_display_count]
        
        # 显示报警
        for alarm in display_alarms:
            self.add_alarm_item(alarm)
        
        # 更新状态
        self.update_status(len(display_alarms), len(filtered_alarms))
        
        # 自动滚动到底部
        if self.auto_scroll and display_alarms:
            self.alarm_list.scrollToBottom()
    
    def get_current_alarms(self):
        """获取当前报警数据"""
        alarms = []
        
        # 优先从系统服务管理器获取实时报警
        if self.system_service_manager:
            try:
                active_alarms = self.system_service_manager.get_active_alarms()
                for alarm_state in active_alarms:
                    # 调试输出：检查报警状态中的alarm_id
                    print(f"[DEBUG] 报警状态: tag={alarm_state.tag_name}, alarm_id={alarm_state.alarm_id}")
                    
                    alarm = {
                        'tag_name': alarm_state.tag_name,
                        'alarm_type': alarm_state.alarm_type,
                        'message': alarm_state.message,
                        'alarm_type_name': alarm_state.alarm_type_name,
                        'alarm_id': alarm_state.alarm_id,  # 添加报警ID
                        'status': '活动',
                        'timestamp': alarm_state.first_trigger_time,
                        'is_active': True
                    }
                    alarms.append(alarm)
            except Exception as e:
                print(f"[ALARM DISPLAY] 从系统服务管理器获取报警失败: {e}")
        
        # 如果没有实时数据，从数据管理器获取
        if not alarms and self.data_manager:
            for alarm in self.data_manager.alarms:
                # 显示活动报警和最近恢复的报警（1小时内）
                is_active = alarm.get('active', True)
                is_recently_recovered = False
                
                if not is_active:
                    # 检查是否是最近恢复的报警（1小时内）
                    recovery_time = alarm.get('recovery_time')
                    if recovery_time:
                        time_diff = datetime.now() - recovery_time
                        if time_diff.total_seconds() <= 3600:  # 1小时内
                            is_recently_recovered = True
                
                if is_active or is_recently_recovered:
                    status = '活动' if is_active else '已恢复'
                    converted_alarm = {
                        'tag_name': alarm.get('tag_name', ''),
                        'alarm_type': alarm.get('alarm_type', ''),
                        'message': alarm.get('message', ''),
                        'alarm_type_name': alarm.get('alarm_type_name', alarm.get('priority', '中')),
                        'alarm_id': alarm.get('alarm_id'),  # 添加报警ID
                        'status': status,
                        'timestamp': alarm.get('timestamp', datetime.now()),
                        'is_active': is_active,
                        'recovery_time': alarm.get('recovery_time')
                    }
                    alarms.append(converted_alarm)
        
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
    
    def add_alarm_item(self, alarm):
        """添加报警项到列表"""
        item = QListWidgetItem()
        
        # 构建显示文本
        display_text = self.build_display_text(alarm)
        item.setText(display_text)
        
        # 设置颜色
        self.set_item_color(item, alarm)
        
        # 设置字体
        font = QFont()
        font.setPointSize(9)
        if alarm.get('is_active', False):
            font.setBold(True)
        item.setFont(font)
        
        self.alarm_list.addItem(item)
    
    def build_display_text(self, alarm):
        """构建显示文本"""
        parts = []
        
        # 调试输出：检查报警数据中的alarm_id
        print(f"[DEBUG] 构建显示文本: alarm_id={alarm.get('alarm_id')}, 显示ID={self.show_alarm_id}")
        
        # 报警ID
        if self.show_alarm_id and alarm.get('alarm_id'):
            parts.append(f"ID:{alarm['alarm_id']}")
        
        # 时间戳
        if self.show_timestamp:
            timestamp = alarm['timestamp'].strftime("%H:%M:%S")
            parts.append(f"[{timestamp}]")
        
        # 报警类型
        if self.show_alarm_type:
            alarm_type_name = alarm.get('alarm_type_name', '中')
            parts.append(f"[{alarm_type_name}]")
        
        # 标签名称
        parts.append(alarm['tag_name'])
        
        # 报警消息
        parts.append(f"- {alarm['message']}")
        
        return " ".join(parts)
    
    def set_item_color(self, item, alarm):
        """设置项颜色"""
        alarm_type_name = alarm.get('alarm_type_name', '中')
        
        try:
            alarm_type = alarm_type_manager.get_alarm_type_by_display_name(alarm_type_name)
            if alarm_type:
                # 使用报警类型配置的颜色
                fg_color = alarm_type_manager.get_qcolor_from_hex(alarm_type.foreground_color)
                bg_color = alarm_type_manager.get_qcolor_from_hex(alarm_type.background_color)
                
                item.setForeground(fg_color)
                item.setBackground(bg_color)
        except Exception:
            # 如果颜色配置失败，使用默认颜色
            if alarm.get('is_active', False):
                item.setBackground(QColor(255, 220, 220))  # 活动报警红色背景
            else:
                item.setBackground(QColor(240, 240, 240))  # 非活动报警灰色背景
    
    def update_status(self, display_count, total_count):
        """更新状态显示"""
        self.count_label.setText(f"报警数量: {display_count}/{total_count}")
        
        if display_count > 0:
            self.status_label.setText("有报警")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.status_label.setText("正常")
            self.status_label.setStyleSheet("color: green;")
    
    def open_config_dialog(self):
        """打开配置对话框"""
        dialog = AlarmDisplayConfigDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # 应用配置
            self.apply_config(dialog.get_config())
    
    def apply_config(self, config):
        """应用配置"""
        self.visible_alarm_types = config.get('visible_alarm_types', set())
        self.max_display_count = config.get('max_display_count', 50)
        self.auto_scroll = config.get('auto_scroll', True)
        self.show_timestamp = config.get('show_timestamp', True)
        self.show_alarm_type = config.get('show_alarm_type', True)
        self.show_alarm_id = config.get('show_alarm_id', True)
        
        # 立即刷新显示
        self.refresh_alarms()
    
    def get_config(self):
        """获取当前配置"""
        return {
            'visible_alarm_types': self.visible_alarm_types,
            'max_display_count': self.max_display_count,
            'auto_scroll': self.auto_scroll,
            'show_timestamp': self.show_timestamp,
            'show_alarm_type': self.show_alarm_type,
            'show_alarm_id': self.show_alarm_id
        }


class AlarmDisplayConfigDialog(QDialog):
    """报警显示配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.setWindowTitle("报警显示配置")
        self.setModal(True)
        self.setMinimumSize(400, 500)
        
        self.init_ui()
        self.load_current_config()
    
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
        
        self.max_count_spin = QSpinBox()
        self.max_count_spin.setRange(1, 200)
        self.max_count_spin.setValue(50)
        display_layout.addRow("最大显示数量:", self.max_count_spin)
        
        self.auto_scroll_check = QCheckBox("自动滚动到底部")
        self.auto_scroll_check.setChecked(True)
        display_layout.addRow(self.auto_scroll_check)
        
        self.show_timestamp_check = QCheckBox("显示时间戳")
        self.show_timestamp_check.setChecked(True)
        display_layout.addRow(self.show_timestamp_check)
        
        self.show_type_check = QCheckBox("显示报警类型")
        self.show_type_check.setChecked(True)
        display_layout.addRow(self.show_type_check)
        
        self.show_id_check = QCheckBox("显示报警ID")
        self.show_id_check.setChecked(True)
        display_layout.addRow(self.show_id_check)
        
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
            self.max_count_spin.setValue(config.get('max_display_count', 50))
            self.auto_scroll_check.setChecked(config.get('auto_scroll', True))
            self.show_timestamp_check.setChecked(config.get('show_timestamp', True))
            self.show_type_check.setChecked(config.get('show_alarm_type', True))
            self.show_id_check.setChecked(config.get('show_alarm_id', True))
    
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
        
        return {
            'visible_alarm_types': visible_types,
            'max_display_count': self.max_count_spin.value(),
            'auto_scroll': self.auto_scroll_check.isChecked(),
            'show_timestamp': self.show_timestamp_check.isChecked(),
            'show_alarm_type': self.show_type_check.isChecked(),
            'show_alarm_id': self.show_id_check.isChecked()
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