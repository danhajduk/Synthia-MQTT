const $ = (id) => document.getElementById(id);
const STORAGE_KEY = "mqtt_setup_state_v1";
const MAX_STEP = 6;

const state = {
  currentStep: 1,
  mode: "external",
  testPassed: false,
  applyDone: false,
  registerDone: false,
  viewMode: "setup",
  external: {
    host: "10.0.0.100",
    port: 1883,
    tls: false,
    username: "",
    hasPassword: false,
    directAccessMode: "gateway_only",
    baseTopic: "synthia",
    haPrefix: "homeassistant",
    qos: 1,
    allowUnvalidated: false,
  },
  embedded: {
    allowAnonymous: false,
    persistence: true,
    logType: "stdout",
    port: 1883,
    adminUser: "",
    hasAdminPass: false,
    baseTopic: "synthia",
    haPrefix: "homeassistant",
    qos: 1,
  },
  core: {
    registerEnabled: false,
    coreBaseUrl: "http://localhost:3000",
    addonBaseUrl: "http://localhost:18080",
    hasToken: false,
  },
};

function parsePayload(raw) {
  const input = raw.trim();
  if (!input) return "";
  try {
    return JSON.parse(input);
  } catch {
    return input;
  }
}

async function api(path, method = "GET", body) {
  const response = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const errText = await response.text();
    throw new Error(errText || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

function selectedMode() {
  return document.querySelector('input[name="mode"]:checked')?.value || "external";
}

function setText(id, value) {
  $(id).textContent = value;
}

function setResult(id, text) {
  $(id).textContent = text;
}

function setGlobalError(message) {
  ["details-error", "mode-save-result", "test-result", "apply-result", "register-result", "publish-result"].forEach((id) => {
    const element = $(id);
    if (element) {
      element.textContent = message;
    }
  });
}

function saveState() {
  const persist = {
    ...state,
    external: { ...state.external },
    embedded: { ...state.embedded },
    core: { ...state.core },
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(persist));
}

function loadSavedState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    Object.assign(state, parsed);
    state.currentStep = Math.min(Math.max(Number(state.currentStep) || 1, 1), MAX_STEP);
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function fillFieldsFromState() {
  document.querySelectorAll('input[name="mode"]').forEach((radio) => {
    radio.checked = radio.value === state.mode;
  });
  $("external-direct-access-mode").addEventListener("change", () => {
    snapshotFieldsToState();
    syncModeUI();
  });

  $("external-host").value = state.external.host;
  $("external-port").value = String(state.external.port);
  $("external-tls").checked = Boolean(state.external.tls);
  $("external-user").value = state.external.username;
  $("external-pass").value = "";
  $("external-direct-access-mode").value = state.external.directAccessMode || "gateway_only";
  $("external-base-topic").value = state.external.baseTopic;
  $("external-ha-prefix").value = state.external.haPrefix;
  $("external-qos").value = String(state.external.qos);
  $("allow-unvalidated").checked = Boolean(state.external.allowUnvalidated);

  $("embedded-anon").checked = Boolean(state.embedded.allowAnonymous);
  $("embedded-persist").checked = Boolean(state.embedded.persistence);
  $("embedded-log").value = state.embedded.logType;
  $("embedded-port").value = String(state.embedded.port);
  $("embedded-user").value = state.embedded.adminUser;
  $("embedded-pass").value = "";
  $("embedded-base-topic").value = state.embedded.baseTopic;
  $("embedded-ha-prefix").value = state.embedded.haPrefix;
  $("embedded-qos").value = String(state.embedded.qos);

  $("register-enabled").checked = Boolean(state.core.registerEnabled);
  $("core-base-url").value = state.core.coreBaseUrl;
  $("addon-base-url").value = state.core.addonBaseUrl;
  $("core-token").value = "";
}

function snapshotFieldsToState() {
  state.mode = selectedMode();
  state.external.host = $("external-host").value.trim();
  state.external.port = Number($("external-port").value);
  state.external.tls = $("external-tls").checked;
  state.external.username = $("external-user").value.trim();
  state.external.hasPassword = Boolean($("external-pass").value);
  state.external.directAccessMode = $("external-direct-access-mode").value || "gateway_only";
  state.external.baseTopic = $("external-base-topic").value.trim() || "synthia";
  state.external.haPrefix = $("external-ha-prefix").value.trim() || "homeassistant";
  state.external.qos = Number($("external-qos").value);
  state.external.allowUnvalidated = $("allow-unvalidated").checked;

  state.embedded.allowAnonymous = $("embedded-anon").checked;
  state.embedded.persistence = $("embedded-persist").checked;
  state.embedded.logType = $("embedded-log").value.trim() || "stdout";
  state.embedded.port = Number($("embedded-port").value);
  state.embedded.adminUser = $("embedded-user").value.trim();
  state.embedded.hasAdminPass = Boolean($("embedded-pass").value);
  state.embedded.baseTopic = $("embedded-base-topic").value.trim() || "synthia";
  state.embedded.haPrefix = $("embedded-ha-prefix").value.trim() || "homeassistant";
  state.embedded.qos = Number($("embedded-qos").value);

  state.core.registerEnabled = $("register-enabled").checked;
  state.core.coreBaseUrl = $("core-base-url").value.trim();
  state.core.addonBaseUrl = $("addon-base-url").value.trim();
  state.core.hasToken = Boolean($("core-token").value);
}

function setViewMode(viewMode) {
  state.viewMode = viewMode;
  $("setup-view").classList.toggle("hidden", viewMode !== "setup");
  $("dashboard-view").classList.toggle("hidden", viewMode !== "dashboard");
  saveState();
}

function syncModeUI() {
  const mode = selectedMode();
  state.mode = mode;
  $("external-form").classList.toggle("hidden", mode !== "external");
  $("embedded-form").classList.toggle("hidden", mode !== "embedded");
  $("restart-broker").classList.toggle("hidden", mode !== "embedded");
  $("allow-unvalidated-wrap").classList.toggle("hidden", mode !== "external");

  const registerToggle = $("register-enabled");
  if (mode === "embedded") {
    registerToggle.checked = true;
    registerToggle.disabled = true;
  } else {
    registerToggle.disabled = false;
  }
  setResult("mode-support", mode === "embedded" ? "Direct MQTT expected: yes" : "Direct MQTT expected: no (gateway mode)");
  if (mode === "external") {
    $("external-direct-mode-note").textContent =
      state.external.directAccessMode === "manual_direct_access"
        ? "Manual direct mode: operator must provision broker-side users and record manual mapping per registration."
        : "Gateway-only mode: addon direct MQTT credentials are not provisioned for external broker mode.";
  }
  snapshotFieldsToState();
  saveState();
}

function setStep(step) {
  state.currentStep = Math.min(Math.max(step, 1), MAX_STEP);
  for (let i = 1; i <= MAX_STEP; i += 1) {
    $(`step-${i}`).classList.toggle("hidden", i !== state.currentStep);
    const marker = $(`marker-${i}`);
    marker.classList.toggle("active", i === state.currentStep);
    marker.classList.toggle("done", i < state.currentStep);
  }
  saveState();
}

function validationError(message) {
  setResult("details-error", message);
  return false;
}

function validateDetails() {
  snapshotFieldsToState();
  if (state.mode === "external") {
    if (!state.external.host) return validationError("External host is required.");
    if (!Number.isInteger(state.external.port) || state.external.port < 1 || state.external.port > 65535) {
      return validationError("External port must be between 1 and 65535.");
    }
    if (!Number.isInteger(state.external.qos) || state.external.qos < 0 || state.external.qos > 2) {
      return validationError("External QoS must be 0, 1, or 2.");
    }
  } else {
    if (!Number.isInteger(state.embedded.port) || state.embedded.port < 1 || state.embedded.port > 65535) {
      return validationError("Embedded broker port must be between 1 and 65535.");
    }
    if (!state.embedded.allowAnonymous && !state.embedded.adminUser) {
      return validationError("Admin user is required when anonymous mode is disabled.");
    }
    if (!Number.isInteger(state.embedded.qos) || state.embedded.qos < 0 || state.embedded.qos > 2) {
      return validationError("Embedded QoS must be 0, 1, or 2.");
    }
  }
  setResult("details-error", "Details look valid.");
  saveState();
  return true;
}

function updateSetupStatus(install, health) {
  setText("status-setup-state", install.setup_state);
  setText("status-setup-guidance", install.setup_guidance);
  setText("status-mode", install.mode);
  setText("status-external-direct-mode", install.external_direct_access_mode);
  setText("status-direct-summary", install.direct_access_summary);
  setText("status-configured", String(install.configured));
  setText("status-verified", String(install.verified));
  setText("status-registered", String(install.registered_to_core));
  setText("status-direct-mqtt", String(install.direct_mqtt_supported));
  setText("status-docker-sock", String(install.docker_sock_available));
  setText("status-broker-running", String(install.broker_running));
  setText("status-mqtt", String(install.mqtt_connected));
  setText("status-health", health.status);
  setText("status-error", install.last_error || "none");
}

function updateDashboardStatus(install, health) {
  setText("dash-status-setup-state", install.setup_state);
  setText("dash-status-setup-guidance", install.setup_guidance);
  setText("dash-status-mode", install.mode);
  setText("dash-status-external-direct-mode", install.external_direct_access_mode);
  setText("dash-status-direct-summary", install.direct_access_summary);
  setText("dash-status-configured", String(install.configured));
  setText("dash-status-verified", String(install.verified));
  setText("dash-status-registered", String(install.registered_to_core));
  setText("dash-status-direct-mqtt", String(install.direct_mqtt_supported));
  setText("dash-status-docker-sock", String(install.docker_sock_available));
  setText("dash-status-broker-running", String(install.broker_running));
  setText("dash-status-mqtt", String(install.mqtt_connected));
  setText("dash-status-health", health.status);
  setText("dash-status-error", install.last_error || "none");
}

async function loadStatusSnapshot() {
  const [install, health] = await Promise.all([api("/api/install/status"), api("/api/addon/health")]);
  updateSetupStatus(install, health);
  updateDashboardStatus(install, health);
  return { install, health };
}

async function runTestStep() {
  snapshotFieldsToState();
  if (state.mode === "external") {
    const payload = {
      host: state.external.host,
      port: state.external.port,
      tls: state.external.tls,
      username: state.external.username || null,
      password: $("external-pass").value || null,
    };
    const result = await api("/api/install/test-external", "POST", payload);
    state.testPassed = result.ok;
    setResult(
      "test-result",
      result.ok
        ? `External test passed (${result.diagnostic_code}).`
        : `External test failed (${result.diagnostic_code}): ${result.reason || "unknown"}`
    );
    $("external-pass").value = "";
    state.external.hasPassword = false;
  } else {
    if (!validateDetails()) return;
    state.testPassed = true;
    setResult("test-result", "Embedded config syntax check passed.");
  }
  saveState();
  await loadStatusSnapshot();
}

async function saveModeSelection() {
  snapshotFieldsToState();
  const result = await api("/api/install/mode", "POST", {
    mode: state.mode,
    external_direct_access_mode: state.external.directAccessMode,
  });
  setResult(
    "mode-save-result",
    `Mode saved: ${result.mode}. External direct mode: ${result.external_direct_access_mode}. Direct MQTT expected: ${result.direct_mqtt_supported ? "yes" : "no"}.`
  );
  await loadStatusSnapshot();
}

function buildApplyPayload() {
  if (state.mode === "external") {
    return {
      mode: "external",
      external: {
        host: state.external.host,
        port: state.external.port,
        tls: state.external.tls,
        username: state.external.username || null,
      password: $("external-pass").value || null,
    },
      external_direct_access_mode: state.external.directAccessMode,
      base_topic: state.external.baseTopic,
      ha_discovery_prefix: state.external.haPrefix,
      qos_default: state.external.qos,
      allow_unvalidated: state.external.allowUnvalidated,
    };
  }
  return {
    mode: "embedded",
    embedded: {
      allow_anonymous: state.embedded.allowAnonymous,
      persistence: state.embedded.persistence,
      log_type: state.embedded.logType,
      port: state.embedded.port,
      admin_user: state.embedded.adminUser || null,
      admin_pass: $("embedded-pass").value || null,
    },
    base_topic: state.embedded.baseTopic,
    ha_discovery_prefix: state.embedded.haPrefix,
    qos_default: state.embedded.qos,
  };
}

async function runApplyStep() {
  snapshotFieldsToState();
  if (!validateDetails()) return;
  const payload = buildApplyPayload();
  const result = await api("/api/install/apply", "POST", payload);
  state.applyDone = Boolean(result.ok);
  const warnings = result.warnings?.length ? ` Warnings: ${result.warnings.join(" | ")}` : "";
  setResult("apply-result", result.ok ? `Apply succeeded.${warnings}` : `Apply failed.${warnings}`);

  if (result.requires_operator_action && result.operator_action) {
    $("operator-wrap").classList.remove("hidden");
    $("operator-action").value = result.operator_action;
  } else {
    $("operator-wrap").classList.add("hidden");
    $("operator-action").value = "";
  }

  $("external-pass").value = "";
  $("embedded-pass").value = "";
  state.external.hasPassword = false;
  state.embedded.hasAdminPass = false;
  saveState();
  await loadStatusSnapshot();
}

async function runBrokerRestart() {
  const result = await api("/api/broker/restart", "POST", {});
  setResult("apply-result", result.ok ? "Broker restarted and ready." : `Restart failed: ${result.reason || "unknown"}`);
  await loadStatusSnapshot();
}

async function runCoreRegistration() {
  snapshotFieldsToState();
  if (!$("register-enabled").checked) {
    state.registerDone = false;
    setResult("register-result", "Core registration skipped.");
    saveState();
    return;
  }
  const payload = {
    core_base_url: state.core.coreBaseUrl,
    base_url: state.core.addonBaseUrl,
    addon_id: "mqtt",
    auth_token: $("core-token").value || null,
  };
  const result = await api("/api/install/register-core", "POST", payload);
  state.registerDone = Boolean(result.ok);
  setResult("register-result", result.ok ? "Core registration succeeded." : "Core registration failed.");
  $("core-token").value = "";
  state.core.hasToken = false;
  saveState();
  await loadStatusSnapshot();
}

async function loadDoneSummary() {
  snapshotFieldsToState();
  const [install, health, effective] = await Promise.all([
    api("/api/install/status"),
    api("/api/addon/health"),
    api("/api/addon/config/effective"),
  ]);

  const mode = selectedMode();
  const host = mode === "external" ? state.external.host : "mosquitto";
  const port = mode === "external" ? state.external.port : state.embedded.port;
  const coreUrl = state.core.coreBaseUrl || "-";
  const addonUrl = state.core.addonBaseUrl || "-";

  setText("summary-mode", mode);
  setText("summary-host", host || "-");
  setText("summary-port", String(port || "-"));
  setText("summary-core-url", coreUrl);
  setText("summary-addon-url", addonUrl);
  setText("summary-pass", "masked");

  $("done-output").textContent = JSON.stringify(
    {
      install,
      health,
      effective_config: effective,
    },
    null,
    2
  );
}

async function copyFrom(targetId) {
  const value = $(targetId).textContent || "";
  await navigator.clipboard.writeText(value);
}

function resetStateDefaults() {
  Object.assign(state, {
    currentStep: 1,
    mode: "external",
    testPassed: false,
    applyDone: false,
    registerDone: false,
    viewMode: "setup",
    external: {
      host: "10.0.0.100",
      port: 1883,
      tls: false,
      username: "",
      hasPassword: false,
      directAccessMode: "gateway_only",
      baseTopic: "synthia",
      haPrefix: "homeassistant",
      qos: 1,
      allowUnvalidated: false,
    },
    embedded: {
      allowAnonymous: false,
      persistence: true,
      logType: "stdout",
      port: 1883,
      adminUser: "",
      hasAdminPass: false,
      baseTopic: "synthia",
      haPrefix: "homeassistant",
      qos: 1,
    },
    core: {
      registerEnabled: false,
      coreBaseUrl: "http://localhost:3000",
      addonBaseUrl: "http://localhost:18080",
      hasToken: false,
    },
  });
}

async function resetSetup() {
  await api("/api/install/reset", "POST", {});
  localStorage.removeItem(STORAGE_KEY);
  resetStateDefaults();
  fillFieldsFromState();
  syncModeUI();
  setStep(1);
  setViewMode("setup");
  setResult("details-error", "Setup state reset.");
  setResult("test-result", "-");
  setResult("apply-result", "-");
  setResult("register-result", "-");
  await loadStatusSnapshot();
}

async function loadDashboardSummary() {
  const [config, health, install] = await Promise.all([
    api("/api/addon/config/effective"),
    api("/api/addon/health"),
    api("/api/install/status"),
  ]);
  $("finish-output").textContent = JSON.stringify({ config, health, install }, null, 2);
}

async function loadRegistrationInspector() {
  const response = await api("/api/mqtt/registrations");
  const setup = response.setup || {};
  const registrations = Array.isArray(response.registrations) ? response.registrations : [];
  setText("reg-setup-state", String(setup.setup_state || "-"));
  setText("reg-broker-mode", String(setup.broker_mode || "-"));
  setText("reg-broker-reachable", String(setup.broker_reachable ?? "-"));
  setText("reg-direct-supported", String(setup.direct_mqtt_supported ?? "-"));
  setText("reg-broker-profile", String(setup.broker_profile || "-"));
  setText("reg-count", String(registrations.length));
  $("registration-output").textContent = JSON.stringify(registrations, null, 2);
}

async function loadPublishTraces() {
  const response = await api("/api/mqtt/publish-traces?limit=100");
  const traces = Array.isArray(response.traces) ? response.traces : [];
  const denied = traces.filter((trace) => trace.outcome === "denied").length;
  const errors = traces.filter((trace) => trace.outcome === "error").length;
  const last = traces.length > 0 ? `${traces[0].operation} (${traces[0].outcome})` : "-";
  setText("trace-count", String(traces.length));
  setText("trace-denied-count", String(denied));
  setText("trace-error-count", String(errors));
  setText("trace-last-op", last);
  $("trace-output").textContent = JSON.stringify(traces, null, 2);
}

async function loadTopicExplorer() {
  const response = await api("/api/mqtt/topic-explorer");
  setText("topic-base", String(response.base_topic || "-"));
  setText("topic-reserved-count", String(Array.isArray(response.reserved_namespaces) ? response.reserved_namespaces.length : 0));
  setText("topic-addon-count", String(Array.isArray(response.addon_namespaces) ? response.addon_namespaces.length : 0));
  setText("topic-lifecycle-count", String(Array.isArray(response.lifecycle_topics) ? response.lifecycle_topics.length : 0));
  setText("topic-family-count", String(Array.isArray(response.topic_families) ? response.topic_families.length : 0));
  $("topic-explorer-output").textContent = JSON.stringify(
    {
      reserved_namespaces: response.reserved_namespaces || [],
      addon_namespaces: response.addon_namespaces || [],
      lifecycle_topics: response.lifecycle_topics || [],
      registration_mappings: response.registration_mappings || [],
      topic_families: response.topic_families || [],
    },
    null,
    2
  );
}

async function loadMetrics() {
  const response = await api("/api/mqtt/metrics");
  setText("metrics-publish-count", String(response.publish_count ?? 0));
  setText("metrics-denied-count", String(response.denied_publish_count ?? 0));
  setText("metrics-reconnect-count", String(response.reconnect_count ?? 0));
  setText("metrics-active-registrations", String(response.active_registrations ?? 0));
  setText("metrics-broker-mode", String(response.broker_mode_summary?.mode || "-"));
  setText("metrics-direct-model", String(response.broker_mode_summary?.direct_access_model || "-"));
  $("metrics-output").textContent = JSON.stringify(response.per_addon_usage || [], null, 2);
}

async function publishTest() {
  const payload = {
    topic: $("pub-topic").value.trim(),
    payload: parsePayload($("pub-payload").value),
    retain: $("pub-retain").checked,
    qos: Number($("pub-qos").value),
  };
  const result = await api("/api/mqtt/publish", "POST", payload);
  setResult("publish-result", result.ok ? "Publish succeeded." : "Publish failed.");
}

function bindSetupNavigation() {
  $("next-1").addEventListener("click", () =>
    run(async () => {
      await saveModeSelection();
      setStep(2);
    })
  );
  $("back-2").addEventListener("click", () => setStep(1));
  $("next-2").addEventListener("click", () => {
    if (validateDetails()) setStep(3);
  });
  $("back-3").addEventListener("click", () => setStep(2));
  $("next-3").addEventListener("click", () => setStep(4));
  $("back-4").addEventListener("click", () => setStep(3));
  $("next-4").addEventListener("click", () => setStep(5));
  $("back-5").addEventListener("click", () => setStep(4));
  $("next-5").addEventListener("click", async () => {
    setStep(6);
    await run(loadDoneSummary);
  });
  $("back-6").addEventListener("click", () => setStep(5));
}

function bindEvents() {
  document.querySelectorAll('input[name="mode"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      syncModeUI();
      setResult("details-error", "-");
    });
  });

  $("save-mode").addEventListener("click", () => run(saveModeSelection));
  $("refresh-status").addEventListener("click", () => run(loadStatusSnapshot));
  $("run-test").addEventListener("click", () => run(runTestStep));
  $("run-apply").addEventListener("click", () => run(runApplyStep));
  $("restart-broker").addEventListener("click", () => run(runBrokerRestart));
  $("run-register").addEventListener("click", () => run(runCoreRegistration));
  $("reload-done").addEventListener("click", () => run(loadDoneSummary));
  $("reset-setup").addEventListener("click", () => run(resetSetup));

  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.getAttribute("data-copy");
      if (!targetId) return;
      run(async () => {
        await copyFrom(targetId);
        setResult("register-result", `Copied ${targetId}.`);
      });
    });
  });

  $("refresh-dashboard").addEventListener("click", () => run(loadStatusSnapshot));
  $("open-setup").addEventListener("click", () => {
    setViewMode("setup");
    setStep(1);
    run(loadStatusSnapshot);
  });
  $("load-finish").addEventListener("click", () => run(loadDashboardSummary));
  $("refresh-registrations").addEventListener("click", () => run(loadRegistrationInspector));
  $("refresh-traces").addEventListener("click", () => run(loadPublishTraces));
  $("refresh-topic-explorer").addEventListener("click", () => run(loadTopicExplorer));
  $("refresh-metrics").addEventListener("click", () => run(loadMetrics));
  $("test-publish").addEventListener("click", () => run(publishTest));

  bindSetupNavigation();
}

async function run(action) {
  try {
    await action();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setGlobalError(message);
  }
}

async function initialize() {
  loadSavedState();
  fillFieldsFromState();
  bindEvents();
  syncModeUI();
  setStep(state.currentStep);

  const forceSetup = new URLSearchParams(window.location.search).get("setup") === "1";
  const { install } = await loadStatusSnapshot();

  const setupComplete = ["ready", "degraded"].includes(String(install.setup_state));
  if (forceSetup || !setupComplete) {
    setViewMode("setup");
    await loadDoneSummary();
  } else {
    setViewMode("dashboard");
    await Promise.all([
      loadDashboardSummary(),
      loadRegistrationInspector(),
      loadPublishTraces(),
      loadTopicExplorer(),
      loadMetrics(),
    ]);
  }
}

run(initialize);
