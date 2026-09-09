# VPN Connectivity Troubleshooting

## Overview

This runbook covers diagnosis and resolution for VPN connectivity issues,
including "gateway unreachable" errors, authentication failures, and slow
or dropped connections. Applies to the corporate VPN gateway
(vpn-gateway) used for remote access to internal systems.

## Common symptom: gateway unreachable

When a user reports "gateway unreachable" or a connection timeout, this
almost always indicates the vpn-gateway service itself is down or
unreachable, rather than a problem with the user's individual client
configuration. Confirm the service status before troubleshooting the
user's local setup — checking the user's machine first when the service
is actually down wastes time on both sides.

**Resolution steps:**

1. Check the current status of vpn-gateway via the service status tool.
2. If the service is down or degraded, restart it. Restarting the
   service resolves the large majority of "gateway unreachable" cases,
   since most outages are caused by the service process becoming
   unresponsive under load, not by configuration drift.
3. After a restart, confirm the service reports "running" before closing
   the ticket. A restart command succeeding does not guarantee the
   service actually came back healthy — always verify.
4. If the service is already running and the user still cannot connect,
   the issue is more likely client-side or credential-related; escalate
   to network engineering rather than attempting further service-level
   remediation.

## Common symptom: authentication rejected

If the VPN client connects to the gateway but authentication is
rejected, this is an account-level issue, not a service issue — do not
restart vpn-gateway for this symptom, since it will not resolve an
authentication problem and only adds unnecessary risk to unrelated users
currently connected. Check whether the user's account is locked; if so,
follow the account lockout runbook instead.

## When to escalate instead of remediate

Escalate to network engineering (do not attempt further remediation
yourself) if:

- The gateway has been restarted within the last 30 minutes and the
  problem persists — a second restart in quick succession rarely helps
  and may indicate a deeper infrastructure issue.
- Multiple users across different physical locations report the same
  symptom simultaneously, which suggests a broader network or
  certificate issue rather than a single-service problem.
- The user reports the issue only affects specific internal
  destinations reachable over the VPN (not the VPN connection itself),
  which points to routing configuration rather than gateway health.