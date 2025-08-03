from .base_settings import BaseSettings

class OBISettings(BaseSettings):
    """OBI (Order Book Imbalance) 전략 설정"""
    
    # OBI 전략 파라미터
    DEPTH_LEVEL: int = 5
    OBI_LONG: float = 0.70
    OBI_SHORT: float = 0.30
    TP_PCT: float = 0.0005         # 0.05% 익절
    SL_PCT: float = 0.0005         # 0.05% 손절
    ORDER_TTL: float = 2.0         # 주문 유효시간 (초)