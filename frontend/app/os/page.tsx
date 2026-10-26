"use client";

/**
 * MuseBreak Business OS — WebLLM inference console.
 * Small tier = real in-browser WebLLM (WebGPU). Medium/Large need an API URL
 * or show UNAVAILABLE. Jev is a real human approval gate. zkVM strip polls the
 * hash-commitment heartbeat (NOT zero-knowledge).
 *
 * Live WebGPU inference is not executed in CI/build — needs a real browser GPU.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Shell from "@/components/Shell";
import ModelTiers from "@/components/os/ModelTiers";
import AgentBoard from "@/components/os/AgentBoard";
import JevGate from "@/components/os/JevGate";
import ZkvmStrip from "@/components/os/ZkvmStrip";
import { MODEL_TIERS, readApiUrl, writeApiUrl, type TierSize } from "@/lib/os/models";
import { routeLocal } from "@/lib/os/router";
import {
  chat,
  detectWebGPU,
  loadEngine,
  type LoadProgress,
} from "@/lib/os/webllm";
import {
  callOpenAiCompat,
  commitZkvmNow,
  completeOsTask,
  createOsTask,
  fetchZkvmStatus,
  jevApprove,
  listOsTasks,
} from "@/lib/os/api";
import { probeGateway } from "@/lib/api";
import "./os.css";

type Task = {
  id: string;
  prompt: string;
  status: string;
  route: any;
  jev?: any;
  result?: any;
};

export default function BusinessOsPage() {
  const [prompt, setPrompt] = useState("Say hello in one short sentence.");
  const [forceSize, setForceSize] = useState<TierSize | null>(null);
  const [webgpuOk, setWebgpuOk] = useState<boolean | null>(null);
  const [webgpuReason, setWebgpuReason] = useState("");
  const [modelLoaded, setModelLoaded] = useState(false);
  const [loadProg, setLoadProg] = useState<LoadProgress | null>(null);
  const [output, setOutput] = useState("");
  const [statusLine, setStatusLine] = useState("Idle");
  const [logs, setLogs] = useState<string[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [gatewayOk, setGatewayOk] = useState(false);
  const [zkvm, setZkvm] = useState<any>(null);
  const [jevOpen, setJevOpen] = useState(false);
  const [pendingTask, setPendingTask] = useState<Task | null>(null);
  const [busy, setBusy] = useState(false);
  const [mediumUrl, setMediumUrl] = useState("");
  const [largeUrl, setLargeUrl] = useState("");
  const [claws, setClaws] = useState<Record<string, boolean>>({
    "recon:read": true,
    "review:read": true,
    "review:review": true,
    "claw-worker:read": true,
    "code:code_write": false,
    "orchestrator:plan": true,
    "orchestrator:assign": true,
    "reporter:report": false,
  });

  const log = useCallback((msg: string) => {
    const t = new Date().toLocaleTimeString("en-IN", { hour12: false, timeZone: "Asia/Calcutta" });
    setLogs((prev) => [`[${t} IST] ${msg}`, ...prev].slice(0, 80));
  }, []);

  const mediumConfigured = !!mediumUrl.trim();
  const largeConfigured = !!largeUrl.trim();

  const preview = useMemo(
    () =>
      routeLocal(prompt, {
        forceSize,
        mediumApiConfigured: mediumConfigured,
        largeApiConfigured: largeConfigured,
      }),
    [prompt, forceSize, mediumConfigured, largeConfigured],
  );

  useEffect(() => {
    setMediumUrl(readApiUrl("medium"));
    setLargeUrl(readApiUrl("large"));
    detectWebGPU().then((s) => {
      setWebgpuOk(s.ok);
      if (!s.ok) setWebgpuReason(s.reason);
      log(s.ok ? "WebGPU available" : `WebGPU unavailable: ${"reason" in s ? s.reason : ""}`);
    });
    probeGateway().then((ok) => {
      setGatewayOk(ok);
      log(ok ? "Gateway reachable" : "Gateway offline — task API disabled, local preview only");
    });
  }, [log]);

  const refreshTasks = useCallback(async () => {
    if (!(await probeGateway())) {
      setGatewayOk(false);
      return;
    }
    setGatewayOk(true);
    try {
      const j = await listOsTasks();
      setTasks(j.tasks || []);
      const z = await fetchZkvmStatus();
      setZkvm(z);
    } catch (e: any) {
      log(`poll error: ${e.message || e}`);
    }
  }, [log]);

  useEffect(() => {
    refreshTasks();
    const id = setInterval(refreshTasks, 5000);
    return () => clearInterval(id);
  }, [refreshTasks]);

  async function ensureSmallModel() {
    const modelId = MODEL_TIERS.small.webllmModelId!;
    if (modelLoaded) return modelId;
    setStatusLine("Loading WebLLM model…");
    log(`Loading ${modelId} (first load downloads weights)`);
    await loadEngine(modelId, (p) => setLoadProg(p));
    setModelLoaded(true);
    setLoadProg(null);
    log(`Model ready: ${modelId}`);
    return modelId;
  }

  async function runInferenceOnTask(task: Task) {
    const size = (task.route?.size || "small") as TierSize;
    const tier = MODEL_TIERS[size];
    setBusy(true);
    setOutput("");
    try {
      if (size === "small") {
        if (!webgpuOk) throw new Error(webgpuReason || "WebGPU unavailable");
        const modelId = await ensureSmallModel();
        setStatusLine("Streaming WebLLM…");
        const result = await chat(modelId, task.prompt, (partial) => setOutput(partial));
        setOutput(result.text);
        setStatusLine("Done (WebLLM · real local)");
        log(`WebLLM completed task ${task.id}`);
        if (gatewayOk) {
          await completeOsTask(task.id, {
            text: result.text,
            source: "webllm",
            model_id: result.modelId,
            simulated: false,
          });
          await refreshTasks();
        }
      } else {
        const url = size === "medium" ? mediumUrl : largeUrl;
        if (!url) throw new Error(`${tier.museLabel} UNAVAILABLE — set API URL`);
        setStatusLine(`Calling ${tier.museLabel} API…`);
        const modelHint =
          size === "medium" ? "codellama:13b-instruct" : "llama3.3:70b";
        const result = await callOpenAiCompat(url, task.prompt, modelHint);
        setOutput(result.text);
        setStatusLine(`Done (${tier.museLabel} · API)`);
        log(`API completed task ${task.id} via ${result.model}`);
        if (gatewayOk) {
          await completeOsTask(task.id, {
            text: result.text,
            source: "api",
            model_id: result.model,
            simulated: false,
          });
          await refreshTasks();
        }
      }
    } catch (e: any) {
      const msg = e?.message || String(e);
      setStatusLine(`Error: ${msg}`);
      setOutput((prev) => prev || `Error: ${msg}`);
      log(`error: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit() {
    if (!prompt.trim()) return;
    setBusy(true);
    try {
      if (!gatewayOk) {
        // Local-only path for small tier
        const local = routeLocal(prompt, {
          forceSize,
          mediumApiConfigured: mediumConfigured,
          largeApiConfigured: largeConfigured,
        });
        if (local.status === "unavailable") {
          setStatusLine(`${local.museLabel} UNAVAILABLE`);
          setOutput(
            `${local.museLabel} is UNAVAILABLE.\nOpen equivalent: ${local.openEquivalent}\nConfigure the API URL below, or pick the small (WebLLM) tier.`,
          );
          return;
        }
        if (local.requiresJev) {
          setPendingTask({
            id: "local_" + Date.now().toString(16),
            prompt,
            status: "awaiting_jev",
            route: {
              size: local.size,
              muse_label: local.museLabel,
              agent: local.agent,
              open_equivalent: local.openEquivalent,
              note: "local preview — gateway offline",
            },
          });
          setJevOpen(true);
          return;
        }
        await runInferenceOnTask({
          id: "local_small",
          prompt,
          status: "ready",
          route: { size: "small", muse_label: local.museLabel, webllm_model_id: local.webllmModelId },
        });
        return;
      }

      const task = await createOsTask({
        prompt,
        force_size: forceSize,
        medium_api_configured: mediumConfigured,
        large_api_configured: largeConfigured,
      });
      log(`task ${task.id} → ${task.route.muse_label} (${task.status})`);
      setTasks((prev) => [task, ...prev]);
      if (task.status === "unavailable") {
        setStatusLine(`${task.route.muse_label} UNAVAILABLE`);
        setOutput(
          `${task.route.muse_label} is UNAVAILABLE.\nOpen equivalent: ${task.route.open_equivalent}\n${task.route.note}`,
        );
        return;
      }
      if (task.status === "awaiting_jev") {
        setPendingTask(task);
        setJevOpen(true);
        setStatusLine("Waiting for Jev approval");
        return;
      }
      await runInferenceOnTask(task);
    } catch (e: any) {
      setStatusLine(`Error: ${e.message || e}`);
      log(`submit error: ${e.message || e}`);
    } finally {
      setBusy(false);
    }
  }

  async function onJevApprove(approver: string) {
    if (!pendingTask) return;
    setBusy(true);
    try {
      let task = pendingTask;
      if (gatewayOk && !task.id.startsWith("local_")) {
        task = await jevApprove(task.id, approver);
        log(`Jev approved ${task.id} by ${approver}`);
        await refreshTasks();
      } else {
        task = {
          ...task,
          status: "ready",
          jev: { approved: true, approver, required: true },
        };
        log(`Jev approved local task by ${approver} (gateway offline)`);
      }
      setJevOpen(false);
      setPendingTask(null);
      if (task.status === "unavailable") {
        setStatusLine("Still UNAVAILABLE after Jev");
        return;
      }
      await runInferenceOnTask(task);
    } catch (e: any) {
      log(`Jev error: ${e.message || e}`);
      setStatusLine(`Jev error: ${e.message || e}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell mode={gatewayOk ? "live" : "simulator"} crumb="MUSEBREAK / BUSINESS OS / WEBLLM">
      <div className="os-page">
        <div className="os-banner">
          <strong>Honesty:</strong> Small tier runs <em>real</em> in-browser WebLLM (WebGPU).
          Medium (Muse Code) and Large (Muse Wonder Full) need an OpenAI-compatible API URL —
          otherwise they show <em>UNAVAILABLE</em>, never a fake completion. The zkVM strip is a{" "}
          <em>hash-commitment MVP</em>, not zero-knowledge. No fabricated GPU clusters, params, or
          latency numbers.
        </div>

        <div className="os-header">
          <div>
            <h1>Business OS</h1>
            <p>
              Open routing · agent swarm · Jev gate · WebLLM inference · responsive web/mobile
            </p>
          </div>
          <div className="os-row">
            <span className={`os-pill ${webgpuOk ? "ok" : "warn"}`}>
              WebGPU {webgpuOk === null ? "…" : webgpuOk ? "ok" : "no"}
            </span>
            <span className={`os-pill ${gatewayOk ? "ok" : "warn"}`}>
              gateway {gatewayOk ? "live" : "offline"}
            </span>
            <span className="os-pill dim">USE_OPEN_SOURCE_ONLY</span>
          </div>
        </div>

        <ZkvmStrip
          status={zkvm}
          online={gatewayOk}
          onCommit={async () => {
            try {
              const s = await commitZkvmNow();
              setZkvm(s);
              log("zkVM heartbeat commit");
            } catch (e: any) {
              log(`zkvm commit failed: ${e.message || e}`);
            }
          }}
        />

        <ModelTiers
          selected={forceSize}
          mediumConfigured={mediumConfigured}
          largeConfigured={largeConfigured}
          webgpuOk={webgpuOk}
          onSelect={setForceSize}
        />

        <div className="os-grid">
          <div className="os-card">
            <h2>Task</h2>
            <textarea
              className="os-prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe a task — small free WebLLM, or larger with API + Jev"
            />
            <div className="os-row">
              <span className="os-pill dim">preview → {preview.museLabel}</span>
              <span className="os-pill dim">agent {preview.agent.name}</span>
              <span className={`os-pill ${preview.status === "ready" ? "ok" : "warn"}`}>
                {preview.status}
              </span>
              {preview.requiresJev ? <span className="os-pill warn">needs Jev</span> : null}
            </div>
            <div className="os-muted">≡ {preview.openEquivalent}</div>
            {webgpuOk === false ? <div className="os-note">{webgpuReason}</div> : null}
            {loadProg ? (
              <div>
                <div className="os-muted">{loadProg.text}</div>
                <div className="os-progress">
                  <i style={{ width: `${Math.round((loadProg.progress || 0) * 100)}%` }} />
                </div>
              </div>
            ) : null}
            <div className="os-row">
              <button type="button" className="os-btn primary" disabled={busy} onClick={onSubmit}>
                {busy ? "Working…" : "Sort & run"}
              </button>
              <button
                type="button"
                className="os-btn ghost"
                disabled={busy || !webgpuOk}
                onClick={async () => {
                  try {
                    await ensureSmallModel();
                    setStatusLine("WebLLM model loaded");
                  } catch (e: any) {
                    setStatusLine(e.message || String(e));
                  }
                }}
              >
                Preload Spark (1B)
              </button>
              <span className="os-muted">{statusLine}</span>
            </div>
            <div className="os-out">{output || "Output streams here."}</div>
          </div>

          <div className="os-card">
            <h2>API endpoints (medium / large)</h2>
            <div className="os-note">
              OpenAI-compatible base URL (we append <code>/v1/chat/completions</code>). Stored in
              localStorage only. Leave blank → tier stays UNAVAILABLE.
            </div>
            <div className="os-settings">
              <label className="os-field">
                Muse Code (medium)
                <input
                  value={mediumUrl}
                  placeholder="http://localhost:8321"
                  onChange={(e) => {
                    setMediumUrl(e.target.value);
                    writeApiUrl("medium", e.target.value);
                  }}
                />
              </label>
              <label className="os-field">
                Muse Wonder Full (large)
                <input
                  value={largeUrl}
                  placeholder="http://localhost:8321"
                  onChange={(e) => {
                    setLargeUrl(e.target.value);
                    writeApiUrl("large", e.target.value);
                  }}
                />
              </label>
            </div>
            <h2 style={{ marginTop: 8 }}>Activity</h2>
            <div className="os-log">
              {logs.length === 0 ? <div className="os-muted">no events yet</div> : null}
              {logs.map((l, i) => (
                <div key={i}>{l}</div>
              ))}
            </div>
          </div>
        </div>

        <div className="os-card">
          <h2>Agent swarm · Claw grants</h2>
          <div className="os-note">
            Tasks are sorted by size and assigned to agents. Claw checkboxes are capability grants
            (UI policy). Agents whose model tier is UNAVAILABLE stay pending — they do not invent
            answers. code_write / action claws still require Jev before any API call.
          </div>
          <AgentBoard
            tasks={tasks}
            claws={claws}
            onToggleClaw={(id, on) => setClaws((c) => ({ ...c, [id]: on }))}
          />
        </div>
      </div>

      <JevGate
        open={jevOpen}
        taskId={pendingTask?.id || ""}
        size={pendingTask?.route?.size || ""}
        museLabel={pendingTask?.route?.muse_label || pendingTask?.route?.museLabel || ""}
        reason={pendingTask?.route?.note || "Large/medium or action-like tasks require Jev."}
        busy={busy}
        onCancel={() => {
          setJevOpen(false);
          setPendingTask(null);
          setStatusLine("Denied by operator");
          log("Jev denied");
        }}
        onApprove={onJevApprove}
      />
    </Shell>
  );
}
