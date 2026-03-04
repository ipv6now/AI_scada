"""
Web HMI 调试脚本 - 使用实际 SCADA 组件 v3
"""
import sys
import time
import json

sys.path.insert(0, r'c:\Users\TUX\source\repos\HMI')

def main():
    print("=" * 60)
    print("HMI Web 调试工具 v3")
    print("=" * 60)
    
    try:
        # 导入实际运行的组件
        from scada_app.core.data_manager import DataManager
        from scada_app.core.config_manager import ConfigurationManager
        from scada_app.comm.plc_manager import PLCManager
        from scada_app.core.project_manager import ProjectManager
        from scada_app.web.web_server import WebServer
        
        # 创建组件
        print("\n1. 创建核心组件...")
        data_manager = DataManager()
        config_manager = ConfigurationManager()
        plc_manager = PLCManager(data_manager)
        project_manager = ProjectManager(data_manager, plc_manager, config_manager)
        
        print(f"   ✓ DataManager 创建成功")
        print(f"   ✓ ConfigurationManager 创建成功")
        print(f"   ✓ PLCManager 创建成功")
        print(f"   ✓ ProjectManager 创建成功")
        
        # 加载项目
        print("\n2. 加载项目...")
        project_manager.load_project()
        print("   ✓ 项目加载完成")
        
        # 检查标签
        print("\n3. 检查数据管理器标签...")
        if hasattr(data_manager, 'tags'):
            tag_count = len(data_manager.tags)
            print(f"   数据管理器中有 {tag_count} 个标签")
            
            if tag_count > 0:
                print("\n   标签列表:")
                for name, tag in list(data_manager.tags.items())[:10]:
                    print(f"     - {name}: value={tag.value}, quality={tag.quality}")
            else:
                print("   没有标签")
        
        # 检查配置管理器标签
        print("\n4. 检查配置管理器标签...")
        if hasattr(config_manager, 'tags'):
            config_tags = config_manager.tags
            print(f"   配置管理器中有 {len(config_tags)} 个标签")
            for tag in config_tags[:5]:
                print(f"     - {tag}")
        else:
            print("   配置管理器没有 tags 属性")
        
        # 检查画面
        print("\n5. 检查画面...")
        screens = []
        if hasattr(project_manager, 'hmi_designer') and project_manager.hmi_designer:
            if hasattr(project_manager.hmi_designer, 'screens'):
                screens = project_manager.hmi_designer.screens
                print(f"   有 {len(screens)} 个画面")
                
                for screen in screens:
                    print(f"\n   画面: {screen.name}")
                    if hasattr(screen, 'objects'):
                        print(f"   对象数: {len(screen.objects)}")
                        for obj in screen.objects:
                            print(f"     - {obj.name} ({obj.type})")
                            if hasattr(obj, 'variables') and obj.variables:
                                for var in obj.variables:
                                    print(f"       变量: {var.name}")
        else:
            print("   没有 HMI 设计器")
        
        # 创建 Web 服务器
        print("\n6. 创建 Web 服务器...")
        web_server = WebServer(data_manager, plc_manager, project_manager)
        print(f"   ✓ Web 服务器创建成功")
        
        # 模拟广播数据
        print("\n7. 模拟标签广播...")
        tags_data = {}
        if hasattr(data_manager, 'tags'):
            for name, tag in data_manager.tags.items():
                value = tag.value if tag.value is not None else 0
                tags_data[name] = {
                    'value': value,
                    'quality': tag.quality if tag.quality else 'Unknown',
                    'timestamp': tag.timestamp.isoformat() if tag.timestamp else None
                }
        
        print(f"   广播数据 ({len(tags_data)} 个标签):")
        if tags_data:
            print(json.dumps(tags_data, indent=2, ensure_ascii=False))
        else:
            print("   (空)")
        
        # 检查画面变量绑定
        print("\n8. 检查画面变量绑定...")
        if screens and tags_data:
            for screen in screens:
                for obj in screen.objects:
                    if hasattr(obj, 'variables') and obj.variables:
                        for var in obj.variables:
                            var_name = var.name
                            if var_name in tags_data:
                                print(f"   ✓ {obj.name} 的变量 '{var_name}' 在标签列表中")
                            else:
                                print(f"   ✗ {obj.name} 的变量 '{var_name}' 不在标签列表中!")
        elif not tags_data:
            print("   标签数据为空，无法检查绑定")
        
        print("\n" + "=" * 60)
        print("调试完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
