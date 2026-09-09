# Account Lockout Resolution

## Overview

Covers diagnosis and resolution of locked user accounts, most commonly
caused by repeated failed login attempts, and the appropriate response
for password reset requests.

## Standard resolution: password reset

For a standard account lockout (user reports being unable to log in,
account status shows "locked", no signs of suspicious activity), the
standard remediation is a password reset, which also unlocks the
account.

**Resolution steps:**

1. Confirm the account is actually locked via the account status tool —
   users sometimes report a "lockout" that is actually an expired
   password or a typo, which look different from a true lockout and
   don't require a reset.
2. Reset the account's password. This action both generates a new
   temporary credential and clears the lockout state in a single step.
3. Confirm the account now shows "unlocked" before closing the ticket.
4. Advise the requester to change their temporary password on next
   login, per standard security policy.

## When NOT to reset automatically

A password reset should not be performed automatically, without a human
approving the action first, in these cases:

- The requester's identity cannot be confirmed through the ticket
  (e.g., the request comes from an email or channel that doesn't match
  the account's registered contact information).
- The account belongs to a privileged or administrative role — these
  always require human verification regardless of how routine the
  request otherwise looks, since a wrongly-reset admin credential is a
  much higher-impact mistake than a standard user account.
- The lockout was preceded by an unusually high number of failed
  attempts in a short window (a pattern more consistent with a
  credential-stuffing attempt than a user simply mistyping their
  password), which should be escalated to security rather than resolved
  as a routine lockout.

## Escalation criteria

Escalate to the security team, rather than resolving as a routine
lockout, if there are signs of a targeted attack: failed attempts from
multiple distinct source locations in a short period, or a lockout
immediately followed by a second lockout shortly after a reset (which
suggests an attacker is also attempting to authenticate).