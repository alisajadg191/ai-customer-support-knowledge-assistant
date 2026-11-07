CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title text NOT NULL,
    body text NOT NULL
);

CREATE TABLE IF NOT EXISTS passages (
    document_id bigint NOT NULL REFERENCES documents ON DELETE CASCADE,
    position integer NOT NULL,
    body text NOT NULL,
    model text NOT NULL,
    embedding vector NOT NULL,
    PRIMARY KEY (document_id, position)
);

CREATE TABLE IF NOT EXISTS accounts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text UNIQUE NOT NULL,
    password_hash text NOT NULL,
    role text NOT NULL CHECK (role IN ('customer', 'staff'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash text PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES accounts ON DELETE CASCADE,
    expires_at timestamptz NOT NULL
);
