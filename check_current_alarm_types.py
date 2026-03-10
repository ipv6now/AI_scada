"""
检查当前项目中的报警类型配置
"""
from scada_app.core.alarm_type_manager import alarm_type_manager

def check_current_alarm_types():
    """检查当前报警类型配置"""
    print("=== 当前报警类型配置 ===")
    
    print(f"报警类型数量: {len(alarm_type_manager.alarm_types)}")
    
    for name, alarm_type in alarm_type_manager.alarm_types.items():
        print(f"\n名称: {name}")
        print(f"显示名称: {alarm_type.display_name}")
        print(f"前景色: {alarm_type.foreground_color}")
        print(f"背景色: {alarm_type.background_color}")
        print(f"描述: {alarm_type.description}")
        print(f"启用: {alarm_type.enabled}")
    
    print(f"\n启用的报警类型名称: {alarm_type_manager.get_alarm_type_names()}")

if __name__ == "__main__":
    check_current_alarm_types()