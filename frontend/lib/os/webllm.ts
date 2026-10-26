/**
 * In-browser WebLLM helper (WebGPU).
 * Dynamic-imports @mlc-ai/web-llm so SSR never loads it.
 * Live inference was not executed on the build box (no WebGPU headless).
 */

export type WebGpuStatus =
  | { ok: true }
  | { ok: false; reason: string };

export type LoadProgress = { progress: number; text: string };

export type ChatResult = {
  text: string;
  modelId: string;
  source: "webllm";
  simulated: false;
};

let enginePromise: Promise<any> | null = null;
let loadedModelId: string | null = null;

export async function detectWebGPU(): Promise<WebGpuStatus> {
  if (typeof navigator === "undefined") {
    return { ok: false, reason: "Not in a browser." };
  }
  const nav = navigator as Navigator & { gpu?: { requestAdapter: () => Promise<unknown> } };
  if (!nav.gpu) {
    return {
      ok: false,
      reason: "WebGPU is not available in this browser. Use Chrome/Edge 113+ on a GPU-capable device, or enable chrome://flags/#enable-unsafe-webgpu.",
    };
  }
  try {
    const adapter = await nav.gpu.requestAdapter();
    if (!adapter) {
      return { ok: false, reason: "WebGPU adapter request returned null (GPU blocked or unavailable)." };
    }
    return { ok: true };
  } catch (e: any) {
    return { ok: false, reason: `WebGPU adapter error: ${e?.message || e}` };
  }
}

export async function loadEngine(
  modelId: string,
  onProgress?: (p: LoadProgress) => void,
): Promise<{ modelId: string }> {
  const gpu = await detectWebGPU();
  if (!gpu.ok) throw new Error(gpu.reason);

  if (enginePromise && loadedModelId === modelId) {
    await enginePromise;
    return { modelId };
  }

  enginePromise = (async () => {
    const webllm = await import("@mlc-ai/web-llm");
    const engine = await webllm.CreateMLCEngine(modelId, {
      initProgressCallback: (report: { progress: number; text: string }) => {
        onProgress?.({ progress: report.progress, text: report.text });
      },
    });
    loadedModelId = modelId;
    return engine;
  })();

  try {
    await enginePromise;
    return { modelId };
  } catch (e) {
    enginePromise = null;
    loadedModelId = null;
    throw e;
  }
}

export async function chat(
  modelId: string,
  prompt: string,
  onToken?: (partial: string) => void,
): Promise<ChatResult> {
  if (!enginePromise || loadedModelId !== modelId) {
    await loadEngine(modelId);
  }
  const engine = await enginePromise!;
  const messages = [
    {
      role: "system",
      content:
        "You are MuseBreak Muse Spark (open: Llama-3.2-1B via WebLLM). Be concise and honest. You run locally in the user's browser.",
    },
    { role: "user", content: prompt },
  ];

  // Prefer streaming when available
  let text = "";
  try {
    const chunks = await engine.chat.completions.create({
      messages,
      stream: true,
      temperature: 0.7,
      max_tokens: 512,
    });
    for await (const chunk of chunks) {
      const delta = chunk?.choices?.[0]?.delta?.content || "";
      if (delta) {
        text += delta;
        onToken?.(text);
      }
    }
  } catch {
    const out = await engine.chat.completions.create({
      messages,
      stream: false,
      temperature: 0.7,
      max_tokens: 512,
    });
    text = out?.choices?.[0]?.message?.content || "";
    onToken?.(text);
  }

  return { text, modelId, source: "webllm", simulated: false };
}

export function resetEngine() {
  enginePromise = null;
  loadedModelId = null;
}
