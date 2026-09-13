/**
 * OpenCore Studio — Desktop Application Client Logic
 */

document.addEventListener("DOMContentLoaded", () => {
  // Global State
  const state = {
    profiles: [],
    currentProfileId: "intel_comet_lake",
    currentProfile: null,
    kextCatalog: [],
    selectedKexts: new Set(["Lilu", "VirtualSMC", "SMCProcessor", "SMCSuperIO", "WhateverGreen", "AppleALC", "IntelMausi"]),
    quirks: {
      Booter: {},
      Kernel: {},
      ACPI: {},
      UEFI: {}
    },
    bootArgs: "-v keepsyms=1 debug=0x100 alcid=1",
    smbios: {
      model: "iMac20,1",
      serial: "",
      mlb: "",
      uuid: "",
      rom: ""
    },
    amdCoreCount: 8,
    repos: [],
    latestXml: "",
    validationResults: [],
    schemaQuirks: { ACPI: {}, Booter: {}, Kernel: {}, UEFI: {} },
    updateStatus: null,
    gpus: [],
    gpuId: "",
    cpuFilter: "",
    suggestedProfileId: "",
    macosInstallers: [],
    selectedMacosId: "",
    currentTab: "wizard",
    visitedTabs: new Set(["wizard"]),
    wizardTouched: false,
    efiReady: false
  };

  const STEPS = [
    { id: "wizard", title: "Hardware", hint: "CPU" },
    { id: "kexts", title: "Kexts", hint: "Pick" },
    { id: "quirks", title: "Quirks", hint: "Args" },
    { id: "smbios", title: "SMBIOS", hint: "IDs" },
    { id: "repos", title: "Updates", hint: "Extra" },
    { id: "preview", title: "Plist", hint: "XML" },
    { id: "usb", title: "EFI", hint: "USB" }
  ];

  const SESSION_KEY = "ocs-session-v1";

  // DOM Elements
  const tabPanes = document.querySelectorAll(".tab-pane");
  const profilesContainer = document.getElementById("profiles-list");
  const activeProfileBadge = document.getElementById("active-profile-badge");
  const kextCardsContainer = document.getElementById("kext-cards-container");
  const kextCountBadge = document.getElementById("kext-count-badge");
  const kextSearch = document.getElementById("kext-search");
  const kextCatButtons = document.querySelectorAll("#kext-categories .pill-btn");
  
  const booterQuirksList = document.getElementById("booter-quirks-list");
  const kernelQuirksList = document.getElementById("kernel-quirks-list");
  const miscQuirksList = document.getElementById("misc-quirks-list");
  
  const bootArgsInput = document.getElementById("custom-boot-args");
  const bootArgsChips = document.querySelectorAll("#boot-args-presets .chip");
  
  const smbiosModelSelect = document.getElementById("smbios-model-select");
  const smbiosSerialInput = document.getElementById("smbios-serial");
  const smbiosMlbInput = document.getElementById("smbios-mlb");
  const smbiosUuidInput = document.getElementById("smbios-uuid");
  const smbiosRomInput = document.getElementById("smbios-rom");
  const btnRegenSmbios = document.getElementById("btn-regen-smbios");
  
  const amdCoreGroup = document.getElementById("amd-core-config-group");
  const amdCoreSlider = document.getElementById("amd-core-slider");
  const amdCoreDisplay = document.getElementById("amd-core-display");
  
  const plistCodeContent = document.getElementById("plist-code-content");
  const plistSizeBadge = document.getElementById("plist-size-badge");
  const diagnosticsList = document.getElementById("diagnostics-list");
  
  const statKexts = document.getElementById("stat-kexts");
  const statSsdts = document.getElementById("stat-ssdts");
  const statPatches = document.getElementById("stat-patches");
  
  const btnValidate = document.getElementById("btn-validate");
  const btnDownloadPlist = document.getElementById("btn-download-plist");
  const btnDownloadPlist2 = document.getElementById("btn-download-plist-2");
  const btnCopyPlist = document.getElementById("btn-copy-plist");
  
  const toast = document.getElementById("toast");

  // Show Toast Message
  function showToast(msg) {
    toast.textContent = msg;
    toast.style.display = "block";
    setTimeout(() => {
      toast.style.display = "none";
    }, 2800);
  }

  function stepDone(id) {
    if (id === "wizard") return !!(state.currentProfileId && (state.wizardTouched || state.gpuId || state.visitedTabs.has("kexts")));
    if (id === "kexts") return state.selectedKexts.has("Lilu") && state.selectedKexts.size >= 3;
    if (id === "quirks") return state.visitedTabs.has("quirks") && !!(state.bootArgs || "").trim();
    if (id === "smbios") return !!(state.smbios.serial && state.smbios.mlb && state.smbios.uuid);
    if (id === "repos") return state.visitedTabs.has("repos");
    if (id === "preview") return !!(state.latestXml && state.latestXml.length > 40);
    if (id === "usb") return !!state.efiReady;
    return false;
  }

  function nextStepId(fromId) {
    const index = STEPS.findIndex((step) => step.id === fromId);
    if (index < 0) return "";
    return (STEPS[index + 1] || {}).id || "";
  }

  function goToTab(tabId) {
    if (!tabId || !document.getElementById(`tab-${tabId}`)) return;
    state.currentTab = tabId;
    state.visitedTabs.add(tabId);
    tabPanes.forEach((pane) => pane.classList.toggle("active", pane.id === `tab-${tabId}`));
    if (tabId === "preview") buildAndRefreshPlist().then(() => refreshStepper());
    if (tabId === "usb") {
      refreshUsbTargets();
      loadMacosCatalog();
    }
    refreshStepper();
    const main = document.querySelector(".app-main");
    if (main) main.scrollTop = 0;
  }

  function refreshStepper() {
    const list = document.getElementById("step-list");
    if (!list) return;
    const firstOpen = STEPS.find((step) => !stepDone(step.id));
    list.innerHTML = STEPS.map((step, index) => {
      const done = stepDone(step.id);
      const active = state.currentTab === step.id;
      const nextUp = firstOpen && firstOpen.id === step.id;
      const meta = done ? "Done" : step.hint;
      return `<button type="button" class="step-item ${active ? "active" : ""} ${done ? "done" : ""} ${nextUp ? "next-up" : ""}" data-tab="${step.id}">
        <span class="step-connector"></span>
        <span class="step-index">${done ? "✓" : index + 1}</span>
        <span class="step-copy"><span class="step-title">${step.title}</span><span class="step-meta"> · ${meta}</span></span>
      </button>`;
    }).join("");
    list.querySelectorAll(".step-item").forEach((btn) => {
      btn.addEventListener("click", () => goToTab(btn.getAttribute("data-tab")));
    });
    updateStepCallout();
  }

  function updateStepCallout() {
    const current = STEPS.find((step) => step.id === state.currentTab) || STEPS[0];
    const next = STEPS.find((step) => step.id === nextStepId(current.id));
    const done = stepDone(current.id);
    const callout = document.getElementById("step-callout");
    const calloutText = document.getElementById("step-callout-text");
    const banner = document.getElementById("step-banner");
    const bannerText = document.getElementById("step-banner-text");
    const skipIds = ["btn-step-skip", "btn-step-banner-skip"];
    const nextBtns = [document.getElementById("btn-step-next"), document.getElementById("btn-step-banner-next")];
    skipIds.forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.hidden = current.id !== "repos";
    });
    if (!next) {
      const msg = done ? "EFI / USB is ready. Copy it to a stick when you want." : "Build the EFI folder to finish this pass.";
      if (callout) callout.hidden = false;
      if (calloutText) calloutText.textContent = msg;
      if (banner) banner.hidden = done;
      if (bannerText) bannerText.textContent = msg;
      nextBtns.forEach((btn) => { if (btn) btn.hidden = true; });
      return;
    }
    nextBtns.forEach((btn) => {
      if (!btn) return;
      btn.hidden = false;
      btn.textContent = current.id === "repos" ? `Continue to ${next.title}` : `Continue to ${next.title}`;
    });
    const msg = done
      ? `${current.title} looks good. Continue to ${next.title}.`
      : current.id === "wizard"
        ? "Pick or confirm a CPU/GPU profile, then continue to Kexts."
        : current.id === "repos"
          ? "Updates are optional. Sync now, or skip ahead to the plist."
          : `Finish ${current.title.toLowerCase()}, then continue to ${next.title}.`;
    if (callout) callout.hidden = false;
    if (calloutText) calloutText.textContent = msg;
    if (banner) banner.hidden = false;
    if (bannerText) bannerText.textContent = msg;
  }

  function advanceFromCurrent() {
    const next = nextStepId(state.currentTab);
    if (next) goToTab(next);
  }

  document.getElementById("btn-step-next")?.addEventListener("click", advanceFromCurrent);
  document.getElementById("btn-step-banner-next")?.addEventListener("click", advanceFromCurrent);
  document.getElementById("btn-step-skip")?.addEventListener("click", () => goToTab("preview"));
  document.getElementById("btn-step-banner-skip")?.addEventListener("click", () => goToTab("preview"));

  // Fetch Initial Data
  async function initApp() {
    try {
      const [profilesRes, kextsRes, reposRes, schemaRes, gpusRes] = await Promise.all([
        fetch("/api/profiles").then(r => r.json()),
        fetch("/api/kexts").then(r => r.json()),
        fetch("/api/repos").then(r => r.json()),
        fetch("/api/schema").then(r => r.json()).catch(() => null),
        fetch("/api/gpus").then(r => r.json()).catch(() => null)
      ]);

      if (profilesRes.success) {
        state.profiles = profilesRes.profiles;
        renderProfiles();
        selectProfile(state.currentProfileId, { silent: true });
      }

      if (kextsRes.success) {
        state.kextCatalog = kextsRes.kexts;
        renderKexts();
      }

      if (reposRes.success) {
        renderRepos(reposRes.data);
      }

      if (schemaRes && schemaRes.success) {
        applySchemaStatus(schemaRes);
      }

      if (gpusRes && gpusRes.success) {
        state.gpus = gpusRes.gpus || [];
        renderGpus();
      }

      await loadOpenCoreVersionCallout();

      const saved = loadSession();
      const banner = document.getElementById("session-banner");
      if (saved && banner) {
        banner.style.display = "flex";
        document.getElementById("session-banner-text").textContent =
          `Last config saved${saved.savedAt ? " " + saved.savedAt : ""}. Resume to keep editing, or start fresh.`;
      }

      // Generate initial SMBIOS
      await regenerateSmbios("iMac20,1");
      fetch("/api/efi/status").then((r) => r.json()).then((manifest) => {
        state.efiReady = !!(manifest && manifest.success && (manifest.readyForUsb || manifest.zipPath));
        refreshStepper();
      }).catch(() => {});
      refreshStepper();

    } catch (err) {
      console.error("Initialization error:", err);
      showToast("Error connecting to OpenCore Studio backend.");
    }
  }

  // Render Hardware Profiles
  function renderProfiles() {
    profilesContainer.innerHTML = "";
    const q = (state.cpuFilter || "").toLowerCase();
    const visible = state.profiles.filter(p => {
      if (!q) return true;
      const hay = [p.id, p.name, p.cpuFamily, p.description, ...(p.examples || []), ...(p.searchTerms || []), ...(p.chipsets || [])].join(" ").toLowerCase();
      return hay.includes(q);
    });
    (visible.length ? visible : state.profiles).forEach(p => {
      const card = document.createElement("div");
      card.className = `profile-card ${p.id === state.currentProfileId ? "active" : ""} ${p.id === state.suggestedProfileId ? "suggested" : ""}`;
      card.dataset.id = p.id;
      const examples = (p.examples || []).slice(0, 4).join(", ");
      card.innerHTML = `
        <div class="profile-card-header">
          <div class="profile-title">${p.name}</div>
          <span class="profile-badge">${p.platform || 'Desktop'}</span>
        </div>
        <p class="profile-desc">${p.description}</p>
        <div class="profile-specs">
          <div><strong>CPU:</strong> ${p.cpuFamily}</div>
          ${examples ? `<div class="profile-examples">Examples: ${examples}</div>` : ""}
        </div>
      `;
      card.addEventListener("click", () => selectProfile(p.id));
      profilesContainer.appendChild(card);
    });
  }

  // Select Hardware Profile
  async function selectProfile(profileId, options = {}) {
    state.currentProfileId = profileId;
    document.querySelectorAll(".profile-card").forEach(c => {
      c.classList.toggle("active", c.dataset.id === profileId);
    });

    try {
      const res = await fetch(`/api/profiles/${profileId}`).then(r => r.json());
      if (!res.success) return;
      const p = res.profile;
      state.currentProfile = p;

      // Update Header Badge
      activeProfileBadge.textContent = `Profile: ${p.name}`;

      // Update Side Panel
      document.getElementById("panel-profile-title").textContent = p.name;
      document.getElementById("panel-profile-desc").textContent = p.description;

      // Chipsets
      const chipsetsEl = document.getElementById("panel-chipsets");
      chipsetsEl.innerHTML = (p.chipsets || ["Generic"]).map(c => `<span class="chip-tag">${c}</span>`).join("");

      // SSDTs
      const ssdtEl = document.getElementById("panel-ssdts");
      const ssdts = p.mandatorySsdt || [];
      ssdtEl.innerHTML = ssdts.map(s => `
        <li class="ssdt-item">
          <div class="ssdt-name">${s.name}</div>
          <div class="ssdt-reason">${s.reason}</div>
        </li>
      `).join("");

      const preserve = !!options.preserve;
      if (!preserve) {
        if (p.recommendedKexts && p.recommendedKexts.length > 0) {
          state.selectedKexts = new Set(p.recommendedKexts);
        }
        state.quirks.Booter = Object.assign({}, state.schemaQuirks.Booter || {}, p.booterQuirks || {});
        state.quirks.Kernel = Object.assign({}, state.schemaQuirks.Kernel || {}, p.kernelQuirks || {});
        state.quirks.ACPI = Object.assign({}, state.schemaQuirks.ACPI || {}, p.acpiQuirks || {});
        state.quirks.UEFI = Object.assign({}, state.schemaQuirks.UEFI || {}, p.uefiQuirks || {});
        let recSmbios = "iMac20,1";
        if (typeof p.recommendedSmbios === "string") recSmbios = p.recommendedSmbios;
        else if (typeof p.recommendedSmbios === "object") {
          recSmbios = p.recommendedSmbios.igpu_only || p.recommendedSmbios.default || Object.values(p.recommendedSmbios)[0];
        }
        if ([...smbiosModelSelect.options].some(o => o.value === recSmbios)) {
          smbiosModelSelect.value = recSmbios;
        }
        await regenerateSmbios(recSmbios);
        if (p.recommendedBootArgs) setBootArgs(p.recommendedBootArgs);
      }

      renderKexts();
      renderQuirks();

      const isAmd = p.architecture === "AMD" || profileId.includes("amd") || profileId.includes("ryzen");
      amdCoreGroup.style.display = isAmd ? "block" : "none";

      if (!preserve) {
        saveSession();
        if (!options.silent) {
          state.wizardTouched = true;
          showToast(`Switched to profile: ${p.name}`);
        }
        refreshStepper();
      }
    } catch (err) {
      console.error(err);
    }
  }

  // Render Kexts
  function renderKexts(category = "all", query = "") {
    kextCardsContainer.innerHTML = "";
    const lowerQuery = query.toLowerCase();

    const filtered = state.kextCatalog.filter(k => {
      const matchCat = category === "all" || k.category.toLowerCase() === category.toLowerCase();
      const matchSearch = !query || k.name.toLowerCase().includes(lowerQuery) || k.description.toLowerCase().includes(lowerQuery);
      return matchCat && matchSearch;
    });

    filtered.forEach(k => {
      const isSelected = state.selectedKexts.has(k.id);
      const isMandatory = k.required === true;
      const card = document.createElement("div");
      card.className = `kext-card ${isSelected ? "enabled" : ""}`;
      card.innerHTML = `
        <div class="kext-card-header">
          <div class="kext-name">
            ${k.name}
            ${isMandatory ? '<span class="badge badge-accent">Required</span>' : ''}
          </div>
          <label class="switch">
            <input type="checkbox" data-id="${k.id}" ${isSelected ? 'checked' : ''} ${isMandatory ? 'disabled' : ''}>
            <span class="slider"></span>
          </label>
        </div>
        <div class="kext-desc">${k.description}</div>
        <div class="kext-meta-row">
          <span class="kext-priority-tag">Order Prio: ${k.priority}</span>
          ${k.latestRelease ? `<span class="kext-priority-tag">${k.latestRelease}</span>` : ""}
          <span class="kext-author"><a href="https://github.com/${k.github}" target="_blank" rel="noopener">${k.github}</a></span>
        </div>
      `;

      const toggle = card.querySelector('input[type="checkbox"]');
      if (!isMandatory) {
        toggle.addEventListener("change", (e) => {
          if (e.target.checked) {
            state.selectedKexts.add(k.id);
            card.classList.add("enabled");
          } else {
            state.selectedKexts.delete(k.id);
            card.classList.remove("enabled");
          }
          updateKextCount();
        });
      }
      kextCardsContainer.appendChild(card);
    });

    updateKextCount();
  }

  function updateKextCount() {
    if (kextCountBadge) kextCountBadge.textContent = state.selectedKexts.size;
    refreshStepper();
  }

  // Filter Kexts
  kextCatButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      kextCatButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      renderKexts(btn.dataset.cat, kextSearch.value);
    });
  });

  kextSearch.addEventListener("input", (e) => {
    const activeCat = document.querySelector("#kext-categories .pill-btn.active")?.dataset.cat || "all";
    renderKexts(activeCat, e.target.value);
  });

  // Render Quirks
  function renderQuirks() {
    renderQuirksGroup(booterQuirksList, state.quirks.Booter, "Booter");
    renderQuirksGroup(kernelQuirksList, state.quirks.Kernel, "Kernel");

    miscQuirksList.innerHTML = "";
    Object.keys(state.quirks.ACPI || {}).forEach((key) => {
      appendMiscQuirk(key, state.quirks.ACPI[key], "ACPI");
    });
    Object.keys(state.quirks.UEFI || {}).forEach((key) => {
      appendMiscQuirk(key, state.quirks.UEFI[key], "UEFI");
    });
    if (!miscQuirksList.children.length) {
      miscQuirksList.innerHTML = '<div class="quirk-row"><div class="quirk-info"><span class="quirk-desc">No ACPI/UEFI boolean quirks in the active Sample.plist.</span></div></div>';
    }
  }

  function appendMiscQuirk(key, val, groupKey) {
    if (typeof val !== "boolean") return;
    const row = document.createElement("div");
    row.className = "quirk-row";
    row.innerHTML = `
      <div class="quirk-info">
        <span class="quirk-name">${key} (${groupKey})</span>
      </div>
      <label class="switch">
        <input type="checkbox" data-group="${groupKey}" data-key="${key}" ${val ? "checked" : ""}>
        <span class="slider"></span>
      </label>
    `;
    row.querySelector("input").addEventListener("change", (e) => {
      state.quirks[groupKey][key] = e.target.checked;
    });
    miscQuirksList.appendChild(row);
  }

  function renderQuirksGroup(container, quirksObj, groupKey) {
    container.innerHTML = "";
    Object.keys(quirksObj).forEach(key => {
      const val = quirksObj[key];
      if (typeof val !== "boolean") return;

      const row = document.createElement("div");
      row.className = "quirk-row";
      row.innerHTML = `
        <div class="quirk-info">
          <span class="quirk-name">${key}</span>
        </div>
        <label class="switch">
          <input type="checkbox" data-group="${groupKey}" data-key="${key}" ${val ? 'checked' : ''}>
          <span class="slider"></span>
        </label>
      `;

      row.querySelector('input').addEventListener("change", (e) => {
        state.quirks[groupKey][key] = e.target.checked;
      });

      container.appendChild(row);
    });
  }

  // Boot Args Chips & Input
  function setBootArgs(argsStr) {
    state.bootArgs = argsStr;
    bootArgsInput.value = argsStr;
    updateBootArgChips();
  }

  function updateBootArgChips() {
    const tokens = state.bootArgs.split(/\s+/).filter(Boolean);
    bootArgsChips.forEach(chip => {
      const arg = chip.dataset.arg;
      chip.classList.toggle("active", tokens.includes(arg));
    });
  }

  bootArgsChips.forEach(chip => {
    chip.addEventListener("click", () => {
      const arg = chip.dataset.arg;
      let tokens = state.bootArgs.split(/\s+/).filter(Boolean);
      if (tokens.includes(arg)) {
        tokens = tokens.filter(t => t !== arg);
      } else {
        tokens.push(arg);
      }
      setBootArgs(tokens.join(" "));
    });
  });

  bootArgsInput.addEventListener("input", (e) => {
    state.bootArgs = e.target.value;
    updateBootArgChips();
  });

  // AMD Core Count Slider
  amdCoreSlider.addEventListener("input", (e) => {
    const val = parseInt(e.target.value, 10);
    state.amdCoreCount = val;
    const hex = val.toString(16).toUpperCase().padStart(2, '0');
    amdCoreDisplay.textContent = `${val} Cores (0x${hex})`;
  });

  // SMBIOS Logic
  async function regenerateSmbios(model) {
    try {
      const res = await fetch("/api/generate-smbios", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model })
      }).then(r => r.json());

      if (res.success) {
        state.smbios = res.smbios;
        smbiosSerialInput.value = res.smbios.serial;
        smbiosMlbInput.value = res.smbios.mlb;
        smbiosUuidInput.value = res.smbios.uuid;
        smbiosRomInput.value = res.smbios.rom;
        refreshStepper();
      }
    } catch (err) {
      console.error("SMBIOS generation failed:", err);
    }
  }

  btnRegenSmbios.addEventListener("click", () => {
    regenerateSmbios(smbiosModelSelect.value);
    showToast("Generated fresh authentic SMBIOS identity.");
  });

  smbiosModelSelect.addEventListener("change", (e) => {
    regenerateSmbios(e.target.value);
  });

  // Copy Buttons
  document.querySelectorAll(".btn-copy").forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.target;
      const input = document.getElementById(targetId);
      if (input && input.value) {
        navigator.clipboard.writeText(input.value);
        showToast(`Copied ${targetId.replace("smbios-", "")} to clipboard`);
      }
    });
  });

  function saveSession() {
    const payload = {
      savedAt: new Date().toLocaleString(),
      profileId: state.currentProfileId,
      gpuId: state.gpuId,
      selectedKexts: Array.from(state.selectedKexts),
      bootArgs: state.bootArgs,
      smbios: state.smbios,
      quirks: state.quirks,
      amdCoreCount: state.amdCoreCount,
      latestXml: state.latestXml || "",
      selectedMacosId: state.selectedMacosId || ""
    };
    try {
      localStorage.setItem(SESSION_KEY, JSON.stringify(payload));
    } catch (err) {
      console.warn("Could not persist session", err);
    }
  }

  function loadSession() {
    try {
      const raw = localStorage.getItem(SESSION_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (err) {
      return null;
    }
  }

  async function hydrateStudio(studio, xml) {
    if (!studio) return;
    if (studio.profileId) {
      await selectProfile(studio.profileId, { preserve: true });
    }
    if (Array.isArray(studio.selectedKextIds || studio.selectedKexts)) {
      state.selectedKexts = new Set(studio.selectedKextIds || studio.selectedKexts);
      renderKexts();
    }
    if (studio.bootArgs) setBootArgs(studio.bootArgs);
    if (studio.quirks) {
      state.quirks.ACPI = Object.assign({}, state.quirks.ACPI, studio.quirks.ACPI || {});
      state.quirks.Booter = Object.assign({}, state.quirks.Booter, studio.quirks.Booter || {});
      state.quirks.Kernel = Object.assign({}, state.quirks.Kernel, studio.quirks.Kernel || {});
      state.quirks.UEFI = Object.assign({}, state.quirks.UEFI, studio.quirks.UEFI || {});
      renderQuirks();
    }
    if (studio.smbios) {
      state.smbios = Object.assign({}, state.smbios, studio.smbios);
      if (studio.smbios.model && [...smbiosModelSelect.options].some(o => o.value === studio.smbios.model)) {
        smbiosModelSelect.value = studio.smbios.model;
      }
      smbiosSerialInput.value = state.smbios.serial || "";
      smbiosMlbInput.value = state.smbios.mlb || "";
      smbiosUuidInput.value = state.smbios.uuid || "";
      smbiosRomInput.value = state.smbios.rom || "";
    }
    if (studio.gpuId) {
      state.gpuId = studio.gpuId;
      renderGpus();
    }
    if (xml) {
      state.latestXml = xml;
      plistCodeContent.textContent = xml;
    }
    if (studio.gpuId || studio.profileId) state.wizardTouched = true;
    saveSession();
    refreshStepper();
  }

  function renderGpus(filter = "") {
    const wrap = document.getElementById("gpu-cards");
    if (!wrap) return;
    wrap.innerHTML = "";
    const q = filter.toLowerCase();
    const list = state.gpus.filter(g => {
      if (!q) return true;
      return [g.id, g.name, g.family, ...(g.examples || []), ...(g.aliases || [])].join(" ").toLowerCase().includes(q);
    });
    (list.length ? list : state.gpus).forEach(g => {
      const card = document.createElement("div");
      card.className = `gpu-card ${g.id === state.gpuId ? "active" : ""}`;
      card.innerHTML = `
        <div class="gpu-card-title">${g.name}</div>
        <div class="gpu-card-meta"><span class="gpu-support-${g.support}">${g.support}</span> · ${g.family}</div>
      `;
      card.addEventListener("click", () => applyGpu(g.id));
      wrap.appendChild(card);
    });
  }

  function mergeBootArg(arg, enabled) {
    let tokens = state.bootArgs.split(/\s+/).filter(Boolean);
    if (enabled && !tokens.includes(arg)) tokens.push(arg);
    if (!enabled) tokens = tokens.filter(t => t !== arg);
    setBootArgs(tokens.join(" "));
  }

  async function applyGpu(gpuId) {
    state.gpuId = gpuId;
    renderGpus(document.getElementById("gpu-search")?.value || "");
    try {
      const res = await fetch("/api/gpu/apply-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gpuId })
      }).then(r => r.json());
      const box = document.getElementById("gpu-match-result");
      if (!res.success) {
        if (box) {
          box.textContent = res.error || "GPU apply failed";
          box.className = "cpu-match-result match-miss";
        }
        return;
      }
      (res.addKexts || []).forEach(id => state.selectedKexts.add(id));
      (res.removeKexts || []).forEach(id => {
        if (id === "Lilu" || id === "VirtualSMC") return;
        state.selectedKexts.delete(id);
      });
      renderKexts();
      (res.requiredBootArgs || []).forEach(arg => mergeBootArg(arg, true));
      const optional = (res.optionalBootArgs || []).map(a => a.arg || a).filter(Boolean);
      if (box) {
        box.className = `cpu-match-result ${res.support === "unsupported" ? "match-miss" : "match-ok"}`;
        box.innerHTML = `<strong>${res.gpu.name}</strong> — ${res.support}. ${res.notes || ""}`
          + (optional.length ? `<div style="margin-top:6px;">Optional args: ${optional.map(a => `<button class="chip" data-gpu-arg="${a}">${a}</button>`).join(" ")}</div>` : "");
        box.querySelectorAll("[data-gpu-arg]").forEach(btn => {
          btn.addEventListener("click", () => mergeBootArg(btn.dataset.gpuArg, true));
        });
      }
      saveSession();
      state.wizardTouched = true;
      showToast(`GPU family set: ${res.gpu.name}`);
      refreshStepper();
    } catch (err) {
      console.error(err);
    }
  }

  let cpuSearchTimer = null;
  document.getElementById("cpu-search").addEventListener("input", (e) => {
    const value = e.target.value.trim();
    state.cpuFilter = value;
    renderProfiles();
    clearTimeout(cpuSearchTimer);
    if (!value) {
      state.suggestedProfileId = "";
      document.getElementById("cpu-match-result").textContent = "No lookup yet. Example: W-2133 → Xeon W-2100 / C422.";
      document.getElementById("cpu-match-result").className = "cpu-match-result";
      return;
    }
    cpuSearchTimer = setTimeout(async () => {
      const res = await fetch(`/api/hardware/match?cpu=${encodeURIComponent(value)}`).then(r => r.json());
      const box = document.getElementById("cpu-match-result");
      const cpu = res.cpu || res;
      if (cpu && cpu.success && cpu.profile) {
        state.suggestedProfileId = cpu.profile.id;
        const extra = cpu.cpu ? ` ${cpu.cpu.socket || ""} ${cpu.cpu.chipset || ""}`.trim() : "";
        box.className = "cpu-match-result match-ok";
        box.textContent = `${value} → ${cpu.profile.name}${extra ? " · " + extra : ""}. Click the highlighted card or it will be selected.`;
        renderProfiles();
        selectProfile(cpu.profile.id);
      } else {
        state.suggestedProfileId = "";
        box.className = "cpu-match-result match-miss";
        box.textContent = (cpu && cpu.error) || res.error || "No matching architecture profile.";
        renderProfiles();
      }
    }, 280);
  });

  document.getElementById("gpu-search").addEventListener("input", async (e) => {
    const value = e.target.value.trim();
    renderGpus(value);
    if (!value) return;
    const res = await fetch(`/api/hardware/match?gpu=${encodeURIComponent(value)}`).then(r => r.json());
    if (res.gpu && res.gpu.success && res.gpu.gpu) {
      applyGpu(res.gpu.gpu.id);
    }
  });

  document.getElementById("btn-load-plist")?.addEventListener("click", () => {
    if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.studio) {
      window.webkit.messageHandlers.studio.postMessage("loadPlist");
      return;
    }
    document.getElementById("file-load-plist")?.click();
  });

  document.getElementById("file-load-plist").addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const buf = await file.arrayBuffer();
    await importPlistPayload({ b64: bytesToBase64(new Uint8Array(buf)) });
    e.target.value = "";
  });

  function bytesToBase64(bytes) {
    let binary = "";
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
  }

  async function importPlistXml(xml) {
    return importPlistPayload({ xml });
  }

  async function importPlistPayload(body) {
    const res = await fetch("/api/import-plist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then((r) => r.json());
    if (!res.success) {
      showToast(res.error || "Could not import plist");
      return false;
    }
    await hydrateStudio(res.studio, res.xml);
    showToast("Loaded config.plist — edit and rebuild anytime.");
    return true;
  }

  async function importPendingNativePlist() {
    const res = await fetch("/api/plist/pending-import").then((r) => r.json());
    if (!res.success) {
      showToast(res.error || "Could not import plist");
      return false;
    }
    await hydrateStudio(res.studio, res.xml);
    showToast("Loaded config.plist — edit and rebuild anytime.");
    return true;
  }

  document.getElementById("btn-resume-session").addEventListener("click", async () => {
    const saved = loadSession();
    if (!saved) return;
    await hydrateStudio({
      profileId: saved.profileId,
      gpuId: saved.gpuId,
      selectedKextIds: saved.selectedKexts,
      bootArgs: saved.bootArgs,
      smbios: saved.smbios,
      quirks: saved.quirks
    }, saved.latestXml);
    if (saved.amdCoreCount) {
      state.amdCoreCount = saved.amdCoreCount;
      amdCoreSlider.value = saved.amdCoreCount;
    }
    if (saved.selectedMacosId) {
      state.selectedMacosId = saved.selectedMacosId;
    }
    document.getElementById("session-banner").style.display = "none";
    showToast("Resumed last Studio config.");
  });

  document.getElementById("btn-clear-session").addEventListener("click", () => {
    localStorage.removeItem(SESSION_KEY);
    document.getElementById("session-banner").style.display = "none";
    showToast("Cleared saved config.");
  });

  // Repositories & Guidance Hub
  function renderRepos(repoData) {
    const list = document.getElementById("repos-list");
    list.innerHTML = "";
    (repoData.repositories || []).forEach(r => {
      const item = document.createElement("div");
      item.className = "repo-item";
      item.innerHTML = `
        <div>
          <div class="repo-name">${r.name}</div>
          <div class="repo-url">${r.url || r.manifestUrl || 'GitHub'}</div>
        </div>
        <span class="badge ${r.official ? 'badge-pulse' : 'badge-accent'}">${r.official ? 'Official' : 'Custom'}</span>
      `;
      list.appendChild(item);
    });
  }

  // Register Custom Repo
  document.getElementById("form-add-repo").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("repo-name").value;
    const url = document.getElementById("repo-url").value;
    const maintainer = document.getElementById("repo-maintainer").value;

    const res = await fetch("/api/repos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, url, maintainer })
    }).then(r => r.json());

    if (res.success) {
      showToast("Custom repository registered successfully!");
      renderRepos(res.data);
      e.target.reset();
    } else {
      showToast(`Error: ${res.error}`);
    }
  });

  // Import Hardware Guidance from URL
  document.getElementById("btn-import-url").addEventListener("click", async () => {
    const url = document.getElementById("import-url").value.trim();
    if (!url) return;
    const res = await fetch("/api/profiles/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    }).then(r => r.json());

    if (res.success) {
      showToast(`Successfully imported profile: ${res.profile.name}`);
      const profsRes = await fetch("/api/profiles").then(r => r.json());
      if (profsRes.success) {
        state.profiles = profsRes.profiles;
        renderProfiles();
        selectProfile(res.profile.id);
      }
    } else {
      showToast(`Import error: ${res.error}`);
    }
  });

  // Import Hardware Guidance from JSON
  document.getElementById("btn-import-json").addEventListener("click", async () => {
    const raw = document.getElementById("import-json").value.trim();
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw);
      const res = await fetch("/api/profiles/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ json: parsed })
      }).then(r => r.json());

      if (res.success) {
        showToast(`Successfully imported: ${res.profile.name}`);
        const profsRes = await fetch("/api/profiles").then(r => r.json());
        if (profsRes.success) {
          state.profiles = profsRes.profiles;
          renderProfiles();
          selectProfile(res.profile.id);
        }
      } else {
        showToast(`Import error: ${res.error}`);
      }
    } catch (e) {
      showToast("Invalid JSON payload.");
    }
  });

  async function loadOpenCoreVersionCallout() {
    const box = document.getElementById("oc-version-callout");
    if (!box) return;
    const text = document.getElementById("oc-version-callout-text");
    const includedLabel = document.getElementById("oc-included-label");
    const latestLabel = document.getElementById("oc-latest-label");
    const latestWrap = document.getElementById("oc-choice-latest-wrap");
    const select = document.getElementById("oc-first-release-select");
    const boot = await fetch("/api/bootstrap").then((r) => r.json()).catch(() => null);
    if (!boot || !boot.needsChoice) {
      box.hidden = true;
      if (boot && boot.schema) applySchemaStatus(boot.schema);
      return;
    }
    if (boot.schema) applySchemaStatus(boot.schema);
    box.hidden = false;
    if (text) text.textContent = boot.message || "";
    if (includedLabel) includedLabel.textContent = boot.includedTag || "bundled";
    if (latestLabel) latestLabel.textContent = boot.latestTag || "—";
    if (latestWrap) latestWrap.hidden = !boot.hasNewer;
    if (select) {
      select.innerHTML = (boot.releases || []).map((rel) => (
        `<option value="${rel.tag}" ${rel.tag === boot.includedTag ? "selected" : ""}>${rel.tag}${rel.tag === boot.latestTag ? " (latest)" : ""}${rel.tag === boot.includedTag ? " (included)" : ""}</option>`
      )).join("");
    }
  }

  function selectedFirstOpenTag() {
    const choice = document.querySelector("input[name='oc-first-choice']:checked")?.value || "included";
    const included = (document.getElementById("oc-included-label")?.textContent || "").trim();
    const latest = (document.getElementById("oc-latest-label")?.textContent || "").trim();
    const other = document.getElementById("oc-first-release-select")?.value || "";
    if (choice === "latest" && latest && latest !== "—") return latest;
    if (choice === "other") return other || included;
    return included;
  }

  document.querySelectorAll("input[name='oc-first-choice']").forEach((input) => {
    input.addEventListener("change", () => {
      const select = document.getElementById("oc-first-release-select");
      if (select) select.hidden = input.value !== "other" && document.querySelector("input[name='oc-first-choice']:checked")?.value !== "other";
    });
  });
  const otherChoice = document.getElementById("oc-choice-other");
  const firstSelect = document.getElementById("oc-first-release-select");
  if (otherChoice && firstSelect) {
    otherChoice.addEventListener("change", () => {
      firstSelect.hidden = !otherChoice.checked;
    });
  }

  document.getElementById("btn-oc-first-continue")?.addEventListener("click", async () => {
    const tag = selectedFirstOpenTag();
    const btn = document.getElementById("btn-oc-first-continue");
    const text = document.getElementById("oc-version-callout-text");
    if (btn) btn.disabled = true;
    if (text) text.textContent = `Applying OpenCore ${tag}…`;
    const res = await fetch("/api/bootstrap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ opencoreTag: tag })
    }).then((r) => r.json()).catch((err) => ({ success: false, error: String(err) }));
    if (btn) btn.disabled = false;
    if (!res.success) {
      if (text) text.textContent = res.error || "Could not apply that OpenCore version.";
      showToast(res.error || "OpenCore apply failed.");
      return;
    }
    if (res.schema) applySchemaStatus(res.schema);
    const box = document.getElementById("oc-version-callout");
    if (box) box.hidden = true;
    showToast(res.message || `Using OpenCore ${tag}.`);
  });

  async function applyOpenCoreTag(tag) {
    if (!tag) return;
    showToast(`Switching to OpenCore ${tag}…`);
    const res = await fetch("/api/bootstrap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ opencoreTag: tag })
    }).then((r) => r.json()).catch((err) => ({ success: false, error: String(err) }));
    const menu = document.getElementById("oc-version-menu");
    if (menu) menu.hidden = true;
    if (!res.success) {
      showToast(res.error || "Could not switch OpenCore version.");
      return;
    }
    if (res.schema) applySchemaStatus(res.schema);
    showToast(res.message || `Using OpenCore ${tag}.`);
  }

  async function showOpenCoreVersionMenu(event) {
    if (event) event.preventDefault();
    const menu = document.getElementById("oc-version-menu");
    if (!menu) return;
    menu.hidden = false;
    menu.innerHTML = '<div class="oc-version-menu-label">Loading releases…</div>';
    const boot = await fetch("/api/bootstrap?force=1").then((r) => r.json()).catch(() => null);
    if (!boot) {
      menu.innerHTML = '<div class="oc-version-menu-label">Could not load versions.</div>';
      return;
    }
    const current = (boot.schema && boot.schema.current && boot.schema.current.opencoreTag) || boot.includedTag || "";
    const latest = boot.latestTag || "";
    const rows = [`<div class="oc-version-menu-label">OpenCore version</div>`];
    (boot.releases || []).forEach((rel) => {
      const bits = [];
      if (rel.tag === current || rel.tag === boot.includedTag) bits.push("current");
      if (rel.tag === latest) bits.push("latest");
      const suffix = bits.length ? ` — ${bits.join(", ")}` : "";
      rows.push(`<button type="button" data-oc-tag="${rel.tag}" class="${rel.tag === current ? "active" : ""}">${rel.tag}${suffix}</button>`);
    });
    menu.innerHTML = rows.join("");
    menu.querySelectorAll("button[data-oc-tag]").forEach((btn) => {
      btn.addEventListener("click", () => applyOpenCoreTag(btn.getAttribute("data-oc-tag")));
    });
  }

  const ocBadge = document.getElementById("oc-schema-badge");
  if (ocBadge) {
    ocBadge.addEventListener("click", showOpenCoreVersionMenu);
    ocBadge.addEventListener("contextmenu", showOpenCoreVersionMenu);
  }
  document.addEventListener("click", (event) => {
    const menu = document.getElementById("oc-version-menu");
    if (!menu || menu.hidden) return;
    if (event.target.closest("#oc-version-menu") || event.target.closest("#oc-schema-badge")) return;
    menu.hidden = true;
  });

  window.ocsImportPlistPayload = (payload) => importPlistXml((payload && payload.xml) || "");
  window.ocsImportPendingNative = () => importPendingNativePlist();
  window.ocsShowVersionPicker = () => showOpenCoreVersionMenu();
  window.ocsExportPlist = () => triggerDownloadPlist();

  function applySchemaStatus(payload) {
    const current = payload.current || {};
    const schema = payload.schema || {};
    if (schema.quirks) {
      state.schemaQuirks = schema.quirks;
    }
    const badge = document.getElementById("oc-schema-badge");
    const label = current.label || schema.label || "OpenCore Sample.plist";
    if (badge) {
      badge.textContent = `● ${label}`;
      badge.classList.remove("badge-stale");
      badge.classList.add("badge-pulse");
    }
    const ocStatus = document.getElementById("upd-opencore-status");
    const amdStatus = document.getElementById("upd-amd-status");
    if (ocStatus) ocStatus.textContent = `Current: ${current.opencoreTag || "bundled"}`;
    if (amdStatus) amdStatus.textContent = `Current: ${current.amdRef || "bundled"}`;
    const rollbackBtn = document.getElementById("btn-rollback-updates");
    if (rollbackBtn) rollbackBtn.disabled = !current.canRollback;
  }

  function summarizeUpdateCheck(data) {
    const lines = [];
    const oc = data.available && data.available.opencore;
    const amd = data.available && data.available.amdVanilla;
    const kexts = data.available && data.available.kexts;
    if (oc && !oc.error) {
      lines.push(`OpenCore ${oc.tag}${oc.changed ? " — Sample.plist differs from your local copy." : " — already matches your local Sample.plist."}`);
      if (oc.notes) lines.push(oc.notes.split("\n").slice(0, 8).join("\n"));
      const added = (oc.schemaDiff && oc.schemaDiff.added) || [];
      const removed = (oc.schemaDiff && oc.schemaDiff.removed) || [];
      if (added.length) lines.push(`Added keys: ${added.slice(0, 12).join(", ")}${added.length > 12 ? "…" : ""}`);
      if (removed.length) lines.push(`Removed keys: ${removed.slice(0, 12).join(", ")}${removed.length > 12 ? "…" : ""}`);
    } else if (oc && oc.error) {
      lines.push(`OpenCore check failed: ${oc.error}`);
    }
    if (amd && !amd.error) {
      lines.push(`AMD Vanilla ${amd.ref} — ${amd.changed ? "patches.plist has upstream changes." : "already current."} (${amd.patchCount} patches)`);
    } else if (amd && amd.error) {
      lines.push(`AMD Vanilla check failed: ${amd.error}`);
    }
    if (kexts && !kexts.error) {
      lines.push(`Kext catalog: ${kexts.updates.length} newer release tag(s) across ${kexts.checkedRepos} repos.`);
      kexts.updates.slice(0, 8).forEach((u) => {
        lines.push(`  ${u.name}: ${u.current} → ${u.latest}`);
      });
    } else if (kexts && kexts.error) {
      lines.push(`Kext check failed: ${kexts.error}`);
    }
    if (data.errors && data.errors.length) {
      lines.push(data.errors.join("\n"));
    }
    return lines.join("\n") || "No update details returned.";
  }

  function renderReleasePicker(releases, selectedTag) {
    const group = document.getElementById("oc-release-picker-group");
    const select = document.getElementById("oc-release-select");
    if (!group || !select) return;
    select.innerHTML = "";
    (releases || []).forEach((rel) => {
      const opt = document.createElement("option");
      opt.value = rel.tag;
      opt.textContent = `${rel.tag}${rel.prerelease ? " (pre-release)" : ""}`;
      if (rel.tag === selectedTag) opt.selected = true;
      select.appendChild(opt);
    });
    group.style.display = select.options.length ? "block" : "none";
  }

  function markBadgeStale(isStale) {
    const badge = document.getElementById("oc-schema-badge");
    if (!badge) return;
    badge.classList.toggle("badge-stale", !!isStale);
    badge.classList.toggle("badge-pulse", !isStale);
  }

  document.getElementById("btn-check-updates").addEventListener("click", async () => {
    const notes = document.getElementById("update-notes");
    const applyBtn = document.getElementById("btn-apply-updates");
    notes.textContent = "Checking GitHub for OpenCorePkg, AMD Vanilla, and kext releases…";
    notes.classList.remove("has-changes");
    applyBtn.disabled = true;
    try {
      const res = await fetch("/api/updates/status?refresh=1").then((r) => r.json());
      state.updateStatus = res;
      applySchemaStatus(res);
      const oc = res.available && res.available.opencore;
      if (oc && oc.releases) renderReleasePicker(oc.releases, oc.tag);
      if (oc && !oc.error) {
        document.getElementById("upd-opencore-status").textContent =
          `Current: ${res.current.opencoreTag} → latest ${oc.tag}${oc.changed ? " (update available)" : " (current)"}`;
      }
      if (res.available && res.available.amdVanilla && !res.available.amdVanilla.error) {
        const amd = res.available.amdVanilla;
        document.getElementById("upd-amd-status").textContent =
          `Current: ${res.current.amdRef} → ${amd.ref}${amd.changed ? " (update available)" : " (current)"}`;
      }
      if (res.available && res.available.kexts && !res.available.kexts.error) {
        const kexts = res.available.kexts;
        document.getElementById("upd-kexts-status").textContent =
          `${kexts.updates.length} newer tag(s) across ${kexts.checkedRepos} repos.`;
      }
      const hasChanges = !!(
        (oc && oc.changed) ||
        (res.available && res.available.amdVanilla && res.available.amdVanilla.changed) ||
        (res.available && res.available.kexts && res.available.kexts.updates && res.available.kexts.updates.length)
      );
      notes.textContent = summarizeUpdateCheck(res);
      notes.classList.toggle("has-changes", hasChanges);
      markBadgeStale(hasChanges);
      applyBtn.disabled = false;
      showToast(hasChanges ? "Upstream updates are available." : "Local files already match upstream.");
    } catch (err) {
      notes.textContent = `Update check failed: ${err}`;
      showToast("Could not reach GitHub for updates.");
    }
  });

  document.getElementById("btn-apply-updates").addEventListener("click", async () => {
    const components = [];
    if (document.getElementById("upd-opencore").checked) components.push("opencore");
    if (document.getElementById("upd-amd").checked) components.push("amd");
    if (document.getElementById("upd-kexts").checked) components.push("kexts");
    if (!components.length) {
      showToast("Select at least one update component.");
      return;
    }
    const notes = document.getElementById("update-notes");
    notes.textContent = "Downloading and validating upstream files…";
    try {
      const tag = document.getElementById("oc-release-select").value || undefined;
      const res = await fetch("/api/updates/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ components, opencoreTag: tag })
      }).then((r) => r.json());
      applySchemaStatus(res);
      if (res.schema && res.schema.quirks && state.currentProfile) {
        const p = state.currentProfile;
        state.quirks.Booter = Object.assign({}, res.schema.quirks.Booter || {}, p.booterQuirks || {});
        state.quirks.Kernel = Object.assign({}, res.schema.quirks.Kernel || {}, p.kernelQuirks || {});
        state.quirks.ACPI = Object.assign({}, res.schema.quirks.ACPI || {}, p.acpiQuirks || {});
        state.quirks.UEFI = Object.assign({}, res.schema.quirks.UEFI || {}, p.uefiQuirks || {});
        renderQuirks();
      }
      const kextsRes = await fetch("/api/kexts").then((r) => r.json());
      if (kextsRes.success) {
        state.kextCatalog = kextsRes.kexts;
        renderKexts();
      }
      const parts = [];
      if (res.applied && res.applied.opencore) parts.push(`OpenCore ${res.applied.opencore.tag}`);
      if (res.applied && res.applied.amdVanilla) parts.push(`AMD Vanilla ${res.applied.amdVanilla.ref}`);
      if (res.applied && res.applied.kexts) parts.push(`${res.applied.kexts.applied} kext tag(s)`);
      notes.textContent = [
        parts.length ? `Applied: ${parts.join(", ")}.` : "Nothing was applied.",
        ...(res.errors || [])
      ].join("\n");
      notes.classList.remove("has-changes");
      markBadgeStale(false);
      document.getElementById("btn-rollback-updates").disabled = !res.current?.canRollback;
      showToast(res.success ? "Upstream files applied. New plist builds will use them." : (res.errors || []).join(" "));
    } catch (err) {
      notes.textContent = `Apply failed: ${err}`;
      showToast("Failed to apply upstream updates.");
    }
  });

  document.getElementById("btn-rollback-updates").addEventListener("click", async () => {
    const notes = document.getElementById("update-notes");
    try {
      const res = await fetch("/api/updates/rollback", { method: "POST" }).then((r) => r.json());
      applySchemaStatus(res);
      notes.textContent = (res.restored || []).join("\n") || "No backups were available.";
      showToast(res.success ? "Restored the previous Sample/patches/kext catalog." : "Nothing to roll back.");
    } catch (err) {
      notes.textContent = `Rollback failed: ${err}`;
    }
  });

  // Build & Refresh Plist
  function studioBuildPayload() {
    return {
      profileId: state.currentProfileId,
      selectedKextIds: Array.from(state.selectedKexts),
      bootArgs: state.bootArgs,
      smbios: state.smbios,
      amdCoreCount: state.amdCoreCount,
      quirkOverrides: {
        Booter: state.quirks.Booter,
        Kernel: state.quirks.Kernel,
        ACPI: state.quirks.ACPI,
        UEFI: state.quirks.UEFI
      },
      hardwareInfo: {
        cpuFamily: state.currentProfile?.cpuFamily || "",
        gpuType: state.bootArgs.includes("agdpmod=pikera") ? "AMD Navi RX 6000" : "Intel UHD"
      }
    };
  }

  async function buildAndRefreshPlist() {
    plistCodeContent.textContent = "<!-- Compiling 100% compliant OpenCore config.plist... -->";
    try {
      const payload = studioBuildPayload();

      const res = await fetch("/api/build-plist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }).then(r => r.json());

      if (res.success) {
        state.latestXml = res.xml;
        plistCodeContent.textContent = res.xml;
        const sizeKb = (res.xml.length / 1024).toFixed(1);
        plistSizeBadge.textContent = `${sizeKb} KB`;

        statKexts.textContent = res.kextCount;
        statSsdts.textContent = res.ssdtCount;
        statPatches.textContent = res.patchCount;

        renderDiagnostics(res.validation);
        saveSession();
        refreshStepper();
      } else {
        plistCodeContent.textContent = `<!-- Build Error: ${res.error} -->`;
      }
    } catch (err) {
      console.error("Plist build failed:", err);
      plistCodeContent.textContent = "<!-- Error communicating with builder engine -->";
    }
  }

  // Render Diagnostics
  function renderDiagnostics(checks = []) {
    diagnosticsList.innerHTML = "";
    if (!checks.length) {
      diagnosticsList.innerHTML = '<div class="diag-item diag-PASS">All sanity checks passed!</div>';
      return;
    }

    checks.forEach(c => {
      const item = document.createElement("div");
      item.className = `diag-item diag-${c.level}`;
      item.innerHTML = `
        <div class="diag-header">
          <span>[${c.level}] ${c.section}</span>
        </div>
        <div>${c.message}</div>
        ${c.remedy ? `<div class="diag-remedy">&rarr; Fix: ${c.remedy}</div>` : ''}
      `;
      diagnosticsList.appendChild(item);
    });
  }

  // Download & Copy Plist
  async function triggerDownloadPlist() {
    if (!state.latestXml) {
      await buildAndRefreshPlist();
    }
    if (!state.latestXml) {
      showToast("Could not compile config.plist.");
      return;
    }
    const staged = await fetch("/api/plist/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ xml: state.latestXml })
    }).then((r) => r.json()).catch(() => null);
    if (!staged || !staged.success) {
      showToast((staged && staged.error) || "Could not prepare config.plist.");
      return;
    }
    window.location.href = "/api/plist/export";
    showToast("Saving config.plist…");
  }

  btnDownloadPlist.addEventListener("click", () => {
    // If not compiled yet, compile first then trigger download
    buildAndRefreshPlist().then(triggerDownloadPlist);
  });
  btnDownloadPlist2.addEventListener("click", triggerDownloadPlist);

  btnCopyPlist.addEventListener("click", () => {
    if (state.latestXml) {
      navigator.clipboard.writeText(state.latestXml);
      showToast("Copied full config.plist XML to clipboard!");
    }
  });

  let macosPollTimer = null;

  function formatBytes(n) {
    const bytes = Number(n) || 0;
    if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
    if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
    if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${bytes} B`;
  }

  function formatEta(seconds) {
    if (seconds == null || seconds < 0) return "";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (mins >= 60) return `${Math.floor(mins / 60)}h ${mins % 60}m left`;
    if (mins > 0) return `${mins}m ${secs}s left`;
    return `${secs}s left`;
  }

  function selectedMacos() {
    return state.macosInstallers.find((item) => item.id === state.selectedMacosId) || null;
  }

  function macosDownloadBadges(item) {
    const bits = [];
    if (item.availableOnThisMac) {
      bits.push('<span class="macos-local-badge">On this Mac</span>');
    }
    if (item.downloadStatus === "complete") {
      bits.push('<span class="macos-local-badge macos-cached-badge">Downloaded</span>');
    } else if (item.downloadStatus === "downloading") {
      bits.push('<span class="macos-local-badge macos-partial-badge">Downloading</span>');
    } else if (item.downloadStatus === "partial") {
      bits.push('<span class="macos-local-badge macos-partial-badge">Partial</span>');
    }
    return bits.join(" ");
  }

  function updateMacosButtons(job) {
    const dlBtn = document.getElementById("btn-download-macos");
    const cancelBtn = document.getElementById("btn-cancel-macos");
    const removeBtn = document.getElementById("btn-remove-macos-partial");
    const selected = selectedMacos();
    const busy = job && job.status === "downloading";
    const isPartial = !!(selected && selected.downloadStatus === "partial");
    if (dlBtn) {
      dlBtn.disabled = !selected || busy || (selected.downloadStatus === "complete" && !busy);
      dlBtn.textContent = selected && selected.downloadStatus === "complete"
        ? "Already downloaded"
        : isPartial
          ? "Resume download"
          : "Download selected installer";
    }
    if (cancelBtn) {
      cancelBtn.hidden = !busy;
      cancelBtn.disabled = !busy;
    }
    if (removeBtn) {
      removeBtn.hidden = !isPartial || busy;
      removeBtn.disabled = !isPartial || busy;
    }
  }

  function renderMacosProgress(job) {
    const wrap = document.querySelector(".macos-progress");
    const bar = document.getElementById("macos-progress-bar");
    const label = document.getElementById("macos-progress-label");
    const box = document.getElementById("macos-download-status");
    if (!box) return;
    const selected = selectedMacos();
    if (wrap) wrap.hidden = !(job && (job.status === "downloading" || (job.percent > 0 && job.status !== "idle")));
    if (bar) bar.style.width = `${Math.max(0, Math.min(100, (job && job.percent) || 0))}%`;
    if (label) {
      if (job && (job.status === "downloading" || job.status === "complete")) {
        const speed = job.speedBps ? ` · ${formatBytes(job.speedBps)}/s` : "";
        const eta = job.status === "downloading" && job.etaSeconds != null ? ` · ${formatEta(job.etaSeconds)}` : "";
        label.textContent = `${job.percent || 0}% · ${formatBytes(job.bytesReceived)} / ${formatBytes(job.bytesTotal || job.sizeBytes)}${speed}${eta}`;
      } else {
        label.textContent = "";
      }
    }
    if (job && job.status === "error") {
      box.className = "cpu-match-result match-miss";
      box.textContent = job.error || job.message || "Download failed.";
    } else if (job && job.status === "complete") {
      box.className = "cpu-match-result match-ok";
      box.textContent = job.message || `Cached at ${job.localPath}`;
    } else if (job && job.status === "cancelled") {
      box.className = "cpu-match-result";
      box.textContent = job.message || "Download cancelled. You can resume later.";
    } else if (job && job.status === "downloading") {
      box.className = "cpu-match-result match-ok";
      box.textContent = job.message || "Downloading…";
    } else if (selected && selected.downloadStatus === "complete") {
      box.className = "cpu-match-result match-ok";
      box.textContent = `Already cached: ${selected.localPath || selected.title}`;
    } else if (selected && selected.downloadStatus === "partial") {
      box.className = "cpu-match-result";
      box.textContent = `Partial download ${formatBytes(selected.downloadedBytes)} of ${selected.sizeLabel}. Resume, or remove the leftover file.`;
    } else if (selected) {
      box.className = "cpu-match-result";
      box.textContent = `Ready to download ${selected.title} ${selected.version} (${selected.sizeLabel}).`;
    } else {
      box.className = "cpu-match-result";
      box.textContent = "Select a version to download it into the local cache.";
    }
    updateMacosButtons(job);
  }

  function renderMacosCatalog(data) {
    const status = document.getElementById("macos-catalog-status");
    const list = document.getElementById("macos-catalog-list");
    if (!list) return;
    if (status) {
      status.hidden = true;
      status.textContent = "";
    }
    if (!data || !data.success) {
      if (status) {
        status.hidden = false;
        status.className = "cpu-match-result match-miss";
        status.textContent = (data && data.error) || "Could not list macOS installers.";
      }
      list.innerHTML = "";
      return;
    }
    state.macosInstallers = data.installers || [];
    list.innerHTML = "";
    state.macosInstallers.forEach((item) => {
      const card = document.createElement("div");
      card.className = `macos-build-card ${item.id === state.selectedMacosId ? "active" : ""}`;
      card.innerHTML = `
        <div class="macos-build-title">${item.title} ${item.version} ${macosDownloadBadges(item)}</div>
        <div class="macos-build-meta">Build ${item.build} · ${item.sizeLabel}</div>
      `;
      card.addEventListener("click", () => {
        state.selectedMacosId = item.id;
        saveSession();
        list.querySelectorAll(".macos-build-card").forEach((el) => el.classList.remove("active"));
        card.classList.add("active");
        renderMacosProgress({ status: item.downloadStatus === "complete" ? "complete" : "idle", localPath: item.localPath, percent: item.downloadStatus === "complete" ? 100 : 0, bytesReceived: item.downloadedBytes, bytesTotal: item.sizeBytes });
        showToast(`Selected ${item.title} ${item.version}${item.downloadStatus === "complete" ? " (already cached)" : ""}`);
      });
      list.appendChild(card);
    });
    renderMacosProgress({ status: "idle" });
  }

  function stopMacosPoll() {
    if (macosPollTimer) {
      clearInterval(macosPollTimer);
      macosPollTimer = null;
    }
  }

  async function pollMacosDownload() {
    try {
      const job = await fetch("/api/macos/download/status").then((r) => r.json());
      if (job && job.id) {
        const row = state.macosInstallers.find((item) => item.id === job.id);
        if (row) {
          row.downloadStatus = job.status === "complete" ? "complete" : job.status === "downloading" ? "downloading" : (job.status === "cancelled" || job.status === "error") && job.bytesReceived ? "partial" : row.downloadStatus;
          row.downloadedBytes = job.bytesReceived || row.downloadedBytes;
          row.localPath = job.localPath || row.localPath;
        }
      }
      renderMacosProgress(job);
      if (job && job.status === "downloading") {
        if (!macosPollTimer) macosPollTimer = setInterval(() => pollMacosDownload(), 1000);
      } else {
        const wasPolling = !!macosPollTimer;
        stopMacosPoll();
        if (wasPolling) {
          const catalog = {
            success: true,
            installers: state.macosInstallers,
            majors: [...new Set(state.macosInstallers.map((i) => i.name))],
            localCount: state.macosInstallers.filter((i) => i.availableOnThisMac).length,
            downloadedCount: state.macosInstallers.filter((i) => i.downloadStatus === "complete").length
          };
          renderMacosCatalog(catalog);
          renderMacosProgress(job);
        }
      }
    } catch (err) {
      renderMacosProgress({ status: "error", error: String(err) });
      stopMacosPoll();
    }
  }

  async function loadMacosCatalog(refresh = false) {
    const status = document.getElementById("macos-catalog-status");
    if (status) {
      status.hidden = true;
      status.textContent = "";
    }
    try {
      const res = await fetch(`/api/macos/catalog${refresh ? "?refresh=1" : ""}`).then((r) => r.json());
      renderMacosCatalog(res);
      pollMacosDownload();
    } catch (err) {
      renderMacosCatalog({ success: false, error: String(err) });
    }
  }

  const refreshMacosBtn = document.getElementById("btn-refresh-macos");
  if (refreshMacosBtn) {
    refreshMacosBtn.addEventListener("click", () => loadMacosCatalog(true));
  }

  const downloadMacosBtn = document.getElementById("btn-download-macos");
  if (downloadMacosBtn) {
    downloadMacosBtn.addEventListener("click", async () => {
      const selected = selectedMacos();
      if (!selected) {
        showToast("Select a macOS version first.");
        return;
      }
      downloadMacosBtn.disabled = true;
      const res = await fetch("/api/macos/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: selected.id })
      }).then((r) => r.json());
      renderMacosProgress(res);
      if (!res.success) {
        showToast(res.error || "Could not start download.");
        updateMacosButtons(res);
        return;
      }
      showToast(res.status === "complete" ? "Installer already cached." : `Downloading ${selected.title} ${selected.version}…`);
      pollMacosDownload(false);
    });
  }

  const cancelMacosBtn = document.getElementById("btn-cancel-macos");
  if (cancelMacosBtn) {
    cancelMacosBtn.addEventListener("click", async () => {
      const res = await fetch("/api/macos/download/cancel", { method: "POST" }).then((r) => r.json());
      renderMacosProgress(res);
      showToast("Cancel requested.");
    });
  }

  const removeMacosBtn = document.getElementById("btn-remove-macos-partial");
  if (removeMacosBtn) {
    removeMacosBtn.addEventListener("click", async () => {
      const selected = selectedMacos();
      if (!selected || selected.downloadStatus !== "partial") {
        showToast("Select a partial download to remove.");
        return;
      }
      removeMacosBtn.disabled = true;
      const res = await fetch("/api/macos/download/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: selected.id })
      }).then((r) => r.json());
      if (!res.success) {
        showToast(res.error || "Could not remove partial download.");
        updateMacosButtons(res);
        return;
      }
      selected.downloadStatus = "none";
      selected.downloadedBytes = 0;
      selected.localPath = "";
      showToast("Removed the partial download.");
      loadMacosCatalog(false);
    });
  }

  let selectedUsbVolume = "";

  function renderEfiLog(manifest) {
    const log = document.getElementById("efi-build-log");
    const zipBtn = document.getElementById("btn-download-efi-zip");
    if (!log) return;
    if (!manifest || !manifest.success) {
      log.textContent = (manifest && manifest.error) || "No EFI built yet.";
      if (zipBtn) zipBtn.style.display = "none";
      return;
    }
    const lines = [
      `OpenCore ${manifest.opencoreTag} — built ${manifest.builtAt || ""}`,
      `BOOT/BOOTx64.efi: ${manifest.bootloader && manifest.bootloader.BOOTx64 ? "yes" : "NO"}`,
      `OC/OpenCore.efi: ${manifest.bootloader && manifest.bootloader.OpenCore ? "yes" : "NO"}`,
      `Kexts: ${(manifest.kextsInstalled || []).join(", ") || "(none)"}`,
      `SSDTs: ${(manifest.ssdtsInstalled || []).join(", ") || "(none)"}`,
    ];
    if ((manifest.kextsMissing || []).length) lines.push(`Kext gaps: ${manifest.kextsMissing.join("; ")}`);
    if ((manifest.ssdtsMissing || []).length) lines.push(`SSDT gaps: ${manifest.ssdtsMissing.join("; ")}`);
    lines.push(manifest.resources || "");
    lines.push(manifest.readyForUsb ? "Ready to copy onto a USB volume." : "Build is incomplete.");
    log.textContent = lines.filter(Boolean).join("\n");
    if (zipBtn) zipBtn.style.display = manifest.zipPath ? "inline-flex" : "none";
  }

  async function refreshUsbTargets() {
    const list = document.getElementById("usb-volume-list");
    const diskSelect = document.getElementById("usb-disk-select");
    if (!list) return;
    list.innerHTML = "Scanning mounted external volumes…";
    try {
      const res = await fetch("/api/efi/targets").then(r => r.json());
      list.innerHTML = "";
      (res.volumes || []).forEach(v => {
        const row = document.createElement("label");
        row.className = `usb-volume-item ${selectedUsbVolume === v.mountPoint ? "active" : ""}`;
        row.innerHTML = `<input type="radio" name="usb-volume" value="${v.mountPoint}" ${selectedUsbVolume === v.mountPoint ? "checked" : ""}>
          <div><strong>${v.name}</strong><div class="gpu-card-meta">${v.mountPoint} · ${v.fileSystem || "volume"}</div></div>`;
        row.querySelector("input").addEventListener("change", () => {
          selectedUsbVolume = v.mountPoint;
          document.getElementById("btn-copy-efi").disabled = false;
          list.querySelectorAll(".usb-volume-item").forEach(el => el.classList.remove("active"));
          row.classList.add("active");
        });
        list.appendChild(row);
      });
      if (!list.children.length) {
        list.textContent = "No external volumes mounted. Plug in a USB stick and refresh. You can also Prepare a whole disk below.";
      }
      diskSelect.innerHTML = '<option value="">No whole disk selected</option>';
      (res.disks || []).forEach(d => {
        const opt = document.createElement("option");
        opt.value = d.device;
        opt.textContent = `${d.device} — ${d.name} (${Math.round((d.size || 0) / 1e9)} GB)`;
        diskSelect.appendChild(opt);
      });
    } catch (err) {
      list.textContent = `Could not list volumes: ${err}`;
    }
  }

  document.getElementById("btn-build-efi").addEventListener("click", async () => {
    const log = document.getElementById("efi-build-log");
    log.textContent = "Downloading OpenCore, kexts, and SSDTs. This can take a minute…";
    try {
      const payload = studioBuildPayload();
      payload.opencoreTag = document.getElementById("efi-oc-tag").value.trim();
      const res = await fetch("/api/efi/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }).then(r => r.json());
      renderEfiLog(res);
      state.efiReady = !!res.success;
      refreshStepper();
      showToast(res.success ? "EFI folder built." : (res.error || "EFI build failed"));
    } catch (err) {
      log.textContent = `EFI build failed: ${err}`;
    }
  });

  document.getElementById("btn-refresh-usb").addEventListener("click", refreshUsbTargets);

  document.getElementById("btn-copy-efi").addEventListener("click", async () => {
    const box = document.getElementById("usb-write-log");
    if (!selectedUsbVolume) {
      box.textContent = "Select a mounted USB volume first.";
      return;
    }
    box.textContent = `Copying EFI to ${selectedUsbVolume}…`;
    const res = await fetch("/api/efi/copy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mountPoint: selectedUsbVolume })
    }).then(r => r.json());
    box.className = `cpu-match-result ${res.success ? "match-ok" : "match-miss"}`;
    box.textContent = res.message || res.error || JSON.stringify(res);
    showToast(res.success ? "USB EFI copied." : (res.error || "Copy failed"));
  });

  document.getElementById("btn-prepare-usb").addEventListener("click", async () => {
    const box = document.getElementById("usb-write-log");
    const device = document.getElementById("usb-disk-select").value;
    const confirm = document.getElementById("usb-erase-confirm").value.trim();
    if (!device) {
      box.textContent = "Select a whole external disk.";
      return;
    }
    box.textContent = `Erasing ${device} and copying EFI…`;
    const res = await fetch("/api/efi/prepare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device, confirm })
    }).then(r => r.json());
    box.className = `cpu-match-result ${res.success ? "match-ok" : "match-miss"}`;
    box.textContent = res.message || res.error || JSON.stringify(res);
    showToast(res.success ? "USB prepared and EFI copied." : (res.error || "Prepare failed"));
    refreshUsbTargets();
  });

  btnValidate.addEventListener("click", () => {
    goToTab("preview");
  });

  // Start Application
  initApp();
});
