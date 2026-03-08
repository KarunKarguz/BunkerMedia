const statusPill = document.getElementById("status-pill");
const refreshBtn = document.getElementById("refresh-btn");
const syncBtn = document.getElementById("sync-btn");
const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("search-input");
const searchResults = document.getElementById("search-results");

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
  const colorByTone = {
    neutral: "var(--muted)",
    good: "var(--good)",
    warn: "var(--warn)",
    bad: "var(--bad)",
  };
  statusPill.style.color = colorByTone[tone] || colorByTone.neutral;
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

function renderVideoCards(container, videos = [], source = "default") {
  container.innerHTML = "";
  if (!videos.length) {
    emptyState(container, "No items yet.");
    return;
  }

  videos.forEach((video) => {
    const node = cardTemplate.content.cloneNode(true);
    const card = node.querySelector(".card");
    const title = node.querySelector(".card-title");
    const meta = node.querySelector(".card-meta");
    const note = node.querySelector(".card-note");
    const actions = node.querySelector(".card-actions");

    title.textContent = video.title || "Untitled";
    meta.textContent = `${video.channel || "Unknown"}  |  ${video.video_id}`;

    if (source === "recommended" && video.explanation?.components) {
      const components = video.explanation.components;
      note.textContent = `score=${video.score?.toFixed?.(3) ?? video.score} semantic=${components.semantic_similarity} recency=${components.recency}`;
    } else {
      note.textContent = video.upload_date ? `uploaded ${video.upload_date}` : "metadata only";
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
        actionButton("Queue", "btn-soft", async () => {
          await queueUrl(video.source_url, "auto", 1);
        })
      );
    }

    card.dataset.videoId = video.video_id;
    container.appendChild(node);
  });
}

function renderJobs(container, jobs, isDeadLetter = false) {
  container.innerHTML = "";
  if (!jobs.length) {
    emptyState(container, isDeadLetter ? "No dead-letter items." : "Queue is empty.");
    return;
  }

  jobs.forEach((job) => {
    const node = jobTemplate.content.cloneNode(true);
    node.querySelector(".job-main").textContent = job.url;

    const statusText = isDeadLetter
      ? `attempts=${job.attempts} failed_at=${job.failed_at || "n/a"}`
      : `status=${job.status} attempts=${job.attempts} next=${job.next_run_at || "now"}`;
    node.querySelector(".job-sub").textContent = statusText;

    const actions = node.querySelector(".job-actions");
    if (isDeadLetter && job.id) {
      actions.appendChild(
        actionButton("Retry", "btn-soft", async () => {
          await retryDeadLetter(job.id);
        })
      );
    }

    container.appendChild(node);
  });
}

async function loadHome() {
  setStatus("Refreshing...", "warn");
  try {
    const data = await fetchJson("/bunku/data/home?limit=16");
    renderVideoCards(rails.continue, data.continue_watching || [], "continue");
    renderVideoCards(rails.downloaded, data.downloaded || [], "downloaded");
    renderVideoCards(rails.recommended, data.recommended || [], "recommended");
    renderVideoCards(rails.fresh, data.fresh || [], "fresh");
    renderJobs(queueList, data.queue || [], false);
    renderJobs(deadlettersList, data.deadletters || [], true);

    if (data.offline_mode) {
      setStatus("Offline mode active", "warn");
    } else {
      setStatus("Online sync available", "good");
    }
  } catch (err) {
    console.error(err);
    setStatus("Failed to refresh", "bad");
  }
}

async function search(query) {
  const q = query.trim();
  if (!q) {
    emptyState(searchResults, "Enter text to search.");
    return;
  }
  setStatus(`Searching: ${q}`, "warn");
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
  setStatus("Queued for download", "good");
  await loadHome();
}

async function sendFeedback(videoId, payload) {
  const body = {
    watch_seconds: 0,
    completed: false,
    liked: payload.liked ?? null,
    disliked: payload.disliked ?? null,
    rating: payload.rating ?? null,
    notes: payload.notes ?? null,
  };
  await fetchJson(`/videos/${encodeURIComponent(videoId)}/watched`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  setStatus("Feedback recorded", "good");
  await loadHome();
}

async function retryDeadLetter(deadLetterId) {
  await fetchJson(`/deadletters/${deadLetterId}/retry`, { method: "POST" });
  setStatus(`Retried dead-letter ${deadLetterId}`, "good");
  await loadHome();
}

async function triggerSync() {
  setStatus("Sync requested", "warn");
  await fetchJson("/bunku/data/sync", { method: "POST" });
  setStatus("Sync completed", "good");
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

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  search(searchInput.value);
});

loadHome();
