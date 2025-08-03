import asyncio
from binance import AsyncClient, BinanceSocketManager
from typing import Optional
import time
import threading

from config.settings import settings
from utils.logger import log


class FuturesDepthStream:
    """Original depth stream for OBI strategy - maintained for backward compatibility"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol.lower()
        self.depth = None

    async def run(self):
        try:
            # Create AsyncClient for futures
            kwargs = {
                "api_key": settings.BINANCE_API_KEY,
                "api_secret": settings.BINANCE_SECRET,
                "testnet": settings.TESTNET,
            }
            client = await AsyncClient.create(**kwargs)
            
            try:
                bm = BinanceSocketManager(client)
                # Use futures depth stream
                async with bm.futures_depth_socket(self.symbol) as stream:
                    while True:
                        msg = await stream.recv()
                        # Transform message to match original format expected by strategy
                        # BinanceSocketManager returns {'bids': [...], 'asks': [...], ...}
                        # but strategy expects {'b': [...], 'a': [...], ...}
                        if 'bids' in msg and 'asks' in msg:
                            self.depth = {
                                'b': msg['bids'],
                                'a': msg['asks']
                            }
            finally:
                await client.close_connection()
        except asyncio.CancelledError:
            log.info("FuturesDepthStream: cancelled")
            raise
        except Exception as e:
            log.exception("FuturesDepthStream error")
            raise e


class EnhancedFuturesStream:
    """
    Enhanced futures stream for VWAP strategy supporting multiple data streams:
    - Depth stream for order book data
    - Trade stream for VWAP calculation
    - Kline stream for ADX calculation
    """
    
    def __init__(self, symbol: str, strategy=None):
        self.symbol = symbol.lower()
        self.strategy = strategy  # VWAP strategy instance
        
        # Data streams
        self.depth = None
        self.current_price = 0.0
        
        # Stream tasks
        self.depth_task = None
        self.trade_task = None
        self.kline_task = None
        
        # Connection monitoring
        self.connection_stats = {
            'reconnect_count': 0,
            'last_reconnect_time': None,
            'total_disconnections': 0,
            'stream_start_time': time.time(),
            'last_depth_update': None,
            'last_trade_update': None,
            'last_kline_update': None
        }
        
        # Health monitoring
        self._health_monitor_task = None
        self._monitoring_active = False
    
    async def run(self):
        """Run multiple WebSocket streams concurrently"""
        try:
            kwargs = {
                "api_key": settings.BINANCE_API_KEY,
                "api_secret": settings.BINANCE_SECRET,
                "testnet": settings.TESTNET,
            }
            client = await AsyncClient.create(**kwargs)
            
            try:
                # VWAP 전략인 경우 ADX 초기화
                if self.strategy and hasattr(self.strategy, 'initialize_adx_with_history'):
                    log.info("[EnhancedFuturesStream] Initializing VWAP strategy ADX with historical data...")
                    await self.strategy.initialize_adx_with_history()
                
                bm = BinanceSocketManager(client)
                
                # Start health monitoring
                self._monitoring_active = True
                self._health_monitor_task = asyncio.create_task(self._monitor_connection_health())
                
                # Create concurrent stream tasks
                self.depth_task = asyncio.create_task(self._run_depth_stream(bm))
                self.trade_task = asyncio.create_task(self._run_trade_stream(bm))
                self.kline_task = asyncio.create_task(self._run_kline_stream(bm))
                
                log.info(f"[EnhancedFuturesStream] All streams started for {self.symbol}")
                
                # Wait for all streams
                await asyncio.gather(
                    self.depth_task,
                    self.trade_task,
                    self.kline_task,
                    self._health_monitor_task
                )
            finally:
                self._monitoring_active = False
                await client.close_connection()
                
        except asyncio.CancelledError:
            log.info("[EnhancedFuturesStream] Stream cancelled")
            self._monitoring_active = False
            if self.depth_task:
                self.depth_task.cancel()
            if self.trade_task:
                self.trade_task.cancel()
            if self.kline_task:
                self.kline_task.cancel()
            if self._health_monitor_task:
                self._health_monitor_task.cancel()
            raise
        except Exception as e:
            log.exception("[EnhancedFuturesStream] Stream error")
            self._monitoring_active = False
            raise e
    
    async def _run_depth_stream(self, bm: BinanceSocketManager):
        """Handle order book depth updates (maintains compatibility with OBI strategy)"""
        retry_count = 0
        max_retries = 5
        base_delay = 1
        
        while retry_count < max_retries:
            try:
                log.info(f"[DepthStream] Starting depth stream (attempt {retry_count + 1})")
                async with bm.futures_depth_socket(self.symbol) as stream:
                    retry_count = 0  # 성공적으로 연결되면 리트라이 카운트 리셋
                    
                    while True:
                        msg = await stream.recv()
                        if 'bids' in msg and 'asks' in msg:
                            self.depth = {
                                'b': msg['bids'],
                                'a': msg['asks']
                            }
                            # Update current price from best bid/ask
                            if len(msg['bids']) > 0 and len(msg['asks']) > 0:
                                bid = float(msg['bids'][0][0])
                                ask = float(msg['asks'][0][0])
                                self.current_price = (bid + ask) / 2
                                
                            # 연결 상태 업데이트
                            self.connection_stats['last_depth_update'] = time.time()
                            
            except asyncio.CancelledError:
                log.info("[DepthStream] Depth stream cancelled")
                raise
            except Exception as e:
                retry_count += 1
                self.connection_stats['total_disconnections'] += 1
                self.connection_stats['last_reconnect_time'] = time.time()
                
                if retry_count >= max_retries:
                    log.error(f"[DepthStream] Max retries ({max_retries}) reached. Giving up.")
                    raise
                
                delay = base_delay * (2 ** (retry_count - 1))  # 지수 백오프
                log.warning(f"[DepthStream] Connection error (attempt {retry_count}/{max_retries}): {e}")
                log.info(f"[DepthStream] Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
    
    async def _run_trade_stream(self, bm: BinanceSocketManager):
        """Handle individual trades for VWAP calculation"""
        retry_count = 0
        max_retries = 5
        base_delay = 1
        
        while retry_count < max_retries:
            try:
                log.info(f"[TradeStream] Starting trade stream (attempt {retry_count + 1})")
                async with bm.aggtrade_futures_socket(self.symbol) as stream:
                    retry_count = 0  # 성공적으로 연결되면 리트라이 카운트 리셋
                    
                    while True:
                        msg = await stream.recv()
                        price = float(msg['data']['p'])
                        quantity = float(msg['data']['q'])
                        
                        # Update current price
                        self.current_price = price
                        
                        # Update strategy if available
                        if self.strategy:
                            self.strategy.update_trade(price, quantity)
                            
                            # Check for session reset
                            self.strategy.check_session_reset()
                        
                        # Update GUI data every few updates (to avoid overwhelming)
                        if hasattr(self, '_gui_update_counter'):
                            self._gui_update_counter += 1
                        else:
                            self._gui_update_counter = 1
                        
                        if self._gui_update_counter % 10 == 0:  # Update every 10 trades
                            self.update_gui_data()
                        
                        # 연결 상태 업데이트
                        self.connection_stats['last_trade_update'] = time.time()
                        
            except asyncio.CancelledError:
                log.info("[TradeStream] Trade stream cancelled")
                raise
            except Exception as e:
                retry_count += 1
                self.connection_stats['total_disconnections'] += 1
                self.connection_stats['last_reconnect_time'] = time.time()
                
                if retry_count >= max_retries:
                    log.error(f"[TradeStream] Max retries ({max_retries}) reached. Giving up.")
                    raise
                
                delay = base_delay * (2 ** (retry_count - 1))  # 지수 백오프
                log.warning(f"[TradeStream] Connection error (attempt {retry_count}/{max_retries}): {e}")
                log.info(f"[TradeStream] Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
    
    async def _run_kline_stream(self, bm: BinanceSocketManager):
        """Handle kline data for ADX calculation"""
        retry_count = 0
        max_retries = 5
        base_delay = 1
        
        while retry_count < max_retries:
            try:
                log.info(f"[KlineStream] Starting kline stream (attempt {retry_count + 1})")
                async with bm.kline_futures_socket(self.symbol, interval='1m') as stream:
                    retry_count = 0  # 성공적으로 연결되면 리트라이 카운트 리셋
                    
                    while True:
                        msg = await stream.recv()
                        kline = msg['k']
                        
                        # Only process closed klines
                        if kline['x']:  # Kline is closed
                            high = float(kline['h'])
                            low = float(kline['l'])
                            close = float(kline['c'])
                            
                            log.debug(f"[KlineStream] Kline closed - H:{high}, L:{low}, C:{close}")
                            
                            # Update strategy if available
                            if self.strategy:
                                old_adx = getattr(self.strategy, 'current_adx', None)
                                self.strategy.update_kline(high, low, close)
                                new_adx = getattr(self.strategy, 'current_adx', None)
                                log.debug(f"[KlineStream] ADX updated from {old_adx} to {new_adx}")
                        
                        # 연결 상태 업데이트
                        self.connection_stats['last_kline_update'] = time.time()
                        
            except asyncio.CancelledError:
                log.info("[KlineStream] Kline stream cancelled")
                raise
            except Exception as e:
                retry_count += 1
                self.connection_stats['total_disconnections'] += 1
                self.connection_stats['last_reconnect_time'] = time.time()
                
                if retry_count >= max_retries:
                    log.error(f"[KlineStream] Max retries ({max_retries}) reached. Giving up.")
                    raise
                
                delay = base_delay * (2 ** (retry_count - 1))  # 지수 백오프
                log.warning(f"[KlineStream] Connection error (attempt {retry_count}/{max_retries}): {e}")
                log.info(f"[KlineStream] Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
    
    def get_indicator_data(self) -> dict:
        """Get current values of all indicators"""
        if self.strategy:
            indicator_data = self.strategy.get_indicator_data()
            indicator_data['current_price'] = self.current_price
            return indicator_data
        else:
            return {
                'current_price': self.current_price,
                'depth_available': self.depth is not None
            }
    
    def update_gui_data(self):
        """GUI 데이터 브로커 업데이트 및 VWAP 히스토리 저장"""
        try:
            # GUI 데이터 브로커가 있는 경우에만 업데이트
            try:
                from gui.data_broker import data_broker
                
                # 현재 가격 업데이트
                data_broker.update_price(self.current_price)
                
                # 전략별 지표 업데이트
                if self.strategy:
                    indicator_data = self.strategy.get_indicator_data()
                    
                    # VWAP 전략 지표
                    if hasattr(self.strategy, 'vwap_calc'):
                        vwap = indicator_data.get('vwap', 0)
                        upper_band = indicator_data.get('upper_band', 0)
                        lower_band = indicator_data.get('lower_band', 0)
                        adx = indicator_data.get('adx')  # None을 허용
                        
                        data_broker.update_indicators(
                            vwap=vwap,
                            upper_band=upper_band,
                            lower_band=lower_band,
                            adx=adx if adx is not None else 0
                        )
                        
                        # 변동성 중단 상태
                        is_halted = indicator_data.get('is_halted', False)
                        data_broker.set_halt_status(is_halted)
                        
                        # 연결 상태 통계 업데이트
                        if hasattr(self, 'get_connection_stats'):
                            connection_stats = self.get_connection_stats()
                            data_broker.update_connection_stats(connection_stats)
                        
                        # VWAP 히스토리 DB 저장 (10초마다)
                        if vwap > 0:
                            self._save_vwap_history_async(vwap, upper_band, lower_band, adx)
                    
                    # 전략 타입 업데이트
                    from config.settings import settings
                    data_broker.update_state(strategy_type=settings.STRATEGY_TYPE)
            except ImportError:
                # GUI 모듈이 없는 경우 무시
                pass
        except Exception as e:
            log.debug(f"GUI update failed: {e}")
    
    def _save_vwap_history_async(self, vwap: float, upper_band: float, lower_band: float, adx: float):
        """VWAP 히스토리를 비동기로 저장 (GUI 스레드를 차단하지 않음)"""
        if not hasattr(self, '_last_vwap_save_time'):
            self._last_vwap_save_time = 0
        
        import time
        current_time = time.time()
        
        # 10초마다만 저장 (과도한 저장 방지)
        if current_time - self._last_vwap_save_time >= 10:
            self._last_vwap_save_time = current_time
            
            # PositionManager 인스턴스를 통해 저장
            try:
                # main.py에서 전역 position_manager에 접근
                import asyncio
                from config.settings import settings
                
                # 비동기 태스크로 실행하여 GUI 스레드 차단 방지
                asyncio.create_task(self._save_vwap_to_db(
                    settings.SYMBOL, vwap, upper_band, lower_band, self.current_price, adx
                ))
                log.debug(f"[VWAPHistory] Saving VWAP data: vwap={vwap:.2f}, adx={adx}")
            except Exception as e:
                log.error(f"Failed to save VWAP history: {e}")
    
    async def _save_vwap_to_db(self, symbol: str, vwap: float, upper_band: float, 
                              lower_band: float, current_price: float, adx: float):
        """VWAP 데이터를 DB에 저장"""
        try:
            import aiosqlite
            
            # ADX 값이 None이면 NULL로 저장, 값이 있으면 그대로 저장
            adx_value = adx if adx is not None else None
            
            async with aiosqlite.connect("storage/orders.db") as db:
                # 현재 윈도우 내 거래 수 계산
                trade_count = 0
                if hasattr(self.strategy, 'vwap_calc'):
                    trade_count = self.strategy.vwap_calc.get_trade_count()
                
                await db.execute(
                    """
                    INSERT INTO vwap_history 
                    (symbol, vwap, upper_band, lower_band, current_price, adx, volume_window_trades)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (symbol, vwap, upper_band, lower_band, current_price, adx_value, trade_count)
                )
                await db.commit()
                log.debug(f"[VWAPHistory] Saved to DB: vwap={vwap:.2f}, bands=[{lower_band:.2f}-{upper_band:.2f}], adx={adx_value}")
        except Exception as e:
            log.error(f"Error saving VWAP history: {e}")
    
    async def _monitor_connection_health(self):
        """연결 상태를 모니터링하고 통계를 로깅"""
        while self._monitoring_active:
            try:
                await asyncio.sleep(30)  # 30초마다 체크
                
                current_time = time.time()
                uptime = current_time - self.connection_stats['stream_start_time']
                
                # 각 스트림의 마지막 업데이트 시간 체크
                depth_lag = None
                trade_lag = None
                kline_lag = None
                
                if self.connection_stats['last_depth_update']:
                    depth_lag = current_time - self.connection_stats['last_depth_update']
                    
                if self.connection_stats['last_trade_update']:
                    trade_lag = current_time - self.connection_stats['last_trade_update']
                    
                if self.connection_stats['last_kline_update']:
                    kline_lag = current_time - self.connection_stats['last_kline_update']
                
                # 상태 로깅
                log.info(f"[ConnectionHealth] Uptime: {uptime/60:.1f}min, Disconnections: {self.connection_stats['total_disconnections']}")
                
                if depth_lag is not None:
                    log.debug(f"[ConnectionHealth] Depth lag: {depth_lag:.1f}s")
                if trade_lag is not None:
                    log.debug(f"[ConnectionHealth] Trade lag: {trade_lag:.1f}s")
                if kline_lag is not None:
                    log.debug(f"[ConnectionHealth] Kline lag: {kline_lag:.1f}s")
                
                # 연결 문제 감지 (60초 이상 업데이트 없음)
                if (depth_lag and depth_lag > 60) or (trade_lag and trade_lag > 60):
                    log.warning(f"[ConnectionHealth] Potential connection issue detected. Depth lag: {depth_lag}s, Trade lag: {trade_lag}s")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"[ConnectionHealth] Health monitor error: {e}")
    
    def get_connection_stats(self) -> dict:
        """연결 통계 정보 반환"""
        current_time = time.time()
        uptime = current_time - self.connection_stats['stream_start_time']
        
        return {
            'uptime_minutes': uptime / 60,
            'total_disconnections': self.connection_stats['total_disconnections'],
            'reconnect_count': self.connection_stats['reconnect_count'],
            'last_reconnect_time': self.connection_stats['last_reconnect_time'],
            'depth_lag': current_time - self.connection_stats['last_depth_update'] if self.connection_stats['last_depth_update'] else None,
            'trade_lag': current_time - self.connection_stats['last_trade_update'] if self.connection_stats['last_trade_update'] else None,
            'kline_lag': current_time - self.connection_stats['last_kline_update'] if self.connection_stats['last_kline_update'] else None
        }