# AI Customer Support & Knowledge Assistant

A local support desk where customers can ask policy questions, see the source passages, and open enquiries. Staff can index policies, draft replies using the knowledge base, and approve a reply before the customer sees it.

## Run the demo for free

On a Mac with Docker Desktop and Ollama running, use:

```bash
git clone https://github.com/alisajadg191/ai-customer-support-knowledge-assistant.git
cd ai-customer-support-knowledge-assistant
ollama pull nomic-embed-text
ollama pull qwen3:8b
docker compose up --build -d --wait
docker compose exec app python -m seed
```

Choose a distinct demo password for each account when prompted. Existing accounts are skipped. Open [the support desk](http://127.0.0.1:8000/) or [the API documentation](http://127.0.0.1:8000/docs).

The database and web ports are bound to the Mac's loopback interface. The app container uses Docker Desktop's host address to reach Ollama. If Ollama is unreachable from the container, run the Python app directly on the Mac and keep only Postgres in Docker:

```bash
docker compose stop app
docker compose up -d --wait db
export DATABASE_URL=postgresql://support:support-local@127.0.0.1:55432/support
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m seed
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --no-access-log
```

## Walkthrough

1. Sign in as `staff@example.test`. Index a document titled **Refunds** with the text: “You may request a refund for an unused item within 30 days.”
2. Sign in as `customer@example.test` and ask “When can I request a refund for an unused item?” Expand the source to see the passage. An unrelated question should offer the option to open an enquiry.
3. Create an enquiry with subject **Refund** and message “Can I return my unused item?” Note that it appears in **My enquiries** as open.
4. Return to the staff account. Select **Draft reply**, inspect the policy evidence, and choose **Approve reply**. The staff queue records the reviewer and review time.
5. Return to the customer account and refresh **My enquiries** to see the approved reply. The other demo customer, `other@example.test`, has a separate enquiry list.

## Architecture

- **FastAPI and browser UI.** Pydantic validates requests. Passwords are salted and hashed with scrypt. Expiring bearer sessions are stored as token hashes and revoked at sign-out. Server-side role and owner checks protect staff operations and customer records.
- **PostgreSQL and pgvector.** Document passages and embeddings are saved together in one transaction. Postgres ranks compatible vectors by cosine distance. The current demo uses exact search over a shared policy corpus.
- **Ollama RAG.** Nomic embeds passages and questions. Qwen selects evidence and the server quotes verified passage IDs. Staff drafts can contain generated text and require human review before release. Replies appear in the app.
- **Approval.** The review route locks the enquiry row before checking its status. A repeat decision returns the previous result. Conflicting decisions return HTTP 409.
- **Operations.** `/health` checks database connectivity. Structured request logs record route, status, and duration. Use `docker compose logs app` to inspect them. Ollama failures return HTTP 503 without publishing a draft.

The demo is designed for a single fictional business, synthetic data, and local use. The setup has no paid dependencies. Azure deployment is optional and has no infrastructure provisioned by this repo. Azure Container Apps' free grant has usage limits and charges can apply beyond them.

## Verification

CI runs API tests against real PostgreSQL and pgvector with deterministic model responses, then builds the Docker image and checks the running Compose app. The suite verifies citation provenance, abstention, session revocation, staff access, customer isolation, concurrent approval, rejection and model outages.

To reproduce the database checks locally after starting the database and installing dependencies:

```bash
TEST_DATABASE_URL=postgresql://support:support-local@127.0.0.1:55432/support \
  .venv/bin/python -m pytest -q
```

Each test creates and drops an isolated schema. Use the local demo database or a disposable database with permission to create schemas and enable pgvector.

`DATABASE_URL` is required at app startup. Use `OLLAMA_URL`, `OLLAMA_CHAT_MODEL`, and `OLLAMA_EMBED_MODEL` for model configuration. Switching embedding models requires indexing policies again for the new model. Stop the demo with `docker compose down`; its database volume remains available for the next run.
