---
module: telephony
last_verified_commit: 0000000
---

# telephony — overview

CTI gateway (issue #64, phase 1). A public HMAC-verified webhook accepts
normalized call events from any source (PBX call-flow, Zapier / Make),
numbers are normalized to E.164, callers are matched against patients,
every call lands in a persistent log, and `call.*` events go on the bus.
The screen-pop is a polling toast for users with `telephony.calls.read`;
`/calls` is the log + live view. Community module,
installable/removable.

Vendor adapters (aircall / 3cx / twilio_voice) arrive later as their own
community modules posting into this same gateway. The ingest payload is
documented in the module `CLAUDE.md` and is a public contract.
