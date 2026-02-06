"""
Epoch D.1 — Research Provider Interfaces

Deterministic mock providers for context gathering.
Real providers will be added in Epoch D.2.
"""
from datetime import datetime, timezone, timedelta
from typing import Protocol, Any
from dataclasses import dataclass


# ============================================================================
# PROVIDER DATA MODELS
# ============================================================================

@dataclass(frozen=True)
class NewsItem:
    """Single news headline."""
    source_id: str
    title: str
    snippet: str
    url: str
    published_at: datetime
    reliability_tier: str  # TIER_1, TIER_2, UNKNOWN


@dataclass(frozen=True)
class CalendarEvent:
    """Scheduled macro event."""
    event_id: str
    event_type: str  # FOMC, CPI, NFP, etc.
    title: str
    scheduled_at: datetime
    impact_level: str  # HIGH, MEDIUM, LOW


@dataclass(frozen=True)
class GlobalIndex:
    """Global market index snapshot."""
    symbol: str
    value: float
    change_pct_24h: float


# ============================================================================
# PROVIDER PROTOCOLS
# ============================================================================

class NewsProvider(Protocol):
    """News headlines provider interface."""
    
    def fetch_headlines(self, limit: int = 10) -> list[NewsItem]:
        """Fetch recent news headlines."""
        ...
    
    @property
    def provider_version(self) -> str:
        """Provider version for auditing."""
        ...


class CalendarProvider(Protocol):
    """Economic calendar provider interface."""
    
    def fetch_upcoming_events(self, hours: int = 24) -> list[CalendarEvent]:
        """Fetch upcoming macro events."""
        ...
    
    @property
    def provider_version(self) -> str:
        """Provider version for auditing."""
        ...


class MarketDataProvider(Protocol):
    """Market data provider interface."""
    
    def fetch_global_indices(self) -> dict[str, GlobalIndex]:
        """Fetch global market indices (SPX, VIX, DXY, etc.)."""
        ...
    
    @property
    def provider_version(self) -> str:
        """Provider version for auditing."""
        ...


class LLMAnalyst(Protocol):
    """LLM analyst interface (for extract/judge stages)."""
    
    def generate_json(self, prompt: str, timeout_s: float = 10.0) -> str:
        """Generate JSON response from LLM."""
        ...
    
    @property
    def model_version(self) -> str:
        """Model version for auditing."""
        ...


# ============================================================================
# MOCK IMPLEMENTATIONS (Deterministic for D.1)
# ============================================================================

class MockNewsProvider:
    """Deterministic news provider with stable fixtures."""
    
    def __init__(self, scenario: str = "normal"):
        """
        Initialize with predefined scenario.
        
        Scenarios:
        - normal: Quiet market day
        - fomc_day: FOMC meeting today
        - war: War declaration
        - exchange_outage: Exchange downtime
        - cpi_soon: CPI release tomorrow
        """
        self.scenario = scenario
        self._base_time = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)
    
    def fetch_headlines(self, limit: int = 10) -> list[NewsItem]:
        """Return deterministic fixture based on scenario."""
        fixtures = self._get_scenario_fixtures()
        return fixtures[:limit]
    
    def _get_scenario_fixtures(self) -> list[NewsItem]:
        """Generate fixtures for current scenario."""
        base = [
            NewsItem(
                source_id="news_1_normal",
                title="Markets open higher on earnings optimism",
                snippet="Major indices gain as tech earnings beat expectations",
                url="https://example.com/news/1",
                published_at=self._base_time - timedelta(hours=2),
                reliability_tier="TIER_2"
            ),
            NewsItem(
                source_id="news_2_normal",
                title="Fed signals data-dependent approach",
                snippet="Central bank maintains cautious stance on policy",
                url="https://example.com/news/2",
                published_at=self._base_time - timedelta(hours=4),
                reliability_tier="TIER_1"
            ),
        ]
        
        if self.scenario == "war":
            base.insert(0, NewsItem(
                source_id="news_war_1",
                title="BREAKING: Military conflict escalates in region",
                snippet="Armed forces engage in hostilities, markets react",
                url="https://example.com/news/war",
                published_at=self._base_time - timedelta(minutes=30),
                reliability_tier="TIER_1"
            ))
        
        elif self.scenario == "exchange_outage":
            base.insert(0, NewsItem(
                source_id="news_outage_1",
                title="Major exchange reports technical issues",
                snippet="Trading halted due to system failure",
                url="https://example.com/news/outage",
                published_at=self._base_time - timedelta(minutes=15),
                reliability_tier="TIER_1"
            ))
        
        elif self.scenario == "cpi_soon":
            base.insert(0, NewsItem(
                source_id="news_cpi_1",
                title="CPI report due tomorrow, consensus at 3.2%",
                snippet="Economists expect inflation data to show cooling",
                url="https://example.com/news/cpi",
                published_at=self._base_time - timedelta(hours=6),
                reliability_tier="TIER_1"
            ))
        
        return base
    
    @property
    def provider_version(self) -> str:
        return f"mock_news_v1_scenario_{self.scenario}"


class MockCalendarProvider:
    """Deterministic calendar provider."""
    
    def __init__(self, scenario: str = "normal"):
        self.scenario = scenario
        self._base_time = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)
    
    def fetch_upcoming_events(self, hours: int = 24) -> list[CalendarEvent]:
        """Return deterministic events."""
        events = []
        
        if self.scenario == "fomc_day":
            events.append(CalendarEvent(
                event_id="fomc_20260205",
                event_type="FOMC",
                title="FOMC Meeting Decision",
                scheduled_at=self._base_time + timedelta(hours=2),
                impact_level="HIGH"
            ))
        
        elif self.scenario == "cpi_soon":
            events.append(CalendarEvent(
                event_id="cpi_20260206",
                event_type="CPI",
                title="Consumer Price Index",
                scheduled_at=self._base_time + timedelta(hours=22),
                impact_level="HIGH"
            ))
        
        # Always include a low-impact event
        events.append(CalendarEvent(
            event_id="pmi_20260206",
            event_type="PMI",
            title="Manufacturing PMI",
            scheduled_at=self._base_time + timedelta(hours=30),
            impact_level="MEDIUM"
        ))
        
        return events
    
    @property
    def provider_version(self) -> str:
        return f"mock_calendar_v1_scenario_{self.scenario}"


class MockMarketDataProvider:
    """Deterministic market data provider."""
    
    def __init__(self, scenario: str = "normal"):
        self.scenario = scenario
    
    def fetch_global_indices(self) -> dict[str, GlobalIndex]:
        """Return deterministic index values."""
        if self.scenario == "war":
            # Risk-off: equities down, VIX up
            return {
                "SPX": GlobalIndex("SPX", 4800.0, -2.5),
                "VIX": GlobalIndex("VIX", 22.5, +45.0),
                "DXY": GlobalIndex("DXY", 104.2, +0.8),
            }
        elif self.scenario == "exchange_outage":
            # Chaos: high volatility
            return {
                "SPX": GlobalIndex("SPX", 4950.0, -1.2),
                "VIX": GlobalIndex("VIX", 28.0, +60.0),
                "DXY": GlobalIndex("DXY", 103.5, +0.3),
            }
        else:
            # Normal: mild positive
            return {
                "SPX": GlobalIndex("SPX", 5050.0, +0.5),
                "VIX": GlobalIndex("VIX", 14.2, -2.0),
                "DXY": GlobalIndex("DXY", 103.0, -0.1),
            }
    
    @property
    def provider_version(self) -> str:
        return f"mock_market_v1_scenario_{self.scenario}"


class MockLLMAnalyst:
    """
    Deterministic LLM analyst (returns canned responses).
    
    For D.1, we use fixture-based responses to ensure determinism.
    Real LLM integration will come in D.2.
    """
    
    def __init__(self, scenario: str = "normal"):
        self.scenario = scenario
    
    def generate_json(self, prompt: str, timeout_s: float = 10.0) -> str:
        """Return deterministic JSON based on prompt type."""
        # Detect prompt type by keywords
        if "Extract FACTS ONLY" in prompt or "evidence" in prompt.lower():
            return self._get_extract_response()
        elif "Analyze the extracted facts" in prompt or "regime" in prompt.lower():
            return self._get_judge_response()
        else:
            raise ValueError(f"Unknown prompt type: {prompt[:50]}")
    
    def _get_extract_response(self) -> str:
        """Stage 1 (Extract) response."""
        if self.scenario == "war":
            return """{
                "evidence": [
                    {
                        "source_id": "news_war_1",
                        "source_type": "NEWS",
                        "title": "BREAKING: Military conflict escalates in region",
                        "reference": "https://example.com/news/war",
                        "published_at": "2026-02-05T11:30:00Z",
                        "snippet": "Armed forces engage in hostilities",
                        "reliability_tier": "TIER_1"
                    }
                ],
                "claims": [
                    {
                        "claim_id": "claim_1",
                        "text": "Military conflict has escalated",
                        "evidence_ids": ["news_war_1"]
                    }
                ],
                "extracted_at": "2026-02-05T12:00:00Z",
                "extract_prompt_hash": "extract_v1_war",
                "context_hash": "ctx_war_123"
            }"""
        else:
            # Normal scenario
            return """{
                "evidence": [
                    {
                        "source_id": "news_1_normal",
                        "source_type": "NEWS",
                        "title": "Markets open higher on earnings optimism",
                        "reference": "https://example.com/news/1",
                        "published_at": "2026-02-05T10:00:00Z",
                        "snippet": "Major indices gain as tech earnings beat",
                        "reliability_tier": "TIER_2"
                    }
                ],
                "claims": [
                    {
                        "claim_id": "claim_1",
                        "text": "Equity markets showing positive momentum",
                        "evidence_ids": ["news_1_normal"]
                    }
                ],
                "extracted_at": "2026-02-05T12:00:00Z",
                "extract_prompt_hash": "extract_v1_normal",
                "context_hash": "ctx_normal_123"
            }"""
    
    def _get_judge_response(self) -> str:
        """Stage 2 (Judge) response."""
        if self.scenario == "war":
            return """{
                "regime": "RISK_OFF",
                "volatility_outlook": "EXPANDING",
                "sentiment_score": -0.7,
                "risk_flags": ["WAR", "GEOPOLITICAL_RISK"],
                "confidence": 0.8,
                "reasoning": "Military conflict drives risk-off sentiment",
                "judge_prompt_hash": "judge_v1_war",
                "context_hash": "ctx_war_123"
            }"""
        elif self.scenario == "fomc_day":
            return """{
                "regime": "NEUTRAL",
                "volatility_outlook": "EXPANDING",
                "sentiment_score": 0.0,
                "risk_flags": ["FOMC_TODAY"],
                "confidence": 0.5,
                "reasoning": "FOMC decision pending, markets cautious",
                "judge_prompt_hash": "judge_v1_fomc",
                "context_hash": "ctx_fomc_123"
            }"""
        else:
            # Normal
            return """{
                "regime": "RISK_ON",
                "volatility_outlook": "STABLE",
                "sentiment_score": 0.4,
                "risk_flags": [],
                "confidence": 0.7,
                "reasoning": "Constructive market backdrop with moderate optimism",
                "judge_prompt_hash": "judge_v1_normal",
                "context_hash": "ctx_normal_123"
            }"""
    
    @property
    def model_version(self) -> str:
        return f"mock_llm_v1_scenario_{self.scenario}"
