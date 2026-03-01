const $ = (id) => document.getElementById(id);

const state = {
  dockerSock: false,
};

function selectedMode() {
  return document.querySelector('input[name="mode"]:checked')?.value || "external";
}

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

function setText(id, value) {
  $(id).textContent = value;
}

function syncModePanels() {
  const mode = selectedMode();
  $("external-panel").classList.toggle("hidden", mode !== "external");
  $("embedded-panel").classList.toggle("hidden", mode !== "embedded");
}

async function loadStatus() {
  const [install, health] = await Promise.all([
    api("/api/install/status"),
    api("/api/addon/health"),
  ]);

  state.dockerSock = Boolean(install.docker_sock_available);
  setText("status-mode", install.mode);
  setText("status-docker", String(install.docker_sock_available));
  setText("status-broker", String(install.broker_running));
  setText("status-mqtt", String(install.mqtt_connected));
  setText("status-health", health.status);
  setText("status-error", install.last_error || "none");

  const restartButton = $("restart-broker");
  restartButton.classList.toggle("hidden", !state.dockerSock);

  document.querySelectorAll('input[name="mode"]').forEach((radio) => {
    radio.checked = radio.value === install.mode;
  });
  syncModePanels();
}

async function testExternal() {
  const payload = {
    host: $("external-host").value.trim(),
    port: Number($("external-port").value),
    tls: $("external-tls").checked,
    username: $("external-user").value.trim() || null,
    password: $("external-pass").value || null,
  };

  const result = await api("/api/install/test-external", "POST", payload);
  $("external-result").textContent = result.ok
    ? "External connection test passed."
    : `Connection test failed: ${result.reason || "unknown"}`;
}

async function applyExternal() {
  const payload = {
    mode: "external",
    external: {
      host: $("external-host").value.trim(),
      port: Number($("external-port").value),
      tls: $("external-tls").checked,
      username: $("external-user").value.trim() || null,
      password: $("external-pass").value || null,
    },
    base_topic: $("base-topic").value.trim() || "synthia",
    ha_discovery_prefix: $("ha-prefix").value.trim() || "homeassistant",
    qos_default: Number($("qos-default").value),
  };

  const result = await api("/api/install/apply", "POST", payload);
  $("external-result").textContent = result.ok
    ? "External mode applied."
    : "Apply failed.";
}

async function applyEmbedded() {
  const payload = {
    mode: "embedded",
    embedded: {
      allow_anonymous: $("embedded-anon").checked,
      persistence: $("embedded-persist").checked,
      log_type: $("embedded-log").value.trim() || "stdout",
      port: Number($("embedded-port").value),
      admin_user: $("embedded-user").value.trim() || null,
      admin_pass: $("embedded-pass").value || null,
    },
    base_topic: $("base-topic-embedded").value.trim() || "synthia",
    ha_discovery_prefix: $("ha-prefix-embedded").value.trim() || "homeassistant",
    qos_default: Number($("qos-default-embedded").value),
  };

  const result = await api("/api/install/apply", "POST", payload);
  const operatorWrap = $("operator-wrap");
  $("embedded-result").textContent = result.ok ? "Embedded mode applied." : "Apply failed.";

  if (result.requires_operator_action && result.operator_action) {
    operatorWrap.classList.remove("hidden");
    $("operator-action").value = result.operator_action;
  } else {
    operatorWrap.classList.add("hidden");
    $("operator-action").value = "";
  }

  if (result.warnings?.length) {
    $("embedded-result").textContent += ` Warnings: ${result.warnings.join(" | ")}`;
  }
}

async function restartBroker() {
  const result = await api("/api/broker/restart", "POST", {});
  $("embedded-result").textContent = result.ok
    ? "Broker restarted and ready."
    : `Restart failed: ${result.reason || "unknown"}`;
}

async function loadFinish() {
  const [config, health] = await Promise.all([
    api("/api/addon/config/effective"),
    api("/api/addon/health"),
  ]);
  $("finish-output").textContent = JSON.stringify({ config, health }, null, 2);
}

async function publishTest() {
  const payload = {
    topic: $("pub-topic").value.trim(),
    payload: parsePayload($("pub-payload").value),
    retain: $("pub-retain").checked,
    qos: Number($("pub-qos").value),
  };
  const result = await api("/api/mqtt/publish", "POST", payload);
  $("publish-result").textContent = result.ok ? "Publish succeeded." : "Publish failed.";
}

function bindEvents() {
  $("refresh-status").addEventListener("click", () => run(loadStatus));
  $("test-external").addEventListener("click", () => run(testExternal));
  $("apply-external").addEventListener("click", () => run(applyExternal));
  $("apply-embedded").addEventListener("click", () => run(applyEmbedded));
  $("restart-broker").addEventListener("click", () => run(restartBroker));
  $("load-finish").addEventListener("click", () => run(loadFinish));
  $("test-publish").addEventListener("click", () => run(publishTest));
  document.querySelectorAll('input[name="mode"]').forEach((radio) => {
    radio.addEventListener("change", syncModePanels);
  });
}

async function run(action) {
  try {
    await action();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    $("external-result").textContent = message;
    $("embedded-result").textContent = message;
    $("publish-result").textContent = message;
  }
}

bindEvents();
syncModePanels();
run(loadStatus);
