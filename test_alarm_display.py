"""
测试报警显示控件功能
"""
import sys
import os
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_alarm_display():
    """测试报警显示控件"""
    print("🔍 测试报警显示控件功能...")
    
    # 测试报警类型管理器
    try:
        from scada_app.core.alarm_type_manager import alarm_type_manager
        print("✅ 报警类型管理器导入成功")
        
        alarm_types = alarm_type_manager.get_alarm_type_names()
        print(f"✅ 报警类型列表: {alarm_types}")
        print(f"✅ 报警类型数量: {len(alarm_types)}")
        
    except Exception as e:
        print(f"❌ 报警类型管理器测试失败: {e}")
        return
    
    # 测试数据管理器
    try:
        from scada_app.core.data_manager import DataManager
        data_manager = DataManager()
        print("✅ 数据管理器初始化成功")
        
        # 添加测试报警数据
        test_alarms = [
            {
                'tag_name': '测试标签1',
                'alarm_type': '状态变化_假变真',
                'message': '测试报警消息1',
                'alarm_type_name': '危急',
                'active': True,
                'acknowledged': False,
                'timestamp': datetime.now()
            },
            {
                'tag_name': '测试标签2', 
                'alarm_type': '限值_高',
                'message': '测试报警消息2',
                'alarm_type_name': '高',
                'active': False,  # 已恢复的报警
                'acknowledged': True,
                'timestamp': datetime.now() - timedelta(minutes=30),  # 30分钟前
                'recovery_time': datetime.now() - timedelta(minutes=5)  # 5分钟前恢复
            }
        ]
        
        data_manager.alarms = test_alarms
        print("✅ 测试报警数据创建成功")
        
    except Exception as e:
        print(f"❌ 数据管理器测试失败: {e}")
        return
    
    # 测试报警显示控件
    try:
        from scada_app.hmi.alarm_display_widget import AlarmDisplayWidget
        
        # 创建控件实例
        alarm_widget = AlarmDisplayWidget(
            data_manager=data_manager,
            system_service_manager=None
        )
        print("✅ 报警显示控件初始化成功")
        
        # 测试配置
        config = alarm_widget.get_config()
        print(f"✅ 控件配置: {config}")
        
        # 测试报警获取
        alarms = alarm_widget.get_current_alarms()
        print(f"✅ 获取到 {len(alarms)} 条报警")
        
        for i, alarm in enumerate(alarms):
            print(f"  报警{i+1}: {alarm['tag_name']} - {alarm['status']} - {alarm['alarm_type_name']}")
        
        # 测试筛选
        filtered = alarm_widget.filter_alarms(alarms)
        print(f"✅ 筛选后报警数量: {len(filtered)}")
        
        # 测试配置界面
        from PyQt5.QtWidgets import QApplication
        app = QApplication(sys.argv)
        
        from scada_app.hmi.alarm_display_widget import AlarmDisplayConfigDialog
        config_dialog = AlarmDisplayConfigDialog(alarm_widget)
        
        config = config_dialog.get_config()
        print(f"✅ 配置对话框配置: {config}")
        
        print("✅ 报警显示控件功能测试完成")
        
    except Exception as e:
        print(f"❌ 报警显示控件测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_alarm_display()