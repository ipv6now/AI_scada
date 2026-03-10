"""
测试报警控件配置对话框显示
"""
import sys
import os
from PyQt5.QtWidgets import QApplication, QDialog

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_config_dialog():
    """测试配置对话框显示"""
    print("🔍 测试报警控件配置对话框...")
    
    # 创建QApplication实例
    app = QApplication(sys.argv)
    
    try:
        from scada_app.hmi.alarm_display_widget import AlarmDisplayConfigDialog
        
        # 创建配置对话框
        dialog = AlarmDisplayConfigDialog()
        
        # 检查对话框内容
        print("✅ 配置对话框创建成功")
        print(f"对话框标题: {dialog.windowTitle()}")
        print(f"对话框尺寸: {dialog.size().width()}x{dialog.size().height()}")
        
        # 检查是否有子控件
        children = dialog.children()
        print(f"子控件数量: {len(children)}")
        
        # 检查布局
        layout = dialog.layout()
        if layout:
            print(f"布局类型: {type(layout).__name__}")
            print(f"布局项数量: {layout.count()}")
            
            # 遍历布局项
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item:
                    widget = item.widget()
                    if widget:
                        print(f"  第{i}项: {type(widget).__name__} - {widget.objectName() or '未命名'}")
        else:
            print("❌ 对话框没有布局")
        
        # 显示对话框
        dialog.show()
        print("✅ 对话框显示成功")
        
        # 运行应用
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"❌ 配置对话框测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_config_dialog()