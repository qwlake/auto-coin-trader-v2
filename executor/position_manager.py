import asyncio
import aiosqlite
from typing import Dict, List
from config.settings import settings
from utils.logger import log
from binance import AsyncClient


class PositionManager:
    """
    ┌────────────────────────────────────────────────────────────────────────┐
     - 주문이 들어오면 pending_orders 테이블에 저장
     - DB에 남은 pending_orders, active_positions를 재시작 시 로드
     - 백그라운드 루프:
         1) pending_orders 테이블의 주문을 주기적으로 get_order()로 확인 →
            FILLED 되면 active_positions 테이블에 옮겨 등록
         2) active_positions 테이블의 각 포지션을 TP/SL 조건 비교 →
            조건 만족 시 시장가 청산 → closed_positions 테이블에 기록
    └────────────────────────────────────────────────────────────────────────┘
    """
    def __init__(self, client: AsyncClient):
        self.client = client
        self.db_path = "storage/orders.db"
        self._task = None

    async def init(self):
        """
        1. DB 연결 & 스키마 생성
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
                    orig_qty REAL NOT NULL
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
                    quantity REAL NOT NULL
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
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.commit()

        # 2) 백그라운드 모니터링 태스크 시작
        self._task = asyncio.create_task(self._monitor_positions())
        log.info("[PositionManager] Initialized and monitor task started")

    async def register_order(self, order: Dict):
        """
        place_limit_maker()가 생성한 주문을 pending_orders 테이블에 저장
        """
        order_id = int(order["orderId"])
        symbol = order["symbol"]
        side = order["side"]
        orig_qty = float(order["origQty"])

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO pending_orders (order_id, symbol, side, orig_qty)
                VALUES (?, ?, ?, ?)
                """,
                (order_id, symbol, side, orig_qty)
            )
            await db.commit()

        log.info(f"[PositionManager] Registered pending order {order_id} ({side} {orig_qty} @ {symbol})")

    async def _monitor_positions(self):
        """
        1) pending_orders 테이블 주문 상태 확인 → FILLED 시 active_positions 테이블로 옮기기
        2) active_positions 테이블 포지션 TP/SL 검사 → 청산 시 closed_positions에 기록하고 active_positions에서 삭제
        """
        while True:
            try:
                # ── 1) pending_orders 테이블 주문 체크 ─────────────────────────────────────────
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("SELECT order_id, symbol, side, orig_qty FROM pending_orders")
                    rows = await cursor.fetchall()

                for order_id, symbol, side, orig_qty in rows:
                    # 실제 Binance 주문 상태 확인
                    resp = await self.client.futures_get_order(symbol=symbol, orderId=order_id)
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
                                (order_id, symbol, side, entry_price, quantity)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (order_id, symbol, side, entry_price, executed_qty)
                            )
                            # 1-2) pending_orders에서 삭제
                            await db.execute(
                                "DELETE FROM pending_orders WHERE order_id = ?",
                                (order_id,)
                            )
                            await db.commit()

                        log.info(
                            f"[PositionManager] Order {order_id} FILLED → "
                            f"Active position added (side={side}, entry_price={entry_price}, qty={executed_qty})"
                        )

                # ── 2) active_positions TP/SL 체크 ─────────────────────────────────────────────
                # 현재가 가져오기 (여기서는 단일 심볼 가정. 멀티심볼은 각 심볼별 조회 또는 WebSocket 유지)
                ticker = await self.client.futures_symbol_ticker(symbol=settings.SYMBOL)
                current_price = float(ticker["price"])

                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute(
                        "SELECT order_id, symbol, side, entry_price, quantity FROM active_positions"
                    )
                    active_rows = await cursor.fetchall()

                for order_id, symbol, side, entry_price, qty in active_rows:
                    # TP/SL 가격 계산
                    if side == "BUY":
                        tp_price = entry_price * (1 + settings.TP_PCT)
                        sl_price = entry_price * (1 - settings.SL_PCT)
                        if current_price >= tp_price or current_price <= sl_price:
                            # 시장가 청산 (반대 매매)
                            market_side = "SELL"
                            market_order = await self.client.futures_create_order(
                                symbol=symbol,
                                side=market_side,
                                type="MARKET",
                                quantity=f"{qty:.6f}",
                            )
                            exit_price = float(market_order["fills"][0]["price"])
                            pnl = (exit_price - entry_price) * qty

                            # 2-1) closed_positions에 기록
                            async with aiosqlite.connect(self.db_path) as db:
                                await db.execute(
                                    """
                                    INSERT INTO closed_positions
                                    (order_id, symbol, side, entry_price, exit_price, quantity, pnl)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (order_id, symbol, side, entry_price, exit_price, qty, pnl)
                                )
                                # 2-2) active_positions에서 삭제
                                await db.execute(
                                    "DELETE FROM active_positions WHERE order_id = ?",
                                    (order_id,)
                                )
                                await db.commit()

                            log.info(f"[PositionManager] Closed LONG {order_id} @ {exit_price} / PnL={pnl:.6f}")

                    elif side == "SELL":
                        tp_price = entry_price * (1 - settings.TP_PCT)
                        sl_price = entry_price * (1 + settings.SL_PCT)
                        if current_price <= tp_price or current_price >= sl_price:
                            market_side = "BUY"
                            market_order = await self.client.futures_create_order(
                                symbol=symbol,
                                side=market_side,
                                type="MARKET",
                                quantity=f"{qty:.6f}",
                            )
                            exit_price = float(market_order["fills"][0]["price"])
                            pnl = (entry_price - exit_price) * qty

                            async with aiosqlite.connect(self.db_path) as db:
                                await db.execute(
                                    """
                                    INSERT INTO closed_positions
                                    (order_id, symbol, side, entry_price, exit_price, quantity, pnl)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (order_id, symbol, side, entry_price, exit_price, qty, pnl)
                                )
                                await db.execute(
                                    "DELETE FROM active_positions WHERE order_id = ?",
                                    (order_id,)
                                )
                                await db.commit()

                            log.info(f"[PositionManager] Closed SHORT {order_id} @ {exit_price} / PnL={pnl:.6f}")

                # ── 3) 전체 PnL 누적 합계 로그 (선택사항) ─────────────────────────────────────
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("SELECT SUM(pnl) FROM closed_positions")
                    row = await cursor.fetchone()
                    total_pnl = row[0] or 0.0
                log.info(f"[PositionManager] Total closed PnL so far = {total_pnl:.6f}")

                await asyncio.sleep(1.0)  # 1초마다 체크
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"[PositionManager] Exception in monitor loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)

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