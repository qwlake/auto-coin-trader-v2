import asyncio
from binance import AsyncClient, BinanceSocketManager
from typing import Optional

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
                bm = BinanceSocketManager(client)
                
                # Create concurrent stream tasks
                self.depth_task = asyncio.create_task(self._run_depth_stream(bm))
                self.trade_task = asyncio.create_task(self._run_trade_stream(bm))
                self.kline_task = asyncio.create_task(self._run_kline_stream(bm))
                
                # Wait for all streams
                await asyncio.gather(
                    self.depth_task,
                    self.trade_task,
                    self.kline_task
                )
            finally:
                await client.close_connection()
                
        except asyncio.CancelledError:
            log.info("EnhancedFuturesStream: cancelled")
            if self.depth_task:
                self.depth_task.cancel()
            if self.trade_task:
                self.trade_task.cancel()
            if self.kline_task:
                self.kline_task.cancel()
            raise
        except Exception as e:
            log.exception("EnhancedFuturesStream error")
            raise e
    
    async def _run_depth_stream(self, bm: BinanceSocketManager):
        """Handle order book depth updates (maintains compatibility with OBI strategy)"""
        try:
            async with bm.futures_depth_socket(self.symbol) as stream:
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
        except asyncio.CancelledError:
            log.debug("Depth stream cancelled")
            raise
        except Exception as e:
            log.error(f"Depth stream error: {e}")
            raise
    
    async def _run_trade_stream(self, bm: BinanceSocketManager):
        """Handle individual trades for VWAP calculation"""
        try:
            async with bm.futures_trade_socket(self.symbol) as stream:
                while True:
                    msg = await stream.recv()
                    price = float(msg['p'])
                    quantity = float(msg['q'])
                    
                    # Update current price
                    self.current_price = price
                    
                    # Update strategy if available
                    if self.strategy:
                        self.strategy.update_trade(price, quantity)
                        
                        # Check for session reset
                        self.strategy.check_session_reset()
                        
        except asyncio.CancelledError:
            log.debug("Trade stream cancelled")
            raise
        except Exception as e:
            log.error(f"Trade stream error: {e}")
            raise
    
    async def _run_kline_stream(self, bm: BinanceSocketManager):
        """Handle kline data for ADX calculation"""
        try:
            async with bm.futures_kline_socket(self.symbol, interval='1m') as stream:
                while True:
                    msg = await stream.recv()
                    kline = msg['k']
                    
                    # Only process closed klines
                    if kline['x']:  # Kline is closed
                        high = float(kline['h'])
                        low = float(kline['l'])
                        close = float(kline['c'])
                        
                        # Update strategy if available
                        if self.strategy:
                            self.strategy.update_kline(high, low, close)
                            
        except asyncio.CancelledError:
            log.debug("Kline stream cancelled")
            raise
        except Exception as e:
            log.error(f"Kline stream error: {e}")
            raise
    
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