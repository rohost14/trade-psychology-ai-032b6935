This document lists all identified issues in the current trade architecture, classified by severity, with exact expectations for fixes.
Implement strictly as described. Do not invent alternate behavior.

 HIGH SEVERITY (Must fix before production)
1. Missing behavioral_events persistence layer

Issue
Behavioral detections currently exist implicitly or are computed inline. There is no durable, queryable, explainable record of behavioral signals.

Why this is critical
Without persistence:

No behavior timeline UI

No explainability

No historical learning

No alert deduplication or escalation

No trust in AI output

Required solution
Create a dedicated behavioral_events table.

Minimum schema:

id (UUID, PK)

user_id

broker_account_id

event_type (ENUM / STRING)

severity (LOW / MEDIUM / HIGH)

confidence (FLOAT 0–1)

trigger_trade_id (nullable)

trigger_position_key (instrument + product + direction)

detected_at (TIMESTAMP)

context (JSONB)

delivery_status (PENDING / SENT / ACKED)

acknowledged_at (nullable)

created_at

Constraints:

Events below confidence threshold (e.g. < 0.7) MUST NOT be inserted

Table is append-only (no updates except delivery fields)

2. Behavioral detection is coupled with FIFO / P&L logic

Issue
Some behavioral detection logic is embedded in or implied by FIFO / P&L processing.

Why this is critical
FIFO and reconciliation must remain:

deterministic

idempotent

replayable

Behavior logic inside FIFO causes:

non-repeatable outcomes

corrupted backfills

inconsistent alerts

Required solution
Create a Real-Time Behavioral Evaluator Service.

Behavior evaluator rules:

Runs AFTER a new trade fill is inserted

Input: single new fill

Reads: open_positions, recent trades, recent behavioral_events

Emits: zero or more behavioral_events

Must NOT mutate trades, positions, or P&L

FIFO responsibility ends at:

assigning realized P&L

creating completed_trades

3. No real-time alert delivery mechanism (not sure about this, please take a effective call based on current situation)

Issue
Behavioral signals are not delivered in real time. (I think we have real time but not sure how)

Why this is critical
Polling destroys UX and delays interventions, which defeats the product’s purpose.

Required solution
Add a real-time alert channel:

Preferred (v1):

Server-Sent Events (SSE)

Endpoint example:

/events/behavior

Rules:

Events are pushed ONLY after being persisted

Client reconnect must resume stream safely

No push without DB insert

WebSocket can be added later if bidirectional control is needed.

4. No alert cooldown / escalation state

Issue
Repeated behavioral detections can spam the user.

Why this is critical
Alert fatigue = ignored product = zero value.

Required solution
Add alert state tracking keyed by:

(user_id, event_type)

State fields:

last_alert_time

alert_count

last_severity

Storage:

Redis preferred for fast access

DB optional for audit

Rules:

Enforce minimum cooldown between alerts

Escalate severity only on repeated confirmations

 MEDIUM SEVERITY (Correctness & robustness)
5. Idempotency delete scope is too broad

Issue
Current recomputation deletes completed_trades by:

(broker_account_id + symbol + exchange)

This risks wiping historical trades.

Required solution (choose one)

Delete only trades within the affected fill timestamp range

OR track sync_version / recompute_batch_id

OR delete by derived trade IDs

Hard rule:

Never delete historical data outside the recompute window

6. Direction flip is not explicitly captured

Issue
When a closing fill overshoots and opens a reverse position, this psychological signal is lost.

Required solution
Add field to completed_trades:

closed_by_flip BOOLEAN

Set to true when:

Closing fill both closes a round and opens the opposite direction

This is metadata only, not behavior detection.

7. num_entries / num_exits logic is unreliable

Issue
Counting unique trade_id assumes 1 fill = 1 trade ID.

This is not always true.

Required solution

Count fills directly

Keep trade_id arrays ONLY for audit

Fields:

num_entries = count of entry fills

num_exits = count of exit fills

8. Session P&L definition is ambiguous

Issue
Different services may compute “session P&L” differently.

Required solution
Lock definition globally:

Session = trading day in IST

Reset at market open (e.g. 09:15 IST)

Includes realized P&L only

Unrealized P&L used ONLY for live risk checks

All services must use the same helper.

 LOW SEVERITY (Quality & future safety)
9. Confidence thresholds not enforced centrally

Issue
Low-confidence alerts degrade trust.

Required solution

Enforce global minimum confidence (e.g. 0.7)

Severity must scale with confidence

No alert insertion below threshold

10. Behavioral delivery status not tracked

Issue
No way to know if alerts were sent, seen, or acknowledged.

Required solution
Use fields in behavioral_events:

delivery_status

acknowledged_at

Used for:

retry logic

analytics

alert fatigue tuning

 Hard Constraints (Do Not Violate)

FIFO / P&L must remain deterministic and replayable

Behavior detection must be event-driven, not batch-driven

No behavioral logic inside reconciliation

No silent data loss

No low-confidence alert spam

All real-time alerts must be persisted first

Expected Outcome

After these fixes:

Live behavioral nudges are reliable

Historical behavior is explainable

AI has clean, trustworthy training data

Re-syncs and backfills are safe

UX improves without alert fatigue

Instruction to Claude:
Implement exactly as specified.
If any requirement is unclear, ask before coding.