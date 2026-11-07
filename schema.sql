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
