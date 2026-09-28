const $ = (id) => document.getElementById(id);

const I18N = {
  id: {
    "top.tagline": "Scan Most Replayed, potong otomatis, subtitle rapi.",
    "label.url": "YouTube URL",
    "ph.url": "https://www.youtube.com/watch?v=...",
    "help.url": "Tempel link video/shorts. Nanti keluar preview.",
    "label.mode": "Mode",
    "opt.mode.heatmap": "Scan heatmap (Most Replayed)",
    "opt.mode.custom": "Custom start/end (manual)",
    "help.mode": "Scan = cari momen paling rame. Custom = potong dari waktu yang kamu tentuin.",
    "label.ratio": "Ratio",
    "opt.ratio.9_16": "9:16 (Shorts)",
    "opt.ratio.original": "Original",
    "help.ratio": "Pilih bentuk output video. 9:16 buat Shorts/Reels/TikTok.",
    "label.crop": "Crop",
    "opt.crop.default": "Default",
    "opt.crop.split_left": "Split Left",
    "opt.crop.split_right": "Split Right",
    "help.crop": "Split itu buat gaming: atas gameplay, bawah facecam.",
    "label.padding": "Padding (detik)",
    "help.padding": "Nambah detik sebelum & sesudah momen biar nggak “kepotong nanggung”.",
    "label.max_clips": "Max clips",
    "help.max_clips": "Berapa potongan yang mau dihasilkan dari heatmap.",
    "label.subtitle": "Subtitle",
    "opt.no": "No",
    "opt.yes": "Yes",
    "help.subtitle": "Kalau Yes, audio ditranskrip jadi teks lalu dibakar ke video.",
    "label.whisper_model": "Model (Whisper)",
    "help.whisper_model": "Ini model AI buat transkripsi suara ke teks. Makin besar makin akurat, makin berat.",
    "label.subtitle_font": "Font Subtitle",
    "opt.custom": "Custom…",
    "ph.subtitle_font_custom": "Nama font custom (mis. Poppins)",
    "help.subtitle_font": "Kalau font-nya ada di folder fonts, isi Fonts dir = fonts.",
    "label.subtitle_location": "Subtitle Location",
    "opt.subtitle_location.bottom": "Bottom",
    "opt.subtitle_location.center": "Centered",
    "help.subtitle_location": "Bottom = lebih natural buat Shorts. Centered = lebih “in your face”.",
    "label.subtitle_fontsdir": "Fonts dir (opsional)",
    "help.subtitle_fontsdir": "Folder berisi file .ttf/.otf buat subtitle. Default: folder project <b>fonts</b>.",
    "label.start": "Start (detik atau mm:ss)",
    "ph.start": "689 atau 11:29",
    "label.end": "End (detik atau mm:ss)",
    "ph.end": "742 atau 12:22",
    "btn.scan": "Scan Heatmap",
    "btn.clip": "Buat Clip",
    "help.actions": "Scan Heatmap = ambil daftar momen “Most Replayed”. Buat Clip = download + crop + (opsional) subtitle.",
    "panel.segments": "Segments",
    "btn.select_all": "Select All",
    "btn.clear": "Clear",
    "btn.create_selected": "Create Selected Clip",
    "panel.progress": "Progress",
    "js.modal.preview_segment": "Preview Segment",
    "js.modal.preview_clip": "Preview Clip",
    "js.segments.empty": "Belum ada segment. Klik Scan Heatmap dulu.",
    "js.segments.empty.scanned": "Scan sudah dijalankan tapi tidak ada segment. Coba lagi, atau pakai mode Custom start/end.",
    "js.seg.score.title": "Skor intensitas heatmap",
    "js.seg.score.none": "Tanpa skor heatmap (fallback)",
    "js.src.heatmap": "Sumber: Most Replayed YouTube ({markers} titik heatmap, {count} momen).",
    "js.src.fallback": "Sumber: fallback. {reason} Segment di bawah dibuat berjarak rata dari durasi video, bukan dari heatmap.",
    "js.src.fallback.short": "Fallback",
    "js.src.heatmap.short": "Most Replayed",
    "js.preview.loading": "Loading preview…",
    "js.progress.count": "{done}/{total} selesai • {success} sukses",
    "js.selected.count": "{count} dipilih",
    "js.stage.download": "Download",
    "js.stage.crop": "Crop",
    "js.stage.subtitle": "Subtitle",
    "js.stage.subtitle_model_load": "Load model",
    "js.stage.subtitle_transcribe": "Transcribe",
    "js.stage.subtitle_write": "Tulis subtitle",
    "js.stage.burn_subtitle": "Burn subtitle",
    "js.stage.finalize": "Finalize",
    "js.stage.done_clip": "Selesai",
    "js.topprogress.processing": "Processing",
    "panel.ai": "AI Metadata",
    "label.ai_base_url": "AI server (base URL)",
    "help.ai_base_url": "Ollama, LM Studio, atau llama.cpp server. Hanya alamat lokal atau jaringan LAN yang boleh dipakai.",
    "label.ai_model": "Model",
    "help.ai_model": "Tekan Test server buat ambil daftar model yang tersedia.",
    "label.ai_api_key": "API key (opsional)",
    "help.ai_api_key": "Cuma diisi kalau server lokalmu minta kunci. Disimpan di browser ini saja.",
    "label.ai_tone": "Gaya tulisan",
    "help.ai_tone": "Informatif, santai, energetik, atau edukatif — diterapkan ke judul, hook, dan deskripsi.",
    "label.ai_hook": "Hook relevan",
    "help.ai_hook": "Buat kalimat pembuka yang relevan dengan topik video.",
    "opt.ai_tone.informative": "Informatif",
    "opt.ai_tone.casual": "Santai",
    "opt.ai_tone.energetic": "Energetik",
    "opt.ai_tone.educational": "Edukatif",
    "label.ai_timeout": "Timeout (detik)",
    "help.ai_timeout": "Model lokal di CPU bisa lambat. Naikkan kalau sering kehabisan waktu.",
    "label.ai_note": "Instruksi tambahan (opsional)",
    "help.ai_note": "Misalnya: fokus pemula, atau sebut Tools yang dipakai.",
    "label.ai_transcript": "Transkrip (opsional)",
    "help.ai_transcript": "Tempel cuplikan transkrip (dari subtitle, .srt, atau catatan) supaya judul dan tag jauh lebih akurat.",
    "label.ai_titles": "Pilihan judul",
    "label.ai_description": "Deskripsi",
    "label.ai_tags": "Tag",
    "btn.ai_test": "Test server",
    "btn.ai_use_transcript": "Pakai transkrip",
    "btn.ai_generate": "Generate metadata",
    "btn.copy": "Salin",
    "btn.copy_all": "Salin semua",
    "js.ai.ready": "Siap",
    "js.ai.no_model": "Isi base URL lalu pilih model dulu.",
    "js.ai.need_video": "Tempel link YouTube dulu supaya AI tahu topiknya.",
    "js.ai.testing": "Menghubungi server AI...",
    "js.ai.test_ok": "Server hidup, {count} model tersedia",
    "js.ai.test_ok_empty": "Server hidup, tapi daftar model kosong. Isi nama model manual.",
    "js.ai.model_missing": "Server hidup, tapi model {model} tidak ada di daftarnya.",
    "js.ai.generating": "Model berpikir... di CPU ini bisa lama.",
    "js.ai.done": "Selesai dalam {sec} detik",
    "js.ai.partial": "Model menjawab tidak lengkap, hasil parsial tetap ditampilkan.",
    "js.ai.lang_warn": "Ada karakter dari bahasa lain. Periksa sebelum dipakai.",
    "js.ai.copied": "Tersalin",
    "js.ai.copy_fail": "Gagal menyalin. Salin manual dari kotak ini.",
    "js.ai.transcript_added": "Transkrip dipakai sebagai konteks.",
    "js.ai.transcript_none": "Kotak transkrip masih kosong. Tempel cuplikan transkrip dulu.",
    "js.ai.tr_title": "Judul hasil generate",
    "js.ai.desc_empty": "(model tidak memberi judul)",
    "js.ai.tags_empty": "(model tidak memberi tag)",
    "js.ai.hash_empty": "(model tidak memberi hashtag)",
    "js.ai.hash_desc_on": "Hashtag ikut ditempel di akhir deskripsi",
    "js.ai.hash_desc_off": "Hashtag tidak ditempel di deskripsi",
    "js.ai.cfg_saving": "Menyimpan config AI...",
    "js.ai.cfg_saved": "Config AI tersimpan di server.",
    "js.ai.cfg_saved_key": "Config AI tersimpan (termasuk API key di server).",
    "js.ai.cfg_loaded": "Config AI dimuat dari server.",
    "js.ai.cfg_loaded_key": "Config AI dimuat. API key tersimpan dipakai dari server.",
    "js.ai.cfg_cleared": "Config AI dihapus dari server.",
    "js.ai.cfg_failed": "Gagal menyimpan config:",
    "btn.ai_save": "Simpan config",
    "btn.ai_clear_cfg": "Hapus config",
    "label.ai.hashtags": "Hashtag",
    "help.ai.hashtags": "Hashtag ditempel di akhir deskripsi dan bisa di atas judul. Maksimal 15 yang tampil.",
    "js.ai.busy": "Still jalan...",
  },
  en: {
    "top.tagline": "Scan Most Replayed, auto cut, clean subtitles.",
    "label.url": "YouTube URL",
    "ph.url": "https://www.youtube.com/watch?v=...",
    "help.url": "Paste a video/shorts link. Preview will show up.",
    "label.mode": "Mode",
    "opt.mode.heatmap": "Scan heatmap (Most Replayed)",
    "opt.mode.custom": "Custom start/end (manual)",
    "help.mode": "Scan = find the hottest moments. Custom = cut by your timestamps.",
    "label.ratio": "Ratio",
    "opt.ratio.9_16": "9:16 (Shorts)",
    "opt.ratio.original": "Original",
    "help.ratio": "Choose output aspect ratio. 9:16 is for Shorts/Reels/TikTok.",
    "label.crop": "Crop",
    "opt.crop.default": "Default",
    "opt.crop.split_left": "Split Left",
    "opt.crop.split_right": "Split Right",
    "help.crop": "Split is for gaming: gameplay on top, facecam below.",
    "label.padding": "Padding (seconds)",
    "help.padding": "Adds seconds before & after, so it doesn’t cut awkwardly.",
    "label.max_clips": "Max clips",
    "help.max_clips": "How many clips to generate from the heatmap.",
    "label.subtitle": "Subtitle",
    "opt.no": "No",
    "opt.yes": "Yes",
    "help.subtitle": "If Yes, audio is transcribed to text and burned into the video.",
    "label.whisper_model": "Model (Whisper)",
    "help.whisper_model": "AI model for speech-to-text. Bigger = more accurate, heavier.",
    "label.subtitle_font": "Subtitle Font",
    "opt.custom": "Custom…",
    "ph.subtitle_font_custom": "Custom font name (e.g. Poppins)",
    "help.subtitle_font": "If the font is in fonts folder, set Fonts dir = fonts.",
    "label.subtitle_location": "Subtitle Location",
    "opt.subtitle_location.bottom": "Bottom",
    "opt.subtitle_location.center": "Centered",
    "help.subtitle_location": "Bottom looks natural for Shorts. Centered is more “in your face”.",
    "label.subtitle_fontsdir": "Fonts dir (optional)",
    "help.subtitle_fontsdir": "Folder containing .ttf/.otf for subtitles. Default: project <b>fonts</b> folder.",
    "label.start": "Start (seconds or mm:ss)",
    "ph.start": "689 or 11:29",
    "label.end": "End (seconds or mm:ss)",
    "ph.end": "742 or 12:22",
    "btn.scan": "Scan Heatmap",
    "btn.clip": "Create Clip",
    "help.actions": "Scan Heatmap = fetch “Most Replayed” moments. Create Clip = download + crop + (optional) subtitles.",
    "panel.segments": "Segments",
    "btn.select_all": "Select All",
    "btn.clear": "Clear",
    "btn.create_selected": "Create Selected Clip",
    "panel.progress": "Progress",
    "js.modal.preview_segment": "Preview Segment",
    "js.modal.preview_clip": "Preview Clip",
    "js.segments.empty": "No segments yet. Click Scan Heatmap first.",
    "js.segments.empty.scanned": "Scan ran but produced no segments. Try again, or use Custom start/end mode.",
    "js.seg.score.title": "Heatmap intensity score",
    "js.seg.score.none": "No heatmap score (fallback)",
    "js.src.heatmap": "Source: YouTube Most Replayed ({markers} heatmap points, {count} moments).",
    "js.src.fallback": "Source: fallback. {reason} The segments below are evenly spaced across the video, not heatmap based.",
    "js.src.fallback.short": "Fallback",
    "js.src.heatmap.short": "Most Replayed",
    "js.preview.loading": "Loading preview…",
    "js.progress.count": "{done}/{total} done • {success} success",
    "js.selected.count": "{count} selected",
    "js.stage.download": "Download",
    "js.stage.crop": "Crop",
    "js.stage.subtitle": "Subtitle",
    "js.stage.subtitle_model_load": "Load model",
    "js.stage.subtitle_transcribe": "Transcribe",
    "js.stage.subtitle_write": "Write subtitles",
    "js.stage.burn_subtitle": "Burn subtitles",
    "js.stage.finalize": "Finalize",
    "js.stage.done_clip": "Done",
    "js.topprogress.processing": "Processing",
    "panel.ai": "AI Metadata",
    "label.ai_base_url": "AI server (base URL)",
    "help.ai_base_url": "Ollama, LM Studio, or a llama.cpp server. Only local or LAN addresses are allowed.",
    "label.ai_model": "Model",
    "help.ai_model": "Press Test server to fetch the list of available models.",
    "label.ai_api_key": "API key (optional)",
    "help.ai_api_key": "Only needed if your local server requires one. Stored in this browser only.",
    "label.ai_tone": "Writing tone",
    "help.ai_tone": "Informative, casual, energetic, or educational — applied to titles, hook, and description.",
    "label.ai_hook": "Relevant hook",
    "help.ai_hook": "Create an opening sentence relevant to the video topic.",
    "opt.ai_tone.informative": "Informative",
    "opt.ai_tone.casual": "Casual",
    "opt.ai_tone.energetic": "Energetic",
    "opt.ai_tone.educational": "Educational",
    "label.ai_timeout": "Timeout (seconds)",
    "help.ai_timeout": "Local models on CPU can be slow. Raise this if requests keep timing out.",
    "label.ai_note": "Extra instruction (optional)",
    "help.ai_note": "For example: aimed at beginners, or mention the tools used.",
    "label.ai_transcript": "Transcript (optional)",
    "help.ai_transcript": "Paste a transcript excerpt (from subtitles, an .srt, or your notes) so titles and tags are far more accurate.",
    "label.ai_titles": "Title options",
    "label.ai_description": "Description",
    "label.ai_tags": "Tags",
    "btn.ai_test": "Test server",
    "btn.ai_use_transcript": "Use transcript",
    "btn.ai_generate": "Generate metadata",
    "btn.copy": "Copy",
    "btn.copy_all": "Copy all",
    "js.ai.ready": "Ready",
    "js.ai.no_model": "Fill in the base URL and pick a model first.",
    "js.ai.need_video": "Paste a YouTube link first so the AI knows the topic.",
    "js.ai.testing": "Contacting AI server...",
    "js.ai.test_ok": "Server is up, {count} model(s) available",
    "js.ai.test_ok_empty": "Server is up, but the model list is empty. Type the model name manually.",
    "js.ai.model_missing": "Server is up, but model {model} is not in its list.",
    "js.ai.generating": "Model is thinking... this can be slow on CPU.",
    "js.ai.done": "Finished in {sec}s",
    "js.ai.partial": "The model answered incompletely, partial results are shown.",
    "js.ai.lang_warn": "Output contains characters from another language. Check before using.",
    "js.ai.copied": "Copied",
    "js.ai.copy_fail": "Copy failed. Copy manually from this box.",
    "js.ai.transcript_added": "Transcript will be used as context.",
    "js.ai.transcript_none": "The transcript box is empty. Paste a transcript excerpt first.",
    "js.ai.tr_title": "Generated title",
    "js.ai.desc_empty": "(model returned no title)",
    "js.ai.tags_empty": "(model returned no tags)",
    "js.ai.hash_empty": "(model returned no hashtags)",
    "js.ai.hash_desc_on": "Hashtags are appended to the description",
    "js.ai.hash_desc_off": "Hashtags are not appended to the description",
    "js.ai.cfg_saving": "Saving AI config...",
    "js.ai.cfg_saved": "AI config saved on the server.",
    "js.ai.cfg_saved_key": "AI config saved (including the API key on the server).",
    "js.ai.cfg_loaded": "AI config loaded from the server.",
    "js.ai.cfg_loaded_key": "AI config loaded. The stored API key is used from the server.",
    "js.ai.cfg_cleared": "AI config removed from the server.",
    "js.ai.cfg_failed": "Could not save config:",
    "btn.ai_save": "Save config",
    "btn.ai_clear_cfg": "Clear config",
    "label.ai.hashtags": "Hashtags",
    "help.ai.hashtags": "Hashtags are appended to the description and can also sit above the title. YouTube shows at most 15.",
    "js.ai.busy": "Still running...",
  },
};

let currentLang = "id";

function t(key, vars) {
  const base = I18N[currentLang] || I18N.id;
  const fallback = I18N.id || {};
  let s = base[key] ?? fallback[key] ?? key;
  if (vars && typeof s === "string") {
    Object.entries(vars).forEach(([k, v]) => {
      s = s.replaceAll(`{${k}}`, String(v));
    });
  }
  return s;
}

const TOP_PROGRESS = {
  pct: 0,
  titleBase: document.title || "YouTube Heatmap Clipper",
  hideTimer: null,
};

function clamp(n, a, b) {
  return Math.min(b, Math.max(a, n));
}

function easeOutCubic(x) {
  const t = clamp(x, 0, 1);
  return 1 - Math.pow(1 - t, 3);
}

function stageLabel(stage) {
  const key = {
    download: "js.stage.download",
    crop: "js.stage.crop",
    subtitle: "js.stage.subtitle",
    subtitle_model_load: "js.stage.subtitle_model_load",
    subtitle_transcribe: "js.stage.subtitle_transcribe",
    subtitle_write: "js.stage.subtitle_write",
    burn_subtitle: "js.stage.burn_subtitle",
    finalize: "js.stage.finalize",
    done_clip: "js.stage.done_clip",
  }[stage];
  return key ? t(key) : stage || "";
}

function computeJobPct(job) {
  if (!job) return { pct: 0, text: "", active: false };
  const status = job.status || "";
  if (status !== "running" && status !== "queued") {
    const done = Number(job.done || 0);
    const total = Number(job.total || 0);
    const pct = total > 0 ? clamp((done / total) * 100, 0, 100) : 0;
    return { pct, text: "", active: false };
  }

  const total = Math.max(1, Number(job.total || 1));
  const done = clamp(Number(job.done || 0), 0, total);
  const subtitleEnabled = Boolean(job.subtitle_enabled);
  const stage = job.stage || "";
  const stageAt = job.stage_at ? Number(job.stage_at) : 0;
  const elapsed = stageAt ? Date.now() - stageAt : 0;
  const clipIndexRaw = Number(job.stage_clip || job.current || (done + 1) || 1);
  const clipIndex = clamp(clipIndexRaw, 1, total);

  const mapNoSub = {
    download: { a: 0.04, b: 0.62, d: 14000 },
    crop: { a: 0.62, b: 0.96, d: 9000 },
    finalize: { a: 0.96, b: 0.995, d: 2500 },
    done_clip: { a: 1, b: 1, d: 0 },
  };
  const mapSub = {
    download: { a: 0.03, b: 0.55, d: 14000 },
    crop: { a: 0.55, b: 0.86, d: 9000 },
    subtitle: { a: 0.86, b: 0.87, d: 1200 },
    subtitle_model_load: { a: 0.87, b: 0.885, d: 2500 },
    subtitle_transcribe: { a: 0.885, b: 0.93, d: 20000 },
    subtitle_write: { a: 0.93, b: 0.94, d: 1800 },
    burn_subtitle: { a: 0.94, b: 0.985, d: 12000 },
    finalize: { a: 0.985, b: 0.995, d: 2500 },
    done_clip: { a: 1, b: 1, d: 0 },
  };

  const table = subtitleEnabled ? mapSub : mapNoSub;
  const s = table[stage] || (subtitleEnabled ? mapSub.download : mapNoSub.download);
  const within = s.d > 0 ? s.a + (s.b - s.a) * easeOutCubic(clamp(elapsed / s.d, 0, 0.98)) : s.a;
  const pctBase = ((clipIndex - 1) + within) / total * 100;
  const pctFloor = (done / total) * 100;
  const pct = clamp(Math.max(pctBase, pctFloor), 0, 99.5);

  const clipText = total > 0 ? `clip ${clipIndex}/${total}` : "";
  const sLabel = stageLabel(stage);
  const text = [t("js.topprogress.processing"), clipText, sLabel].filter(Boolean).join(" • ");
  return { pct, text, active: true };
}

function renderTopProgress(job) {
  const wrap = $("topProgressWrap");
  const bar = $("topProgressBar");
  const textEl = $("topProgressText");
  if (!wrap || !bar || !textEl) return;

  const { pct, text, active } = computeJobPct(job);

  if (!active) {
    if (job && (job.status === "done" || job.status === "error")) {
      bar.style.width = "100%";
      textEl.textContent = job.status === "error" ? "Error" : "";
      wrap.classList.remove("hide");
      clearTimeout(TOP_PROGRESS.hideTimer);
      TOP_PROGRESS.hideTimer = setTimeout(() => {
        wrap.classList.add("hide");
        bar.style.width = "0%";
        textEl.textContent = "";
      }, 650);
      document.title = TOP_PROGRESS.titleBase;
      TOP_PROGRESS.pct = 0;
      return;
    }
    wrap.classList.add("hide");
    bar.style.width = "0%";
    textEl.textContent = "";
    document.title = TOP_PROGRESS.titleBase;
    TOP_PROGRESS.pct = 0;
    return;
  }

  clearTimeout(TOP_PROGRESS.hideTimer);
  wrap.classList.remove("hide");
  TOP_PROGRESS.pct = Math.max(TOP_PROGRESS.pct, pct);
  bar.style.width = `${TOP_PROGRESS.pct.toFixed(1)}%`;
  textEl.textContent = text;
  document.title = `${TOP_PROGRESS.titleBase} (${Math.round(TOP_PROGRESS.pct)}%)`;
}

function applyI18n() {
  document.documentElement.lang = currentLang;
  $("langId")?.classList.toggle("isActive", currentLang === "id");
  $("langEn")?.classList.toggle("isActive", currentLang === "en");

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.dataset.i18n;
    if (!key) return;
    el.innerHTML = t(key);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.dataset.i18nPlaceholder;
    if (!key) return;
    el.setAttribute("placeholder", t(key));
  });
}

function setLang(lang) {
  currentLang = lang === "en" ? "en" : "id";
  localStorage.setItem("lang", currentLang);
  applyI18n();
  renderSegments(lastScanSegments);
  updateSelectedUi();
  if (typeof aiRetranslate === "function") aiRetranslate();
}

function fmtTime(s) {
  const sec = Math.max(0, Math.floor(Number(s) || 0));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const r = sec % 60;
  if (h > 0) return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return data;
}


// ---------------------------------------------------------------------------
// Panel AI Metadata (judul, deskripsi, tag) lewat LLM lokal
// ---------------------------------------------------------------------------

const AI_LS_KEY = "yhc.ai.settings";
let aiBusy = false;
let aiMetaData = { titles: [], description: "", tags: [], hashtags: [] };
// Apakah baris hashtag ditempel di akhir deskripsi.
let aiHashInDesc = true;
let aiTranscript = "";

function aiLoadSettings() {
  try {
    const raw = JSON.parse(localStorage.getItem(AI_LS_KEY) || "{}");
    return raw && typeof raw === "object" ? raw : {};
  } catch (e) {
    return {};
  }
}

function aiCollectSettings() {
  return {
    base_url: $("aiBaseUrl").value.trim(),
    model: $("aiModel").value.trim(),
    api_key: $("aiApiKey").value,
    tone: $("aiTone").value,
    include_hook: $("aiHook").checked,
    timeout: Number($("aiTimeout").value) || 600,
    note: $("aiNote").value.trim(),
    transcript: aiTranscript || "",
    options: {
      hashtags_in_description: aiHashInDesc !== false,
    },
  };
}

function aiSaveSettings() {
  const payload = aiCollectSettings();
  try {
    // API key sengaja tidak ditulis ke localStorage. Kalau browser dipakai
    // di komputer bersama, kunci tidak ikut bocor lewat storage; key yang
    // sudah disimpan tetap ada di file config server.
    const untukBrowser = { ...payload };
    delete untukBrowser.api_key;
    localStorage.setItem(AI_LS_KEY, JSON.stringify(untukBrowser));
  } catch (e) {
    // Penyimpanan penuh atau ditolak browser: bukan kondisi fatal.
  }
  return payload;
}

async function aiSaveConfigServer() {
  // Config disimpan di server, bukan hanya localStorage: aplikasi portable
  // memakai find_free_port(), jadi kalau port 5000 dipakai, browser pindah
  // origin dan localStorage ikut hilang. Config di server tetap ada.
  aiSaveSettings();
  const st = $("aiConfigStatus");
  st.textContent = t("js.ai.cfg_saving");
  try {
    const res = await fetch("/api/ai/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(aiCollectSettings()),
    });
    const j = await res.json();
    if (!res.ok || !j.ok) throw new Error(j.error || res.statusText);
    st.textContent = j.config && j.config.has_api_key
      ? t("js.ai.cfg_saved_key")
      : t("js.ai.cfg_saved");
  } catch (e) {
    st.textContent = t("js.ai.cfg_failed") + " " + (e.message || e);
  }
}

async function aiClearConfigServer() {
  const st = $("aiConfigStatus");
  st.textContent = t("js.ai.cfg_saving");
  try {
    const res = await fetch("/api/ai/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reset: true }),
    });
    if (!res.ok) throw new Error(res.statusText);
    try { localStorage.removeItem(AI_LS_KEY); } catch (e) { /* abaikan */ }
    $("aiApiKey").value = "";
    $("aiConfigStatus").textContent = t("js.ai.cfg_cleared");
  } catch (e) {
    st.textContent = t("js.ai.cfg_failed") + " " + (e.message || e);
  }
}

async function aiRestoreConfigFromServer() {
  // Isi form dari config tersimpan server. localStorage tetap jadi fallback
  // supaya tetap jalan kalau endpoint config tidak tersedia.
  try {
    const res = await fetch("/api/ai/config");
    if (!res.ok) return false;
    const j = await res.json();
    const c = (j && j.config) || {};
    if (!Object.keys(c).length) return false;
    if (c.base_url) $("aiBaseUrl").value = c.base_url;
    if (c.model) $("aiModel").value = c.model;
    if (c.tone) $("aiTone").value = c.tone;
    if (typeof c.include_hook === "boolean") $("aiHook").checked = c.include_hook;
    if (c.timeout) $("aiTimeout").value = c.timeout;
    if (c.note) $("aiNote").value = c.note;
    if (typeof c.transcript === "string" && c.transcript) {
      $("aiTranscript").value = c.transcript;
    }
    if (typeof c.hashtags_in_description === "boolean") {
      aiHashInDesc = c.hashtags_in_description;
    }
    const chk = $("aiHashInDesc");
    if (chk) {
      chk.checked = aiHashInDesc;
      const label = chk.parentElement?.querySelector("span");
      if (label) label.textContent = t(aiHashInDesc ? "js.ai.hash_desc_on" : "js.ai.hash_desc_off");
    }
    // API key sengaja tidak dikirim balik ke browser. Kalau ada key
    // tersimpan, kolom dikosongkan dan server yang tetap memakainya.
    $("aiConfigStatus").textContent = c.has_api_key
      ? t("js.ai.cfg_loaded_key")
      : t("js.ai.cfg_loaded");
    return true;
  } catch (e) {
    return false;
  }
}

function aiRestoreSettings() {
  const s = aiLoadSettings();
  $("aiBaseUrl").value = s.base_url || "";
  $("aiModel").value = s.model || "";
  $("aiApiKey").value = s.api_key || "";
  $("aiNote").value = s.note || "";
  $("aiHook").checked = s.include_hook !== false;
  $("aiTimeout").value = s.timeout || 600;
  if (s.tone) $("aiTone").value = s.tone;
}

// Teks status dan hint disimpan sebagai kunci i18n juga, supayaPergantian
// bahasa di tengah sesi tidak meninggalkan panel dalam bahasa lama.
let aiStatusKey = "";
let aiStatusVars = null;
let aiStatusKind = "";
let aiHintKey = "";
let aiHintVars = null;
let aiHintKind = "";

function aiSetStatus(text, kind, key, vars) {
  aiStatusKey = key || "";
  aiStatusVars = vars || null;
  aiStatusKind = kind || "";
  const el = $("aiStatus");
  el.textContent = text || "";
  el.classList.remove("isOk", "isErr", "isBusy");
  if (kind) el.classList.add("is" + kind);
}

function aiSetHint(text, kind, key, vars) {
  aiHintKey = key || "";
  aiHintVars = vars || null;
  aiHintKind = kind || "";
  const el = $("aiHint");
  el.textContent = text || "";
  el.classList.remove("isOk", "isErr", "isBusy", "aiHintShow");
  if (text) el.classList.add("aiHintShow");
  if (kind) el.classList.add("is" + kind);
}

function aiRetranslate() {
  if (aiStatusKey) aiSetStatus(t(aiStatusKey, aiStatusVars), aiStatusKind, aiStatusKey, aiStatusVars);
  if (aiHintKey) aiSetHint(t(aiHintKey, aiHintVars), aiHintKind, aiHintKey, aiHintVars);
  if (aiMetaData.titles.length || aiMetaData.tags.length) aiRenderResult(aiMetaData);
  aiSetBusy(aiBusy);
}

function aiSetBusy(on, label) {
  aiBusy = !!on;
  $("aiGenerateBtn").disabled = aiBusy;
  $("aiTestBtn").disabled = aiBusy;
  $("aiUseTranscript").disabled = aiBusy;
  $("aiGenerateBtn").textContent = aiBusy
    ? t("js.ai.busy")
    : t("btn.ai_generate");
  if (on) aiSetStatus(label || t("js.ai.generating"), "Busy", "js.ai.generating");
}

function aiCollectPayload() {
  const s = aiSaveSettings();
  return {
    base_url: s.base_url,
    model: s.model,
    api_key: s.api_key,
    url: $("url").value.trim(),
    segments: (lastScanSegments || []).map((seg) => ({
      label: seg.label || "",
      score: seg.score ?? null,
    })),
    transcript: aiTranscript,
    options: {
      lang: currentLang,
      tone: s.tone,
      note: s.note,
      include_hook: s.include_hook,
      timeout: s.timeout,
      n_titles: 3,
      hashtags_in_description: s.options.hashtags_in_description !== false,
    },
  };
}

function aiFillModelList(models) {
  const list = $("aiModelList");
  list.innerHTML = "";
  (models || []).forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    list.appendChild(opt);
  });
}

function aiRenderResult(meta) {
  aiMetaData = {
    titles: Array.isArray(meta.titles) ? meta.titles : [],
    hook: meta.hook || "",
    description: meta.description || "",
    tags: Array.isArray(meta.tags) ? meta.tags : [],
    hashtags: Array.isArray(meta.hashtags)
      ? meta.hashtags
      : (typeof meta.hashtags === "string" ? meta.hashtags.split(/[\s,]+/).filter(Boolean) : []),
  };

  const box = $("aiTitles");
  box.innerHTML = "";
  if (aiMetaData.titles.length) {
    aiMetaData.titles.forEach((title, i) => {
      const row = document.createElement("div");
      row.className = "aiTitleRow";
      const label = document.createElement("span");
      label.className = "aiTitleLabel";
      label.textContent = t("js.ai.tr_title") + " " + (i + 1);
      const val = document.createElement("span");
      val.className = "aiTitleText";
      val.textContent = title;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn ghost smallBtn";
      btn.textContent = t("btn.copy");
      btn.addEventListener("click", () => aiCopy(title, btn));
      row.append(label, val, btn);
      box.appendChild(row);
    });
  } else {
    box.innerHTML = '<div class="aiEmpty">' + t("js.ai.desc_empty") + "</div>";
  }

  $("aiHookText").value = aiMetaData.hook || "";
  $("aiDescription").value = aiMetaData.description || "";

  const tagBox = $("aiTags");
  tagBox.innerHTML = "";
  if (aiMetaData.tags.length) {
    aiMetaData.tags.forEach((tag) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "aiTag";
      chip.textContent = tag;
      chip.title = t("btn.copy");
      chip.addEventListener("click", () => aiCopy(tag, chip));
      tagBox.appendChild(chip);
    });
  } else {
    tagBox.innerHTML = '<div class="aiEmpty">' + t("js.ai.tags_empty") + "</div>";
  }
  $("aiTagsRaw").value = aiMetaData.tags.join(", ");

  // Hashtag ditampilkan terpisah supaya jelas ini tidak sama dengan tag,
  // dan bisa disalin tanpa mengambil baris hashtag di dalam deskripsi.
  const hashBox = $("aiHashtags");
  hashBox.innerHTML = "";
  if (aiMetaData.hashtags.length) {
    aiMetaData.hashtags.forEach((tag) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "aiTag hash";
      chip.textContent = tag;
      chip.title = t("btn.copy");
      chip.addEventListener("click", () => aiCopy(tag, chip));
      hashBox.appendChild(chip);
    });
  } else {
    hashBox.innerHTML = '<div class="aiEmpty">' + t("js.ai.hash_empty") + "</div>";
  }
  $("aiHashtagCount").textContent = aiMetaData.hashtags.length + " / 15";

  $("aiDescCount").textContent = aiMetaData.description.length + " / 5000";
  const tagChars = aiMetaData.tags.reduce((a, b) => a + b.length + 1, 0);
  $("aiTagCount").textContent =
    aiMetaData.tags.length + " / 30" + (tagChars ? " · " + tagChars + " / 500" : "");

  $("aiResult").classList.remove("hide");
}

function aiRenderIdle() {
  aiMetaData = { titles: [], hook: "", description: "", tags: [], hashtags: [] };
  $("aiTitles").innerHTML = "";
  $("aiTags").innerHTML = "";
  $("aiHashtags").innerHTML = "";
  $("aiTagsRaw").value = "";
  $("aiDescription").value = "";
  $("aiDescCount").textContent = "";
  $("aiTagCount").textContent = "";
  $("aiHashtagCount").textContent = "";
  $("aiResult").classList.add("hide");
}

async function aiCopy(text, btn) {
  const original = btn ? btn.textContent : "";
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      // Fallback untuk konteks non-HTTPS (app lokal dibuka lewat LAN/file).
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      if (!ok) throw new Error("execCommand gagal");
    }
    if (btn) {
      btn.textContent = t("js.ai.copied");
      setTimeout(() => {
        btn.textContent = original;
      }, 1200);
    }
    aiSetHint(t("js.ai.copied"), "Ok", "js.ai.copied");
    setTimeout(() => aiSetHint(""), 2000);
  } catch (e) {
    aiSetHint(t("js.ai.copy_fail"), "Err", "js.ai.copy_fail");
  }
}

function aiTitlesAsText() {
  return aiMetaData.titles.join("\n");
}

function aiTagsAsText() {
  return aiMetaData.tags.join(", ");
}

function aiHashtagsAsText() {
  // Hashtag dipakai apa adanya (sudah diawali #) dan dipisah spasi, karena
  // itu bentuk yang ditempel di deskripsi YouTube.
  return aiMetaData.hashtags.join(" ");
}

async function aiTestServer() {
  if (aiBusy) return;
  const s = aiSaveSettings();
  if (!s.base_url || !s.model) {
    aiSetHint(t("js.ai.no_model"), "Err", "js.ai.no_model");
    return;
  }
  aiSetBusy(true, t("js.ai.testing"));
  aiSetHint("");
  try {
    const data = await postJson("/api/ai/probe", {
      base_url: s.base_url,
      model: s.model,
      api_key: s.api_key,
      options: { timeout: 20 },
    });
    aiFillModelList(data.models);
    if (data.model_found === false) {
      aiSetHint(t("js.ai.model_missing", { model: s.model }), "Err", "js.ai.model_missing", { model: s.model });
      aiSetStatus(t("js.ai.test_ok", { count: data.count || 0 }), "Err", "js.ai.test_ok", { count: data.count || 0 });
    } else if (!data.models || !data.models.length) {
      aiSetHint(t("js.ai.test_ok_empty"), "Ok", "js.ai.test_ok_empty");
      aiSetStatus(t("js.ai.test_ok", { count: 0 }), "Ok", "js.ai.test_ok", { count: 0 });
    } else {
      aiSetHint("");
      aiSetStatus(t("js.ai.test_ok", { count: data.count }), "Ok", "js.ai.test_ok", { count: data.count });
    }
  } catch (e) {
    aiSetHint(e.message, "Err");
    aiSetStatus("", "Err");
  } finally {
    aiSetBusy(false);
  }
}

async function aiGenerate() {
  if (aiBusy) return;
  const s = aiSaveSettings();
  if (!s.base_url || !s.model) {
    aiSetHint(t("js.ai.no_model"), "Err", "js.ai.no_model");
    return;
  }
  // Konteks bisa datang dari link YouTube ATAU dari transkrip yang diketik
  // sendiri. Jangan lebih ketat dari server: user yang sudah menempel
  // transkrip tetap berhak generate.
  if (!currentPreview && !$("url").value.trim() && !aiTranscript) {
    aiSetHint(t("js.ai.need_video"), "Err", "js.ai.need_video");
    return;
  }
  aiSetBusy(true, t("js.ai.generating"));
  aiSetHint("");
  try {
    const data = await postJson("/api/ai/generate", aiCollectPayload());
    const meta = data.meta || {};
    aiRenderResult(meta);
    const sec = meta.elapsed || 0;
    const lengkap = meta.partial === false;
    aiSetStatus(t("js.ai.done", { sec }), lengkap ? "Ok" : "Err", "js.ai.done", { sec });
    if (!lengkap) aiSetHint(t("js.ai.partial"), "Err", "js.ai.partial");
    // Model kecil kadang menjawab dengan aksara lain (Mandarin, Korea,
    // Jepang). Isi jawaban tetap ditampilkan apa adanya - user yang
    // menilai - tapi diberi tahu supaya tidak ikut ter-paste ke YouTube.
    const langWarn = meta.language && meta.language.ok === false
      ? meta.language.message : "";
    if (langWarn) {
      aiSetHint(langWarn, "Err", langWarn);
      aiSetStatus(t("js.ai.lang_warn"), "Err", "js.ai.lang_warn");
    }
  } catch (e) {
    aiSetHint(e.message, "Err");
    aiSetStatus("", "Err");
  } finally {
    aiSetBusy(false);
  }
}

function aiReadTranscriptBox() {
  const el = $("aiTranscript");
  const text = (el ? el.value : "").trim();
  if (!text) {
    aiSetHint(t("js.ai.transcript_none"), "Err", "js.ai.transcript_none");
    return;
  }
  aiTranscript = text.slice(0, 6000);
  aiSetHint(t("js.ai.transcript_added"), "Ok", "js.ai.transcript_added");
}

function openModal(title, bodyEl) {
  $("modalTitle").textContent = title || "";
  const root = $("modalBody");
  root.innerHTML = "";
  root.appendChild(bodyEl);
  $("modal").classList.remove("hide");
}

function closeModal() {
  $("modal").classList.add("hide");
  $("modalBody").innerHTML = "";
}

function debounce(fn, wait) {
  let t = null;
  return (...args) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

function readPayload() {
  const fontSel = $("subtitle_font_select").value;
  const fontCustom = ($("subtitle_font_custom").value || "").trim();
  const subtitleFont = fontSel === "custom" ? fontCustom : fontSel;
  return {
    url: $("url").value,
    mode: $("mode").value,
    ratio: $("ratio").value,
    crop: $("crop").value,
    padding: Number($("padding").value || 0),
    max_clips: Number($("max_clips").value || 6),
    subtitle: $("subtitle").value === "y",
    whisper_model: $("whisper_model").value,
    subtitle_font: subtitleFont,
    subtitle_location: $("subtitle_location").value,
    subtitle_fontsdir: $("subtitle_fontsdir").value || "",
    start: $("start").value || "",
    end: $("end").value || "",
  };
}

function setBusy(busy) {
  $("scanBtn").disabled = busy;
  $("clipBtn").disabled = busy;
  $("segSelectAllBtn").disabled = busy;
  $("segClearBtn").disabled = busy;
  $("segCreateBtn").disabled = busy || selectedKeys.size === 0;
}

function getVideoThumb(videoId, fallback) {
  if (!videoId) return fallback || "";
  return `https://i.ytimg.com/vi_webp/${videoId}/hqdefault.webp`;
}

function openYouTubePreview(videoId, startSec, endSec, title) {
  const start = Math.max(0, Math.floor(Number(startSec) || 0));
  const end = Math.max(0, Math.floor(Number(endSec) || 0));
  const url = `https://www.youtube.com/embed/${encodeURIComponent(videoId)}?start=${start}${end > start ? `&end=${end}` : ""}&autoplay=1&playsinline=1&rel=0`;
  const iframe = document.createElement("iframe");
  iframe.className = "embed";
  iframe.src = url;
  iframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
  iframe.allowFullscreen = true;
  openModal(title || t("js.modal.preview_segment"), iframe);
}

function openClipPreview(title, src) {
  const v = document.createElement("video");
  v.className = "video";
  v.controls = true;
  v.autoplay = true;
  v.muted = true;
  v.playsInline = true;
  v.src = src;
  openModal(title || t("js.modal.preview_clip"), v);
}

function segKey(seg) {
  const start = Math.round(Number(seg.start || 0) * 1000);
  const dur = Math.round(Number(seg.duration || 0) * 1000);
  return `${start}:${dur}`;
}

function setSegControlsVisible(visible) {
  $("segControls").classList.toggle("hide", !visible);
}

function updateSelectedUi() {
  const count = selectedKeys.size;
  $("segSelectedMeta").textContent = count > 0 ? t("js.selected.count", { count }) : "";
  $("segCreateBtn").disabled = count === 0 || $("scanBtn").disabled;
  setSegControlsVisible($("mode").value === "heatmap" && lastScanSegments.length > 0);
}

function selectAllSegments() {
  selectedKeys = new Set(lastScanSegments.map(segKey));
  renderSegments(lastScanSegments);
  updateSelectedUi();
}

function clearSelectedSegments() {
  selectedKeys = new Set();
  renderSegments(lastScanSegments);
  updateSelectedUi();
}

async function clipSelected() {
  if ($("mode").value !== "heatmap") return;
  if (selectedKeys.size === 0) return;
  setBusy(true);
  try {
    const payload = readPayload();
    const picked = lastScanSegments.filter((s) => selectedKeys.has(segKey(s)));
    const data = await postJson("/api/clip", { ...payload, segments: picked });
    const jobId = data.job_id;
    await pollJob(jobId);
  } catch (e) {
    renderProgress({ status: "error", error: e.message, total: 0, done: 0, id: "" });
  } finally {
    setBusy(false);
    updateSelectedUi();
  }
}

function renderSegments(segments, scanned) {
  const root = $("segments");
  root.innerHTML = "";
  if (!segments || segments.length === 0) {
    const key = scanned ? "js.segments.empty.scanned" : "js.segments.empty";
    root.innerHTML = `<div class="small">${t(key)}</div>`;
    updateSelectedUi();
    return;
  }
  segments.forEach((s, idx) => {
    const start = Number(s.start || 0);
    const dur = Number(s.duration || 0);
    const end = start + dur;
    const score = Number(s.score || 0);
    const el = document.createElement("div");
    el.className = "seg";
    const key = segKey(s);
    if (selectedKeys.has(key)) el.classList.add("selected");
    const thumb = getVideoThumb(currentVideoId, currentPreview?.thumbnail);
    el.innerHTML = `
      <div class="segThumb">
        <img alt="" src="${thumb}" />
        <div class="segTime">${fmtTime(start)}</div>
      </div>
      <div class="segMain">
        <div class="t">#${idx + 1} ${fmtTime(start)} → ${fmtTime(end)}</div>
        <div class="m">durasi ${Math.round(dur)}s</div>
      </div>
      <div class="segSide">
        <div class="pill${score > 0 ? "" : " noScore"}" title="${score > 0 ? t("js.seg.score.title") : t("js.seg.score.none")}">${score > 0 ? score.toFixed(2) : "\u2014"}</div>
        <button class="btn ghost smallBtn" type="button" data-preview="1">Preview</button>
      </div>
    `;
    el.addEventListener("click", (ev) => {
      const target = ev.target;
      if (target && target.dataset && target.dataset.preview) {
        ev.preventDefault();
        ev.stopPropagation();
        if (currentVideoId) openYouTubePreview(currentVideoId, start, end, currentPreview?.title || "Preview Segment");
        return;
      }
      if ($("mode").value === "custom") {
        $("start").value = Math.floor(start);
        $("end").value = Math.floor(end);
        return;
      }
      if (selectedKeys.has(key)) selectedKeys.delete(key);
      else selectedKeys.add(key);
      el.classList.toggle("selected");
      updateSelectedUi();
    });
    root.appendChild(el);
  });
  updateSelectedUi();
}

function renderProgress(job) {
  const root = $("progress");
  const meta = $("jobMeta");
  const out = $("outputs");
  root.innerHTML = "";
  out.innerHTML = "";
  meta.textContent = "";
  if (!job) return;
  renderTopProgress(job);
  const total = Number(job.total || 0);
  const done = Number(job.done || 0);
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  const stage = stageLabel(job.stage || "");
  meta.textContent = `${job.status} • ${(job.status_text || "").trim()}${stage ? " • " + stage : ""}`.trim();

  const bar = document.createElement("div");
  bar.innerHTML = `<div class="bar"><div style="width:${pct}%"></div></div>`;
  root.appendChild(bar);

  const line = document.createElement("div");
  line.className = "small";
  line.textContent =
    total > 0
      ? t("js.progress.count", { done, total, success: job.success || 0 })
      : "";
  root.appendChild(line);

  if (job.status === "error") {
    const err = document.createElement("div");
    err.className = "small";
    err.textContent = job.error || "error";
    root.appendChild(err);
  }

  if (Array.isArray(job.outputs) && job.outputs.length > 0) {
    job.outputs.forEach((f) => {
      const el = document.createElement("div");
      el.className = "out";
      const nama = encodeURIComponent(f.name);
      // Route terpisah: /clips/ untuk diputar (inline), /download/ untuk
      // diunduh. Kalau keduanya pakai route yang sama, header
      // Content-Disposition: attachment bikin <video> gagal memutar.
      const playHref = `/clips/${job.id}/${nama}`;
      const dlHref = `/download/${job.id}/${nama}`;
      el.innerHTML = `
        <div class="outLeft">
          <a href="${playHref}" target="_blank" rel="noreferrer">${f.name}</a>
          <div class="small">${Math.round((f.size || 0) / 1024)} KB</div>
        </div>
        <div class="outRight">
          <button class="btn ghost smallBtn" type="button" data-play="1">Play</button>
          <a class="btn smallBtn" href="${dlHref}" download>Download</a>
        </div>
      `;
      el.querySelector("[data-play]")?.addEventListener("click", (ev) => {
        ev.preventDefault();
        openClipPreview(f.name, playHref);
      });
      out.appendChild(el);
    });
  }
}

let lastScanSegments = [];
let lastPreviewUrl = "";
let currentPreview = null;
let currentVideoId = "";
let selectedKeys = new Set();

function renderScanSource(data, count) {
  const box = $("segSource");
  if (!box) return;
  const source = (data && data.source) || "";
  if (!source || source === "none" || !count) {
    box.classList.add("hide");
    box.textContent = "";
    return;
  }
  if (source === "heatmap") {
    box.textContent = t("js.src.heatmap", {
      markers: Number(data.markers || 0),
      count,
    });
    box.classList.remove("fallback");
  } else {
    box.textContent = t("js.src.fallback", {
      reason: (data && data.detail) || "",
    });
    box.classList.add("fallback");
  }
  box.classList.remove("hide");
}

async function scan() {
  setBusy(true);
  try {
    const { url, max_clips } = readPayload();
    const data = await postJson("/api/scan", { url, max_clips });
    lastScanSegments = data.segments || [];
    selectedKeys = new Set();
    currentVideoId = data.video_id || currentVideoId;
    $("segMeta").textContent = `${lastScanSegments.length} segments • durasi ~${fmtTime(data.duration || 0)}`;
    renderScanSource(data, lastScanSegments.length);
    renderSegments(lastScanSegments, true);
  } catch (e) {
    $("segMeta").textContent = e.message;
    renderScanSource(null, 0);
    renderSegments([], true);
  } finally {
    setBusy(false);
    updateSelectedUi();
  }
}

async function preview() {
  const url = $("url").value.trim();
  if (!url || url === lastPreviewUrl) return;
  lastPreviewUrl = url;
  const box = $("preview");
  const title = $("pvTitle");
  const sub = $("pvSub");
  const img = $("thumbImg");
  try {
    title.textContent = t("js.preview.loading");
    sub.textContent = "";
    img.removeAttribute("src");
    box.classList.remove("hide");
    const data = await postJson("/api/preview", { url });
    const p = data.preview || {};
    currentPreview = p;
    if (p.id) currentVideoId = p.id;
    title.textContent = p.title || "Untitled";
    const dur = p.duration != null ? fmtTime(p.duration) : "";
    const uploader = p.uploader || "";
    sub.textContent = [uploader, dur].filter(Boolean).join(" • ");
    if (p.thumbnail) img.src = p.thumbnail;
  } catch (e) {
    box.classList.add("hide");
  }
}

async function clip() {
  setBusy(true);
  try {
    const payload = readPayload();
    const data = await postJson("/api/clip", payload);
    const jobId = data.job_id;
    await pollJob(jobId);
  } catch (e) {
    renderProgress({ status: "error", error: e.message, total: 0, done: 0, id: "" });
  } finally {
    setBusy(false);
  }
}

async function pollJob(jobId) {
  const started = Date.now();
  while (true) {
    const res = await fetch(`/api/job/${jobId}`);
    const data = await res.json().catch(() => null);
    if (!data || !data.ok) throw new Error("Job not found");
    renderProgress(data.job);
    if (data.job.status === "done" || data.job.status === "error") return;
    if (Date.now() - started > 1000 * 60 * 30) throw new Error("Timeout");
    await new Promise((r) => setTimeout(r, 1500));
  }
}

function toggleMode() {
  const isCustom = $("mode").value === "custom";
  $("customBox").classList.toggle("hide", !isCustom);
  $("scanBtn").classList.toggle("hide", isCustom);
  if (isCustom) {
    setSegControlsVisible(false);
    $("segSelectedMeta").textContent = "";
  } else {
    setSegControlsVisible(lastScanSegments.length > 0);
    updateSelectedUi();
  }
}

function toggleFont() {
  const isCustom = $("subtitle_font_select").value === "custom";
  $("subtitle_font_custom").classList.toggle("hide", !isCustom);
}

$("mode").addEventListener("change", toggleMode);
$("subtitle_font_select").addEventListener("change", toggleFont);
$("url").addEventListener("input", debounce(preview, 500));
$("scanBtn").addEventListener("click", scan);
$("clipBtn").addEventListener("click", clip);
$("segSelectAllBtn").addEventListener("click", selectAllSegments);
$("segClearBtn").addEventListener("click", clearSelectedSegments);
$("segCreateBtn").addEventListener("click", clipSelected);
$("modalClose").addEventListener("click", closeModal);
$("aiTestBtn").addEventListener("click", aiTestServer);
$("aiGenerateBtn").addEventListener("click", aiGenerate);
$("aiUseTranscript").addEventListener("click", aiReadTranscriptBox);
$("aiSaveBtn").addEventListener("click", aiSaveConfigServer);
$("aiHashInDesc")?.addEventListener("change", (e) => {
  aiHashInDesc = e.target.checked;
  const label = e.target.parentElement?.querySelector("span");
  if (label) label.textContent = t(aiHashInDesc ? "js.ai.hash_desc_on" : "js.ai.hash_desc_off");
  aiSaveSettings();
});
$("aiClearCfgBtn").addEventListener("click", aiClearConfigServer);
["aiBaseUrl", "aiModel", "aiTone", "aiTimeout", "aiNote", "aiApiKey"].forEach((id) => {
  $(id)?.addEventListener("change", () => { aiSaveSettings(); aiSetStatus(""); });
});
// Kolom API key tidak ikut auto-save ke localStorage: tidak ada alasan
// menyalin kunci ke storage browser kalau sudah aman di server.
$("aiApiKey")?.addEventListener("input", () => aiSetStatus(""));
// Kolom API key tidak ikut auto-save ke localStorage: tidak perlu menyalin
// kunci ke storage browser karena sudah aman di file config server.
document.querySelectorAll("[data-copy]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const src = btn.dataset.copy;
    const text = src === "aiTitles"
      ? aiTitlesAsText()
      : src === "aiDescription"
        ? ($("aiDescription").value || "")
        : src === "aiHashtags"
          ? aiHashtagsAsText()
          : aiTagsAsText();
    aiCopy(text, btn);
  });
});

$("modalBackdrop").addEventListener("click", closeModal);
$("langId")?.addEventListener("click", () => setLang("id"));
$("langEn")?.addEventListener("click", () => setLang("en"));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});

currentLang = localStorage.getItem("lang") || document.documentElement.lang || "id";
currentLang = currentLang === "en" ? "en" : "id";
applyI18n();
toggleMode();
toggleFont();
renderSegments([]);
aiRestoreSettings();
aiRenderIdle();
// Config server adalah sumber utama; localStorage hanya fallback supaya
// form tidak kosong kalau endpoint config gagal dijangkau.
aiRestoreConfigFromServer().then((ok) => {
  if (!ok && $("aiConfigStatus")) $("aiConfigStatus").textContent = "";
});
