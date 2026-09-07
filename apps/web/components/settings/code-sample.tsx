"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const samples: Record<string, string> = {
  cURL: `curl -X POST https://api.relaydesk.dev/v1/conversations \\
  -H "Authorization: Bearer rd_your_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{
    "customer_email": "customer@example.com",
    "customer_name": "Priya Raman",
    "subject": "Help with order",
    "message": "I need help with my recent order.",
    "priority": "high",
    "external_id": "ticket-123",
    "metadata": { "order_id": "ord_456", "plan": "growth" }
  }'`,
  Python: `import httpx

httpx.post(
    "https://api.relaydesk.dev/v1/conversations",
    headers={"Authorization": "Bearer rd_your_key_here"},
    json={
        "customer_email": "customer@example.com",
        "customer_name": "Priya Raman",
        "subject": "Help with order",
        "message": "I need help with my recent order.",
        "priority": "high",
        "external_id": "ticket-123",
        "metadata": {"order_id": "ord_456", "plan": "growth"},
    },
)`,
  "Node.js": `await fetch("https://api.relaydesk.dev/v1/conversations", {
  method: "POST",
  headers: {
    Authorization: "Bearer rd_your_key_here",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    customer_email: "customer@example.com",
    customer_name: "Priya Raman",
    subject: "Help with order",
    message: "I need help with my recent order.",
    priority: "high",
    external_id: "ticket-123",
    metadata: { order_id: "ord_456", plan: "growth" },
  }),
});`,
  Ruby: `require "net/http"
require "json"

uri = URI("https://api.relaydesk.dev/v1/conversations")
Net::HTTP.post(
  uri,
  {
    customer_email: "customer@example.com",
    customer_name: "Priya Raman",
    subject: "Help with order",
    message: "I need help with my recent order.",
    priority: "high",
    external_id: "ticket-123",
    metadata: { order_id: "ord_456", plan: "growth" }
  }.to_json,
  "Authorization" => "Bearer rd_your_key_here",
  "Content-Type" => "application/json"
)`,
};

export function CodeSample() {
  const [language, setLanguage] = useState("cURL");
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(samples[language]);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked; the sample is selectable either way.
    }
  }

  return (
    <Tabs value={language} onValueChange={setLanguage}>
      <div className="mb-2 flex items-center justify-between">
        <TabsList>
          {Object.keys(samples).map((key) => (
            <TabsTrigger key={key} value={key}>
              {key}
            </TabsTrigger>
          ))}
        </TabsList>
        <button
          type="button"
          onClick={copy}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[12px] text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      {Object.entries(samples).map(([key, code]) => (
        <TabsContent key={key} value={key}>
          <pre className="overflow-x-auto rounded-md border border-ink-200 bg-ink-950 p-4 font-mono text-[12px] leading-relaxed text-ink-100">
            <code>{code}</code>
          </pre>
        </TabsContent>
      ))}
    </Tabs>
  );
}
