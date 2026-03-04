"""
数据日志配置对话框
允许用户配置数据日志设置，支持 SQL Server
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QPushButton, QLineEdit, QComboBox, QLabel,
                             QDialogButtonBox, QGroupBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QSpinBox, QCheckBox,
                             QTextEdit, QMessageBox, QDoubleSpinBox, QGridLayout,
                             QStyledItemDelegate, QWidget)
from PyQt5.QtCore import Qt, pyqtSignal
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from scada_app.core.data_manager import DataManager
from scada_app.core.sql_server_manager import sql_server_manager
from scada_app.hmi.variable_selector import VariableSelectorDialog


class LogRule:
    def __init__(self, tag_name="", sample_rate=1.0, storage_duration_days=30, 
                 enabled=True, rule_id=None):
        self.tag_name = tag_name
        self.sample_rate = sample_rate
        self.storage_duration_days = storage_duration_days
        self.enabled = enabled
        self.rule_id = rule_id
    
    def to_dict(self):
        return {
            'tag_name': self.tag_name,
            'sample_rate': self.sample_rate,
            'storage_duration_days': self.storage_duration_days,
            'enabled': self.enabled,
            'rule_id': self.rule_id
        }


class TagNameEditor(QWidget):
    valueChanged = pyqtSignal(str)
    
    def __init__(self, tag_names, data_manager=None, config_manager=None, parent=None):
        super().__init__(parent)
        self.tag_names = tag_names
        self.data_manager = data_manager
        self.config_manager = config_manager
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.line_edit = QLineEdit()
        self.line_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.line_edit)
        
        self.btn = QPushButton("...")
        self.btn.setFixedSize(24, 24)
        self.btn.clicked.connect(self._open_selector)
        layout.addWidget(self.btn)
        
        self.setLayout(layout)
    
    def _on_text_changed(self, text):
        self.valueChanged.emit(text)
    
    def _open_selector(self):
        dialog = VariableSelectorDialog(self, self.data_manager, self.config_manager, self.line_edit.text())
        if dialog.exec_() == QDialog.Accepted:
            var = dialog.get_selected_variable()
            if var:
                self.line_edit.setText(var)
    
    def setText(self, text):
        self.line_edit.setText(text)
    
    def text(self):
        return self.line_edit.text()


class TagNameDelegate(QStyledItemDelegate):
    def __init__(self, tag_names, data_manager=None, config_manager=None, parent=None):
        super().__init__(parent)
        self.tag_names = tag_names
        self.data_manager = data_manager
        self.config_manager = config_manager
    
    def createEditor(self, parent, option, index):
        editor = TagNameEditor(self.tag_names, self.data_manager, self.config_manager, parent)
        editor.valueChanged.connect(lambda: self.commitData.emit(editor))
        return editor
    
    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        editor.setText(value if value else "")
    
    def setModelData(self, editor, model, index):
        model.setData(index, editor.text(), Qt.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class EnabledDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(["是", "否"])
        return combo
    
    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        editor.setCurrentText(value if value in ["是", "否"] else "是")
    
    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)


class DataLoggingConfigDialog(QDialog):
    def __init__(self, parent=None, data_manager=None, config_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.config_manager = config_manager
        self.log_rules = []
        self.setWindowTitle("数据日志配置")
        self.setGeometry(200, 200, 800, 500)

        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        self.setWindowModality(Qt.NonModal)

        self.db_connected = False
        self.db_config_group = None

        self.init_ui()
        self.load_saved_config()
        self.load_rules_from_config_manager()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        title_label = QLabel("数据日志配置")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        self.db_config_group = QGroupBox("SQL Server 数据库配置")
        db_layout = QVBoxLayout()
        
        db_grid_layout = QGridLayout()
        
        self.server_edit = QLineEdit("localhost")
        db_grid_layout.addWidget(QLabel("服务器:"), 0, 0)
        db_grid_layout.addWidget(self.server_edit, 0, 1)
        
        self.database_edit = QLineEdit("HMI_DataLogging")
        db_grid_layout.addWidget(QLabel("数据库:"), 0, 2)
        db_grid_layout.addWidget(self.database_edit, 0, 3)
        
        self.username_edit = QLineEdit("sa")
        db_grid_layout.addWidget(QLabel("用户名:"), 1, 0)
        db_grid_layout.addWidget(self.username_edit, 1, 1)
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        db_grid_layout.addWidget(QLabel("密码:"), 1, 2)
        db_grid_layout.addWidget(self.password_edit, 1, 3)
        
        db_layout.addLayout(db_grid_layout)
        
        db_btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("连接数据库")
        self.connect_btn.clicked.connect(self.connect_to_database)
        db_btn_layout.addWidget(self.connect_btn)
        
        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        db_btn_layout.addWidget(self.status_label)
        db_btn_layout.addStretch()
        
        db_layout.addLayout(db_btn_layout)
        self.db_config_group.setLayout(db_layout)
        layout.addWidget(self.db_config_group)
        
        storage_config_group = QGroupBox("全局存储配置")
        storage_layout = QFormLayout()
        
        self.storage_type_combo = QComboBox()
        self.storage_type_combo.addItems(["SQLite", "CSV文件", "SQL Server"])
        self.storage_type_combo.currentTextChanged.connect(self.on_storage_type_changed)
        storage_layout.addRow("存储方式:", self.storage_type_combo)
        
        storage_config_group.setLayout(storage_layout)
        layout.addWidget(storage_config_group)
        
        rules_label = QLabel("日志规则:")
        layout.addWidget(rules_label)
        
        self.rule_table = QTableWidget()
        self.rule_table.setColumnCount(4)
        self.rule_table.setHorizontalHeaderLabels([
            "标签名称", "采样频率(秒)", "存储时长(天)", "启用"
        ])
        header = self.rule_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.rule_table.setColumnWidth(0, 200)
        self.rule_table.setColumnWidth(1, 100)
        self.rule_table.setColumnWidth(2, 100)
        self.rule_table.setColumnWidth(3, 60)
        
        tag_names = list(self.data_manager.tags.keys()) if self.data_manager else []
        self.tag_delegate = TagNameDelegate(tag_names, self.data_manager, self.config_manager, self)
        self.rule_table.setItemDelegateForColumn(0, self.tag_delegate)
        
        self.enabled_delegate = EnabledDelegate(self)
        self.rule_table.setItemDelegateForColumn(3, self.enabled_delegate)
        
        self.rule_table.cellChanged.connect(self.on_table_cell_changed)
        
        layout.addWidget(self.rule_table)
        
        btn_layout = QHBoxLayout()
        
        self.add_rule_btn = QPushButton("添加规则")
        self.add_rule_btn.clicked.connect(self.add_rule)
        btn_layout.addWidget(self.add_rule_btn)
        
        self.remove_rule_btn = QPushButton("删除规则")
        self.remove_rule_btn.clicked.connect(self.remove_rule)
        btn_layout.addWidget(self.remove_rule_btn)
        
        btn_layout.addStretch()
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        btn_layout.addWidget(button_box)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
    def on_table_cell_changed(self, row, column):
        """Handle table cell changes"""
        if row >= len(self.log_rules):
            return
        
        rule = self.log_rules[row]
        item = self.rule_table.item(row, column)
        if not item:
            return
        
        if column == 0:
            rule.tag_name = item.text()
        elif column == 1:
            try:
                rule.sample_rate = float(item.text())
            except ValueError:
                pass
        elif column == 2:
            try:
                rule.storage_duration_days = int(item.text())
            except ValueError:
                pass
        elif column == 3:
            rule.enabled = item.text() == "是"
        
    def connect_to_database(self):
        """Connect to SQL Server database"""
        try:
            # Configure SQL Server manager
            sql_server_manager.server = self.server_edit.text()
            sql_server_manager.database = self.database_edit.text()
            sql_server_manager.username = self.username_edit.text()
            sql_server_manager.password = self.password_edit.text()

            # Connect and initialize
            if sql_server_manager.connect() and sql_server_manager.initialize_database():
                self.db_connected = True
                self.status_label.setText("已连接")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
                # Save configuration on successful connection
                self.save_config()
                QMessageBox.information(self, "成功", "数据库连接成功！")
            else:
                self.db_connected = False
                self.status_label.setText("连接失败")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
                QMessageBox.warning(self, "错误", "数据库连接失败！")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"数据库连接错误: {str(e)}")
    
    def add_rule(self):
        """Add a new logging rule"""
        rule = LogRule()
        self.log_rules.append(rule)
        self.update_rule_table()
    
    def remove_rule(self):
        """Remove selected logging rule"""
        current_row = self.rule_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "无选择", "请选择要删除的规则。")
            return
        
        if current_row < len(self.log_rules):
            del self.log_rules[current_row]
            self.update_rule_table()
    
    def update_rule_table(self):
        """Update the rule table with current rules"""
        self.rule_table.blockSignals(True)
        self.rule_table.setRowCount(len(self.log_rules))
        
        for row, rule in enumerate(self.log_rules):
            tag_item = QTableWidgetItem(rule.tag_name)
            self.rule_table.setItem(row, 0, tag_item)
            
            rate_item = QTableWidgetItem(str(rule.sample_rate))
            self.rule_table.setItem(row, 1, rate_item)
            
            dur_item = QTableWidgetItem(str(rule.storage_duration_days))
            self.rule_table.setItem(row, 2, dur_item)
            
            enabled_text = "是" if rule.enabled else "否"
            enabled_item = QTableWidgetItem(enabled_text)
            self.rule_table.setItem(row, 3, enabled_item)
        
        self.rule_table.blockSignals(False)
    
    def on_storage_type_changed(self, storage_type_text):
        """Handle storage type change"""
        # Map display text to internal type
        type_map = {
            "SQLite": "sqlite",
            "CSV文件": "csv",
            "SQL Server": "sqlserver"
        }
        storage_type = type_map.get(storage_type_text, "sqlite")
        
        # Update config manager
        if self.config_manager:
            self.config_manager.storage_type = storage_type
        
        # Update storage manager
        try:
            from scada_app.core.data_storage_manager import data_storage_manager
            data_storage_manager.set_storage_type(storage_type)
        except Exception as e:
            print(f"Error setting storage type: {e}")
    
    def get_log_rules(self):
        """Return the configured logging rules"""
        return self.log_rules

    def load_saved_config(self):
        """Load saved database configuration from sql_server_manager"""
        # Load saved values from sql_server_manager (which is loaded from project file)
        server = sql_server_manager.server or "localhost"
        database = sql_server_manager.database or "HMI_DataLogging"
        username = sql_server_manager.username or "sa"
        password = sql_server_manager.password or ""
        port = getattr(sql_server_manager, 'port', 1433)

        # Set values to UI
        self.server_edit.setText(server)
        self.database_edit.setText(database)
        self.username_edit.setText(username)
        self.password_edit.setText(password)
        
        # Load storage type from config manager
        if self.config_manager:
            storage_type = getattr(self.config_manager, 'storage_type', 'sqlite')
            type_map = {
                "sqlite": "SQLite",
                "csv": "CSV文件",
                "sqlserver": "SQL Server"
            }
            display_text = type_map.get(storage_type, "SQLite")
            idx = self.storage_type_combo.findText(display_text)
            if idx >= 0:
                self.storage_type_combo.setCurrentIndex(idx)

    def save_config(self):
        """Save database configuration to sql_server_manager"""
        # Update sql_server_manager (will be saved to project file)
        sql_server_manager.server = self.server_edit.text()
        sql_server_manager.database = self.database_edit.text()
        sql_server_manager.username = self.username_edit.text()
        sql_server_manager.password = self.password_edit.text()

    def sync_rules_to_config_manager(self):
        """Sync logging rules to config_manager for project save"""
        rules_dict_list = []
        for rule in self.log_rules:
            rules_dict_list.append({
                'tag_name': rule.tag_name,
                'sample_rate': rule.sample_rate,
                'storage_duration_days': rule.storage_duration_days,
                'enabled': rule.enabled,
                'rule_id': rule.rule_id
            })

        if self.config_manager:
            if hasattr(self.config_manager, 'logging_rules'):
                self.config_manager.logging_rules = rules_dict_list
            elif hasattr(self.config_manager, 'set_logging_rules'):
                self.config_manager.set_logging_rules(rules_dict_list)

    def load_rules_from_config_manager(self):
        """Load logging rules from config_manager when opening dialog"""
        if not self.config_manager:
            return

        rules_data = []

        if hasattr(self.config_manager, 'logging_rules'):
            rules_data = self.config_manager.logging_rules
        elif hasattr(self.config_manager, 'get_logging_rules'):
            rules_data = self.config_manager.get_logging_rules()

        if rules_data:
            self.log_rules = []
            for rule_data in rules_data:
                rule = LogRule(
                    tag_name=rule_data.get('tag_name', ''),
                    sample_rate=rule_data.get('sample_rate', 1.0),
                    storage_duration_days=rule_data.get('storage_duration_days', 30),
                    enabled=rule_data.get('enabled', True),
                    rule_id=rule_data.get('rule_id')
                )
                self.log_rules.append(rule)
            self.update_rule_table()

    def accept(self):
        """Override accept to save configuration before closing"""
        self.save_config()
        self.sync_rules_to_config_manager()
        super().accept()