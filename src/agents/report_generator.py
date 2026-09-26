from datetime import timezone

"""
Report Generator Agent for the Financial Research Analyst.

This agent generates comprehensive investment research reports.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool, tool

from src.agents.base import BaseAgent
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _recommendation_sensitivity(
    score_data: Dict[str, float],
    weights: Dict[str, float],
    perturbation: float = 0.1,
) -> Dict[str, Any]:
    """Compute how sensitive the recommendation label is to a ±perturbation of each input.

    Implements F2 fix (prd.md §4, architecture.md §3.2, tasks.md Phase 3).
    OD-2 resolved: ±0.1 one-at-a-time perturbation (default).

    This is SEPARATE from BaseAgent._extract_confidence(), which parses LLM
    free-text confidence scores via regex — they solve different problems and
    must not be conflated (architecture.md §2).

    Args:
        score_data: Dict with keys 'technical', 'fundamental', 'sentiment', 'risk'
                    (each a float in [0, 1]).
        weights:    The same weights dict used to compute the composite.
        perturbation: How much to shift each score up/down (default 0.1 = 10pp).

    Returns:
        Dict with:
        - 'robust' (bool): True if the label is stable under all perturbations.
        - 'most_sensitive_input' (str): The input whose perturbation causes the
          biggest composite shift.
        - 'sensitivity_detail' (dict): Per-input breakdown showing ±composite and
          whether the label changes.
    """
    def _label(composite: float) -> str:
        if composite >= 0.7:
            return "STRONG BUY"
        elif composite >= 0.55:
            return "BUY"
        elif composite >= 0.45:
            return "HOLD"
        elif composite >= 0.3:
            return "SELL"
        return "STRONG SELL"

    def _composite(scores: Dict[str, float]) -> float:
        return (
            scores.get("technical", 0.5) * weights["technical"]
            + scores.get("fundamental", 0.5) * weights["fundamental"]
            + scores.get("sentiment", 0.5) * weights["sentiment"]
            + (1 - scores.get("risk", 0.5)) * weights["risk"]
        )

    base = _composite(score_data)
    base_label = _label(base)

    detail: Dict[str, Any] = {}
    max_impact = 0.0
    most_sensitive = ""
    any_label_change = False

    for inp in ("technical", "fundamental", "sentiment", "risk"):
        results_for_inp = {}
        for sign, suffix in ((+1, "up"), (-1, "down")):
            perturbed = dict(score_data)
            perturbed[inp] = max(0.0, min(1.0, score_data.get(inp, 0.5) + sign * perturbation))
            c = _composite(perturbed)
            lbl = _label(c)
            changed = lbl != base_label
            results_for_inp[suffix] = {
                "composite": round(c, 4),
                "label": lbl,
                "label_changed": changed,
            }
            if changed:
                any_label_change = True
            impact = abs(c - base)
            if impact > max_impact:
                max_impact = impact
                most_sensitive = inp
        detail[inp] = results_for_inp

    return {
        "robust": not any_label_change,
        "most_sensitive_input": most_sensitive,
        "sensitivity_detail": detail,
    }


class ReportGeneratorAgent(BaseAgent):
    """Agent specialized in generating investment research reports."""

    def __init__(self, **kwargs):
        super().__init__(
            name="ReportGenerator",
            description="Generates comprehensive investment research reports",
            **kwargs,
        )

    def _get_default_tools(self) -> List[BaseTool]:
        """Get report generation tools."""

        @tool("format_report_section")
        def format_report_section_tool(section_name: str, content: str) -> str:
            """Format a report section with proper headers."""
            separator = "=" * 80
            return f"\n{separator}\n{section_name.upper()}\n{separator}\n{content}\n"

        @tool("generate_executive_summary")
        def generate_executive_summary_tool(analysis_data: str) -> str:
            """Generate an executive summary from analysis data."""
            import json

            data = json.loads(analysis_data) if isinstance(analysis_data, str) else analysis_data

            symbol = data.get("symbol", "UNKNOWN")
            recommendation = data.get("recommendation", "HOLD")
            confidence = data.get("confidence", 0.5)

            return f"""
EXECUTIVE SUMMARY - {symbol}
{'=' * 40}
Recommendation: {recommendation}
Confidence Level: {confidence * 100:.0f}%
Analysis Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}

Key Findings:
\u2022 Technical Analysis: {data.get('technical_summary', 'N/A')}
\u2022 Fundamental Analysis: {data.get('fundamental_summary', 'N/A')}
\u2022 Sentiment Analysis: {data.get('sentiment_summary', 'N/A')}
\u2022 Risk Assessment: {data.get('risk_summary', 'N/A')}
"""

        @tool("generate_recommendation")
        def generate_recommendation_tool(scores: str) -> Dict[str, Any]:
            """Generate investment recommendation from scores.

            Returns the composite recommendation label, composite score (as
            'confidence'), and a sensitivity assessment showing whether the label
            is robust or fragile to a ±0.1 perturbation of each input score (F2
            fix, architecture.md §3.2).  The 'sensitivity' key is distinct from
            BaseAgent._extract_confidence()'s per-agent LLM confidence score.
            """
            import json

            score_data = json.loads(scores) if isinstance(scores, str) else scores

            technical = score_data.get("technical", 0.5)
            fundamental = score_data.get("fundamental", 0.5)
            sentiment = score_data.get("sentiment", 0.5)
            risk = score_data.get("risk", 0.5)

            # F4: weights now read from config (src/config.py AgentSettings).
            # Populated at call time so tests can patch get_settings cleanly.
            from src.config import get_settings
            cfg_weights = get_settings().agent.confidence_weights
            weights = {
                "technical": cfg_weights.get("technical", 0.25),
                "fundamental": cfg_weights.get("fundamental", 0.35),
                "sentiment": cfg_weights.get("sentiment", 0.20),
                "risk": cfg_weights.get("risk", 0.20),
            }

            composite = (
                technical * weights["technical"]
                + fundamental * weights["fundamental"]
                + sentiment * weights["sentiment"]
                + (1 - risk) * weights["risk"]
            )

            if composite >= 0.7:
                recommendation = "STRONG BUY"
            elif composite >= 0.55:
                recommendation = "BUY"
            elif composite >= 0.45:
                recommendation = "HOLD"
            elif composite >= 0.3:
                recommendation = "SELL"
            else:
                recommendation = "STRONG SELL"

            # F2: sensitivity — separate from BaseAgent._extract_confidence()
            normalised = {
                "technical": technical,
                "fundamental": fundamental,
                "sentiment": sentiment,
                "risk": risk,
            }
            sensitivity = _recommendation_sensitivity(normalised, weights)

            return {
                "recommendation": recommendation,
                "confidence": round(composite, 2),
                "composite_score": round(composite, 2),
                "sensitivity": sensitivity,
            }

        return [
            format_report_section_tool,
            generate_executive_summary_tool,
            generate_recommendation_tool,
        ]

    def _get_system_prompt(self) -> str:
        return """You are a Report Generator Agent. Create professional investment research reports including:
1. Executive Summary with key findings
2. Detailed analysis sections
3. Investment recommendations with reasoning
4. Risk disclosures and caveats
Use clear, professional language suitable for institutional investors."""

    async def generate_report(self, symbol: str, analysis_results: Dict) -> Dict[str, Any]:
        """Generate comprehensive investment report."""
        logger.info(f"Generating report for {symbol}")
        task = f"Generate a comprehensive investment research report for {symbol}."
        result = await self.execute(task)
        return {
            "symbol": symbol,
            "report": result.data.get("output", "") if result.success else None,
        }

    def create_report_dict(self, symbol: str, analyses: Dict[str, Any]) -> Dict[str, Any]:
        """Create structured report dictionary."""
        return {
            "symbol": symbol,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "technical": analyses.get("technical", {}),
            "fundamental": analyses.get("fundamental", {}),
            "sentiment": analyses.get("sentiment", {}),
            "risk": analyses.get("risk", {}),
            "recommendation": analyses.get("recommendation", {}),
        }
