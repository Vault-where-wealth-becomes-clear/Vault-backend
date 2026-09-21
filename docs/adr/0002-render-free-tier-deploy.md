# ADR-0002: Render free tier as a deliberate, temporary deployment target

## Status

Accepted (documents an existing, intentional trade-off)

## Context

`render.yaml` configures deployment to Render, including the
`RUN_WORKER_INLINE` flag that runs the SQS worker inside the same process as
the API rather than as a separate service. This is a reasonable and common
choice for a pre-launch product, but it carries known limitations that are
easy to forget were ever a deliberate trade-off rather than an oversight.

## Decision

We deploy on Render's free/low tier for now, with the worker running inline
in the API process (`RUN_WORKER_INLINE=true`), because:

- Pre-launch traffic doesn't justify a separate paid worker dyno yet.
- It keeps infrastructure cost at effectively zero while validating the
  product.

## Consequences

- **Cold starts / spin-down**: Render's free tier spins services down after
  inactivity, adding latency to the first request after idle periods.
- **No process isolation between API and worker**: a slow or crashing
  extraction job runs in the same process as user-facing API requests, and
  can affect API responsiveness or availability.
- **No horizontal scaling** of the worker independent of the API.
- **Single point of failure**: one Render service instance for both
  concerns.

## When to revisit

This decision should be revisited when any of the following happen:

- Real user traffic makes cold starts user-visible/complaining-worthy.
- Statement processing volume makes inline worker execution noticeably
  degrade API latency.
- The product moves out of pre-launch and needs an SLA.

At that point, splitting the worker into its own Render service (or moving
it off Render entirely) and upgrading off the free tier should be
considered — not treated as urgent before then.
