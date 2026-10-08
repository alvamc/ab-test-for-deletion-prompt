"""
Simulate account-level data for an A/B test of a "delete invalid documents" prompt.

All data is synthetic. The design mirrors a real experiment pattern:
- Randomization unit: account (prevents spillover between users who share an account)
- Primary metric: did the account delete at least one invalid document? (binary)
- Baseline rate around 30%
- Treatment effect that starts a little higher in week 1 and settles (mild novelty)
- Four weeks of enrollment to capture weekly patterns
"""

import argparse
import os

import numpy as np
import pandas as pd

BASELINE_RATE = 0.30
# True treatment lift by enrollment week, in percentage points.
# A slightly higher week-1 lift simulates a mild novelty effect that fades.
TRUE_LIFT_BY_WEEK = {1: 0.105, 2: 0.095, 3: 0.090, 4: 0.090}


def simulate(n_accounts: int, seed: int, srm_bias: float = 0.0) -> pd.DataFrame:
    """Return one row per account with variant, enrollment week, and outcome.

    srm_bias lets you deliberately break the 50/50 split to see the SRM check fire.
    """
    rng = np.random.default_rng(seed)
    p_treatment = 0.5 + srm_bias
    variant = np.where(rng.random(n_accounts) < p_treatment, "treatment", "control")
    week = rng.integers(1, 5, size=n_accounts)  # weeks 1-4

    lift = np.array([TRUE_LIFT_BY_WEEK[w] for w in week])
    p_delete = np.where(variant == "treatment", BASELINE_RATE + lift, BASELINE_RATE)
    deleted = (rng.random(n_accounts) < p_delete).astype(int)

    return pd.DataFrame(
        {
            "account_id": np.arange(1, n_accounts + 1),
            "variant": variant,
            "enrollment_week": week,
            "deleted_invalid_doc": deleted,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-accounts", type=int, default=12000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--srm-bias", type=float, default=0.0,
                        help="Shift the treatment share away from 0.5 to test the SRM check")
    parser.add_argument("--out", default="data/experiment_accounts.csv")
    args = parser.parse_args()

    df = simulate(args.n_accounts, args.seed, args.srm_bias)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df):,} accounts to {args.out}")


if __name__ == "__main__":
    main()
