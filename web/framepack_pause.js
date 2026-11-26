import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const API_PREFIX = "/framepack-pause";

async function callApi(action) {
    const method = action === "status" ? "GET" : "POST";
    const response = await api.fetchApi(API_PREFIX + "/" + action, { method });
    if (!response.ok) {
        throw new Error("FramePack Pause API returned HTTP " + response.status);
    }
    return response.json();
}

function statusText(state) {
    if (!state.sampler_patched) return "Waiting for Kijai's UniPC sampler hook";
    if (!state.pipeline_patched) return "Sampler found; waiting for Kijai's FramePack pipeline hook";
    if (!state.node_patched) return "Sampler hooked; FramePack node registration not detected yet";
    if (state.phase === "interrupted") return "Generation interrupted" + (state.last_error ? ": " + state.last_error : "");
    if (state.phase === "complete") return "Generation complete";
    if (state.paused) return "Paused at a safe sampler boundary";
    if (state.pause_requested) return "Pause requested — waiting for the current iteration to finish";
    if (state.phase === "preparing") return "Preparing FramePack generation";
    if (state.phase === "denoising") return "Generating video";
    return "Idle — FramePack hooks ready";
}

function progressText(state) {
    if (state.total_sections && state.total_steps) {
        return "Section " + state.section + " / " + state.total_sections +
            " · Step " + state.step + " / " + state.total_steps;
    }
    return "No active FramePack denoising";
}

function toast(kind, title, detail) {
    const manager = app.extensionManager && app.extensionManager.toast;
    if (manager && typeof manager.add === "function") {
        manager.add({ severity: kind, summary: title, detail, life: 3500 });
    }
}

async function runAction(action) {
    try {
        const state = await callApi(action);
        const title = action === "pause" ? "FramePack pause requested" : "FramePack " + action;
        toast("success", title, statusText(state));
        return state;
    } catch (error) {
        console.error("[FramePack Pause]", error);
        toast("error", "FramePack Pause error", error.message || String(error));
        throw error;
    }
}

app.registerExtension({
    name: "Comfy.FramePackPause",
    commands: [
        {
            id: "framepack-pause.pause",
            label: "Pause FramePack sampling",
            function: () => runAction("pause")
        },
        {
            id: "framepack-pause.resume",
            label: "Resume FramePack sampling",
            function: () => runAction("resume")
        },
        {
            id: "framepack-pause.status",
            label: "Refresh FramePack progress",
            function: () => callApi("status").then((state) => {
                toast("info", "FramePack status", statusText(state) + " · " + progressText(state));
                return state;
            })
        }
    ],
    menuCommands: [
        {
            path: ["FramePack Pause"],
            commands: [
                "framepack-pause.pause",
                "framepack-pause.resume",
                "framepack-pause.status"
            ]
        }
    ],
    async setup() {
        // Trigger a backend registry scan as soon as the frontend extension loads.
        // This ensures FramePackSampler.process is wrapped before the user queues it.
        callApi("status").catch((error) => {
            console.warn("[FramePack Pause] Initial status check failed:", error);
        });

        app.extensionManager.registerSidebarTab({
            id: "framepack-pause-controller",
            title: "FramePack Pause",
            tooltip: "Pause, resume and monitor FramePack generation",
            icon: "icon-[lucide--pause]",
            type: "custom",
            render: (container) => {
                container.replaceChildren();
                const root = document.createElement("div");
                root.style.cssText = "display:flex;flex-direction:column;gap:12px;padding:12px;";
                const title = document.createElement("strong");
                title.textContent = "FramePack controller";
                const status = document.createElement("div");
                status.textContent = "Checking FramePack hooks…";
                status.style.cssText = "font-size:13px;line-height:1.5;";
                const progress = document.createElement("progress");
                progress.max = 100;
                progress.value = 0;
                progress.style.cssText = "width:100%;height:12px;";
                const percent = document.createElement("strong");
                percent.textContent = "0%";
                percent.style.cssText = "font-variant-numeric:tabular-nums;";
                const details = document.createElement("div");
                details.textContent = "No active FramePack denoising";
                details.style.cssText = "font-size:12px;opacity:.8;";
                const section = document.createElement("div");
                section.style.cssText = "display:flex;gap:8px;flex-wrap:wrap;";

                function makeButton(label, action) {
                    const button = document.createElement("button");
                    button.textContent = label;
                    button.style.cssText = "padding:8px 12px;border-radius:6px;cursor:pointer;";
                    button.addEventListener("click", async () => {
                        button.disabled = true;
                        try {
                            renderState(await runAction(action));
                        } catch (error) {
                            status.textContent = error.message || String(error);
                        } finally {
                            button.disabled = false;
                        }
                    });
                    return button;
                }

                function renderState(state) {
                    status.textContent = statusText(state);
                    details.textContent = progressText(state);
                    const value = Number(state.progress_percent || 0);
                    progress.value = Math.max(0, Math.min(100, value));
                    percent.textContent = value.toFixed(1) + "% denoising progress";
                    progress.setAttribute("aria-label", percent.textContent);
                }

                const pause = makeButton("Pause", "pause");
                const resume = makeButton("Resume", "resume");
                const refresh = document.createElement("button");
                refresh.textContent = "Refresh";
                refresh.style.cssText = "padding:8px 12px;border-radius:6px;cursor:pointer;";
                refresh.addEventListener("click", async () => {
                    refresh.disabled = true;
                    try {
                        renderState(await callApi("status"));
                    } catch (error) {
                        status.textContent = error.message || String(error);
                    } finally {
                        refresh.disabled = false;
                    }
                });
                section.append(pause, resume, refresh);

                const note = document.createElement("small");
                note.textContent = "Progress covers denoising across all FramePack latent sections. Model loading, preprocessing and VAE decoding are separate phases. Pause takes effect between sampler iterations; model and latent memory stay allocated.";
                note.style.cssText = "opacity:.7;line-height:1.45;";
                root.append(title, status, progress, percent, details, section, note);
                container.append(root);

                let disposed = false;
                const refreshStatus = async () => {
                    try {
                        const state = await callApi("status");
                        if (!disposed) renderState(state);
                    } catch (error) {
                        if (!disposed) status.textContent = error.message || String(error);
                    }
                };
                refreshStatus();
                const timer = window.setInterval(refreshStatus, 1000);
                return () => {
                    disposed = true;
                    window.clearInterval(timer);
                };
            }
        });
    }
});
