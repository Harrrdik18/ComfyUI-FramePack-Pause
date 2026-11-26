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
    if (!state.patched) return "Waiting for Kijai FramePack sampler to load";
    if (state.active && state.paused) {
        return "Paused at sampler step " + state.step +
            (state.total_steps ? " / " + state.total_steps : "");
    }
    if (state.active) {
        return "Sampling: step " + state.step +
            (state.total_steps ? " / " + state.total_steps : "");
    }
    return state.paused ? "Pause armed for next FramePack run" : "Idle — sampler hook ready";
}

function toast(kind, title, detail) {
    const manager = app.extensionManager && app.extensionManager.toast;
    if (!manager || typeof manager.add !== "function") return;
    manager.add({ severity: kind, summary: title, detail, life: 3500 });
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
            label: "Refresh FramePack pause status",
            function: () => callApi("status").then((state) => {
                toast("info", "FramePack Pause", statusText(state));
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
        app.extensionManager.registerSidebarTab({
            id: "framepack-pause-controller",
            title: "FramePack Pause",
            tooltip: "Pause and resume FramePack sampling",
            icon: "pi pi-pause",
            type: "custom",
            render: (container) => {
                container.replaceChildren();
                const root = document.createElement("div");
                root.style.cssText = "display:flex;flex-direction:column;gap:12px;padding:12px;";
                const status = document.createElement("div");
                status.textContent = "Checking sampler…";
                status.style.cssText = "font-size:13px;line-height:1.5;";
                const row = document.createElement("div");
                row.style.cssText = "display:flex;gap:8px;flex-wrap:wrap;";

                function makeButton(label, action) {
                    const button = document.createElement("button");
                    button.textContent = label;
                    button.style.cssText = "padding:8px 12px;border-radius:6px;cursor:pointer;";
                    button.addEventListener("click", async () => {
                        button.disabled = true;
                        try {
                            const state = await runAction(action);
                            status.textContent = statusText(state);
                        } catch (error) {
                            status.textContent = error.message || String(error);
                        } finally {
                            button.disabled = false;
                        }
                    });
                    return button;
                }

                const pause = makeButton("Pause", "pause");
                const resume = makeButton("Resume", "resume");
                const refresh = document.createElement("button");
                refresh.textContent = "Refresh status";
                refresh.style.cssText = "padding:8px 12px;border-radius:6px;cursor:pointer;";
                refresh.addEventListener("click", async () => {
                    refresh.disabled = true;
                    try {
                        status.textContent = statusText(await callApi("status"));
                    } catch (error) {
                        status.textContent = error.message || String(error);
                    } finally {
                        refresh.disabled = false;
                    }
                });
                row.append(pause, resume, refresh);

                const note = document.createElement("small");
                note.textContent = "Pause takes effect between sampler iterations. The current GPU operation finishes first; model and latent memory remain allocated while paused.";
                note.style.cssText = "opacity:.7;line-height:1.45;";
                root.append(status, row, note);
                container.append(root);

                callApi("status")
                    .then((state) => { status.textContent = statusText(state); })
                    .catch((error) => { status.textContent = error.message || String(error); });
            }
        });
    }
});
