from typing import Optional
from strategy.common.base_strategy import BaseStrategy
from config.settings import settings


def calc_obi(depth_snap: dict, level: int):
    bids = depth_snap["b"][:level]
    asks = depth_snap["a"][:level]
    bid_val = sum(float(p)*float(q) for p, q in bids)
    ask_val = sum(float(p)*float(q) for p, q in asks)
    return bid_val / (bid_val + ask_val)


class OBIScalperStrategy(BaseStrategy):
    """
    Order Book Imbalance (OBI) 스캘핑 전략
    
    호가창의 매수/매도 물량 불균형을 이용하여 단기 가격 움직임을 예측하는 전략입니다.
    """
    
    def __init__(self):
        self.current_depth = None
    
    def signal(self) -> Optional[str]:
        """거래 신호 생성"""
        if not self.is_ready():
            return None
            
        obi = calc_obi(self.current_depth, settings.DEPTH_LEVEL)
        if obi >= settings.OBI_LONG:
            return "LONG"
        elif obi <= settings.OBI_SHORT:
            return "SHORT"
        return None
    
    def is_ready(self) -> bool:
        """전략이 신호 생성 준비가 되었는지 확인"""
        return self.current_depth is not None
    
    def get_indicator_data(self) -> dict:
        """현재 지표 데이터 반환"""
        if not self.current_depth:
            return {"obi": None}
        
        obi = calc_obi(self.current_depth, settings.DEPTH_LEVEL)
        return {
            "obi": obi,
            "obi_long_threshold": settings.OBI_LONG,
            "obi_short_threshold": settings.OBI_SHORT
        }
    
    def update_depth(self, depth_snap: dict):
        """
        새로운 호가창 데이터로 전략 업데이트
        """
        self.current_depth = depth_snap