# 웹소켓 연결 모니터링 및 복구 시스템

## 문제 상황
```
2025-08-04 00:15:55,157 [ERROR] binance.ws.reconnecting_websocket: BinanceWebsocketClosed (Connection closed. Reconnecting...)
```

이런 웹소켓 연결 끊김은 일반적인 상황으로, 다음과 같은 이유로 발생합니다:
- 네트워크 불안정
- Binance 서버 점검
- 긴 시간 연결 유지로 인한 자동 끊김
- 방화벽/프록시 문제

## 구현된 개선사항

### 1. 자동 재연결 시스템 (Enhanced)
- **지수 백오프**: 재연결 시도 간격을 1초 → 2초 → 4초로 점진적 증가
- **최대 재시도**: 각 스트림당 5번까지 재시도
- **스트림별 독립적 복구**: depth, trade, kline 스트림이 개별적으로 복구됨

### 2. 연결 상태 모니터링
```python
connection_stats = {
    'reconnect_count': 0,
    'last_reconnect_time': None,
    'total_disconnections': 0,
    'stream_start_time': time.time(),
    'last_depth_update': None,
    'last_trade_update': None,
    'last_kline_update': None
}
```

### 3. 건강상태 체크
- **30초마다 연결 상태 점검**
- **60초 이상 데이터 없으면 경고**
- **각 스트림별 지연시간 추적**

### 4. GUI 모니터링 (계획)
- 연결 시간 표시
- 연결 끊김 횟수 추적
- 데이터 지연 상태 표시 (🟢 정상 / 🟡 지연 / 🔴 문제)

## 사용법

### 모니터링 로그 확인
```bash
# 연결 상태 로그
grep "ConnectionHealth" logs/bot.log

# 재연결 로그
grep "Connection error" logs/bot.log
```

### 주요 로그 메시지
- `[ConnectionHealth] Uptime: X.Xmin, Disconnections: X` - 정상 상태 보고
- `[DepthStream] Connection error (attempt X/5)` - 재연결 시도 중
- `[ConnectionHealth] Potential connection issue detected` - 연결 문제 감지

## 추가 권장사항

### 1. 네트워크 안정화
```bash
# DNS 설정 최적화
echo "nameserver 8.8.8.8" >> /etc/resolv.conf
echo "nameserver 1.1.1.1" >> /etc/resolv.conf
```

### 2. 방화벽 설정
```bash
# Binance API 포트 허용
sudo ufw allow out 443/tcp
sudo ufw allow out 9443/tcp
```

### 3. 모니터링 스크립트
```bash
#!/bin/bash
# check_connection.sh
tail -f logs/bot.log | grep -E "(ConnectionHealth|Connection error|Disconnections)"
```

### 4. 알람 설정 (옵션)
- 연결 끊김이 10회 이상 발생시 알림
- 60초 이상 데이터 없을 때 알림
- 봇이 완전히 중단되었을 때 알림

## 문제 해결 순서

1. **로그 확인**: 재연결이 정상적으로 이루어지는지 확인
2. **네트워크 점검**: ping, traceroute로 연결 상태 확인
3. **방화벽 점검**: 필요한 포트가 열려있는지 확인
4. **Binance 상태**: https://binance.com/en/support/announcement 점검
5. **봇 재시작**: 문제가 지속되면 봇 재시작

대부분의 경우 자동 재연결으로 문제가 해결되며, 이는 정상적인 동작입니다.