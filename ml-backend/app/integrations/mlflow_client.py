"""
MLflow Client — ml-backend/app/integrations/mlflow_client.py.

Responsibility: Handles experiment tracking, parameter logging, metric recording,
and artifact storage for the Computer Vision (CV) scoring engine and fake review detector.

Supports:
  - Live MLflow tracking server (via MLFLOW_TRACKING_URI env var)
  - Local disk-backed tracking store (.mlruns/ directory) as zero-dependency fallback
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Check if native mlflow is installed
HAS_NATIVE_MLFLOW = False
try:
    import mlflow
    HAS_NATIVE_MLFLOW = True
except ImportError:
    HAS_NATIVE_MLFLOW = False


class MLflowTracker:
    """
    MLflow Experiment Tracking Client for Fashion AI CV Engine.
    """

    def __init__(self, experiment_name: str = "fashion_ai_cv_scoring"):
        self.experiment_name = experiment_name
        self.tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "file:./.mlruns")
        self.active_run_id: Optional[str] = None
        self.active_run_data: Dict[str, Any] = {}
        self.local_runs_dir = Path("./.mlruns")
        self.local_runs_dir.mkdir(exist_ok=True, parents=True)

        if HAS_NATIVE_MLFLOW:
            try:
                mlflow.set_tracking_uri(self.tracking_uri)
                mlflow.set_experiment(self.experiment_name)
                logger.info(f"[mlflow_client] Native MLflow initialized at {self.tracking_uri}")
            except Exception as exc:
                logger.warning(f"[mlflow_client] Native MLflow setup warning: {exc}")

    def start_run(self, run_name: str = "cv_scoring_job") -> str:
        """
        Start a new experiment tracking run.
        Returns unique run_id.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        run_id = f"run_{run_name}_{timestamp}"
        self.active_run_id = run_id
        self.active_run_data = {
            "run_id": run_id,
            "run_name": run_name,
            "experiment_name": self.experiment_name,
            "start_time": datetime.utcnow().isoformat(),
            "status": "RUNNING",
            "params": {},
            "metrics": {},
            "tags": {"service": "cv_engine", "version": "0.1.0"},
        }

        if HAS_NATIVE_MLFLOW:
            try:
                mlflow.start_run(run_name=run_name)
                logger.info(f"[mlflow_client] Native MLflow run started: {run_name}")
            except Exception as exc:
                logger.warning(f"[mlflow_client] Failed to start native MLflow run: {exc}")

        logger.info(f"[mlflow_client] Started experiment run ID={run_id}")
        return run_id

    def log_param(self, key: str, value: Any) -> None:
        """Log a single parameter."""
        if not self.active_run_id:
            self.start_run()
        self.active_run_data["params"][key] = str(value)

        if HAS_NATIVE_MLFLOW:
            try:
                mlflow.log_param(key, value)
            except Exception:
                pass

    def log_params(self, params: Dict[str, Any]) -> None:
        """Log a dictionary of parameters."""
        for k, v in params.items():
            self.log_param(k, v)

    def log_metric(self, key: str, value: float, step: Optional[int] = None) -> None:
        """Log a single numeric metric."""
        if not self.active_run_id:
            self.start_run()
        self.active_run_data["metrics"][key] = float(value)

        if HAS_NATIVE_MLFLOW:
            try:
                mlflow.log_metric(key, float(value), step=step)
            except Exception:
                pass

    def log_metrics(self, metrics: Dict[str, float]) -> None:
        """Log a dictionary of metrics."""
        for k, v in metrics.items():
            self.log_metric(k, v)

    def log_artifact_data(self, filename: str, content: Any) -> str:
        """Save a JSON or text artifact file to run directory."""
        if not self.active_run_id:
            self.start_run()

        run_folder = self.local_runs_dir / self.active_run_id
        run_folder.mkdir(exist_ok=True, parents=True)
        file_path = run_folder / filename

        with open(file_path, "w", encoding="utf-8") as f:
            if isinstance(content, (dict, list)):
                json.dump(content, f, indent=2)
            else:
                f.write(str(content))

        logger.info(f"[mlflow_client] Saved artifact {filename} at {file_path}")
        return str(file_path)

    def end_run(self, status: str = "FINISHED") -> Dict[str, Any]:
        """
        End active experiment run and write summary log.
        """
        if not self.active_run_id:
            return {}

        self.active_run_data["status"] = status
        self.active_run_data["end_time"] = datetime.utcnow().isoformat()

        # Save run summary JSON into .mlruns directory
        self.log_artifact_data("run_summary.json", self.active_run_data)

        if HAS_NATIVE_MLFLOW:
            try:
                mlflow.end_run(status=status)
            except Exception:
                pass

        completed_data = self.active_run_data
        logger.info(f"[mlflow_client] Ended experiment run ID={self.active_run_id} status={status}")
        self.active_run_id = None
        self.active_run_data = {}

        return completed_data


# Singleton instance
default_mlflow_tracker = MLflowTracker()
