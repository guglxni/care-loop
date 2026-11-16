# Health intelligence

This package is the Care Loop care-coordination core. It turns a patient record into findings, care-coordination events, and a summary a care team can review. It does not diagnose, prescribe, or recommend medicines. It does not tell a patient to take a dose, skip a dose, or change a dose.

Thresholds live in [`fixtures/rule_catalog.json`](fixtures/rule_catalog.json) and in each care plan's `approved_rule_ids`. A rule runs only when the catalog marks that rule `approved` and a care plan for that patient lists its id. Unapproved rules never fire.

The engine reads `comparator`, `value`, `unit`, `metric`, `context`, `priority`, and `team` from the catalog. Comparators are `gt`, `gte`, `lt`, `lte`, and `eq`. A measurement rule matches when the reading unit equals the catalog unit. A null rule `context` matches any measurement context. A set rule `context` matches only that context.

`coordination_defaults` stores priority labels for missing measurements, unconfirmed doses, missed doses, overdue consultations, and pending laboratory appointments. Those labels are coordination priorities, not diagnoses.

## Run the tests

From the repository root, once the domain modules exist:

```bash
python -m pytest intelligence/tests
```

The engine imports these callables:

- `intelligence.adherence.evaluate_adherence(record, as_of, catalog)`
- `intelligence.glucose.evaluate_glucose(record, as_of, catalog)`
- `intelligence.blood_pressure.evaluate_blood_pressure(record, as_of, catalog)`
- `intelligence.consultations.evaluate_consultations(record, as_of, catalog)`
- `intelligence.care_gaps.evaluate_care_gaps(findings, record, as_of, catalog)`
- `intelligence.escalation.build_events(findings, record, as_of, catalog, existing_open_keys)`
- `intelligence.summary.build_summary(record, events, as_of)`

`intelligence.models` and `intelligence.rules` import on their own. `evaluate` loads the domain modules when it is called.

## Entry point

```python
def evaluate(
    record: PatientRecord,
    as_of: datetime,
    catalog: dict,
    existing_open_keys: set[str] | None = None,
) -> IntelligenceResult:
    ...
```

```python
from datetime import datetime, timezone

from intelligence import IntelligenceResult, PatientRecord, evaluate
from intelligence.rules import load_catalog

catalog = load_catalog()
result = evaluate(record, datetime.now(timezone.utc), catalog)
```

`as_of` must be timezone-aware. The engine raises `ValueError` when it is naive. `existing_open_keys` is the set of dedupe keys already open. The engine forwards that set to escalation and leaves the patient record and the catalog unchanged.

Call order:

1. Adherence, glucose, blood pressure, and consultations produce findings.
2. The engine keeps a ruled finding only when `rule_is_approved_for` is true.
3. Care gaps see those findings and may add findings of their own.
4. The same approval gate runs again.
5. Escalation builds events and escalation history.
6. Events and history for a rule that is not approved for the patient are removed.
7. The summary is built from the remaining events.

Findings with `rule_id` `None` are coordination findings and pass the gate.

Model records take keyword arguments. `reading_origin(source)` maps `manual` to `patient_reported`, `cgm`, `glucometer`, and `home_monitor` to `device_recorded`, and `clinic` to `staff_recorded`. Each summary reading includes `measurement_type`, `value`, `secondary_value`, `unit`, `context`, `measured_at` as an ISO timestamp, `source`, and `origin`.

```python
from intelligence.models import Finding

Finding(
    kind="unconfirmed_dose",
    description="Scheduled dose has no confirmation.",
    priority="low",
    dedupe_key="dose:med-1:2026-11-15T08:00:00+00:00",
    rule_id=None,
    evidence={"medication_id": "med-1"},
)
```

## Catalog helpers

Import these from `intelligence.rules`:

- `load_catalog(path=None)`
- `validate_catalog(catalog)`
- `get_rule(catalog, rule_id)`
- `rule_is_approved_for(record, catalog, rule_id)`
- `matching_rules(catalog, metric, context=None)` returns catalog-approved rules. A null context does not filter by context. Care-plan membership stays in `rule_is_approved_for`.
- `applicable_rules(record, catalog, metric)`
- `rules_for_reading(record, catalog, metric=..., unit=..., context=...)`
- `compare(comparator, observed, bound)`
- `matches_rule(rule, observed)`
- `in_window(moment, as_of, rule)`
- `rule_min_occurrences(rule)`
- `coordination_priority(catalog, key)`

`adherence-repeat-gap` uses `min_occurrences` and `window_hours`. Its comparator and value describe that same occurrence count. `in_window` reads the width from the rule.

## Fixture

`fixtures/rule_catalog.json` includes:

- approved `glucose-fasting-review`
- unapproved `glucose-draft-unapproved`
- approved `bp-systolic-review`
- approved `adherence-repeat-gap`

The draft stays in the catalog so a caller can prove an unapproved rule does not run, including when a care plan lists its id.
