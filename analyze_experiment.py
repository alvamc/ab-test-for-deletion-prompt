"""
Analyze the simulated A/B test end to end:

1. Power and sample size for the planned minimum detectable effect (MDE)
2. Sample ratio mismatch (SRM) check
3. Primary result: difference in proportions with a confidence interval
4. Decision: statistical significance AND practical significance (CI lower bound vs MDE)
5. Novelty check: lift by enrollment week
"""

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chisquare
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import (
    confint_proportions_2indep,
    proportion_effectsize,
    proportions_ztest,
)

BASELINE_RATE = 0.30
MDE = 0.05      # 5 percentage points, absolute
ALPHA = 0.05
POWER = 0.80
SRM_ALPHA = 0.001  # strict threshold, the common convention for SRM checks


def required_sample_size(baseline: float, mde: float, alpha: float, power: float) -> int:
    """Accounts needed per arm to detect an absolute lift of `mde` over `baseline`."""
    effect = proportion_effectsize(baseline + mde, baseline)
    n = NormalIndPower().solve_power(effect_size=effect, alpha=alpha, power=power,
                                     ratio=1.0, alternative="two-sided")
    return int(np.ceil(n))


def srm_check(df: pd.DataFrame) -> dict:
    counts = df["variant"].value_counts().reindex(["control", "treatment"]).fillna(0)
    expected = [counts.sum() / 2] * 2
    stat, p = chisquare(counts.values, f_exp=expected)
    return {"control_n": int(counts["control"]), "treatment_n": int(counts["treatment"]),
            "chi2": float(stat), "p_value": float(p), "srm_detected": bool(p < SRM_ALPHA)}


def compare(df: pd.DataFrame) -> dict:
    """Difference in proportions (treatment minus control) with a 95% CI."""
    g = df.groupby("variant")["deleted_invalid_doc"].agg(["sum", "count"])
    x_t, n_t = g.loc["treatment"]
    x_c, n_c = g.loc["control"]
    p_t, p_c = x_t / n_t, x_c / n_c
    _, p_value = proportions_ztest([x_t, x_c], [n_t, n_c])
    lo, hi = confint_proportions_2indep(x_t, n_t, x_c, n_c, method="newcomb", compare="diff")
    return {"control_rate": float(p_c), "treatment_rate": float(p_t),
            "lift_pp": float(p_t - p_c), "ci_low_pp": float(lo), "ci_high_pp": float(hi),
            "p_value": float(p_value)}


def weekly_lift(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for week, wdf in df.groupby("enrollment_week"):
        r = compare(wdf)
        r["week"] = int(week)
        rows.append(r)
    return pd.DataFrame(rows)[["week", "control_rate", "treatment_rate",
                               "lift_pp", "ci_low_pp", "ci_high_pp"]]


def plot_weekly(weekly: pd.DataFrame, path: str) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    y = weekly["lift_pp"] * 100
    err = [(weekly["lift_pp"] - weekly["ci_low_pp"]) * 100,
           (weekly["ci_high_pp"] - weekly["lift_pp"]) * 100]
    ax.errorbar(weekly["week"], y, yerr=err, fmt="o-", capsize=4, label="Lift (95% CI)")
    ax.axhline(MDE * 100, linestyle="--", color="tab:red", label=f"MDE = {MDE * 100:.0f} pp")
    ax.axhline(0, color="grey", linewidth=0.8)
    ax.set_xticks(weekly["week"])
    ax.set_xlabel("Enrollment week")
    ax.set_ylabel("Lift (percentage points)")
    ax.set_title("Treatment lift by week (novelty check)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/experiment_accounts.csv")
    parser.add_argument("--outdir", default="output")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    df = pd.read_csv(args.data)
    n_required = required_sample_size(BASELINE_RATE, MDE, ALPHA, POWER)
    srm = srm_check(df)
    overall = compare(df)
    weekly = weekly_lift(df)

    stat_sig = overall["p_value"] < ALPHA
    practical = overall["ci_low_pp"] > MDE
    decision = "Launch" if (stat_sig and practical and not srm["srm_detected"]) else "Do not launch yet"

    print(f"Required sample size: {n_required:,} accounts per arm "
          f"(baseline {BASELINE_RATE:.0%}, MDE {MDE * 100:.0f} pp, alpha {ALPHA}, power {POWER})")
    print(f"Actual: control {srm['control_n']:,}, treatment {srm['treatment_n']:,}")
    print(f"SRM check: chi2 = {srm['chi2']:.2f}, p = {srm['p_value']:.3f} -> "
          f"{'SRM DETECTED, stop and investigate' if srm['srm_detected'] else 'no SRM'}")
    print(f"Control rate {overall['control_rate']:.1%} | Treatment rate {overall['treatment_rate']:.1%}")
    print(f"Lift {overall['lift_pp'] * 100:.1f} pp "
          f"(95% CI {overall['ci_low_pp'] * 100:.1f} to {overall['ci_high_pp'] * 100:.1f} pp), "
          f"p = {overall['p_value']:.2g}")
    print(f"Statistically significant: {stat_sig} | CI lower bound above MDE: {practical}")
    print("\nWeekly lift (novelty check):")
    shown = weekly.copy()
    for c in ["control_rate", "treatment_rate", "lift_pp", "ci_low_pp", "ci_high_pp"]:
        shown[c] = (shown[c] * 100).round(1)
    shown.columns = ["week", "control_%", "treatment_%", "lift_pp", "ci_low_pp", "ci_high_pp"]
    print(shown.to_string(index=False))
    print(f"\nDecision: {decision}")

    plot_weekly(weekly, f"{args.outdir}/weekly_lift.png")
    with open(f"{args.outdir}/results.json", "w") as f:
        json.dump({"required_n_per_arm": n_required, "srm": srm, "overall": overall,
                   "weekly": weekly.to_dict(orient="records"), "decision": decision}, f, indent=2)


if __name__ == "__main__":
    main()
