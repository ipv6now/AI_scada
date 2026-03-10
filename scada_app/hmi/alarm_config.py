"""
报警配置对话框
允许用户配置报警规则和设置
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QPushButton, QLineEdit, QComboBox, QLabel, 
                             QDialogButtonBox, QGroupBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QSpinBox, QCheckBox,
                             QTextEdit, QMessageBox, QDoubleSpinBox)
from PyQt5.QtCore import Qt
from scada_app.core.data_manager import DataManager


class AlarmRule:
    def __init__(self, tag_name="", alarm_type="限值", condition="高", threshold=0.0, 
                 message="", enabled=True, priority="中"):
        self.tag_name = tag_name
        self.alarm_type = alarm_type  # 限值, 状态变化, 变化率
        self.condition = condition    # 高, 低, 很高, 很低 用于限值
        self.threshold = threshold
        self.message = message
        self.enabled = enabled
        self.priority = priority    # 低, 中, 高, 危急


class AlarmConfigDialog(QDialog):
    def __init__(self, parent=None, data_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.alarm_rules = []
        self.setWindowTitle("报警配置")
        self.setGeometry(200, 200, 900, 600)
        
        self.init_ui()
        self.load_existing_rules()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("报警配置")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Alarm rules table
        self.rule_table = QTableWidget()
        self.rule_table.setColumnCount(7)
        self.rule_table.setHorizontalHeaderLabels([
            "标签名称", "类型", "条件", "阈值", "消息", "报警类型", "启用"
        ])
        header = self.rule_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(QLabel("报警规则:"))
        layout.addWidget(self.rule_table)
        
        # Buttons for alarm rules
        btn_layout = QHBoxLayout()
        
        self.add_rule_btn = QPushButton("添加规则")
        self.add_rule_btn.clicked.connect(self.add_rule)
        btn_layout.addWidget(self.add_rule_btn)
        
        self.edit_rule_btn = QPushButton("编辑规则")
        self.edit_rule_btn.clicked.connect(self.edit_rule)
        btn_layout.addWidget(self.edit_rule_btn)
        
        self.remove_rule_btn = QPushButton("删除规则")
        self.remove_rule_btn.clicked.connect(self.remove_rule)
        btn_layout.addWidget(self.remove_rule_btn)
        
        layout.addLayout(btn_layout)
        
        # Rule configuration group
        config_group = QGroupBox("规则配置")
        config_layout = QFormLayout()
        
        # Tag selection
        self.tag_combo = QComboBox()
        if self.data_manager:
            for tag_name in self.data_manager.tags.keys():
                self.tag_combo.addItem(tag_name)
        config_layout.addRow("标签:", self.tag_combo)
        
        # Alarm type
        self.type_combo = QComboBox()
        self.type_combo.addItems(["限值", "状态变化", "变化率"])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        config_layout.addRow("类型:", self.type_combo)
        
        # Condition
        self.condition_combo = QComboBox()
        self.condition_combo.addItems(["高", "低", "很高", "很低"])
        config_layout.addRow("条件:", self.condition_combo)
        
        # Threshold
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(-999999, 999999)
        self.threshold_spin.setDecimals(2)
        config_layout.addRow("阈值:", self.threshold_spin)
        
        # Message
        self.message_edit = QTextEdit()
        self.message_edit.setMaximumHeight(60)
        config_layout.addRow("消息:", self.message_edit)
        
        # Priority
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["低", "中", "高", "危急"])
        config_layout.addRow("报警类型:", self.priority_combo)
        
        # Enabled
        self.enabled_check = QCheckBox("启用")
        self.enabled_check.setChecked(True)
        config_layout.addRow("", self.enabled_check)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("应用规则")
        self.apply_btn.clicked.connect(self.apply_rule)
        button_layout.addWidget(self.apply_btn)
        
        button_layout.addStretch()
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        button_layout.addWidget(button_box)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def on_type_changed(self, alarm_type):
        """Update available conditions based on alarm type"""
        self.condition_combo.clear()
        if alarm_type == "限值":
            self.condition_combo.addItems(["高", "低", "很高", "很低"])
            self.threshold_spin.setEnabled(True)
        elif alarm_type == "状态变化":
            self.condition_combo.addItems(["假变真", "真变假", "变化"])
            self.threshold_spin.setEnabled(False)
        elif alarm_type == "变化率":
            self.condition_combo.addItems(["正", "负"])
            self.threshold_spin.setEnabled(True)
    
    def load_existing_rules(self):
        """Load existing alarm rules if available"""
        # For now, just initialize with empty list
        # In a real implementation, this would load from database/config
        pass
    
    def add_rule(self):
        """Add a new alarm rule"""
        rule = AlarmRule()
        self.alarm_rules.append(rule)
        self.update_rule_table()
    
    def edit_rule(self):
        """Edit selected alarm rule"""
        current_row = self.rule_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "无选择", "请选择要编辑的规则。")
            return
        
        if current_row < len(self.alarm_rules):
            rule = self.alarm_rules[current_row]
            self.populate_form_from_rule(rule)
    
    def remove_rule(self):
        """Remove selected alarm rule"""
        current_row = self.rule_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "无选择", "请选择要删除的规则。")
            return
        
        if current_row < len(self.alarm_rules):
            del self.alarm_rules[current_row]
            self.update_rule_table()
    
    def apply_rule(self):
        """Apply the current form settings to a rule"""
        rule = AlarmRule(
            tag_name=self.tag_combo.currentText(),
            alarm_type=self.type_combo.currentText(),
            condition=self.condition_combo.currentText(),
            threshold=self.threshold_spin.value(),
            message=self.message_edit.toPlainText(),
            enabled=self.enabled_check.isChecked(),
            priority=self.priority_combo.currentText()
        )
        
        # If we're editing an existing rule, update it; otherwise add new
        current_row = self.rule_table.currentRow()
        if 0 <= current_row < len(self.alarm_rules):
            self.alarm_rules[current_row] = rule
        else:
            self.alarm_rules.append(rule)
        
        self.update_rule_table()
        self.clear_form()
    
    def populate_form_from_rule(self, rule):
        """Populate form fields with rule data"""
        idx = self.tag_combo.findText(rule.tag_name)
        if idx >= 0:
            self.tag_combo.setCurrentIndex(idx)
        
        idx = self.type_combo.findText(rule.alarm_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        
        idx = self.condition_combo.findText(rule.condition)
        if idx >= 0:
            self.condition_combo.setCurrentIndex(idx)
        
        self.threshold_spin.setValue(rule.threshold)
        self.message_edit.setPlainText(rule.message)
        
        idx = self.priority_combo.findText(rule.priority)
        if idx >= 0:
            self.priority_combo.setCurrentIndex(idx)
        
        self.enabled_check.setChecked(rule.enabled)
    
    def clear_form(self):
        """Clear the form fields"""
        self.tag_combo.setCurrentIndex(-1)
        self.type_combo.setCurrentIndex(0)
        self.condition_combo.setCurrentIndex(0)
        self.threshold_spin.setValue(0.0)
        self.message_edit.clear()
        self.priority_combo.setCurrentIndex(1)  # 中
        self.enabled_check.setChecked(True)
    
    def update_rule_table(self):
        """Update the rule table with current rules"""
        self.rule_table.setRowCount(len(self.alarm_rules))
        
        for row, rule in enumerate(self.alarm_rules):
            # Tag Name
            tag_item = QTableWidgetItem(rule.tag_name)
            self.rule_table.setItem(row, 0, tag_item)
            
            # Type
            type_item = QTableWidgetItem(rule.alarm_type)
            self.rule_table.setItem(row, 1, type_item)
            
            # Condition
            cond_item = QTableWidgetItem(rule.condition)
            self.rule_table.setItem(row, 2, cond_item)
            
            # Threshold
            thresh_item = QTableWidgetItem(str(rule.threshold))
            self.rule_table.setItem(row, 3, thresh_item)
            
            # Message
            msg_item = QTableWidgetItem(rule.message[:30] + "..." if len(rule.message) > 30 else rule.message)
            self.rule_table.setItem(row, 4, msg_item)
            
            # Priority
            prio_item = QTableWidgetItem(rule.priority)
            self.rule_table.setItem(row, 5, prio_item)
            
            # Enabled
            enabled_text = "是" if rule.enabled else "否"
            enabled_item = QTableWidgetItem(enabled_text)
            self.rule_table.setItem(row, 6, enabled_item)
    
    def get_alarm_rules(self):
        """Return the configured alarm rules"""
        return self.alarm_rules