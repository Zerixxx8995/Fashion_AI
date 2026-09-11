"""
MLflow Tracker Unit Tests — ml-backend/tests/test_mlflow.py.

Responsibility: Verify experiment tracking, param/metric logging,
and artifact creation in MLflowTracker.
"""

import json
from pathlib import Path
from app.integrations.mlflow_client import MLflowTracker


def test_mlflow_tracker_run_lifecycle(tmp_path: Path):
    tracker = MLflowTracker(experiment_name="test_experiment")
    tracker.local_runs_dir = tmp_path

    # Start run
    run_id = tracker.start_run(run_name="unit_test_run")
    assert run_id.startswith("run_unit_test_run_")
    assert tracker.active_run_id == run_id

    # Log params & metrics
    tracker.log_params({"model": "CLIP-ViT-B/32", "batch_size": 16})
    tracker.log_metrics({"overall_confidence": 0.88, "latency_ms": 42.5})

    # End run
    summary = tracker.end_run(status="FINISHED")

    assert summary["status"] == "FINISHED"
    assert summary["params"]["model"] == "CLIP-ViT-B/32"
    assert summary["metrics"]["overall_confidence"] == 0.88
    assert tracker.active_run_id is None

    # Check disk artifact
    run_folder = tmp_path / run_id
    assert run_folder.exists()
    summary_file = run_folder / "run_summary.json"
    assert summary_file.exists()

    with open(summary_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["run_id"] == run_id
        assert data["params"]["batch_size"] == "16"
        assert data["metrics"]["latency_ms"] == 42.5
