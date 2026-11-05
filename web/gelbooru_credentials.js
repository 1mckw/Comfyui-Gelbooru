import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

/*
 * Gelbooru credentials UI.
 *
 * ComfyUI writes every node input into the `prompt` chunk and every widget
 * value into the `workflow` chunk of the PNG metadata, so an API key typed into
 * the node widget leaks into every saved image and every exported workflow.
 *
 * The key is therefore kept on the server (user/default/gelbooru_credentials.json)
 * and the node only carries a profile name. This script hides the legacy widget,
 * shows the key status and provides the dialog that writes the key server side.
 *
 * Layout note: the DOM widget must stay the LAST entry of `node.widgets`, see
 * web/tag_rules.js for the serialization details.
 */

const NODE_TYPES = new Set(["Gelbooru (Random)", "Gelbooru (ID)"]);
const API_URL = "/gelbooru/credentials";
const LEGACY_WIDGET = "api_credentials";
const PROFILE_WIDGET = "credentials_profile";
const DEFAULT_PROFILE = "default";
const STYLE_ID = "gelbooru-credentials-style";
const PANEL_HEIGHT = 42;

const CSS = `
.gelcreds {
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  padding: 2px 6px 4px;
  color: var(--input-text, #ddd);
  font-family: inherit;
  font-size: 12px;
}
.gelcreds-row { display: flex; align-items: center; gap: 8px; height: 32px; }
.gelcreds-dot { width: 8px; height: 8px; border-radius: 50%; background: #888; flex: 0 0 auto; }
.gelcreds-dot.ok { background: #4caf50; }
.gelcreds-dot.warn { background: #e0a030; }
.gelcreds-dot.bad { background: #e05555; }
.gelcreds-text {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: var(--input-text, #ddd);
  font-size: 11px;
}
.gelcreds-btn {
  flex: 0 0 auto;
  padding: 3px 10px;
  border: 1px solid var(--border-color, #4e4e4e);
  border-radius: 4px;
  background: var(--comfy-menu-bg, #353535);
  color: var(--input-text, #ddd);
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
}
.gelcreds-btn:hover { border-color: #4f8cff; color: #fff; }
.gelcreds-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, .55);
}
.gelcreds-card {
  width: 420px;
  max-width: calc(100vw - 32px);
  padding: 16px;
  border: 1px solid var(--border-color, #4e4e4e);
  border-radius: 8px;
  background: var(--comfy-menu-bg, #353535);
  color: var(--input-text, #ddd);
  font-family: inherit;
  font-size: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, .5);
}
.gelcreds-card h3 { margin: 0 0 8px; font-size: 14px; font-weight: 600; }
.gelcreds-card p { margin: 0 0 12px; color: var(--descrip-text, #999); font-size: 11px; line-height: 1.45; }
.gelcreds-field { display: flex; flex-direction: column; gap: 3px; margin-bottom: 10px; }
.gelcreds-field label { color: var(--descrip-text, #999); font-size: 11px; }
.gelcreds-input {
  box-sizing: border-box;
  width: 100%;
  padding: 5px 8px;
  background: var(--comfy-input-bg, #222);
  color: var(--input-text, #ddd);
  border: 1px solid var(--border-color, #4e4e4e);
  border-radius: 4px;
  font-family: inherit;
  font-size: 12px;
  outline: none;
}
.gelcreds-input:focus { border-color: #4f8cff; }
.gelcreds-error { min-height: 14px; color: var(--error-text, #f44); font-size: 11px; }
.gelcreds-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px; }
.gelcreds-actions .gelcreds-btn.danger { color: #e08080; border-color: rgba(255, 90, 90, .45); }
.gelcreds-actions .gelcreds-btn.danger:hover { background: rgba(255, 90, 90, .15); border-color: rgba(255, 90, 90, .7); }
`;

function ensureStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = CSS;
  document.head.appendChild(style);
}

function getWidget(node, name) {
  return (node.widgets || []).find((widget) => widget && widget.name === name);
}

function hideWidget(widget) {
  if (!widget) return;
  widget.options = widget.options || {};
  widget.options.hidden = true;
  widget.options.collapsed = true;
  widget.hidden = true;
  widget.type = "converted-widget";
  widget.serialize = true;
  widget.computeSize = () => [0, -4];
  widget.draw = () => {};
}

function parseLegacy(value) {
  const text = String(value ?? "").trim();
  if (!text) return { api_key: "", user_id: "" };
  if (text.startsWith("{")) {
    try {
      const data = JSON.parse(text);
      return {
        api_key: String(data?.api_key ?? "").trim(),
        user_id: String(data?.user_id ?? "").trim(),
      };
    } catch (error) {
      return { api_key: "", user_id: "" };
    }
  }
  const params = new URLSearchParams(text.replace(/^&+/, ""));
  return {
    api_key: (params.get("api_key") ?? "").trim(),
    user_id: (params.get("user_id") ?? "").trim(),
  };
}

function notify(message, severity = "success") {
  try {
    app.extensionManager?.toast?.add?.({ severity, summary: message, life: 5000 });
  } catch (error) {
    /* older frontend without toasts */
  }
  console.info(`[Gelbooru] ${message}`);
}

async function fetchStatus(profile) {
  const response = await api.fetchApi(`${API_URL}?profile=${encodeURIComponent(profile || DEFAULT_PROFILE)}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return await response.json();
}

async function saveCredentials(profile, apiKey, userId) {
  const response = await api.fetchApi(API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile, api_key: apiKey, user_id: userId }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return await response.json();
}

async function deleteCredentials(profile) {
  const response = await api.fetchApi(`${API_URL}?profile=${encodeURIComponent(profile || DEFAULT_PROFILE)}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return await response.json();
}

function describeStatus(status) {
  if (!status) return { text: "API key: unknown", tone: "warn" };
  if (status.source === "env") {
    return { text: "API key: from environment variables", tone: "ok" };
  }
  if (status.api_key_set) {
    const hint = status.api_key_hint ? ` (${status.api_key_hint})` : "";
    const user = status.user_id ? ` - user ${status.user_id}` : "";
    return { text: `API key: saved${hint}${user}`, tone: "ok" };
  }
  return { text: "API key: not set", tone: "bad" };
}

function openDialog(node, state) {
  ensureStyles();
  if (state.dialog) return;

  const overlay = document.createElement("div");
  overlay.className = "gelcreds-overlay";

  const card = document.createElement("div");
  card.className = "gelcreds-card";

  const title = document.createElement("h3");
  title.textContent = "Gelbooru API key";

  const hint = document.createElement("p");
  hint.textContent =
    "The key is stored on the server (user/default/gelbooru_credentials.json) and is never written into workflows or PNG metadata.";

  const makeField = (labelText, input) => {
    const field = document.createElement("div");
    field.className = "gelcreds-field";
    const label = document.createElement("label");
    label.textContent = labelText;
    field.append(label, input);
    return field;
  };

  const profileInput = document.createElement("input");
  profileInput.className = "gelcreds-input";
  profileInput.type = "text";
  profileInput.value = state.profile || DEFAULT_PROFILE;
  profileInput.placeholder = DEFAULT_PROFILE;

  const keyInput = document.createElement("input");
  keyInput.className = "gelcreds-input";
  keyInput.type = "password";
  keyInput.placeholder = "paste your api_key";
  keyInput.autocomplete = "off";
  keyInput.spellcheck = false;

  const userInput = document.createElement("input");
  userInput.className = "gelcreds-input";
  userInput.type = "text";
  userInput.value = state.status?.user_id || "";
  userInput.placeholder = "your numeric user_id";
  userInput.spellcheck = false;

  const error = document.createElement("div");
  error.className = "gelcreds-error";

  const actions = document.createElement("div");
  actions.className = "gelcreds-actions";

  const cancelButton = document.createElement("button");
  cancelButton.type = "button";
  cancelButton.className = "gelcreds-btn";
  cancelButton.textContent = "Cancel";

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.className = "gelcreds-btn danger";
  deleteButton.textContent = "Remove";

  const saveButton = document.createElement("button");
  saveButton.type = "button";
  saveButton.className = "gelcreds-btn";
  saveButton.textContent = "Save";

  actions.append(deleteButton, cancelButton, saveButton);
  card.append(title, hint, makeField("Profile", profileInput), makeField("API key", keyInput), makeField("User ID", userInput), error, actions);
  overlay.appendChild(card);

  const close = () => {
    overlay.remove();
    state.dialog = null;
    document.removeEventListener("keydown", onKeyDown, true);
  };

  const onKeyDown = (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      close();
    }
  };

  const setBusy = (busy) => {
    saveButton.disabled = busy;
    deleteButton.disabled = busy;
    cancelButton.disabled = busy;
  };

  const save = async () => {
    const profile = profileInput.value.trim() || DEFAULT_PROFILE;
    const apiKey = keyInput.value.trim();
    const userId = userInput.value.trim();
    if (!apiKey && !userId) {
      error.textContent = "Enter the API key (and the user id).";
      return;
    }
    setBusy(true);
    error.textContent = "";
    try {
      await saveCredentials(profile, apiKey || undefined, userId || undefined);
      state.profile = profile;
      if (state.profileWidget) {
        state.profileWidget.value = profile;
        try {
          state.profileWidget.callback?.(profile);
        } catch (callbackError) {
          /* optional callback */
        }
      }
      close();
      notify("Gelbooru: API key saved on the server");
      refreshStatus(node, state);
    } catch (requestError) {
      error.textContent = `Could not save: ${requestError.message || requestError}`;
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    const profile = profileInput.value.trim() || DEFAULT_PROFILE;
    setBusy(true);
    error.textContent = "";
    try {
      await deleteCredentials(profile);
      close();
      notify("Gelbooru: API key removed from the server", "warning");
      refreshStatus(node, state);
    } catch (requestError) {
      error.textContent = `Could not remove: ${requestError.message || requestError}`;
    } finally {
      setBusy(false);
    }
  };

  cancelButton.addEventListener("click", close);
  saveButton.addEventListener("click", save);
  deleteButton.addEventListener("click", remove);
  overlay.addEventListener("pointerdown", (event) => {
    event.stopPropagation();
    if (event.target === overlay) close();
  });
  for (const input of [profileInput, keyInput, userInput]) {
    input.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.key === "Enter") save();
    });
  }
  document.addEventListener("keydown", onKeyDown, true);

  document.body.appendChild(overlay);
  state.dialog = overlay;
  keyInput.focus();
}

function renderStatus(state, status) {
  state.status = status;
  const { text, tone } = describeStatus(status);
  state.dot.className = `gelcreds-dot ${tone}`;
  state.text.textContent = text;
  state.text.title = status?.store_path ? `Stored in: ${status.store_path}` : "";
}

async function refreshStatus(node, state) {
  try {
    const data = await fetchStatus(state.profile);
    renderStatus(state, data.status);
  } catch (error) {
    state.dot.className = "gelcreds-dot warn";
    state.text.textContent = "API key: status unavailable";
    state.text.title = String(error?.message || error);
  }
}

async function migrateLegacyKey(node, state) {
  const legacyWidget = state.legacyWidget;
  if (!legacyWidget) return false;
  const raw = String(legacyWidget.value ?? "").trim();
  if (!raw) return false;

  const parsed = parseLegacy(raw);
  if (!parsed.api_key && !parsed.user_id) {
    legacyWidget.value = "";
    return false;
  }

  try {
    const data = await fetchStatus(state.profile);
    if (!data?.status?.api_key_set) {
      await saveCredentials(state.profile, parsed.api_key || undefined, parsed.user_id || undefined);
      notify("Gelbooru: the API key found in this workflow was moved to the server store");
    } else {
      notify("Gelbooru: the API key found in this workflow was removed - the stored key is used instead", "warning");
    }
    legacyWidget.value = "";
    try {
      legacyWidget.callback?.("");
    } catch (callbackError) {
      /* optional callback */
    }
    node.graph?.change?.();
    node.setDirtyCanvas?.(true, true);
    refreshStatus(node, state);
    return true;
  } catch (error) {
    // Never drop the key when the server could not store it.
    console.warn("[Gelbooru] Could not migrate the API key from the workflow:", error);
    state.text.textContent = "API key: found in workflow, not migrated";
    state.dot.className = "gelcreds-dot warn";
    return false;
  }
}

function install(node) {
  if (!node || node.__gelbooruCredentialsUI) return;

  const profileWidget = getWidget(node, PROFILE_WIDGET);
  if (!profileWidget) {
    // Node definition from an older version - nothing to manage here.
    return;
  }

  ensureStyles();
  const legacyWidget = getWidget(node, LEGACY_WIDGET);
  hideWidget(legacyWidget);
  hideWidget(profileWidget);

  const root = document.createElement("div");
  root.className = "gelcreds";

  const row = document.createElement("div");
  row.className = "gelcreds-row";
  const dot = document.createElement("span");
  dot.className = "gelcreds-dot";
  const text = document.createElement("span");
  text.className = "gelcreds-text";
  text.textContent = "API key: loading...";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "gelcreds-btn";
  button.textContent = "API key...";
  button.title = "Store the Gelbooru API key on the server so it never lands in workflows or image metadata";
  row.append(dot, text, button);
  root.appendChild(row);

  for (const type of ["pointerdown", "pointerup", "mousedown", "mouseup", "click", "dblclick", "wheel"]) {
    root.addEventListener(type, (event) => event.stopPropagation());
  }

  const widget = node.addDOMWidget("gelbooru_credentials", "credentials", root, {
    serialize: false,
    hideOnZoom: false,
    getMinHeight: () => PANEL_HEIGHT,
    getMaxHeight: () => PANEL_HEIGHT + 2,
  });
  widget.serialize = false;

  const state = {
    profile: String(profileWidget.value || DEFAULT_PROFILE).trim() || DEFAULT_PROFILE,
    profileWidget,
    legacyWidget,
    dot,
    text,
    status: null,
    dialog: null,
  };
  node.__gelbooruCredentialsUI = state;

  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    openDialog(node, state);
  });

  const computed = node.computeSize();
  node.setSize([node.size[0], Math.max(node.size[1], computed[1])]);
  node.setDirtyCanvas?.(true, true);

  migrateLegacyKey(node, state).finally(() => refreshStatus(node, state));
}

app.registerExtension({
  name: "Gelbooru.Credentials",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!NODE_TYPES.has(nodeData?.name)) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function (...args) {
      const result = onNodeCreated?.apply(this, args);
      install(this);
      return result;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (...args) {
      const result = onConfigure?.apply(this, args);
      install(this);
      const state = this.__gelbooruCredentialsUI;
      if (state) {
        state.profile = String(state.profileWidget?.value || DEFAULT_PROFILE).trim() || DEFAULT_PROFILE;
        migrateLegacyKey(this, state).finally(() => refreshStatus(this, state));
      }
      return result;
    };
  },
  async nodeCreated(node) {
    if (!NODE_TYPES.has(node?.comfyClass || node?.type)) return;
    install(node);
  },
});
