"use client";

import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { type ApiInfo, getApiInfo, getHealth } from "@/lib/api";

type ConnectionStatus = "checking" | "connected" | "disconnected";

export default function Home() {
  const [status, setStatus] = useState<ConnectionStatus>("checking");
  const [apiInfo, setApiInfo] = useState<ApiInfo | null>(null);

  useEffect(() => {
    async function checkApi() {
      try {
        const [health, info] = await Promise.all([getHealth(), getApiInfo()]);
        setApiInfo(info);
        setStatus(health.status === "ok" ? "connected" : "disconnected");
      } catch {
        setStatus("disconnected");
      }
    }

    void checkApi();
  }, []);

  const connected = status === "connected";

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-16">
      <div className="w-full max-w-xl">
        <div className="mb-8">
          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.2em] text-indigo-600">
            Relaydesk
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
            Open-source AI-native customer support.
          </h1>
        </div>

        <Card>
          <CardHeader>
            <p className="text-sm font-medium text-slate-500">API Status</p>
            <div className="mt-2 flex items-center gap-2">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  connected
                    ? "bg-emerald-500"
                    : status === "checking"
                      ? "bg-amber-400"
                      : "bg-red-500"
                }`}
              />
              <span className="text-xl font-semibold capitalize text-slate-950">
                {status}
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <div className="border-t border-slate-100 pt-5">
              <p className="text-sm font-medium text-slate-500">Backend</p>
              <div className="mt-1 flex items-baseline justify-between gap-4">
                <span className="font-medium text-slate-900">
                  {apiInfo?.name ?? "Unavailable"}
                </span>
                {apiInfo && (
                  <span className="font-mono text-sm text-slate-500">
                    v{apiInfo.version}
                  </span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
