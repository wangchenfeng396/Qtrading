# 新增策略开发指南

Qtrading 系统采用了插件化架构，允许开发者在不修改核心回测引擎和实盘逻辑的情况下，快速添加并测试新的交易策略。

遵循以下 4 个步骤即可完成一个新策略的开发与部署。

---

## 第一步：创建策略文件
在 `src/strategies/` 目录下创建一个新的 Python 文件，例如 `grid_strategy.py`。

## 第二步：实现策略逻辑
新策略必须继承 `BaseStrategy` 基类，并实现以下三个核心方法。

### 策略模板示例：
```python
from .base import BaseStrategy
import indicators # 引用通用指标库
import pandas as pd

class GridStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        # 初始化您的自定义参数
        self.my_param = 10 

    def calculate_indicators(self, df):
        """
        【回测专用】在大表上预计算指标
        """
        df = df.copy()
        df['my_ema'] = indicators.calculate_ema(df['close'], self.my_param)
        return df

    def check_signal(self, row, prev_row=None):
        """
        【回测专用】逐行判断信号
        Returns: 'LONG', 'SHORT' 或 None
        """
        if row['close'] > row['my_ema']:
            return 'LONG'
        return None

    def analyze_live(self, df_1h, df_15m, df_5m):
        """
        【实盘/模拟专用】处理实时获取的多周期数据
        Returns: 符合规范的字典
        """
        # 1. 计算实时指标
        df_5m['my_ema'] = indicators.calculate_ema(df_5m['close'], self.my_param)
        
        # 2. 获取最新值
        latest = df_5m.iloc[-1]
        
        # 3. 逻辑判断
        signal = 'LONG' if latest['close'] > latest['my_ema'] else None
        
        return {
            'signal': signal,
            'price': latest['close'],
            'atr': 100.0, # 如果不使用 ATR 止损可传固定值
            'indicators': {
                'ema': latest['my_ema'] # 用于日志显示
            }
        }
```

---

## 第三步：在工厂中注册
打开 `src/strategy_factory.py`，导入您的新类并将其添加到选择逻辑中。

```python
from strategies.trend_mean_reversion import TrendMeanReversion
from strategies.grid_strategy import GridStrategy # 1. 导入新策略

def get_strategy(strategy_name):
    if strategy_name == 'TrendMeanReversion':
        return TrendMeanReversion(config)
    elif strategy_name == 'GridStrategy': # 2. 注册名字
        return GridStrategy(config)
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")
```

---

## 第四步：修改配置运行
打开系统主配置文件 `src/config.py`，修改 `ACTIVE_STRATEGY` 变量。

```python
# --- 策略选择 ---
ACTIVE_STRATEGY = 'GridStrategy'  # 填入您在工厂中注册的名字
```

---

## 验证与部署

1.  **回测验证**:
    运行 `python src/main.py`，确认资金曲线和交易记录符合您的逻辑预期。
2.  **模拟盘演练**:
    运行 `python testnet/run_simulation.py`，观察实时信号触发情况。
3.  **正式上线**:
    运行 `./start_live.sh` 开启实盘。
