"""
anomaly_detector.py
Statistical anomaly detection: rolling Z-score and Isolation Forest.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Dict, Deque, Optional, List

import numpy as np


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class AnomalyResult:
    is_anomaly: bool
    z_score: float
    severity: str          # "normal" | "anomaly" | "severe_anomaly"
    description: str


# ---------------------------------------------------------------------------
# Z-score detector
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """
    Per-machine, per-metric rolling Z-score anomaly detector.

    Maintains a fixed-size window of recent readings.  Once the window
    contains at least `min_samples` observations the detector begins
    scoring new values.  Until then it returns a non-anomaly result.

    Thresholds
    ----------
    |z| > 3.5  → severe anomaly
    |z| > 2.5  → anomaly
    otherwise  → normal
    """

    SEVERE_THRESHOLD = 3.5
    ANOMALY_THRESHOLD = 2.5

    def __init__(self, window_size: int = 50, min_samples: int = 10) -> None:
        self.window_size = window_size
        self.min_samples = min_samples
        # _windows[machine_id][metric] = deque of recent values
        self._windows: Dict[str, Dict[str, Deque[float]]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, machine_id: str, metric: str, value: float) -> None:
        """Append *value* to the rolling window for (machine_id, metric)."""
        self._ensure_window(machine_id, metric)
        self._windows[machine_id][metric].append(value)

    def detect(self, machine_id: str, metric: str, value: float) -> AnomalyResult:
        """
        Score *value* against the current rolling window.
        Does **not** add the value to the window; call update() separately.
        """
        self._ensure_window(machine_id, metric)
        window = self._windows[machine_id][metric]

        if len(window) < self.min_samples:
            return AnomalyResult(
                is_anomaly=False,
                z_score=0.0,
                severity="normal",
                description=f"Insufficient history for {metric} on {machine_id} "
                            f"({len(window)}/{self.min_samples} samples).",
            )

        arr = np.array(window, dtype=float)
        mean = float(np.mean(arr))
        std = float(np.std(arr))

        if std < 1e-9:
            z_score = 0.0
        else:
            z_score = (value - mean) / std

        abs_z = abs(z_score)

        if abs_z > self.SEVERE_THRESHOLD:
            return AnomalyResult(
                is_anomaly=True,
                z_score=round(z_score, 3),
                severity="severe_anomaly",
                description=(
                    f"Severe anomaly detected on {machine_id}/{metric}: "
                    f"value={value:.3f}, z-score={z_score:.2f} "
                    f"(threshold ±{self.SEVERE_THRESHOLD})."
                ),
            )
        elif abs_z > self.ANOMALY_THRESHOLD:
            return AnomalyResult(
                is_anomaly=True,
                z_score=round(z_score, 3),
                severity="anomaly",
                description=(
                    f"Anomaly detected on {machine_id}/{metric}: "
                    f"value={value:.3f}, z-score={z_score:.2f} "
                    f"(threshold ±{self.ANOMALY_THRESHOLD})."
                ),
            )
        else:
            return AnomalyResult(
                is_anomaly=False,
                z_score=round(z_score, 3),
                severity="normal",
                description=(
                    f"{machine_id}/{metric} is normal: "
                    f"value={value:.3f}, z-score={z_score:.2f}."
                ),
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_window(self, machine_id: str, metric: str) -> None:
        if machine_id not in self._windows:
            self._windows[machine_id] = {}
        if metric not in self._windows[machine_id]:
            self._windows[machine_id][metric] = deque(maxlen=self.window_size)


# ---------------------------------------------------------------------------
# Isolation Forest detector
# ---------------------------------------------------------------------------

try:
    from sklearn.ensemble import IsolationForest  # type: ignore

    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False


class IsolationForestDetector:
    """
    Per-machine, per-metric Isolation Forest anomaly detector.

    The model is trained lazily once `train_after` samples have been
    collected.  Subsequent calls to `detect()` score new readings
    against the trained model.  The model is re-trained whenever
    `retrain_every` additional samples arrive after the initial
    training.

    Falls back to a plain Z-score detector if scikit-learn is not
    installed.
    """

    def __init__(
        self,
        train_after: int = 100,
        retrain_every: int = 200,
        contamination: float = 0.05,
        window_size: int = 500,
    ) -> None:
        if not _SKLEARN_AVAILABLE:
            raise ImportError(
                "scikit-learn is required for IsolationForestDetector. "
                "Install it with: pip install scikit-learn"
            )
        self.train_after = train_after
        self.retrain_every = retrain_every
        self.contamination = contamination
        self.window_size = window_size

        # _buffers[machine_id][metric] = list of floats (unbounded training set)
        self._buffers: Dict[str, Dict[str, List[float]]] = {}
        # _models[machine_id][metric] = fitted IsolationForest
        self._models: Dict[str, Dict[str, IsolationForest]] = {}
        # _sample_counts counts total samples seen since last train
        self._sample_counts: Dict[str, Dict[str, int]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, machine_id: str, metric: str, value: float) -> None:
        """Append *value* to the buffer and re-train if due."""
        self._ensure_buffers(machine_id, metric)
        buf = self._buffers[machine_id][metric]
        buf.append(value)
        # Keep buffer bounded to avoid unlimited memory growth
        if len(buf) > self.window_size:
            self._buffers[machine_id][metric] = buf[-self.window_size:]

        self._sample_counts[machine_id][metric] += 1
        count = self._sample_counts[machine_id][metric]

        should_train = (
            count == self.train_after
            or (count > self.train_after and (count - self.train_after) % self.retrain_every == 0)
        )
        if should_train:
            self._train(machine_id, metric)

    def detect(self, machine_id: str, metric: str, value: float) -> AnomalyResult:
        """Score *value* — does not add it to the training buffer."""
        self._ensure_buffers(machine_id, metric)
        model = self._models.get(machine_id, {}).get(metric)

        if model is None:
            buf = self._buffers[machine_id][metric]
            return AnomalyResult(
                is_anomaly=False,
                z_score=0.0,
                severity="normal",
                description=(
                    f"Model not yet trained for {machine_id}/{metric} "
                    f"({len(buf)}/{self.train_after} samples collected)."
                ),
            )

        score = float(model.decision_function([[value]])[0])
        prediction = int(model.predict([[value]])[0])  # -1 = anomaly, 1 = normal
        is_anomaly = prediction == -1

        # Normalize the decision score to an approximate z-score for consistency
        # (decision_function returns distance from decision boundary; more negative = more anomalous)
        pseudo_z = -score * 5.0  # rough scaling so values are in a similar range to z-scores

        if is_anomaly and pseudo_z > IsolationForestDetector._z(3.5):
            severity = "severe_anomaly"
            desc = (
                f"Isolation Forest: severe anomaly on {machine_id}/{metric}: "
                f"value={value:.3f}, decision score={score:.4f}."
            )
        elif is_anomaly:
            severity = "anomaly"
            desc = (
                f"Isolation Forest: anomaly on {machine_id}/{metric}: "
                f"value={value:.3f}, decision score={score:.4f}."
            )
        else:
            severity = "normal"
            desc = (
                f"Isolation Forest: {machine_id}/{metric} normal: "
                f"value={value:.3f}, decision score={score:.4f}."
            )

        return AnomalyResult(
            is_anomaly=is_anomaly,
            z_score=round(pseudo_z, 3),
            severity=severity,
            description=desc,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _train(self, machine_id: str, metric: str) -> None:
        buf = self._buffers[machine_id][metric]
        X = np.array(buf, dtype=float).reshape(-1, 1)
        model = IsolationForest(contamination=self.contamination, random_state=42)
        model.fit(X)
        if machine_id not in self._models:
            self._models[machine_id] = {}
        self._models[machine_id][metric] = model

    def _ensure_buffers(self, machine_id: str, metric: str) -> None:
        if machine_id not in self._buffers:
            self._buffers[machine_id] = {}
            self._sample_counts[machine_id] = {}
        if metric not in self._buffers[machine_id]:
            self._buffers[machine_id][metric] = []
            self._sample_counts[machine_id][metric] = 0

    @staticmethod
    def _z(val: float) -> float:
        """Helper to avoid magic numbers in comparisons."""
        return val
