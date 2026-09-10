"""
SAFEGUARD AI - Anomaly Detection
Uses rolling statistics (Z-score) and Isolation Forest to detect
abnormal machine conditions from telemetry streams.
"""
import logging
from collections import deque
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import IsolationForest
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available; using Z-score only for anomaly detection.")


@dataclass
class AnomalyResult:
    is_anomaly: bool
    anomaly_score: float        # 0.0–1.0, higher = more anomalous
    method: str                 # zscore, isolation_forest, combined
    zscore_flags: Dict[str, float]  # parameter -> z-score
    explanation: str


class RollingStats:
    """Maintains rolling mean and std dev for a single numeric stream."""

    def __init__(self, window: int = 20):
        self.window = window
        self._buffer: deque = deque(maxlen=window)

    def update(self, value: float):
        self._buffer.append(value)

    def mean(self) -> Optional[float]:
        if len(self._buffer) < 2:
            return None
        return sum(self._buffer) / len(self._buffer)

    def std(self) -> Optional[float]:
        if len(self._buffer) < 2:
            return None
        m = self.mean()
        variance = sum((x - m) ** 2 for x in self._buffer) / len(self._buffer)
        return math.sqrt(variance)

    def zscore(self, value: float) -> Optional[float]:
        m = self.mean()
        s = self.std()
        if m is None or s is None or s == 0:
            return None
        return abs((value - m) / s)

    @property
    def ready(self) -> bool:
        return len(self._buffer) >= max(5, self.window // 4)


class MachineAnomalyDetector:
    """
    Per-machine anomaly detector.
    Maintains rolling statistics for each telemetry parameter and optionally
    trains an Isolation Forest on recent history.
    """

    TELEMETRY_PARAMS = ["temperature", "vibration", "rpm", "pressure", "load", "current"]

    def __init__(self, machine_id: str, window: int = 20, zscore_threshold: float = 2.5,
                 contamination: float = 0.05):
        self.machine_id = machine_id
        self.window = window
        self.zscore_threshold = zscore_threshold
        self.contamination = contamination

        # Rolling stats per parameter
        self.stats: Dict[str, RollingStats] = {
            p: RollingStats(window) for p in self.TELEMETRY_PARAMS
        }

        # Isolation Forest
        self._if_model = None
        self._if_buffer: deque = deque(maxlen=500)
        self._if_trained = False

    def update(self, reading: Dict[str, float]) -> AnomalyResult:
        """
        Feed a new reading, update internal state, and return anomaly assessment.
        """
        # Update rolling stats
        for param in self.TELEMETRY_PARAMS:
            if param in reading:
                self.stats[param].update(reading[param])

        # Update IF buffer
        feature_vector = [reading.get(p, 0.0) for p in self.TELEMETRY_PARAMS]
        self._if_buffer.append(feature_vector)

        # Try to train / retrain IF every 50 samples
        if SKLEARN_AVAILABLE and len(self._if_buffer) >= 30:
            if not self._if_trained or len(self._if_buffer) % 50 == 0:
                self._train_isolation_forest()

        return self._assess(reading)

    def _train_isolation_forest(self):
        """Train Isolation Forest on buffered samples."""
        try:
            import numpy as np
            X = np.array(list(self._if_buffer))
            self._if_model = IsolationForest(
                contamination=self.contamination,
                random_state=42,
                n_estimators=50,
            )
            self._if_model.fit(X)
            self._if_trained = True
        except Exception as e:
            logger.warning(f"IF training failed for {self.machine_id}: {e}")

    def _assess(self, reading: Dict[str, float]) -> AnomalyResult:
        """Run anomaly detection and return result."""
        zscore_flags: Dict[str, float] = {}
        z_anomaly = False

        for param in self.TELEMETRY_PARAMS:
            if param not in reading:
                continue
            rs = self.stats[param]
            if rs.ready:
                z = rs.zscore(reading[param])
                if z is not None:
                    zscore_flags[param] = round(z, 3)
                    if z > self.zscore_threshold:
                        z_anomaly = True

        # Isolation Forest score
        if_anomaly = False
        if_score = 0.0
        if SKLEARN_AVAILABLE and self._if_trained and self._if_model is not None:
            try:
                import numpy as np
                vec = np.array([[reading.get(p, 0.0) for p in self.TELEMETRY_PARAMS]])
                raw_score = self._if_model.score_samples(vec)[0]
                # Convert: score_samples returns negative anomaly score (-1=anomalous, 0=normal)
                if_score = max(0.0, min(1.0, (-raw_score - 0.3) / 0.7))
                if_anomaly = self._if_model.predict(vec)[0] == -1
            except Exception:
                pass

        # Combine
        is_anomaly = z_anomaly or if_anomaly

        # Composite anomaly score (0–1)
        z_score_max = max(zscore_flags.values()) if zscore_flags else 0.0
        z_normalized = min(1.0, z_score_max / (self.zscore_threshold * 2))
        if SKLEARN_AVAILABLE and self._if_trained:
            anomaly_score = 0.6 * z_normalized + 0.4 * if_score
            method = "combined"
        else:
            anomaly_score = z_normalized
            method = "zscore"

        anomaly_score = round(anomaly_score, 4)

        # Build explanation
        flagged = [f"{p}(z={z:.2f})" for p, z in zscore_flags.items() if z > self.zscore_threshold]
        if flagged:
            explanation = f"Anomalous parameters detected: {', '.join(flagged)}."
        elif if_anomaly:
            explanation = "Isolation Forest detected an unusual combination of parameters."
        else:
            explanation = "No anomaly detected."

        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            method=method,
            zscore_flags=zscore_flags,
            explanation=explanation,
        )


class AnomalyDetectionManager:
    """Manages per-machine anomaly detectors."""

    def __init__(self, window: int = 20, zscore_threshold: float = 2.5,
                 contamination: float = 0.05):
        self.window = window
        self.zscore_threshold = zscore_threshold
        self.contamination = contamination
        self._detectors: Dict[str, MachineAnomalyDetector] = {}

    def get_detector(self, machine_id: str) -> MachineAnomalyDetector:
        if machine_id not in self._detectors:
            self._detectors[machine_id] = MachineAnomalyDetector(
                machine_id,
                window=self.window,
                zscore_threshold=self.zscore_threshold,
                contamination=self.contamination,
            )
        return self._detectors[machine_id]

    def update(self, machine_id: str, reading: Dict[str, float]) -> AnomalyResult:
        return self.get_detector(machine_id).update(reading)


# Module-level singleton
anomaly_manager = AnomalyDetectionManager()
