"""
测试报警类型保存到项目文件的功能
"""
import json
from pathlib import Path
from scada_app.core.alarm_type_manager import alarm_type_manager
from scada_app.core.project_manager import ProjectManager
from scada_app.core.data_manager import DataManager
from scada_app.comm.plc_manager import PLCManager
from scada_app.core.config_manager import ConfigurationManager

def test_alarm_type_saving():
    """测试报警类型保存功能"""
    print("=== 测试报警类型保存功能 ===")
    
    # 初始化必要的组件
    data_manager = DataManager()
    plc_manager = PLCManager()
    config_manager = ConfigurationManager(data_manager, plc_manager)
    
    # 创建项目管理器
    project_manager = ProjectManager(data_manager, plc_manager, config_manager)
    
    # 添加一些自定义报警类型
    from scada_app.core.alarm_type_manager import AlarmType
    
    # 添加一个自定义报警类型
    custom_type = AlarmType(
        name="custom_warning",
        display_name="自定义警告",
        foreground_color="#FFFFFF",
        background_color="#FFA500",
        description="自定义警告类型",
        enabled=True
    )
    alarm_type_manager.add_alarm_type(custom_type)
    
    print("添加的自定义报警类型:")
    for name, alarm_type in alarm_type_manager.alarm_types.items():
        print(f"  - {name}: {alarm_type.display_name}")
    
    # 测试导出功能
    alarm_types_data = project_manager._export_alarm_types()
    print(f"\n导出的报警类型数据: {len(alarm_types_data)} 个类型")
    for name, data in alarm_types_data.items():
        print(f"  - {name}: {data}")
    
    # 测试保存项目
    test_project_file = "test_alarm_types.scada"
    
    # 添加一些测试报警规则
    config_manager.alarm_rules = [
        {
            'tag_name': 'test_tag',
            'alarm_type': '状态变化',
            'condition': '假变真',
            'threshold': 0.0,
            'message': '测试报警',
            'enabled': True,
            'alarm_type_name': '自定义警告',  # 使用自定义报警类型
            'bit_offset': None,
            'alarm_id': 1
        }
    ]
    
    # 保存项目
    success = project_manager.save_project(test_project_file)
    print(f"\n保存项目结果: {'成功' if success else '失败'}")
    
    if success:
        # 读取保存的项目文件
        with open(test_project_file, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
        
        print(f"\n项目文件版本: {project_data['metadata']['version']}")
        
        # 检查是否包含报警类型配置
        if 'alarm_types' in project_data:
            print(f"项目文件中包含报警类型配置: {len(project_data['alarm_types'])} 个类型")
            for name, data in project_data['alarm_types'].items():
                print(f"  - {name}: {data}")
        else:
            print("项目文件中没有报警类型配置")
        
        # 测试加载功能
        print("\n=== 测试报警类型加载功能 ===")
        
        # 清空报警类型管理器
        alarm_type_manager.alarm_types.clear()
        alarm_type_manager._load_default_types()
        
        print("加载前的报警类型:")
        for name, alarm_type in alarm_type_manager.alarm_types.items():
            print(f"  - {name}: {alarm_type.display_name}")
        
        # 加载项目
        load_success = project_manager.load_project(test_project_file)
        print(f"加载项目结果: {'成功' if load_success else '失败'}")
        
        print("\n加载后的报警类型:")
        for name, alarm_type in alarm_type_manager.alarm_types.items():
            print(f"  - {name}: {alarm_type.display_name}")
        
        # 清理测试文件
        if Path(test_project_file).exists():
            Path(test_project_file).unlink()
            print(f"\n已删除测试文件: {test_project_file}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_alarm_type_saving()