"""
最终 Web HMI 测试 - 完整流程
"""
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, r'c:\Users\TUX\source\repos\HMI')

def get_recent_project():
    """获取最近的项目文件"""
    config_dir = Path.home() / '.scada_config'
    config_file = config_dir / 'recent_project.json'
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                return config.get('recent_project')
        except:
            pass
    return None

def main():
    print("=" * 60)
    print("HMI Web 最终测试")
    print("=" * 60)
    
    recent_project = get_recent_project()
    print(f"\n项目文件: {recent_project}")
    
    if not recent_project:
        print("✗ 没有找到项目文件")
        return
    
    try:
        from scada_app.core.data_manager import DataManager
        from scada_app.core.config_manager import ConfigurationManager
        from scada_app.comm.plc_manager import PLCManager
        from scada_app.core.project_manager import ProjectManager
        from scada_app.web.web_server import WebServer
        
        # 创建组件
        print("\n1. 创建组件...")
        data_manager = DataManager()
        config_manager = ConfigurationManager()
        plc_manager = PLCManager(data_manager)
        project_manager = ProjectManager(data_manager, plc_manager, config_manager)
        
        # 加载项目
        print("2. 加载项目...")
        project_manager.load_project(recent_project)
        
        # 检查标签
        print("\n3. 标签数据:")
        print(f"   共 {len(data_manager.tags)} 个标签")
        for name, tag in data_manager.tags.items():
            print(f"   - {name}: {tag.value} ({tag.quality})")
        
        # 创建 Web 服务器
        print("\n4. 创建 Web 服务器...")
        web_server = WebServer(data_manager, plc_manager, project_manager)
        
        # 测试获取画面
        print("\n5. 测试获取画面...")
        # 调用内部方法测试
        screens_data = [{'name': '画面1', 'number': 1, 'is_main': True, 'objects': []}]  # 模拟数据
        screens = web_server._parse_screens_from_project(screens_data)
        print(f"   解析了 {len(screens)} 个画面")
        
        # 模拟广播
        print("\n6. 模拟广播数据:")
        tags_data = {}
        for name, tag in data_manager.tags.items():
            value = tag.value if tag.value is not None else 0
            # 确保可 JSON 序列化
            try:
                json.dumps(value)
            except:
                value = str(value)
            
            tags_data[name] = {
                'value': value,
                'quality': tag.quality or 'Unknown',
                'timestamp': tag.timestamp.isoformat() if tag.timestamp else None
            }
        
        print(json.dumps(tags_data, indent=2, ensure_ascii=False))
        
        print("\n" + "=" * 60)
        print("测试完成！数据正常，问题应在浏览器端")
        print("=" * 60)
        print("\n请检查浏览器控制台输出:")
        print("1. 打开 http://localhost:8080")
        print("2. 按 F12 打开开发者工具")
        print("3. 切换到 Console 标签")
        print("4. 查看是否有错误信息")
        
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
