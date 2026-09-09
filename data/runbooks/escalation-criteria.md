# General Escalation Criteria

## Overview

This runbook applies across all ticket categories and takes precedence
over category-specific guidance when there's a conflict — if a
category-specific runbook says to remediate automatically but a
condition below applies, escalate instead.

## Always escalate to a human, regardless of category, when:

- The requester's identity or authorization to make the request cannot
  be confirmed from the ticket alone.
- The affected system or account is privileged, administrative, or
  customer-facing — the cost of a wrong automated action on these is
  much higher than on a standard internal, non-privileged resource.
- A remediation action has already been attempted for this same issue
  within the current incident and did not resolve it. Repeating the same
  automated action a second time rarely succeeds where it just failed,
  and risks masking a deeper problem that needs human investigation.
- There are signs of a security incident (credential stuffing patterns,
  unusual access patterns, multiple simultaneous failures across
  unrelated systems) rather than a routine operational issue.
- The ticket describes symptoms not covered by any existing runbook —
  do not attempt to improvise an automated remediation for a situation
  with no documented precedent; escalate for human judgment instead.

## Priority-based handling

Ticket priority should influence urgency of response, but not by itself
determine whether an action requires human approval — a "critical"
priority ticket for a privileged account still requires human approval
before remediation, it just requires that approval faster, not a
bypass of the approval step itself.