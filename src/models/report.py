"""
Report data models.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RecommendationType(str, Enum):
    """Investment recommendation types."""

    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class DCFScenario(BaseModel):
    """A single DCF scenario (bull / base / bear).

    F3 fix (prd.md §4, architecture.md §3.3, tasks.md Phase 4).
    Fields mirror run_dcf_analysis()'s per-scenario return shape so that wiring
    is plumbing, not redesign.  Every value field includes its assumption so that
    a bare dollar figure is never shown without context (skill rule #1,
    design.md §2, rules.md R1).
    """

    growth_rate: float = 0.0          # % pa, e.g. 10.0 means 10%
    terminal_growth: float = 0.0      # % pa terminal growth assumption
    intrinsic_value: float = 0.0      # per-share intrinsic value ($)
    upside_pct: float = 0.0           # vs current price (%)
    wacc_pct: Optional[float] = None  # WACC used (%), carried so it's always visible


class Recommendation(BaseModel):
    """Investment recommendation."""

    action: RecommendationType = RecommendationType.HOLD
    confidence: float = Field(default=0.5, ge=0, le=1)
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    time_horizon: str = "medium_term"
    reasoning: str = ""
    risks: List[str] = Field(default_factory=list)
    catalysts: List[str] = Field(default_factory=list)

    # F3: scenario and sensitivity fields (Optional — non-DCF paths leave these None)
    scenario_analysis: Optional[Dict[str, DCFScenario]] = None
    recommendation_sensitivity: Optional[Dict[str, Any]] = None



class ReportSection(BaseModel):
    """A section in the research report."""

    title: str
    content: str
    data: Dict[str, Any] = Field(default_factory=dict)
    charts: List[str] = Field(default_factory=list)


class ResearchReport(BaseModel):
    """Complete investment research report."""

    report_id: str = ""
    symbol: str
    company_name: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    analyst: str = "AI Financial Research Agent"

    executive_summary: str = ""
    recommendation: Recommendation = Field(default_factory=Recommendation)

    sections: List[ReportSection] = Field(default_factory=list)

    # Analysis summaries
    technical_summary: str = ""
    fundamental_summary: str = ""
    sentiment_summary: str = ""
    risk_summary: str = ""

    # Key metrics
    current_price: float = 0.0
    fair_value_estimate: Optional[float] = None
    upside_potential: Optional[float] = None

    # Metadata
    data_sources: List[str] = Field(default_factory=list)
    disclaimers: str = (
        "This report is for informational purposes only and does not constitute investment advice."
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    def to_markdown(self) -> str:
        """Convert report to markdown format."""
        md = []
        md.append(f"# Investment Research Report: {self.symbol}")
        md.append(f"**Company:** {self.company_name}")
        md.append(f"**Date:** {self.generated_at.strftime('%Y-%m-%d')}")
        md.append(f"**Analyst:** {self.analyst}")
        md.append("")
        md.append("---")
        md.append("")
        md.append("## Executive Summary")
        md.append(self.executive_summary)
        md.append("")
        md.append("## Recommendation")
        md.append(f"**Action:** {self.recommendation.action.value}")
        md.append(f"**Confidence:** {self.recommendation.confidence * 100:.0f}%")
        if self.recommendation.target_price:
            md.append(f"**Target Price:** ${self.recommendation.target_price:.2f}")
        md.append(f"**Reasoning:** {self.recommendation.reasoning}")
        md.append("")

        # F3: Scenario Analysis section — only renders when populated.
        # Every dollar figure carries its assumption inline (skill rule #1, design.md §2).
        if self.recommendation.scenario_analysis:
            md.append("## Scenario Analysis")
            for name, sc in self.recommendation.scenario_analysis.items():
                wacc_note = f", {sc.wacc_pct:.1f}% WACC" if sc.wacc_pct is not None else ""
                md.append(
                    f"**{name.capitalize()} Case:** "
                    f"${sc.intrinsic_value:.2f} ({sc.upside_pct:+.1f}% upside) — "
                    f"assumes {sc.growth_rate:.1f}% growth, "
                    f"{sc.terminal_growth:.1f}% terminal{wacc_note}"
                )
            if self.recommendation.recommendation_sensitivity:
                sens = self.recommendation.recommendation_sensitivity
                robust_str = "Robust" if sens.get("robust") else "Fragile"
                most = sens.get("most_sensitive_input", "")
                md.append("")
                md.append(
                    f"**Recommendation Sensitivity:** {robust_str} — "
                    f"most sensitive to '{most}' score"
                )
            md.append("")

        for section in self.sections:
            md.append(f"## {section.title}")
            md.append(section.content)
            md.append("")

        md.append("---")
        md.append(f"*{self.disclaimers}*")

        return "\n".join(md)

    def to_text(self) -> str:
        """Convert report to plain text format."""
        lines = []
        lines.append("=" * 80)
        lines.append(f"INVESTMENT RESEARCH REPORT: {self.symbol}")
        lines.append("=" * 80)
        lines.append(f"Company: {self.company_name}")
        lines.append(f"Date: {self.generated_at.strftime('%Y-%m-%d')}")
        lines.append("-" * 80)
        lines.append("")
        lines.append("EXECUTIVE SUMMARY")
        lines.append("-" * 40)
        lines.append(self.executive_summary)
        lines.append("")
        lines.append("RECOMMENDATION")
        lines.append("-" * 40)
        lines.append(f"Action: {self.recommendation.action.value}")
        lines.append(f"Confidence: {self.recommendation.confidence * 100:.0f}%")
        lines.append("")

        # F3: Scenario Analysis section — only renders when populated.
        # Every value line carries its assumption (skill rule #1, design.md §3).
        if self.recommendation.scenario_analysis:
            lines.append("SCENARIO ANALYSIS")
            lines.append("-" * 40)
            for name, sc in self.recommendation.scenario_analysis.items():
                wacc_note = f", {sc.wacc_pct:.1f}% WACC" if sc.wacc_pct is not None else ""
                lines.append(
                    f"{name.capitalize():<5}  "
                    f"${sc.intrinsic_value:.2f}  "
                    f"({sc.upside_pct:+.1f}% upside, "
                    f"{sc.growth_rate:.1f}% growth assumed{wacc_note})"
                )
            if self.recommendation.recommendation_sensitivity:
                sens = self.recommendation.recommendation_sensitivity
                robust_str = "Robust" if sens.get("robust") else "Fragile"
                most = sens.get("most_sensitive_input", "")
                lines.append("")
                lines.append(
                    f"Recommendation sensitivity: {robust_str} "
                    f"(most sensitive to '{most}')"
                )
            lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)
