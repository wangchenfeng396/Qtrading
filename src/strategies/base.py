from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    def __init__(self, config):
        self.config = config

    @abstractmethod
    def calculate_indicators(self, df):
        """
        为回测准备数据：在合并后的 DataFrame 上计算所有指标
        """
        pass

    @abstractmethod
    def check_signal(self, row, prev_row=None):
        """
        回测每一步的信号检查
        Returns: 'LONG', 'SHORT', or None
        """
        pass

    @abstractmethod
    def analyze_live(self, df_1h, df_15m, df_5m):
        """
        实盘/模拟盘的实时分析
        Returns: {
            'signal': 'LONG'/'SHORT'/None,
            'price': float,
            'atr': float,
            'indicators': dict (用于日志显示)
        }
        """
        pass
