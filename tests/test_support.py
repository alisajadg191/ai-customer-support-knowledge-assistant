from concurrent.futures import ThreadPoolExecutor

from conftest import login
from model import ModelUnavailable

REFUNDS = {"title": "Refunds", "body": "You may request a refund for an unused item within 30 days."}
DELIVERY = {"title": "Delivery", "body": "Standard delivery takes three working days."}


def post(client, path, headers, data=None, expected=200):
    response = client.post(path, headers=headers, json=data)
    assert response.status_code == expected, response.text
    return response.json()


def test_health_and_ui(demo):
    client, _ = demo
    assert client.get("/health").json() == {"status": "ok", "database": "ready"}
    assert "Customer Support Desk" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200


def test_authentication_roles_and_logout(demo):
    client, _ = demo
    post(client, "/ask", {}, {"question": "Refund?"}, 401)
    post(client, "/auth/login", {}, {"email": "staff@example.test", "password": "wrong"}, 401)
    customer = login(client, "customer")
    post(client, "/documents", customer, REFUNDS, 403)
    assert client.get("/enquiries/staff", headers=customer).status_code == 403
    assert client.post("/auth/logout", headers=customer).status_code == 204
    post(client, "/ask", customer, {"question": "Refund?"}, 401)


def test_pgvector_retrieval_citations_and_abstention(demo):
    client, _ = demo
    staff = login(client, "staff")
    customer = login(client, "customer")
    post(client, "/documents", staff, DELIVERY, 201)
    refund = post(client, "/documents", staff, REFUNDS, 201)
    question = {"question": "When can I request a refund?"}
    assert post(client, "/search", customer, question)[0]["document_id"] == refund["id"]
    result = post(client, "/ask", customer, question)
    assert result["status"] == "answered"
    citation, = result["citations"]
    assert citation["document_id"] == refund["id"]
    assert result["answer"] == "[1] " + REFUNDS["body"]
    assert client.get(f"/documents/{refund['id']}", headers=customer).json()["body"] == citation["text"]
    assert post(client, "/ask", customer, {"question": "Do you repair computers?"}) == {
        "status": "insufficient_evidence", "answer": None, "citations": []
    }


def test_approval_releases_reply_only_to_owner(demo):
    client, _ = demo
    customer = login(client, "customer")
    other = login(client, "other")
    staff = login(client, "staff")
    post(client, "/documents", staff, REFUNDS, 201)
    entry = post(client, "/enquiries", customer, {"subject": "Refund", "message": "Can I return my item?"}, 201)
    path = f"/enquiries/{entry['id']}"
    post(client, path + "/decision", staff, {"decision": "approve"}, 409)
    post(client, path + "/draft", other, expected=403)
    draft = post(client, path + "/draft", staff)
    assert draft["status"] == "pending"
    assert draft["draft_sources"][0]["title"] == "Refunds"
    mine, = client.get("/enquiries/mine", headers=customer).json()
    assert mine["reply"] is None and "draft" not in mine
    assert client.get("/enquiries/mine", headers=other).json() == []

    def approve(_):
        return post(client, path + "/decision", staff, {"decision": "approve"})

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.map(approve, range(2))
    assert first == second
    assert first["reviewed_by"] is not None
    post(client, path + "/decision", staff, {"decision": "reject"}, 409)
    mine, = client.get("/enquiries/mine", headers=customer).json()
    assert mine["status"] == "answered"
    assert mine["reply"] == draft["draft"]


def test_rejected_reply_stays_private(demo):
    client, _ = demo
    staff = login(client, "staff")
    customer = login(client, "customer")
    post(client, "/documents", staff, REFUNDS, 201)
    entry = post(client, "/enquiries", customer, {"subject": "Refund", "message": "How do returns work?"}, 201)
    path = f"/enquiries/{entry['id']}"
    post(client, path + "/draft", staff)
    rejected = post(client, path + "/decision", staff, {"decision": "reject"})
    assert rejected["status"] == "rejected"
    post(client, path + "/decision", staff, {"decision": "approve"}, 409)
    mine, = client.get("/enquiries/mine", headers=customer).json()
    assert mine["reply"] is None


def test_model_outage_keeps_enquiry_open(demo, monkeypatch):
    client, model = demo
    staff = login(client, "staff")
    customer = login(client, "customer")
    entry = post(client, "/enquiries", customer, {"subject": "Refund", "message": "Can I return this?"}, 201)

    def unavailable(*args, **kwargs):
        raise ModelUnavailable("offline")

    monkeypatch.setattr(model, "embed", unavailable)
    post(client, "/documents", staff, REFUNDS, 503)
    post(client, f"/enquiries/{entry['id']}/draft", staff, expected=503)
    queued, = client.get("/enquiries/staff", headers=staff).json()
    assert queued["status"] == "open" and queued["draft"] is None
