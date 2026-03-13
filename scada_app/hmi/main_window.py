"""
Main SCADA Application Window
"""
import sys
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QMenuBar, QStatusBar,
                             QAction, QToolBar, QLabel, QDialog, QMessageBox,
                             QTextEdit, QPushButton, QSplitter)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QFont

from scada_app.hmi.hmi_designer import HMIDesigner
from scada_app.hmi.hmi_viewer import HMIViewer
from scada_app.comm.plc_manager import PLCManager
from scada_app.core.data_manager import DataManager
from scada_app.hmi.data_monitor import DataMonitorWidget, TagMonitor
from scada_app.core.config_manager import ConfigurationManager
from scada_app.core.data_poller import DataPoller
from scada_app.core.system_service_manager import SystemServiceManager
from scada_app.core.project_manager import ProjectManager
from scada_app.core.user_manager import UserManager, UserRole
from scada_app.hmi.login_dialog import LoginDialog
from scada_app.hmi.user_management import UserManagementDialog
from scada_app.hmi.system_monitor import SystemMonitorDialog
from scada_app.hmi.alarm_viewer import AlarmViewerDialog
from scada_app.core.logger import logger
from scada_app.core.system_monitor import system_monitor

# Web server import
try:
    from scada_app.web.web_server import WebServer
    WEB_SERVER_AVAILABLE = True
except ImportError:
    WEB_SERVER_AVAILABLE = False
    logger.warning("Web server module not available")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SCADA System - Industrial Automation Platform")
        self.setGeometry(100, 100, 1200, 800)
        
        # Track unsaved changes
        self._has_unsaved_changes = False
        
        # Initialize user manager without login dialog for debugging
        self.user_manager = UserManager()
        # Create a default admin user for debugging
        self.user_manager.create_default_user()
        
        # Initialize core components
        self.plc_manager = PLCManager()
        self.data_manager = DataManager()
        self.plc_manager.set_data_manager(self.data_manager)  # Set data manager for read-after-write
        self.config_manager = ConfigurationManager(self.data_manager, self.plc_manager)
        self.data_poller = DataPoller(self.data_manager, self.plc_manager)
        self.system_service_manager = SystemServiceManager(self.data_manager, self.plc_manager, self.config_manager)
        self.project_manager = ProjectManager(self.data_manager, self.plc_manager, self.config_manager, self.system_service_manager)
        self.hmi_designer = HMIDesigner(self.data_manager, self)
        self.hmi_designer.config_manager = self.config_manager
        self.project_manager.set_hmi_designer(self.hmi_designer)  # Set HMI designer reference
        self.tag_monitor = TagMonitor(self.data_manager, self.plc_manager)
        
        # Initialize web server
        self.web_server = None
        self.web_server_thread = None
        
        # Start system monitoring
        system_monitor.start_monitoring()
        logger.info("SCADA system started")
        
        # Set up the UI first
        self.init_ui()
        
        # Start application stats update timer
        self.start_app_stats_timer()
        
        # Auto-load recent project on startup (after UI is initialized)
        self.auto_load_recent_project()
        
    def start_app_stats_timer(self):
        """Start timer to update application statistics"""
        from PyQt5.QtCore import QTimer
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.update_application_stats)
        self.stats_timer.start(1000)  # Update every second
        
    def update_application_stats(self):
        """Update application statistics to system monitor"""
        try:
            # Get PLC connection count
            plc_connections = len(self.plc_manager.active_connections)
            
            # Get active tags count
            active_tags = len(self.data_manager.tags)
            
            # Get polling rate (if available)
            polling_rate = 0.0
            if hasattr(self, 'data_poller') and self.data_poller:
                polling_rate = getattr(self.data_poller, 'current_polling_rate', 0.0)
            
            # Update system monitor with application stats
            system_monitor.update_application_stats(
                plc_connections=plc_connections,
                active_tags=active_tags,
                polling_rate=polling_rate
            )
        except Exception as e:
            logger.error(f"Error updating application stats: {e}")
    
    def closeEvent(self, event):
        """Handle window close event - prompt to save if there are unsaved changes"""
        if self._has_unsaved_changes or self._check_for_changes():
            reply = QMessageBox.question(
                self, '保存更改',
                '项目有未保存的更改，是否保存？',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                # Try to save, if successful close, otherwise stay open
                saved = self._do_save()
                if saved:
                    event.accept()
                else:
                    # Save was cancelled or failed, don't close
                    event.ignore()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
    
    def _do_save(self):
        """Perform save operation, returns True if saved successfully or user chose not to save"""
        # Check if we have a project file (from project_manager or config_manager)
        project_file = None
        if hasattr(self, 'project_manager') and self.project_manager and self.project_manager.project_file:
            project_file = self.project_manager.project_file
        elif self.config_manager.config_file:
            project_file = self.config_manager.config_file
        
        if project_file:
            # Has existing file, save directly
            if self.project_manager.save_project(project_file):
                self.status_bar.showMessage(f"项目已保存: {project_file}", 2000)
                self.clear_modified()
                return True
            else:
                QMessageBox.critical(self, "错误", "保存项目失败")
                return False
        else:
            # No existing file, show save as dialog
            from PyQt5.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(
                self, '保存项目', 'project.hmi', 'HMI项目文件 (*.hmi);;JSON文件 (*.json);;所有文件 (*)'
            )
            
            if file_path:
                # User selected a file
                if self.project_manager.save_project(file_path):
                    self.status_bar.showMessage(f"项目已保存: {file_path}", 2000)
                    self.clear_modified()
                    return True
                else:
                    QMessageBox.critical(self, "错误", "保存项目失败")
                    return False
            else:
                # User cancelled the save dialog
                return False
    
    def _check_for_changes(self):
        """Check if there are any unsaved changes"""
        # Check if project has been modified
        if hasattr(self, 'project_manager') and self.project_manager:
            if hasattr(self.project_manager, 'project_file') and self.project_manager.project_file:
                return True
        
        # Check if there are any tags defined
        if hasattr(self, 'data_manager') and self.data_manager:
            if len(self.data_manager.tags) > 0:
                return True
        
        # Check if there are PLC connections
        if hasattr(self, 'plc_manager') and self.plc_manager:
            if len(self.plc_manager.connections) > 0:
                return True
        
        return False
    
    def mark_modified(self):
        """Mark the project as modified"""
        self._has_unsaved_changes = True
        # Update window title to show modification
        title = self.windowTitle()
        if not title.startswith('*'):
            self.setWindowTitle('* ' + title)
    
    def clear_modified(self):
        """Clear the modified flag"""
        self._has_unsaved_changes = False
        # Remove modification indicator from title
        title = self.windowTitle()
        if title.startswith('* '):
            self.setWindowTitle(title[2:])
        
    def init_ui(self):
        """Initialize the user interface"""
        self.create_menu_bar()
        self.create_tool_bar()
        self.create_central_widget()
        self.create_status_bar()
        
    def create_menu_bar(self):
        """Create the menu bar with user permission controls"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('文件')
        
        new_action = QAction('新建项目', self)
        new_action.setShortcut('Ctrl+N')
        new_action.triggered.connect(self.new_project)
        file_menu.addAction(new_action)
        
        open_action = QAction('打开项目', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_project)
        file_menu.addAction(open_action)
        
        save_action = QAction('保存项目', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)
        
        save_as_action = QAction('项目另存为...', self)
        save_as_action.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu for HMI Designer
        edit_menu = menubar.addMenu('编辑')
        
        # Cut action
        cut_action = QAction('剪切', self)
        cut_action.setShortcut('Ctrl+X')
        cut_action.triggered.connect(lambda: self.hmi_designer.cut_selected_object())
        edit_menu.addAction(cut_action)
        
        # Copy action
        copy_action = QAction('复制', self)
        copy_action.setShortcut('Ctrl+C')
        copy_action.triggered.connect(lambda: self.hmi_designer.copy_selected_object())
        edit_menu.addAction(copy_action)
        
        # Paste action
        paste_action = QAction('粘贴', self)
        paste_action.setShortcut('Ctrl+V')
        paste_action.triggered.connect(lambda: self.hmi_designer.paste_object())
        edit_menu.addAction(paste_action)
        
        edit_menu.addSeparator()
        
        # Duplicate action
        duplicate_action = QAction('复制对象', self)
        duplicate_action.setShortcut('Ctrl+D')
        duplicate_action.triggered.connect(lambda: self.hmi_designer.duplicate_selected_object())
        edit_menu.addAction(duplicate_action)
        
        # Delete action
        delete_action = QAction('删除', self)
        delete_action.setShortcut('Delete')
        delete_action.triggered.connect(lambda: self.hmi_designer.delete_selected_object())
        edit_menu.addAction(delete_action)
        
        edit_menu.addSeparator()
        
        # Undo/Redo actions
        undo_action = QAction('撤销', self)
        undo_action.setShortcut('Ctrl+Z')
        undo_action.triggered.connect(lambda: self.hmi_designer.undo())
        edit_menu.addAction(undo_action)
        
        redo_action = QAction('重做', self)
        redo_action.setShortcut('Ctrl+Y')
        redo_action.triggered.connect(lambda: self.hmi_designer.redo())
        edit_menu.addAction(redo_action)
        
        # PLC menu
        plc_menu = menubar.addMenu('PLC')
        
        connect_action = QAction('连接PLC', self)
        connect_action.triggered.connect(self.connect_plc)
        plc_menu.addAction(connect_action)
        
        disconnect_action = QAction('断开PLC连接', self)
        disconnect_action.triggered.connect(self.disconnect_plc)
        plc_menu.addAction(disconnect_action)
        
        configure_action = QAction('配置连接', self)
        configure_action.triggered.connect(self.configure_plc_connections)
        # Only engineers and admins can configure PLC connections
        if self.user_manager.has_permission('engineer'):
            plc_menu.addAction(configure_action)
        
        # Variables menu
        variables_menu = menubar.addMenu('变量')
        
        self.variable_manager_action = QAction('变量管理', self)
        self.variable_manager_action.triggered.connect(self.open_variable_manager)
        # Only engineers and admins can manage variables
        if self.user_manager.has_permission('engineer'):
            variables_menu.addAction(self.variable_manager_action)
        
        # View menu
        view_menu = menubar.addMenu('视图')
        
        refresh_action = QAction('刷新数据', self)
        refresh_action.setShortcut('F5')
        refresh_action.triggered.connect(self.refresh_data)
        view_menu.addAction(refresh_action)
        
        # HMI Designer View menu items
        view_menu.addSeparator()
        
        # Resolution settings
        resolution_menu = view_menu.addMenu('画面分辨率')
        
        # Standard resolutions
        standard_resolutions = [
            ("800x600", 800, 600),
            ("1024x768", 1024, 768),
            ("1280x720", 1280, 720),
            ("1366x768", 1366, 768),
            ("1440x900", 1440, 900),
            ("1920x1080", 1920, 1080)
        ]
        
        for name, width, height in standard_resolutions:
            resolution_action = QAction(name, self)
            resolution_action.triggered.connect(lambda checked, w=width, h=height: self.hmi_designer.set_global_resolution(w, h))
            resolution_menu.addAction(resolution_action)
        
        # Custom resolution
        custom_action = QAction('自定义分辨率...', self)
        custom_action.triggered.connect(lambda: self.hmi_designer.show_custom_resolution_dialog())
        resolution_menu.addAction(custom_action)
        
        # System monitor menu
        system_menu = menubar.addMenu('系统')
        
        system_monitor_action = QAction('系统监控', self)
        system_monitor_action.triggered.connect(self.open_system_monitor)
        system_menu.addAction(system_monitor_action)
        
        # Alarm viewer menu
        alarm_action = QAction('报警监控', self)
        alarm_action.triggered.connect(self.open_alarm_viewer)
        system_menu.addAction(alarm_action)
        
        # Terminal output menu
        terminal_action = QAction('终端输出', self)
        terminal_action.triggered.connect(self.open_terminal_output)
        system_menu.addAction(terminal_action)
        
        # Configuration menu
        config_menu = menubar.addMenu('配置')
        
        alarm_config_action = QAction('报警配置', self)
        alarm_config_action.triggered.connect(self.open_alarm_config)
        # Only engineers and admins can configure alarms
        if self.user_manager.has_permission('engineer'):
            config_menu.addAction(alarm_config_action)
        
        # Alarm type configuration menu
        alarm_type_config_action = QAction('报警类型配置', self)
        alarm_type_config_action.triggered.connect(self.open_alarm_type_config)
        # Only engineers and admins can configure alarm types
        if self.user_manager.has_permission('engineer'):
            config_menu.addAction(alarm_type_config_action)
        
        logging_config_action = QAction('数据记录配置', self)
        logging_config_action.triggered.connect(self.open_logging_config)
        # Engineers, admins and operators can view/configure logging
        if self.user_manager.has_permission('operator'):
            config_menu.addAction(logging_config_action)
        
        # User menu
        user_menu = menubar.addMenu('用户')
        
        # User management (admin only)
        if self.user_manager.has_permission('admin'):
            user_management_action = QAction('用户管理', self)
            user_management_action.triggered.connect(self.open_user_management)
            user_menu.addAction(user_management_action)
        
        # Current user info
        current_user = self.user_manager.get_current_user()
        if current_user:
            user_info_action = QAction(f'当前用户: {current_user.username} ({current_user.role.value})', self)
            user_info_action.setEnabled(False)
            user_menu.addAction(user_info_action)
        
        # Logout
        logout_action = QAction('退出登录', self)
        logout_action.triggered.connect(self.logout)
        user_menu.addAction(logout_action)
        
        # Web Access menu
        web_menu = menubar.addMenu('Web访问')
        
        self.start_web_action = QAction('启动Web服务器', self)
        self.start_web_action.triggered.connect(self.start_web_server)
        web_menu.addAction(self.start_web_action)
        
        self.stop_web_action = QAction('停止Web服务器', self)
        self.stop_web_action.triggered.connect(self.stop_web_server)
        self.stop_web_action.setEnabled(False)
        web_menu.addAction(self.stop_web_action)
        
        web_menu.addSeparator()
        
        web_info_action = QAction('Web访问地址: http://localhost:8080', self)
        web_info_action.setEnabled(False)
        web_menu.addAction(web_info_action)
        
    def start_web_server(self):
        """Start the web server for remote access"""
        if not WEB_SERVER_AVAILABLE:
            QMessageBox.warning(self, "警告", "Web服务器模块不可用，请安装依赖: pip install flask flask-socketio flask-cors eventlet")
            return
        
        try:
            if self.web_server is None:
                self.web_server = WebServer(
                    data_manager=self.data_manager,
                    plc_manager=self.plc_manager,
                    project_manager=self.project_manager,
                    host='0.0.0.0',
                    port=8080
                )
                
                # Start web server in a separate thread
                self.web_server_thread = threading.Thread(target=self.web_server.start)
                self.web_server_thread.daemon = True
                self.web_server_thread.start()
                
                # Wait a moment for server to start and determine actual port
                import time
                time.sleep(0.5)
                
                actual_port = self.web_server.port if hasattr(self.web_server, 'port') else 8080
                
                self.start_web_action.setEnabled(False)
                self.stop_web_action.setEnabled(True)
                self.status_bar.showMessage(f"Web服务器已启动: http://localhost:{actual_port}", 5000)
                logger.info(f"Web server started on http://localhost:{actual_port}")
                QMessageBox.information(self, "成功", f"Web服务器已启动\n访问地址: http://localhost:{actual_port}")
        except Exception as e:
            logger.error(f"Failed to start web server: {e}")
            QMessageBox.critical(self, "错误", f"启动Web服务器失败: {str(e)}")
    
    def stop_web_server(self):
        """Stop the web server"""
        try:
            if self.web_server:
                self.web_server.stop()
                self.web_server = None
                self.web_server_thread = None
                
                self.start_web_action.setEnabled(True)
                self.stop_web_action.setEnabled(False)
                self.status_bar.showMessage("Web服务器已停止", 3000)
                logger.info("Web server stopped")
        except Exception as e:
            logger.error(f"Error stopping web server: {e}")
        
    def create_tool_bar(self):
        """Create the toolbar"""
        toolbar = self.addToolBar('主工具栏')
        
        # Project actions (essential for quick access)
        toolbar.addAction(QIcon(), '新建', self.new_project)
        toolbar.addAction(QIcon(), '打开', self.open_project)
        toolbar.addAction(QIcon(), '保存', self.save_project)
        
        toolbar.addSeparator()
        
        # Essential runtime controls
        self.run_btn = toolbar.addAction(QIcon(), '运行系统', self.run_system)
        self.run_btn.setToolTip('启动整个SCADA系统')
        
        self.stop_btn = toolbar.addAction(QIcon(), '停止系统', self.stop_system)
        self.stop_btn.setToolTip('停止整个SCADA系统')
        self.stop_btn.setEnabled(False)
        
        toolbar.addSeparator()
        
        # Quick access to data refresh
        toolbar.addAction(QIcon(), '刷新', self.refresh_data)
        
        toolbar.addSeparator()
        

        
    def create_central_widget(self):
        """Create the central widget with tabs"""
        central_widget = QWidget()
        layout = QVBoxLayout()
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Add HMI Designer as the first tab
        self.tab_widget.addTab(self.hmi_designer, "HMI设计")
        
        # Create data monitor widget
        self.data_monitor_widget = DataMonitorWidget(self.data_manager, self.plc_manager)
        self.tab_widget.addTab(self.data_monitor_widget, "数据监控")
        
        # Create history viewer widget
        from .history_viewer import HistoryViewerWidget
        self.history_viewer_widget = HistoryViewerWidget(self.data_manager)
        self.tab_widget.addTab(self.history_viewer_widget, "历史查询")
        
        layout.addWidget(self.tab_widget)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        # Initialize HMI viewer window
        self.hmi_viewer_window = None
        

        
    def create_status_bar(self):
        """Create the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 - SCADA系统已初始化")
        
    # Menu action handlers
    def new_project(self):
        """Create a new project"""
        # Check for unsaved changes first
        if self._has_unsaved_changes or self._check_for_changes():
            reply = QMessageBox.question(
                self, '保存更改',
                '当前项目有未保存的更改，是否保存？',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                if not self.save_project():
                    return  # Save failed or cancelled
            elif reply == QMessageBox.Cancel:
                return  # User cancelled
        
        # Reset managers
        self.plc_manager = PLCManager()
        self.data_manager = DataManager()
        self.plc_manager.set_data_manager(self.data_manager)
        self.config_manager = ConfigurationManager(self.data_manager, self.plc_manager)
        
        # Clear modification flag
        self._has_unsaved_changes = False
        
        self.status_bar.showMessage("新项目已创建", 2000)
        
    def open_project(self):
        """Open an existing project"""
        # Check for unsaved changes first
        if self._has_unsaved_changes or self._check_for_changes():
            reply = QMessageBox.question(
                self, '保存更改',
                '当前项目有未保存的更改，是否保存？',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                if not self.save_project():
                    return  # Save failed or cancelled
            elif reply == QMessageBox.Cancel:
                return  # User cancelled
        
        from PyQt5.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, '打开SCADA配置', '', 'SCADA配置文件 (*.json);;所有文件 (*)'
        )

        if file_path:
            if self.config_manager.load_configuration(file_path):
                # Sync logging rules to system_service_manager
                self._sync_logging_rules_to_service()
                # Clear modification flag
                self._has_unsaved_changes = False
                self.status_bar.showMessage(f"项目已加载: {file_path}", 2000)
            else:
                QMessageBox.critical(self, "错误", f"从 {file_path} 加载配置失败")

    def _sync_logging_rules_to_service(self):
        """Sync logging rules from config_manager to system_service_manager"""
        try:
            # Get logging configs from config_manager (already loaded)
            logging_configs = getattr(self.config_manager, 'logging_rules', [])

            if logging_configs:
                self.system_service_manager.set_logging_rules(logging_configs)

        except Exception as e:
            pass
        
    def save_project(self):
        """Save the current project, returns True on success"""
        return self._do_save()
    
    def save_project_as(self):
        """Save the current project with a new name, returns True on success"""
        from PyQt5.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, '保存项目', 'project.hmi', 'HMI项目文件 (*.hmi);;JSON文件 (*.json);;所有文件 (*)'
        )
        
        if file_path:
            if self.project_manager.save_project(file_path):
                self.status_bar.showMessage(f"项目已保存: {file_path}", 2000)
                self.clear_modified()
                return True
            else:
                QMessageBox.critical(self, "错误", "保存项目失败")
                return False
        return False
        
    def connect_plc(self):
        """Connect to PLCs"""
        self.status_bar.showMessage("正在连接PLC...", 2000)
        
        # Connect to all configured PLCs
        self.plc_manager.connect_all()
        
        # Start data polling to sync PLC data to DataManager
        self.data_poller.start_polling()
        
        self.status_bar.showMessage("已连接到PLC并开始数据轮询", 5000)
        
    def disconnect_plc(self):
        """Disconnect from PLCs"""
        self.status_bar.showMessage("正在断开PLC连接...", 2000)
        
        # Stop data polling
        self.data_poller.stop_polling()
        
        # Disconnect from all PLCs
        self.plc_manager.disconnect_all()
        
        self.status_bar.showMessage("已断开PLC连接并停止数据轮询", 5000)
        
    def configure_plc_connections(self):
        """Open PLC configuration dialog"""
        from scada_app.comm.connection_config import ConnectionManagerDialog
        dialog = ConnectionManagerDialog(self, self.plc_manager)
        dialog.exec_()
        
    def open_variable_manager(self):
        """Open variable manager"""
        from scada_app.core.variable_manager import VariableManagementDialog
        dialog = VariableManagementDialog(self, self.data_manager, self.plc_manager, self.config_manager)
        dialog.exec_()
        self.status_bar.showMessage("变量管理器已打开", 2000)
        
    def start_monitoring(self):
        """Start the tag monitoring service"""
        if hasattr(self, 'tag_monitor'):
            self.tag_monitor.start_monitoring(1000)  # Update every 1000ms
            self.status_bar.showMessage("标签监控已启动", 2000)
    
    def stop_monitoring(self):
        """Stop the tag monitoring service"""
        if hasattr(self, 'tag_monitor'):
            self.tag_monitor.stop_monitoring()
            self.status_bar.showMessage("标签监控已停止", 2000)
    
    def open_alarm_config(self):
        """Open the alarm configuration dialog"""
        try:
            from scada_app.hmi.alarm_config_new import AlarmConfigDialog
            dialog = AlarmConfigDialog(self, self.data_manager, self.config_manager)
            if dialog.exec_() == QDialog.Accepted:
                # Process the alarm rules if needed
                alarm_rules = dialog.get_alarm_rules()
                self.status_bar.showMessage(f"报警配置已更新，包含 {len(alarm_rules)} 条规则", 2000)
        except ImportError:
            # 如果新模块不存在，回退到旧版本
            try:
                from scada_app.hmi.alarm_config import AlarmConfigDialog
                dialog = AlarmConfigDialog(self, self.data_manager)
                if dialog.exec_() == QDialog.Accepted:
                    alarm_rules = dialog.get_alarm_rules()
                    self.status_bar.showMessage(f"报警配置已更新，包含 {len(alarm_rules)} 条规则", 2000)
            except ImportError:
                QMessageBox.warning(self, "Missing Module", "Alarm configuration module not found.")
    
    def open_logging_config(self):
        """Open the data logging configuration dialog"""
        try:
            from scada_app.hmi.data_logging_config import DataLoggingConfigDialog
            dialog = DataLoggingConfigDialog(self, self.data_manager, self.config_manager)
            if dialog.exec_() == QDialog.Accepted:
                # Process the logging rules if needed
                log_rules = dialog.get_log_rules()

                rules_dict_list = []
                for rule in log_rules:
                    rules_dict_list.append({
                        'tag_name': rule.tag_name,
                        'sample_rate': rule.sample_rate,
                        'storage_duration_days': rule.storage_duration_days,
                        'enabled': rule.enabled,
                        'rule_id': rule.rule_id
                    })

                self.config_manager.logging_rules = rules_dict_list

                self.system_service_manager.set_logging_rules(rules_dict_list)

                self.status_bar.showMessage(f"数据记录配置已更新，包含 {len(log_rules)} 条规则", 2000)
        except ImportError as e:
            QMessageBox.warning(self, "Missing Module", f"Data logging configuration module not found: {str(e)}")
    
    def open_alarm_type_config(self):
        """Open the alarm type configuration dialog"""
        try:
            from scada_app.hmi.alarm_type_config import AlarmTypeConfigDialog
            dialog = AlarmTypeConfigDialog(self)
            dialog.exec_()
            self.status_bar.showMessage("报警类型配置已更新", 2000)
        except ImportError as e:
            QMessageBox.warning(self, "模块缺失", f"报警类型配置模块未找到: {e}")
    
    
    def run_system(self):
        """Run the entire SCADA system - activate all components"""
        self.status_bar.showMessage("正在启动SCADA系统...", 2000)
        
        # Connect to PLCs
        self.plc_manager.connect_all()
        
        # Apply poll interval from config
        if hasattr(self.config_manager, 'poll_interval'):
            self.data_poller.set_poll_interval(self.config_manager.poll_interval)
        
        # Start data polling to sync PLC data to DataManager
        self.data_poller.start_polling()
        
        # Start monitoring
        if hasattr(self, 'tag_monitor'):
            self.tag_monitor.start_monitoring(1000)  # Update every 1000ms
        
        # Open HMI Viewer in a separate window
        if hasattr(self, 'hmi_designer'):
            try:
                # Create a temporary HMI file from current project data
                import os
                import tempfile
                import json
                
                hmi_viewer_path = os.path.join(tempfile.gettempdir(), "current_hmi_screen.hmi")
                
                # Build HMI project data from designer screens
                if self.hmi_designer.screens:
                    print(f"Preparing HMI data from {len(self.hmi_designer.screens)} screens")
                    hmi_data = {
                        'hmi_screens': []
                    }
                    
                    for screen in self.hmi_designer.screens:
                        # Handle both HMIScreen objects and dict formats
                        if hasattr(screen, 'objects'):
                            objects = screen.objects
                            screen_name = screen.name if hasattr(screen, 'name') else 'Untitled'
                            screen_number = screen.number if hasattr(screen, 'number') else 0
                            screen_is_main = screen.is_main if hasattr(screen, 'is_main') else False
                            screen_resolution = screen.resolution if hasattr(screen, 'resolution') else {'width': 1000, 'height': 600}
                        else:
                            objects = screen.get('objects', [])
                            screen_name = screen.get('name', 'Untitled')
                            screen_number = screen.get('number', 0)
                            screen_is_main = screen.get('is_main', False)
                            screen_resolution = screen.get('resolution', {'width': 1000, 'height': 600})
                        
                        print(f"  Processing screen '{screen_name}': {len(objects)} objects")
                        
                        # Get background color
                        screen_bg_color = screen.background_color if hasattr(screen, 'background_color') else screen.get('background_color', '#FFFFFF')
                        
                        screen_data = {
                            'name': screen_name,
                            'number': screen_number,
                            'is_main': screen_is_main,
                            'resolution': screen_resolution,
                            'background_color': screen_bg_color,
                            'objects': []
                        }
                        
                        for obj in objects:
                            obj_data = {
                                'obj_type': obj.obj_type,
                                'x': obj.x,
                                'y': obj.y,
                                'width': obj.width,
                                'height': obj.height,
                                'properties': obj.properties,
                                'variables': []
                            }
                            
                            for var in obj.variables:
                                var_data = {
                                    'variable_name': var.variable_name,
                                    'variable_type': var.variable_type,
                                    'address': var.address,
                                    'description': var.description,
                                    'bit_offset': getattr(var, 'bit_offset', None)
                                }
                                obj_data['variables'].append(var_data)
                            
                            if hasattr(obj, 'visibility'):
                                obj_data['visibility'] = obj.visibility.copy()
                            
                            screen_data['objects'].append(obj_data)
                        
                        hmi_data['hmi_screens'].append(screen_data)
                    
                    # Save to temporary file for HMI viewer
                    with open(hmi_viewer_path, 'w', encoding='utf-8') as f:
                        json.dump(hmi_data, f, indent=2, ensure_ascii=False)
                    
                    print(f"HMI project data prepared with {len(hmi_data['hmi_screens'])} screens")
                
                # Create and show HMI viewer window
                if self.hmi_viewer_window is None or not self.hmi_viewer_window.isVisible():
                    from PyQt5.QtCore import Qt
                    from PyQt5.QtWidgets import QWidget
                    # Use QWidget instead of QDialog and don't set parent to avoid stay-on-top behavior
                    self.hmi_viewer_window = QWidget()
                    self.hmi_viewer_window.setWindowTitle("HMI运行视图")
                    self.hmi_viewer_window.setGeometry(150, 150, 1200, 800)
                    # Enable maximize and minimize buttons
                    self.hmi_viewer_window.setWindowFlags(
                        Qt.Window |
                        Qt.WindowMaximizeButtonHint |
                        Qt.WindowMinimizeButtonHint |
                        Qt.WindowCloseButtonHint
                    )

                    from .hmi_viewer import HMIViewer
                    self.hmi_viewer = HMIViewer()
                    self.hmi_viewer.set_managers(self.data_manager, self.plc_manager, self.system_service_manager)
                    self.hmi_viewer.load_hmi_project(hmi_viewer_path)
                    self.hmi_viewer.start_refresh()

                    layout = QVBoxLayout()
                    layout.setContentsMargins(0, 0, 0, 0)  # Remove white border
                    layout.setSpacing(0)  # Remove spacing between widgets
                    layout.addWidget(self.hmi_viewer)
                    self.hmi_viewer_window.setLayout(layout)
                    
                    # Connect close event to save trend data
                    self.hmi_viewer_window.closeEvent = lambda event: self._on_hmi_viewer_close(event)

                    # Show as independent window (not stay on top)
                    self.hmi_viewer_window.show()
                    self.status_bar.showMessage("HMI运行视图已打开", 2000)
                else:
                    # Just raise the window without forcing it to stay on top
                    self.hmi_viewer_window.raise_()
                    self.hmi_viewer_window.activateWindow()
                
            except Exception as e:
                print(f"Error preparing HMI project: {e}")
                import traceback
                traceback.print_exc()
        
        # Sync logging rules from config_manager to system_service_manager
        self._sync_logging_rules_to_service()
        
        # Enable alarm monitoring
        # This would be handled by the tag monitor or a separate alarm service
        # For now, we assume it's integrated with the tag monitoring
        
        # Start system services (alarms, logging, etc.)
        self.system_service_manager.start_services()
        
        # Load alarm rules from configuration
        # This would typically be loaded from a configuration file or database
        # For now, we'll create some default alarm rules for demonstration
        try:
            from scada_app.hmi.alarm_config import AlarmRule
            
            # Create default alarm rules if none exist
            default_rules = []
            
            # Add a high temperature alarm rule if temperature tag exists
            if '温度' in self.data_manager.tags:
                temp_rule = AlarmRule(
                    tag_name='温度',
                    alarm_type='LIMIT',
                    condition='HIGH',
                    threshold=80.0,
                    message='温度超过上限',
                    enabled=True,
                    priority='HIGH'
                )
                default_rules.append(temp_rule)
            
            # Add a low pressure alarm rule if pressure tag exists
            if '压力' in self.data_manager.tags:
                pressure_rule = AlarmRule(
                    tag_name='压力',
                    alarm_type='LIMIT',
                    condition='LOW',
                    threshold=1.0,
                    message='压力低于下限',
                    enabled=True,
                    priority='MEDIUM'
                )
                default_rules.append(pressure_rule)
            
            # Set alarm rules
            if default_rules:
                self.system_service_manager.set_alarm_rules(default_rules)
                logger.info(f"Loaded {len(default_rules)} default alarm rules")
        except ImportError:
            logger.warning("Alarm configuration module not found, using default alarm logic")
        
        # Update UI
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # Switch to data monitoring view automatically
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "数据监控":
                self.tab_widget.setCurrentIndex(i)
                break
        
        self.status_bar.showMessage("SCADA系统运行中 - 所有组件已激活", 5000)
    
    def stop_system(self):
        """Stop the entire SCADA system"""
        self.status_bar.showMessage("正在停止SCADA系统...", 2000)
        
        # Stop data polling
        self.data_poller.stop_polling()
        
        # Stop monitoring
        if hasattr(self, 'tag_monitor'):
            self.tag_monitor.stop_monitoring()
        
        # Stop system services
        self.system_service_manager.stop_services()
        
        # Stop HMI viewer refresh
        if hasattr(self, 'hmi_viewer') and self.hmi_viewer:
            self.hmi_viewer.stop_refresh()
        
        # Close HMI viewer window if open
        if hasattr(self, 'hmi_viewer_window') and self.hmi_viewer_window:
            if self.hmi_viewer_window.isVisible():
                self.hmi_viewer_window.close()
                self.hmi_viewer_window = None
        
        # Disconnect from PLCs
        self.plc_manager.disconnect_all()
        
        # Update UI
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # Switch back to design view
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "HMI设计":
                self.tab_widget.setCurrentIndex(i)
                break
        
        self.status_bar.showMessage("SCADA系统已停止", 5000)
    
    def _on_hmi_viewer_close(self, event):
        """Handle HMI viewer window close event - save trend data"""
        if hasattr(self, 'hmi_viewer') and self.hmi_viewer:
            self.hmi_viewer.stop_refresh()
            self.hmi_viewer.cleanup()
        event.accept()
    
    def auto_load_recent_project(self):
        """Auto-load the most recently used project on startup"""
        recent_project = self.project_manager.get_recent_project_file()
        if recent_project:
            success = self.project_manager.load_project(recent_project)
            if success:
                self.status_bar.showMessage(f"最近项目已加载: {recent_project}", 3000)
                print(f"Auto-loaded recent project: {recent_project}")
            else:
                self.status_bar.showMessage("无法加载最近项目", 3000)
        else:
            self.status_bar.showMessage("无最近项目可加载", 2000)
    
    def new_project(self):
        """Create a new project"""
        from PyQt5.QtWidgets import QFileDialog
        project_file, _ = QFileDialog.getSaveFileName(
            self, "New Project", "", "SCADA Project Files (*.scada);;All Files (*)"
        )
        if project_file:
            if not project_file.endswith('.scada'):
                project_file += '.scada'
            
            # Clear current configuration
            self._clear_current_configuration()
            
            # Set project file and save
            self.project_manager.project_file = project_file
            success = self.project_manager.save_project(project_file, is_save_as=True)
            
            if success:
                # Set as recent project
                self.project_manager.set_recent_project_file(project_file)
                self.status_bar.showMessage(f"New project created and saved: {project_file}", 3000)
            else:
                self.status_bar.showMessage("Failed to save new project", 3000)
    
    def open_project(self):
        """Open an existing project"""
        from PyQt5.QtWidgets import QFileDialog
        project_file, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "SCADA Project Files (*.scada);;All Files (*)"
        )
        if project_file:
            success = self.project_manager.load_project(project_file)
            if success:
                self.project_manager.set_recent_project_file(project_file)
                self.status_bar.showMessage(f"Project opened: {project_file}", 3000)
            else:
                self.status_bar.showMessage("Failed to open project", 3000)
    
    def save_project(self):
        """Save the current project"""
        if self.project_manager.project_file:
            success = self.project_manager.save_project(self.project_manager.project_file, is_save_as=False)
            if success:
                self.status_bar.showMessage(f"Project saved: {self.project_manager.project_file}", 3000)
            else:
                self.status_bar.showMessage("Failed to save project", 3000)
        else:
            self.save_project_as()
    
    def save_project_as(self):
        """Save the current project with a new name"""
        from PyQt5.QtWidgets import QFileDialog
        
        # Get current project directory as default location
        default_dir = ""
        if self.project_manager.project_dir:
            default_dir = str(self.project_manager.project_dir)
        
        project_file, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", default_dir, "SCADA Project Files (*.scada);;All Files (*)"
        )
        if project_file:
            if not project_file.endswith('.scada'):
                project_file += '.scada'
            
            # This is a "Save As" operation - copy all resources
            success = self.project_manager.save_project(project_file, is_save_as=True)
            if success:
                self.project_manager.set_recent_project_file(project_file)
                self.status_bar.showMessage(f"Project saved as: {project_file}", 3000)
            else:
                self.status_bar.showMessage("Failed to save project", 3000)
    
    def _clear_current_configuration(self):
        """Clear the current configuration"""
        # Clear PLC connections
        self.plc_manager.connections.clear()
        self.plc_manager.active_connections.clear()
        
        # Clear data manager tags
        self.data_manager.tags.clear()
        self.data_manager.alarms.clear()
        
        # Clear HMI designer objects
        self.hmi_designer.objects = []
        self.hmi_designer.scene.clear()
        self.hmi_designer.selected_object = None
        self.hmi_designer.update_properties_panel()
    
    def refresh_data(self):
        """Refresh all data displays"""
        self.status_bar.showMessage("Refreshing data...", 2000)
        
        # Refresh data monitor
        if hasattr(self, 'data_monitor_widget'):
            self.data_monitor_widget.populate_tag_table()
    

    
    def open_user_management(self):
        """Open user management dialog"""
        dialog = UserManagementDialog(self.user_manager, self)
        dialog.exec_()
    
    def logout(self):
        """Logout current user and show login dialog"""
        # Stop all services
        self.data_poller.stop_polling()
        self.system_service_manager.stop_all_services()
        
        # Disconnect all PLCs
        self.plc_manager.disconnect_all()
        
        # Clear current user
        self.user_manager.logout()
        
        # Show login dialog again
        login_dialog = LoginDialog(self)
        if login_dialog.exec_() == QDialog.Accepted:
            # Get the authenticated user manager
            self.user_manager = login_dialog.get_user_manager()
            
            # Recreate menu bar with new user permissions
            self.menuBar().clear()
            self.create_menu_bar()
            
            # Update status bar
            current_user = self.user_manager.get_current_user()
            if current_user:
                self.status_bar.showMessage(f"欢迎回来，{current_user.username} ({current_user.role.value})", 3000)
        else:
            # User canceled login, exit application
            QApplication.instance().quit()
    
    def open_system_monitor(self):
        """Open system monitor dialog"""
        dialog = SystemMonitorDialog(self)
        dialog.exec_()
    
    def open_alarm_viewer(self):
        """Open alarm viewer dialog"""
        try:
            # 如果窗口已存在且可见，直接激活
            if hasattr(self, '_alarm_viewer') and self._alarm_viewer is not None and self._alarm_viewer.isVisible():
                self._alarm_viewer.raise_()
                self._alarm_viewer.activateWindow()
                return
            
            # 创建新窗口，使用self作为父窗口防止被垃圾回收
            self._alarm_viewer = AlarmViewerDialog(self, self.data_manager, self.system_service_manager)
            
            # 连接窗口关闭信号
            self._alarm_viewer.destroyed.connect(self._on_alarm_viewer_closed)
            
            # 显示窗口
            self._alarm_viewer.show()
            self._alarm_viewer.raise_()
            self._alarm_viewer.activateWindow()
            
        except Exception as e:
            print(f"打开报警监控窗口失败: {e}")
            import traceback
            traceback.print_exc()
            self._alarm_viewer = None
    
    def _on_alarm_viewer_closed(self):
        """Handle alarm viewer window close"""
        self._alarm_viewer = None
    
    def open_terminal_output(self):
        """Open terminal output window"""
        if not hasattr(self, '_terminal_window') or self._terminal_window is None:
            self._terminal_window = TerminalOutputWindow(self)
        self._terminal_window.show()
        self._terminal_window.raise_()
        self._terminal_window.activateWindow()


class TerminalOutputWindow(QDialog):
    """终端输出窗口 - 显示系统日志和调试信息"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("终端输出")
        self.setGeometry(100, 100, 800, 600)
        self.init_ui()
        self.start_capturing()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 输出文本框
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
        """)
        layout.addWidget(self.output_text)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear_output)
        btn_layout.addWidget(self.clear_btn)
        
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setCheckable(True)
        self.pause_btn.clicked.connect(self.toggle_pause)
        btn_layout.addWidget(self.pause_btn)
        
        btn_layout.addStretch()
        
        self.copy_btn = QPushButton("复制")
        self.copy_btn.clicked.connect(self.copy_output)
        btn_layout.addWidget(self.copy_btn)
        
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_output)
        btn_layout.addWidget(self.save_btn)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # 定时器用于更新输出
        self.update_timer = None
        self.is_paused = False
        self.output_buffer = []
    
    def start_capturing(self):
        """开始捕获输出"""
        import sys
        from PyQt5.QtCore import QTimer
        
        # 保存原始stdout
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
        # 创建自定义输出流
        class OutputStream:
            def __init__(self, window):
                self.window = window
                self.max_buffer_size = 10000  # 最大缓冲区条目数
            
            def write(self, text):
                if text:
                    # 限制缓冲区大小，防止内存溢出
                    if len(self.window.output_buffer) > self.max_buffer_size:
                        # 丢弃最旧的 20% 数据
                        self.window.output_buffer = self.window.output_buffer[int(self.max_buffer_size * 0.2):]
                    self.window.output_buffer.append(text)
            
            def flush(self):
                pass
        
        # 重定向stdout和stderr
        sys.stdout = OutputStream(self)
        sys.stderr = OutputStream(self)
        
        # 创建定时器定期更新显示
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(100)  # 每100ms更新一次
    
    def update_display(self):
        """更新显示"""
        if self.is_paused or not self.output_buffer:
            return
        
        # 批量处理输出
        text = ''.join(self.output_buffer)
        self.output_buffer.clear()
        
        if text:
            # 限制单行长度，防止过长行导致性能问题
            max_line_length = 1000
            lines = text.split('\n')
            truncated_lines = []
            for line in lines:
                if len(line) > max_line_length:
                    line = line[:max_line_length] + '...[截断]'
                truncated_lines.append(line)
            text = '\n'.join(truncated_lines)
            
            self.output_text.moveCursor(self.output_text.textCursor().End)
            self.output_text.insertPlainText(text)
            
            # 限制行数，防止内存溢出
            max_lines = 5000
            doc = self.output_text.document()
            if doc.lineCount() > max_lines:
                cursor = self.output_text.textCursor()
                cursor.movePosition(cursor.Start)
                cursor.movePosition(cursor.Down, cursor.KeepAnchor, doc.lineCount() - max_lines)
                cursor.removeSelectedText()
    
    def clear_output(self):
        """清空输出"""
        self.output_text.clear()
        self.output_buffer.clear()
    
    def toggle_pause(self):
        """暂停/继续"""
        self.is_paused = self.pause_btn.isChecked()
        self.pause_btn.setText("继续" if self.is_paused else "暂停")
    
    def copy_output(self):
        """复制到剪贴板"""
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(self.output_text.toPlainText())
    
    def save_output(self):
        """保存到文件"""
        from PyQt5.QtWidgets import QFileDialog
        from datetime import datetime
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存终端输出", 
            f"terminal_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.output_text.toPlainText())
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"无法保存文件: {e}")
    
    def closeEvent(self, event):
        """关闭事件"""
        import sys
        
        # 恢复原始stdout
        if hasattr(self, 'original_stdout'):
            sys.stdout = self.original_stdout
        if hasattr(self, 'original_stderr'):
            sys.stderr = self.original_stderr
        
        if self.update_timer:
            self.update_timer.stop()
        
        # 通知父窗口
        if self.parent() and hasattr(self.parent(), '_terminal_window'):
            self.parent()._terminal_window = None
        
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()