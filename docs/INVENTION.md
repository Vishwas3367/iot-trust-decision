# Decision mechanism (what is actually novel here)

This prototype is not “a trust score.” The score is an intermediate quantity.
The claim is a **context-gated decision policy for conflicting IoT evidence**.

## What we refuse to do

- Threshold a single sensor (`if temperature > 70: shutdown`).
- Average all readings, which lets a failed probe cancel a real emergency.
- Freeze a source at a lifetime reliability percentage.
- Treat pairwise conflict as automatic rejection.

## What the engine actually does

1. **Detect factions, not just outliers.** Observations are clustered by gap.
   Two-versus-two disagreement is a split, not “one bad sensor.”
2. **Gate evidence by observation quality.** Freshness and communication quality
   multiply into an evidence-quality term. A dangerous value on a stale, lossy
   link cannot dominate the decision by itself.
3. **Blend prior reliability with live behavior.** Historical reliability is a
   prior. Temporal consistency and peer agreement are the likelihood. The blend
   weight moves toward the prior when the current sample is thin.
4. **Score contextual relevance to the decision being made.** A cold outlet
   reading during high load is less relevant to a thermal-trip decision than a
   fresh core probe.
5. **Act on trust mass, not headcount.** The dominant cluster is the one with
   the largest sum of trust, not the largest number of sensors.
6. **Separate conflict from confidence.** High conflict plus one trusted
   faction can still **EXECUTE**. Two strong factions suppress confidence and
   yield **REQUEST_DATA** or **DEFER**.

## Policy

| Confidence | Controller |
|---|---|
| ≥ 0.80 | EXECUTE the machine intent of the trusted consensus |
| 0.50–0.80 | REQUEST additional samples; hold actuation |
| < 0.50 | DEFER; recommend more information or a human |

Machine intent (NORMAL / WARN / SHUTDOWN) is computed only from the trusted
consensus, never from the naive mean.

## Why a weighted sum is not the invention

A linear combination of reliability features is a convenience. The invention is
the **quality-gated posterior**, **trust-mass cluster selection**, and the
**execute / request / defer** controller that treats conflict as a reason to
think, not a reason to discard.
