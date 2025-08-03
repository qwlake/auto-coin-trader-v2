from .base_settings import BaseSettings

class VWAPSettings(BaseSettings):
    """VWAP Mean Reversion 전략 설정"""
    
    # VWAP 계산 파라미터
    VWAP_WINDOW_MINUTES: int = 5          # VWAP 계산 윈도우 (분)
    VWAP_BAND_MULTIPLIER: float = 1.5     # 표준편차 밴드 배수
    VWAP_STDDEV_PERIOD: int = 20          # 표준편차 계산 기간
    VWAP_PROFIT_TARGET: float = 0.006     # 0.6% 익절
    VWAP_STOP_LOSS: float = 0.003         # 0.3% 손절
    
    # ADX 파라미터 (추세 강도 측정)
    ADX_PERIOD: int = 14
    ADX_TREND_THRESHOLD: float = 20.0     # 추세 발생 임계값
    ADX_STRONG_TREND_THRESHOLD: float = 40.0  # 강한 추세 임계값
    
    # 변동성 모니터링
    VOLATILITY_THRESHOLD: float = 0.0015  # 0.15% 변동성 임계값
    VOLATILITY_HALT_DURATION: int = 600   # 10분간 거래 중단
    
    # 세션 관리
    SESSION_RESET_HOUR: int = 0           # UTC 기준 VWAP 리셋 시간