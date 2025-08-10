# Test Suite

이 프로젝트의 테스트 스위트입니다.

## 테스트 실행 방법

### 프로젝트 루트에서 실행:
```bash
# 모든 테스트 실행
python -m pytest test/ -v

# 특정 테스트 파일 실행
python -m pytest test/test_order_executor.py -v

# 커버리지와 함께 실행 (pytest-cov 설치 필요)
python -m pytest test/ --cov=executor --cov-report=html
```

### test 폴더에서 실행:
```bash
cd test
python -m pytest test_order_executor.py -v
```

## 테스트 구조

- `conftest.py`: pytest 설정 및 공통 픽스처
- `test_order_executor.py`: order_executor 모듈 테스트

## 환경 설정

⚠️ **중요**: 테스트 실행 전에 프로젝트 루트에 `.env` 파일이 필요합니다.

```bash
# .env 파일 예시
BINANCE_API_KEY=your_api_key
BINANCE_SECRET=your_secret
TESTNET=True
DRY_RUN=True
STRATEGY_TYPE=OBI
SYMBOL=BTCUSDT
SIZE_QUOTE=10.0
```

- 테스트는 자동으로 프로젝트 루트의 `.env` 파일을 로드합니다
- `.env` 파일이 없으면 테스트가 실패합니다 (의도된 동작)
- 모든 테스트는 DRY_RUN 모드와 실제 API 호출을 구분하여 테스트합니다

## 테스트 커버리지

현재 `order_executor.py` 모듈의 주요 함수들을 테스트합니다:
- ✅ get_symbol_ticker (가격 조회)
- ✅ get_open_orders (미체결 주문 조회)
- ✅ get_order (주문 상태 조회)
- ✅ place_market_order (시장가 주문)
- ✅ place_limit_maker (지정가 주문)
- ✅ inject_client (클라이언트 주입)
- ✅ 에러 핸들링