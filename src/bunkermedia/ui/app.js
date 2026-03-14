const statusPill = document.getElementById("status-pill");
const profileSelect = document.getElementById("profile-select");
const profileAddBtn = document.getElementById("profile-add-btn");
const profileForm = document.getElementById("profile-form");
const profileName = document.getElementById("profile-name");
const profileKids = document.getElementById("profile-kids");
const profilePrivate = document.getElementById("profile-private");
const profilePin = document.getElementById("profile-pin");
const kidsBadge = document.getElementById("kids-badge");
const tvModeBtn = document.getElementById("tv-mode-btn");
const refreshBtn = document.getElementById("refresh-btn");
const syncBtn = document.getElementById("sync-btn");
const importsBtn = document.getElementById("imports-btn");
const planBtn = document.getElementById("plan-btn");
const storageBtn = document.getElementById("storage-btn");
const installBtn = document.getElementById("install-btn");
const ingestForm = document.getElementById("ingest-form");
const ingestUrl = document.getElementById("ingest-url");
const ingestType = document.getElementById("ingest-type");
const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("search-input");
const filterChannel = document.getElementById("filter-channel");
const filterFreshness = document.getElementById("filter-freshness");
const filterDurationMin = document.getElementById("filter-duration-min");
const filterDurationMax = document.getElementById("filter-duration-max");
const filterDownloaded = document.getElementById("filter-downloaded");
const filterResetBtn = document.getElementById("filter-reset-btn");
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
const privacyState = document.getElementById("privacy-state");
const privacyNote = document.getElementById("privacy-note");

const rails = {
  continue: document.getElementById("rail-continue"),
  downloaded: document.getElementById("rail-downloaded"),
  recommended: document.getElementById("rail-recommended"),
  fresh: document.getElementById("rail-fresh"),
};

const queueList = document.getElementById("queue-list");
const deadlettersList = document.getElementById("deadletters-list");
const deadlettersClearRetriedBtn = document.getElementById("deadletters-clear-retried-btn");
const deadlettersClearAllBtn = document.getElementById("deadletters-clear-all-btn");
const cardTemplate = document.getElementById("video-card-template");
const jobTemplate = document.getElementById("job-row-template");
const playerModal = document.getElementById("player-modal");
const playerBackdrop = document.getElementById("player-backdrop");
const playerTitle = document.getElementById("player-title");
const playerMeta = document.getElementById("player-meta");
const playerVideo = document.getElementById("player-video");
const playerWatchedBtn = document.getElementById("player-watched-btn");
const playerExternalBtn = document.getElementById("player-external-btn");
const playerCloseBtn = document.getElementById("player-close-btn");

const TV_MODE_KEY = "bunkermedia.tv_mode";
const videoRegistry = new Map();
const whyState = new Set();
let activeVideoId = null;
let lastFocusedElement = null;
let tvModeEnabled = localStorage.getItem(TV_MODE_KEY) !== "off";
let currentProfileId = null;
let deferredInstallPrompt = null;
let profileDirectory = [];

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
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", handler);
  return button;
}

function setTvMode(enabled) {
  tvModeEnabled = Boolean(enabled);
  document.body.classList.toggle("tv-mode", tvModeEnabled);
  tvModeBtn.textContent = tvModeEnabled ? "TV Mode On" : "TV Mode Off";
  tvModeBtn.setAttribute("aria-pressed", String(tvModeEnabled));
  localStorage.setItem(TV_MODE_KEY, tvModeEnabled ? "on" : "off");
}

function setKidsModeBadge(enabled) {
  kidsBadge.hidden = !enabled;
}

function setInstallAvailability(available) {
  installBtn.hidden = !available;
}

function renderProfiles(activeProfile, profiles = []) {
  profileDirectory = profiles || [];
  currentProfileId = activeProfile && activeProfile.profile_id ? activeProfile.profile_id : null;
  profileSelect.innerHTML = "";
  profiles.forEach((profile) => {
    const option = document.createElement("option");
    option.value = profile.profile_id;
    const labels = [profile.display_name];
    if (profile.is_kids) {
      labels.push("Kids");
    }
    if (profile.can_access_private) {
      labels.push("Vault");
    }
    if (profile.pin_required) {
      labels.push("PIN");
    }
    option.textContent = labels.join(" | ");
    if (profile.profile_id === currentProfileId) {
      option.selected = true;
    }
    profileSelect.appendChild(option);
  });
  setKidsModeBadge(Boolean(activeProfile && activeProfile.is_kids));
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

function activeSearchFilters() {
  const params = new URLSearchParams();
  const channel = filterChannel.value.trim();
  const freshness = filterFreshness.value.trim();
  const durationMin = filterDurationMin.value.trim();
  const durationMax = filterDurationMax.value.trim();

  if (channel) {
    params.set("channel", channel);
  }
  if (freshness) {
    params.set("freshness_days", freshness);
  }
  if (durationMin) {
    params.set("duration_min", String(Number(durationMin) * 60));
  }
  if (durationMax) {
    params.set("duration_max", String(Number(durationMax) * 60));
  }
  if (filterDownloaded.checked) {
    params.set("downloaded_only", "true");
  }
  return params;
}

function summarizeWhy(video) {
  if (!video || !video.explanation || !video.explanation.components) {
    return "";
  }
  const parts = video.explanation.components;
  const strong = [];
  if (Number(parts.semantic_similarity || 0) > 0.15) {
    strong.push(`semantic match ${Number(parts.semantic_similarity).toFixed(2)}`);
  }
  if (Number(parts.channel_preference || 0) > 0.1) {
    strong.push(`channel affinity ${Number(parts.channel_preference).toFixed(2)}`);
  }
  if (Number(parts.watch_history || 0) > 0.1) {
    strong.push(`watch history ${Number(parts.watch_history).toFixed(2)}`);
  }
  if (Number(parts.recency || 0) > 0.2) {
    strong.push(`freshness ${Number(parts.recency).toFixed(2)}`);
  }
  if (!strong.length) {
    strong.push(`trend score ${Number(parts.trending || 0).toFixed(2)}`);
  }
  return `Why this: ${strong.join(" | ")}`;
}

function canManagePrivateVault() {
  const selected = profileDirectory.find((profile) => profile.profile_id === currentProfileId);
  return Boolean(selected && selected.can_access_private);
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
  if (video.privacy_level === "explicit") {
    return "Explicit";
  }
  if (video.privacy_level === "private") {
    return "Private";
  }
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

function registerVideo(video, source) {
  if (!video || !video.video_id) {
    return null;
  }
  const existing = videoRegistry.get(video.video_id) || {};
  const merged = { ...existing, ...video, source_context: source };
  videoRegistry.set(video.video_id, merged);
  return merged;
}

function streamUrl(videoId) {
  return `/stream/${encodeURIComponent(videoId)}`;
}

async function markWatched(videoId, completed = true) {
  if (!videoId) {
    return;
  }
  await sendFeedback(videoId, {
    liked: null,
    disliked: null,
    completed,
    watch_seconds: Math.round(playerVideo.currentTime || 0),
  });
}

function openPlayer(videoId) {
  const video = videoRegistry.get(videoId);
  if (!video || !(video.downloaded || video.local_path)) {
    return;
  }
  activeVideoId = videoId;
  lastFocusedElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  playerTitle.textContent = video.title || "Untitled";
  playerMeta.textContent = `${video.channel || "Unknown"}  |  ${video.upload_date || "Undated"}  |  Local playback`;
  playerExternalBtn.dataset.videoId = videoId;
  playerWatchedBtn.dataset.videoId = videoId;
  playerVideo.src = streamUrl(videoId);
  playerVideo.dataset.videoId = videoId;
  playerModal.hidden = false;
  document.body.classList.add("modal-open");
  playerCloseBtn.focus();
  playerVideo.play().catch(() => {});
}

function closePlayer() {
  if (playerModal.hidden) {
    return;
  }
  playerVideo.pause();
  playerVideo.removeAttribute("src");
  playerVideo.load();
  playerModal.hidden = true;
  document.body.classList.remove("modal-open");
  activeVideoId = null;
  if (lastFocusedElement) {
    lastFocusedElement.focus();
  }
}

async function activateCard(card) {
  const videoId = card.dataset.videoId;
  const sourceUrl = card.dataset.sourceUrl;
  const type = card.dataset.targetType || "auto";
  const isDownloaded = card.dataset.downloaded === "true";

  if (isDownloaded && videoId) {
    openPlayer(videoId);
    return;
  }
  if (sourceUrl) {
    await queueUrl(sourceUrl, type, 1);
  }
}

function isTypingTarget(target) {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tag = target.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select" || target.isContentEditable;
}

function visibleNavigableElements() {
  return Array.from(
    document.querySelectorAll(
      [
        "button:not([disabled])",
        "input:not([disabled])",
        "select:not([disabled])",
        ".video-card",
        ".job-row",
      ].join(",")
    )
  ).filter((element) => {
    if (!(element instanceof HTMLElement)) {
      return false;
    }
    if (playerModal.hidden === false) {
      return playerModal.contains(element);
    }
    if (element.closest("[hidden]")) {
      return false;
    }
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  });
}

function focusElement(element) {
  if (!(element instanceof HTMLElement)) {
    return;
  }
  element.focus({ preventScroll: true });
  element.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
}

function pickSpatialTarget(elements, activeElement, direction) {
  if (!(activeElement instanceof HTMLElement)) {
    return elements[0] || null;
  }
  const activeRect = activeElement.getBoundingClientRect();
  const activeCenterX = activeRect.left + activeRect.width / 2;
  const activeCenterY = activeRect.top + activeRect.height / 2;

  const candidates = elements
    .filter((element) => element !== activeElement)
    .map((element) => {
      const rect = element.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const deltaX = centerX - activeCenterX;
      const deltaY = centerY - activeCenterY;

      if (direction === "left" && deltaX >= -12) {
        return null;
      }
      if (direction === "right" && deltaX <= 12) {
        return null;
      }
      if (direction === "up" && deltaY >= -12) {
        return null;
      }
      if (direction === "down" && deltaY <= 12) {
        return null;
      }

      const primary = direction === "left" || direction === "right" ? Math.abs(deltaX) : Math.abs(deltaY);
      const secondary = direction === "left" || direction === "right" ? Math.abs(deltaY) : Math.abs(deltaX);
      return { element, score: primary * 4 + secondary };
    })
    .filter(Boolean)
    .sort((a, b) => a.score - b.score);

  return candidates.length ? candidates[0].element : null;
}

function moveFocus(direction) {
  const elements = visibleNavigableElements();
  if (!elements.length) {
    return;
  }
  const target = pickSpatialTarget(elements, document.activeElement, direction) || elements[0];
  focusElement(target);
}

function renderVideoCards(container, videos = [], source = "default") {
  container.innerHTML = "";
  if (!videos.length) {
    emptyState(container, "No items yet.");
    return;
  }

  videos.forEach((video) => {
    const registeredVideo = registerVideo(video, source) || video;
    const node = cardTemplate.content.cloneNode(true);
    const card = node.querySelector(".video-card");
    const art = node.querySelector(".video-art");
    const badge = node.querySelector(".video-badge");
    const chip = node.querySelector(".video-chip");
    const title = node.querySelector(".video-title");
    const meta = node.querySelector(".video-meta");
    const note = node.querySelector(".video-note");
    const why = node.querySelector(".video-why");
    const actions = node.querySelector(".video-actions");

    card.tabIndex = 0;
    card.dataset.videoId = registeredVideo.video_id || "";
    card.dataset.sourceUrl = registeredVideo.source_url || "";
    card.dataset.targetType = "auto";
    card.dataset.downloaded = String(Boolean(registeredVideo.downloaded || registeredVideo.local_path));
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", registeredVideo.title || "Untitled");

    art.style.setProperty("--poster-hue", `${artSeed(registeredVideo)}deg`);
    badge.textContent = videoInitials(registeredVideo);
    chip.textContent = chipText(registeredVideo, source);
    title.textContent = registeredVideo.title || "Untitled";
    meta.textContent = `${registeredVideo.channel || "Unknown"}  |  ${registeredVideo.upload_date || "Undated"}`;

    if (source === "recommended" && registeredVideo.explanation && registeredVideo.explanation.components) {
      note.textContent = summarizeWhy(registeredVideo);
      why.textContent = [
        `Final score ${(registeredVideo.score || 0).toFixed(2)}`,
        `Trend ${Number(registeredVideo.explanation.components.trending || 0).toFixed(2)}`,
        `Channel ${Number(registeredVideo.explanation.components.channel_preference || 0).toFixed(2)}`,
        `History ${Number(registeredVideo.explanation.components.watch_history || 0).toFixed(2)}`,
        `Semantic ${Number(registeredVideo.explanation.components.semantic_similarity || 0).toFixed(2)}`,
        `Recency ${Number(registeredVideo.explanation.components.recency || 0).toFixed(2)}`,
      ].join(" | ");
      why.hidden = !whyState.has(String(registeredVideo.video_id));
    } else if (registeredVideo.downloaded || registeredVideo.local_path) {
      note.textContent = "Ready for offline playback.";
      why.hidden = true;
    } else {
      note.textContent = registeredVideo.source_url ? "Available to queue in background." : "Metadata only.";
      why.hidden = true;
    }

    if (registeredVideo.privacy_level === "private") {
      note.textContent = `${note.textContent} Private vault item.`;
    }
    if (registeredVideo.privacy_level === "explicit") {
      note.textContent = `${note.textContent} Explicit vault item.`;
    }

    card.addEventListener("click", async (event) => {
      if (event.target instanceof HTMLElement && event.target.closest("button")) {
        return;
      }
      try {
        await activateCard(card);
      } catch (err) {
        console.error(err);
        setStatus("Card action failed", "bad");
      }
    });
    card.addEventListener("keydown", async (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      event.preventDefault();
      try {
        await activateCard(card);
      } catch (err) {
        console.error(err);
        setStatus("Card action failed", "bad");
      }
    });

    if (registeredVideo.downloaded || registeredVideo.local_path) {
      actions.appendChild(
        actionButton("Play", "btn-primary", () => {
          openPlayer(registeredVideo.video_id);
        })
      );
    }

    actions.appendChild(
      actionButton("Like", "btn-good", async () => {
        await sendFeedback(registeredVideo.video_id, { liked: true, disliked: false, completed: false });
      })
    );
    actions.appendChild(
      actionButton("Dislike", "btn-bad", async () => {
        await sendFeedback(registeredVideo.video_id, { liked: false, disliked: true, completed: false });
      })
    );

    if (!registeredVideo.downloaded && registeredVideo.source_url) {
      actions.appendChild(
        actionButton("Queue", "btn-ghost", async () => {
          await queueUrl(registeredVideo.source_url, "auto", 1);
        })
      );
    }

    if (canManagePrivateVault()) {
      const nextPrivacy =
        registeredVideo.privacy_level === "standard"
          ? "private"
          : registeredVideo.privacy_level === "private"
            ? "explicit"
            : "standard";
      const label =
        registeredVideo.privacy_level === "standard"
          ? "Private"
          : registeredVideo.privacy_level === "private"
            ? "Explicit"
            : "Normal";
      actions.appendChild(
        actionButton(label, "btn-ghost", async () => {
          await setVideoPrivacy(registeredVideo.video_id, nextPrivacy);
        })
      );
    }

    if (source === "recommended" && registeredVideo.explanation) {
      actions.appendChild(
        actionButton(why.hidden ? "Why This" : "Hide Why", "btn-ghost", () => {
          const key = String(registeredVideo.video_id);
          if (why.hidden) {
            whyState.add(key);
            why.hidden = false;
          } else {
            whyState.delete(key);
            why.hidden = true;
          }
          renderVideoCards(container, videos, source);
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
    const row = node.querySelector(".job-row");
    const state = node.querySelector(".job-state");
    const priority = node.querySelector(".job-priority");
    const main = node.querySelector(".job-main");
    const sub = node.querySelector(".job-sub");
    const actions = node.querySelector(".job-actions");

    row.tabIndex = 0;
    row.setAttribute("role", "group");

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
    } else if (job.id) {
      actions.appendChild(
        actionButton("Up", "btn-ghost", async () => {
          await updateJobPriority(job.id, Number(job.priority || 0) + 1);
        })
      );
      actions.appendChild(
        actionButton("Down", "btn-ghost", async () => {
          await updateJobPriority(job.id, Number(job.priority || 0) - 1);
        })
      );
      if (job.status === "paused") {
        actions.appendChild(
          actionButton("Resume", "btn-gold", async () => {
            await resumeJob(job.id);
          })
        );
      } else if (job.status === "pending") {
        actions.appendChild(
          actionButton("Pause", "btn-bad", async () => {
            await pauseJob(job.id);
          })
        );
      }
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
        registerVideo(featured, "featured");
        openPlayer(featured.video_id);
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

function renderPrivacy(data) {
  const privacy = data.privacy || {};
  const profile = privacy.active_profile || {};
  const notes = privacy.notes || [];

  if (!privacy.private_mode_enabled) {
    privacyState.textContent = "Off";
    privacyNote.textContent = "Private vault mode disabled";
    return;
  }

  if (privacy.status === "ok") {
    privacyState.textContent = "Ready";
  } else if (privacy.status === "warning") {
    privacyState.textContent = "Check";
  } else {
    privacyState.textContent = "Info";
  }

  const statusBits = [];
  if (privacy.marker_present) {
    statusBits.push("marker");
  }
  if (privacy.encrypted_mount_detected) {
    statusBits.push("encrypted mount");
  }
  if (profile.can_access_private) {
    statusBits.push("vault profile");
  }
  privacyNote.textContent = statusBits.length ? statusBits.join(" | ") : notes.join(" | ") || "No privacy hints";
}

async function loadHome() {
  setStatus("Refreshing bunker...", "warn");
  try {
    const data = await fetchJson("/bunku/data/home?limit=16");
    renderProfiles(data.active_profile || null, data.profiles || []);
    renderHeroStrip(data);
    renderFeatured(data);
    renderStats(data);
    renderSystem(data);
    renderPrivacy(data);
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

    if (
      tvModeEnabled &&
      playerModal.hidden &&
      (!document.activeElement || document.activeElement === document.body)
    ) {
      const firstTarget = visibleNavigableElements()[0];
      if (firstTarget) {
        focusElement(firstTarget);
      }
    }
  } catch (err) {
    console.error(err);
    setStatus("Refresh failed", "bad");
  }
}

async function search(query) {
  const q = query.trim();
  const params = activeSearchFilters();
  if (!q && Array.from(params.keys()).length === 0) {
    emptyState(searchResults, "Enter text or apply filters.");
    return;
  }
  if (q) {
    params.set("q", q);
  } else {
    params.set("q", "");
  }
  params.set("limit", "18");
  setStatus(q ? `Searching for ${q}` : "Applying filters", "warn");
  try {
    const rows = await fetchJson(`/search?${params.toString()}`);
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
    watch_seconds: payload.watch_seconds != null ? payload.watch_seconds : 0,
    completed: payload.completed != null ? payload.completed : false,
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

async function clearDeadLetters(retriedOnly = false) {
  const suffix = retriedOnly ? "?retried_only=true" : "";
  const result = await fetchJson(`/deadletters${suffix}`, { method: "DELETE" });
  setStatus(`Cleared ${result.deleted || 0} dead letters`, "good");
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

async function setVideoPrivacy(videoId, privacyLevel) {
  await fetchJson(`/videos/${encodeURIComponent(videoId)}/privacy`, {
    method: "POST",
    body: JSON.stringify({ privacy_level: privacyLevel }),
  });
  setStatus(`Privacy set to ${privacyLevel}`, "good");
  await loadHome();
}

async function pauseJob(jobId) {
  await fetchJson(`/jobs/${jobId}/pause`, { method: "POST" });
  setStatus(`Paused job ${jobId}`, "good");
  await loadHome();
}

async function resumeJob(jobId) {
  await fetchJson(`/jobs/${jobId}/resume`, { method: "POST" });
  setStatus(`Resumed job ${jobId}`, "good");
  await loadHome();
}

async function updateJobPriority(jobId, priority) {
  await fetchJson(`/jobs/${jobId}/priority`, {
    method: "POST",
    body: JSON.stringify({ priority }),
  });
  setStatus(`Priority updated for job ${jobId}`, "good");
  await loadHome();
}

async function selectProfile(profileId) {
  const profile = profileDirectory.find((item) => item.profile_id === profileId);
  let pin = null;
  if (profile && profile.pin_required) {
    pin = window.prompt(`Enter PIN for ${profile.display_name}`) || "";
    if (!pin) {
      throw new Error("PIN required");
    }
  }
  await fetchJson(`/profiles/${encodeURIComponent(profileId)}/select`, {
    method: "POST",
    body: JSON.stringify({ pin }),
  });
  setStatus(`Switched to ${profileSelect.options[profileSelect.selectedIndex].text}`, "good");
  await loadHome();
}

async function createProfile(displayName, isKids, canAccessPrivate, pin) {
  const result = await fetchJson("/profiles", {
    method: "POST",
    body: JSON.stringify({
      display_name: displayName,
      is_kids: isKids,
      can_access_private: canAccessPrivate,
      pin: pin || null,
    }),
  });
  setStatus(`Created profile ${result.profile.display_name}`, "good");
  profileForm.hidden = true;
  profileName.value = "";
  profileKids.checked = false;
  profilePrivate.checked = false;
  profilePin.value = "";
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

async function registerShellServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    return;
  }
  try {
    await navigator.serviceWorker.register("/bunku/sw.js", { scope: "/bunku/" });
  } catch (err) {
    console.error("service worker registration failed", err);
  }
}

refreshBtn.addEventListener("click", () => {
  loadHome();
});

tvModeBtn.addEventListener("click", () => {
  setTvMode(!tvModeEnabled);
});

profileAddBtn.addEventListener("click", () => {
  profileForm.hidden = !profileForm.hidden;
  if (!profileForm.hidden) {
    profileName.focus();
  }
});

profileSelect.addEventListener("change", async () => {
  try {
    await selectProfile(profileSelect.value);
  } catch (err) {
    console.error(err);
    setStatus("Profile switch failed", "bad");
    await loadHome();
  }
});

profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const displayName = profileName.value.trim();
  const pin = profilePin.value.trim();
  if (!displayName) {
    setStatus("Enter a profile name", "warn");
    return;
  }
  if (pin && pin.length < 4) {
    setStatus("PIN must be at least 4 characters", "warn");
    return;
  }
  try {
    await createProfile(displayName, Boolean(profileKids.checked), Boolean(profilePrivate.checked), pin);
  } catch (err) {
    console.error(err);
    setStatus("Profile creation failed", "bad");
  }
});

installBtn.addEventListener("click", async () => {
  if (!deferredInstallPrompt) {
    return;
  }
  deferredInstallPrompt.prompt();
  try {
    await deferredInstallPrompt.userChoice;
  } catch (err) {
    console.error(err);
  }
  deferredInstallPrompt = null;
  setInstallAvailability(false);
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

filterResetBtn.addEventListener("click", () => {
  searchInput.value = "";
  filterChannel.value = "";
  filterFreshness.value = "";
  filterDurationMin.value = "";
  filterDurationMax.value = "";
  filterDownloaded.checked = false;
  emptyState(searchResults, "Filters cleared.");
});

deadlettersClearRetriedBtn.addEventListener("click", async () => {
  try {
    await clearDeadLetters(true);
  } catch (err) {
    console.error(err);
    setStatus("Dead-letter cleanup failed", "bad");
  }
});

deadlettersClearAllBtn.addEventListener("click", async () => {
  try {
    await clearDeadLetters(false);
  } catch (err) {
    console.error(err);
    setStatus("Dead-letter cleanup failed", "bad");
  }
});

playerBackdrop.addEventListener("click", closePlayer);
playerCloseBtn.addEventListener("click", closePlayer);
playerExternalBtn.addEventListener("click", () => {
  if (activeVideoId) {
    window.open(streamUrl(activeVideoId), "_blank", "noopener");
  }
});
playerWatchedBtn.addEventListener("click", async () => {
  try {
    await markWatched(activeVideoId, true);
    setStatus("Marked as watched", "good");
    closePlayer();
  } catch (err) {
    console.error(err);
    setStatus("Watch update failed", "bad");
  }
});
playerVideo.addEventListener("ended", async () => {
  try {
    await markWatched(activeVideoId, true);
    setStatus("Playback completed", "good");
  } catch (err) {
    console.error(err);
  }
});

document.addEventListener("keydown", async (event) => {
  if (event.key === "Escape" && !playerModal.hidden) {
    event.preventDefault();
    closePlayer();
    return;
  }

  if (!tvModeEnabled) {
    return;
  }

  if (isTypingTarget(event.target) || event.altKey || event.ctrlKey || event.metaKey) {
    return;
  }

  if (event.key === "ArrowLeft") {
    event.preventDefault();
    moveFocus("left");
    return;
  }
  if (event.key === "ArrowRight") {
    event.preventDefault();
    moveFocus("right");
    return;
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    moveFocus("up");
    return;
  }
  if (event.key === "ArrowDown") {
    event.preventDefault();
    moveFocus("down");
    return;
  }
  if (
    (event.key === "Enter" || event.key === " ") &&
    document.activeElement &&
    document.activeElement.classList &&
    document.activeElement.classList.contains("job-row")
  ) {
    event.preventDefault();
    const retryButton = document.activeElement.querySelector("button");
    if (retryButton) {
      retryButton.click();
    }
  }
});

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  setInstallAvailability(true);
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  setInstallAvailability(false);
  setStatus("Bunku installed on this device", "good");
});

setTvMode(tvModeEnabled);
setInstallAvailability(false);
registerShellServiceWorker();
loadHome();
