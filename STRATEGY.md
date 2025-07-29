# OBI 스캘핑 전략

## 현재 구현된 전략 개요

### 호가 불균형(OBI) 기반 신호 생성
- 상위 5단계 호가의 가중 평균으로 OBI 계산: `calc_obi()` 함수
- OBI = `bid_volume / (bid_volume + ask_volume)`
- 호가별 거래량 = `price * quantity`

### 거래 신호 조건
- 롱 진입: OBI >= 0.70 (매수 70% 이상 우위)
- 숏 진입: OBI <= 0.30 (매수 30% 이하 우위)
- 중립 구간: 0.30 < OBI < 0.70 (신호 없음)

### 주문 실행
- 선물 전용 LIMIT_MAKER 주문 (GTX 타입)
- 진입 가격: 현재 최우선 호가 중간값 `(bid + ask) / 2`
- 주문 수량: 20 USDT 상당 코인 수량으로 계산

### 포지션 관리
- SQLite 데이터베이스로 주문/포지션 상태 추적
- 3개 테이블: `pending_orders`, `active_positions`, `closed_positions`
- 백그라운드 1초 주기로 체결 확인 및 TP/SL 모니터링

### 익절/손절 기준
- 익절: 진입가격 대비 +0.05% (0.0005)
- 손절: 진입가격 대비 -0.05% (0.0005)
- 조건 만족시 시장가 청산 주문 실행

---

## 파일 구조 및 주요 설정

### 설정 파일 (`config/settings.py`)
```python
DEPTH_LEVEL: 5       # 호가 단계 수
OBI_LONG: 0.70       # 롱 진입 임계값
OBI_SHORT: 0.30      # 숏 진입 임계값
TP_PCT: 0.0005       # 익절 비율 (0.05%)
SL_PCT: 0.0005       # 손절 비율 (0.05%)
SIZE_QUOTE: 20       # 주문당 USDT 금액
ORDER_TTL: 2.0       # 주문 TTL (미구현)
```

### 전략 로직 (`strategy/obi_scalper.py`)
- `calc_obi()`: 호가 데이터로부터 OBI 계산
- `signal()`: OBI 값을 기준으로 "LONG"/"SHORT"/None 반환

### 주문 실행 (`executor/order_executor.py`)
- `place_limit_maker()`: 선물 지정가 주문 생성
- WebSocket API 사용, DRY_RUN 모드 지원
- 거래량 소수점 6자리 내림 처리

### 포지션 관리 (`executor/position_manager.py`)
- 주문 등록 → 체결 확인 → 포지션 활성화 → TP/SL 모니터링
- 모든 상태 변화를 SQLite에 기록
- 백그라운드 모니터링 루프 운영

### 메인 루프 (`main.py`)
- WebSocket으로 실시간 호가 데이터 수신
- 0.2초마다 OBI 신호 체크
- 신호 발생시 즉시 주문 실행 및 포지션 등록

---

## 현재 전략의 특징

### 장점
1. 실시간 호가 불균형 감지로 단기 기회 포착
2. Post-only 주문으로 수수료 절약
3. 대칭적 TP/SL로 방향성 편향 제거
4. SQLite 기반 상태 관리로 재시작시 복구 가능

### 현재 한계점
1. 고정 임계값으로 시장 변동성 미반영
2. 중간값 주문으로 스프레드 활용도 낮음
3. TTL 기능 미구현으로 장기간 미체결 주문 잔존
4. 신호 스무딩 없어 노이즈 민감
5. 성과 지표 추적 기능 부재