import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BINANCE_API_KEY: str
    BINANCE_SECRET: str
    TESTNET: bool = False          # 메인넷 연결 여부
    DRY_RUN: bool = True           # True일 때는 주문 시뮬레이션만
    SYMBOL: str = "BTCUSDT"
    DEPTH_LEVEL: int = 5           # 호가 N단
    OBI_LONG: float = 0.70
    OBI_SHORT: float = 0.30
    TP_PCT: float = 0.0005         # +0.05 %
    SL_PCT: float = 0.0005         # –0.05 %
    ORDER_TTL: float = 2.0         # 초
    SIZE_USDT: float = 20          # 1회 주문액

    model_config = {               # ← v2 방식의 설정
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

settings = Settings()