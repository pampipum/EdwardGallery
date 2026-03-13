#!/usr/bin/env node

import fs from "node:fs/promises";
import process from "node:process";
import { AgentMailClient } from "agentmail";

const to = process.argv[2];
const subject = process.argv[3] || "Zurich AI presentation critique";

if (!to) {
  console.error("Usage: node scripts/send-presentation-critique-email.mjs <to> [subject]");
  process.exit(1);
}

const apiKey = process.env.AGENTMAIL_API_KEY;

if (!apiKey) {
  console.error("Missing AGENTMAIL_API_KEY");
  process.exit(1);
}

const client = new AgentMailClient({ apiKey });
const critiquePath = new URL("../docs/presentations/zurich-ai-presentation-review.md", import.meta.url);
const critique = await fs.readFile(critiquePath, "utf8");

const inboxId = await ensureInbox(client);
const text = [
  "Hi,",
  "",
  "Here is the complete critique of the Zurich AI presentation:",
  "",
  critique,
  "",
  "Sent from the Swiss AI Audit workspace."
].join("\n");

const html = [
  "<p>Hi,</p>",
  "<p>Here is the complete critique of the Zurich AI presentation:</p>",
  `<pre style="font-family: Georgia, serif; white-space: pre-wrap; line-height: 1.6;">${escapeHtml(critique)}</pre>`,
  "<p>Sent from the Swiss AI Audit workspace.</p>"
].join("");

const sendResponse = await client.inboxes.messages.send(inboxId, {
  to,
  subject,
  text,
  html,
  labels: ["project-update", "presentation-review"]
});

const result = sendResponse.data ?? sendResponse;
console.log(JSON.stringify({ inboxId, messageId: result.id ?? result.messageId ?? null }, null, 2));

async function ensureInbox(client) {
  const preferred = process.env.MAIL_FROM || "albi@agentmail.to";

  try {
    const [username, domain] = preferred.split("@");
    const created = await client.inboxes.create({ username, domain });
    const inbox = created.data ?? created;
    return inbox.inboxId || inbox.id || preferred;
  } catch {
    try {
      const listed = await client.inboxes.list();
      const inboxes = listed.data?.inboxes ?? listed.inboxes ?? [];
      const matched = inboxes.find((item) => item.inboxId === preferred || item.id === preferred);
      if (matched) {
        return matched.inboxId || matched.id;
      }
    } catch {
      // fall through
    }

    const created = await client.inboxes.create();
    const inbox = created.data ?? created;
    return inbox.inboxId || inbox.id;
  }
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
