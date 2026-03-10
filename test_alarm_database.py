"""
测试报警保存到数据库的功能
"""
import sqlite3
from datetime import datetime
from scada_app.core.data_manager import DataManager

def test_alarm_database():
    """测试报警数据库功能"""
    print("=== 测试报警数据库功能 ===")
    
    # 初始化数据管理器
    data_manager = DataManager()
    
    # 先检查数据库表结构
    conn = data_manager._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(alarms)")
        columns = cursor.fetchall()
        
        print("\n数据库alarms表结构:")
        for col in columns:
            print(f"  列 {col[0]}: {col[1]} ({col[2]})")
            
        # 检查是否有alarm_type_name列
        has_alarm_type_name = any(col[1] == 'alarm_type_name' for col in columns)
        print(f"\n是否有alarm_type_name列: {has_alarm_type_name}")
        
        if not has_alarm_type_name:
            print("需要更新数据库表结构...")
            # 删除旧表并重新创建
            cursor.execute("DROP TABLE IF EXISTS alarms")
            cursor.execute('''
                CREATE TABLE alarms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_name TEXT,
                    alarm_type TEXT,
                    message TEXT,
                    active BOOLEAN,
                    acknowledged BOOLEAN,
                    priority TEXT,
                    alarm_type_name TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            print("数据库表结构已更新")
            
    finally:
        data_manager._return_connection(conn)
    
    # 测试触发报警
    print("\n触发测试报警...")
    data_manager.raise_alarm(
        tag_name="test_tag",
        alarm_type="状态变化_假变真",
        message="测试报警消息",
        alarm_type_name="危急"
    )
    
    # 检查数据库中的报警记录
    conn = data_manager._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM alarms ORDER BY id DESC LIMIT 5')
        alarms = cursor.fetchall()
        
        print(f"\n数据库中的报警记录数量: {len(alarms)}")
        
        if alarms:
            print("\n最近5条报警记录:")
            for alarm in alarms:
                print(f"  ID: {alarm[0]}")
                print(f"  标签: {alarm[1]}")
                print(f"  报警类型: {alarm[2]}")
                print(f"  消息: {alarm[3]}")
                print(f"  活动: {alarm[4]}")
                print(f"  已确认: {alarm[5]}")
                print(f"  报警类型名称: {alarm[6]}")
                print(f"  时间: {alarm[7]}")
                print("  ---")
        else:
            print("数据库中没有报警记录")
            
    finally:
        data_manager._return_connection(conn)
    
    # 测试报警确认功能
    if alarms:
        latest_alarm_id = alarms[0][0]
        print(f"\n确认报警 ID: {latest_alarm_id}")
        success = data_manager.acknowledge_alarm(latest_alarm_id)
        print(f"报警确认结果: {'成功' if success else '失败'}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_alarm_database()