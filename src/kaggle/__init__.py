"""Track 2 quarantine (KDR-001 SS contamination safeguards / KDR-003 SS6).

Everything under this package is Kaggle-only, competition-legal-but-non-deployable
leakage code. No module outside `src/kaggle/` or `scripts/kaggle/` may import from
here -- that is the one invariant the code-valve grep enforces before any merge to
`main` (`grep -rn --include="*.py" "import.*kaggle" src/ scripts/`, excluding both
quarantine trees, must be empty).
"""
