"use strict";

const el = id => document.getElementById(id);
const session = document.querySelector('meta[name="operator-session"]').content;
const pretty = data => JSON.stringify(data, null, 2);
let selectedJob = "", activeReview = null, image = null, frame = "", observation = null;
let available = {}, processing = false, activeBox = null, refreshing = false;

async function api(path, body) {
  const options = body === undefined ? {} : {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-AIWork-Session": session},
    body: JSON.stringify(body)
  };
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request failed");
  return result;
}

async function act(action) {
  el("notice").textContent = "";
  try { await action(); }
  catch (error) { el("notice").textContent = error.message; }
}

function button(label, run) {
  const result = document.createElement("button");
  result.type = "button";
  result.textContent = label;
  result.onclick = () => act(run);
  return result;
}

function node(tag, text) {
  const result = document.createElement(tag);
  result.textContent = text;
  return result;
}

function draft() {
  const data = Object.fromEntries(new FormData(el("task")));
  for (const key of ["inputs", "write_roots", "deliverables"])
    data[key] = data[key].split(/\r?\n/).map(value => value.trim()).filter(Boolean);
  for (const key of ["commands", "checks"]) data[key] = JSON.parse(data[key]);
  for (const key of ["timeout", "complexity", "min_context"]) data[key] = Number(data[key]);
  return data;
}

function clearReview() {
  activeReview = null;
  el("review").hidden = true;
  el("submit").disabled = true;
}

el("task").oninput = clearReview;
el("task").onsubmit = event => {
  event.preventDefault();
  act(async () => {
    const request = draft();
    const result = await api("/api/review", request);
    if (pretty(request) !== pretty(draft())) return;
    activeReview = { ...request, review: result.review };
    const { manifest, eligible, verification_image } = result;
    el("review").textContent = pretty({manifest, eligible, verification_image});
    el("review").hidden = false;
    el("submit").disabled = false;
  });
};
el("submit").onclick = () => act(async () => {
  const reviewed = activeReview;
  clearReview();
  selectedJob = (await api("/api/queue", reviewed)).job;
  await refreshJobs();
  el("notice").textContent = "Queued. Choose Run to start this task.";
});

async function detail(job) {
  selectedJob = job;
  const data = await api("/api/jobs/" + job);
  if (selectedJob !== job) return;
  const current = el("detail");
  // Preserve disclosure state across polling.
  const expanded = new Set([...current.querySelectorAll("details[open]")].map(item => item.dataset.key));
  current.replaceChildren(node("h3", "Job " + job), node("p", data.detail || data.status));
  for (const attempt of data.attempts) {
    const record = data.records.find(item => item.n === Number(attempt.attempt.split("-")[1]));
    current.append(node("p", `${attempt.attempt} · ${record?.profile || "running"} · ${record?.status || "in progress"}`));
    const groups = [
      ["Telemetry", pretty({metrics: attempt.metrics, execution: attempt.execution, admission: attempt.admission})],
      ["Independent verification", pretty(attempt.verification)],
      ["Proposed source diff", attempt.patch || "No source diff recorded."]
    ];
    for (const [label, contents] of groups) {
      const info = document.createElement("details");
      info.dataset.key = attempt.attempt + label;
      info.open = expanded.has(info.dataset.key);
      info.append(node("summary", label), node("pre", contents));
      current.append(info);
    }
  }
}

async function refreshJobs() {
  if (refreshing) return;
  refreshing = true;
  try {
    const data = await api("/api/jobs");
    const tbody = el("jobs");
    tbody.replaceChildren();
    if (data.dispatch_error) el("notice").textContent = data.dispatch_error;
    for (const job of data.jobs) {
      const row = document.createElement("tr");
      const status = node("td", job.status);
      status.title = job.detail;
      const actions = node("td", "");
      actions.className = "actions";
      actions.append(button("Details", () => detail(job.id)));
      if (job.dispatchable) {
        const run = button("Run", async () => {
          run.disabled = true;
          await api("/api/run", {job: job.id});
          selectedJob = job.id;
          await refreshJobs();
        });
        run.disabled = data.dispatching;
        actions.append(run);
      }
      row.append(node("td", job.id.slice(0, 12)), status, node("td", job.updated), actions);
      tbody.append(row);
    }
    if (selectedJob) await detail(selectedJob);
  } finally {
    refreshing = false;
  }
}

async function refreshStatus() {
  available = await api("/api/status");
  const modelNodes = el("models");
  modelNodes.replaceChildren();
  const gib = bytes => typeof bytes === "number" ? (bytes / 2**30).toFixed(2) + " GiB" : "unavailable";
  const mem = available.memory;
  el("memory").textContent = `RAM free ${gib(mem.ram_available_bytes)} / ${gib(mem.ram_total_bytes)}\nVRAM free ${gib(mem.gpu_free_bytes)} / ${gib(mem.gpu_total_bytes)}`;
  for (const profile of available.profiles) {
    const readiness = profile.ready?.ready === true ? "ready"
      : profile.ready ? profile.ready.detail : "readiness unchecked";
    const resident = profile.residency ? profile.residency.resident ? "resident" : "idle/unloaded"
      : profile.owned_runtime ? "owned model starts at dispatch" : "residency unavailable";
    modelNodes.append(node("span", `${profile.id} · ${profile.model} · ${profile.context} context · ${resident} · ${readiness}`),
      button("Check " + profile.id, async () => {
        await api("/api/probe", {profile: profile.id});
        await refreshStatus();
      }));
  }
  el("permit-reclaim").disabled = !available.reclamation_enrolled;
  el("reclaim").disabled = !available.reclamation_enrolled || !el("permit-reclaim").checked;
  updateScreenControls();
}
el("refresh").onclick = () => act(refreshJobs);
el("refresh-models").onclick = () => act(refreshStatus);
el("permit-reclaim").onchange = () => {
  el("reclaim").disabled = !el("permit-reclaim").checked;
};
el("reclaim").onclick = () => act(async () => {
  el("permit-reclaim").checked = false;
  el("reclaim").disabled = true;
  const result = await api("/api/reclaim", {confirm: true});
  el("reclamation").textContent = pretty(result);
  el("reclamation").hidden = false;
  await refreshStatus();
});

function updateScreenControls() {
  const remote = el("perception-lane").value === "a100";
  el("consent").hidden = !remote;
  const enabled = remote ? available.remote_perception : available.local_perception;
  el("screen-status").textContent = processing ? "Processing screenshot…" : enabled ? ""
    : "The selected perception backend is not configured.";
  el("interpret").disabled = processing || !frame || !enabled || (remote && !el("share").checked);
  el("export-observation").disabled = processing || observation?.location !== "local";
  el("capture").disabled = processing;
  el("image-file").disabled = processing;
}

function draw() {
  if (!image) return;
  const canvas = el("preview");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(image, 0, 0);
  ctx.lineWidth = Math.max(1, canvas.width / 475);
  ctx.font = Math.max(12, canvas.width / 85) + "px system-ui";
  for (const box of observation?.elements || []) {
    const [left, top, right, bottom] = box.bbox.map((position, index) => position * (index % 2 ? canvas.height : canvas.width));
    ctx.strokeStyle = box.id === activeBox ? "#fff238" : box.kind === "text" ? "#73f0ff" : "#f371f9";
    ctx.strokeRect(left, top, right - left, bottom - top);
    ctx.fillStyle = "#172832";
    ctx.fillRect(left, top, ctx.measureText(String(box.id)).width + 6, parseInt(ctx.font, 10) + 4);
    ctx.fillStyle = ctx.strokeStyle;
    ctx.fillText(String(box.id), left + 3, top + parseInt(ctx.font, 10));
  }
}

async function preview(png) {
  frame = "";
  observation = null;
  activeBox = null;
  el("share").checked = false;
  el("elements").replaceChildren();
  el("observation").textContent = "";
  el("preview").hidden = true;
  const loading = new Image();
  loading.src = "data:image/png;base64," + png;
  await loading.decode();
  image = loading;
  frame = png;
  draw();
  el("preview").hidden = false;
  updateScreenControls();
}

async function readPng(file) {
  if (file.size > 4 * 1024 * 1024) throw new Error("Choose a PNG no larger than 4 MiB.");
  const png = new Uint8Array(await file.arrayBuffer());
  const header = new DataView(png.buffer);
  if (png.length < 33 || header.getUint32(0) !== 0x89504e47 ||
      header.getUint32(4) !== 0x0d0a1a0a || header.getUint32(12) !== 0x49484452)
    throw new Error("Choose a valid PNG.");
  const w = header.getUint32(16), h = header.getUint32(20);
  if (!w || !h || w > 4096 || h > 4096 || w * h > 4096 * 2160)
    throw new Error("Screenshot dimensions exceed the interpretation limit.");
  let binary = "";
  for (let offset = 0; offset < png.length; offset += 16384)
    binary += String.fromCharCode(...png.subarray(offset, offset + 16384));
  return btoa(binary);
}

function loadScreenshot(read) {
  return act(async () => {
    processing = true;
    el("share").checked = false;
    updateScreenControls();
    try { await preview(await read()); }
    finally {
      processing = false;
      updateScreenControls();
    }
  });
}

el("capture").onclick = () => loadScreenshot(async () => (await api("/api/capture", {})).png);
el("image-file").onchange = () => {
  const file = el("image-file").files[0];
  if (file) loadScreenshot(() => readPng(file));
};
el("perception-lane").onchange = () => {
  el("share").checked = false;
  updateScreenControls();
};
el("share").onchange = updateScreenControls;
el("export-observation").onclick = () => {
  if (observation?.location !== "local" || processing) return;
  const url = URL.createObjectURL(new Blob([pretty(observation) + "\n"], {type:"application/json"}));
  const link = document.createElement("a");
  link.href = url;
  link.download = "reviewed-screen.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
el("interpret").onclick = () => act(async () => {
  const shareRemote = el("share").checked;
  const location = el("perception-lane").value;
  el("share").checked = false;
  processing = true;
  updateScreenControls();
  try {
    observation = await api("/api/perception", {png: frame, location, share_remote: shareRemote});
    activeBox = null;
    el("observation").textContent = pretty(observation);
    const items = el("elements");
    items.replaceChildren();
    for (const item of observation.elements) {
      const li = document.createElement("li");
      li.append(button(item.kind + " · " + item.description, () => { activeBox = item.id; draw(); }));
      items.append(li);
    }
    draw();
  } finally {
    processing = false;
    updateScreenControls();
  }
});

act(refreshJobs);
act(refreshStatus);
setInterval(() => refreshJobs().catch(() => {}), 5000);
