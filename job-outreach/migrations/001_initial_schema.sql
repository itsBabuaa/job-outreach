-- Job Digest Mailer: Initial Schema

CREATE TABLE subscribers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text UNIQUE NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    skill_set text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE job_listings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    url text UNIQUE NOT NULL,
    title text NOT NULL,
    company text NOT NULL,
    tags text[] NOT NULL DEFAULT '{}',
    date_posted date,
    source text NOT NULL,
    salary text NOT NULL DEFAULT '',
    requirements text NOT NULL DEFAULT '',
    summary text NOT NULL DEFAULT '',
    scraped_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sent_digests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id uuid NOT NULL REFERENCES subscribers(id) ON DELETE CASCADE,
    date_sent date NOT NULL,
    job_count int NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sent_digest_jobs (
    digest_id uuid NOT NULL REFERENCES sent_digests(id) ON DELETE CASCADE,
    job_id uuid NOT NULL REFERENCES job_listings(id) ON DELETE CASCADE,
    PRIMARY KEY (digest_id, job_id)
);

-- Indexes
CREATE INDEX idx_job_listings_tags ON job_listings USING GIN (tags);
CREATE INDEX idx_sent_digests_subscriber_date ON sent_digests (subscriber_id, date_sent);
