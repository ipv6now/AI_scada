"""
报警类型配置对话框 - 配置预定义的报警类型及其颜色
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, QLabel, 
                             QMessageBox, QColorDialog, QLineEdit, QTextEdit, 
                             QCheckBox, QGroupBox, QFormLayout, QComboBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from scada_app.core.alarm_type_manager import alarm_type_manager, AlarmType


class AlarmTypeConfigDialog(QDialog):
    """报警类型配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("报警类型配置")
        self.setGeometry(300, 200, 800, 600)
        
        self.alarm_type_manager = alarm_type_manager
        self.init_ui()
        self.load_alarm_types()
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 说明文字
        description_label = QLabel("配置预定义的报警类型，每个类型可以设置不同的前景色和背景色。\n报警类型配置将自动保存到项目文件中。")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        
        # 报警类型表格
        self.create_alarm_type_table(layout)
        
        # 编辑区域
        self.create_edit_area(layout)
        
        # 按钮区域
        self.create_button_area(layout)
        
        self.setLayout(layout)
    
    def create_alarm_type_table(self, layout):
        """创建报警类型表格"""
        group_box = QGroupBox("报警类型列表")
        group_layout = QVBoxLayout()
        
        self.alarm_type_table = QTableWidget()
        self.alarm_type_table.setColumnCount(6)
        self.alarm_type_table.setHorizontalHeaderLabels([
            "名称", "显示名称", "前景色", "背景色", "描述", "启用"
        ])
        
        # 设置列宽
        header = self.alarm_type_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 名称
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 显示名称
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 前景色
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 背景色
        header.setSectionResizeMode(4, QHeaderView.Stretch)          # 描述
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 启用
        
        self.alarm_type_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.alarm_type_table.itemSelectionChanged.connect(self.on_selection_changed)
        
        group_layout.addWidget(self.alarm_type_table)
        group_box.setLayout(group_layout)
        layout.addWidget(group_box)
    
    def create_edit_area(self, layout):
        """创建编辑区域"""
        group_box = QGroupBox("编辑报警类型")
        form_layout = QFormLayout()
        
        # 名称输入
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入唯一标识名称")
        form_layout.addRow("名称:", self.name_edit)
        
        # 显示名称输入
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText("输入显示名称")
        form_layout.addRow("显示名称:", self.display_name_edit)
        
        # 颜色选择
        color_layout = QHBoxLayout()
        
        self.foreground_color_btn = QPushButton("选择前景色")
        self.foreground_color_btn.clicked.connect(self.select_foreground_color)
        color_layout.addWidget(self.foreground_color_btn)
        
        self.background_color_btn = QPushButton("选择背景色")
        self.background_color_btn.clicked.connect(self.select_background_color)
        color_layout.addWidget(self.background_color_btn)
        
        self.color_preview = QLabel()
        self.color_preview.setMinimumSize(50, 30)
        self.color_preview.setStyleSheet("background-color: white; border: 1px solid black;")
        color_layout.addWidget(self.color_preview)
        
        form_layout.addRow("颜色:", color_layout)
        
        # 描述输入
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        self.description_edit.setPlaceholderText("输入报警类型描述")
        form_layout.addRow("描述:", self.description_edit)
        
        # 启用复选框
        self.enabled_checkbox = QCheckBox("启用此报警类型")
        self.enabled_checkbox.setChecked(True)
        form_layout.addRow("启用:", self.enabled_checkbox)
        
        group_box.setLayout(form_layout)
        layout.addWidget(group_box)
    
    def create_button_area(self, layout):
        """创建按钮区域"""
        button_layout = QHBoxLayout()
        
        # 添加按钮
        self.add_btn = QPushButton("添加")
        self.add_btn.clicked.connect(self.add_alarm_type)
        button_layout.addWidget(self.add_btn)
        
        # 更新按钮
        self.update_btn = QPushButton("更新")
        self.update_btn.clicked.connect(self.update_alarm_type)
        button_layout.addWidget(self.update_btn)
        
        # 删除按钮
        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self.delete_alarm_type)
        button_layout.addWidget(self.delete_btn)
        
        button_layout.addStretch()
        
        # 关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def load_alarm_types(self):
        """加载报警类型到表格"""
        self.alarm_type_table.setRowCount(0)
        
        for i, alarm_type in enumerate(self.alarm_type_manager.get_all_alarm_types()):
            self.alarm_type_table.insertRow(i)
            
            # 名称
            name_item = QTableWidgetItem(alarm_type.name)
            self.alarm_type_table.setItem(i, 0, name_item)
            
            # 显示名称
            display_name_item = QTableWidgetItem(alarm_type.display_name)
            self.alarm_type_table.setItem(i, 1, display_name_item)
            
            # 前景色
            fg_color_item = QTableWidgetItem(alarm_type.foreground_color)
            fg_color_item.setBackground(self.alarm_type_manager.get_qcolor_from_hex(alarm_type.foreground_color))
            self.alarm_type_table.setItem(i, 2, fg_color_item)
            
            # 背景色
            bg_color_item = QTableWidgetItem(alarm_type.background_color)
            bg_color_item.setBackground(self.alarm_type_manager.get_qcolor_from_hex(alarm_type.background_color))
            self.alarm_type_table.setItem(i, 3, bg_color_item)
            
            # 描述
            desc_item = QTableWidgetItem(alarm_type.description)
            self.alarm_type_table.setItem(i, 4, desc_item)
            
            # 启用
            enabled_item = QTableWidgetItem("是" if alarm_type.enabled else "否")
            self.alarm_type_table.setItem(i, 5, enabled_item)
    
    def on_selection_changed(self):
        """处理表格选择变化"""
        selected_rows = self.alarm_type_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            self.load_selected_alarm_type(row)
    
    def load_selected_alarm_type(self, row):
        """加载选中的报警类型到编辑区域"""
        name = self.alarm_type_table.item(row, 0).text()
        alarm_type = self.alarm_type_manager.get_alarm_type(name)
        
        if alarm_type:
            self.name_edit.setText(alarm_type.name)
            self.display_name_edit.setText(alarm_type.display_name)
            self.description_edit.setText(alarm_type.description)
            self.enabled_checkbox.setChecked(alarm_type.enabled)
            
            # 更新颜色预览
            self.update_color_preview(alarm_type.foreground_color, alarm_type.background_color)
    
    def select_foreground_color(self):
        """选择前景色"""
        color = QColorDialog.getColor()
        if color.isValid():
            self.current_foreground_color = color.name()
            self.update_color_preview(self.current_foreground_color, self.current_background_color)
    
    def select_background_color(self):
        """选择背景色"""
        color = QColorDialog.getColor()
        if color.isValid():
            self.current_background_color = color.name()
            self.update_color_preview(self.current_foreground_color, self.current_background_color)
    
    def update_color_preview(self, fg_color, bg_color):
        """更新颜色预览"""
        self.current_foreground_color = fg_color
        self.current_background_color = bg_color
        
        style = f"color: {fg_color}; background-color: {bg_color}; border: 1px solid black; padding: 5px;"
        self.color_preview.setStyleSheet(style)
        self.color_preview.setText("预览文本")
    
    def add_alarm_type(self):
        """添加新的报警类型"""
        name = self.name_edit.text().strip()
        display_name = self.display_name_edit.text().strip()
        
        if not name or not display_name:
            QMessageBox.warning(self, "错误", "名称和显示名称不能为空")
            return
        
        if name in self.alarm_type_manager.alarm_types:
            QMessageBox.warning(self, "错误", f"报警类型 '{name}' 已存在")
            return
        
        alarm_type = AlarmType(
            name=name,
            display_name=display_name,
            foreground_color=self.current_foreground_color if hasattr(self, 'current_foreground_color') else '#000000',
            background_color=self.current_background_color if hasattr(self, 'current_background_color') else '#FFFFFF',
            description=self.description_edit.toPlainText().strip(),
            enabled=self.enabled_checkbox.isChecked()
        )
        
        self.alarm_type_manager.add_alarm_type(alarm_type)
        self.load_alarm_types()
        
        QMessageBox.information(self, "成功", f"已添加报警类型: {display_name}")
    
    def update_alarm_type(self):
        """更新选中的报警类型"""
        selected_rows = self.alarm_type_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "错误", "请先选择一个报警类型")
            return
        
        row = selected_rows[0].row()
        old_name = self.alarm_type_table.item(row, 0).text()
        
        name = self.name_edit.text().strip()
        display_name = self.display_name_edit.text().strip()
        
        if not name or not display_name:
            QMessageBox.warning(self, "错误", "名称和显示名称不能为空")
            return
        
        alarm_type = AlarmType(
            name=name,
            display_name=display_name,
            foreground_color=self.current_foreground_color if hasattr(self, 'current_foreground_color') else '#000000',
            background_color=self.current_background_color if hasattr(self, 'current_background_color') else '#FFFFFF',
            description=self.description_edit.toPlainText().strip(),
            enabled=self.enabled_checkbox.isChecked()
        )
        
        self.alarm_type_manager.update_alarm_type(old_name, alarm_type)
        self.load_alarm_types()
        
        QMessageBox.information(self, "成功", f"已更新报警类型: {display_name}")
    
    def delete_alarm_type(self):
        """删除选中的报警类型"""
        selected_rows = self.alarm_type_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "错误", "请先选择一个报警类型")
            return
        
        row = selected_rows[0].row()
        name = self.alarm_type_table.item(row, 0).text()
        display_name = self.alarm_type_table.item(row, 1).text()
        
        # 检查是否为默认类型
        if name in ["critical", "high", "medium", "low"]:
            QMessageBox.warning(self, "错误", "默认报警类型不能删除")
            return
        
        reply = QMessageBox.question(self, "确认删除", 
                                    f"确定要删除报警类型 '{display_name}' 吗？",
                                    QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.alarm_type_manager.remove_alarm_type(name)
            self.load_alarm_types()
            self.clear_edit_fields()
            QMessageBox.information(self, "成功", f"已删除报警类型: {display_name}")
    
    def clear_edit_fields(self):
        """清空编辑字段"""
        self.name_edit.clear()
        self.display_name_edit.clear()
        self.description_edit.clear()
        self.enabled_checkbox.setChecked(True)
        self.update_color_preview("#000000", "#FFFFFF")


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dialog = AlarmTypeConfigDialog()
    dialog.show()
    sys.exit(app.exec_())