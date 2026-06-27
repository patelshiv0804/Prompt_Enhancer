from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class HealthCheckResult:
    healthy: bool
    details: Optional[str] = None


@dataclass
class PromptAnalysisResult:
    clarity: float
    context: float
    specificity: float
    constraints: float
    output_structure: float
    strengths: str
    weaknesses: str
    recommendations: str
    grade: str


@dataclass
class PromptOptimizationResult:
    optimized_prompt: str
    template_id: str
    score: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass
class GenerationResult:
    text: str
    metadata: Optional[dict[str, Any]] = None
