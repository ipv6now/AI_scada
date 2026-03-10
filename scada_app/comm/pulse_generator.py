"""
脉冲生成器模块 - 提供多种方式在PLC中生成脉冲信号
"""

import time
import threading
from enum import Enum
from typing import Dict, Callable, Optional


class PulseType(Enum):
    """脉冲类型枚举"""
    SINGLE_SHOT = "single_shot"      # 单次脉冲
    CONTINUOUS = "continuous"        # 连续脉冲
    EDGE_TRIGGERED = "edge_triggered"  # 边沿触发


class PulseGenerator:
    """
    脉冲生成器类 - 在软件端生成精确的脉冲信号
    """
    def __init__(self):
        self.pulse_threads: Dict[str, threading.Thread] = {}
        self.pulse_callbacks: Dict[str, Callable] = {}  # 回调函数存储
        self.active_pulses: Dict[str, bool] = {}       # 活跃脉冲状态
        self.pulse_params: Dict[str, dict] = {}        # 脉冲参数存储

    def generate_pulse(
        self,
        tag_name: str,
        plc_manager,
        pulse_width: float = 0.1,
        pulse_type: PulseType = PulseType.SINGLE_SHOT,
        callback: Optional[Callable] = None
    ):
        """
        生成脉冲信号
        
        Args:
            tag_name: 要触发脉冲的标签名
            plc_manager: PLC管理器实例
            pulse_width: 脉冲宽度（秒）
            pulse_type: 脉冲类型
            callback: 完成后的回调函数
        """
        # 如果已有活跃脉冲，则停止它
        if tag_name in self.active_pulses and self.active_pulses[tag_name]:
            self.stop_pulse(tag_name)
        
        # 存储参数
        self.pulse_params[tag_name] = {
            'pulse_width': pulse_width,
            'pulse_type': pulse_type,
            'callback': callback
        }
        
        # 启动脉冲线程
        thread = threading.Thread(
            target=self._execute_pulse,
            args=(tag_name, plc_manager),
            daemon=True
        )
        self.pulse_threads[tag_name] = thread
        self.active_pulses[tag_name] = True
        thread.start()
    
    def _execute_pulse(self, tag_name: str, plc_manager):
        """执行脉冲生成的核心逻辑"""
        params = self.pulse_params.get(tag_name, {})
        pulse_width = params.get('pulse_width', 0.1)
        pulse_type = params.get('pulse_type', PulseType.SINGLE_SHOT)
        callback = params.get('callback', None)
        
        try:
            # 设置为高电平
            plc_manager.write_tag(tag_name, True)
            print(f"Pulse: Set {tag_name} to True")
            
            # 根据脉冲类型执行不同的行为
            if pulse_type == PulseType.SINGLE_SHOT:
                # 单次脉冲 - 延时后复位
                time.sleep(pulse_width)
                if self.active_pulses.get(tag_name, False):
                    plc_manager.write_tag(tag_name, False)
                    print(f"Pulse: Set {tag_name} to False")
                    
            elif pulse_type == PulseType.CONTINUOUS:
                # 连续脉冲 - 持续循环直到被停止
                while self.active_pulses.get(tag_name, False):
                    time.sleep(pulse_width)
                    if self.active_pulses.get(tag_name, False):
                        plc_manager.write_tag(tag_name, False)
                        print(f"Pulse: Set {tag_name} to False")
                        time.sleep(pulse_width)
                        if self.active_pulses.get(tag_name, False):
                            plc_manager.write_tag(tag_name, True)
                            print(f"Pulse: Set {tag_name} to True")
                            
        except Exception as e:
            print(f"Error in pulse generation for {tag_name}: {e}")
        finally:
            # 清理状态
            self.active_pulses[tag_name] = False
            if callback:
                callback()
    
    def stop_pulse(self, tag_name: str):
        """停止指定的脉冲"""
        if tag_name in self.active_pulses:
            self.active_pulses[tag_name] = False
            # 等待线程结束（最多等待1秒）
            if tag_name in self.pulse_threads:
                thread = self.pulse_threads[tag_name]
                if thread.is_alive():
                    thread.join(timeout=1.0)
    
    def stop_all_pulses(self):
        """停止所有脉冲"""
        for tag_name in list(self.active_pulses.keys()):
            self.stop_pulse(tag_name)


# 创建全局脉冲生成器实例
pulse_generator = PulseGenerator()


def create_momentary_pulse(tag_name: str, plc_manager, pulse_width: float = 0.1):
    """
    创建点动脉冲 - 专门用于替代传统点动机制
    
    Args:
        tag_name: 要触发脉冲的标签名
        plc_manager: PLC管理器实例
        pulse_width: 脉冲宽度（秒）
    """
    print(f"Creating momentary pulse for {tag_name} with width {pulse_width}s")
    pulse_generator.generate_pulse(
        tag_name=tag_name,
        plc_manager=plc_manager,
        pulse_width=pulse_width,
        pulse_type=PulseType.SINGLE_SHOT
    )


def create_edge_triggered_pulse(
    trigger_tag: str,
    target_tag: str,
    plc_manager,
    pulse_width: float = 0.1
):
    """
    创建边沿触发脉冲 - 当触发标签从False变为True时产生脉冲
    
    Args:
        trigger_tag: 触发标签
        target_tag: 目标脉冲标签
        plc_manager: PLC管理器实例
        pulse_width: 脉冲宽度（秒）
    """
    def edge_detector():
        # 这里可以实现边沿检测逻辑
        pass
    
    # 监视触发标签的变化
    pass


if __name__ == "__main__":
    # 测试脉冲生成器
    print("Testing Pulse Generator...")
    
    # 模拟PLC管理器
    class MockPLCManager:
        def __init__(self):
            self.tags = {}
        
        def write_tag(self, tag_name, value, bit_offset=None):
            self.tags[tag_name] = value
            print(f"MockPLC: Writing {tag_name} = {value}, bit_offset={bit_offset}")
    
    plc = MockPLCManager()
    
    # 测试单次脉冲
    print("\n--- Testing Single Shot Pulse ---")
    create_momentary_pulse("test_bool_1", plc, 0.5)
    
    # 等待脉冲完成
    time.sleep(1)
    
    print("\n--- Testing Continuous Pulse ---")
    # 测试连续脉冲
    pulse_generator.generate_pulse(
        "test_bool_2",
        plc,
        pulse_width=0.2,
        pulse_type=PulseType.CONTINUOUS
    )
    
    # 运行一段时间后停止
    time.sleep(1)
    pulse_generator.stop_pulse("test_bool_2")
    
    print("\nPulse Generator test completed!")