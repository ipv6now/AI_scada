"""
报警配置对话框 - 表格式编辑版本
支持变量选择器、下拉框选择、导入导出CSV
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QPushButton, QLineEdit, QComboBox, QLabel, 
                             QDialogButtonBox, QGroupBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QSpinBox, QCheckBox,
                             QTextEdit, QMessageBox, QDoubleSpinBox, QStyledItemDelegate,
                             QWidget, QFileDialog)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
import csv
from scada_app.core.alarm_type_manager import alarm_type_manager
import os
import sys

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from scada_app.core.data_manager import DataManager
from scada_app.hmi.variable_selector import VariableSelectorDialog


class AlarmRule:
    """报警规则类"""
    
    def __init__(self, tag_name='', alarm_type='状态变化', condition='假变真', threshold=0.0, 
                 message='', enabled=True, alarm_type_name='中', bit_offset=None, alarm_id=None):
        self.tag_name = tag_name
        self.alarm_type = alarm_type    # 状态变化, 变化率, 高, 低, 很高, 很低
        self.condition = condition    # 高, 低, 很高, 很低, 假变真, 真变假, 变化, 正, 负
        self.threshold = threshold
        self.message = message
        self.enabled = enabled
        self.alarm_type_name = alarm_type_name    # 改为报警类型名称
        self.bit_offset = bit_offset  # 位偏移 (0-15)
        self.alarm_id = alarm_id  # 报警ID，用于在报警监控中显示
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'tag_name': self.tag_name,
            'alarm_type': self.alarm_type,
            'condition': self.condition,
            'threshold': self.threshold,
            'message': self.message,
            'enabled': self.enabled,
            'alarm_type_name': self.alarm_type_name,  # 改为报警类型名称
            'bit_offset': self.bit_offset,
            'alarm_id': self.alarm_id
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建规则"""
        bit_offset = data.get('bit_offset')
        if bit_offset is not None:
            try:
                bit_offset = int(bit_offset)
            except (ValueError, TypeError):
                bit_offset = None
        
        alarm_id = data.get('alarm_id')
        if alarm_id is not None:
            try:
                alarm_id = int(alarm_id)
            except (ValueError, TypeError):
                alarm_id = None
        
        return cls(
            tag_name=data.get('tag_name', ''),
            alarm_type=data.get('alarm_type', '状态变化'),
            condition=data.get('condition', '假变真'),
            threshold=float(data.get('threshold', 0.0)),
            message=data.get('message', ''),
            enabled=data.get('enabled', True) in [True, 'True', '是', '1'],
            alarm_type_name=data.get('alarm_type_name', '中'),  # 改为报警类型名称
            bit_offset=bit_offset,
            alarm_id=alarm_id
        )


class TagNameEditor(QWidget):
    """标签名称编辑器 - 支持变量选择器"""
    valueChanged = pyqtSignal(str)
    
    def __init__(self, data_manager=None, config_manager=None, parent=None):
        super().__init__(parent)
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
    """标签名称编辑器委托 - 支持变量选择器"""
    
    def __init__(self, data_manager=None, config_manager=None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.config_manager = config_manager
    
    def createEditor(self, parent, option, index):
        """创建变量选择器编辑器"""
        editor = TagNameEditor(self.data_manager, self.config_manager, parent)
        editor.valueChanged.connect(lambda: self.commitData.emit(editor))
        return editor
    
    def setEditorData(self, editor, index):
        """设置编辑器数据"""
        value = index.model().data(index, Qt.EditRole)
        editor.setText(value if value else "")
    
    def setModelData(self, editor, model, index):
        """将编辑器数据保存到模型"""
        model.setData(index, editor.text(), Qt.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class ComboBoxDelegate(QStyledItemDelegate):
    """下拉框编辑器"""
    
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = items
    
    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.setEditable(False)  # 不可编辑，确保下拉箭头显示
        editor.addItems(self.items)
        return editor
    
    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        if value in self.items:
            editor.setCurrentText(value)
        elif self.items:
            editor.setCurrentText(self.items[0])
    
    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class BitOffsetDelegate(QStyledItemDelegate):
    """位偏移编辑器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.setEditable(True)  # 可编辑，允许输入0-15或空值
        editor.addItems(["", "0", "1", "2", "3", "4", "5", "6", "7", 
                        "8", "9", "10", "11", "12", "13", "14", "15"])
        return editor
    
    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        if value is not None and value != "":
            editor.setCurrentText(str(value))
        else:
            editor.setCurrentText("")
    
    def setModelData(self, editor, model, index):
        value = editor.currentText().strip()
        if value == "":
            model.setData(index, None, Qt.EditRole)
        else:
            try:
                bit_offset = int(value)
                if 0 <= bit_offset <= 15:
                    model.setData(index, bit_offset, Qt.EditRole)
                else:
                    model.setData(index, None, Qt.EditRole)
            except ValueError:
                model.setData(index, None, Qt.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class AlarmTypeDelegate(QStyledItemDelegate):
    """报警类型编辑器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.setEditable(False)  # 不可编辑，确保下拉箭头显示
        
        # 获取所有启用的报警类型显示名称
        alarm_type_names = alarm_type_manager.get_alarm_type_names()
        editor.addItems(alarm_type_names)
        
        return editor
    
    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        if value in alarm_type_manager.get_alarm_type_names():
            editor.setCurrentText(value)
        elif alarm_type_manager.get_alarm_type_names():
            editor.setCurrentText(alarm_type_manager.get_alarm_type_names()[0])
    
    def setModelData(self, editor, model, index):
        value = editor.currentText()
        model.setData(index, value, Qt.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class EnabledDelegate(QStyledItemDelegate):
    """启用状态编辑器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.setEditable(False)  # 不可编辑，确保下拉箭头显示
        editor.addItems(["是", "否"])
        return editor
    
    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        if value in ["是", "否"]:
            editor.setCurrentText(value)
        else:
            # 根据布尔值设置
            if value in [True, "True", "1"]:
                editor.setCurrentText("是")
            else:
                editor.setCurrentText("否")
    
    def setModelData(self, editor, model, index):
        value = editor.currentText()
        model.setData(index, value, Qt.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class AlarmConfigDialog(QDialog):
    """报警配置对话框 - 表格式编辑版本"""
    
    def __init__(self, parent=None, data_manager=None, config_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.config_manager = config_manager
        self.alarm_rules = []
        self.setWindowTitle("报警配置")
        self.setGeometry(200, 200, 1000, 600)
        
        # 设置为无模态窗口
        self.setModal(False)
        self.setWindowFlags(Qt.Window)
        
        self.init_ui()
        self.load_existing_rules()
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 标题
        title_label = QLabel("报警配置")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # 报警规则表格
        self.rule_table = QTableWidget()
        self.rule_table.setColumnCount(9)
        self.rule_table.setHorizontalHeaderLabels([
            "报警ID", "标签名称", "报警类型", "条件", "阈值", "位偏移", "消息", "报警类型", "启用"
        ])
        
        # 设置列宽和可调整性
        header = self.rule_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)  # 所有列都可手动调整
        
        # 设置初始列宽
        self.rule_table.setColumnWidth(0, 60)   # 报警ID
        self.rule_table.setColumnWidth(1, 150)  # 标签名称
        self.rule_table.setColumnWidth(2, 100)  # 类型
        self.rule_table.setColumnWidth(3, 80)   # 条件
        self.rule_table.setColumnWidth(4, 80)   # 阈值
        self.rule_table.setColumnWidth(5, 60)   # 位偏移
        self.rule_table.setColumnWidth(6, 200)  # 消息
        self.rule_table.setColumnWidth(7, 60)   # 报警类型
        self.rule_table.setColumnWidth(8, 40)   # 启用
        
        # 设置表格属性
        self.rule_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rule_table.setAlternatingRowColors(True)
        self.rule_table.setEditTriggers(QTableWidget.AllEditTriggers)  # 所有编辑触发方式
        
        # 设置自定义编辑器
        self.rule_table.setItemDelegateForColumn(1, TagNameDelegate(self.data_manager, self.config_manager, self))  # 标签名称
        self.rule_table.setItemDelegateForColumn(2, ComboBoxDelegate(["限值", "状态变化", "变化率"], self))  # 报警类型
        self.rule_table.setItemDelegateForColumn(3, ComboBoxDelegate(["高", "低", "很高", "很低", "假变真", "真变假", "变化", "正", "负"], self))  # 条件
        self.rule_table.setItemDelegateForColumn(5, BitOffsetDelegate(self))  # 位偏移
        # 第7列改为报警类型选择器
        self.rule_table.setItemDelegateForColumn(7, AlarmTypeDelegate(self))  # 报警类型
        self.rule_table.setItemDelegateForColumn(8, EnabledDelegate(self))  # 启用
        
        # 连接单元格点击事件，确保点击时立即进入编辑模式
        self.rule_table.cellClicked.connect(self.on_cell_clicked)
        
        # 连接单元格修改事件，实时检测报警ID重复
        self.rule_table.cellChanged.connect(self.on_cell_changed)
        
        layout.addWidget(self.rule_table)
        
        # 表格操作按钮
        table_btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("添加规则")
        self.add_btn.clicked.connect(self.add_rule)
        table_btn_layout.addWidget(self.add_btn)
        
        self.remove_btn = QPushButton("删除选中")
        self.remove_btn.clicked.connect(self.remove_selected_rules)
        table_btn_layout.addWidget(self.remove_btn)
        
        self.clear_btn = QPushButton("清空表格")
        self.clear_btn.clicked.connect(self.clear_rules)
        table_btn_layout.addWidget(self.clear_btn)
        
        table_btn_layout.addStretch()
        layout.addLayout(table_btn_layout)
        
        # 导入导出按钮
        import_export_layout = QHBoxLayout()
        
        self.import_btn = QPushButton("导入CSV")
        self.import_btn.clicked.connect(self.import_csv)
        import_export_layout.addWidget(self.import_btn)
        
        self.export_btn = QPushButton("导出CSV")
        self.export_btn.clicked.connect(self.export_csv)
        import_export_layout.addWidget(self.export_btn)
        
        import_export_layout.addStretch()
        layout.addLayout(import_export_layout)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("应用")
        self.apply_btn.clicked.connect(self.apply_rules)
        button_layout.addWidget(self.apply_btn)
        
        button_layout.addStretch()
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_layout.addWidget(button_box)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_existing_rules(self):
        """加载现有规则"""
        # 从配置管理器加载现有规则
        if self.config_manager and hasattr(self.config_manager, 'alarm_rules'):
            try:
                self.alarm_rules = []
                for rule_data in self.config_manager.alarm_rules:
                    rule = AlarmRule.from_dict(rule_data)
                    self.alarm_rules.append(rule)
                print(f"从配置加载了 {len(self.alarm_rules)} 条报警规则")
            except Exception as e:
                print(f"加载报警规则失败: {e}")
                self.alarm_rules = []
        else:
            # 如果没有配置管理器，使用空列表
            self.alarm_rules = []
        
        self.update_rule_table()
    
    def update_rule_table(self):
        """更新规则表格"""
        self.rule_table.setRowCount(len(self.alarm_rules))
        
        for i, rule in enumerate(self.alarm_rules):
            # 报警ID
            alarm_id_text = str(rule.alarm_id) if rule.alarm_id is not None else ""
            alarm_id_item = QTableWidgetItem(alarm_id_text)
            alarm_id_item.setTextAlignment(Qt.AlignCenter)
            self.rule_table.setItem(i, 0, alarm_id_item)
            
            # 标签名称
            self.rule_table.setItem(i, 1, QTableWidgetItem(rule.tag_name))
            
            # 报警类型
            self.rule_table.setItem(i, 2, QTableWidgetItem(rule.alarm_type))
            
            # 条件
            self.rule_table.setItem(i, 3, QTableWidgetItem(rule.condition))
            
            # 阈值
            threshold_item = QTableWidgetItem(str(rule.threshold))
            threshold_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.rule_table.setItem(i, 4, threshold_item)
            
            # 位偏移
            bit_offset_text = str(rule.bit_offset) if rule.bit_offset is not None else ""
            bit_offset_item = QTableWidgetItem(bit_offset_text)
            bit_offset_item.setTextAlignment(Qt.AlignCenter)
            if rule.bit_offset is not None:
                bit_offset_item.setBackground(Qt.cyan)
            self.rule_table.setItem(i, 5, bit_offset_item)
            
            # 消息
            self.rule_table.setItem(i, 6, QTableWidgetItem(rule.message))
            
            # 报警类型
            alarm_type_item = QTableWidgetItem(rule.alarm_type_name)
            # 使用报警类型管理器设置颜色
            try:
                from scada_app.core.alarm_type_manager import alarm_type_manager
                alarm_type = alarm_type_manager.get_alarm_type_by_display_name(rule.alarm_type_name)
                if alarm_type:
                    fg_color = alarm_type_manager.get_qcolor_from_hex(alarm_type.foreground_color)
                    bg_color = alarm_type_manager.get_qcolor_from_hex(alarm_type.background_color)
                    alarm_type_item.setForeground(fg_color)
                    alarm_type_item.setBackground(bg_color)
            except ImportError:
                pass  # 如果报警类型管理器不可用，保持默认颜色
            
            self.rule_table.setItem(i, 7, alarm_type_item)
            
            # 启用状态
            enabled_text = "是" if rule.enabled else "否"
            enabled_item = QTableWidgetItem(enabled_text)
            if not rule.enabled:
                enabled_item.setBackground(Qt.lightGray)
            self.rule_table.setItem(i, 8, enabled_item)
    
    def on_cell_clicked(self, row, column):
        """单元格点击事件处理"""
        # 对于下拉框列，立即进入编辑模式
        if column in [2, 3, 5, 7, 8]:  # 报警类型、条件、位偏移、报警类型、启用列
            self.rule_table.editItem(self.rule_table.item(row, column))

    def on_cell_changed(self, row, column):
        """处理单元格修改事件，实时检测报警ID重复"""
        if column == 0:  # 报警ID列
            # 暂时断开信号，避免递归触发
            self.rule_table.cellChanged.disconnect(self.on_cell_changed)
            
            try:
                # 获取当前单元格的报警ID
                current_item = self.rule_table.item(row, column)
                if current_item:
                    alarm_id_text = current_item.text().strip()
                    if alarm_id_text:
                        try:
                            current_alarm_id = int(alarm_id_text)
                        except ValueError:
                            # 如果不是有效的数字，恢复为自动分配的ID
                            current_alarm_id = None
                    else:
                        current_alarm_id = None
                    
                    if current_alarm_id is not None:
                        # 检查是否有其他行使用相同的报警ID
                        duplicate_rows = []
                        for other_row in range(self.rule_table.rowCount()):
                            if other_row != row:  # 排除当前行
                                other_item = self.rule_table.item(other_row, column)
                                if other_item:
                                    other_text = other_item.text().strip()
                                    if other_text:
                                        try:
                                            other_alarm_id = int(other_text)
                                            if other_alarm_id == current_alarm_id:
                                                duplicate_rows.append(other_row + 1)  # 行号从1开始
                                        except ValueError:
                                            pass
                        
                        # 如果发现重复，提示用户并自动重新分配
                        if duplicate_rows:
                            # 找到可用的报警ID
                            used_ids = set()
                            for r in range(self.rule_table.rowCount()):
                                item = self.rule_table.item(r, column)
                                if item and r != row:
                                    text = item.text().strip()
                                    if text:
                                        try:
                                            used_ids.add(int(text))
                                        except ValueError:
                                            pass
                            
                            # 找到最小的未使用的ID
                            new_id = 1
                            while new_id in used_ids:
                                new_id += 1
                            
                            # 更新当前单元格
                            current_item.setText(str(new_id))
                            
                            # 提示用户
                            QMessageBox.warning(
                                self, 
                                "报警ID重复", 
                                f"报警ID {current_alarm_id} 已被第 {', '.join(map(str, duplicate_rows))} 行使用，\n"
                                f"已自动重新分配为 {new_id}"
                            )
            finally:
                # 重新连接信号
                self.rule_table.cellChanged.connect(self.on_cell_changed)
    
    def get_next_alarm_id(self):
        """获取下一个可用的报警ID"""
        if not self.alarm_rules:
            return 1
        
        # 获取所有现有的报警ID
        existing_ids = set()
        for rule in self.alarm_rules:
            if rule.alarm_id is not None:
                existing_ids.add(rule.alarm_id)
        
        # 找到最小的未使用的ID
        next_id = 1
        while next_id in existing_ids:
            next_id += 1
        
        return next_id
    
    def add_rule(self):
        """添加新规则"""
        # 先读取表格中的现有规则，确保不会丢失已配置的规则
        self.read_rules_from_table()
        
        rule = AlarmRule()
        # 自动分配唯一的报警ID
        rule.alarm_id = self.get_next_alarm_id()
        self.alarm_rules.append(rule)
        self.update_rule_table()
        # 选中新添加的行
        self.rule_table.selectRow(len(self.alarm_rules) - 1)
    
    def remove_selected_rules(self):
        """删除选中的规则"""
        # 先读取表格中的现有规则，确保不会丢失已配置的规则
        self.read_rules_from_table()
        
        selected_rows = set()
        for item in self.rule_table.selectedItems():
            selected_rows.add(item.row())
        
        # 从后往前删除，避免索引变化
        for row in sorted(selected_rows, reverse=True):
            if 0 <= row < len(self.alarm_rules):
                self.alarm_rules.pop(row)
        
        self.update_rule_table()
    
    def clear_rules(self):
        """清空所有规则"""
        reply = QMessageBox.question(self, "确认", "确定要清空所有报警规则吗？",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # 清空规则前不需要读取表格，因为是要清空所有规则
            self.alarm_rules.clear()
            self.update_rule_table()
    
    def apply_rules(self):
        """应用规则到系统"""
        # 从表格读取数据更新规则列表
        self.read_rules_from_table()
        
        # 保存规则到配置管理器
        if self.config_manager:
            try:
                # 确保配置管理器有报警规则属性
                if not hasattr(self.config_manager, 'alarm_rules'):
                    self.config_manager.alarm_rules = []
                
                # 转换为字典格式保存
                self.config_manager.alarm_rules = [rule.to_dict() for rule in self.alarm_rules]
                print(f"保存了 {len(self.alarm_rules)} 条报警规则到配置管理器")
            except Exception as e:
                print(f"保存报警规则失败: {e}")
                QMessageBox.warning(self, "警告", f"保存报警规则失败: {e}")
        
        # 调用系统服务管理器设置报警规则
        try:
            # 尝试从主窗口获取系统服务管理器
            parent = self.parent()
            if parent and hasattr(parent, 'system_service_manager'):
                parent.system_service_manager.set_alarm_rules(self.alarm_rules)
                print(f"已设置 {len(self.alarm_rules)} 条报警规则到系统服务管理器")
            else:
                # 如果无法获取系统服务管理器，尝试从数据管理器获取
                if self.data_manager and hasattr(self.data_manager, 'system_service_manager'):
                    self.data_manager.system_service_manager.set_alarm_rules(self.alarm_rules)
                    print(f"已设置 {len(self.alarm_rules)} 条报警规则到系统服务管理器")
                else:
                    print("警告: 无法找到系统服务管理器，报警规则可能不会立即生效")
        except Exception as e:
            print(f"设置报警规则到系统服务管理器失败: {e}")
            QMessageBox.warning(self, "警告", f"设置报警规则失败: {e}")
        
        QMessageBox.information(self, "成功", f"已应用 {len(self.alarm_rules)} 条报警规则")
    
    def read_rules_from_table(self):
        """从表格读取规则数据"""
        new_rules = []
        used_alarm_ids = set()  # 用于检测重复的报警ID
        
        for row in range(self.rule_table.rowCount()):
            rule = AlarmRule()
            
            # 报警ID
            alarm_id_item = self.rule_table.item(row, 0)
            if alarm_id_item:
                alarm_id_text = alarm_id_item.text().strip()
                if alarm_id_text:
                    try:
                        rule.alarm_id = int(alarm_id_text)
                    except ValueError:
                        rule.alarm_id = None
                else:
                    rule.alarm_id = None
            
            # 检查报警ID是否重复，如果重复则重新分配
            if rule.alarm_id is not None and rule.alarm_id in used_alarm_ids:
                # 找到下一个可用的ID
                next_id = 1
                while next_id in used_alarm_ids:
                    next_id += 1
                rule.alarm_id = next_id
            
            # 如果没有报警ID，自动分配一个
            if rule.alarm_id is None:
                next_id = 1
                while next_id in used_alarm_ids:
                    next_id += 1
                rule.alarm_id = next_id
            
            # 记录已使用的报警ID
            used_alarm_ids.add(rule.alarm_id)
            
            # 标签名称
            tag_item = self.rule_table.item(row, 1)
            if tag_item:
                rule.tag_name = tag_item.text()
            
            # 报警类型
            type_item = self.rule_table.item(row, 2)
            if type_item:
                rule.alarm_type = type_item.text()
            
            # 条件
            condition_item = self.rule_table.item(row, 3)
            if condition_item:
                rule.condition = condition_item.text()
            
            # 阈值
            threshold_item = self.rule_table.item(row, 4)
            if threshold_item:
                try:
                    rule.threshold = float(threshold_item.text())
                except ValueError:
                    rule.threshold = 0.0
            
            # 位偏移
            bit_offset_item = self.rule_table.item(row, 5)
            if bit_offset_item:
                bit_offset_text = bit_offset_item.text().strip()
                if bit_offset_text == "":
                    rule.bit_offset = None
                else:
                    try:
                        rule.bit_offset = int(bit_offset_text)
                        if not (0 <= rule.bit_offset <= 15):
                            rule.bit_offset = None
                    except ValueError:
                        rule.bit_offset = None
            
            # 消息
            message_item = self.rule_table.item(row, 6)
            if message_item:
                rule.message = message_item.text()
            
            # 报警类型
            alarm_type_item = self.rule_table.item(row, 7)
            if alarm_type_item:
                rule.alarm_type_name = alarm_type_item.text()
            
            # 启用状态
            enabled_item = self.rule_table.item(row, 8)
            if enabled_item:
                rule.enabled = enabled_item.text() == "是"
            
            new_rules.append(rule)
        
        self.alarm_rules = new_rules
    
    def import_csv(self):
        """从CSV文件导入规则"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择CSV文件", "", "CSV文件 (*.csv)")
        
        if file_path:
            try:
                # 使用GBK编码读取，与导出保持一致
                with open(file_path, 'r', encoding='gbk') as file:
                    reader = csv.DictReader(file)
                    imported_rules = []
                    
                    # 中文表头到英文字段名的映射
                    header_mapping = {
                        '报警ID': 'alarm_id',
                        '标签名称': 'tag_name',
                        '报警类型': 'alarm_type',
                        '条件': 'condition',
                        '阈值': 'threshold',
                        '位偏移': 'bit_offset',
                        '消息': 'message',
                        '报警类型': 'alarm_type_name',
                        '启用': 'enabled'
                    }
                    
                    # 获取现有报警ID集合，用于检测重复
                    existing_alarm_ids = set()
                    for rule in self.alarm_rules:
                        if rule.alarm_id is not None:
                            existing_alarm_ids.add(rule.alarm_id)
                    
                    for row in reader:
                        # 将中文表头转换为英文字段名
                        converted_row = {}
                        for chinese_key, value in row.items():
                            english_key = header_mapping.get(chinese_key, chinese_key)
                            converted_row[english_key] = value
                        
                        rule = AlarmRule.from_dict(converted_row)
                        
                        # 检查报警ID是否重复，如果重复则重新分配
                        if rule.alarm_id is not None and rule.alarm_id in existing_alarm_ids:
                            # 找到下一个可用的ID
                            next_id = 1
                            while next_id in existing_alarm_ids:
                                next_id += 1
                            rule.alarm_id = next_id
                        
                        # 如果没有报警ID，自动分配一个
                        if rule.alarm_id is None:
                            next_id = 1
                            while next_id in existing_alarm_ids:
                                next_id += 1
                            rule.alarm_id = next_id
                        
                        # 记录已使用的报警ID
                        existing_alarm_ids.add(rule.alarm_id)
                        imported_rules.append(rule)
                    
                    if imported_rules:
                        self.alarm_rules.extend(imported_rules)
                        self.update_rule_table()
                        QMessageBox.information(self, "成功", f"从 {file_path} 导入了 {len(imported_rules)} 条规则")
                    else:
                        QMessageBox.warning(self, "警告", "CSV文件中没有找到有效的规则数据")
                        
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入CSV文件失败：{str(e)}")
    
    def export_csv(self):
        """导出规则到CSV文件"""
        if not self.alarm_rules:
            QMessageBox.warning(self, "警告", "没有规则可以导出")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存CSV文件", "alarm_rules.csv", "CSV文件 (*.csv)")
        
        if file_path:
            try:
                # 使用GBK编码，确保Excel中文显示正常
                with open(file_path, 'w', encoding='gbk', newline='') as file:
                    # 确保数据是最新的
                    self.read_rules_from_table()
                    
                    # 使用中文表头，与表格列对应
                    fieldnames = ['alarm_id', 'tag_name', 'alarm_type', 'condition', 'threshold', 
                                'bit_offset', 'message', 'alarm_type_name', 'enabled']
                    
                    # 创建中文表头映射
                    header_mapping = {
                        'alarm_id': '报警ID',
                        'tag_name': '标签名称',
                        'alarm_type': '报警类型',
                        'condition': '条件',
                        'threshold': '阈值',
                        'bit_offset': '位偏移',
                        'message': '消息',
                        'alarm_type_name': '报警类型',
                        'enabled': '启用'
                    }
                    
                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    
                    # 写入中文表头
                    writer.writerow(header_mapping)
                    
                    # 写入数据
                    for rule in self.alarm_rules:
                        writer.writerow(rule.to_dict())
                
                QMessageBox.information(self, "成功", f"已导出 {len(self.alarm_rules)} 条规则到 {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出CSV文件失败：{str(e)}")
    
    def get_alarm_rules(self):
        """获取报警规则列表"""
        self.read_rules_from_table()
        return self.alarm_rules
    
    def accept(self):
        """确认对话框"""
        self.read_rules_from_table()
        super().accept()


if __name__ == "__main__":
    # 测试代码
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # 创建测试用的数据管理器
    class MockDataManager:
        def __init__(self):
            self.tags = {
                "温度传感器1": None,
                "压力传感器1": None,
                "液位传感器1": None,
                "电机状态1": None
            }
    
    dialog = AlarmConfigDialog(data_manager=MockDataManager())
    dialog.show()
    
    sys.exit(app.exec_())