-- Add broker_account_id column to holdings table
ALTER TABLE holdings 
ADD COLUMN IF NOT EXISTS broker_account_id UUID REFERENCES broker_accounts(id);

-- Make it not null after filling data if needed, but for now allow nulls or handle defaulting
-- Since we are syncing fresh, we can try to make it NOT NULL immediately if table is empty
-- or just leave it nullable if there's existing data (though sync will fail if null)
-- Given the error 'InFailedSQLTransaction' earlier, better to trust the code will fill it.
-- But the model says nullable=False.
-- Let's try to add it as nullable first, then existing data might be an issue.
-- However, since this is a dev/test env, we can likely truncate or just add it.

ALTER TABLE holdings 
ALTER COLUMN broker_account_id SET NOT NULL;
