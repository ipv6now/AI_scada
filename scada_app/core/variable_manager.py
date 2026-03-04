"""
变量管理对话框
允许用户管理SCADA系统的变量，支持变量分组
"""
import csv
import io
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QHeaderView, QPushButton,
                             QDialogButtonBox, QGroupBox, QMessageBox, QComboBox,
                             QLineEdit, QLabel, QFileDialog, QAbstractItemView, QSpinBox,
                             QSplitter, QListWidget, QListWidgetItem, QInputDialog,
                             QMenu, QAction, QWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from scada_app.core.data_manager import TagType, DataType
from scada_app.comm.plc_manager import PLCProtocol


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class VariableManagementDialog(QDialog):
    def __init__(self, parent=None, data_manager=None, plc_manager=None, config_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.plc_manager = plc_manager
        self.config_manager = config_manager
        self.setWindowTitle("变量管理")
        self.setGeometry(200, 200, 1200, 700)

        # 变量分组数据: {group_name: [tag_names]}
        self.variable_groups = {}
        # 当前选中的分组
        self.current_group = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

       

        # 创建分割器，左侧为分组列表，右侧为变量表
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：分组列表
        left_widget = QGroupBox("变量分组")
        left_layout = QVBoxLayout()

        # 分组列表
        self.group_list = QListWidget()
        self.group_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.group_list.customContextMenuRequested.connect(self.show_group_context_menu)
        self.group_list.itemClicked.connect(self.on_group_selected)
        left_layout.addWidget(self.group_list)

        # 分组操作按钮
        group_btn_layout = QHBoxLayout()
        self.add_group_btn = QPushButton("新建分组")
        self.add_group_btn.clicked.connect(self.add_group)
        group_btn_layout.addWidget(self.add_group_btn)

        self.rename_group_btn = QPushButton("重命名")
        self.rename_group_btn.clicked.connect(self.rename_group)
        group_btn_layout.addWidget(self.rename_group_btn)

        self.delete_group_btn = QPushButton("删除分组")
        self.delete_group_btn.clicked.connect(self.delete_group)
        group_btn_layout.addWidget(self.delete_group_btn)

        left_layout.addLayout(group_btn_layout)
        left_widget.setLayout(left_layout)
        left_widget.setMaximumWidth(250)
        splitter.addWidget(left_widget)

        # 右侧：变量表
        right_widget = QWidget()
        right_layout = QVBoxLayout()

        # 当前分组标题
        self.group_title_label = QLabel("全部变量")
        self.group_title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_layout.addWidget(self.group_title_label)

        # Variable table - editable
        self.variable_table = QTableWidget()
        self.variable_table.setColumnCount(6)
        self.variable_table.setHorizontalHeaderLabels([
            "变量名", "地址", "数据类型", "连接", "标签类型", "描述"
        ])
        header = self.variable_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        # Enable editing
        self.variable_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.variable_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.variable_table.setSelectionMode(QAbstractItemView.ExtendedSelection)  # 支持多选

        # Connect cell changed signal
        self.variable_table.cellChanged.connect(self.on_cell_changed)

        right_layout.addWidget(QLabel("已配置变量 (双击直接编辑):"))
        right_layout.addWidget(self.variable_table)

        # Poll interval setting
        poll_group = QGroupBox("轮询设置")
        poll_layout = QHBoxLayout()
        
        poll_layout.addWidget(QLabel("数据轮询间隔:"))
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setMinimum(100)
        self.poll_interval_spin.setMaximum(10000)
        self.poll_interval_spin.setSingleStep(100)
        self.poll_interval_spin.setValue(1000)
        self.poll_interval_spin.setSuffix(" 毫秒")
        self.poll_interval_spin.setToolTip("设置PLC数据轮询的时间间隔 (100-10000毫秒)")
        poll_layout.addWidget(self.poll_interval_spin)
        
        poll_layout.addStretch()
        poll_group.setLayout(poll_layout)
        right_layout.addWidget(poll_group)

        # Buttons
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("添加变量")
        self.add_btn.clicked.connect(self.add_variable)
        btn_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("删除变量")
        self.remove_btn.clicked.connect(self.remove_variable)
        btn_layout.addWidget(self.remove_btn)

        self.move_to_group_btn = QPushButton("移动到分组")
        self.move_to_group_btn.clicked.connect(self.move_to_group)
        btn_layout.addWidget(self.move_to_group_btn)

        btn_layout.addStretch()

        # CSV Import/Export buttons
        self.import_btn = QPushButton("导入CSV")
        self.import_btn.clicked.connect(self.import_csv)
        btn_layout.addWidget(self.import_btn)

        self.export_btn = QPushButton("导出CSV")
        self.export_btn.clicked.connect(self.export_csv)
        btn_layout.addWidget(self.export_btn)

        right_layout.addLayout(btn_layout)

        # OK/Cancel
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)

        right_layout.addWidget(button_box)
        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)

        splitter.setSizes([200, 1000])
        layout.addWidget(splitter)
        self.setLayout(layout)

        # Load existing variables
        self.load_groups()
        self.load_variables()
        
        # Load poll interval
        self.load_poll_interval()

    def load_poll_interval(self):
        """Load poll interval from config manager"""
        if self.config_manager and hasattr(self.config_manager, 'poll_interval'):
            self.poll_interval_spin.setValue(self.config_manager.poll_interval)
    
    def save_poll_interval(self):
        """Save poll interval to config manager"""
        if self.config_manager:
            self.config_manager.poll_interval = self.poll_interval_spin.value()

    def load_groups(self):
        """Load variable groups from config manager"""
        self.group_list.clear()
        
        # 添加"全部变量"选项
        all_item = QListWidgetItem("全部变量")
        all_item.setData(Qt.UserRole, "__all__")
        self.group_list.addItem(all_item)
        
        # 从config_manager加载分组
        if self.config_manager and hasattr(self.config_manager, 'variable_groups'):
            self.variable_groups = self.config_manager.variable_groups.copy()
        else:
            self.variable_groups = {}
        
        # 添加分组到列表
        for group_name in self.variable_groups.keys():
            item = QListWidgetItem(group_name)
            item.setData(Qt.UserRole, group_name)
            self.group_list.addItem(item)
        
        # 选中"全部变量"
        self.group_list.setCurrentRow(0)
        self.current_group = "__all__"

    def on_group_selected(self, item):
        """Handle group selection"""
        group_key = item.data(Qt.UserRole)
        self.current_group = group_key
        
        if group_key == "__all__":
            self.group_title_label.setText("全部变量")
        else:
            count = len(self.variable_groups.get(group_key, []))
            self.group_title_label.setText(f"{group_key} ({count}个变量)")
        
        self.load_variables()

    def add_group(self):
        """Add a new variable group"""
        name, ok = QInputDialog.getText(self, "新建分组", "请输入分组名称:")
        if ok and name:
            name = name.strip()
            if not name:
                QMessageBox.warning(self, "错误", "分组名称不能为空")
                return
            
            if name in self.variable_groups:
                QMessageBox.warning(self, "错误", "分组名称已存在")
                return
            
            if name == "全部变量":
                QMessageBox.warning(self, "错误", "不能使用保留名称")
                return
            
            self.variable_groups[name] = []
            
            # 添加到列表
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, name)
            self.group_list.addItem(item)
            
            # 保存到config_manager
            self.save_groups()

    def rename_group(self):
        """Rename selected group"""
        current_item = self.group_list.currentItem()
        if not current_item:
            return
        
        group_key = current_item.data(Qt.UserRole)
        if group_key == "__all__":
            QMessageBox.warning(self, "错误", "不能重命名'全部变量'")
            return
        
        new_name, ok = QInputDialog.getText(self, "重命名分组", "请输入新的分组名称:", text=group_key)
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                QMessageBox.warning(self, "错误", "分组名称不能为空")
                return
            
            if new_name in self.variable_groups and new_name != group_key:
                QMessageBox.warning(self, "错误", "分组名称已存在")
                return
            
            # 重命名
            self.variable_groups[new_name] = self.variable_groups.pop(group_key)
            current_item.setText(new_name)
            current_item.setData(Qt.UserRole, new_name)
            
            # 保存
            self.save_groups()

    def delete_group(self):
        """Delete selected group"""
        current_item = self.group_list.currentItem()
        if not current_item:
            return
        
        group_key = current_item.data(Qt.UserRole)
        if group_key == "__all__":
            QMessageBox.warning(self, "错误", "不能删除'全部变量'")
            return
        
        reply = QMessageBox.question(self, "确认删除",
                                    f"确定要删除分组 '{group_key}' 吗?\n分组内的变量不会被删除。",
                                    QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            del self.variable_groups[group_key]
            self.group_list.takeItem(self.group_list.row(current_item))
            
            # 如果当前选中的是被删除的分组，切换到"全部变量"
            if self.current_group == group_key:
                self.group_list.setCurrentRow(0)
                self.current_group = "__all__"
                self.load_variables()
            
            # 保存
            self.save_groups()

    def show_group_context_menu(self, pos):
        """Show context menu for group list"""
        item = self.group_list.itemAt(pos)
        if not item:
            return
        
        group_key = item.data(Qt.UserRole)
        if group_key == "__all__":
            return
        
        menu = QMenu(self)
        rename_action = QAction("重命名", self)
        rename_action.triggered.connect(self.rename_group)
        menu.addAction(rename_action)
        
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(self.delete_group)
        menu.addAction(delete_action)
        
        menu.exec_(self.group_list.mapToGlobal(pos))

    def move_to_group(self):
        """Move selected variables to a group"""
        # 获取所有选中的行
        selected_rows = self.variable_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "未选择", "请选择要移动的变量。")
            return
        
        # 获取所有选中行的变量名
        var_names = []
        for index in selected_rows:
            row = index.row()
            name_item = self.variable_table.item(row, 0)
            if name_item:
                var_names.append(name_item.text())
        
        if not var_names:
            return
        
        # 获取分组列表
        groups = list(self.variable_groups.keys())
        if not groups:
            reply = QMessageBox.question(self, "无分组", 
                                        "还没有创建分组，是否现在创建一个?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.add_group()
                groups = list(self.variable_groups.keys())
                if not groups:
                    return
            else:
                return
        
        # 显示分组选择对话框
        title = f"移动 {len(var_names)} 个变量到分组" if len(var_names) > 1 else "移动到分组"
        group_name, ok = QInputDialog.getItem(self, title, 
                                             "选择目标分组:", 
                                             groups + ["(无分组)"], 
                                             0, False)
        if ok:
            # 对每个变量进行处理
            for var_name in var_names:
                # 从所有分组中移除该变量
                for g in self.variable_groups:
                    if var_name in self.variable_groups[g]:
                        self.variable_groups[g].remove(var_name)
                
                # 添加到新分组（如果不是"(无分组)"）
                if group_name != "(无分组)":
                    if group_name in self.variable_groups:
                        self.variable_groups[group_name].append(var_name)
            
            # 保存
            self.save_groups()
            
            # 刷新显示
            if self.current_group != "__all__":
                self.load_variables()

    def save_groups(self):
        """Save groups to config manager"""
        if self.config_manager:
            self.config_manager.variable_groups = self.variable_groups.copy()

    def load_variables(self):
        """Load existing variables into the table"""
        # Block signals to prevent cellChanged from firing during load
        self.variable_table.blockSignals(True)

        self.variable_table.setRowCount(0)  # Clear existing rows

        if self.data_manager:
            # 获取要显示的变量
            if self.current_group == "__all__":
                # 显示所有变量
                tags_to_show = list(self.data_manager.tags.items())
            else:
                # 显示当前分组的变量
                group_vars = self.variable_groups.get(self.current_group, [])
                tags_to_show = [(name, self.data_manager.tags[name]) 
                               for name in group_vars 
                               if name in self.data_manager.tags]
            
            row = 0
            for name, tag in tags_to_show:
                self.variable_table.insertRow(row)

                # Variable Name
                name_item = QTableWidgetItem(tag.name)
                name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
                self.variable_table.setItem(row, 0, name_item)

                # Address
                address_item = QTableWidgetItem(tag.address or "")
                address_item.setFlags(address_item.flags() | Qt.ItemIsEditable)
                self.variable_table.setItem(row, 1, address_item)

                # Data Type - use NoWheelComboBox
                data_type_combo = NoWheelComboBox()
                data_type_combo.addItems([dt.value for dt in DataType])
                data_type_combo.setCurrentText(tag.data_type.value)
                data_type_combo.currentTextChanged.connect(lambda text, r=row: self.on_data_type_changed(r, text))
                self.variable_table.setCellWidget(row, 2, data_type_combo)

                # Connection - use NoWheelComboBox
                conn_combo = NoWheelComboBox()
                conn_combo.addItem("")  # Empty option for internal variables
                if self.plc_manager:
                    for conn_name in self.plc_manager.connections.keys():
                        conn_combo.addItem(conn_name)
                conn_combo.setCurrentText(tag.plc_connection or "")
                conn_combo.currentTextChanged.connect(lambda text, r=row: self.on_connection_changed(r, text))
                self.variable_table.setCellWidget(row, 3, conn_combo)

                # Tag Type - use NoWheelComboBox
                tag_type_combo = NoWheelComboBox()
                tag_type_combo.addItems([tt.value for tt in TagType])
                tag_type_combo.setCurrentText(tag.tag_type.value)
                tag_type_combo.currentTextChanged.connect(lambda text, r=row: self.on_tag_type_changed(r, text))
                self.variable_table.setCellWidget(row, 4, tag_type_combo)

                # Description
                desc_item = QTableWidgetItem(tag.description or "")
                desc_item.setFlags(desc_item.flags() | Qt.ItemIsEditable)
                self.variable_table.setItem(row, 5, desc_item)

                # Update connection combo enabled state based on tag type
                self.update_connection_state(row, tag.tag_type.value)

                row += 1

        # Re-enable signals
        self.variable_table.blockSignals(False)

    def get_row_data(self, row):
        """Get all data from a row"""
        name_item = self.variable_table.item(row, 0)
        address_item = self.variable_table.item(row, 1)
        desc_item = self.variable_table.item(row, 5)

        # Get values from comboboxes
        data_type_combo = self.variable_table.cellWidget(row, 2)
        conn_combo = self.variable_table.cellWidget(row, 3)
        tag_type_combo = self.variable_table.cellWidget(row, 4)

        var_name = name_item.text().strip() if name_item else ""
        address = address_item.text().strip() if address_item else ""
        description = desc_item.text().strip() if desc_item else ""
        data_type_str = data_type_combo.currentText() if data_type_combo else "INT"
        connection = conn_combo.currentText() if conn_combo else ""
        tag_type_str = tag_type_combo.currentText() if tag_type_combo else "PLC"

        return var_name, address, description, data_type_str, connection, tag_type_str

    def update_connection_state(self, row, tag_type_str):
        """Update connection combo enabled state based on tag type"""
        conn_combo = self.variable_table.cellWidget(row, 3)
        address_item = self.variable_table.item(row, 1)

        if not conn_combo:
            return

        if tag_type_str == "INTERNAL":
            conn_combo.setEnabled(False)
            conn_combo.setCurrentText("")
            if address_item:
                address_item.setText("")
        else:
            conn_combo.setEnabled(True)

    def on_data_type_changed(self, row, text):
        """Handle data type combo change"""
        self.save_row_to_data_manager(row)

    def on_connection_changed(self, row, text):
        """Handle connection combo change"""
        self.save_row_to_data_manager(row)

    def on_tag_type_changed(self, row, text):
        """Handle tag type combo change"""
        # Update connection combo state
        self.update_connection_state(row, text)
        # Save to data manager
        self.save_row_to_data_manager(row)

    def on_cell_changed(self, row, column):
        """Handle cell editing for name, address, description columns"""
        if column in [0, 1, 5]:  # Only handle text columns
            self.save_row_to_data_manager(row)

    def save_row_to_data_manager(self, row):
        """Save row data to data manager"""
        if not self.data_manager:
            return

        var_name, address, description, data_type_str, connection, tag_type_str = self.get_row_data(row)

        if not var_name:
            return

        # Validate tag type
        try:
            tag_type = TagType(tag_type_str)
        except ValueError:
            tag_type = TagType.PLC

        # Validate data type
        try:
            data_type = DataType(data_type_str)
        except ValueError:
            data_type = DataType.INT

        # For internal variables, clear address and connection
        if tag_type == TagType.INTERNAL:
            address = ""
            connection = ""

        # Create or update tag
        from scada_app.core.data_manager import Tag
        new_tag = Tag(
            name=var_name,
            tag_type=tag_type,
            data_type=data_type,
            address=address if address else None,
            description=description if description else "",
            plc_connection=connection if connection else ""
        )

        # Check if this is a rename operation
        old_name = None
        for old_tag_name, old_tag in list(self.data_manager.tags.items()):
            # Find if there's another row with this old name
            for r in range(self.variable_table.rowCount()):
                if r != row:
                    other_name_item = self.variable_table.item(r, 0)
                    if other_name_item and other_name_item.text().strip() == old_tag_name:
                        break
            else:
                # This old tag name is not in the table anymore, it was renamed
                if old_tag_name != var_name:
                    old_name = old_tag_name

        # Remove old tag if renamed
        if old_name and old_name in self.data_manager.tags:
            del self.data_manager.tags[old_name]
            # 更新分组中的变量名
            for group in self.variable_groups:
                if old_name in self.variable_groups[group]:
                    idx = self.variable_groups[group].index(old_name)
                    self.variable_groups[group][idx] = var_name

        # Add/update the tag
        self.data_manager.add_tag(new_tag)
        
        # 如果当前在某个分组中，确保新变量在该分组中
        if self.current_group != "__all__" and self.current_group in self.variable_groups:
            if var_name not in self.variable_groups[self.current_group]:
                self.variable_groups[self.current_group].append(var_name)

    def add_variable(self):
        """Add a new variable directly to the table"""
        row = self.variable_table.rowCount()
        self.variable_table.insertRow(row)

        # Block signals temporarily
        self.variable_table.blockSignals(True)

        # Set default values
        default_name = f"变量{len(self.data_manager.tags) + 1}"

        # Variable Name
        name_item = QTableWidgetItem(default_name)
        name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
        self.variable_table.setItem(row, 0, name_item)

        # Address
        address_item = QTableWidgetItem("")
        address_item.setFlags(address_item.flags() | Qt.ItemIsEditable)
        self.variable_table.setItem(row, 1, address_item)

        # Data Type - use NoWheelComboBox
        data_type_combo = NoWheelComboBox()
        data_type_combo.addItems([dt.value for dt in DataType])
        data_type_combo.setCurrentText("INT")
        data_type_combo.currentTextChanged.connect(lambda text, r=row: self.on_data_type_changed(r, text))
        self.variable_table.setCellWidget(row, 2, data_type_combo)

        # Connection - use NoWheelComboBox
        conn_combo = NoWheelComboBox()
        conn_combo.addItem("")  # Empty option for internal variables
        if self.plc_manager:
            for conn_name in self.plc_manager.connections.keys():
                conn_combo.addItem(conn_name)
        conn_combo.currentTextChanged.connect(lambda text, r=row: self.on_connection_changed(r, text))
        self.variable_table.setCellWidget(row, 3, conn_combo)

        # Tag Type - use NoWheelComboBox
        tag_type_combo = NoWheelComboBox()
        tag_type_combo.addItems([tt.value for tt in TagType])
        tag_type_combo.setCurrentText("PLC")
        tag_type_combo.currentTextChanged.connect(lambda text, r=row: self.on_tag_type_changed(r, text))
        self.variable_table.setCellWidget(row, 4, tag_type_combo)

        # Description
        desc_item = QTableWidgetItem("")
        desc_item.setFlags(desc_item.flags() | Qt.ItemIsEditable)
        self.variable_table.setItem(row, 5, desc_item)

        # Re-enable signals
        self.variable_table.blockSignals(False)

        # Add to data manager
        from scada_app.core.data_manager import Tag
        new_tag = Tag(
            name=default_name,
            tag_type=TagType.PLC,
            data_type=DataType.INT,
            address=None,
            description="",
            plc_connection=""
        )
        self.data_manager.add_tag(new_tag)
        
        # 如果当前在某个分组中，将新变量添加到该分组
        if self.current_group != "__all__" and self.current_group in self.variable_groups:
            self.variable_groups[self.current_group].append(default_name)
            self.save_groups()

        # Select and edit the new row
        self.variable_table.selectRow(row)
        self.variable_table.editItem(name_item)

    def remove_variable(self):
        """Remove selected variables"""
        # 获取所有选中的行
        selected_rows = self.variable_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "未选择", "请选择要删除的变量。")
            return

        # 获取所有选中行的变量名
        var_names = []
        for index in selected_rows:
            row = index.row()
            name_item = self.variable_table.item(row, 0)
            if name_item:
                var_names.append(name_item.text())
        
        if not var_names:
            return

        # Confirm deletion
        if len(var_names) == 1:
            msg = f"确定要删除变量 '{var_names[0]}' 吗?"
        else:
            msg = f"确定要删除选中的 {len(var_names)} 个变量吗?"
        
        reply = QMessageBox.question(self, "确认删除", msg,
                                    QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            for var_name in var_names:
                # Remove from data manager
                if var_name in self.data_manager.tags:
                    del self.data_manager.tags[var_name]

                # 从所有分组中移除
                for group in self.variable_groups:
                    if var_name in self.variable_groups[group]:
                        self.variable_groups[group].remove(var_name)
            
            self.save_groups()

            # Reload table
            self.load_variables()

    def export_csv(self):
        """Export variables to CSV file"""
        if not self.data_manager or not self.data_manager.tags:
            QMessageBox.information(self, "无数据", "没有可导出的变量。")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出变量到CSV", "variables.csv",
            "CSV文件 (*.csv);;所有文件 (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                # Write header
                writer.writerow(["变量名", "地址", "数据类型", "连接", "标签类型", "描述", "分组"])

                # Write data
                for name, tag in self.data_manager.tags.items():
                    # 查找变量所属的分组
                    groups = []
                    for g, vars in self.variable_groups.items():
                        if name in vars:
                            groups.append(g)
                    group_str = ";".join(groups)
                    
                    writer.writerow([
                        tag.name,
                        tag.address or "",
                        tag.data_type.value,
                        tag.plc_connection or "",
                        tag.tag_type.value,
                        tag.description or "",
                        group_str
                    ])

            QMessageBox.information(self, "导出成功",
                                  f"成功导出 {len(self.data_manager.tags)} 个变量到 {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出错误", f"导出CSV失败: {str(e)}")

    def import_csv(self):
        """Import variables from CSV file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "从CSV导入变量", "",
            "CSV文件 (*.csv);;所有文件 (*)"
        )

        if not file_path:
            return

        try:
            imported_count = 0
            skipped_count = 0

            with open(file_path, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.reader(f)

                # Skip header row
                header = next(reader, None)

                for row in reader:
                    if len(row) < 6:
                        continue

                    var_name = row[0].strip()
                    address = row[1].strip()
                    data_type_str = row[2].strip()
                    connection = row[3].strip()
                    tag_type_str = row[4].strip()
                    description = row[5].strip()
                    group_str = row[6].strip() if len(row) > 6 else ""

                    if not var_name:
                        continue

                    # Skip if variable already exists
                    if var_name in self.data_manager.tags:
                        skipped_count += 1
                        continue

                    # Validate and convert types
                    try:
                        tag_type = TagType(tag_type_str) if tag_type_str else TagType.PLC
                    except ValueError:
                        tag_type = TagType.PLC

                    try:
                        data_type = DataType(data_type_str) if data_type_str else DataType.INT
                    except ValueError:
                        data_type = DataType.INT

                    # For internal variables, clear address and connection
                    if tag_type == TagType.INTERNAL:
                        address = ""
                        connection = ""

                    # Create tag
                    from scada_app.core.data_manager import Tag
                    new_tag = Tag(
                        name=var_name,
                        tag_type=tag_type,
                        data_type=data_type,
                        address=address if address else None,
                        description=description,
                        plc_connection=connection
                    )

                    self.data_manager.add_tag(new_tag)
                    
                    # 处理分组
                    if group_str:
                        groups = group_str.split(";")
                        for g in groups:
                            g = g.strip()
                            if g:
                                if g not in self.variable_groups:
                                    self.variable_groups[g] = []
                                if var_name not in self.variable_groups[g]:
                                    self.variable_groups[g].append(var_name)
                    
                    imported_count += 1

            # Reload groups and variables
            self.save_groups()
            self.load_groups()
            self.load_variables()

            msg = f"成功导入 {imported_count} 个变量。"
            if skipped_count > 0:
                msg += f"\n{skipped_count} 个变量被跳过 (已存在)。"

            QMessageBox.information(self, "导入完成", msg)

        except Exception as e:
            QMessageBox.critical(self, "导入错误", f"导入CSV失败: {str(e)}")

    def on_accept(self):
        """Save all changes before closing"""
        # All changes are already saved to data_manager during editing
        # Save poll interval
        self.save_poll_interval()
        # Save groups
        self.save_groups()
        self.accept()


class VariableConfigDialog(QDialog):
    """Legacy dialog - kept for compatibility but no longer used"""
    def __init__(self, parent=None, variable_data=None, data_manager=None, plc_manager=None):
        super().__init__(parent)
        self.variable_data = variable_data or {}
        self.data_manager = data_manager
        self.plc_manager = plc_manager
        self.setWindowTitle("配置变量")
        self.setGeometry(300, 300, 400, 350)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Form group
        form_group = QGroupBox("变量设置")
        form_layout = QVBoxLayout()

        # Variable Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("变量名:"))
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.variable_data.get('name', ''))
        name_layout.addWidget(self.name_edit)
        form_layout.addLayout(name_layout)

        # Address (for PLC variables only)
        addr_layout = QHBoxLayout()
        addr_layout.addWidget(QLabel("地址:"))
        self.address_edit = QLineEdit()
        self.address_edit.setText(self.variable_data.get('address', ''))
        addr_layout.addWidget(self.address_edit)
        form_layout.addLayout(addr_layout)
