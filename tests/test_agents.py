"""
Tests for the agents module.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.agents.base import AgentResult, AgentState, BaseAgent
from src.agents.data_collector import DataCollectorAgent
from src.agents.fundamental import FundamentalAnalystAgent
from src.agents.risk import RiskAnalystAgent
from src.agents.sentiment import SentimentAnalystAgent
from src.agents.technical import TechnicalAnalystAgent


class TestAgentState:
    """Tests for AgentState model."""

    def test_agent_state_creation(self):
        """Test creating an agent state."""
        state = AgentState(agent_name="TestAgent")
        assert state.agent_name == "TestAgent"
        assert state.status == "idle"
        assert state.current_task is None
        assert state.messages == []
        assert state.results == {}

    def test_agent_state_update(self):
        """Test updating agent state."""
        state = AgentState(agent_name="TestAgent")
        state.status = "running"
        state.current_task = "Analyze AAPL"

        assert state.status == "running"
        assert state.current_task == "Analyze AAPL"


class TestAgentResult:
    """Tests for AgentResult model."""

    def test_agent_result_success(self):
        """Test successful agent result."""
        result = AgentResult(
            success=True,
            data={"output": "Analysis complete"},
            agent_name="TestAgent",
            execution_time_seconds=1.5,
        )

        assert result.success is True
        assert result.error is None
        assert result.data["output"] == "Analysis complete"

    def test_agent_result_failure(self):
        """Test failed agent result."""
        result = AgentResult(
            success=False,
            error="API error",
            agent_name="TestAgent",
        )

        assert result.success is False
        assert result.error == "API error"

    def test_agent_result_to_dict(self):
        """Test converting result to dictionary."""
        result = AgentResult(
            success=True,
            data={"key": "value"},
            agent_name="TestAgent",
        )

        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict["success"] is True
        assert "timestamp" in result_dict


class TestDataCollectorAgent:
    """Tests for DataCollectorAgent."""

    def test_agent_initialization(self):
        """Test agent initializes correctly."""
        with patch("src.agents.base.BaseAgent._create_default_llm"):
            agent = DataCollectorAgent()

            assert agent.name == "DataCollector"
            assert agent.state.status == "idle"

    def test_agent_has_tools(self):
        """Test agent has required tools."""
        with patch("src.agents.base.BaseAgent._create_default_llm"):
            agent = DataCollectorAgent()

            tool_names = [t.name for t in agent.tools]
            assert "get_stock_price" in tool_names
            assert "get_historical_data" in tool_names


class TestTechnicalAnalystAgent:
    """Tests for TechnicalAnalystAgent."""

    def test_agent_initialization(self):
        """Test agent initializes correctly."""
        with patch("src.agents.base.BaseAgent._create_default_llm"):
            agent = TechnicalAnalystAgent()

            assert agent.name == "TechnicalAnalyst"

    def test_generate_signals(self):
        """Test signal generation from indicators."""
        with patch("src.agents.base.BaseAgent._create_default_llm"):
            agent = TechnicalAnalystAgent()

            indicators = {
                "rsi": {"value": 25},
                "macd": {"histogram": 0.5, "crossover": "bullish"},
                "moving_averages": {"sma_200": 150},
                "current_price": 160,
            }

            signals = agent.generate_signals(indicators)

            assert "overall" in signals
            assert "confidence" in signals
            assert "individual_signals" in signals


class TestRiskAnalystAgent:
    """Tests for RiskAnalystAgent."""

    def test_agent_initialization(self):
        """Test agent initializes correctly."""
        with patch("src.agents.base.BaseAgent._create_default_llm"):
            agent = RiskAnalystAgent()

            assert agent.name == "RiskAnalyst"

    def test_agent_has_risk_tools(self):
        """Test agent has risk calculation tools."""
        with patch("src.agents.base.BaseAgent._create_default_llm"):
            agent = RiskAnalystAgent()

            tool_names = [t.name for t in agent.tools]
            assert "calculate_volatility" in tool_names
            assert "calculate_var" in tool_names
            assert "calculate_sharpe_ratio" in tool_names


class TestFundamentalAnalystAgent:
    """Tests for FundamentalAnalystAgent."""

    def test_agent_initialization(self):
        """Test agent initializes correctly."""
        with patch("src.agents.base.BaseAgent._create_default_llm"):
            agent = FundamentalAnalystAgent()

            assert agent.name == "FundamentalAnalyst"

    def test_calculate_intrinsic_value(self):
        """Test that calculate_intrinsic_value delegates to get_dcf_summary (dcf_model.py).

        OD-1 resolution (see memory.md D1, tasks.md Phase 2): updated rather than
        retired — the test now asserts on the delegated output shape instead of the
        old crude hardcoded-rate output shape.
        """
        mock_dcf_result = {
            "symbol": "AAPL",
            "current_price": 150.0,
            "wacc": {"wacc": 0.092, "wacc_pct": 9.2},
            "scenarios": {
                "bull": {
                    "intrinsic_value": 210.0,
                    "upside_pct": 40.0,
                    "growth_rate": 12.0,
                    "terminal_growth": 3.0,
                },
                "base": {
                    "intrinsic_value": 170.0,
                    "upside_pct": 13.3,
                    "growth_rate": 10.0,
                    "terminal_growth": 2.5,
                },
                "bear": {
                    "intrinsic_value": 130.0,
                    "upside_pct": -13.3,
                    "growth_rate": 8.0,
                    "terminal_growth": 2.0,
                },
            },
            "margin_of_safety_pct": 13.3,
            "recommendation": "Hold",
        }
        with patch("src.agents.base.BaseAgent._create_default_llm"):
            with patch(
                "src.agents.fundamental.get_dcf_summary",
                return_value=mock_dcf_result,
            ) as mock_dcf:
                agent = FundamentalAnalystAgent()
                result = agent.calculate_intrinsic_value({}, method="dcf", symbol="AAPL")

                mock_dcf.assert_called_once_with("AAPL")
                assert "scenarios" in result
                assert "wacc" in result
                assert "margin_of_safety_pct" in result
                # All three scenarios present
                for scenario in ("bull", "base", "bear"):
                    assert scenario in result["scenarios"]


class TestSentimentAnalystAgent:
    """Tests for SentimentAnalystAgent."""

    def test_agent_initialization(self):
        """Test agent initializes correctly."""
        with patch("src.agents.base.BaseAgent._create_default_llm"):
            agent = SentimentAnalystAgent()

            assert agent.name == "SentimentAnalyst"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
