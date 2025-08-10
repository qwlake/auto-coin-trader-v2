import asyncio
import aiosqlite
from typing import Dict, List, Optional, Tuple
from config.settings import settings
from utils.logger import log
from datetime import datetime
from . import order_executor


class PositionManager:
    """
    Enhanced Position Manager with strategy-specific support
    
    ┌────────────────────────────────────────────────────────────────────────┐
     - 주문이 들어오면 pending_orders 테이블에 저장 (strategy context 포함)
     - DB에 남은 pending_orders, active_positions를 재시작 시 로드
     - 백그라운드 루프:
         1) pending_orders 테이블의 주문을 주기적으로 get_order()로 확인 →
            FILLED 되면 active_positions 테이블에 옮겨 등록
         2) active_positions 테이블의 각 포지션을 strategy-specific TP/SL 조건 비교 →
            조건 만족 시 시장가 청산 → closed_positions 테이블에 기록
    └────────────────────────────────────────────────────────────────────────┘
    """
    def __init__(self):
        self.db_path = "storage/orders.db"
        self._task = None

    async def init(self):
        """
        1. DB 연결 & 스키마 생성 (enhanced for VWAP strategy)
        2. pending_orders / active_positions 테이블에서 기존 데이터를 메모리 없이 계속 DB로 관리
        3. 백그라운드 _monitor_positions() 실행
        """
        # 1) DB 스키마 생성
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_orders (
                    order_id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    orig_qty REAL NOT NULL,
                    strategy_type TEXT DEFAULT 'OBI',
                    vwap_at_entry REAL DEFAULT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS active_positions (
                    order_id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    strategy_type TEXT DEFAULT 'OBI',
                    vwap_at_entry REAL DEFAULT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS closed_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    pnl REAL NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    strategy_type TEXT DEFAULT 'OBI',
                    vwap_at_entry REAL DEFAULT NULL,
                    exit_reason TEXT DEFAULT 'TP_SL'
                )
                """
            )
            
            # VWAP 히스토리 테이블 추가
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS vwap_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    vwap REAL NOT NULL,
                    upper_band REAL,
                    lower_band REAL,
                    current_price REAL,
                    adx REAL,
                    volume_window_trades INTEGER DEFAULT 0
                )
                """
            )
            
            await db.commit()

        # 2) 백그라운드 모니터링 태스크 시작
        self._task = asyncio.create_task(self._monitor_positions())
        log.info("[PositionManager] Initialized and monitor task started")

    async def register_order(self, order: Dict, strategy_type: str = None, vwap_at_entry: float = None):
        """
        Enhanced order registration with strategy context
        place_limit_maker()가 생성한 주문을 pending_orders 테이블에 저장
        """
        order_id = int(order["orderId"])
        symbol = order["symbol"]
        side = order["side"]
        orig_qty = float(order["origQty"])
        
        # Determine strategy type from settings if not provided
        if strategy_type is None:
            strategy_type = settings.STRATEGY_TYPE

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO pending_orders 
                (order_id, symbol, side, orig_qty, strategy_type, vwap_at_entry)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (order_id, symbol, side, orig_qty, strategy_type, vwap_at_entry)
            )
            await db.commit()

        # Enhanced logging with strategy context
        if strategy_type == "VWAP" and vwap_at_entry:
            log.info(f"[PositionManager] Registered pending order {order_id} ({side} {orig_qty} @ {symbol}) - Strategy: {strategy_type}, VWAP: {vwap_at_entry:.2f}")
        else:
            log.info(f"[PositionManager] Registered pending order {order_id} ({side} {orig_qty} @ {symbol}) - Strategy: {strategy_type}")

    async def _monitor_positions(self):
        """
        Enhanced position monitoring with strategy-specific TP/SL
        1) pending_orders 테이블 주문 상태 확인 → FILLED 시 active_positions 테이블로 옮기기
        2) active_positions 테이블 포지션 TP/SL 검사 → 청산 시 closed_positions에 기록하고 active_positions에서 삭제
        """
        while True:
            try:
                # ── 1) pending_orders 테이블 주문 체크 ─────────────────────────────────────────
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute(
                        "SELECT order_id, symbol, side, orig_qty, strategy_type, vwap_at_entry FROM pending_orders"
                    )
                    rows = await cursor.fetchall()

                for row in rows:
                    order_id, symbol, side, orig_qty, strategy_type, vwap_at_entry = row
                        
                    # 실제 Binance 주문 상태 확인
                    resp = await order_executor.get_order(symbol=symbol, order_id=order_id)
                    status = resp.get("status")
                    if status == "FILLED":
                        entry_price = (
                            float(resp.get("avgPrice")) if resp.get("avgPrice")
                            else float(resp.get("price"))
                        )
                        executed_qty = float(resp.get("executedQty", orig_qty))

                        # 1-1) active_positions 테이블에 추가
                        async with aiosqlite.connect(self.db_path) as db:
                            await db.execute(
                                """
                                INSERT OR REPLACE INTO active_positions
                                (order_id, symbol, side, entry_price, quantity, strategy_type, vwap_at_entry)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                (order_id, symbol, side, entry_price, executed_qty, strategy_type, vwap_at_entry)
                            )
                            # 1-2) pending_orders에서 삭제
                            await db.execute(
                                "DELETE FROM pending_orders WHERE order_id = ?",
                                (order_id,)
                            )
                            await db.commit()

                        log.info(
                            f"[PositionManager] Order {order_id} FILLED → "
                            f"Active position added (side={side}, entry_price={entry_price}, qty={executed_qty}, strategy={strategy_type})"
                        )

                # ── 2) active_positions TP/SL 체크 ─────────────────────────────────────────────
                # 현재가 가져오기 (여기서는 단일 심볼 가정. 멀티심볼은 각 심볼별 조회 또는 WebSocket 유지)
                ticker = await order_executor.get_symbol_ticker(symbol=settings.SYMBOL)
                current_price = float(ticker["price"])

                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute(
                        "SELECT order_id, symbol, side, entry_price, quantity, strategy_type, vwap_at_entry FROM active_positions"
                    )
                    active_rows = await cursor.fetchall()

                for row in active_rows:
                    order_id, symbol, side, entry_price, qty, strategy_type, vwap_at_entry = row
                    
                    # Strategy-specific TP/SL calculation
                    if strategy_type == "VWAP":
                        tp_pct = settings.VWAP_PROFIT_TARGET  # 0.6%
                        sl_pct = settings.VWAP_STOP_LOSS      # 0.3%
                    else:
                        tp_pct = settings.TP_PCT  # Existing OBI values
                        sl_pct = settings.SL_PCT
                    
                    # Check exit conditions
                    should_close, exit_reason = self._check_exit_conditions(
                        side, entry_price, current_price, tp_pct, sl_pct, vwap_at_entry
                    )
                    
                    if should_close:
                        # Execute market order for position closure
                        market_side = "SELL" if side == "BUY" else "BUY"
                        market_order = await order_executor.place_market_order(
                            symbol=symbol,
                            side=market_side,
                            quantity=f"{qty:.6f}"
                        )
                        exit_price = float(market_order["fills"][0]["price"])
                        pnl = self._calculate_pnl(side, entry_price, exit_price, qty)
                        
                        # Record in closed_positions with enhanced data
                        async with aiosqlite.connect(self.db_path) as db:
                            await db.execute(
                                """
                                INSERT INTO closed_positions
                                (order_id, symbol, side, entry_price, exit_price, quantity, pnl,
                                 strategy_type, vwap_at_entry, exit_reason)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (order_id, symbol, side, entry_price, exit_price, qty, pnl,
                                 strategy_type, vwap_at_entry, exit_reason)
                            )
                            await db.execute(
                                "DELETE FROM active_positions WHERE order_id = ?",
                                (order_id,)
                            )
                            await db.commit()
                        
                        log.info(f"[PositionManager] Closed {strategy_type} {side} {order_id} @ {exit_price} / PnL={pnl:.6f} / Reason={exit_reason}")

                # ── 3) 전체 PnL 누적 합계 로그 (선택사항) ─────────────────────────────────────
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("SELECT SUM(pnl) FROM closed_positions")
                    row = await cursor.fetchone()
                    total_pnl = row[0] or 0.0
                log.info(f"[PositionManager] Total closed PnL so far = {total_pnl:.6f}")
                
                # GUI 데이터 업데이트
                await self.update_gui_data()

                await asyncio.sleep(1.0)  # 1초마다 체크
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"[PositionManager] Exception in monitor loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    def _check_exit_conditions(self, side: str, entry_price: float, current_price: float, 
                              tp_pct: float, sl_pct: float, vwap_at_entry: float = None) -> Tuple[bool, str]:
        """Check if position should be closed and return reason"""
        if side == "BUY":
            tp_price = entry_price * (1 + tp_pct)
            sl_price = entry_price * (1 - sl_pct)
            
            if current_price >= tp_price:
                return True, "PROFIT_TARGET"
            elif current_price <= sl_price:
                return True, "STOP_LOSS"
            # VWAP reversion check for mean reversion strategy
            elif vwap_at_entry and current_price >= vwap_at_entry:
                return True, "VWAP_REVERSION"
                
        elif side == "SELL":
            tp_price = entry_price * (1 - tp_pct)
            sl_price = entry_price * (1 + sl_pct)
            
            if current_price <= tp_price:
                return True, "PROFIT_TARGET"
            elif current_price >= sl_price:
                return True, "STOP_LOSS"
            # VWAP reversion check for mean reversion strategy
            elif vwap_at_entry and current_price <= vwap_at_entry:
                return True, "VWAP_REVERSION"
        
        return False, ""

    def _calculate_pnl(self, side: str, entry_price: float, exit_price: float, quantity: float) -> float:
        """Calculate PnL for a position"""
        if side == "BUY":
            return (exit_price - entry_price) * quantity
        else:  # SELL
            return (entry_price - exit_price) * quantity

    async def get_portfolio_stats(self) -> Dict:
        """GUI용 포트폴리오 통계 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 활성 포지션 수
                cursor = await db.execute("SELECT COUNT(*) FROM active_positions")
                active_count = (await cursor.fetchone())[0]
                
                # 오늘의 통계
                today = datetime.now().strftime("%Y-%m-%d")
                cursor = await db.execute("""
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(pnl) as total_pnl,
                        AVG(pnl) as avg_pnl
                    FROM closed_positions
                    WHERE DATE(timestamp) = ?
                """, (today,))
                
                row = await cursor.fetchone()
                if row and row[0] > 0:
                    return {
                        'active_positions': active_count,
                        'total_trades': row[0],
                        'winning_trades': row[1],
                        'win_rate': (row[1] / row[0]) * 100 if row[0] > 0 else 0,
                        'total_pnl': row[2] or 0,
                        'daily_pnl': row[2] or 0,
                        'avg_pnl': row[3] or 0
                    }
                else:
                    return {
                        'active_positions': active_count,
                        'total_trades': 0,
                        'winning_trades': 0,
                        'win_rate': 0,
                        'total_pnl': 0,
                        'daily_pnl': 0,
                        'avg_pnl': 0
                    }
        except Exception as e:
            log.error(f"Error getting portfolio stats: {e}")
            return {
                'active_positions': 0,
                'total_trades': 0,
                'winning_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'daily_pnl': 0,
                'avg_pnl': 0
            }
    
    async def update_gui_data(self):
        """GUI 데이터 브로커 업데이트"""
        try:
            # GUI 데이터 브로커가 있는 경우에만 업데이트
            try:
                from gui.data_broker import data_broker
                stats = await self.get_portfolio_stats()
                data_broker.update_portfolio(**stats)
            except ImportError:
                # GUI 모듈이 없는 경우 무시
                pass
        except Exception as e:
            log.debug(f"GUI update failed: {e}")

    async def close(self):
        """
        외부에서 PositionManager를 종료할 때 호출
        """
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("[PositionManager] Monitor task cancelled")

    async def save_vwap_history(self, symbol: str, vwap: float, upper_band: float = None, 
                               lower_band: float = None, current_price: float = None, 
                               adx: float = None, volume_window_trades: int = 0):
        """VWAP 히스토리 데이터를 DB에 저장"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO vwap_history 
                    (symbol, vwap, upper_band, lower_band, current_price, adx, volume_window_trades)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (symbol, vwap, upper_band, lower_band, current_price, adx, volume_window_trades)
                )
                await db.commit()
        except Exception as e:
            log.error(f"Error saving VWAP history: {e}")
    
    async def get_vwap_history(self, symbol: str, hours: int = 1) -> list:
        """지정된 시간 동안의 VWAP 히스토리 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    """
                    SELECT timestamp, vwap, upper_band, lower_band, current_price, adx
                    FROM vwap_history 
                    WHERE symbol = ? AND timestamp >= datetime('now', '-{} hours')
                    ORDER BY timestamp ASC
                    """.format(hours),
                    (symbol,)
                )
                rows = await cursor.fetchall()
                return [
                    {
                        'timestamp': row[0],
                        'vwap': row[1],
                        'upper_band': row[2],
                        'lower_band': row[3],
                        'current_price': row[4],
                        'adx': row[5]
                    }
                    for row in rows
                ]
        except Exception as e:
            log.error(f"Error getting VWAP history: {e}")
            return []
    
    async def cleanup_old_vwap_history(self, days: int = 7):
        """오래된 VWAP 히스토리 데이터 정리"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM vwap_history WHERE timestamp < datetime('now', '-{} days')".format(days)
                )
                await db.commit()
        except Exception as e:
            log.error(f"Error cleaning up VWAP history: {e}")
