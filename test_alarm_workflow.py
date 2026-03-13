"""报警测试脚本"""
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scada_app.core.data_manager import DataManager
from scada_app.core.alarm_buffer import AlarmBuffer, AlarmBufferType
from scada_app.core.system_service_manager import AlarmStatus

def test_alarm_workflow():
    """测试报警工作流程"""
    print("=== 开始测试报警工作流程 ===")
    
    # 初始化
    data_manager = DataManager()
    alarm_buffer = AlarmBuffer()
    
    # 模拟报警ID
    alarm_id = "1001"
    tag_name = "TEST_TAG"
    alarm_type = "LIMIT_HIGH"
    alarm_type_name = "高"
    message = "测试报警消息"
    
    print(f"\n1. 报警触发")
    print(f"   报警ID: {alarm_id}")
    print(f"   标签: {tag_name}")
    print(f"   类型: {alarm_type}")
    print(f"   消息: {message}")
    
    # 插入活动记录
    data_manager.raise_alarm(tag_name, alarm_type, message, alarm_type_name, alarm_id)
    
    # 添加到报警缓冲区
    from scada_app.core.alarm_buffer import AlarmBufferEntry
    entry = AlarmBufferEntry(
        alarm_id=alarm_id,
        tag_name=tag_name,
        alarm_type=alarm_type,
        alarm_type_name=alarm_type_name,
        message=message,
        timestamp=datetime.now(),
        status='活动',
        buffer_type=AlarmBufferType.ANALOG,
        priority=2
    )
    alarm_buffer.add_alarm(entry)
    
    # 检查报警缓冲区
    buffer_entry = alarm_buffer.get_alarm_by_id(alarm_id)
    print(f"   报警缓冲区状态: {buffer_entry.status if buffer_entry else 'None'}")
    print(f"   报警缓冲区确认时间: {buffer_entry.acknowledge_time if buffer_entry else 'None'}")
    print(f"   报警缓冲区恢复时间: {buffer_entry.recover_time if buffer_entry else 'None'}")
    
    # 检查数据库记录
    conn = data_manager._get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, tag_name, alarm_type, message, active, acknowledged, 
               priority, alarm_type_name, timestamp, alarm_id, recover_time, 
               acknowledge_time, acknowledged_by
        FROM alarms
        WHERE alarm_id = ?
        ORDER BY timestamp DESC
    ''', (alarm_id,))
    records = cursor.fetchall()
    print(f"   数据库记录数: {len(records)}")
    for i, record in enumerate(records):
        print(f"   记录{i+1}: active={record[4]}, acknowledged={record[5]}, recover_time={record[10]}, acknowledge_time={record[11]}")
    data_manager._return_connection(conn)
    
    print(f"\n2. 报警确认")
    acknowledged_by = "test_user"
    
    # 确认报警缓冲区
    alarm_buffer.acknowledge_alarm(alarm_id, acknowledged_by)
    
    # 检查报警缓冲区
    buffer_entry = alarm_buffer.get_alarm_by_id(alarm_id)
    print(f"   报警缓冲区状态: {buffer_entry.status if buffer_entry else 'None'}")
    print(f"   报警缓冲区确认时间: {buffer_entry.acknowledge_time if buffer_entry else 'None'}")
    print(f"   报警缓冲区恢复时间: {buffer_entry.recover_time if buffer_entry else 'None'}")
    
    # 从报警缓冲区获取确认时间
    buffer_acknowledge_time = buffer_entry.acknowledge_time if buffer_entry else None
    print(f"   从缓冲区获取的确认时间: {buffer_acknowledge_time}")
    
    # 插入确认记录到数据库
    data_manager.acknowledge_alarm(alarm_id, acknowledged_by, buffer_acknowledge_time)
    
    # 检查数据库记录
    conn = data_manager._get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, tag_name, alarm_type, message, active, acknowledged, 
               priority, alarm_type_name, timestamp, alarm_id, recover_time, 
               acknowledge_time, acknowledged_by
        FROM alarms
        WHERE alarm_id = ?
        ORDER BY timestamp DESC
    ''', (alarm_id,))
    records = cursor.fetchall()
    print(f"   数据库记录数: {len(records)}")
    for i, record in enumerate(records):
        print(f"   记录{i+1}: active={record[4]}, acknowledged={record[5]}, recover_time={record[10]}, acknowledge_time={record[11]}")
    data_manager._return_connection(conn)
    
    print(f"\n3. 报警恢复")
    
    # 恢复报警缓冲区
    alarm_buffer.recover_alarm(alarm_id)
    
    # 检查报警缓冲区
    buffer_entry = alarm_buffer.get_alarm_by_id(alarm_id)
    print(f"   报警缓冲区状态: {buffer_entry.status if buffer_entry else 'None'}")
    print(f"   报警缓冲区确认时间: {buffer_entry.acknowledge_time if buffer_entry else 'None'}")
    print(f"   报警缓冲区恢复时间: {buffer_entry.recover_time if buffer_entry else 'None'}")
    
    # 从报警缓冲区获取恢复时间
    buffer_recover_time = buffer_entry.recover_time if buffer_entry else None
    print(f"   从缓冲区获取的恢复时间: {buffer_recover_time}")
    
    # 插入恢复记录到数据库
    data_manager.recover_alarm(alarm_id, buffer_recover_time)
    
    # 检查数据库记录
    conn = data_manager._get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, tag_name, alarm_type, message, active, acknowledged, 
               priority, alarm_type_name, timestamp, alarm_id, recover_time, 
               acknowledge_time, acknowledged_by
        FROM alarms
        WHERE alarm_id = ?
        ORDER BY timestamp DESC
    ''', (alarm_id,))
    records = cursor.fetchall()
    print(f"   数据库记录数: {len(records)}")
    for i, record in enumerate(records):
        print(f"   记录{i+1}: active={record[4]}, acknowledged={record[5]}, recover_time={record[10]}, acknowledge_time={record[11]}")
    data_manager._return_connection(conn)
    
    print(f"\n4. 最终数据库记录")
    conn = data_manager._get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, tag_name, alarm_type, message, active, acknowledged, 
               priority, alarm_type_name, timestamp, alarm_id, recover_time, 
               acknowledge_time, acknowledged_by
        FROM alarms
        WHERE alarm_id = ?
        ORDER BY timestamp ASC
    ''', (alarm_id,))
    records = cursor.fetchall()
    print(f"   总记录数: {len(records)}")
    for i, record in enumerate(records):
        status = "活动" if record[4] else ("已确认" if record[5] else "已恢复")
        print(f"   记录{i+1}: status={status}, timestamp={record[8]}, recover_time={record[10]}, acknowledge_time={record[11]}")
    data_manager._return_connection(conn)
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_alarm_workflow()