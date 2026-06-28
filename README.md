# Bosch Production Line Failure Detection (Production ML System)

## 🚀 Overview
This project simulates a real-world production ML system for detecting manufacturing failures in highly imbalanced industrial data (~0.58% failure rate).

Unlike leaderboard-focused solutions, this system is designed for:
- Real-world deployment
- Business decision-making
- Cost-sensitive optimization
- Monitoring and drift detection

---

## 🧠 Key Philosophy

We intentionally moved away from pure MCC optimization.

Why?

Top Kaggle solutions (~0.52 MCC) rely on:
- Data leakage
- Future information
- Non-deployable tricks

This project focuses on:
✅ Reproducibility  
✅ Leakage-safe modeling  
✅ Production reliability  

---

## 🏗️ Architecture

### 🔵 Production Pipeline (`main` branch)
- Decision system (threshold + cost optimization)
- Production batch inference (label-free, `scripts/run_production_inference.py` --
  see `docs/ml_system_tracks.md` Track 3). The previous "batch simulation" step here
  was actually labeled offline evaluation; it now lives separately as
  `scripts/run_offline_batch_eval.py` (Track 1), not part of this pipeline.
- Drift detection (Evidently)
- API (FastAPI)
- Dashboard (Streamlit)

### 🟢 Training Pipeline (`training-pipeline` branch)
- Data ingestion (CSV → Parquet, memory safe)
- Feature engineering (baseline + G + H)
- Chunk-aware CV (leakage-safe)
- LightGBM training
- Meta-model stacking
- OOF prediction generation

---

## 🔁 End-to-End Flow

Raw CSV → Parquet → Features → Models → OOF predictions
↓
Meta model
↓
Production system (thresholding + cost + simulation)
↓
Dashboard + API + Monitoring

---

## 📊 Key Results

> ⚠️ **Historical / UNVERIFIED (World B)**
> The numbers below ("Best MCC: ~0.317", "Recall @ 10% inspection: ~0.63") come
> from `data/features/oof_predictions_context_meta_v2_blend.parquet`, a
> 1,183,747-row file whose generating raw/intermediate/model artifacts were
> **deliberately deleted** from this repo (see `data/README.md`). No training
> script in this repository's history reproduces that file, so these numbers
> are **not currently reproducible** from committed code — treat them as a
> record of a past experiment, not a guarantee about the current pipeline.
>
> The only metrics that ARE reproducible today come from the committed 50,000-row
> dev sample (271 positives, 0.542% failure rate): honest OOF MCC ranges from
> 0.016 (baseline) to 0.131 (dataset_h), with the meta-model at 0.052 — worse
> than its best base model. Full details, exact numbers, and regeneration
> commands (both dev-sample and full-scale) are in
> [`docs/reproducible_metrics_report.md`](docs/reproducible_metrics_report.md).

- Best MCC: ~0.317 *(World B, historical/unverified — see note above)*
- Recall @ 10% inspection: ~0.63 *(World B, historical/unverified — see note above)*
- Precision: low (expected due to imbalance)

**RP2 honest deployable distribution** (reproducible, rolling-origin forward-chaining,
`outputs/e3_rolling_origin_results.json`):
- Deployable MCC range across 5 temporal windows: **0.06–0.18** (mean ≈ 0.12, CI [0.05, 0.19])
- Non-stationarity (prevalence shift 0.33%–0.94%) dominates deployment behavior
- Static threshold not deployable: optimal threshold ranged 0.14–0.72 across windows
- AUC ≈ 0.55 stable — ranking quality is not the bottleneck; operating point is

Track 3 label-free production inference (5 batches, 50,000 rows) and Evidently score-distribution
drift monitoring are deployed and wired to the dashboard.

---

## ⚙️ How to Run

### Training (separate branch)

> Note: running this end-to-end reproduces the **World-A dev-sample metrics**
> in `docs/reproducible_metrics_report.md`, NOT the "Key Results" numbers
> above. `scripts/prepare_data.py` defaults to processing the FULL raw CSVs
> with no row cap — pass `--sample-rows 50000 --sample-tag dev` for the fast
> dev-sample path. See `docs/reproducible_metrics_report.md` for both exact
> command sequences (full-scale and dev-sample) and `data/README.md` for why
> the historical "Key Results" numbers above cannot currently be regenerated.

```bash
git checkout training-pipeline
python scripts/prepare_data.py --zip-path ~/Downloads/bosch-production-line-performance.zip --overwrite
python scripts/build_dataset_baseline.py
python scripts/build_dataset_g.py
python scripts/build_dataset_h.py
python scripts/train_baseline.py
python scripts/train_dataset_g.py
python scripts/train_dataset_h.py
python scripts/train_meta_model.py
````

### Production

```bash
git checkout main
python scripts/run_full_system.py
streamlit run apps/streamlit_dashboard/app.py
```

---

## 📚 Runbooks

Practical, command-level guides for local setup, each of the three tracks, the dashboard, Docker,
AWS S3, and EC2 deployment — including current known gaps — live in
[`docs/runbooks/`](docs/runbooks/README.md).

---

## 📈 Dashboard Features

**View A — Production Monitoring (Track 3, label-free)**
* Batch/cycle/run-sequence progress
* Risk-score distribution histogram
* Flagged / auto-reject / manual-inspect counts
* Score-distribution drift (Evidently: KS test on `risk_score`)
* Top-100-by-risk-score table

**View B — Offline Evaluation / Decision Analysis (labeled OOF data)**
* Threshold tuning
* Inspection budget simulation
* Recall vs precision trade-offs
* Cost optimization
* Failure analysis

---

## 🧠 Business Interpretation

This system answers:

* How many failures are we catching?
* What is the inspection cost?
* What is the optimal threshold?
* What happens if we increase recall?

---

## 🛠️ Tech Stack

* Python, Pandas, LightGBM
* Streamlit (dashboard)
* FastAPI (serving)
* Evidently (monitoring)
* Docker (deployment-ready)

---

## 🔮 Future Improvements

* Real-time streaming (Kafka)
* Automated retraining
* Cloud deployment (AWS/GCP)
* Model registry

---

## 👨‍💻 Author

Anudeep Reddy Mutyala