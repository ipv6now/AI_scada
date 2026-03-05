# 异步通信使用指南

## 概述

SCADA 系统现在支持异步通信，使用 asyncio + 线程池方案，避免阻塞主线程。

## 架构

```
主线程 (Qt Event Loop)
    ↓
异步协调器 (AsyncCommCoordinator)
    ↓
线程池 (ThreadPoolExecutor)
    ↓
同步通信库 (pymodbus, snap7)
```

## 使用方法

### 1. Modbus 异步读写

```python
import asyncio
from scada_app.comm.modbus_handler import ModbusHandler, async_read_tag, async_write_tag

async def modbus_example():
    # 创建 Modbus 连接
    handler = ModbusHandler(address="192.168.0.1", port=502)
    handler.connect()
    
    # 异步读取
    value = await async_read_tag(handler, "40001")
    print(f"Value: {value}")
    
    # 异步写入
    success = await async_write_tag(handler, "40001", 123)
    print(f"Write success: {success}")
    
    handler.disconnect()

# 运行异步函数
asyncio.run(modbus_example())
```

### 2. S7 异步读写

```python
import asyncio
from scada_app.comm.s7_driver import S7Driver, S7ConnectionConfig, async_read_tag, async_write_tag

async def s7_example():
    # 创建 S7 连接配置
    config = S7ConnectionConfig(
        ip_address="192.168.0.2",
        rack=0,
        slot=1,
        connection_name="S7_Connection"
    )
    
    # 创建驱动
    driver = S7Driver(config)
    driver.connect()
    
    # 异步读取
    value = await async_read_tag(driver, "DB1.DBX0.0", "BOOL")
    print(f"Value: {value}")
    
    # 异步写入
    success = await async_write_tag(driver, "DB1.DBX0.0", True, "BOOL")
    print(f"Write success: {success}")
    
    driver.disconnect()

# 运行异步函数
asyncio.run(s7_example())
```

### 3. 在现有代码中使用

如果不想修改现有代码，可以继续使用同步方法。异步方法是可选的。

```python
# 同步方式（仍然支持）
handler = ModbusHandler(address="192.168.0.1", port=502)
handler.connect()
value = handler.read_tag("40001")  # 阻塞调用
handler.disconnect()

# 异步方式（推荐用于新代码）
async def read_value():
    handler = ModbusHandler(address="192.168.0.1", port=502)
    handler.connect()
    value = await async_read_tag(handler, "40001")  # 非阻塞调用
    handler.disconnect()
    return value
```

## 性能优化

### 1. 使用线程池

所有通信操作使用共享线程池，避免频繁创建/销毁线程：

```python
# Modbus
executor = ModbusHandler.get_executor()

# S7
executor = S7Driver.get_executor()
```

### 2. 批量操作

使用批量读取减少通信次数：

```python
# Modbus
values = handler.read_tags_batch(["40001", "40002", "40003"])

# S7
values = driver.read_tags_batch(["DB1.DBX0.0", "DB1.DBX1.0", "DB1.DBX2.0"])
```

## 注意事项

1. **异步函数必须在事件循环中运行**
   - 使用 `asyncio.run()` 运行顶层协程
   - 或在已有事件循环中使用 `await`

2. **线程安全**
   - 所有通信操作都是线程安全的
   - 可以在多个线程中并发调用

3. **错误处理**
   - 异步操作会抛出与同步操作相同的异常
   - 使用 try/except 捕获错误

```python
async def safe_read():
    try:
        value = await async_read_tag(handler, "40001")
        return value
    except Exception as e:
        print(f"Read error: {e}")
        return None
```

4. **资源清理**
   - 使用完毕后记得断开连接
   - 关闭应用时停止异步协调器

```python
# 停止异步协调器
async_comm_coordinator.stop()
```

## 迁移指南

### 从同步迁移到异步

1. **识别通信瓶颈**
   - 使用日志或性能分析工具
   - 找出耗时的通信操作

2. **创建异步包装函数**
   - 使用 `async_read_tag` 替代 `read_tag`
   - 使用 `async_write_tag` 替代 `write_tag`

3. **更新调用代码**
   - 将同步调用改为 `await` 调用
   - 确保在事件循环中运行

4. **测试**
   - 验证功能正确性
   - 检查性能提升

## 故障排除

### 问题：异步操作卡住

**原因：** 事件循环未运行或阻塞

**解决方案：**
- 确保在事件循环中运行异步代码
- 避免在异步函数中使用阻塞调用

### 问题：性能没有提升

**原因：** 通信操作本身不是瓶颈

**解决方案：**
- 检查是否是网络延迟或 PLC 响应慢
- 优化通信频率
- 使用批量读取

### 问题：多线程冲突

**原因：** 同时从多个线程访问同一资源

**解决方案：**
- 使用锁保护共享资源
- 使用队列进行线程间通信

## 总结

异步通信方案提供了以下优势：

1. ✅ **非阻塞** - 通信操作不阻塞主线程
2. ✅ **高并发** - 可以同时处理多个通信请求
3. ✅ **兼容性好** - 可以继续使用现有的同步库
4. ✅ **易于集成** - 与 Qt 事件循环无缝集成

推荐在新代码中使用异步通信，现有代码可以继续使用同步方式。
