# Internal Service Outage Response

## Overview

Covers response procedures when an internal service (wiki, file share,
email, or similar) is reported down or degraded by one or more users.
Applies broadly across services, not just one specific system.

## Initial triage

When a service outage is reported, first determine whether the report
is isolated to one user or affects multiple users, since this changes
the likely cause and the appropriate response:

- **Single user affected**: more likely a client-side, network-path, or
  permissions issue specific to that user, not a genuine service outage.
  Check the service's own status first regardless — if the service
  reports healthy, the investigation should focus on the user's specific
  access path rather than the service itself.
- **Multiple users affected**: strong signal of a genuine service-level
  issue. Proceed directly to checking and, if appropriate, restarting
  the affected service.

## Standard resolution: service restart

For a service reporting "down" or "degraded" with no other obvious
cause, a restart is the standard first remediation step for internal
services covered by this runbook (examples: confluence-internal,
file-share-01).

**Resolution steps:**

1. Check current service status before restarting — restarting a
   service that is already healthy provides no benefit and briefly
   disrupts any users currently connected to it.
2. If down or degraded, restart the service.
3. Confirm the service reports "running" after the restart before
   closing the ticket or notifying the requester that the issue is
   resolved.
4. Update the ticket with resolution notes describing what was done,
   not just that it was "fixed" — future triage benefits from knowing
   whether a restart alone resolved a given service's issue, since a
   service that requires frequent restarts to stay healthy is itself
   worth flagging to engineering.

## When restarting is not appropriate

Do not restart a service, and escalate instead, when:

- The service has already been restarted within the current incident
  and the problem recurred — a repeat failure shortly after a restart
  indicates a deeper issue a restart will not fix.
- The reported symptom is data loss, data corruption, or incorrect data
  being returned by the service, rather than unavailability — these
  require investigation before any remediation action, since a restart
  could destroy diagnostic evidence needed to understand what happened.
- The outage affects a critical, customer-facing, or compliance-relevant
  system — these should always be escalated to a human for approval
  before any remediation action is taken, regardless of how routine the
  fix would otherwise be for an internal-only service.