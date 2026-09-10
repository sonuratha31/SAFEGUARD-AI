"""
SAFEGUARD AI - Predictive Trend Analysis
Detects and forecasts deteriorating machine conditions.
"""
import logging
import math
from collections import deque
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TrendAnalysis:
    machine_id: str
    parameter: str
    trend: str           # increasing / decreasing / stable
    slope: float         # units per reading (positive = rising)
    confidence: float    # 0–1
    current_value: float
    predicted_1h: float  # [PREDICTION] value in ~1 hour
    predicted_4h: float  # [PREDICTION] value in ~4 hours
    readings_window: int
    is_prediction: bool = True  # Always True — these are forecasts
    explanation: str = ""


class TrendAnalyzer:
    """
    Uses linear regression over a rolling window to detect trends
    and project future values.

    All projected values are clearly labelled as PREDICTIONS.
    """

    def __init__(self, window: int = 30, interval_seconds: int = 5):
        self.window = window
        self.interval_seconds = interval_seconds
        self._buffers: Dict[str, Dict[str, deque]] = {}
        # steps_per_hour = 3600 / interval_seconds
        self._steps_per_hour = 3600 / interval_seconds

    TRACKED_PARAMS = ["temperature", "vibration", "rpm", "pressure", "load"]

    def update(self, machine_id: str, reading: Dict[str, float]) -> Dict[str, TrendAnalysis]:
        """Update buffers and return trend analysis for all tracked parameters."""
        if machine_id not in self._buffers:
            self._buffers[machine_id] = {
                p: deque(maxlen=self.window) for p in self.TRACKED_PARAMS
            }

        for param in self.TRACKED_PARAMS:
            if param in reading:
                self._buffers[machine_id][param].append(reading[param])

        return self._analyze_all(machine_id)

    def _linear_regression(self, values: List[float]) -> Tuple[float, float, float]:
        """
        Returns (slope, intercept, r_squared).
        slope > 0 = increasing, slope < 0 = decreasing.
        """
        n = len(values)
        if n < 3:
            return 0.0, values[-1] if values else 0.0, 0.0

        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(values) / n

        ss_xy = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
        ss_xx = sum((x - mean_x) ** 2 for x in xs)

        if ss_xx == 0:
            return 0.0, mean_y, 0.0

        slope = ss_xy / ss_xx
        intercept = mean_y - slope * mean_x

        # R²
        y_pred = [slope * x + intercept for x in xs]
        ss_res = sum((values[i] - y_pred[i]) ** 2 for i in range(n))
        ss_tot = sum((v - mean_y) ** 2 for v in values)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        return slope, intercept, max(0.0, r_squared)

    def _analyze_all(self, machine_id: str) -> Dict[str, TrendAnalysis]:
        results = {}
        for param in self.TRACKED_PARAMS:
            buf = self._buffers[machine_id][param]
            if len(buf) < 5:
                continue
            values = list(buf)
            slope, intercept, r_sq = self._linear_regression(values)
            current = values[-1]
            n = len(values)

            steps_1h = self._steps_per_hour
            steps_4h = 4 * self._steps_per_hour
            pred_1h = round(intercept + slope * (n + steps_1h), 2)
            pred_4h = round(intercept + slope * (n + steps_4h), 2)

            # Classify trend
            threshold_pct = 0.005  # 0.5% per step considered significant
            if slope > current * threshold_pct:
                trend = "increasing"
            elif slope < -current * threshold_pct:
                trend = "decreasing"
            else:
                trend = "stable"

            explanation = (
                f"[PREDICTION] {param.capitalize()} trend: {trend}. "
                f"Current: {current:.2f}, slope: {slope:+.4f}/step, "
                f"R²={r_sq:.2f}. "
                f"Predicted 1h: {pred_1h:.2f}, 4h: {pred_4h:.2f}."
            )

            results[param] = TrendAnalysis(
                machine_id=machine_id,
                parameter=param,
                trend=trend,
                slope=round(slope, 6),
                confidence=round(r_sq, 3),
                current_value=round(current, 2),
                predicted_1h=pred_1h,
                predicted_4h=pred_4h,
                readings_window=n,
                is_prediction=True,
                explanation=explanation,
            )
        return results


# Module-level singleton
trend_analyzer = TrendAnalyzer()
