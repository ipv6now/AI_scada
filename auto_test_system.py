"""
自动测试系统 - 主动检测SCADA系统bug
"""
import sys
import os
import traceback
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class AutoTestSystem:
    """自动测试系统"""
    
    def __init__(self):
        self.test_results = []
        self.errors_found = []
        self.warnings_found = []
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始自动测试系统...")
        print("=" * 60)
        
        # 运行模块导入测试
        self.test_module_imports()
        
        # 运行类初始化测试  
        self.test_class_initialization()
        
        # 运行数据库连接测试
        self.test_database_connections()
        
        # 运行报警系统测试
        self.test_alarm_system()
        
        # 运行项目管理器测试
        self.test_project_manager()
        
        # 运行UI组件测试
        self.test_ui_components()
        
        # 显示测试结果
        self.print_test_results()
        
        return len(self.errors_found) == 0
    
    def test_module_imports(self):
        """测试所有模块是否能正常导入"""
        print("📦 测试模块导入...")
        
        modules_to_test = [
            "scada_app.core.data_manager",
            "scada_app.core.system_service_manager", 
            "scada_app.core.project_manager",
            "scada_app.core.alarm_type_manager",
            "scada_app.hmi.main_window",
            "scada_app.hmi.alarm_viewer",
            "scada_app.hmi.alarm_config_new",
            "scada_app.hmi.alarm_type_config"
        ]
        
        for module_path in modules_to_test:
            try:
                __import__(module_path)
                self.log_success(f"✓ {module_path} 导入成功")
            except Exception as e:
                self.log_error(f"✗ {module_path} 导入失败: {e}")
                self.errors_found.append(f"模块导入失败: {module_path} - {e}")
    
    def test_class_initialization(self):
        """测试核心类是否能正常初始化"""
        print("\n🏗️  测试类初始化...")
        
        try:
            from scada_app.core.data_manager import DataManager
            dm = DataManager()
            self.log_success("✓ DataManager 初始化成功")
            
            # 保存DataManager实例供其他测试使用
            self.data_manager = dm
        except Exception as e:
            self.log_error(f"✗ DataManager 初始化失败: {e}")
            self.errors_found.append(f"DataManager初始化失败: {e}")
            return  # 如果DataManager失败，其他测试无法继续
        
        try:
            from scada_app.core.system_service_manager import SystemServiceManager
            # 创建模拟的PLC管理器
            class MockPLCManager:
                def __init__(self):
                    self.connections = {}
                def get_connection(self, name):
                    return None
            
            # 创建模拟的配置管理器
            class MockConfigManager:
                def __init__(self):
                    self.alarm_rules = []
            
            plc_manager = MockPLCManager()
            config_manager = MockConfigManager()
            
            ssm = SystemServiceManager(self.data_manager, plc_manager, config_manager)
            self.log_success("✓ SystemServiceManager 初始化成功")
            
            # 保存实例供其他测试使用
            self.system_service_manager = ssm
            self.plc_manager = plc_manager
            self.config_manager = config_manager
            
        except Exception as e:
            self.log_error(f"✗ SystemServiceManager 初始化失败: {e}")
            self.errors_found.append(f"SystemServiceManager初始化失败: {e}")
        
        try:
            from scada_app.core.project_manager import ProjectManager
            pm = ProjectManager(self.data_manager, self.plc_manager, self.config_manager)
            self.log_success("✓ ProjectManager 初始化成功")
            
            # 保存实例供其他测试使用
            self.project_manager = pm
            
        except Exception as e:
            self.log_error(f"✗ ProjectManager 初始化失败: {e}")
            self.errors_found.append(f"ProjectManager初始化失败: {e}")
    
    def test_database_connections(self):
        """测试数据库连接和表结构"""
        print("\n🗄️  测试数据库连接...")
        
        try:
            from scada_app.core.data_manager import DataManager
            dm = DataManager()
            
            # 测试数据库连接
            conn = dm._get_connection()
            cursor = conn.cursor()
            
            # 检查表结构
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            expected_tables = ['tags', 'tag_history', 'alarms']
            found_tables = [table[0] for table in tables]
            
            for table in expected_tables:
                if table in found_tables:
                    self.log_success(f"✓ 数据库表 {table} 存在")
                else:
                    self.log_error(f"✗ 数据库表 {table} 不存在")
                    self.errors_found.append(f"数据库表缺失: {table}")
            
            # 检查alarms表结构
            cursor.execute("PRAGMA table_info(alarms)")
            columns = [col[1] for col in cursor.fetchall()]
            
            expected_columns = ['alarm_type_name']
            for col in expected_columns:
                if col in columns:
                    self.log_success(f"✓ alarms表包含列 {col}")
                else:
                    self.log_error(f"✗ alarms表缺少列 {col}")
                    self.errors_found.append(f"alarms表缺少列: {col}")
            
            dm._return_connection(conn)
            
        except Exception as e:
            self.log_error(f"✗ 数据库测试失败: {e}")
            self.errors_found.append(f"数据库测试失败: {e}")
    
    def test_alarm_system(self):
        """测试报警系统功能"""
        print("\n🚨 测试报警系统...")
        
        # 检查是否已初始化必要的实例
        if not hasattr(self, 'data_manager'):
            self.log_error("✗ DataManager未初始化，跳过报警系统测试")
            return
        
        try:
            # 测试报警触发
            try:
                self.data_manager.raise_alarm(
                    tag_name="test_tag",
                    alarm_type="状态变化_假变真", 
                    message="自动测试报警",
                    alarm_type_name="危急"
                )
                self.log_success("✓ 报警触发成功")
            except Exception as e:
                self.log_error(f"✗ 报警触发失败: {e}")
                self.errors_found.append(f"报警触发失败: {e}")
            
            # 检查报警是否保存到数据库
            conn = self.data_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM alarms WHERE tag_name='test_tag'")
            count = cursor.fetchone()[0]
            
            if count > 0:
                self.log_success("✓ 报警成功保存到数据库")
            else:
                self.log_error("✗ 报警未保存到数据库")
                self.errors_found.append("报警未保存到数据库")
            
            self.data_manager._return_connection(conn)
            
        except Exception as e:
            self.log_error(f"✗ 报警系统测试失败: {e}")
            self.errors_found.append(f"报警系统测试失败: {e}")
    
    def test_project_manager(self):
        """测试项目管理器功能"""
        print("\n📁 测试项目管理器...")
        
        # 检查是否已初始化必要的实例
        if not hasattr(self, 'project_manager'):
            self.log_error("✗ ProjectManager未初始化，跳过项目管理器测试")
            return
        
        try:
            # 测试项目保存和加载
            test_project_file = "test_project.hmiproject"
            
            # 创建测试项目数据
            self.project_manager.project_data = {
                'metadata': {'version': '1.6'},
                'alarms': [],
                'alarm_types': {'critical': {'display_name': '危急'}}
            }
            
            # 测试保存
            success = self.project_manager.save_project(test_project_file)
            if success:
                self.log_success("✓ 项目保存成功")
            else:
                self.log_error("✗ 项目保存失败")
                self.errors_found.append("项目保存失败")
            
            # 测试加载
            success = self.project_manager.load_project(test_project_file)
            if success:
                self.log_success("✓ 项目加载成功")
            else:
                self.log_error("✗ 项目加载失败")
                self.errors_found.append("项目加载失败")
            
            # 清理测试文件
            if os.path.exists(test_project_file):
                os.remove(test_project_file)
                
        except Exception as e:
            self.log_error(f"✗ 项目管理器测试失败: {e}")
            self.errors_found.append(f"项目管理器测试失败: {e}")
    
    def test_ui_components(self):
        """测试UI组件（不显示窗口）"""
        print("\n🖥️  测试UI组件...")
        
        try:
            # 测试报警配置对话框初始化
            from scada_app.hmi.alarm_config_new import AlarmConfigDialog
            
            # 不显示窗口，只测试初始化
            dialog = AlarmConfigDialog(None, None, None)
            self.log_success("✓ 报警配置对话框初始化成功")
            
        except Exception as e:
            self.log_error(f"✗ UI组件测试失败: {e}")
            self.errors_found.append(f"UI组件测试失败: {e}")
    
    def log_success(self, message):
        """记录成功信息"""
        print(f"  {message}")
        self.test_results.append(("SUCCESS", message))
    
    def log_error(self, message):
        """记录错误信息"""
        print(f"  {message}")
        self.test_results.append(("ERROR", message))
    
    def log_warning(self, message):
        """记录警告信息"""
        print(f"  ⚠ {message}")
        self.test_results.append(("WARNING", message))
    
    def print_test_results(self):
        """打印测试结果"""
        print("\n" + "=" * 60)
        print("📊 测试结果汇总:")
        print("=" * 60)
        
        success_count = len([r for r in self.test_results if r[0] == "SUCCESS"])
        error_count = len([r for r in self.test_results if r[0] == "ERROR"])
        
        print(f"✅ 成功: {success_count}")
        print(f"❌ 错误: {error_count}")
        
        if error_count > 0:
            print(f"\n🔧 发现 {len(self.errors_found)} 个需要修复的问题:")
            for i, error in enumerate(self.errors_found, 1):
                print(f"  {i}. {error}")
        else:
            print("\n🎉 所有测试通过！系统运行正常。")
        
        print("=" * 60)


def run_auto_test():
    """运行自动测试"""
    tester = AutoTestSystem()
    success = tester.run_all_tests()
    
    # 如果有错误，自动尝试修复
    if not success and tester.errors_found:
        print("\n🛠️  尝试自动修复发现的问题...")
        auto_fix_errors(tester.errors_found)
        
        # 重新运行测试验证修复效果
        print("\n🔄 重新运行测试验证修复效果...")
        tester = AutoTestSystem()
        success = tester.run_all_tests()
    
    return success


def auto_fix_errors(errors):
    """自动修复常见错误"""
    for error in errors:
        if "alarm_type_name" in error and "缺少列" in error:
            print("  🔧 修复alarms表缺少alarm_type_name列的问题...")
            fix_database_schema()
        elif "模块导入失败" in error:
            print(f"  🔧 修复模块导入问题: {error}")
            # 这里可以添加具体的模块修复逻辑


def fix_database_schema():
    """修复数据库表结构"""
    try:
        from scada_app.core.data_manager import DataManager
        dm = DataManager()
        
        conn = dm._get_connection()
        cursor = conn.cursor()
        
        # 检查并修复alarms表结构
        cursor.execute("PRAGMA table_info(alarms)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'alarm_type_name' not in columns:
            print("    ➕ 为alarms表添加alarm_type_name列")
            cursor.execute("ALTER TABLE alarms ADD COLUMN alarm_type_name TEXT")
            conn.commit()
        
        dm._return_connection(conn)
        print("    ✅ 数据库表结构修复完成")
        
    except Exception as e:
        print(f"    ❌ 数据库修复失败: {e}")


if __name__ == "__main__":
    print("🤖 SCADA系统自动测试系统")
    print("=" * 60)
    
    success = run_auto_test()
    
    if success:
        print("\n🎯 自动测试完成，系统运行正常！")
        sys.exit(0)
    else:
        print("\n⚠️  自动测试完成，发现需要手动修复的问题")
        sys.exit(1)