# 🖥️ Trading Bot GUI 사용법

## 개요

Streamlit 기반의 실시간 모니터링 GUI를 제공합니다. 트레이딩 봇의 모든 활동을 웹 브라우저에서 실시간으로 모니터링할 수 있습니다.

## 주요 기능

### 📊 실시간 대시보드
- **현재 가격**: 실시간 시세 표시
- **일일 PnL**: 오늘의 손익 현황
- **승률**: 거래 성공률 추적
- **활성 포지션**: 현재 진행 중인 거래 수

### 📈 차트 분석
- **가격 차트**: 실시간 가격 움직임
- **VWAP 지표**: VWAP, 상단/하단 밴드 (VWAP 전략 시)
- **PnL 차트**: 누적 손익 그래프
- **거래량**: 실시간 거래량 표시

### 💼 거래 관리
- **활성 포지션**: 진행 중인 거래 상세 정보
- **거래 내역**: 완료된 거래 기록
- **성과 통계**: 승률, 평균 손익, 최대 손실 등

### 🎯 전략 모니터링
- **OBI 전략**: 호가 불균형 지표, 신호 상태
- **VWAP 전략**: VWAP 대비 가격 위치, ADX 상태, 변동성 중단 여부

## 설치 및 실행

### 1. 의존성 설치
```bash
uv sync
```

### 2. GUI 실행
```bash
# 방법 1: 실행 스크립트 사용
python run_gui.py

# 방법 2: 직접 실행
uv run streamlit run gui/streamlit_app.py
```

### 3. 브라우저 접속
```
http://localhost:8501
```

## 사용법

### 기본 설정
1. **자동 새로고침**: 사이드바에서 활성화/비활성화
2. **새로고침 간격**: 1-10초 설정 가능
3. **수동 새로고침**: "🔄 지금 새로고침" 버튼

### 실시간 모니터링
1. **메인 봇 실행**: `python main.py`
2. **GUI 실행**: `python run_gui.py`
3. **브라우저에서 모니터링**: 자동으로 데이터가 업데이트됨

### 전략별 모니터링

#### OBI 전략
- **신호 상태**: BUY/SELL 신호 표시
- **OBI 값**: 현재 호가 불균형 수치
- **임계값**: 매수/매도 임계값 (0.3/0.7)

#### VWAP 전략  
- **신호 상태**: LONG/SHORT 신호 표시
- **VWAP 대비**: 현재 가격이 VWAP 대비 얼마나 높은/낮은지
- **시장 상태**: ADX 기반 추세 강도 (횡보/추세/강한추세)
- **변동성 중단**: 높은 변동성으로 인한 거래 중단 여부

## 데이터 흐름

```
Trading Bot → Data Broker → GUI
     ↓              ↓         ↓
- 실시간 가격    - JSON 파일   - 자동 새로고침
- 지표 데이터    - SQLite DB   - 차트 업데이트  
- 거래 신호     - 상태 관리    - 테이블 갱신
- 포지션 정보
```

## 문제 해결

### GUI가 데이터를 표시하지 않는 경우
1. **봇 실행 확인**: `python main.py`가 실행 중인지 확인
2. **데이터 파일 확인**: `storage/gui_state.json` 파일 존재 여부
3. **데이터베이스 확인**: `storage/orders.db` 파일 존재 여부

### 차트가 표시되지 않는 경우
1. **의존성 확인**: `uv sync` 재실행
2. **브라우저 캐시**: 브라우저 새로고침 (Ctrl+F5)
3. **포트 충돌**: 8501 포트가 사용 중인지 확인

### 성능 최적화
1. **새로고침 간격**: 느린 시스템에서는 간격을 늘림
2. **자동 새로고침**: 필요시 비활성화
3. **브라우저 탭**: 여러 탭 동시 사용 지양

## 커스터마이징

### 새로운 차트 추가
```python
# gui/components/charts.py에 새 함수 추가
def create_custom_chart(data):
    # Plotly 차트 구현
    pass
```

### 새로운 위젯 추가
```python
# gui/components/widgets.py에 새 함수 추가
def create_custom_widget(state):
    # Streamlit 위젯 구현
    pass
```

### 데이터 확장
```python
# gui/data_broker.py의 TradingState에 필드 추가
@dataclass
class TradingState:
    # 기존 필드들...
    custom_field: float = 0.0
```

## 보안 주의사항

1. **로컬 접속만**: GUI는 localhost에서만 실행
2. **API 키**: GUI에서 API 키 정보 표시 안 함
3. **민감 정보**: 로그에서 민감 정보 자동 필터링

## 지원되는 브라우저

- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

## 기술 스택

- **Frontend**: Streamlit
- **Charts**: Plotly
- **Data**: Pandas, NumPy
- **Storage**: SQLite, JSON
- **Backend**: AsyncIO, Binance API