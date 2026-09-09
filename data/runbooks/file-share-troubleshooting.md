# File Share Performance Troubleshooting

## Overview

Covers diagnosis of slow or intermittent file share access, distinct
from a full outage (the share is reachable but performance is degraded,
not down entirely).

## Diagnosis

Slow file share access has meaningfully different likely causes
depending on scope and duration, which should guide the response:

- **Intermittent slowness over multiple days, affecting many users**:
  more likely an underlying capacity or infrastructure issue than
  something a single restart will resolve. A restart may provide
  temporary relief but is unlikely to be a durable fix; this pattern
  should be flagged for engineering investigation into root cause even
  if a restart is performed as an immediate mitigation.
- **Sudden slowness starting recently, isolated to one share**: check
  that specific share's status first; a restart is a reasonable first
  attempt if the service reports degraded.

## Resolution steps

1. Check the affected share's current status.
2. If status is "degraded", a restart is a reasonable first remediation
   attempt, but set the expectation with the requester that this may
   only provide temporary relief if the underlying cause is capacity-
   related rather than a simple service hang.
3. Document in the ticket whether the restart improved performance or
   not — this data matters for identifying a recurring capacity problem
   over time, even if any single incident doesn't clearly show one.

## Escalation criteria

Escalate to infrastructure/storage engineering, rather than continuing
to attempt service-level remediation, if:

- The same share has required multiple restart attempts across separate
  tickets within a short period (a pattern, not an isolated incident).
- The slowness correlates with a specific time of day or known
  high-usage period, suggesting a capacity limit rather than a
  transient fault.