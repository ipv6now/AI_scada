"""
Web HMI 调试脚本
测试 WebSocket 数据流和标签广播
"""
import sys
import time
import json

# 添加项目路径
sys.path.insert(0, r'c:\Users\TUX\source\repos\HMI')

def test_data_manager():
    """测试数据管理器中的标签数据"""
    print("=" * 60)
    print("测试数据管理器")
    print("=" * 60)
    
    try:
        from scada_app.core.data_manager import DataManager
        
        dm = DataManager()
        
        # 检查是否有标签
        if hasattr(dm, 'tags') and dm.tags:
            print(f"✓ 数据管理器中有 {len(dm.tags)} 个标签")
            for name, tag in list(dm.tags.items())[:5]:
                print(f"  - {name}: value={tag.value}, quality={tag.quality}")
        else:
            print("✗ 数据管理器中没有标签")
            
        return dm
    except Exception as e:
        print(f"✗ 数据管理器错误: {e}")
        return None

def test_web_server():
    """测试 Web 服务器"""
    print("\n" + "=" * 60)
    print("测试 Web 服务器")
    print("=" * 60)
    
    try:
        from scada_app.web.web_server import WebServer
        
        ws = WebServer()
        print(f"✓ Web 服务器创建成功")
        print(f"  - 运行状态: {ws.running}")
        print(f"  - 数据管理器: {ws.data_manager}")
        
        return ws
    except Exception as e:
        print(f"✗ Web 服务器错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_tag_broadcast():
    """模拟标签广播"""
    print("\n" + "=" * 60)
    print("测试标签广播数据格式")
    print("=" * 60)
    
    try:
        from scada_app.core.data_manager import DataManager
        
        dm = DataManager()
        
        # 模拟广播数据
        tags_data = {}
        if hasattr(dm, 'tags'):
            for name, tag in dm.tags.items():
                value = tag.value
                if value is None:
                    value = 0
                
                tags_data[name] = {
                    'value': value,
                    'quality': tag.quality if tag.quality else 'Unknown',
                    'timestamp': tag.timestamp.isoformat() if tag.timestamp else None
                }
        
        print(f"✓ 广播数据格式:")
        print(json.dumps(tags_data, indent=2, ensure_ascii=False))
        
        return tags_data
    except Exception as e:
        print(f"✗ 标签广播错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_screen_data():
    """测试画面数据"""
    print("\n" + "=" * 60)
    print("测试画面数据")
    print("=" * 60)
    
    try:
        from scada_app.core.project_manager import ProjectManager
        
        pm = ProjectManager()
        
        # 获取画面
        screens = []
        if hasattr(pm, 'hmi_designer') and pm.hmi_designer:
            if hasattr(pm.hmi_designer, 'screens'):
                screens = pm.hmi_designer.screens
        
        print(f"✓ 找到 {len(screens)} 个画面")
        
        for screen in screens:
            print(f"\n  画面: {screen.name}")
            if hasattr(screen, 'objects'):
                print(f"  对象数: {len(screen.objects)}")
                for obj in screen.objects[:3]:
                    print(f"    - {obj.name} ({obj.type})")
                    if hasattr(obj, 'variables') and obj.variables:
                        var_names = [v.name for v in obj.variables]
                        print(f"      变量: {var_names}")
        
        return screens
    except Exception as e:
        print(f"✗ 画面数据错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_http_api():
    """测试 HTTP API"""
    print("\n" + "=" * 60)
    print("测试 HTTP API")
    print("=" * 60)
    
    try:
        import requests
        
        # 测试画面列表 API
        try:
            response = requests.get('http://127.0.0.1:8080/api/screens', timeout=2)
            print(f"✓ /api/screens 状态: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  响应: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
        except Exception as e:
            print(f"✗ /api/screens 错误: {e}")
        
        # 测试标签列表 API
        try:
            response = requests.get('http://127.0.0.1:8080/api/tags', timeout=2)
            print(f"✓ /api/tags 状态: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  标签数: {len(data.get('tags', []))}")
        except Exception as e:
            print(f"✗ /api/tags 错误: {e}")
            
    except ImportError:
        print("✗ 需要安装 requests: pip install requests")
    except Exception as e:
        print(f"✗ HTTP API 错误: {e}")

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("HMI Web 调试工具")
    print("=" * 60)
    
    # 测试各个组件
    dm = test_data_manager()
    ws = test_web_server()
    tags = test_tag_broadcast()
    screens = test_screen_data()
    test_http_api()
    
    print("\n" + "=" * 60)
    print("调试完成")
    print("=" * 60)
    
    # 总结
    print("\n总结:")
    print(f"  - 数据管理器: {'✓' if dm else '✗'}")
    print(f"  - Web 服务器: {'✓' if ws else '✗'}")
    print(f"  - 标签数据: {'✓' if tags else '✗'}")
    print(f"  - 画面数据: {'✓' if screens else '✗'}")

if __name__ == '__main__':
    main()
