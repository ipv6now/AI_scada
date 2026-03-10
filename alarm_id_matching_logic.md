# 报警ID匹配逻辑详细说明

## 概述

报警监控器需要从系统服务管理器获取的报警状态中，找到对应的报警规则ID，以便在表格中显示正确的报警ID。这个过程涉及复杂的匹配逻辑。

## 数据结构

### 报警状态 (AlarmState)
```python
@dataclass
class AlarmState:
    tag_name: str              # 标签名，如 "MW300"
    alarm_type: str           # 报警类型，如 "状态变化_假变真_bit0"
    status: AlarmStatus       # 状态：ACTIVE, ACKNOWLEDGED, RECOVERED
    alarm_type_name: str      # 报警类型名称，如 "中"
    message: str              # 消息内容，如 "0000"
    first_trigger_time: datetime  # 首次触发时间
    recover_time: datetime    # 恢复时间
```

### 报警规则 (AlarmRule)
```python
@dataclass
class AlarmRule:
    alarm_id: str             # 报警ID，如 "A001"
    tag_name: str            # 标签名，如 "MW300"
    alarm_type: str          # 报警类型，如 "状态变化_假变真"
    message: str             # 消息内容，如 "0000"
    alarm_type_name: str     # 报警类型名称，如 "中"
    # ... 其他属性
```

## 匹配逻辑详解

### 第一步：标签名精确匹配
```python
if rule.tag_name == alarm_state.tag_name:
```
这是最基础的条件，必须完全匹配标签名。

### 第二步：报警类型匹配（支持包含关系）
```python
if rule.alarm_type in alarm_state.alarm_type or alarm_state.alarm_type in rule.alarm_type:
```

由于报警状态和报警规则的报警类型可能略有不同，支持双向包含匹配：

**示例场景**:
- 报警规则: `alarm_type = "状态变化_假变真"`
- 报警状态: `alarm_type = "状态变化_假变真_bit0"`
- 匹配结果: ✅ 成功（规则类型包含在状态类型中）

**示例场景**:
- 报警规则: `alarm_type = "状态变化_假变真_bit0"`
- 报警状态: `alarm_type = "状态变化_假变真"`
- 匹配结果: ✅ 成功（状态类型包含在规则类型中）

### 第三步：消息内容匹配（备用方案）
```python
if rule.tag_name == alarm_state.tag_name and rule.message in alarm_state.message:
```

如果前两步没有找到匹配，尝试使用消息内容匹配：

**示例场景**:
- 报警规则: `message = "0000"`
- 报警状态: `message = "状态变化_假变真_0000"`
- 匹配结果: ✅ 成功（规则消息包含在状态消息中）

## 实际匹配示例

### 示例1：位偏移报警
```
报警规则:
- alarm_id: "A001"
- tag_name: "MW300"
- alarm_type: "状态变化_假变真"
- message: "0000"

报警状态:
- tag_name: "MW300"
- alarm_type: "状态变化_假变真_bit0"
- message: "0000"

匹配过程:
1. 标签名匹配: ✅ MW300 == MW300
2. 报警类型匹配: ✅ "状态变化_假变真" in "状态变化_假变真_bit0"
3. 结果: 匹配成功，alarm_id = "A001"
```

### 示例2：限值报警
```
报警规则:
- alarm_id: "A002"
- tag_name: "温度传感器"
- alarm_type: "限值_高"
- message: "温度过高"

报警状态:
- tag_name: "温度传感器"
- alarm_type: "限值_高"
- message: "温度过高警告"

匹配过程:
1. 标签名匹配: ✅ "温度传感器" == "温度传感器"
2. 报警类型匹配: ✅ "限值_高" == "限值_高"
3. 结果: 匹配成功，alarm_id = "A002"
```

### 示例3：复杂消息匹配
```
报警规则:
- alarm_id: "A003"
- tag_name: "压力传感器"
- alarm_type: "限值_低"
- message: "低压"

报警状态:
- tag_name: "压力传感器"
- alarm_type: "限值_低"
- message: "系统压力过低，请检查"

匹配过程:
1. 标签名匹配: ✅ "压力传感器" == "压力传感器"
2. 报警类型匹配: ✅ "限值_低" == "限值_低"
3. 消息内容匹配: ✅ "低压" in "系统压力过低，请检查"
4. 结果: 匹配成功，alarm_id = "A003"
```

## 常见问题

### 1. 为什么报警ID显示为空？
可能原因：
- 没有配置对应的报警规则
- 标签名不匹配
- 报警类型和消息都不匹配

### 2. 如何调试匹配失败？
可以在代码中添加调试输出：
```python
print(f"尝试匹配: 状态={alarm_state.tag_name}:{alarm_state.alarm_type}:{alarm_state.message}")
for rule in self.system_service_manager.alarm_rules:
    print(f"规则: {rule.alarm_id}:{rule.tag_name}:{rule.alarm_type}:{rule.message}")
    # 检查匹配条件
```

### 3. 匹配性能如何？
- 时间复杂度: O(n×m)，其中n是报警状态数，m是报警规则数
- 对于小规模数据（<1000条）性能良好
- 大规模数据可考虑建立索引优化

## 改进建议

### 1. 添加缓存机制
```python
# 使用字典缓存匹配结果
self._alarm_id_cache = {}

def get_alarm_id_cached(self, alarm_state):
    key = f"{alarm_state.tag_name}:{alarm_state.alarm_type}:{alarm_state.message}"
    if key in self._alarm_id_cache:
        return self._alarm_id_cache[key]
    # ... 执行匹配逻辑 ...
    self._alarm_id_cache[key] = alarm_id
    return alarm_id
```

### 2. 支持模糊匹配
```python
# 支持正则表达式匹配
import re
if re.search(rule.pattern, alarm_state.alarm_type):
    return rule.alarm_id
```

### 3. 添加权重评分
```python
def calculate_match_score(rule, alarm_state):
    score = 0
    if rule.tag_name == alarm_state.tag_name:
        score += 50
    if rule.alarm_type in alarm_state.alarm_type:
        score += 30
    if rule.message in alarm_state.message:
        score += 20
    return score

# 选择最高分的规则
best_rule = max(rules, key=lambda r: calculate_match_score(r, alarm_state))
```