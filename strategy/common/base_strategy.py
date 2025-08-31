from abc import ABC, abstractmethod
from typing import Optional


class BaseStrategy(ABC):
    """
    Base Strategy Class
    
    모든 트레이딩 전략이 구현해야 하는 기본 인터페이스를 정의합니다.
    """
    
    @abstractmethod
    def signal(self) -> Optional[str]:
        """거래 신호 생성"""
        pass
    
    @abstractmethod
    def is_ready(self) -> bool:
        """전략이 신호 생성 준비가 되었는지 확인"""
        pass
    
    @abstractmethod
    def get_indicator_data(self) -> dict:
        """현재 지표 데이터 반환"""
        pass
    
    async def initialize_with_history(self):
        """
        봇 시작 시 히스토리 데이터로 초기화 (선택적)
        각 전략에서 필요에 따라 구현
        """
        pass
    
    def update_trade(self, price: float, volume: float):
        """
        새로운 거래 데이터로 전략 업데이트 (선택적)
        트레이드 스트림이 필요한 전략에서 구현
        """
        pass
    
    def update_kline(self, high: float, low: float, close: float):
        """
        새로운 캔들 데이터로 전략 업데이트 (선택적)
        캔들 데이터가 필요한 전략에서 구현
        """
        pass