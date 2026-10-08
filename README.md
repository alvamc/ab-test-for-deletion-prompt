# A/B Test: Prompting Users to Delete Invalid Documents

An end-to-end A/B test analysis, from power calculation to launch decision, using **simulated data**.

The design mirrors an experiment I ran in a previous role on a document-management product: a new in-product prompt (a modal) asked users to delete invalid documents cluttering their accounts, such as drafts never completed, duplicates, and documents created by mistake. No real company data or code is used here.

## Question

Does actively prompting users increase the share of accounts that delete at least one invalid document?

## Design

| Choice | Value | Why |
|---|---|---|
| Primary metric | % of accounts deleting at least one invalid document | Binary, easy to interpret, directly tied to the goal |
| Baseline | ~30% | Pre-experiment rate |
| Minimum detectable effect (MDE) | 5 percentage points, absolute | Smallest lift worth shipping the prompt for |
| Alpha / Power | 0.05 / 0.80 | Standard thresholds |
| Randomization unit | Account | Users who share an account would otherwise see different experiences and influence each other (avoids SUTVA violations) |
| Duration | 4 weeks | Captures day-of-week and week-to-week variation |
| Integrity check | Sample ratio mismatch (chi-square, p < 0.001) | Catches broken assignment before trusting results |
| Novelty check | Lift plotted by enrollment week | A new prompt can get early attention that fades |

## Decision rule

Launch only if all three hold:
1. No sample ratio mismatch.
2. The result is statistically significant (p < 0.05).
3. The **lower bound** of the 95% confidence interval is above the 5-point MDE, so the lift is practically meaningful and not just detectable.

## Results (simulated run, seed 42)

- Required sample: **1,376 accounts per arm**. Actual: about 6,000 per arm.
- SRM check: p = 0.86, no mismatch.
- Control 28.8% vs. treatment 39.5%: **lift of 10.7 percentage points (95% CI 9.0 to 12.4)**.
- The CI lower bound clears the 5-point MDE. **Decision: launch.**
- Novelty: lift stays well above zero in every week, with the week-3 dip still above the MDE.

![Weekly lift](output/weekly_lift.png)

## Run it

```bash
pip install -r requirements.txt
python simulate_data.py
python analyze_experiment.py
```

To see the integrity check fire, simulate a broken 53/47 split:

```bash
python simulate_data.py --srm-bias 0.03 --out data/srm_case.csv
python analyze_experiment.py --data data/srm_case.csv
```

The SRM check flags the mismatch and the decision becomes "Do not launch yet."

## What I would add in production

- **Guardrail metrics**, for example accidental deletion of valid documents, support tickets, and session abandonment after the prompt.
- **Variance reduction (CUPED)** using each account's pre-period behavior, to reach the same power with fewer accounts.
- **Heterogeneity checks** by account size or segment, planned in advance to avoid fishing.

## Files

- `simulate_data.py` generates synthetic account-level data with a mild novelty effect.
- `analyze_experiment.py` runs the power calculation, SRM check, primary comparison, decision rule, and weekly novelty check, and writes `output/results.json` and `output/weekly_lift.png`.
