# 0041 — FHIR R4 read-only facade as the public data API

- **Status:** accepted
- **Date:** 2026-10-22
- **Deciders:** maintainers (@martinezsalmeron, @ZoliQua)
- **Tags:** interoperability, fhir, api, registry, compliance, architecture

## Context

Issue #747. Third parties increasingly expect clinical data in HL7 FHIR rather than in our `ApiResponse` envelope: labs, radiology centres, hospitals, patient apps and integrators. National connectors already on paper need it too:

- Poland P1 sends medical events over FHIR (ADR 0033).
- Germany's ePA uses FHIR-based MIOs (ADR 0032).

In the EU, the EHDS Regulation (EU) 2025/327 is in force. Its preparatory work points to FHIR R4 plus the International Patient Summary (IPS) as the European exchange format. Its obligations for EHR systems phase in by data category: patient summaries and e-prescriptions first, then imaging, test results and discharge reports in 2031. Two things have not been checked against the Official Journal text (Art. 105) or the implementing acts yet: the exact application date for EHR systems, and whether a dental practice system falls under the "EHR system" definition. This ADR does not depend on either answer.

Today we have two HTTP surfaces:

- **`/api/v1/**`** serves the Nuxt UI and the copilot. It is shaped for screens and carries business rules that have no 1:1 FHIR equivalent, for example plan-owned quote lines (#176/#177), budget states and Verifactu invariants.
- **`/api/v1/integrations/public/`** is a token-authenticated, read-only public API (issue #65 §5). It offers `ping` and patient lookup by phone, email or national id.

Our clinical data is barely coded:

- The only standard code is the tooth number: FDI / ISO 3950 (`odontogram/models.py:50`, `budget`, `billing`).
- Allergies and medications are free-text strings (`patients_clinical/models.py:76`, `:106`).
- `medication_catalog` has no ATC code.
- Treatments use clinic-defined catalog codes.
- Findings are odontogram states.

There is no mature, generally adopted dental FHIR implementation guide. The HL7 Dental Data Exchange IG is US-centric and built around referrals.

## Decision

DentalPin exposes clinical data to third parties through a **read-only FHIR R4 facade**. Module-contributed providers, collected through a core registry, assemble it. This facade becomes **the** public data API, and the internal API stays private.

1. **Two APIs, one audience each.**
   - `/api/v1/**` stays internal. It is not a public contract and keeps changing freely.
   - `/api/v1/fhir/R4/**` is the public, versioned contract.
   - The `integrations/public` read endpoints are frozen (no new endpoints). They are deprecated once FHIR `Patient` search by `identifier`/`telecom` covers lookup, and removed only after checking that no Zapier, Make or n8n integration depends on them.
   - Webhooks (REST Hooks) stay in `integrations`. FHIR Subscriptions are out of scope.
2. **The provider contract lives in core.** It follows the `get_tools()` shape, as in ADR 0038.
   - `BaseModule` gains an optional `get_fhir_providers()` (default `[]`).
   - Core collects providers from **active** modules only (ADR 0020).
   - Each module maps **its own** models and calls its own existing service methods. Providers duplicate no queries and contain no business logic, so the facade is a translation of shape.
   - Contributor modules take **no** dependency on `fhir`.
3. **A removable `fhir` module serves the facade.**
   - It owns the routes, search and paging, the `Bundle` assembly and the access log.
   - It generates `CapabilityStatement` (`/metadata`) from the registered providers, so it lists exactly what is installed.
   - Its only `depends` is `integrations`, for token authentication.
4. **R4 (4.0.1), JSON only.** IPS, the EU profiles and US Core are all on R4. Do not support R5 or XML until a consumer needs them.
5. **Read-only.** Supported interactions are `read`, `search-type` and `Patient/$everything`. Create, update and delete over FHIR would bypass the business rules and the billing invariants. Inbound FHIR, if ever needed, is an import format for `migration_import`, not a live write API.
6. **Authentication reuses the integrations API tokens** (`dp_…`, clinic-scoped and rate-limited), with new scopes of the form `fhir:<ResourceType>.read`. SMART on FHIR (OAuth2 with `patient/*.rs` scopes and launch context) gets its own ADR when a consumer needs it.
7. **Tenancy.**
   - The token's `clinic_id` scopes every query and every reference the facade resolves.
   - A resource from another clinic answers **404**, never 403, so its existence does not leak.
   - Our UUIDs are used as FHIR logical ids unchanged.
8. **Minimal search.**
   - Supported parameters: `_id`, `_lastUpdated`, `_count`, `patient`, `date` and `identifier`, plus `telecom` on `Patient`.
   - Paging is `Bundle.link[next]` over the PK-tiebroken ordering from #724.
   - Not supported: chained search, `_include`/`_revinclude` and `_has`.
   - An unsupported parameter answers 400 with an `OperationOutcome`. It is never silently ignored, because that would return an over-broad result set.
9. **Terminology: text first, codes optional.**
   - Providers emit `CodeableConcept.text` from our free text and add a `coding` only where we hold a real code (FDI today).
   - The output is valid FHIR but **not IPS-conformant**. The `CapabilityStatement` says so and claims no IPS profile.
   - Storing SNOMED CT, ATC or ICD-10 codes (as optional columns plus a mapping UI) is a separate ADR, because SNOMED CT is not free in every country and a self-hosted product cannot ship it blindly.
   - The dental mapping is our own, documented profile: odontogram → `Condition`/`Procedure`, with `bodySite` carrying tooth and surface.
10. **Every request is logged.**
    - The `fhir` module writes one row per request: token, clinic, interaction, resource type and the patient ids whose data was returned.
    - No response bodies are stored.
    - This is the minimum needed to answer "who read this patient's record" under GDPR Art. 15 and the logging expectations of EHDS.
11. **Validation happens in tests, not at runtime.** Providers return plain dicts. `fhir.resources` (pydantic v2) is a test-only dependency, and the tests validate each provider's output against R4.

## Consequences

### Good

- A single public contract for third parties, in a standard they already speak. The overlapping `integrations/public` read API goes away instead of growing.
- Module isolation holds. `fhir` never imports clinical modules, the clinical modules never depend on `fhir`, and uninstalling a module simply drops its resources from `/metadata`.
- Country connectors (P1, ePA, HCDSNS…) can build on the same providers instead of each re-mapping Patient, Condition and Procedure.
- The GDPR portability export (ADR 0038) can emit a FHIR `Bundle` via `Patient/$everything` instead of growing a second exporter.
- No runtime dependency is added for an output-only surface.

### Bad / accepted trade-offs

- Two APIs mean two shapes to keep in sync. This is mitigated by providers calling service methods and by the R4 validation tests, but a new field reaches FHIR only when someone maps it.
- Until coded terminology lands, the output is weak for semantic interoperability. It is good for display and integration, and not enough for IPS or EHDS conformance.
- Read-only means integrators still cannot push data in. That is deliberate, and it will be requested.
- Phase 1 has no SMART on FHIR, so patient-facing apps cannot use the facade directly. Only server-to-server integrations holding a clinic token can.
- The access log is a new table that grows with traffic. Retention follows `gdpr` `RetentionPolicy` when that module is installed; otherwise rows are kept.
- `fhir` depends on `integrations` for token auth. If more consumers appear, token auth should move to core.

## Alternatives considered

- **Turn `/api/v1/**` into FHIR** — rejected.
  - Every screen would pay for FHIR's verbosity and lossy mapping.
  - Business rules with no FHIR equivalent (budget states, plan-owned quote lines, Verifactu chains) would need extensions everywhere.
  - The internal API would lose its freedom to change.
- **Keep three APIs (internal, `integrations/public`, FHIR)** — rejected. That would mean two public contracts for the same data, each needing its own scopes, docs and deprecation story.
- **Mappings inside the `fhir` module, with `depends` on every clinical module** — rejected. It would need about 10 `depends`, it would break on every uninstall, and `fhir` would have to know every module's internals. This is the same argument ADR 0038 made against a registry inside `gdpr`.
- **Event-bus fan-out to assemble resources** — rejected for the reason given in ADR 0038: a fan-out cannot prove completeness, and `$everything` must be complete or fail.
- **R5** — rejected for now. Adoption is marginal, and IPS and the EU profiles are on R4.
- **`fhir.resources` models at runtime** — rejected. They add a heavy dependency and per-request validation cost to an output-only surface, and validating in tests catches the same mistakes.
- **Code everything with SNOMED CT up front** — deferred. It is blocked by licensing outside member countries, and by data we do not hold today.

## Phasing

- **Phase 1:**
  - Core registry and the `fhir` module.
  - `CapabilityStatement`, `Organization`, `Location`, `Practitioner`, `PractitionerRole`, `Patient`, `RelatedPerson`, `Appointment`, `AllergyIntolerance`, `MedicationStatement`.
  - `Patient/$everything`, token scopes and the access log.
  - `integrations/public` read endpoints marked deprecated.
- **Phase 2:**
  - `Condition` and `Procedure` with tooth/surface `bodySite`.
  - Periodontal `Observation`.
  - `CarePlan` / `ServiceRequest`, `MedicationRequest`, `DocumentReference`, `ImagingStudy`.
  - A written dental profile.
- **Out of scope:**
  - Billing, payments, budgets and claims (country ADRs).
  - Writes.
  - FHIR Subscriptions.
  - Certification.
- **Separate ADRs:** coded terminology (SNOMED/ATC/ICD-10 and licensing), and SMART on FHIR.

## How to verify the rule still holds

- `rg "def get_fhir_providers" backend/app/core/plugins/base.py` resolves, and the registry lives under `backend/app/core/`.
- `rg '"fhir"' backend/app/modules/*/__init__.py` finds no clinical module that lists `fhir` in `depends`.
- `rg "from app.modules\.(?!integrations)" backend/app/modules/fhir` finds nothing (the `fhir` module imports no clinical module).
- No route under `backend/app/modules/fhir` uses POST, PUT, PATCH or DELETE (read-only).
- A test validates every registered provider's output with `fhir.resources` R4 models.
- A test reads another clinic's resource and gets 404.
- A test sends an unsupported search parameter and gets a 400 `OperationOutcome`.
- A test checks that every request writes an access-log row.
- No new endpoint appears under `integrations/public` (frozen).

## References

- Issue #747 (analysis and mapping table), issue #65 §5 (`integrations/public`), #724 (PK tiebreak)
- ADR 0020 (module live iff installed), ADR 0032 (Germany TI/ePA), ADR 0033 (Poland P1), ADR 0035 (US / ONC), ADR 0038 (subject export registry)
- `backend/app/core/plugins/base.py` (`get_tools()`)
- `backend/app/core/agents/tools/registry.py`
- `backend/app/modules/integrations/public.py` (`require_scope`)
- `backend/app/modules/integrations/triggers.py` (`SUPPORTED_TOKEN_SCOPES`)
- `backend/app/modules/odontogram/models.py:50` (FDI)
- `backend/app/modules/patients_clinical/models.py`
- HL7 FHIR R4 (4.0.1): <https://hl7.org/fhir/R4/>
- International Patient Summary IG: <https://hl7.org/fhir/uv/ips/>
- Regulation (EU) 2025/327 (EHDS): <https://eur-lex.europa.eu/eli/reg/2025/327/oj>
