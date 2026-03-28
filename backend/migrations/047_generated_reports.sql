-- Generated Reports: persists morning briefs, EOD reports, weekly summaries
CREATE TABLE IF NOT EXISTS generated_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    report_type VARCHAR(30) NOT NULL,
    report_date DATE NOT NULL,
    report_data JSONB NOT NULL DEFAULT '{}',
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_via VARCHAR(20)
);

CREATE INDEX IF NOT EXISTS idx_generated_reports_account_date
    ON generated_reports(broker_account_id, report_date DESC);
CREATE INDEX IF NOT EXISTS idx_generated_reports_type
    ON generated_reports(broker_account_id, report_type, report_date DESC);

COMMENT ON TABLE generated_reports IS 'Saved copies of all generated reports for the Reports Hub';
COMMENT ON COLUMN generated_reports.report_type IS 'morning_briefing | post_market | weekly_summary';
COMMENT ON COLUMN generated_reports.sent_via IS 'whatsapp | null if not sent';
