import os
from dotenv import load_dotenv
from .base_settings import BaseSettings
from .obi_settings import OBISettings  
from .vwap_settings import VWAPSettings

# .env와 .apikey 파일 로드
load_dotenv()  # .env 로드
load_dotenv(".apikey")  # .apikey 로드

def get_settings():
    """전략 타입에 따라 적절한 설정을 반환"""
    # .env 파일에서 전략 타입 확인 (기본값: OBI)
    strategy_type = os.getenv("STRATEGY_TYPE", "OBI").upper()
    
    if strategy_type == "VWAP":
        return VWAPSettings()
    elif strategy_type == "OBI":
        return OBISettings()
    else:
        raise ValueError(f"Unknown strategy type: {strategy_type}. Use 'OBI' or 'VWAP'")

# 전역 설정 인스턴스
settings = get_settings()

# 디버그용 출력
print(f"Loaded {type(settings).__name__} for strategy: {settings.STRATEGY_TYPE}")
