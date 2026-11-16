"""Care coordination tests.

Integration cases call intelligence.engine.evaluate. The chart is built in this
file. Coordination does not diagnose, prescribe, recommend taking a medicine,
or change a dose.
"""

import dataclasses
import inspect
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import intelligence.models as models
from intelligence.care_gaps import evaluate_care_gaps
from intelligence.consultations import evaluate_consultations
from intelligence.escalation import BANNED_PHRASES, build_events, new_model
from intelligence.models import (
    CareCoordinationEvent,
    Consultation,
    Finding,
    PatientRecord,
    PatientSummary,
    Reading,
)
from intelligence.rules import coordination_priority, rule_is_approved_for
from intelligence.summary import build_summary

PATIENT_ID = "11111111-1111-4111-8111-111111111111"
CLINICIAN = "Dr. Anika Shah"
IST = timezone(timedelta(hours=5, minutes=30))
MEDICATION_ID = "22222222-2222-4222-8222-222222222222"
PRESCRIBED_DOSAGE = "500 mg"
MONITORING = {
    "glucose": {"context": "fasting", "times": ["07:00"], "days": "daily"},
    "blood_pressure": {"times": ["08:10"], "days": "daily"},
}

MISSED_KINDS = {
    "adherence_missed",
    "missed_dose",
    "dose_missed",
    "adherence_dose_missed",
    "reported_missed_dose",
    "adherence_not_taken",
}
UNCONFIRMED_KINDS = {
    "adherence_unconfirmed",
    "adherence_unknown",
    "dose_unconfirmed",
    "unconfirmed_dose",
    "adherence_pending",
    "unknown_dose",
}
ADVICE_PHRASES = BANNED_PHRASES + ("take your medicine", "take the medicine", "change a dose")


def test_upcoming_consultation_names_clinician_type_and_time(as_of, catalog):
    when = datetime(2026, 11, 20, 9, 30, tzinfo=IST)
    record = build_record(
        consultations=[
            build_consultation(
                "visit-future",
                clinician=CLINICIAN,
                when=when,
                consultation_type="consultation",
                status="scheduled",
            )
        ]
    )
    findings = evaluate_consultations(record, as_of, catalog)
    assert len(findings) == 1
    finding = findings[0]
    assert _kind(finding) == "consultation_upcoming"
    assert _priority(finding) == "low"
    assert _rule_id(finding) is None
    assert _dedupe(finding) == "consult-upcoming:visit-future"
    text = _description(finding)
    assert CLINICIAN in text
    assert "consultation" in text
    assert when.isoformat() in text
    assert_no_advice([finding])


def test_appointment_at_as_of_is_upcoming_not_overdue(as_of, catalog):
    record = build_record(
        consultations=[
            build_consultation(
                "visit-now",
                clinician=CLINICIAN,
                when=as_of,
                consultation_type="consultation",
                status="scheduled",
            )
        ]
    )
    kinds = {_kind(finding) for finding in evaluate_consultations(record, as_of, catalog)}
    assert kinds == {"consultation_upcoming"}


def test_overdue_and_laboratory_findings_when_both_apply(as_of, catalog):
    when = as_of - timedelta(hours=2)
    record = build_record(
        consultations=[
            build_consultation(
                "lab-late",
                clinician=CLINICIAN,
                when=when,
                consultation_type="laboratory",
                status="scheduled",
            )
        ]
    )
    findings = evaluate_consultations(record, as_of, catalog)
    by_kind = {_kind(finding): finding for finding in findings}
    assert set(by_kind) == {"consultation_overdue", "laboratory_pending"}
    assert _dedupe(by_kind["consultation_overdue"]) == "consult-overdue:lab-late"
    assert _dedupe(by_kind["laboratory_pending"]) == "lab-pending:lab-late"
    assert _priority(by_kind["consultation_overdue"]) == coordination_priority(
        catalog, "overdue_consultation_priority"
    )
    assert _priority(by_kind["laboratory_pending"]) == coordination_priority(
        catalog, "pending_laboratory_priority"
    )
    assert _rule_id(by_kind["consultation_overdue"]) is None
    assert CLINICIAN in _description(by_kind["laboratory_pending"])
    assert "laboratory" in _description(by_kind["laboratory_pending"]).lower()
    assert when.isoformat() in _description(by_kind["consultation_overdue"])


def test_future_laboratory_is_upcoming_and_pending(as_of, catalog):
    when = as_of + timedelta(days=2)
    record = build_record(
        consultations=[
            build_consultation(
                "lab-next",
                clinician=CLINICIAN,
                when=when,
                consultation_type="laboratory",
                status="scheduled",
            )
        ]
    )
    kinds = {_kind(finding) for finding in evaluate_consultations(record, as_of, catalog)}
    assert kinds == {"consultation_upcoming", "laboratory_pending"}


def test_follow_up_task_when_no_later_visit_is_scheduled(as_of, catalog):
    record = build_record(
        consultations=[
            build_consultation(
                "visit-done",
                clinician=CLINICIAN,
                when=as_of - timedelta(days=10),
                consultation_type="consultation",
                status="completed",
            )
        ]
    )
    findings = evaluate_consultations(record, as_of, catalog)
    assert len(findings) == 1
    assert _kind(findings[0]) == "follow_up_task"
    assert _priority(findings[0]) == "low"
    assert _dedupe(findings[0]) == "follow-up:visit-done"
    assert _description(findings[0]) == "Follow-up task open after consultation visit-done"


def test_follow_up_task_not_opened_when_later_visit_exists(as_of, catalog):
    record = build_record(
        consultations=[
            build_consultation(
                "visit-done",
                clinician=CLINICIAN,
                when=as_of - timedelta(days=10),
                consultation_type="consultation",
                status="completed",
            ),
            build_consultation(
                "visit-next",
                clinician=CLINICIAN,
                when=as_of + timedelta(days=5),
                consultation_type="follow_up",
                status="scheduled",
            ),
        ]
    )
    kinds = {_kind(finding) for finding in evaluate_consultations(record, as_of, catalog)}
    assert "follow_up_task" not in kinds
    assert "consultation_upcoming" in kinds


def test_cancelled_follow_up_does_not_close_the_task(as_of, catalog):
    record = build_record(
        consultations=[
            build_consultation(
                "visit-done",
                clinician=CLINICIAN,
                when=as_of - timedelta(days=10),
                consultation_type="consultation",
                status="completed",
            ),
            build_consultation(
                "visit-cancelled",
                clinician=CLINICIAN,
                when=as_of + timedelta(days=5),
                consultation_type="follow_up",
                status="cancelled",
            ),
        ]
    )
    findings = [
        finding
        for finding in evaluate_consultations(record, as_of, catalog)
        if _kind(finding) == "follow_up_task"
    ]
    assert len(findings) == 1
    assert _dedupe(findings[0]) == "follow-up:visit-done"


def test_repeated_monitoring_gap_groups_missing_readings(as_of, catalog):
    record = build_record()
    findings = [
        make_finding(kind="glucose_missing", dedupe_key="glucose-missing:1"),
        make_finding(kind="bp_missing", dedupe_key="bp-missing:1"),
        make_finding(kind="glucose_rule_match", dedupe_key="glucose-rule:1", rule_id="glucose-fasting-gte-180"),
    ]
    created = evaluate_care_gaps(findings, record, as_of, catalog)
    kinds = [_kind(finding) for finding in created]
    assert kinds == ["repeated_monitoring_gap"]
    gap = created[0]
    assert _priority(gap) == "medium"
    assert _rule_id(gap) is None
    assert _dedupe(gap) == f"gap:monitoring:{PATIENT_ID}"
    listed = _flatten(_evidence(gap))
    assert "glucose-missing:1" in listed
    assert "bp-missing:1" in listed
    assert "threshold" not in _description(gap).lower()
    assert "180" not in _description(gap)


def test_repeated_monitoring_gap_respects_catalog_count(as_of):
    record = build_record()
    findings = [
        make_finding(kind="glucose_missing", dedupe_key="glucose-missing:1"),
        make_finding(kind="bp_missing", dedupe_key="bp-missing:1"),
    ]
    catalog = {"coordination_defaults": {"repeated_gap_count": 3}}
    assert evaluate_care_gaps(findings, record, as_of, catalog) == []
    catalog["coordination_defaults"]["repeated_gap_count"] = 2
    assert len(evaluate_care_gaps(findings, record, as_of, catalog)) == 1


def test_one_missing_reading_is_not_a_repeated_gap(as_of, catalog):
    record = build_record()
    findings = [make_finding(kind="glucose_missing", dedupe_key="glucose-missing:1")]
    assert evaluate_care_gaps(findings, record, as_of, catalog) == []


def test_recurring_adherence_concern_copies_rule_and_reasons(as_of, catalog):
    record = build_record()
    findings = [
        make_finding(
            kind="adherence_repeated_gap",
            dedupe_key="adherence-gap:1",
            rule_id="adherence-repeated",
            priority="medium",
            evidence={"reported_reasons": ["away from home", "asleep"]},
        )
    ]
    created = evaluate_care_gaps(findings, record, as_of, catalog)
    assert len(created) == 1
    concern = created[0]
    assert _kind(concern) == "recurring_adherence_concern"
    assert _rule_id(concern) == "adherence-repeated"
    assert _priority(concern) == "medium"
    assert _dedupe(concern) == f"gap:adherence:{PATIENT_ID}"
    text = _description(concern)
    assert text.startswith("Recurring reported adherence gap for care coordination review.")
    assert "away from home" in text
    assert "asleep" in text
    assert "away from home" in _flatten(_evidence(concern))


def test_care_gaps_do_not_pass_other_findings_through(as_of, catalog):
    record = build_record()
    findings = [make_finding(kind="glucose_rule_match", dedupe_key="glucose-rule:1", rule_id="glucose-fasting-gte-180")]
    assert evaluate_care_gaps(findings, record, as_of, catalog) == []


def test_pending_care_task_per_overdue_or_laboratory_finding(as_of, catalog):
    record = build_record()
    findings = [
        make_finding(kind="consultation_overdue", dedupe_key="consult-overdue:visit-1", priority="high"),
        make_finding(kind="laboratory_pending", dedupe_key="lab-pending:lab-1", priority="medium"),
        make_finding(kind="consultation_upcoming", dedupe_key="consult-upcoming:visit-2"),
    ]
    created = evaluate_care_gaps(findings, record, as_of, catalog)
    assert [_kind(finding) for finding in created] == ["pending_care_task", "pending_care_task"]
    assert _dedupe(created[0]) == "gap:consult-overdue:visit-1"
    assert _dedupe(created[1]) == "gap:lab-pending:lab-1"
    assert _rule_id(created[0]) is None
    assert _priority(created[0]) == "high"
    assert _priority(created[1]) == "medium"


def test_events_drop_unapproved_rules_and_duplicate_keys(as_of, catalog):
    approved = find_rule(catalog, metric="blood_glucose", approved=True, threshold=180)
    unapproved = find_rule(catalog, metric="blood_glucose", approved=False, threshold=140)
    approved_id = rule_id(approved)
    unapproved_id = rule_id(unapproved)
    record = build_record(rule_ids=[approved_id, unapproved_id], rules=[approved, unapproved])
    assert _approved_for(catalog, unapproved_id, record) is False
    assert _approved_for(catalog, approved_id, record) is True
    findings = [
        make_finding(
            kind="glucose_rule_match",
            dedupe_key="glucose-rule:approved",
            rule_id=approved_id,
            priority="high",
            description="Fasting glucose 190 mg/dL met an approved coordination rule.",
        ),
        make_finding(
            kind="glucose_rule_match",
            dedupe_key="glucose-rule:draft",
            rule_id=unapproved_id,
            priority="medium",
            description="Fasting glucose 150 mg/dL met a draft rule.",
        ),
        make_finding(
            kind="glucose_rule_match",
            dedupe_key="glucose-rule:approved",
            rule_id=approved_id,
            priority="high",
            description="Duplicate fasting glucose rule match.",
        ),
    ]
    events, escalations = build_events(findings, record, as_of, catalog, None)
    assert len(events) == 1
    assert len(escalations) == 1
    assert _event_type(events[0]) == "glucose_rule_match"
    assert _dedupe(events[0]) == "glucose-rule:approved"
    assert _rule_id(events[0]) == approved_id
    assert events[0].status == "open"
    assert events[0].requires_human_review is True
    assert escalations[0].opened_at == as_of
    again, again_escalations = build_events(
        findings,
        record,
        as_of,
        catalog,
        {"glucose-rule:approved"},
    )
    assert again == []
    assert again_escalations == []


def test_event_team_selection(as_of, catalog):
    approved = find_rule(catalog, metric="blood_glucose", approved=True, threshold=180)
    approved_id = rule_id(approved)
    record = build_record(rule_ids=[approved_id], rules=[approved])
    coordination = make_finding(kind="consultation_upcoming", dedupe_key="consult-upcoming:1")
    routed = make_finding(
        kind="consultation_overdue",
        dedupe_key="consult-overdue:1",
        evidence={"team": "night-desk"},
    )
    ruled = make_finding(
        kind="glucose_rule_match",
        dedupe_key="glucose-rule:1",
        rule_id=approved_id,
        priority="high",
    )
    events, _ = build_events([coordination, routed, ruled], record, as_of, catalog)
    by_key = {_dedupe(event): event for event in events}
    assert by_key["consult-upcoming:1"].team == "care-coordination"
    assert by_key["consult-overdue:1"].team == "night-desk"
    assert by_key["glucose-rule:1"].team == _catalog_team(approved)


def test_banned_phrases_never_appear_in_event_descriptions(as_of, catalog):
    record = build_record()
    finding = make_finding(
        kind="adherence_missed",
        dedupe_key="adherence-missed:1",
        description="Please take the medicine and change a dose.",
    )
    events, _ = build_events([finding], record, as_of, catalog)
    assert len(events) == 1
    text = _description(events[0]).lower()
    assert "take the medicine" not in text
    assert "change a dose" not in text
    assert "diagnos" not in text
    assert "prescri" not in text
    assert events[0].requires_human_review is True


def test_summary_lists_recent_readings_and_adherence_counts(as_of):
    readings = []
    for index in range(20):
        readings.append(
            build_reading(
                f"glucose-{index}",
                measurement_type="blood_glucose",
                value=100 + index,
                unit="mg/dL",
                context="fasting",
                when=as_of - timedelta(hours=2, minutes=index),
                source="glucometer",
            )
        )
    pressure_at = as_of - timedelta(minutes=2)
    readings.extend(
        [
            build_reading(
                "glucose-recent",
                measurement_type="blood_glucose",
                value=112,
                unit="mg/dL",
                context="fasting",
                when=as_of - timedelta(minutes=1),
                source="glucometer",
            ),
            build_reading(
                "glucose-manual",
                measurement_type="blood_glucose",
                value=118,
                unit="mg/dL",
                context="fasting",
                when=as_of - timedelta(seconds=30),
                source="manual",
            ),
            build_reading(
                "bp-systolic",
                measurement_type="systolic_blood_pressure",
                value=122,
                secondary=78,
                unit="mmHg",
                context=None,
                when=pressure_at,
                source="home_monitor",
            ),
            build_reading(
                "bp-diastolic",
                measurement_type="diastolic_blood_pressure",
                value=78,
                unit="mmHg",
                context=None,
                when=pressure_at,
                source="home_monitor",
            ),
        ]
    )
    readings.append(
        build_reading(
            "future-glucose",
            measurement_type="blood_glucose",
            value=130,
            unit="mg/dL",
            context="fasting",
            when=as_of + timedelta(hours=1),
            source="glucometer",
        )
    )
    doses = [
        build_dose("dose-taken", when=as_of - timedelta(hours=5), status="taken", source="app"),
        build_dose(
            "dose-missed-app",
            when=as_of - timedelta(hours=4),
            status="missed",
            reason="away from home",
            source="app",
        ),
        build_dose(
            "dose-missed-call",
            when=as_of - timedelta(hours=3),
            status="missed",
            reason=None,
            source="call_self_report",
        ),
        build_dose(
            "dose-missed-inferred",
            when=as_of - timedelta(hours=2),
            status="missed",
            reason=None,
            source="inferred",
        ),
        build_dose("dose-unknown", when=as_of - timedelta(hours=1), status="unknown", source=None),
        build_dose("dose-none", when=as_of - timedelta(minutes=30), status=None, source=None),
        build_dose("dose-future", when=as_of + timedelta(hours=2), status="missed", reason="later", source="app"),
    ]
    open_event = new_model(
        CareCoordinationEvent,
        id="event-open",
        patient_id=PATIENT_ID,
        event_type="consultation_upcoming",
        kind="consultation_upcoming",
        description=f"Scheduled consultation with {CLINICIAN} at {as_of.isoformat()}.",
        event_description=f"Scheduled consultation with {CLINICIAN} at {as_of.isoformat()}.",
        priority="low",
        status="open",
        requires_human_review=True,
        dedupe_key="consult-upcoming:1",
        rule_id=None,
        team="care-coordination",
        evidence={},
        opened_at=as_of,
        created_at=as_of,
    )
    resolved_event = SimpleNamespace(
        event_type="follow_up_task",
        event_description="Follow-up task open after consultation visit-done",
        description="Follow-up task open after consultation visit-done",
        priority="low",
        status="resolved",
        dedupe_key="follow-up:visit-done",
    )
    record = build_record(readings=readings, doses=doses)
    summary = build_summary(record, [open_event, resolved_event], as_of)
    adherence = _adherence(summary)
    assert adherence["patient_id"] == PATIENT_ID
    assert adherence["as_of"] == as_of.isoformat()
    rows = _rows(summary)
    assert len(rows) == 20
    assert _row(rows[0], "source") == "manual"
    assert _origin_text(_row(rows[0], "origin")) == "patient_reported"
    glucometer = next(row for row in rows if _row(row, "source") == "glucometer")
    assert _origin_text(_row(glucometer, "origin")) == "device_recorded"
    identifiers = {_row(row, "measured_at") for row in rows}
    assert (as_of + timedelta(hours=1)).isoformat() not in identifiers
    types = {_row(row, "measurement_type") for row in rows}
    assert "systolic_blood_pressure" in types
    assert "diastolic_blood_pressure" in types
    measured = {_row(row, "measurement_type"): _row(row, "measured_at") for row in rows}
    assert "T" in measured["systolic_blood_pressure"]
    assert measured["systolic_blood_pressure"] == measured["diastolic_blood_pressure"]
    assert adherence["taken"] == 1
    assert adherence["missed"] == 3
    assert adherence["unconfirmed"] == 2
    missed_items = adherence["missed_items"]
    assert len(missed_items) == 3
    assert missed_items[0]["medication_name"] == "Metformin"
    assert missed_items[0]["reported_reason"] == "away from home"
    sources = {item["report_source"] for item in missed_items}
    assert sources == {"patient-reported", "inferred"}
    assert all(item["schedule_time"] for item in missed_items)
    assert "later" not in {item["reported_reason"] for item in missed_items}
    tasks = _tasks(summary)
    assert len(tasks) == 1
    task = tasks[0]
    assert _row(task, "event_type") == "consultation_upcoming"
    assert _row(task, "dedupe_key") == "consult-upcoming:1"
    assert _row(task, "priority") == "low"
    assert "diagnos" not in _row(task, "description").lower()


def test_normal_day_has_no_rule_escalation(as_of, catalog):
    record = normal_record(as_of)
    result = run_evaluate(record, as_of, catalog)
    events, _, summary = result
    assert [event for event in events if _rule_id(event)] == []
    assert_no_advice(events)
    summary = summary if summary is not None else build_summary(record, events, as_of)
    rows = _rows(summary)
    manual = next(row for row in rows if _row(row, "source") == "manual")
    glucometer = next(row for row in rows if _row(row, "source") == "glucometer")
    assert _origin_text(_row(manual, "origin")) == "patient_reported"
    assert _origin_text(_row(glucometer, "origin")) == "device_recorded"
    types = {_row(row, "measurement_type") for row in rows}
    assert "systolic_blood_pressure" in types
    assert "diastolic_blood_pressure" in types


def test_missing_data_opens_coordination_events(as_of, catalog):
    record = missing_record(as_of)
    events, _, _ = run_evaluate(record, as_of, catalog)
    kinds = {_event_type(event) for event in events}
    assert "glucose_missing" in kinds
    assert kinds & MISSED_KINDS, kinds
    assert kinds & UNCONFIRMED_KINDS, kinds
    assert_no_advice(events)
    blob = " ".join(_description(event).lower() for event in events)
    assert "take your medicine" not in blob
    assert "take the medicine" not in blob
    assert "change a dose" not in blob


def test_approved_glucose_rule_escalates_once(as_of, catalog):
    approved = find_rule(catalog, metric="blood_glucose", approved=True, threshold=180)
    record = build_record(
        readings=[
            build_reading(
                "glucose-190",
                measurement_type="blood_glucose",
                value=190,
                unit="mg/dL",
                context="fasting",
                when=datetime(2026, 11, 15, 7, 0, tzinfo=IST),
                source="glucometer",
            )
        ],
        rule_ids=[rule_id(approved)],
        rules=[approved],
        monitoring={},
    )
    events, _, _ = run_evaluate(record, as_of, catalog)
    matches = [event for event in events if _event_type(event) == "glucose_rule_match"]
    assert len(matches) == 1
    assert _rule_id(matches[0]) == rule_id(approved)
    assert_no_advice(matches)
    key = _dedupe(matches[0])
    again, _, _ = run_evaluate(record, as_of, catalog, existing_open_keys={key})
    assert [event for event in again if _dedupe(event) == key] == []
    assert [event for event in again if _event_type(event) == "glucose_rule_match"] == []


def test_unapproved_glucose_rule_does_not_escalate(as_of, catalog):
    unapproved = find_rule(catalog, metric="blood_glucose", approved=False, threshold=140)
    readings = [
        build_reading(
            f"glucose-day-{day}",
            measurement_type="blood_glucose",
            value=110,
            unit="mg/dL",
            context="fasting",
            when=datetime(2026, 11, day, 7, 0, tzinfo=IST),
            source="glucometer",
        )
        for day in range(8, 15)
    ]
    readings.append(
        build_reading(
            "glucose-150",
            measurement_type="blood_glucose",
            value=150,
            unit="mg/dL",
            context="fasting",
            when=datetime(2026, 11, 15, 7, 0, tzinfo=IST),
            source="glucometer",
        )
    )
    record = build_record(
        readings=readings,
        rule_ids=[rule_id(unapproved)],
        rules=[unapproved],
        monitoring=MONITORING,
    )
    events, _, _ = run_evaluate(record, as_of, catalog)
    assert [event for event in events if _event_type(event) == "glucose_rule_match"] == []
    assert [event for event in events if _rule_id(event) == rule_id(unapproved)] == []


def test_approved_blood_pressure_rule_escalates_without_diagnosis_language(as_of, catalog):
    approved = find_rule(catalog, metric="systolic_blood_pressure", approved=True, threshold=160)
    record = build_record(
        readings=[
            build_reading(
                "bp-systolic-170",
                measurement_type="systolic_blood_pressure",
                value=170,
                secondary=88,
                unit="mmHg",
                context="resting",
                when=datetime(2026, 11, 15, 8, 0, tzinfo=IST),
                source="home_monitor",
            ),
            build_reading(
                "bp-diastolic-88",
                measurement_type="diastolic_blood_pressure",
                value=88,
                unit="mmHg",
                context="resting",
                when=datetime(2026, 11, 15, 8, 0, tzinfo=IST),
                source="home_monitor",
            ),
        ],
        rule_ids=[rule_id(approved)],
        rules=[approved],
        monitoring={},
    )
    events, _, _ = run_evaluate(record, as_of, catalog)
    matches = [event for event in events if _event_type(event) == "bp_rule_match"]
    assert len(matches) == 1
    assert "hypertension" not in _description(matches[0]).lower()
    assert_no_advice(matches)


def test_overdue_consultation_and_pending_laboratory_open_events(as_of, catalog):
    record = build_record(
        readings=daily_readings(as_of),
        doses=taken_doses(as_of),
        consultations=[
            build_consultation(
                "visit-overdue",
                clinician=CLINICIAN,
                when=as_of - timedelta(days=1),
                consultation_type="consultation",
                status="scheduled",
            ),
            build_consultation(
                "lab-pending",
                clinician="City Laboratory",
                when=as_of + timedelta(days=3),
                consultation_type="laboratory",
                status="scheduled",
            ),
        ],
        monitoring=MONITORING,
    )
    events, _, _ = run_evaluate(record, as_of, catalog)
    kinds = {_event_type(event) for event in events}
    assert "consultation_overdue" in kinds
    assert "laboratory_pending" in kinds
    assert "pending_care_task" in kinds
    overdue = next(event for event in events if _event_type(event) == "consultation_overdue")
    laboratory = next(event for event in events if _event_type(event) == "laboratory_pending")
    assert CLINICIAN in _description(overdue)
    assert "laboratory" in _description(laboratory).lower()
    assert_no_advice(events)


def normal_record(as_of: datetime) -> PatientRecord:
    readings = daily_readings(as_of)
    readings.append(
        build_reading(
            "glucose-manual",
            measurement_type="blood_glucose",
            value=118,
            unit="mg/dL",
            context="fasting",
            when=datetime(2026, 11, 15, 10, 0, tzinfo=IST),
            source="manual",
        )
    )
    return build_record(
        readings=readings,
        doses=taken_doses(as_of),
        consultations=[
            build_consultation(
                "visit-future",
                clinician=CLINICIAN,
                when=datetime(2026, 11, 20, 9, 30, tzinfo=IST),
                consultation_type="consultation",
                status="scheduled",
            )
        ],
        monitoring=MONITORING,
    )


def missing_record(as_of: datetime) -> PatientRecord:
    readings = [
        reading
        for reading in daily_readings(as_of)
        if not (
            _reading_day(reading) in {14, 15}
            and _reading_type(reading) == "blood_glucose"
        )
    ]
    doses = []
    for dose in taken_doses(as_of):
        moment = _dose_time(dose)
        if moment == datetime(2026, 11, 14, 8, 0, tzinfo=IST):
            doses.append(
                build_dose(
                    "dose-missed",
                    when=moment,
                    status="missed",
                    reason="away from home",
                    source="app",
                )
            )
        elif moment == datetime(2026, 11, 14, 20, 0, tzinfo=IST):
            doses.append(build_dose("dose-unknown", when=moment, status="unknown", source=None))
        else:
            doses.append(dose)
    return build_record(
        readings=readings,
        doses=doses,
        monitoring=MONITORING,
    )


def daily_readings(as_of: datetime) -> list:
    rows = []
    for day in range(1, 16):
        glucose_at = datetime(2026, 11, day, 7, 0, tzinfo=IST)
        pressure_at = datetime(2026, 11, day, 8, 10, tzinfo=IST)
        if glucose_at <= as_of:
            rows.append(
                build_reading(
                    f"glucose-{day}",
                    measurement_type="blood_glucose",
                    value=112,
                    unit="mg/dL",
                    context="fasting",
                    when=glucose_at,
                    source="glucometer",
                )
            )
        if pressure_at <= as_of:
            rows.append(
                build_reading(
                    f"systolic-{day}",
                    measurement_type="systolic_blood_pressure",
                    value=122,
                    secondary=78,
                    unit="mmHg",
                    context="resting",
                    when=pressure_at,
                    source="home_monitor",
                )
            )
            rows.append(
                build_reading(
                    f"diastolic-{day}",
                    measurement_type="diastolic_blood_pressure",
                    value=78,
                    unit="mmHg",
                    context="resting",
                    when=pressure_at,
                    source="home_monitor",
                )
            )
    return rows


def taken_doses(as_of: datetime) -> list:
    doses = []
    for day in range(1, 16):
        for hour in (8, 20):
            moment = datetime(2026, 11, day, hour, 0, tzinfo=IST)
            if moment <= as_of:
                doses.append(build_dose(f"dose-{day}-{hour}", when=moment, status="taken", source="app"))
    return doses


def build_record(
    *,
    readings=None,
    consultations=None,
    doses=None,
    rule_ids=None,
    rules=None,
    monitoring=None,
) -> PatientRecord:
    readings = list(readings or [])
    consultations = list(consultations or [])
    doses = list(doses or [])
    rule_ids = list(rule_ids or [])
    rules = list(rules or [])
    monitoring = dict(monitoring or {})
    medications = [build_medication()] if doses else []
    plan = build_plan(rule_ids, rules, monitoring)
    payload = {
        "id": PATIENT_ID,
        "patient_id": PATIENT_ID,
        "preferred_name": "Meera Iyer",
        "timezone": "Asia/Kolkata",
        "time_zone": "Asia/Kolkata",
        "tz": "Asia/Kolkata",
        "preferred_language": "hi",
        "language": "hi",
        "readings": readings,
        "health_readings": readings,
        "consultations": consultations,
        "appointments": consultations,
        "doses": doses,
        "adherence_logs": doses,
        "adherence_events": doses,
        "scheduled_doses": doses,
        "adherence": doses,
        "medications": medications,
        "care_plan": plan,
        "care_plans": [plan],
        "approved_rule_ids": rule_ids,
        "approved_rules": rule_ids if not _expects_rule_objects(PatientRecord, "approved_rules") else rules,
        "rule_ids": rule_ids,
        "monitoring_schedule": monitoring,
    }
    return new_model(PatientRecord, **_with_required(PatientRecord, payload))


def build_plan(rule_ids: list, rules: list, monitoring: dict):
    plan_cls = getattr(models, "CarePlan", None)
    payload = {
        "id": "plan-1",
        "patient_id": PATIENT_ID,
        "condition": "type_2_diabetes",
        "clinician": CLINICIAN,
        "timezone": "Asia/Kolkata",
        "monitoring_schedule": monitoring,
        "escalation_protocol": {"handoff": "clinician_review"},
        "schedule": monitoring,
        "approved_rule_ids": list(rule_ids),
        "approved_rules": list(rule_ids),
        "rule_ids": list(rule_ids),
        "rules": list(rules or rule_ids),
        "active_rule_ids": list(rule_ids),
    }
    if plan_cls is None:
        return SimpleNamespace(**payload)
    if _expects_rule_objects(plan_cls, "approved_rules"):
        payload["approved_rules"] = list(rules or [{"id": rule} for rule in rule_ids])
    return new_model(plan_cls, **_with_required(plan_cls, payload))


def build_medication():
    payload = {
        "id": MEDICATION_ID,
        "patient_id": PATIENT_ID,
        "medication_id": MEDICATION_ID,
        "medication_name": "Metformin",
        "name": "Metformin",
        "prescribed_dosage": PRESCRIBED_DOSAGE,
        "dosage": "500 mg",
        "frequency": "Twice daily",
        "schedule": {"times": ["08:00", "20:00"]},
        "times": ["08:00", "20:00"],
        "start_date": datetime(2019, 6, 15, tzinfo=timezone.utc).date(),
        "end_date": None,
        "active": True,
        "prescribing_clinician": CLINICIAN,
    }
    medication_cls = _model_class("Medication", "Medicine")
    if medication_cls is None:
        return SimpleNamespace(**payload)
    return new_model(medication_cls, **_with_required(medication_cls, payload))


def build_reading(
    reading_id: str,
    *,
    measurement_type: str,
    value: float,
    unit: str,
    context: str | None,
    when: datetime,
    source: str,
    secondary: float | None = None,
) -> Reading:
    payload = {
        "id": reading_id,
        "patient_id": PATIENT_ID,
        "measurement_type": measurement_type,
        "metric": measurement_type,
        "value": value,
        "secondary_value": secondary,
        "unit": unit,
        "measurement_context": context,
        "context": context,
        "measured_at": when,
        "source": source,
        "device_id": None,
        "data_quality": "valid",
        "support": None,
    }
    return new_model(Reading, **_with_required(Reading, payload))


def build_consultation(
    consultation_id: str,
    *,
    clinician: str,
    when: datetime,
    consultation_type: str,
    status: str,
) -> Consultation:
    payload = {
        "id": consultation_id,
        "patient_id": PATIENT_ID,
        "clinician": clinician,
        "clinician_name": clinician,
        "appointment_date": when,
        "scheduled_at": when,
        "consultation_type": consultation_type,
        "type": consultation_type,
        "status": status,
    }
    return new_model(Consultation, **_with_required(Consultation, payload))


def build_dose(
    dose_id: str,
    *,
    when: datetime,
    status: str | None,
    source: str | None,
    reason: str | None = None,
):
    payload = {
        "id": dose_id,
        "patient_id": PATIENT_ID,
        "medication_id": MEDICATION_ID,
        "medication_name": "Metformin",
        "medicine_name": "Metformin",
        "prescribed_dosage": PRESCRIBED_DOSAGE,
        "schedule_time": when,
        "scheduled_at": when,
        "due_at": when,
        "reported_status": status,
        "status": status,
        "adherence_status": status,
        "reported_reason": reason,
        "reason": reason,
        "source": source,
        "report_source": source,
    }
    dose_cls = _model_class(
        "DoseEvent",
        "Dose",
        "AdherenceDose",
        "ScheduledDose",
        "AdherenceEvent",
        "AdherenceLog",
        "AdherenceReport",
        "MedicationDose",
    )
    if dose_cls is None:
        return SimpleNamespace(**payload)
    return new_model(dose_cls, **_with_required(dose_cls, payload))


def make_finding(
    *,
    kind: str,
    dedupe_key: str,
    priority: str = "low",
    rule_id: str | None = None,
    description: str | None = None,
    evidence: dict | None = None,
) -> Finding:
    text = description or f"Care coordination finding {kind}."
    return new_model(
        Finding,
        id=f"{kind}:{dedupe_key}",
        patient_id=PATIENT_ID,
        kind=kind,
        finding_kind=kind,
        finding_type=kind,
        event_type=kind,
        priority=priority,
        rule_id=rule_id,
        dedupe_key=dedupe_key,
        description=text,
        event_description=text,
        evidence=dict(evidence or {}),
    )


def run_evaluate(record, as_of, catalog, existing_open_keys=None):
    from intelligence.engine import evaluate

    signature = inspect.signature(evaluate)
    kwargs = {}
    if "record" in signature.parameters:
        kwargs["record"] = record
    if "as_of" in signature.parameters:
        kwargs["as_of"] = as_of
    if "catalog" in signature.parameters:
        kwargs["catalog"] = catalog
    if existing_open_keys is not None:
        if "existing_open_keys" not in signature.parameters:
            raise AssertionError("evaluate() has no existing_open_keys parameter")
        kwargs["existing_open_keys"] = existing_open_keys
    if kwargs and "record" in kwargs and "as_of" in kwargs:
        result = evaluate(**kwargs)
    elif existing_open_keys is None:
        result = evaluate(record, as_of, catalog)
    else:
        result = evaluate(record, as_of, catalog, existing_open_keys)
    return unpack_result(result)


def unpack_result(result):
    if isinstance(result, list):
        return result, [], None
    if isinstance(result, tuple):
        summary = None
        lists = []
        for item in result:
            if _looks_like_summary(item):
                summary = item
            elif isinstance(item, list):
                lists.append(item)
        events = []
        escalations = []
        for items in lists:
            if not items:
                if not events:
                    events = items
                continue
            sample = items[0]
            if hasattr(sample, "event_type") or hasattr(sample, "requires_human_review"):
                events = items
            elif hasattr(sample, "opened_at") and not hasattr(sample, "requires_human_review"):
                escalations = items
            elif events == []:
                events = items
        return events, escalations, summary
    if isinstance(result, dict):
        return (
            result.get("events") or result.get("care_events") or [],
            result.get("escalations") or [],
            result.get("summary"),
        )
    return (
        list(getattr(result, "events", []) or []),
        list(getattr(result, "escalations", []) or []),
        getattr(result, "summary", None),
    )


def rules_of(catalog: dict) -> list[dict]:
    bucket = catalog.get("rules", catalog.get("threshold_rules", []))
    if isinstance(bucket, dict):
        rows = []
        for key, rule in bucket.items():
            if isinstance(rule, dict):
                row = dict(rule)
                row.setdefault("id", row.get("rule_id", key))
                rows.append(row)
        return rows
    return [dict(rule) for rule in bucket if isinstance(rule, dict)]


def find_rule(catalog: dict, *, metric: str, approved: bool, threshold: float) -> dict:
    aliases = {metric, metric.removesuffix("_blood_pressure")}
    if metric == "blood_glucose":
        aliases.add("glucose")
    if metric == "systolic_blood_pressure":
        aliases.update({"systolic", "blood_pressure_systolic"})
    for rule in rules_of(catalog):
        rule_metric = rule.get("measurement_type") or rule.get("metric") or rule.get("measure")
        if rule_metric not in aliases:
            continue
        if _rule_approved(rule) != approved:
            continue
        context = rule.get("measurement_context", rule.get("context"))
        if metric == "blood_glucose" and context not in (None, "fasting"):
            continue
        comparator = str(rule.get("comparator") or rule.get("op") or "gte").lower()
        if comparator not in {"gte", ">=", "ge", "greater_than_or_equal"}:
            continue
        if _rule_threshold(rule) == threshold:
            return rule
    raise AssertionError(f"catalog has no {metric} rule approved={approved} threshold={threshold}")


def rule_id(rule: dict) -> str:
    value = rule.get("id", rule.get("rule_id"))
    if value is None:
        raise AssertionError(f"rule has no id: {rule}")
    return str(value)


def _approved_for(catalog, rule, record) -> bool:
    signature = inspect.signature(rule_is_approved_for)
    pool = {
        "catalog": catalog,
        "rule_catalog": catalog,
        "rules": catalog,
        "rule_id": rule,
        "rule": rule,
        "record": record,
        "patient_record": record,
        "patient": record,
    }
    names = [
        name
        for name, param in signature.parameters.items()
        if param.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    ]
    if names and all(name in pool for name in names):
        return bool(rule_is_approved_for(**{name: pool[name] for name in names}))
    return bool(rule_is_approved_for(catalog, rule, record))


def _rule_approved(rule: dict) -> bool:
    if "approved" in rule:
        return bool(rule["approved"])
    return str(rule.get("status", "")).lower() == "approved"


def _rule_threshold(rule: dict) -> float | None:
    for key in ("value", "threshold", "bound", "limit"):
        if key in rule and isinstance(rule[key], (int, float)) and not isinstance(rule[key], bool):
            return float(rule[key])
    return None


def _catalog_team(rule: dict) -> str:
    for key in ("team", "owner_team", "escalation_team", "queue"):
        value = rule.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("escalation", "routing", "assignment"):
        nested = rule.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("team"), str):
            return nested["team"]
    return "care-coordination"


def _with_required(cls, payload: dict) -> dict:
    fields = _fields(cls)
    if not fields:
        return payload
    completed = dict(payload)
    for name, required in fields.items():
        if name in completed or not required:
            continue
        if name in {"patient_id", "id"}:
            completed[name] = PATIENT_ID
        elif name in {"timezone", "time_zone", "tz"}:
            completed[name] = "Asia/Kolkata"
        elif name in {"preferred_name", "name"}:
            completed[name] = "Meera Iyer"
        elif name in {"preferred_language", "language"}:
            completed[name] = "hi"
        else:
            raise TypeError(f"{cls.__name__} requires {name}")
    return completed


def _expects_rule_objects(cls, field_name: str) -> bool:
    annotation = _annotation(cls, field_name)
    return "dict" in str(annotation).lower()


def _fields(cls) -> dict[str, bool]:
    if dataclasses.is_dataclass(cls):
        return {
            field.name: field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
            for field in dataclasses.fields(cls)
        }
    model_fields = getattr(cls, "model_fields", None)
    if isinstance(model_fields, dict):
        return {name: field.is_required() for name, field in model_fields.items()}
    return {}


def _annotation(cls, field_name: str):
    if dataclasses.is_dataclass(cls):
        for field in dataclasses.fields(cls):
            if field.name == field_name:
                return field.type
    model_fields = getattr(cls, "model_fields", None)
    if isinstance(model_fields, dict) and field_name in model_fields:
        return model_fields[field_name].annotation
    return None


def _model_class(*names: str):
    for name in names:
        cls = getattr(models, name, None)
        if cls is not None:
            return cls
    return None


def _kind(finding) -> str:
    return str(getattr(finding, "kind", getattr(finding, "finding_kind", "")))


def _event_type(event) -> str:
    value = getattr(event, "event_type", None)
    if value is None:
        value = getattr(event, "kind", None)
    return "" if value is None else str(value)


def _priority(finding):
    return getattr(finding, "priority", None)


def _rule_id(obj):
    value = getattr(obj, "rule_id", None)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe(obj) -> str:
    return str(getattr(obj, "dedupe_key"))


def _description(obj) -> str:
    value = getattr(obj, "description", None)
    if value is None:
        value = getattr(obj, "event_description", "")
    return "" if value is None else str(value)


def _evidence(obj):
    return getattr(obj, "evidence", {})


def _flatten(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _flatten(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _flatten(item)
    else:
        yield value


def _rows(summary):
    value = getattr(summary, "recent_readings", None)
    if value is None and isinstance(summary, dict):
        value = summary.get("recent_readings")
    return list(value or [])


def _tasks(summary):
    value = getattr(summary, "outstanding_tasks", None)
    if value is None and isinstance(summary, dict):
        value = summary.get("outstanding_tasks")
    return list(value or [])


def _adherence(summary) -> dict:
    value = getattr(summary, "adherence", None)
    if value is None and isinstance(summary, dict):
        value = summary.get("adherence")
    if isinstance(value, dict):
        return value
    return {
        "taken": getattr(value, "taken"),
        "missed": getattr(value, "missed"),
        "unconfirmed": getattr(value, "unconfirmed"),
        "missed_items": list(getattr(value, "missed_items")),
    }


def _summary_clock(summary) -> str:
    value = getattr(summary, "as_of", None)
    if value is None and isinstance(summary, dict):
        value = summary.get("as_of")
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _row(row, key):
    if isinstance(row, dict):
        return row[key]
    return getattr(row, key)


def _origin_text(value) -> str:
    if hasattr(value, "value"):
        value = value.value
    return str(value)


def _reading_day(reading) -> int:
    return reading.measured_at.astimezone(IST).day


def _reading_type(reading) -> str:
    return str(reading.measurement_type)


def _dose_time(dose) -> datetime:
    return getattr(dose, "schedule_time")


def _looks_like_summary(value) -> bool:
    return isinstance(value, PatientSummary) or (
        hasattr(value, "recent_readings") and hasattr(value, "outstanding_tasks")
    )


def assert_no_advice(items) -> None:
    for item in items:
        text = _description(item).lower()
        for phrase in ADVICE_PHRASES:
            assert phrase not in text
