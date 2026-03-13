const statusPill = document.getElementById("status-pill");
const refreshBtn = document.getElementById("refresh-btn");
const syncBtn = document.getElementById("sync-btn");
const importsBtn = document.getElementById("imports-btn");
const planBtn = document.getElementById("plan-btn");
const storageBtn = document.getElementById("storage-btn");
const ingestForm = document.getElementById("ingest-form");
const ingestUrl = document.getElementById("ingest-url");
const ingestType = document.getElementById("ingest-type");
const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("search-input");
const searchResults = document.getElementById("search-results");
const heroStrip = document.getElementById("hero-strip");

const featuredTitle = document.getElementById("featured-title");
const featuredMeta = document.getElementById("featured-meta");
const featuredNote = document.getElementById("featured-note");
const featuredActions = document.getElementById("featured-actions");

const statOfflineHours = document.getElementById("stat-offline-hours");
const statOfflineNote = document.getElementById("stat-offline-note");
const statQueue = document.getElementById("stat-queue");
const statQueueNote = document.getElementById("stat-queue-note");
const statTitles = document.getElementById("stat-titles");
const statStorageNote = document.getElementById("stat-storage-note");
const statDeadletters = document.getElementById("stat-deadletters");
const statDeadlettersNote = document.getElementById("stat-deadletters-note");
const sysMediaFree = document.getElementById("sys-media-free");
const sysMediaNote = document.getElementById("sys-media-note");
const sysMemoryUsed = document.getElementById("sys-memory-used");
const sysMemoryNote = document.getElementById("sys-memory-note");
const sysCpuTemp = document.getElementById("sys-cpu-temp");
const sysCpuNote = document.getElementById("sys-cpu-note");
const sysLoad = document.getElementById("sys-load");
const sysLoadNote = document.getElementById("sys-load-note");

const rails = {
  continue: document.getElementById("rail-continue"),
  downloaded: document.getElementById("rail-downloaded"),
  recommended: document.getElementById("rail-recommended"),
  fresh: document.getElementById("rail-fresh"),
};

const queueList = document.getElementById("queue-list");
const deadlettersList = document.getElementById("deadletters-list");
const cardTemplate = document.getElementById("video-card-template");
const jobTemplate = document.getElementById("job-row-template");

function setStatus(text, tone = "neutral") {
  statusPill.textContent = text;
  statusPill.dataset.tone = tone;
}

function emptyState(container, message) {
  container.innerHTML = "";
  const p = document.createElement("p");
  p.className = "empty";
  p.textContent = message;
  container.appendChild(p);
}

function actionButton(label, className, handler) {
  const button = document.createElement("button");
  button.className = `btn ${className}`;
  button.textContent = label;
  button.addEventListener("click", handler);
  return button;
}

function formatHours(seconds = 0) {
  const hours = Number(seconds || 0) / 3600;
  return `${hours.toFixed(hours >= 10 ? 0 : 1)}h`;
}

function formatBytes(bytes = 0) {
  const value = Number(bytes || 0);
  if (value <= 0) {
    return "0 GB";
  }
  return `${(value / 1024 ** 3).toFixed(value >= 10 * 1024 ** 3 ? 0 : 1)} GB`;
}

function artSeed(video) {
  const source = String(video.channel || video.title || "B");
  let total = 0;
  for (const char of source) {
    total += char.charCodeAt(0);
  }
  return total % 360;
}

function videoInitials(video) {
  const source = String(video.channel || video.title || "BM")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => (part && part[0] ? part[0].toUpperCase() : ""));
  return source.join("") || "BM";
}

function chipText(video, source) {
  if (video.downloaded || video.local_path) {
    return "Local";
  }
  if (source === "recommended") {
    return "Suggested";
  }
  if (source === "fresh") {
    return "New";
  }
  return "Metadata";
}

function renderVideoCards(container, videos = [], source = "default") {
  container.innerHTML = "";
  if (!videos.length) {
    emptyState(container, "No items yet.");
    return;
  }

  videos.forEach((video) => {
    const node = cardTemplate.content.cloneNode(true);
    const art = node.querySelector(".video-art");
    const badge = node.querySelector(".video-badge");
    const chip = node.querySelector(".video-chip");
    const title = node.querySelector(".video-title");
    const meta = node.querySelector(".video-meta");
    const note = node.querySelector(".video-note");
    const actions = node.querySelector(".video-actions");

    art.style.setProperty("--poster-hue", `${artSeed(video)}deg`);
    badge.textContent = videoInitials(video);
    chip.textContent = chipText(video, source);
    title.textContent = video.title || "Untitled";
    meta.textContent = `${video.channel || "Unknown"}  |  ${video.upload_date || "Undated"}`;

    if (source === "recommended" && video.explanation && video.explanation.components) {
      const parts = video.explanation.components;
      note.textContent =
        `score ${(video.score || 0).toFixed(2)}  |  semantic ${parts.semantic_similarity}  |  recency ${parts.recency}`;
    } else if (video.downloaded || video.local_path) {
      note.textContent = "Ready for offline playback.";
    } else {
      note.textContent = video.source_url ? "Available to queue in background." : "Metadata only.";
    }

    if (video.downloaded || video.local_path) {
      actions.appendChild(
        actionButton("Play", "btn-primary", () => {
          window.open(`/stream/${encodeURIComponent(video.video_id)}`, "_blank", "noopener");
        })
      );
    }

    actions.appendChild(
      actionButton("Like", "btn-good", async () => {
        await sendFeedback(video.video_id, { liked: true, disliked: false, completed: false });
      })
    );
    actions.appendChild(
      actionButton("Dislike", "btn-bad", async () => {
        await sendFeedback(video.video_id, { liked: false, disliked: true, completed: false });
      })
    );

    if (!video.downloaded && video.source_url) {
      actions.appendChild(
        actionButton("Queue", "btn-ghost", async () => {
          await queueUrl(video.source_url, "auto", 1);
        })
      );
    }

    container.appendChild(node);
  });
}

function renderJobs(container, jobs, isDeadLetter = false) {
  container.innerHTML = "";
  if (!jobs.length) {
    emptyState(container, isDeadLetter ? "No dead-letter items." : "Queue is clear.");
    return;
  }

  jobs.forEach((job) => {
    const node = jobTemplate.content.cloneNode(true);
    const state = node.querySelector(".job-state");
    const priority = node.querySelector(".job-priority");
    const main = node.querySelector(".job-main");
    const sub = node.querySelector(".job-sub");
    const actions = node.querySelector(".job-actions");

    state.textContent = isDeadLetter ? "Dead" : job.status || "pending";
    priority.textContent = `P${job.priority != null ? job.priority : 0}`;
    main.textContent = job.url;

    sub.textContent = isDeadLetter
      ? `attempts ${job.attempts}  |  failed ${job.failed_at || "unknown"}`
      : `attempts ${job.attempts}  |  next ${job.next_run_at || "now"}`;

    if (isDeadLetter && job.id) {
      actions.appendChild(
        actionButton("Retry", "btn-ghost", async () => {
          await retryDeadLetter(job.id);
        })
      );
    }

    container.appendChild(node);
  });
}

function renderHeroStrip(data) {
  const queueCount = (data.queue || []).length;
  const deadletterCount = (data.deadletters || []).length;
  const downloadedCount = (data.downloaded || []).length;
  const offlineInventory = data.offline_inventory || {};
  const offlineHours = formatHours(offlineInventory.unwatched_duration_seconds || 0);
  heroStrip.innerHTML = "";

  [
    ["Offline runway", offlineHours],
    ["Queued now", String(queueCount)],
    ["Downloaded rail", String(downloadedCount)],
    ["Dead letters", String(deadletterCount)],
  ].forEach(([label, value]) => {
    const item = document.createElement("div");
    item.className = "hero-stat";
    item.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    heroStrip.appendChild(item);
  });
}

function renderFeatured(data) {
  const featured =
    (data.recommended && data.recommended[0]) ||
    (data.downloaded && data.downloaded[0]) ||
    (data.fresh && data.fresh[0]) ||
    null;

  featuredActions.innerHTML = "";
  if (!featured) {
    featuredTitle.textContent = "No featured title yet";
    featuredMeta.textContent = "Sync the bunker or queue a source to build your front page.";
    featuredNote.textContent = "Recommendations and downloaded titles will be highlighted here.";
    return;
  }

  featuredTitle.textContent = featured.title || "Untitled";
  featuredMeta.textContent = `${featured.channel || "Unknown"}  |  ${featured.upload_date || "Undated"}  |  ${featured.downloaded ? "Local copy ready" : "Queue available"}`;

  if (featured.explanation && featured.explanation.components) {
    const parts = featured.explanation.components;
    featuredNote.textContent =
      `Picked because semantic match is ${parts.semantic_similarity}, watch-history score is ${parts.watch_history}, and recency is ${parts.recency}.`;
  } else {
    featuredNote.textContent = featured.downloaded
      ? "Already stored in the bunker and ready for instant playback."
      : "Discovered recently and ready to be queued.";
  }

  if (featured.downloaded || featured.local_path) {
    featuredActions.appendChild(
      actionButton("Play Now", "btn-primary", () => {
        window.open(`/stream/${encodeURIComponent(featured.video_id)}`, "_blank", "noopener");
      })
    );
  }

  if (!featured.downloaded && featured.source_url) {
    featuredActions.appendChild(
      actionButton("Queue Download", "btn-gold", async () => {
        await queueUrl(featured.source_url, "auto", 2);
      })
    );
  }

  featuredActions.appendChild(
    actionButton("Like", "btn-good", async () => {
      await sendFeedback(featured.video_id, { liked: true, disliked: false, completed: false });
    })
  );
}

function renderStats(data) {
  const offline = data.offline_inventory || {};
  const queue = data.queue || [];
  const deadletters = data.deadletters || [];

  statOfflineHours.textContent = formatHours(offline.unwatched_duration_seconds || 0);
  statOfflineNote.textContent = data.offline_mode ? "Offline mode active" : "Online sync available";

  statQueue.textContent = String(queue.length);
  statQueueNote.textContent = queue.length ? "Background jobs in flight" : "Queue idle";

  statTitles.textContent = String(offline.total_downloaded_items || 0);
  statStorageNote.textContent = `${formatBytes(offline.downloaded_storage_bytes || 0)} stored locally`;

  statDeadletters.textContent = String(deadletters.length);
  statDeadlettersNote.textContent = deadletters.length ? "Failures need attention" : "No broken jobs";
}

function renderSystem(data) {
  const system = data.system || {};
  const mediaDisk = system.media_disk || {};
  const memory = system.memory || {};
  const load = system.load || {};

  sysMediaFree.textContent = mediaDisk.free_bytes ? formatBytes(mediaDisk.free_bytes) : "--";
  if (mediaDisk.used_bytes && mediaDisk.total_bytes) {
    sysMediaNote.textContent = `${formatBytes(mediaDisk.used_bytes)} used of ${formatBytes(mediaDisk.total_bytes)}`;
  } else {
    sysMediaNote.textContent = "Disk metrics unavailable";
  }

  sysMemoryUsed.textContent = memory.used_bytes ? formatBytes(memory.used_bytes) : "--";
  if (memory.available_bytes && memory.total_bytes) {
    sysMemoryNote.textContent = `${formatBytes(memory.available_bytes)} free of ${formatBytes(memory.total_bytes)}`;
  } else {
    sysMemoryNote.textContent = "Memory metrics unavailable";
  }

  if (system.cpu_temp_c != null) {
    sysCpuTemp.textContent = `${system.cpu_temp_c.toFixed(1)} C`;
    sysCpuNote.textContent = system.is_raspberry_pi ? "Pi thermal sensor active" : "Thermal sensor active";
  } else {
    sysCpuTemp.textContent = "--";
    sysCpuNote.textContent = "Thermal sensor not available";
  }

  if (load.normalized_load1 != null) {
    sysLoad.textContent = load.normalized_load1.toFixed(2);
    sysLoadNote.textContent = `load1 ${Number(load.load1 || 0).toFixed(2)} across ${Number(load.cpu_count || 1).toFixed(0)} cores`;
  } else {
    sysLoad.textContent = "--";
    sysLoadNote.textContent = "Load average unavailable";
  }
}

async function loadHome() {
  setStatus("Refreshing bunker...", "warn");
  try {
    const data = await fetchJson("/bunku/data/home?limit=16");
    renderHeroStrip(data);
    renderFeatured(data);
    renderStats(data);
    renderSystem(data);
    renderVideoCards(rails.continue, data.continue_watching || [], "continue");
    renderVideoCards(rails.downloaded, data.downloaded || [], "downloaded");
    renderVideoCards(rails.recommended, data.recommended || [], "recommended");
    renderVideoCards(rails.fresh, data.fresh || [], "fresh");
    renderJobs(queueList, data.queue || [], false);
    renderJobs(deadlettersList, data.deadletters || [], true);

    if (data.offline_mode) {
      setStatus("Offline mode active", "warn");
    } else {
      setStatus("Online and syncing", "good");
    }
  } catch (err) {
    console.error(err);
    setStatus("Refresh failed", "bad");
  }
}

async function search(query) {
  const q = query.trim();
  if (!q) {
    emptyState(searchResults, "Enter text to search.");
    return;
  }
  setStatus(`Searching for ${q}`, "warn");
  try {
    const rows = await fetchJson(`/search?q=${encodeURIComponent(q)}&limit=18`);
    renderVideoCards(searchResults, rows || [], "search");
    setStatus("Search complete", "good");
  } catch (err) {
    console.error(err);
    setStatus("Search failed", "bad");
  }
}

async function queueUrl(url, type = "auto", priority = 0) {
  const body = { url, target_type: type, priority };
  await fetchJson("/queue", { method: "POST", body: JSON.stringify(body) });
  setStatus("Queued for background download", "good");
  await loadHome();
}

async function sendFeedback(videoId, payload) {
  const body = {
    watch_seconds: 0,
    completed: false,
    liked: payload.liked != null ? payload.liked : null,
    disliked: payload.disliked != null ? payload.disliked : null,
    rating: payload.rating != null ? payload.rating : null,
    notes: payload.notes != null ? payload.notes : null,
  };
  await fetchJson(`/videos/${encodeURIComponent(videoId)}/watched`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  setStatus("Preference recorded", "good");
  await loadHome();
}

async function retryDeadLetter(deadLetterId) {
  await fetchJson(`/deadletters/${deadLetterId}/retry`, { method: "POST" });
  setStatus(`Retried dead-letter ${deadLetterId}`, "good");
  await loadHome();
}

async function triggerSync() {
  setStatus("Sync in progress", "warn");
  await fetchJson("/bunku/data/sync", { method: "POST" });
  setStatus("Sync finished", "good");
  await loadHome();
}

async function triggerOfflinePlan() {
  setStatus("Planning offline cache", "warn");
  const result = await fetchJson("/offline/plan", { method: "POST" });
  setStatus(`Queued ${result.queued_jobs || 0} items for offline use`, "good");
  await loadHome();
}

async function triggerStorageEnforce() {
  setStatus("Cleaning storage budget", "warn");
  const result = await fetchJson("/storage/enforce", { method: "POST" });
  setStatus(`Freed ${formatBytes(result.freed_bytes || 0)}`, "good");
  await loadHome();
}

async function triggerImportsOrganize() {
  setStatus("Organizing NAS imports", "warn");
  const result = await fetchJson("/imports/organize", { method: "POST" });
  setStatus(`Imported ${result.organized || 0} files`, "good");
  await loadHome();
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Request failed ${response.status}: ${text}`);
  }
  return response.json();
}

refreshBtn.addEventListener("click", () => {
  loadHome();
});

syncBtn.addEventListener("click", async () => {
  try {
    await triggerSync();
  } catch (err) {
    console.error(err);
    setStatus("Sync failed", "bad");
  }
});

importsBtn.addEventListener("click", async () => {
  try {
    await triggerImportsOrganize();
  } catch (err) {
    console.error(err);
    setStatus("NAS import failed", "bad");
  }
});

planBtn.addEventListener("click", async () => {
  try {
    await triggerOfflinePlan();
  } catch (err) {
    console.error(err);
    setStatus("Offline planning failed", "bad");
  }
});

storageBtn.addEventListener("click", async () => {
  try {
    await triggerStorageEnforce();
  } catch (err) {
    console.error(err);
    setStatus("Storage cleanup failed", "bad");
  }
});

ingestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = ingestUrl.value.trim();
  const type = ingestType.value || "auto";
  if (!url) {
    setStatus("Enter a source URL", "warn");
    return;
  }
  try {
    setStatus("Queueing source...", "warn");
    await queueUrl(url, type, 2);
    ingestUrl.value = "";
    ingestType.value = "auto";
  } catch (err) {
    console.error(err);
    setStatus("Queue request failed", "bad");
  }
});

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  search(searchInput.value);
});

loadHome();
