We are starting a **DATABASE ARCHITECTURE & INTEGRITY AUDIT**.

> ## AUDIT PROGRESS  (auto-updated as work completes)
>
> **Output document:** `docs/database/DATABASE_ARCHITECTURE_AUDIT.md`
> **Resumable state:** `backend/DB_audit/_AUDIT_STATE.md`
> **Evidence (live queries, this pass):** `backend/DB_audit/_evidence/`
>
> | spec section | status |
> |---|---|
> | 1. Table inventory | DONE |
> | 2. PK / UUID integrity | DONE |
> | 3. Foreign keys | DONE |
> | 4. Relational / data-flow map | DONE |
> | 5. DB <-> backend code sync | DONE |
> | 6. DB <-> logic <-> API sync | DONE |
> | 7. Data integrity & consistency | DONE |
> | 8. Constraints & uniqueness | DONE |
> | 9. Index architecture & queries | DONE |
> | 10. Scalability | DONE |
> | 11. Transactions & concurrency | DONE |
> | 12. Security | DONE |
> | 13. Observability | DONE |
> | 14. Migrations & schema history | DONE |
> | 15. Legacy / dead / duplicate | DONE |
> | 16. Missing architecture | DONE |
> | 17. Source-of-truth | DONE |
> | 18. Frontend <-> API <-> DB | DONE |
> | 19. Final classification | DONE |
> | 20. Report structure / assembly | DONE |
>
> **ALL 20 SPECIFICATION SECTIONS COMPLETE — TWO PASSES.** Pass 1 covered all 20.
> A thoroughness review found 6 sections shallower than this spec requires
> (security, transactions, query paths, observability, API/frontend, per-table
> purpose); pass 2 deepened each in place. Report: 2,738 lines, 25 parts.
> Nothing remains pending. Nothing was deleted.
>
> Nothing has been modified in the database, schema, migrations, code, API or
> frontend. This banner and the section markers below are the only edits to this
> file, added at the user's request for progress visibility; the specification
> text itself is unchanged.

---

This is a **read-only audit and documentation exercise only**.

Do NOT modify code, database schema, data, migrations, indexes, constraints, APIs, frontend, backend logic, or configuration. Do NOT create migrations. Do NOT “fix” anything you find. Do NOT clean up or delete anything.

**Important evidence rule:** Do not rely on any existing audit documents, reports, previous findings, project notes, or assumptions as evidence. Verify everything directly against the live Supabase database by querying the actual schema/data and against the current codebase where relevant. The **only historical/reference documents you may use as a secondary source are the migration files**, and even those must be validated against the current live database rather than treated as proof of current state. If there is any conflict between documentation/migrations and the live DB, **the live DB wins**.


Create a **separate comprehensive audit document** containing the findings.

The goal is to understand the entire database as a system: what every table is for, how the tables relate to each other, whether the schema is structurally correct, whether the actual DB matches the application code and product logic, what is obsolete, what is missing, and where there are integrity, security, performance, or maintainability risks.

## 1. Complete table inventory  `[DONE -> report section 2,3]`

First establish the exact current production/dev database schema.

Inventory **every table**. Do not assume there are ~70 tables—get the exact number from the live database.

For every table document:

* table name
* purpose / business meaning
* what part of the product uses it
* whether it is actively used
* whether it is historical/legacy
* whether it is test/research/tooling related
* whether it appears unused
* whether it duplicates another table
* whether it should potentially be retired
* approximate row count
* important date/age characteristics
* whether it is partitioned
* retention behavior
* whether it is expected to grow continuously
* corresponding SQLAlchemy/model representation, if one exists
* corresponding backend services/API usage
* corresponding frontend usage, if applicable

Do not label something unused merely because you cannot find an obvious reference. Verify across the repository and database.

## 2. Primary keys and UUID integrity  `[DONE -> report section 5]`

Audit every table's identity model.

For every table verify:

* primary key exists
* primary key columns
* UUID vs integer vs composite key
* whether UUIDs are generated correctly
* whether UUID generation is consistent with application expectations
* whether PKs are nullable
* composite PK correctness
* whether application models agree with the actual DB PK
* whether any tables lack an appropriate identity
* whether IDs are referenced consistently throughout the system
* whether there are suspicious/manual/hard-coded UUIDs
* whether UUID strategy differs unnecessarily between related tables

Identify any mismatch between:
DB reality ↔ SQLAlchemy models ↔ API/application assumptions.

## 3. Foreign keys and relationship integrity  `[DONE -> report section 6]`

Audit **every foreign key**.

For each relationship establish:

* parent table
* child table
* FK column(s)
* referenced PK/unique key
* ON DELETE behavior
* ON UPDATE behavior where relevant
* whether the relationship makes business sense
* whether the relationship is actually used by application logic
* whether the FK is missing where one appears necessary
* whether an FK exists where it should not
* whether the referenced column is actually unique/appropriate
* whether nullable vs non-nullable behavior is correct
* whether there are potential orphan records
* whether cascading behavior is safe
* whether restrictive behavior could unexpectedly block legitimate operations

Explicitly map the major business relationships.

For example, trace the actual chain where applicable:

User
→ Broker Account
→ Orders / Trades / Positions
→ Completed Trades / Ledger
→ Behavioral Events / Risk Alerts
→ Journal / Insights / Reports

Do not assume this example is correct. Verify the real relationships and explain the actual architecture.

## 4. Full relational/data-flow map  `[DONE -> report section 4]`

Build a conceptual map of the database.

Show:

* core entities
* supporting entities
* transactional entities
* analytical entities
* behavioral entities
* configuration/settings entities
* audit/history entities
* admin/system entities
* research/test/tooling entities

Explain how data is supposed to flow through the system.

For example:

broker activity
→ ingestion
→ orders/trades
→ positions/completed trades
→ behavioral analysis
→ alerts/evidence
→ journal/insights/UI

Again, verify this from the actual repository and schema rather than assuming it.

Identify broken, ambiguous, duplicated, or missing relationships.

## 5. Database ↔ backend code synchronization  `[DONE -> report section 7]`

Audit the DB against the backend codebase.

For every model/table where applicable compare:

* columns
* data types
* nullability
* defaults
* primary keys
* foreign keys
* unique constraints
* indexes
* relationships
* enums
* timestamps
* server-generated values
* JSON/JSONB structures
* numeric precision/scale
* timezone behavior
* partitioning expectations

Identify:

* DB columns missing from models
* model columns missing from DB
* wrong types
* wrong nullability
* stale models
* unused models
* tables with no model
* models pointing at nonexistent tables
* application assumptions that do not match the DB

Do not change anything. Just document the mismatch.

## 6. DB ↔ backend logic ↔ API synchronization  `[DONE -> report section 8]`

Trace important data through:

Database
→ model
→ service
→ repository/query
→ API endpoint
→ frontend consumer

Check whether the same concept has consistent meaning across all layers.

Look specifically for:

* fields written but never read
* fields read but never reliably written
* different names for the same concept
* different meanings for the same field
* duplicated sources of truth
* calculations performed differently in different layers
* API fields that do not correspond cleanly to DB fields
* frontend assumptions that don't match backend behavior
* backend assumptions that don't match actual stored data
* stale/legacy API paths
* tables that appear disconnected from the actual product flow

## 7. Data integrity and consistency  `[DONE -> report section 10]`

Audit actual data, not just schema definitions.

Where practical, check for:

* orphaned records
* duplicate records
* duplicate natural keys
* impossible FK relationships
* NULLs where application logic assumes values exist
* invalid enum/status values
* inconsistent timestamps
* impossible chronological relationships
* contradictory state combinations
* stale records
* records pointing to inactive/deleted parents
* duplicate sources of truth
* unexpected empty tables
* unexpectedly tiny tables
* unexpectedly huge tables
* suspicious concentrations of data
* test/synthetic data mixed with production data

Separate **confirmed data defects** from things that merely deserve investigation.

## 8. Constraints and uniqueness  `[DONE -> report section 11]`

Audit:

* PKs
* FKs
* UNIQUE constraints
* composite UNIQUE constraints
* CHECK constraints
* NOT NULL constraints
* defaults
* exclusion constraints where relevant
* database triggers

Assess whether important business invariants are actually enforced at the DB level or only assumed by application code.

Identify important invariants that currently have no DB protection.

Do not recommend implementation details yet; simply document the gap.

## 9. Index architecture and query performance  `[DONE -> report section 12]`

Audit all indexes across all tables.

For each important index determine:

* why it exists
* which queries use it
* whether it appears redundant
* whether it overlaps another index
* whether it is likely useful
* whether critical query paths lack appropriate indexing
* whether indexes match actual WHERE/JOIN/ORDER BY patterns
* whether composite index column ordering makes sense
* whether partitioning and indexes work together correctly

Inspect important production query paths and determine:

* what tables they touch
* joins
* filters
* sorting
* aggregation
* number of DB round trips
* repeated queries
* potentially unnecessary reads
* potentially unnecessary writes
* obvious N+1 patterns
* queries that could become expensive as user/data volume grows

Where safe and read-only, use actual query plans/EXPLAIN information for important queries.

Do not optimize anything. Report the findings.

## 10. Database scalability  `[DONE -> report section 13]`

Evaluate the current schema for projected growth.

Consider:

* current row counts
* growth rates where observable
* high-write tables
* high-read tables
* large JSON/JSONB fields
* indexes on high-write tables
* partitioning
* partition runway
* retention
* archive behavior
* historical data
* large joins
* aggregation workloads
* concurrency
* transaction sizes
* connection usage
* connection pooling
* Celery/background jobs interacting with DB
* ingestion workloads
* behavioral analysis workloads

Assess likely pressure points at increasing scale.

Do not redesign the architecture. Identify the bottlenecks and risks.

## 11. Transactions and concurrency  `[DONE -> report section 14]`

Audit transaction handling across the application/database boundary.

Look for:

* overly broad transactions
* unnecessary commits
* inappropriate rollbacks
* commits inside reusable services
* nested transaction/savepoint usage
* transaction ownership ambiguity
* long-running transactions
* race conditions
* concurrent writes
* upsert behavior
* idempotency
* duplicate event handling
* deadlock risks
* retry behavior
* partial failure behavior

Pay particular attention to ingestion, order lifecycle, trade lifecycle, behavioral detection, scheduled jobs, and admin/maintenance jobs.

## 12. Security audit  `[DONE -> report section 15]`

Audit database-related security without changing anything.

Review:

* database credentials handling
* connection configuration
* secrets exposure
* environment configuration
* service/database permissions where inspectable
* API access patterns
* user/account ownership enforcement
* tenant isolation
* authorization around queries
* whether user-supplied IDs can access another user's data
* admin/superadmin boundaries
* dangerous raw SQL
* dynamic SQL
* SQL injection exposure
* unsafe database functions
* overly broad data access
* sensitive fields stored in DB
* whether credentials/tokens are persisted
* auditability of destructive operations
* migration safety
* destructive SQL safeguards

Clearly separate confirmed vulnerabilities from hardening opportunities.

Do not perform penetration testing or destructive security testing.

## 13. Observability and operational health  `[DONE -> report section 16]`

Audit whether we can actually understand database health in production.

Review:

* query logging/observability
* slow query visibility
* failed query visibility
* connection pool visibility
* transaction visibility
* migration visibility
* partition health
* table growth
* index health
* failed background jobs
* ingestion failures
* data freshness
* stale data detection
* error propagation
* alerting/monitoring
* ability to detect silent data loss
* ability to detect schema drift

Identify important things that currently happen silently.

## 14. Migrations and schema history  `[DONE -> report section 17]`

Audit the migration system against the current live database.

Verify:

* migration ledger
* applied migrations
* skipped migrations
* pending migrations
* checksum consistency
* current schema vs expected schema
* whether migration history actually explains the current DB
* migrations that appear to have been partially applied
* migrations that were replaced/repaired later
* migrations whose intent no longer matches current architecture
* dangerous historical migrations
* manual schema changes that bypassed migrations
* schema objects existing without a clear migration origin

Do not rerun or modify migrations.

## 15. Legacy / dead / duplicate architecture  `[DONE -> report section 18]`

Find tables and database objects that may no longer have a purpose.

Classify them rather than deleting anything:

* ACTIVE — clearly used and justified
* SUPPORTING — used indirectly / infrastructure
* HISTORICAL — intentionally retained
* RESEARCH — research/validation
* TEST — test-only
* LEGACY — old but still present
* DUPLICATE — overlaps another source of truth
* SUSPECT_UNUSED — no confirmed active consumer
* UNKNOWN — insufficient evidence

For anything potentially removable, provide the evidence and confidence level.

## 16. Missing architecture  `[DONE -> report section 19]`

Also look in the opposite direction.

Identify important concepts that appear to exist in application logic but have no proper DB representation, or where the DB lacks a relationship/table needed for the current product architecture.

Examples could include:

* missing audit/history
* missing relationship
* missing uniqueness protection
* missing lifecycle state
* missing source/provenance
* missing ownership boundary
* missing operational metadata

Do not invent requirements. Only flag something as missing when repository/product behavior provides evidence for it.

## 17. Source-of-truth audit  `[DONE -> report section 20]`

For important concepts determine the actual source of truth.

Examples:

* user identity
* broker account
* orders
* fills/trades
* positions
* completed trades
* P&L
* behavioral events
* risk alerts
* journal
* user rules/settings
* trading capital
* strategy classification
* market/broker data

For each determine:

* authoritative table
* secondary copies
* derived tables
* cached representations
* whether multiple sources can disagree
* how synchronization happens
* whether stale copies can exist

This is particularly important for preventing future data inconsistency.

## 18. Frontend ↔ API ↔ DB audit  `[DONE -> report section 9]`

Trace the major frontend data flows.

Identify:

* frontend screens
* API endpoints they consume
* backend services
* tables queried
* tables written
* fields expected by frontend
* fields actually returned
* stale/dead API endpoints
* UI data that has no clear DB source
* DB data that has no consumer

Focus on architectural consistency, not visual/UI review.

## 19. Final classification  `[DONE -> report sections 21,22]`

Every finding must be classified:

### GOOD

Correct, intentional, and no action currently required.

### GOOD WITH NOTE

Correct but worth documenting/monitoring.

### MODIFY

A concrete schema/application/database architecture issue that should eventually be changed.

### INVESTIGATE

Insufficient evidence; needs a focused follow-up.

### RETIRE

Appears obsolete/duplicated/unused, but requires explicit decision before removal.

### MISSING

Something important appears absent.

### SECURITY

Security-related issue or hardening gap.

### PERFORMANCE

Query/scalability/DB efficiency issue.

### DATA INTEGRITY

Actual or likely data consistency problem.

### CRITICAL

Potential severe correctness, security, or data-loss issue.

Do not inflate severity. Use evidence.

## 20. Audit report structure  `[DONE -> report sections 23,24,25]`

Create a separate document, for example:

`docs/database/DATABASE_ARCHITECTURE_AUDIT.md`

The document should contain:

1. Executive Summary
2. Exact Database Inventory
3. Table-by-Table Catalogue
4. Entity Relationship / Data Flow Map
5. PK / UUID Audit
6. FK / Relationship Audit
7. DB ↔ Model Synchronization
8. DB ↔ Backend/API Synchronization
9. Frontend ↔ API ↔ DB Synchronization
10. Data Integrity Findings
11. Constraints & Invariants
12. Index & Query Audit
13. Scalability Assessment
14. Transaction & Concurrency Audit
15. Security Audit
16. Observability Audit
17. Migration/Schema History Audit
18. Legacy / Duplicate / Unused Objects
19. Missing Architecture
20. Source-of-Truth Map
21. Findings by Severity
22. Findings by Classification
23. Recommended Follow-up Order
24. Explicit “Do Not Change Yet” list
25. Evidence / methodology

For the table catalogue, make it comprehensive enough that we can understand the role of **every table individually**, not just the major ones.

For important findings include:

* exact table/object
* exact column(s) where relevant
* evidence
* impact
* confidence
* classification
* severity
* what should be reviewed next

Do not turn this into a list of speculative improvements.

## Most important requirement

This is an **audit, not an implementation task**.

Do not modify anything while conducting it.

Do not create “quick fixes” to make the audit cleaner.

Do not create migrations.

Do not delete tables.

Do not alter constraints.

Do not add indexes.

Do not change models.

Do not change APIs.

Do not change frontend.

Do not change data.

Use the live database as the source of truth for actual DB state, and the repository as the source of truth for intended application behavior. Compare the two and clearly distinguish:

* what is actually true
* what the code intends
* what the data currently contains
* what is uncertain

At the end, give me a concise summary in the response, but put the **full audit in the separate document**.

Do not start implementing any findings after the audit. The audit should finish with a prioritized review list for a separate future implementation phase.
