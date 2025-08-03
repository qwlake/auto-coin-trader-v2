from pydantic_settings import BaseSettings

class BaseSettings(BaseSettings):
    """공통 설정: API 인증, 기본 트레이딩 설정"""
    
    # API 인증
    BINANCE_API_KEY: str
    BINANCE_SECRET: str
    TESTNET: bool = True
    
    # 기본 트레이딩 설정
    DRY_RUN: bool = False
    SYMBOL: str = "BTCUSDT"
    QUOTE_ASSET: str = "USDT"      # "USDT" or "USDC"
    SIZE_QUOTE: float = 20         # 주문할 계정화폐 금액 (ex: 20 USDT)
    
    # 전략 선택
    STRATEGY_TYPE: str = "OBI"     # "OBI" or "VWAP"
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }