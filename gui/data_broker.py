import json
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import sqlite3
from dataclasses import dataclass, asdict

@dataclass
class TradingState:
    """실시간 트레이딩 상태 데이터"""
    timestamp: float
    strategy_type: str
    current_price: float
    vwap: float = 0.0
    upper_band: float = 0.0
    lower_band: float = 0.0
    adx: float = 0.0
    is_halted: bool = False
    signal: str = ""
    
    # OBI specific
    obi_value: float = 0.0
    
    # Portfolio
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    active_positions: int = 0
    total_trades: int = 0
    win_rate: float = 0.0

class DataBroker:
    """메인 봇과 GUI 간의 실시간 데이터 공유 시스템"""
    
    def __init__(self, data_file: str = "storage/gui_state.json"):
        self.data_file = Path(data_file)
        self.data_file.parent.mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self.connection_stats = {}
        
        # 기존 파일이 있으면 로드, 없으면 초기 상태 생성
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self._state = TradingState(**data)
            except (json.JSONDecodeError, TypeError):
                # 파일이 손상되었으면 초기 상태 생성
                self._state = TradingState(
                    timestamp=time.time(),
                    strategy_type="OBI",
                    current_price=0.0
                )
                self._save_state()
        else:
            # 파일이 없으면 초기 상태 생성
            self._state = TradingState(
                timestamp=time.time(),
                strategy_type="OBI",
                current_price=0.0
            )
            self._save_state()
    
    def update_state(self, **kwargs):
        """상태 업데이트"""
        with self._lock:
            # 기존 상태 업데이트
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
            
            # 타임스탬프 갱신
            self._state.timestamp = time.time()
            
            # 파일에 저장
            self._save_state()
    
    def get_state(self) -> TradingState:
        """현재 상태 조회"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    return TradingState(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        
        return self._state
    
    def _save_state(self):
        """상태를 파일에 저장"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(asdict(self._state), f, indent=2)
        except Exception as e:
            print(f"Failed to save state: {e}")
    
    def update_price(self, price: float):
        """가격 업데이트"""
        self.update_state(current_price=price)
    
    def update_indicators(self, vwap: float = None, upper_band: float = None, 
                         lower_band: float = None, adx: float = None, 
                         obi_value: float = None):
        """지표 업데이트"""
        updates = {}
        if vwap is not None:
            updates['vwap'] = vwap
        if upper_band is not None:
            updates['upper_band'] = upper_band
        if lower_band is not None:
            updates['lower_band'] = lower_band
        if adx is not None:
            updates['adx'] = adx
        if obi_value is not None:
            updates['obi_value'] = obi_value
            
        if updates:
            self.update_state(**updates)
    
    def update_signal(self, signal: str):
        """거래 신호 업데이트"""
        self.update_state(signal=signal)
    
    def update_portfolio(self, total_pnl: float = None, daily_pnl: float = None,
                        active_positions: int = None, total_trades: int = None,
                        win_rate: float = None):
        """포트폴리오 정보 업데이트"""
        updates = {}
        if total_pnl is not None:
            updates['total_pnl'] = total_pnl
        if daily_pnl is not None:
            updates['daily_pnl'] = daily_pnl
        if active_positions is not None:
            updates['active_positions'] = active_positions
        if total_trades is not None:
            updates['total_trades'] = total_trades
        if win_rate is not None:
            updates['win_rate'] = win_rate
            
        if updates:
            self.update_state(**updates)
    
    def set_halt_status(self, is_halted: bool):
        """거래 중단 상태 업데이트"""
        self.update_state(is_halted=is_halted)
    
    def update_connection_stats(self, stats: dict):
        """연결 상태 통계 업데이트"""
        with self._lock:
            self.connection_stats = stats
    
    def get_connection_stats(self) -> dict:
        """연결 상태 통계 반환"""
        with self._lock:
            return self.connection_stats.copy()

class DatabaseReader:
    """SQLite 데이터베이스에서 거래 데이터 조회"""
    
    def __init__(self, db_path: str = "storage/orders.db"):
        self.db_path = db_path
    
    def get_active_positions(self) -> list:
        """활성 포지션 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # 먼저 테이블 구조 확인
                cursor = conn.execute("PRAGMA table_info(active_positions)")
                columns = [col[1] for col in cursor.fetchall()]
                
                # timestamp 컬럼이 있는지 확인
                if 'timestamp' in columns:
                    cursor = conn.execute("""
                        SELECT order_id, symbol, side, entry_price, quantity, 
                               strategy_type, vwap_at_entry, timestamp
                        FROM active_positions
                        ORDER BY timestamp DESC
                    """)
                else:
                    cursor = conn.execute("""
                        SELECT order_id, symbol, side, entry_price, quantity, 
                               strategy_type, vwap_at_entry, 
                               datetime('now') as timestamp
                        FROM active_positions
                        ORDER BY order_id DESC
                    """)
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching active positions: {e}")
            return []
    
    def get_closed_positions(self, limit: int = 50) -> list:
        """완료된 포지션 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # 먼저 테이블 구조 확인
                cursor = conn.execute("PRAGMA table_info(closed_positions)")
                columns = [col[1] for col in cursor.fetchall()]
                
                # 필요한 컬럼들이 있는지 확인
                select_fields = ["order_id", "symbol", "side", "entry_price", "exit_price", "quantity", "pnl"]
                optional_fields = {
                    "strategy_type": "strategy_type",
                    "exit_reason": "exit_reason", 
                    "timestamp": "timestamp"
                }
                
                # 존재하는 컬럼만 선택
                for field, column in optional_fields.items():
                    if column in columns:
                        select_fields.append(column)
                    else:
                        if field == "timestamp":
                            select_fields.append("datetime('now') as timestamp")
                        else:
                            select_fields.append(f"NULL as {field}")
                
                query = f"""
                    SELECT {', '.join(select_fields)}
                    FROM closed_positions
                    ORDER BY {"timestamp" if "timestamp" in columns else "id"} DESC
                    LIMIT ?
                """
                
                cursor = conn.execute(query, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching closed positions: {e}")
            return []
    
    def get_daily_stats(self, date: str = None) -> dict:
        """일일 통계 조회"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(pnl) as total_pnl,
                        AVG(pnl) as avg_pnl,
                        MIN(pnl) as min_pnl,
                        MAX(pnl) as max_pnl
                    FROM closed_positions
                    WHERE DATE(timestamp) = ?
                """, (date,))
                
                row = cursor.fetchone()
                if row and row[0] > 0:
                    return {
                        'total_trades': row[0],
                        'winning_trades': row[1],
                        'win_rate': (row[1] / row[0]) * 100 if row[0] > 0 else 0,
                        'total_pnl': row[2] or 0,
                        'avg_pnl': row[3] or 0,
                        'min_pnl': row[4] or 0,
                        'max_pnl': row[5] or 0
                    }
        except Exception as e:
            print(f"Error fetching daily stats: {e}")
        
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'avg_pnl': 0,
            'min_pnl': 0,
            'max_pnl': 0
        }

# 전역 인스턴스
data_broker = DataBroker()
db_reader = DatabaseReader()