import re

with open('README.md', 'r', encoding='utf-8') as f:
    text = f.read()

new_text = """## 欺骗检测功能

NavLib 实现了两种先进的GNSS欺骗信号检测算法，并全面支持多系统（GPS, GLONASS, Galileo, BDS 等）。

### 使用方法

通过修改配置文件中的以下参数开启欺骗检测：

```ini
# 欺骗检测器选项 (0:关闭, 1:窗口化统计检测WS, 2:窗口化新息检测WI)
spoofing-detector = 2

# 欺骗检测输出选项 (0:关闭, 1:输出WS统计量, 2:输出WI统计量,需与上面对应)
out-spoofing = 2

# 窗口大小设置 (推荐范围1~10，最大支持10)
# windowed_size = 10 
```

注意：支持多系统欺骗检测时可以在定位参数中开启所有需要的导航系统星座，比如 `pos1-navsys=63`（所有系统）。当前欺骗检测在紧组合模式单频处理（`pos1-posmode=ins-tightly-coupled`）下生效。

### 输出结果查看

开启欺骗检测并设置输出选项后，运行结果的 `.txt` 后缀输出文件中将会追加欺骗检测的对应统计量（WS或WI值）。

用户可以基于卡方分布的阈值判断是否发生欺骗：
- 提取追加输出对应列的统计量数值。
- 根据各历元的跟踪卫星数量（或自由度），计算卡方分布置信区间（例如99%或99.9%）。
- 若统计量显著超过卡方分布判定阈值，则指示可能出现欺骗。

"""

text = re.sub(r'## 欺骗检测功能\n.*?## 示例数据', new_text + '## 示例数据', text, flags=re.DOTALL)

with open('README.md', 'w', encoding='utf-8') as f:
    f.write(text)
