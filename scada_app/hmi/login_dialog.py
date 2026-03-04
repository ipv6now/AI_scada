"""
Login Dialog for SCADA System
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon
from scada_app.core.user_manager import UserManager, UserRole


class LoginDialog(QDialog):
    """Login dialog for user authentication"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统登录 - SCADA监控系统")
        self.setGeometry(400, 300, 400, 250)
        self.setFixedSize(400, 250)
        self.setWindowModality(Qt.ApplicationModal)
        
        self.user_manager = UserManager()
        self.init_ui()
    
    def init_ui(self):
        """Initialize the login dialog UI"""
        main_layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("SCADA监控系统登录")
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Login form group
        login_group = QGroupBox("用户登录")
        login_layout = QVBoxLayout()
        
        # Username field
        username_layout = QHBoxLayout()
        username_label = QLabel("用户名:")
        username_label.setMinimumWidth(80)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("请输入用户名")
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username_edit)
        login_layout.addLayout(username_layout)
        
        # Password field
        password_layout = QHBoxLayout()
        password_label = QLabel("密码:")
        password_label.setMinimumWidth(80)
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("请输入密码")
        self.password_edit.setEchoMode(QLineEdit.Password)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_edit)
        login_layout.addLayout(password_layout)
        
        # Default credentials hint
        hint_label = QLabel("默认账号: admin / admin123 或 operator / operator123")
        hint_label.setAlignment(Qt.AlignCenter)
        hint_label.setStyleSheet("color: #666; font-size: 10px;")
        login_layout.addWidget(hint_label)
        
        login_group.setLayout(login_layout)
        main_layout.addWidget(login_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.login_button = QPushButton("登录")
        self.login_button.setFixedHeight(35)
        self.login_button.clicked.connect(self.on_login)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFixedHeight(35)
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.login_button)
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addStretch()
        
        main_layout.addLayout(buttons_layout)
        
        # Set focus to username field
        self.username_edit.setFocus()
        
        # Connect Enter key to login
        self.username_edit.returnPressed.connect(self.on_login)
        self.password_edit.returnPressed.connect(self.on_login)
    
    def on_login(self):
        """Handle login button click"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        
        if not username:
            QMessageBox.warning(self, "登录失败", "请输入用户名")
            self.username_edit.setFocus()
            return
        
        if not password:
            QMessageBox.warning(self, "登录失败", "请输入密码")
            self.password_edit.setFocus()
            return
        
        # Authenticate user
        user = self.user_manager.authenticate_user(username, password)
        
        if user:
            QMessageBox.information(self, "登录成功", f"欢迎回来，{username}！")
            self.accept()
        else:
            QMessageBox.warning(self, "登录失败", "用户名或密码错误")
            self.password_edit.clear()
            self.password_edit.setFocus()
    
    def get_user_manager(self):
        """Get the user manager instance"""
        return self.user_manager
