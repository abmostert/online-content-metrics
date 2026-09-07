#!/usr/bin/env python3
"""
network_metrics.py — minimal networking metrics logger + reporter (standard library only)

Data model:
- people.json  : { "<person_id>": {"name": "...", "notes": "...", "created_at": "...", "tier": "A|B|C"} , ... }
- events.jsonl : one JSON object per line (append-only)

Notes:
- Backwards compatible: if a person has no "tier", they are bucketed as "U" (unknown).
- You said you do NOT log connection_requested; acceptance_rate is removed accordingly.
- "scheduling_sent" dropped; keep call_scheduled.

Event types (recommended, aligned to workflow v4.5):
- connection_accepted
- legibility_sent
- value_ping_sent          (proactive give)
- public_comment           (proactive give)
- question_sent
- reprompt_sent
- reply_received
- call_ask_sent
- call_agreed
- call_scheduled
- call_completed
- bow_out_sent
- closed_dormant

Usage examples:
  python network_metrics.py add-person --id samia --name "Samia A." --tier A
  python network_metrics.py set-tier --id samia --tier B
  python network_metrics.py log --id samia --event legibility_sent --meta '{"snippet":"L1"}'
  python network_metrics.py metrics --since 2026-01-26 --until 2026-02-23
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, Any, Iterable, Optional, Tuple

ISO_DT_FMT = "%Y-%m-%dT%H:%M:%SZ"
ISO_D_FMT = "%Y-%m-%d"

# Workflow v4.5 aligned events (no connection_requested, no scheduling_sent)
DEFAULT_EVENTS = [
    "connection_accepted",
    "legibility_sent",
    "value_ping_sent",
    "public_comment",
    "question_sent",
    "reprompt_sent",
    "reply_received",
    "call_ask_sent",
    "call_agreed",
    "call_scheduled",
    "call_completed",
    "bow_out_sent",
    "closed_dormant",
]

VALID_TIERS = {"A", "B", "C", "U"}  # U = unknown bucket for missing tier


def utc_now_iso() -> str:
    return datetime.utcnow().strftime(ISO_DT_FMT)


def die(msg: str, code: int = 2) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)


def ensure_dir(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def load_people(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_people(path: str, people: Dict[str, Any]) -> None:
    ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(people, f, indent=2, ensure_ascii=False, sort_keys=True)


def append_event(path: str, event_obj: Dict[str, Any]) -> None:
    ensure_dir(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event_obj, ensure_ascii=False) + "\n")


def iter_events(path: str) -> Iterable[Dict[str, Any]]:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def parse_ymd(s: str) -> date:
    try:
        return datetime.strptime(s, ISO_D_FMT).date()
    except ValueError:
        die(f"Bad date '{s}'. Use YYYY-MM-DD.")


def in_date_range(ts_iso: str, since: Optional[date], until: Optional[date]) -> bool:
    try:
        dt = datetime.strptime(ts_iso, ISO_DT_FMT)
    except ValueError:
        return False
    d = dt.date()
    if since and d < since:
        return False
    if until and d > until:
        return False
    return True


def get_person_tier(people: Dict[str, Any], person_id: str) -> str:
    """Return A/B/C or U if missing/invalid/unknown person."""
    rec = people.get(person_id)
    if not isinstance(rec, dict):
        return "U"
    t = (rec.get("tier") or "").strip().upper()
    if t in {"A", "B", "C"}:
        return t
    return "U"


@dataclass
class FunnelCounts:
    # Core activity
    connection_accepted: int = 0
    legibility_sent: int = 0
    value_ping_sent: int = 0
    public_comment: int = 0
    question_sent: int = 0
    reprompt_sent: int = 0
    reply_received: int = 0
    call_ask_sent: int = 0
    call_agreed: int = 0
    call_scheduled: int = 0
    call_completed: int = 0
    bow_out_sent: int = 0
    closed_dormant: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {k: getattr(self, k) for k in self.__annotations__.keys()}


def safe_div(n: int, d: int) -> Optional[float]:
    if d == 0:
        return None
    return n / d


def fmt_pct(x: Optional[float]) -> str:
    if x is None:
        return "—"
    return f"{x*100:.1f}%"


def compute_counts(events_path: str, since: Optional[date], until: Optional[date]) -> FunnelCounts:
    c = FunnelCounts()
    for e in iter_events(events_path):
        ts = e.get("ts")
        if not isinstance(ts, str):
            continue
        if not in_date_range(ts, since, until):
            continue
        ev = e.get("event")
        if ev in c.__annotations__:
            setattr(c, ev, getattr(c, ev) + 1)
    return c


def compute_counts_by_tier(
    events_path: str, people: Dict[str, Any], since: Optional[date], until: Optional[date]
) -> Dict[str, FunnelCounts]:
    buckets: Dict[str, FunnelCounts] = {t: FunnelCounts() for t in ["A", "B", "C", "U"]}
    for e in iter_events(events_path):
        ts = e.get("ts")
        if not isinstance(ts, str):
            continue
        if not in_date_range(ts, since, until):
            continue
        pid = e.get("person_id")
        if not isinstance(pid, str):
            tier = "U"
        else:
            tier = get_person_tier(people, pid)

        ev = e.get("event")
        if ev in FunnelCounts.__annotations__:
            setattr(buckets[tier], ev, getattr(buckets[tier], ev) + 1)
    return buckets


def compute_ratios(c: FunnelCounts) -> Dict[str, Optional[float]]:
    """
    Cohort-safe ratios:
    - No acceptance_rate (since connection_requested not logged).
    - Avoid using connection_accepted as denominator for "success" KPIs.
    """
    proactive_gives = c.value_ping_sent + c.public_comment

    return {
        # Engagement quality
        "reply_rate_legibility": safe_div(c.reply_received, c.legibility_sent),
        "reply_rate_value_ping": safe_div(c.reply_received, c.value_ping_sent),
        "reply_rate_questions": safe_div(c.reply_received, c.question_sent),

        # Call funnel health
        "call_yes_rate": safe_div(c.call_agreed, c.call_ask_sent),
        "schedule_rate_from_yes": safe_div(c.call_scheduled, c.call_agreed),
        "completion_rate": safe_div(c.call_completed, c.call_scheduled),

        # Stable KPI alternatives (don’t depend on accepted)
        "calls_completed_per_legibility": safe_div(c.call_completed, c.legibility_sent),
        "calls_completed_per_call_ask": safe_div(c.call_completed, c.call_ask_sent),

        # Give intensity (top-of-funnel)
        "proactive_gives_per_legibility": safe_div(proactive_gives, c.legibility_sent),
    }


def print_counts_block(c: FunnelCounts) -> None:
    for k, v in c.as_dict().items():
        print(f"  {k:26s} {v}")


def print_ratios_block(r: Dict[str, Optional[float]]) -> None:
    print(f"  reply_rate_legibility        {fmt_pct(r['reply_rate_legibility'])}   (reply_received / legibility_sent)")
    print(f"  reply_rate_value_ping        {fmt_pct(r['reply_rate_value_ping'])}   (reply_received / value_ping_sent)")
    print(f"  reply_rate_questions         {fmt_pct(r['reply_rate_questions'])}   (reply_received / question_sent)")
    print(f"  call_yes_rate                {fmt_pct(r['call_yes_rate'])}   (call_agreed / call_ask_sent)")
    print(f"  schedule_rate_from_yes       {fmt_pct(r['schedule_rate_from_yes'])}   (call_scheduled / call_agreed)")
    print(f"  completion_rate              {fmt_pct(r['completion_rate'])}   (call_completed / call_scheduled)")
    print(f"  calls_completed_per_legibility {fmt_pct(r['calls_completed_per_legibility'])}   (call_completed / legibility_sent)")
    print(f"  calls_completed_per_call_ask  {fmt_pct(r['calls_completed_per_call_ask'])}   (call_completed / call_ask_sent)")
    print(f"  proactive_gives_per_legibility {fmt_pct(r['proactive_gives_per_legibility'])}   ((value_ping + public_comment) / legibility_sent)")


def print_report(
    overall: FunnelCounts,
    overall_ratios: Dict[str, Optional[float]],
    by_tier: Dict[str, FunnelCounts],
    since: Optional[date],
    until: Optional[date],
) -> None:
    window = []
    if since:
        window.append(f"since {since.isoformat()}")
    if until:
        window.append(f"until {until.isoformat()}")
    window_txt = f" ({', '.join(window)})" if window else ""

    print(f"\nNetworking Metrics Report{window_txt}\n" + "-" * 40)

    print("\nOverall — Counts")
    print_counts_block(overall)

    print("\nOverall — Ratios")
    print_ratios_block(overall_ratios)

    # Per-tier sections
    for t in ["A", "B", "C", "U"]:
        c = by_tier[t]
        r = compute_ratios(c)
        print(f"\nTier {t} — Counts")
        print_counts_block(c)
        print(f"\nTier {t} — Ratios")
        print_ratios_block(r)

    # Quick interpretation: calls_completed_per_legibility as a stable headline
    kpi = overall_ratios.get("calls_completed_per_legibility")
    if kpi is not None:
        if kpi < 0.05:
            band = "<5% (early or conservative call-asks; check ask volume + tier mix)"
        elif kpi < 0.08:
            band = "5–8% (working; improveable)"
        elif kpi <= 0.12:
            band = "8–12% (target band)"
        else:
            band = ">12% (strong; scale volume)"
        print(f"\nHeadline band (calls_completed_per_legibility): {band}")

    print("")


def validate_tier_value(tier: str) -> str:
    t = (tier or "").strip().upper()
    if t not in {"A", "B", "C"}:
        die("Tier must be A, B, or C.")
    return t


def cmd_add_person(args: argparse.Namespace) -> None:
    people = load_people(args.people)
    pid = args.id.strip()
    if not pid:
        die("Person id cannot be empty.")
    if pid in people and not args.force:
        die(f"Person id '{pid}' already exists. Use --force to overwrite.")

    rec: Dict[str, Any] = {
        "name": args.name,
        "notes": args.notes or "",
        "created_at": utc_now_iso(),
    }
    if args.tier:
        rec["tier"] = validate_tier_value(args.tier)

    people[pid] = rec
    save_people(args.people, people)
    extra = f" tier={rec.get('tier')}" if rec.get("tier") else ""
    print(f"Added person: {pid} ({args.name}){extra}")


def cmd_set_tier(args: argparse.Namespace) -> None:
    people = load_people(args.people)
    pid = args.id.strip()
    if not pid:
        die("Person id cannot be empty.")
    if pid not in people:
        die(f"Unknown person id '{pid}'. Add them first.")

    tier = validate_tier_value(args.tier)
    if not isinstance(people[pid], dict):
        die(f"Person record for '{pid}' is not a JSON object.")

    people[pid]["tier"] = tier
    save_people(args.people, people)
    print(f"Set tier: {pid} -> {tier}")


def cmd_log(args: argparse.Namespace) -> None:
    ev = args.event.strip()
    if ev not in DEFAULT_EVENTS:
        die(f"Unknown event '{ev}'. Allowed: {', '.join(DEFAULT_EVENTS)}")
    pid = args.id.strip()
    if not pid:
        die("Person id cannot be empty.")

    # If people file exists, warn (not fail) if unknown id unless allow-unknown-person
    if os.path.exists(args.people):
        people = load_people(args.people)
        if pid not in people and not args.allow_unknown_person:
            die(f"Unknown person id '{pid}'. Add them first or use --allow-unknown-person.")

    event_obj = {
        "ts": utc_now_iso(),
        "person_id": pid,
        "event": ev,
        "meta": {},
    }
    if args.meta:
        try:
            event_obj["meta"] = json.loads(args.meta)
            if not isinstance(event_obj["meta"], dict):
                die("--meta must be a JSON object, e.g. '{\"q\":\"Q3\"}'")
        except json.JSONDecodeError:
            die("--meta must be valid JSON, e.g. '{\"q\":\"Q3\"}'")

    append_event(args.events, event_obj)
    print(f"Logged: {ev} for {pid}")


def cmd_metrics(args: argparse.Namespace) -> None:
    since = parse_ymd(args.since) if args.since else None
    until = parse_ymd(args.until) if args.until else None
    if since and until and until < since:
        die("--until cannot be earlier than --since.")

    people = load_people(args.people)
    overall = compute_counts(args.events, since, until)
    by_tier = compute_counts_by_tier(args.events, people, since, until)
    ratios = compute_ratios(overall)

    print_report(overall, ratios, by_tier, since, until)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="network_metrics.py", description="Minimal networking metrics logger + reporter.")
    p.add_argument("--people", default="people.json", help="Path to people.json (default: people.json)")
    p.add_argument("--events", default="events.jsonl", help="Path to events.jsonl (default: events.jsonl)")

    sub = p.add_subparsers(dest="cmd", required=True)

    ap = sub.add_parser("add-person", help="Add a person record (minimal).")
    ap.add_argument("--id", required=True, help="Person id (short slug, unique).")
    ap.add_argument("--name", required=True, help="Display name.")
    ap.add_argument("--notes", default="", help="Optional notes.")
    ap.add_argument("--tier", default="", help="Optional tier A/B/C.")
    ap.add_argument("--force", action="store_true", help="Overwrite if id exists.")
    ap.set_defaults(func=cmd_add_person)

    st = sub.add_parser("set-tier", help="Set tier (A/B/C) for an existing person.")
    st.add_argument("--id", required=True, help="Person id.")
    st.add_argument("--tier", required=True, help="Tier A/B/C.")
    st.set_defaults(func=cmd_set_tier)

    lg = sub.add_parser("log", help="Append one event to events.jsonl.")
    lg.add_argument("--id", required=True, help="Person id.")
    lg.add_argument("--event", required=True, help=f"Event type. Allowed: {', '.join(DEFAULT_EVENTS)}")
    lg.add_argument("--meta", default="", help="Optional JSON object meta (e.g. '{\"q\":\"Q3\"}').")
    lg.add_argument("--allow-unknown-person", action="store_true", help="Allow logging for unknown person ids.")
    lg.set_defaults(func=cmd_log)

    mt = sub.add_parser("metrics", help="Show counts and ratios (overall + per-tier).")
    mt.add_argument("--since", default="", help="Start date YYYY-MM-DD (inclusive).")
    mt.add_argument("--until", default="", help="End date YYYY-MM-DD (inclusive).")
    mt.set_defaults(func=cmd_metrics)

    return p


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
