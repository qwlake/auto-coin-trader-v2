import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

# Add the project root to sys.path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from executor.order_executor import (
    inject_client, 
    get_symbol_ticker, 
    get_open_orders,
    place_limit_maker,
    get_order,
    place_market_order
)
from config.settings import settings


class TestOrderExecutor:
    """Test cases for order_executor module"""
    
    def setup_method(self):
        """Setup before each test"""
        # Reset client
        import executor.order_executor
        executor.order_executor.client = None
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock AsyncClient"""
        client = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_get_symbol_ticker_success(self, mock_client):
        """Test successful symbol ticker retrieval"""
        # Setup
        inject_client(mock_client)
        mock_client.futures_symbol_ticker.return_value = {"price": "50000.50"}
        
        # Execute
        with patch.object(settings, 'DRY_RUN', False):
            result = await get_symbol_ticker("BTCUSDT")
        
        # Assert
        assert result["price"] == "50000.50"
        mock_client.futures_symbol_ticker.assert_called_once_with(symbol="BTCUSDT")
    
    @pytest.mark.asyncio
    async def test_get_symbol_ticker_dry_run(self):
        """Test symbol ticker in DRY_RUN mode"""
        with patch.object(settings, 'DRY_RUN', True):
            result = await get_symbol_ticker("BTCUSDT")
            assert result["price"] == "50000.0"
    
    @pytest.mark.asyncio
    async def test_get_open_orders_success(self, mock_client):
        """Test successful open orders retrieval"""
        # Setup
        inject_client(mock_client)
        expected_orders = [
            {"orderId": 12345, "symbol": "BTCUSDT", "side": "BUY", "status": "NEW"},
            {"orderId": 12346, "symbol": "BTCUSDT", "side": "SELL", "status": "NEW"}
        ]
        mock_client.futures_get_open_orders.return_value = expected_orders
        
        # Execute
        with patch.object(settings, 'DRY_RUN', False):
            result = await get_open_orders()
        
        # Assert
        assert result == expected_orders
        mock_client.futures_get_open_orders.assert_called_once_with(symbol=settings.SYMBOL)
    
    @pytest.mark.asyncio
    async def test_get_open_orders_dry_run(self):
        """Test get_open_orders in DRY_RUN mode"""
        with patch.object(settings, 'DRY_RUN', True):
            result = await get_open_orders()
            assert result == []
    
    @pytest.mark.asyncio
    async def test_get_order_success(self, mock_client):
        """Test successful order status retrieval"""
        # Setup
        inject_client(mock_client)
        expected_order = {
            "orderId": 12345,
            "symbol": "BTCUSDT",
            "status": "FILLED",
            "avgPrice": "50000.00",
            "executedQty": "0.001000"
        }
        mock_client.futures_get_order.return_value = expected_order
        
        # Execute
        with patch.object(settings, 'DRY_RUN', False):
            result = await get_order("BTCUSDT", 12345)
        
        # Assert
        assert result == expected_order
        mock_client.futures_get_order.assert_called_once_with(symbol="BTCUSDT", orderId=12345)
    
    @pytest.mark.asyncio
    async def test_get_order_dry_run(self):
        """Test get_order in DRY_RUN mode"""
        with patch.object(settings, 'DRY_RUN', True):
            result = await get_order("BTCUSDT", 12345)
            assert result["orderId"] == 12345
            assert result["symbol"] == "BTCUSDT"
            assert result["status"] == "NEW"
    
    @pytest.mark.asyncio
    async def test_place_market_order_success(self, mock_client):
        """Test successful market order placement"""
        # Setup
        inject_client(mock_client)
        expected_order = {
            "orderId": 12345,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "fills": [{"price": "50000.00"}]
        }
        mock_client.futures_create_order.return_value = expected_order
        
        # Execute
        with patch.object(settings, 'DRY_RUN', False):
            result = await place_market_order("BTCUSDT", "BUY", "0.001000")
        
        # Assert
        assert result == expected_order
        mock_client.futures_create_order.assert_called_once_with(
            symbol="BTCUSDT",
            side="BUY",
            type="MARKET",
            quantity="0.001000"
        )
    
    @pytest.mark.asyncio
    async def test_place_market_order_dry_run(self):
        """Test place_market_order in DRY_RUN mode"""
        with patch.object(settings, 'DRY_RUN', True):
            result = await place_market_order("BTCUSDT", "BUY", "0.001000")
            assert result["orderId"] == -1
            assert result["symbol"] == "BTCUSDT"
            assert result["side"] == "BUY"
            assert result["type"] == "MARKET"
    
    @pytest.mark.asyncio
    async def test_place_limit_maker_dry_run(self):
        """Test place_limit_maker in DRY_RUN mode"""
        with patch.object(settings, 'DRY_RUN', True):
            with patch.object(settings, 'SIZE_QUOTE', 100.0):
                with patch.object(settings, 'SYMBOL', 'BTCUSDT'):
                    result = await place_limit_maker("BUY", 50000.0)
                    assert result["orderId"] == -1
                    assert result["symbol"] == "BTCUSDT"
                    assert result["side"] == "BUY"
                    assert result["type"] == "LIMIT"
    
    @pytest.mark.asyncio
    async def test_client_not_injected_error(self):
        """Test error when client is not injected"""
        # Don't inject client
        with patch.object(settings, 'DRY_RUN', False):
            with pytest.raises(AssertionError, match="AsyncClient"):
                await get_symbol_ticker("BTCUSDT")
    
    def test_inject_client(self, mock_client):
        """Test client injection"""
        inject_client(mock_client)
        import executor.order_executor
        assert executor.order_executor.client == mock_client


if __name__ == "__main__":
    pytest.main([__file__, "-v"])