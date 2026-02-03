"""
EPOCH D Phase D3.1: Bounded Memory Buffers
Fixed-size buffers with conflation metrics
"""
from __future__ import annotations

from collections import deque
from typing import Generic, TypeVar, Optional

T = TypeVar('T')


class BoundedBuffer(Generic[T]):
    """
    Fixed-size buffer with overflow tracking
    
    Features:
    - Bounded memory (fixed maxsize)
    - Conflation (drops oldest on overflow)
    - Metrics (dropped_count)
    """
    
    def __init__(self, maxsize: int = 1000):
        """
        Initialize buffer
        
        Args:
            maxsize: Maximum buffer size
        """
        self.maxsize = maxsize
        self._buffer: deque[T] = deque(maxlen=maxsize)
        self.dropped_count = 0
    
    def append(self, item: T):
        """
        Append item to buffer
        
        If buffer is full, oldest item is dropped (conflation).
        
        Args:
            item: Item to append
        """
        if len(self._buffer) >= self.maxsize:
            self.dropped_count += 1
        
        self._buffer.append(item)
    
    def get_all(self) -> list[T]:
        """Get all items in buffer (FIFO order)"""
        return list(self._buffer)
    
    def clear(self):
        """Clear buffer and metrics"""
        self._buffer.clear()
        self.dropped_count = 0
    
    def __len__(self) -> int:
        return len(self._buffer)
    
    def is_full(self) -> bool:
        """Check if buffer is full"""
        return len(self._buffer) >= self.maxsize
