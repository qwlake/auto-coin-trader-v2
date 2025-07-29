# VWAP Mean Reversion Strategy 구현 가이드

## 1. 전략 개요

### 핵심 컨셉
- **평균 회귀 전략**: VWAP에서 이탈한 가격이 다시 VWAP로 돌아올 것을 기대하는 전략
- **시장 상태 필터**: ADX로 횡보/추세 시장 구분하여 횡보에서만 거래
- **리스크 관리**: 0.6% 익절, 0.3% 손절로 고정
- **실행 방식**: 바이낸스 선물 LIMIT 주문 (기존 OBI 봇과 동일)

## 2. 필요한 기술적 지표

### 2.1 VWAP 계산
```python
class VWAPCalculator:
    def __init__(self):
        self.cumulative_pv = 0.0      # 가격 × 거래량 누적
        self.cumulative_volume = 0.0   # 거래량 누적
        self.session_start = None      # 세션 시작 시간 (UTC 0시)

    def update(self, price: float, volume: float):
        self.cumulative_pv += price * volume
        self.cumulative_volume += volume
        return self.get_vwap()
    
    def get_vwap(self):
        if self.cumulative_volume > 0:
            return self.cumulative_pv / self.cumulative_volume
        return 0.0

    def reset_session(self):
        self.cumulative_pv = 0.0
        self.cumulative_volume = 0.0
```

### 2.2 ADX (추세 강도) 계산
```python
class ADXCalculator:
    def __init__(self, period=14):
        self.period = period
        self.price_history = []
        
    def update(self, high, low, close):
        self.price_history.append({'high': high, 'low': low, 'close': close})
        if len(self.price_history) > self.period * 2:
            self.price_history.pop(0)
        return self.calculate_adx()
    
    def calculate_adx(self):
        # ADX 계산 로직 (14개 캔들 필요)
        if len(self.price_history) < self.period + 1:
            return 0
        # 실제 구현에서는 talib 라이브러리 사용 권장
        pass
```

### 2.3 VWAP 밴드
```python
class VWAPBands:
    def __init__(self, multiplier=1.5, period=20):
        self.multiplier = multiplier
        self.period = period
        self.price_deviations = []
    
    def update(self, current_price, vwap):
        deviation = abs(current_price - vwap)
        self.price_deviations.append(deviation)
        if len(self.price_deviations) > self.period:
            self.price_deviations.pop(0)
        
        if len(self.price_deviations) >= self.period:
            std_dev = statistics.stdev(self.price_deviations)
            return {
                'upper': vwap + (std_dev * self.multiplier),
                'lower': vwap - (std_dev * self.multiplier)
            }
        return None
```

## 3. 데이터 파이프라인

### 3.1 필요한 데이터 스트림
기존 `futures_ws.py`를 확장하여 다음 스트림 추가:

```python
# data/futures_ws.py 확장
class FuturesVWAPStream(FuturesDepthStream):
    def __init__(self, symbol: str):
        super().__init__(symbol)
        self.vwap_calculator = VWAPCalculator()
        self.adx_calculator = ADXCalculator()
        self.bands = VWAPBands()
        
    async def run(self):
        # 기존 depth stream + trade stream + kline stream 추가
        client = await AsyncClient.create(...)
        bm = BinanceSocketManager(client)
        
        # 3개 스트림 동시 실행
        tasks = [
            self._depth_stream(bm),
            self._trade_stream(bm),      # VWAP 계산용
            self._kline_stream(bm)       # ADX 계산용
        ]
        await asyncio.gather(*tasks)
        
    async def _trade_stream(self, bm):
        async with bm.futures_trade_socket(self.symbol) as stream:
            while True:
                msg = await stream.recv()
                price = float(msg['p'])
                volume = float(msg['q'])
                self.current_vwap = self.vwap_calculator.update(price, volume)
                
    async def _kline_stream(self, bm):
        async with bm.futures_kline_socket(self.symbol, '1m') as stream:
            while True:
                msg = await stream.recv()
                if msg['k']['x']:  # 캔들 종료
                    high = float(msg['k']['h'])
                    low = float(msg['k']['l'])
                    close = float(msg['k']['c'])
                    self.current_adx = self.adx_calculator.update(high, low, close)
```

### 3.2 설정 파라미터
`config/settings.py`에 추가:

```python
class Settings(BaseSettings):
    # 기존 설정들...
    
    # VWAP 전략 설정
    STRATEGY_TYPE: str = "OBI"  # "OBI" 또는 "VWAP"
    
    # VWAP 파라미터
    VWAP_BAND_MULTIPLIER: float = 1.5
    VWAP_PROFIT_TARGET: float = 0.006  # 0.6%
    VWAP_STOP_LOSS: float = 0.003      # 0.3%
    
    # ADX 파라미터
    ADX_PERIOD: int = 14
    ADX_THRESHOLD: float = 20.0  # ADX < 20일 때만 거래
```

## 4. 전략 로직 구현

### 4.1 VWAP 전략 모듈 
`strategy/vwap_strategy.py` 새로 생성:

```python
from config.settings import settings
import statistics

class VWAPStrategy:
    def __init__(self):
        self.vwap_calculator = VWAPCalculator()
        self.adx_calculator = ADXCalculator()
        self.bands = VWAPBands()
        self.is_ready = False
        
    def update_data(self, trade_data=None, kline_data=None, current_price=None):
        # 트레이드 데이터로 VWAP 업데이트
        if trade_data:
            self.vwap_calculator.update(trade_data['price'], trade_data['volume'])
            
        # 캔들 데이터로 ADX 업데이트
        if kline_data:
            self.adx_calculator.update(
                kline_data['high'], 
                kline_data['low'], 
                kline_data['close']
            )
            
        # 밴드 업데이트
        if current_price and self.vwap_calculator.get_vwap() > 0:
            self.bands.update(current_price, self.vwap_calculator.get_vwap())
            
        # 준비 상태 체크 (ADX 계산에 충분한 데이터 필요)
        self.is_ready = len(self.adx_calculator.price_history) >= 14
        
    def signal(self, current_price):
        if not self.is_ready:
            return None
            
        vwap = self.vwap_calculator.get_vwap()
        adx = self.adx_calculator.calculate_adx()
        bands = self.bands.update(current_price, vwap)
        
        # ADX 필터: 횡보 시장에서만 거래
        if adx > settings.ADX_THRESHOLD:
            return None
            
        if not bands:
            return None
            
        # 신호 생성
        if current_price <= bands['lower'] and current_price < vwap:
            return "LONG"   # 하단 밴드 터치 + VWAP 아래
        elif current_price >= bands['upper'] and current_price > vwap:
            return "SHORT"  # 상단 밴드 터치 + VWAP 위
            
        return None
```

### 4.2 main.py에서 VWAP 전략 사용
기존 OBI 로직을 VWAP로 교체:

```python
# main.py 수정 부분
from strategy.vwap_strategy import VWAPStrategy

async def runner():
    # ... 기존 초기화 코드 ...
    
    # VWAP 전략 초기화
    vwap_strategy = VWAPStrategy()
    
    # FuturesVWAPStream 사용
    stream = FuturesVWAPStream(settings.SYMBOL)
    ws_task = asyncio.create_task(stream.run())
    
    try:
        while True:
            # 현재 가격 획득
            if stream.depth and "b" in stream.depth and "a" in stream.depth:
                bid = float(stream.depth["b"][0][0])
                ask = float(stream.depth["a"][0][0])
                mid = (bid + ask) / 2
                
                # 전략 데이터 업데이트 
                vwap_strategy.update_data(current_price=mid)
                
                # 신호 생성
                sig = vwap_strategy.signal(mid)
                
                if sig == "LONG":
                    order = await place_limit_maker("BUY", mid)
                    await pos_manager.register_order(order)
                elif sig == "SHORT":
                    order = await place_limit_maker("SELL", mid)
                    await pos_manager.register_order(order)
                    
            await asyncio.sleep(0.2)
    except:
        # ... 기존 정리 코드 ...
```

## 5. 포지션 관리 확장

### 5.1 VWAP 전용 손익 관리
기존 `executor/position_manager.py`에서 VWAP 전략용 TP/SL 로직 추가:

```python
# position_manager.py에 추가할 메서드
async def check_vwap_exit_conditions(self, position, current_price, current_vwap):
    """VWAP 전략 전용 청산 조건 체크"""
    entry_price = position['entry_price']
    side = position['side']
    
    # 1. 고정 손익 목표
    if side == 'BUY':
        profit_target = entry_price * (1 + settings.VWAP_PROFIT_TARGET)
        stop_loss = entry_price * (1 - settings.VWAP_STOP_LOSS)
        
        if current_price >= profit_target:
            return "PROFIT"
        elif current_price <= stop_loss:
            return "LOSS"
        # VWAP 회귀 청산 (롱 포지션이 VWAP 위로 올라가면)
        elif current_price >= current_vwap:
            return "VWAP_REVERSION"
            
    elif side == 'SELL':
        profit_target = entry_price * (1 - settings.VWAP_PROFIT_TARGET)
        stop_loss = entry_price * (1 + settings.VWAP_STOP_LOSS)
        
        if current_price <= profit_target:
            return "PROFIT"
        elif current_price >= stop_loss:
            return "LOSS"
        # VWAP 회귀 청산 (숏 포지션이 VWAP 아래로 내려가면)
        elif current_price <= current_vwap:
            return "VWAP_REVERSION"
    
    return None
```

### 5.2 데이터베이스 확장
기존 테이블에 VWAP 관련 컬럼 추가:

```sql
-- active_positions 테이블에 컬럼 추가
ALTER TABLE active_positions ADD COLUMN strategy_type TEXT DEFAULT 'OBI';
ALTER TABLE active_positions ADD COLUMN vwap_at_entry REAL;

-- closed_positions 테이블에 컬럼 추가  
ALTER TABLE closed_positions ADD COLUMN strategy_type TEXT DEFAULT 'OBI';
ALTER TABLE closed_positions ADD COLUMN exit_reason TEXT;
```

## 6. 구현시 주의사항

### 6.1 ADX 계산 라이브러리
ADX 계산은 복잡하므로 기존 라이브러리 사용 권장:

```bash
# TA-Lib 설치
pip install ta-lib
```

```python
import talib
import numpy as np

class ADXCalculator:
    def __init__(self, period=14):
        self.period = period
        self.highs = []
        self.lows = []
        self.closes = []
        
    def update(self, high, low, close):
        self.highs.append(high)
        self.lows.append(low)  
        self.closes.append(close)
        
        # 버퍼 크기 제한
        max_size = self.period * 3
        if len(self.highs) > max_size:
            self.highs = self.highs[-max_size:]
            self.lows = self.lows[-max_size:]
            self.closes = self.closes[-max_size:]
            
        return self.calculate_adx()
        
    def calculate_adx(self):
        if len(self.highs) < self.period * 2:
            return 0
            
        highs = np.array(self.highs, dtype=np.float64)
        lows = np.array(self.lows, dtype=np.float64)
        closes = np.array(self.closes, dtype=np.float64)
        
        adx = talib.ADX(highs, lows, closes, timeperiod=self.period)
        return adx[-1] if not np.isnan(adx[-1]) else 0
```

### 6.2 VWAP 세션 리셋
일반적으로 VWAP은 하루 단위로 리셋됩니다:

```python
from datetime import datetime, timezone

class VWAPCalculator:
    def __init__(self):
        self.cumulative_pv = 0.0
        self.cumulative_volume = 0.0
        self.last_reset_date = None
        
    def check_session_reset(self):
        """매일 UTC 0시에 VWAP 리셋"""
        current_date = datetime.now(timezone.utc).date()
        if self.last_reset_date != current_date:
            self.cumulative_pv = 0.0
            self.cumulative_volume = 0.0
            self.last_reset_date = current_date
            return True
        return False
```

### 6.3 실시간 데이터 동기화
여러 WebSocket 스트림의 데이터를 동기화하는 것이 핵심:

```python
class FuturesVWAPStream:
    def __init__(self):
        self.latest_trade_price = None
        self.latest_vwap = None
        self.latest_adx = None
        self.data_lock = asyncio.Lock()
        
    async def _trade_stream(self, bm):
        async with bm.futures_trade_socket(self.symbol) as stream:
            while True:
                msg = await stream.recv()
                async with self.data_lock:
                    # 안전하게 데이터 업데이트
                    self.latest_trade_price = float(msg['p'])
                    # VWAP 계산...
```

## 7. 테스트 및 검증

### 7.1 기본 테스트 방법
```bash
# DRY_RUN 모드로 먼저 테스트
export DRY_RUN=true
python main.py
```

### 7.2 성과 지표 모니터링
- 승률: 최소 40% 이상 목표
- 평균 거래 시간: VWAP 회귀 특성상 짧은 시간 내 청산
- 손익비: 익절 0.6% vs 손절 0.3% = 2:1
- ADX 필터 효과: 횡보장에서의 성과 vs 추세장 회피

### 7.3 실제 운영 전 체크리스트
1. **설정 확인**:
   - SYMBOL: 거래할 심볼 설정
   - SIZE_QUOTE: 거래 규모 설정  
   - TESTNET: 테스트넷 여부

2. **지표 준비 상태**:
   - ADX 계산을 위한 최소 14개 캔들 데이터 확보
   - VWAP 계산을 위한 거래 데이터 스트림 정상 작동

3. **리스크 관리**:
   - 최대 동시 포지션 수 제한
   - 일일 최대 손실 한도 설정
   - 네트워크 연결 끊김시 대응 방안

이 가이드는 기존 OBI 스캘핑 봇 구조를 그대로 활용하면서 VWAP 평균 회귀 전략을 추가로 구현할 수 있도록 설계되었습니다. 핵심은 ADX로 시장 상태를 필터링하고, VWAP에서 이탈한 가격의 회귀를 노리는 것입니다.