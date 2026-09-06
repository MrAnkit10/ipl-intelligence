import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.data_loader import load_evaluation_report

st.set_page_config(page_title="Model Insights | IPL Intelligence", page_icon="🔬", layout="wide")
st.title("🔬 Model Insights")

report = load_evaluation_report()
if not report:
    st.warning("No evaluation report found. Run `python -m src.models.train` first.")
    st.stop()

st.subheader("Methodology")
st.markdown(
    """
- **Target**: for every ball of the second innings, label = 1 if the batting (chasing) team went on to win the match.
- **No leakage**: features use only match-state information known at that exact ball — final score, winner, and margin are never inputs.
- **Chronological split**: train ≤ 2022, validate 2023-2024, test ≥ 2025 — never a random split, which would leak balls from the same match across sets.
- **Model selection**: candidates compared on validation log loss.
- **Calibration**: the selected model is recalibrated with isotonic regression fit on the validation split, then judged on the untouched test seasons.
"""
)

st.divider()
st.subheader(f"Best Model: {report['best_model']}")

st.markdown("**Validation metrics (model selection)**")
val_df = pd.DataFrame(report["candidate_validation_metrics"]).T
st.dataframe(val_df.style.format("{:.4f}"), width="stretch")

st.markdown("**Held-out test metrics (2025-2026 seasons)**")
test_df = pd.DataFrame(
    {"raw": report["raw_test_metrics"], "calibrated": report["calibrated_test_metrics"]}
).T
st.dataframe(test_df.style.format("{:.4f}"), width="stretch")

st.divider()
st.subheader("Calibration Curve")
st.caption(
    "A perfectly calibrated model sits on the diagonal: when it says 70% win probability, "
    "the batting team should actually win about 70% of the time in similar situations."
)

fig = go.Figure()
fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect calibration", line=dict(dash="dash", color="gray")))
for name, key in [("Raw", "raw_calibration_curve"), ("Calibrated", "calibrated_calibration_curve")]:
    curve = report[key]
    fig.add_trace(
        go.Scatter(
            x=curve["predicted_probability"],
            y=curve["observed_frequency"],
            mode="lines+markers",
            name=name,
        )
    )
fig.update_layout(
    xaxis_title="Predicted probability",
    yaxis_title="Observed win frequency",
    xaxis_range=[0, 1],
    yaxis_range=[0, 1],
)
st.plotly_chart(fig, width="stretch")

raw_gap = sum(
    abs(p - o)
    for p, o in zip(report["raw_calibration_curve"]["predicted_probability"], report["raw_calibration_curve"]["observed_frequency"])
) / len(report["raw_calibration_curve"]["predicted_probability"])
cal_gap = sum(
    abs(p - o)
    for p, o in zip(
        report["calibrated_calibration_curve"]["predicted_probability"], report["calibrated_calibration_curve"]["observed_frequency"]
    )
) / len(report["calibrated_calibration_curve"]["predicted_probability"])
st.caption(f"Mean |predicted − observed| across deciles: raw = {raw_gap:.3f}, calibrated = {cal_gap:.3f}")
