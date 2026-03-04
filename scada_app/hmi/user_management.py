"""
User Management Dialog for SCADA System
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox, 
    QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from scada_app.core.user_manager import UserManager, UserRole


class UserManagementDialog(QDialog):
    """User management dialog for administrators"""
    def __init__(self, user_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("用户管理 - SCADA监控系统")
        self.setGeometry(300, 200, 600, 400)
        self.user_manager = user_manager
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user management UI"""
        main_layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("用户管理")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # User list table
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(2)
        self.user_table.setHorizontalHeaderLabels(["用户名", "角色"])
        self.user_table.horizontalHeader().setStretchLastSection(True)
        main_layout.addWidget(self.user_table)
        
        # New user form
        new_user_group = QGroupBox("添加新用户")
        new_user_layout = QVBoxLayout()
        
        # Username field
        username_layout = QHBoxLayout()
        username_label = QLabel("用户名:")
        username_label.setMinimumWidth(80)
        self.new_username_edit = QLineEdit()
        self.new_username_edit.setPlaceholderText("请输入用户名")
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.new_username_edit)
        new_user_layout.addLayout(username_layout)
        
        # Password field
        password_layout = QHBoxLayout()
        password_label = QLabel("密码:")
        password_label.setMinimumWidth(80)
        self.new_password_edit = QLineEdit()
        self.new_password_edit.setPlaceholderText("请输入密码")
        self.new_password_edit.setEchoMode(QLineEdit.Password)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.new_password_edit)
        new_user_layout.addLayout(password_layout)
        
        # Role selection
        role_layout = QHBoxLayout()
        role_label = QLabel("角色:")
        role_label.setMinimumWidth(80)
        self.role_combo = QComboBox()
        for role in UserRole:
            self.role_combo.addItem(role.value, role)
        role_layout.addWidget(role_label)
        role_layout.addWidget(self.role_combo)
        new_user_layout.addLayout(role_layout)
        
        new_user_group.setLayout(new_user_layout)
        main_layout.addWidget(new_user_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.add_user_button = QPushButton("添加用户")
        self.add_user_button.setFixedHeight(35)
        self.add_user_button.clicked.connect(self.add_user)
        
        self.remove_user_button = QPushButton("删除用户")
        self.remove_user_button.setFixedHeight(35)
        self.remove_user_button.clicked.connect(self.remove_user)
        
        self.refresh_button = QPushButton("刷新列表")
        self.refresh_button.setFixedHeight(35)
        self.refresh_button.clicked.connect(self.load_users)
        
        self.close_button = QPushButton("关闭")
        self.close_button.setFixedHeight(35)
        self.close_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.add_user_button)
        buttons_layout.addWidget(self.remove_user_button)
        buttons_layout.addWidget(self.refresh_button)
        buttons_layout.addWidget(self.close_button)
        
        main_layout.addLayout(buttons_layout)
        
        # Load users initially
        self.load_users()
    
    def load_users(self):
        """Load users into the table"""
        users = self.user_manager.list_users()
        self.user_table.setRowCount(len(users))
        
        for row, user in enumerate(users):
            username_item = QTableWidgetItem(user["username"])
            role_item = QTableWidgetItem(user["role"])
            
            username_item.setFlags(username_item.flags() & ~Qt.ItemIsEditable)
            role_item.setFlags(role_item.flags() & ~Qt.ItemIsEditable)
            
            self.user_table.setItem(row, 0, username_item)
            self.user_table.setItem(row, 1, role_item)
    
    def add_user(self):
        """Add a new user"""
        username = self.new_username_edit.text().strip()
        password = self.new_password_edit.text()
        role = self.role_combo.currentData()
        
        if not username:
            QMessageBox.warning(self, "添加失败", "请输入用户名")
            self.new_username_edit.setFocus()
            return
        
        if not password:
            QMessageBox.warning(self, "添加失败", "请输入密码")
            self.new_password_edit.setFocus()
            return
        
        if self.user_manager.add_user(username, password, role):
            QMessageBox.information(self, "添加成功", f"用户 {username} 添加成功")
            self.new_username_edit.clear()
            self.new_password_edit.clear()
            self.load_users()
        else:
            QMessageBox.warning(self, "添加失败", "添加用户失败，请检查用户名是否已存在")
    
    def remove_user(self):
        """Remove selected user"""
        selected_rows = self.user_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "删除失败", "请选择要删除的用户")
            return
        
        row = selected_rows[0].row()
        username = self.user_table.item(row, 0).text()
        
        # Prevent deleting the current user
        current_user = self.user_manager.get_current_user()
        if current_user and username == current_user.username:
            QMessageBox.warning(self, "删除失败", "不能删除当前登录的用户")
            return
        
        # Prevent deleting the last admin
        if username == "admin":
            QMessageBox.warning(self, "删除失败", "不能删除默认管理员账户")
            return
        
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除用户 {username} 吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.user_manager.remove_user(username):
                QMessageBox.information(self, "删除成功", f"用户 {username} 删除成功")
                self.load_users()
            else:
                QMessageBox.warning(self, "删除失败", "删除用户失败")
