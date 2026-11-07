const byId = id => document.getElementById(id);
let token = null;

function element(tag, text) {
  const node = document.createElement(tag);
  node.textContent = text;
  return node;
}

async function request(path, body) {
  const session = token;
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      ...(session ? { Authorization: "Bearer " + session } : {}),
      ...(body === undefined ? {} : { "Content-Type": "application/json" })
    },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  const result = response.status === 204 ? null : await response.json();
  if (session !== token) throw new DOMException("Session changed", "AbortError");
  if (!response.ok) {
    throw new Error(typeof result.detail === "string" ? result.detail : "Check the form and try again.");
  }
  return result;
}

function run(button, action) {
  return async event => {
    event.preventDefault();
    byId("notice").textContent = "";
    button.disabled = true;
    try {
      await action();
    } catch (error) {
      if (error.name !== "AbortError") byId("notice").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };
}

function form(id, action) {
  const node = byId(id);
  node.addEventListener("submit", run(node.querySelector("button"), async () => {
    await action(Object.fromEntries(new FormData(node)));
    node.reset();
  }));
}

function showSession(role) {
  byId("login-panel").hidden = Boolean(role);
  byId("logout").hidden = !role;
  for (const name of ["customer", "staff"]) byId(name).hidden = role !== name;
  for (const id of ["answer", "customer-queue", "staff-queue"]) byId(id).replaceChildren();
  for (const id of ["ask", "enquiry", "policy"]) byId(id).reset();
}

async function refresh(role) {
  const staff = role === "staff";
  const records = await request(staff ? "/enquiries/staff" : "/enquiries/mine");
  const queue = byId(role + "-queue");
  queue.replaceChildren();
  if (!records.length) queue.append(element("p", "No enquiries yet."));
  for (const record of records) {
    const card = element("article", "");
    card.append(element("h3", "#" + record.id + " · " + record.subject));
    card.append(element("p", record.status + (staff ? " · " + record.customer_email : "")));
    card.append(element("p", record.message));
    if (record.reply) card.append(element("p", "Support reply: " + record.reply));
    if (staff && record.draft) card.append(element("p", "Draft: " + record.draft));
    if (staff && record.draft_sources?.length) {
      const sources = element("details", "");
      sources.append(element("summary", "Policy evidence"));
      for (const source of record.draft_sources) {
        sources.append(element("p", source.title + " · " + source.text));
      }
      card.append(sources);
    }
    const path = "/enquiries/" + record.id;
    if (staff && record.status === "open") {
      const button = element("button", "Draft reply");
      button.onclick = run(button, async () => {
        await request(path + "/draft", {});
        await refresh(role);
      });
      card.append(button);
    }
    if (staff && record.status === "pending") {
      for (const decision of ["approve", "reject"]) {
        const button = element("button", decision === "approve" ? "Approve reply" : "Reject draft");
        button.onclick = run(button, async () => {
          await request(path + "/decision", { decision });
          await refresh(role);
        });
        card.append(button);
      }
    }
    queue.append(card);
  }
}

form("login", async payload => {
  const result = await request("/auth/login", payload);
  token = result.token;
  byId("login").reset();
  showSession(result.role);
  await refresh(result.role);
});

const logout = byId("logout");
logout.onclick = run(logout, async () => {
  try {
    await request("/auth/logout", {});
  } finally {
    token = null;
    showSession(null);
  }
});

form("ask", async payload => {
  const result = await request("/ask", payload);
  const panel = byId("answer");
  panel.replaceChildren(element("p", result.answer || "I couldn’t find a supported answer. You can open an enquiry below."));
  if (!result.answer) {
    byId("enquiry").elements.message.value = payload.question;
  }
  for (const source of result.citations) {
    const details = element("details", "");
    details.append(element("summary", "[" + source.source_id + "] " + source.title + " · passage " + source.position));
    details.append(element("p", source.text));
    panel.append(details);
  }
});

form("enquiry", async payload => {
  await request("/enquiries", payload);
  await refresh("customer");
});

form("policy", async payload => {
  const document = await request("/documents", payload);
  byId("notice").textContent = "Indexed policy #" + document.id;
});

for (const role of ["customer", "staff"]) {
  const button = byId("refresh-" + role);
  button.onclick = run(button, () => refresh(role));
}
