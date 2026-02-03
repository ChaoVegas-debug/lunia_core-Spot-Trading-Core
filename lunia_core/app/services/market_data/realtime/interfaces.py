"""
EPOCH D Phase D3.1: WebSocket Client Interfaces
Pluggable architecture: Abstract interface + Mock + CCXTPro
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from .models import TickerUpdate, OrderBookL2


class IWebSocketClient(ABC):
    """
    Abstract WebSocket client interface
    
    Implementations:
    - MockWebSocketClient (for testing)
    - CCXTProClient (for production, requires ccxt.pro)
    """
    
    @abstractmethod
    async def connect(self, exchange: str, market_type: str):
        """
        Connect to exchange WebSocket
        
        Args:
            exchange: Exchange ID (e.g., "binance")
            market_type: Market type ("spot", "swap", "future")
        
        Raises:
            ConnectionError: Connection failed
        """
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from WebSocket"""
        pass
    
    @abstractmethod
    async def watch_ticker(self, symbol: str) -> AsyncIterator[TickerUpdate]:
        """
        Watch ticker updates
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
        
        Yields:
            TickerUpdate
        
        Raises:
            Exception: Stream error
        """
        pass
    
    @abstractmethod
    async def watch_order_book(self, symbol: str, limit: int = 20) -> AsyncIterator[OrderBookL2]:
        """
        Watch order book updates
        
        Args:
            symbol: Trading pair
            limit: L2 depth
        
        Yields:
            OrderBookL2
        
        Raises:
            Exception: Stream error
        """
        pass


class MockWebSocketClient(IWebSocketClient):
    """
    Mock WebSocket client for testing
    
    Does NOT connect to external services.
    Returns deterministic test data.
    """
    
    def __init__(self):
        self.connected = False
        self.exchange = None
        self.market_type = None
        self._ticker_data = []
        self._orderbook_data = []
    
    async def connect(self, exchange: str, market_type: str):
        """Simulate connection"""
        self.exchange = exchange
        self.market_type = market_type
        self.connected = True
    
    async def disconnect(self):
        """Simulate disconnection"""
        self.connected = False
    
    async def watch_ticker(self, symbol: str) -> AsyncIterator[TickerUpdate]:
        """Yield mock ticker updates"""
        import time
        
        for data in self._ticker_data:
            if not self.connected:
                break
            yield data
            await asyncio.sleep(0.01)  # Simulate latency
    
    async def watch_order_book(self, symbol: str, limit: int = 20) -> AsyncIterator[OrderBookL2]:
        """Yield mock orderbook updates"""
        import time
        
        for data in self._orderbook_data:
            if not self.connected:
                break
            yield data
            await asyncio.sleep(0.01)
    
    def inject_ticker(self, update: TickerUpdate):
        """Inject mock ticker data (for testing)"""
        self._ticker_data.append(update)
    
    def inject_orderbook(self, update: OrderBookL2):
        """Inject mock orderbook data (for testing)"""
        self._orderbook_data.append(update)


# CCXTProClient placeholder (requires ccxt.pro)
class CCXTProClient(IWebSocketClient):
    """
    ccxt.pro WebSocket client (PRODUCTION ONLY)
    
    IMPORTANT: Requires `pip install ccxt.pro`
    
    This implementation is NOT used in tests.
    Importing this module is safe (no runtime dependency on ccxt.pro).
    """
    
    def __init__(self):
        self.exchange_instance = None
        self.market_type = None
    
    async def connect(self, exchange: str, market_type: str):
        """
        Connect to exchange via ccxt.pro
        
        NOTE: This will fail if ccxt.pro is not installed.
        Only call this in production environments.
        """
        try:
            import ccxt.pro as ccxtpro
        except ImportError:
            raise ImportError(
                "ccxt.pro is required for CCXTProClient. "
                "Install with: pip install ccxt.pro"
            )
        
        # Initialize exchange
        exchange_class = getattr(ccxtpro, exchange)
        self.exchange_instance = exchange_class({
            'enableRateLimit': True,
            'options': {'defaultType': market_type}
        })
        
        self.market_type = market_type
        
        # Load markets
        await self.exchange_instance.load_markets()
    
    async def disconnect(self):
        """Close exchange connection"""
        if self.exchange_instance:
            await self.exchange_instance.close()
    
    async def watch_ticker(self, symbol: str) -> AsyncIterator[TickerUpdate]:
        """Watch ticker via ccxt.pro"""
        import time
        
        while True:
            ticker = await self.exchange_instance.watch_ticker(symbol)
            
            yield TickerUpdate(
                exchange=self.exchange_instance.id,
                symbol=symbol,
                market_type=self.market_type,
                bid=ticker.get('bid'),
                ask=ticker.get('ask'),
                last=ticker.get('last'),
                timestamp_ms=ticker.get('timestamp'),
                received_at_ms=int(time.time() * 1000)
            )
    
    async def watch_order_book(self, symbol: str, limit: int = 20) -> AsyncIterator[OrderBookL2]:
        """Watch order book via ccxt.pro"""
        import time
        from .models import PriceLevel
        
        while True:
            orderbook = await self.exchange_instance.watch_order_book(symbol, limit=limit)
            
            yield OrderBookL2(
                exchange=self.exchange_instance.id,
                symbol=symbol,
                market_type=self.market_type,
                bids=[PriceLevel(price=float(b[0]), amount=float(b[1])) for b in orderbook.get('bids', [])],
                asks=[PriceLevel(price=float(a[0]), amount=float(a[1])) for b in orderbook.get('asks', [])],
                timestamp_ms=orderbook.get('timestamp'),
                received_at_ms=int(time.time() * 1000)
            )


# Import guard for asyncio
import asyncio
