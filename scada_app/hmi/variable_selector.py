from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QTreeWidget, QTreeWidgetItem, QPushButton, QLabel,
                             QDialogButtonBox, QSplitter, QGroupBox, QWidget)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon


class VariableSelectorDialog(QDialog):
    def __init__(self, parent=None, data_manager=None, config_manager=None, current_value=''):
        super().__init__(parent)
        self.data_manager = data_manager
        self.config_manager = config_manager
        self.current_value = current_value
        self.selected_variable = None
        self.recent_variables = []
        
        self.setWindowTitle("选择变量")
        self.setMinimumSize(600, 500)
        
        self._load_recent_variables()
        self.init_ui()
        
    def _load_recent_variables(self):
        if self.config_manager and hasattr(self.config_manager, 'recent_variables'):
            self.recent_variables = self.config_manager.recent_variables[:10]
    
    def _save_recent_variables(self):
        if self.config_manager:
            if not hasattr(self.config_manager, 'recent_variables'):
                self.config_manager.recent_variables = []
            self.config_manager.recent_variables = self.recent_variables[:10]
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入变量名、地址或描述进行搜索...")
        self.search_edit.textChanged.connect(self.on_search_changed)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_layout.addWidget(QLabel("变量分组:"))
        self.group_tree = QTreeWidget()
        self.group_tree.setHeaderHidden(True)
        self.group_tree.itemClicked.connect(self.on_group_clicked)
        left_layout.addWidget(self.group_tree)
        left_widget.setLayout(left_layout)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.variable_label = QLabel("全部变量")
        right_layout.addWidget(self.variable_label)
        
        self.var_tree = QTreeWidget()
        self.var_tree.setHeaderLabels(["变量名", "地址", "类型", "描述"])
        self.var_tree.setColumnWidth(0, 150)
        self.var_tree.setColumnWidth(1, 120)
        self.var_tree.setColumnWidth(2, 80)
        self.var_tree.setColumnWidth(3, 200)
        self.var_tree.itemDoubleClicked.connect(self.on_variable_double_clicked)
        self.var_tree.itemClicked.connect(self.on_variable_clicked)
        right_layout.addWidget(self.var_tree)
        
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: gray; font-style: italic;")
        right_layout.addWidget(self.info_label)
        
        right_widget.setLayout(right_layout)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([150, 450])
        layout.addWidget(splitter)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
        self.load_groups()
        self.load_variables()
        
        if self.current_value:
            self.search_edit.setText(self.current_value)
    
    def load_groups(self):
        self.group_tree.clear()
        
        recent_item = QTreeWidgetItem(self.group_tree, ["最近使用"])
        recent_item.setData(0, Qt.UserRole, "__recent__")
        recent_item.setIcon(0, QIcon.fromTheme("document-open-recent"))
        
        all_item = QTreeWidgetItem(self.group_tree, ["全部变量"])
        all_item.setData(0, Qt.UserRole, "__all__")
        all_item.setSelected(True)
        
        if self.config_manager and hasattr(self.config_manager, 'variable_groups'):
            for group_name in self.config_manager.variable_groups.keys():
                group_item = QTreeWidgetItem(self.group_tree, [group_name])
                group_item.setData(0, Qt.UserRole, group_name)
        
        self.current_group = "__all__"
    
    def load_variables(self, filter_text='', group='__all__'):
        self.var_tree.clear()
        
        if not self.data_manager or not self.data_manager.tags:
            self.info_label.setText("没有可用的变量")
            return
        
        filter_lower = filter_text.lower()
        variables = []
        
        if group == '__recent__':
            for var_name in self.recent_variables:
                if var_name in self.data_manager.tags:
                    tag = self.data_manager.tags[var_name]
                    variables.append((var_name, tag))
            self.variable_label.setText(f"最近使用 ({len(variables)})")
        elif group == '__all__':
            for var_name, tag in self.data_manager.tags.items():
                variables.append((var_name, tag))
            self.variable_label.setText(f"全部变量 ({len(variables)})")
        else:
            if self.config_manager and hasattr(self.config_manager, 'variable_groups'):
                group_vars = self.config_manager.variable_groups.get(group, [])
                for var_name in group_vars:
                    if var_name in self.data_manager.tags:
                        tag = self.data_manager.tags[var_name]
                        variables.append((var_name, tag))
            self.variable_label.setText(f"{group} ({len(variables)})")
        
        matched_count = 0
        for var_name, tag in sorted(variables, key=lambda x: x[0].lower()):
            address = getattr(tag, 'address', '')
            data_type = getattr(tag, 'data_type', '')
            if hasattr(data_type, 'value'):
                data_type = data_type.value
            description = getattr(tag, 'description', '')
            
            if filter_text:
                score = self._calculate_match_score(filter_lower, var_name.lower(), 
                                                    address.lower() if address else '', 
                                                    description.lower() if description else '')
                if score == 0:
                    continue
            else:
                score = 0
            
            item = QTreeWidgetItem([var_name, str(address), str(data_type), description])
            item.setData(0, Qt.UserRole, var_name)
            item.setData(0, Qt.UserRole + 1, score)
            
            if var_name == self.current_value:
                item.setSelected(True)
                self.var_tree.setCurrentItem(item)
            
            self.var_tree.addTopLevelItem(item)
            matched_count += 1
        
        if filter_text:
            self.var_tree.sortByColumn(0, Qt.AscendingOrder)
            self._sort_by_relevance()
        
        self.info_label.setText(f"共 {matched_count} 个匹配变量")
    
    def _calculate_match_score(self, filter_text, name, address, description):
        if not filter_text:
            return 1
        
        if filter_text == name:
            return 100
        if name.startswith(filter_text):
            return 80
        if filter_text in name:
            return 60
        if address and filter_text in address:
            return 50
        if description and filter_text in description:
            return 30
        
        filter_words = filter_text.split()
        name_words = name.split('_')
        for word in filter_words:
            for name_word in name_words:
                if name_word.startswith(word):
                    return 40
        
        return 0
    
    def _sort_by_relevance(self):
        items_data = []
        for i in range(self.var_tree.topLevelItemCount()):
            item = self.var_tree.topLevelItem(i)
            score = item.data(0, Qt.UserRole + 1)
            var_name = item.data(0, Qt.UserRole)
            items_data.append((score, i, var_name, item.text(0), item.text(1), item.text(2), item.text(3)))
        
        items_data.sort(key=lambda x: (-x[0], x[1]))
        
        self.var_tree.clear()
        for score, _, var_name, name, address, data_type, description in items_data:
            item = QTreeWidgetItem([name, address, data_type, description])
            item.setData(0, Qt.UserRole, var_name)
            item.setData(0, Qt.UserRole + 1, score)
            self.var_tree.addTopLevelItem(item)
    
    def on_search_changed(self, text):
        self.load_variables(text, self.current_group)
    
    def on_group_clicked(self, item, column):
        self.current_group = item.data(0, Qt.UserRole)
        self.load_variables(self.search_edit.text(), self.current_group)
    
    def on_variable_clicked(self, item, column):
        self.selected_variable = item.data(0, Qt.UserRole)
        tag = self.data_manager.tags.get(self.selected_variable)
        if tag:
            value = getattr(tag, 'value', 'N/A')
            self.info_label.setText(f"当前值: {value}")
    
    def on_variable_double_clicked(self, item, column):
        self.selected_variable = item.data(0, Qt.UserRole)
        self.accept()
    
    def accept(self):
        if self.selected_variable:
            if self.selected_variable in self.recent_variables:
                self.recent_variables.remove(self.selected_variable)
            self.recent_variables.insert(0, self.selected_variable)
            self._save_recent_variables()
        super().accept()
    
    def get_selected_variable(self):
        return self.selected_variable


class SmartVariableComboBox(QWidget):
    variableSelected = pyqtSignal(str)
    
    def __init__(self, parent=None, data_manager=None, config_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.config_manager = config_manager
        self._current_variable = ''
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.combo = QLineEdit()
        self.combo.setPlaceholderText("输入或选择变量...")
        self.combo.textChanged.connect(self._on_text_changed)
        self.combo.returnPressed.connect(self._on_return_pressed)
        layout.addWidget(self.combo)
        
        self.select_btn = QPushButton("...")
        self.select_btn.setFixedSize(24, 24)
        self.select_btn.clicked.connect(self._open_selector)
        layout.addWidget(self.select_btn)
        
        self.suggestion_list = None
        
        self.setLayout(layout)
    
    def _on_text_changed(self, text):
        self._current_variable = text
        self.variableSelected.emit(text)
    
    def _on_return_pressed(self):
        self._current_variable = self.combo.text()
        self.variableSelected.emit(self._current_variable)
    
    def _open_selector(self):
        dialog = VariableSelectorDialog(
            self, self.data_manager, self.config_manager, self.combo.text()
        )
        if dialog.exec_() == QDialog.Accepted:
            var_name = dialog.get_selected_variable()
            if var_name:
                self.combo.setText(var_name)
                self._current_variable = var_name
                self.variableSelected.emit(var_name)
    
    def currentText(self):
        return self.combo.text()
    
    def setCurrentText(self, text):
        self.combo.setText(text)
        self._current_variable = text
    
    def setText(self, text):
        self.combo.setText(text)
        self._current_variable = text
    
    def text(self):
        return self.combo.text()
    
    def clear(self):
        self.combo.clear()
        self._current_variable = ''
    
    def refresh_variables(self):
        pass
    
    def set_data_manager(self, data_manager):
        self.data_manager = data_manager
    
    def set_config_manager(self, config_manager):
        self.config_manager = config_manager
