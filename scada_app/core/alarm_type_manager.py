"""
报警类型管理器 - 管理预定义的报警类型及其颜色配置
"""
from dataclasses import dataclass
from typing import Dict, List
from PyQt5.QtGui import QColor
import json
import os


@dataclass
class AlarmType:
    """报警类型定义"""
    name: str
    display_name: str
    foreground_color: str  # 前景色，十六进制格式
    background_color: str  # 背景色，十六进制格式
    description: str = ""
    enabled: bool = True


class AlarmTypeManager:
    """报警类型管理器"""
    
    def __init__(self):
        self.alarm_types: Dict[str, AlarmType] = {}
        self._default_types_created = False
        self._load_default_types()
    
    def _load_default_types(self):
        """加载默认报警类型"""
        if self._default_types_created:
            return
            
        # 默认报警类型配置
        default_types = [
            AlarmType(
                name="critical",
                display_name="危急",
                foreground_color="#FFFFFF",
                background_color="#FF0000",
                description="紧急危险，需要立即处理"
            ),
            AlarmType(
                name="high",
                display_name="高",
                foreground_color="#000000",
                background_color="#FFA500",
                description="重要报警，需要优先处理"
            ),
            AlarmType(
                name="medium",
                display_name="中",
                foreground_color="#000000",
                background_color="#FFFF00",
                description="一般报警，需要及时处理"
            ),
            AlarmType(
                name="low",
                display_name="低",
                foreground_color="#000000",
                background_color="#C0C0C0",
                description="提示信息，可延迟处理"
            ),
            AlarmType(
                name="info",
                display_name="信息",
                foreground_color="#000000",
                background_color="#87CEEB",
                description="一般信息提示"
            ),
            AlarmType(
                name="warning",
                display_name="警告",
                foreground_color="#000000",
                background_color="#FFD700",
                description="警告信息"
            ),
            AlarmType(
                name="error",
                display_name="错误",
                foreground_color="#FFFFFF",
                background_color="#DC143C",
                description="错误信息"
            )
        ]
        
        for alarm_type in default_types:
            self.alarm_types[alarm_type.name] = alarm_type
        
        self._default_types_created = True
    
    def get_alarm_type(self, name: str) -> AlarmType:
        """获取报警类型"""
        return self.alarm_types.get(name, self.alarm_types.get("medium", None))
    
    def get_all_alarm_types(self) -> List[AlarmType]:
        """获取所有报警类型"""
        return list(self.alarm_types.values())
    
    def get_alarm_type_names(self) -> List[str]:
        """获取所有报警类型名称"""
        return [alarm_type.display_name for alarm_type in self.alarm_types.values() if alarm_type.enabled]
    
    def get_alarm_type_by_display_name(self, display_name: str) -> AlarmType:
        """通过显示名称获取报警类型"""
        for alarm_type in self.alarm_types.values():
            if alarm_type.display_name == display_name:
                return alarm_type
        return self.alarm_types.get("medium", None)
    
    def add_alarm_type(self, alarm_type: AlarmType):
        """添加报警类型"""
        self.alarm_types[alarm_type.name] = alarm_type
    
    def remove_alarm_type(self, name: str):
        """删除报警类型"""
        if name in self.alarm_types and name not in ["critical", "high", "medium", "low"]:
            del self.alarm_types[name]
    
    def update_alarm_type(self, name: str, alarm_type: AlarmType):
        """更新报警类型"""
        if name in self.alarm_types:
            self.alarm_types[name] = alarm_type
    
    def get_qcolor_from_hex(self, hex_color: str) -> QColor:
        """从十六进制颜色字符串转换为QColor"""
        if hex_color.startswith('#'):
            hex_color = hex_color[1:]
        
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return QColor(r, g, b)
        elif len(hex_color) == 8:  # 包含透明度
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            a = int(hex_color[6:8], 16)
            return QColor(r, g, b, a)
        else:
            return QColor(0, 0, 0)  # 默认黑色
    
    def save_to_file(self, file_path: str):
        """保存报警类型配置到文件"""
        data = {}
        for name, alarm_type in self.alarm_types.items():
            data[name] = {
                'display_name': alarm_type.display_name,
                'foreground_color': alarm_type.foreground_color,
                'background_color': alarm_type.background_color,
                'description': alarm_type.description,
                'enabled': alarm_type.enabled
            }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_from_file(self, file_path: str):
        """从文件加载报警类型配置"""
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for name, type_data in data.items():
                alarm_type = AlarmType(
                    name=name,
                    display_name=type_data.get('display_name', name),
                    foreground_color=type_data.get('foreground_color', '#000000'),
                    background_color=type_data.get('background_color', '#FFFFFF'),
                    description=type_data.get('description', ''),
                    enabled=type_data.get('enabled', True)
                )
                self.alarm_types[name] = alarm_type
            
            return True
        except Exception as e:
            print(f"加载报警类型配置失败: {e}")
            return False


# 全局报警类型管理器实例
alarm_type_manager = AlarmTypeManager()