-- 079_alert_outcome_planned.sql
--
-- Adds a fourth alert outcome: 'planned'.
--
-- Why this one is worth a migration. The existing three answer "what did you
-- do about it" — stopped, took_anyway, not_useful. None of them lets a trader
-- say the thing they most often mean: *the facts are right, the concern is
-- wrong, this was my plan.*
--
-- That distinction is the whole point. `not_useful` currently conflates two
-- completely different statements:
--
--   "your detection is wrong"   → the engine has a precision problem
--   "I meant to do that"        → the engine is correct and simply not
--                                 telling this trader anything new
--
-- Separating them is what makes the precision proxy in
-- /api/admin/detection-quality mean something. Without it, a detector that
-- fires accurately on a deliberate strategy is indistinguishable from one that
-- fires on nothing.
--
-- It is also the only feedback shape that survives this product's hardest
-- constraint: it costs one tap, and the trader base has given us zero of
-- anything that requires typing.
--
-- 069 added a CHECK constraint listing the three original values, so the enum
-- cannot be widened in application code alone — an INSERT of 'planned' fails at
-- the database until this runs.

ALTER TABLE risk_alerts
    DROP CONSTRAINT IF EXISTS risk_alerts_outcome_chk;

ALTER TABLE risk_alerts
    ADD CONSTRAINT risk_alerts_outcome_chk
    CHECK (outcome IS NULL OR outcome IN ('stopped', 'took_anyway', 'not_useful', 'planned'));

-- Existing rows are untouched: the constraint only widens what is permitted,
-- so nothing already stored can violate it.
