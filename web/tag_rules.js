import { app } from "../../scripts/app.js";

/*
 * Tag Rules node UI.
 *
 * The rule table is rendered as a DOM widget. The rules themselves are kept in
 * the hidden `rules_json` STRING widget, so a workflow - and the API - keeps
 * working even if this script is not loaded.
 *
 * Layout note: a DOM widget must stay the LAST entry of `node.widgets`.
 * Litegraph serializes widget values by array index while skipping widgets with
 * `serialize === false`, so moving this widget anywhere else would shift every
 * saved widget value by one slot.
 */

const NODE_NAME = "TagRules";
const RULES_WIDGET = "rules_json";
const MIN_WIDTH = 380;
const MIN_HEIGHT = 140;
const STYLE_ID = "gelbooru-tag-rules-style";

const CSS = `
.tagrules {
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  padding: 2px 6px 6px;
  overflow: auto;
  color: var(--input-text, #ddd);
  font-family: inherit;
  font-size: 12px;
}
.tagrules-body { display: flex; flex-direction: column; gap: 10px; }
.tagrules-section { display: flex; flex-direction: column; gap: 4px; }
.tagrules-caption {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  font-weight: 600;
  color: var(--input-text, #ddd);
  opacity: .92;
}
.tagrules-hint { font-size: 10px; font-weight: 400; color: var(--descrip-text, #999); }
.tagrules-rows { display: flex; flex-direction: column; gap: 3px; }
.tagrules-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) 20px;
  gap: 4px;
  align-items: center;
}
.tagrules-row.is-remove { grid-template-columns: minmax(0, 1fr) 20px; }
.tagrules-head { font-size: 10px; color: var(--descrip-text, #999); padding: 0 1px; }
.tagrules-input {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 3px 6px;
  background: var(--comfy-input-bg, #222);
  color: var(--input-text, #ddd);
  border: 1px solid var(--border-color, #4e4e4e);
  border-radius: 4px;
  font-family: inherit;
  font-size: 12px;
  outline: none;
}
.tagrules-input::placeholder { color: var(--descrip-text, #999); opacity: .75; }
.tagrules-input:focus { border-color: #4f8cff; }
.tagrules-input.is-duplicate { border-color: var(--error-text, #f44); }
.tagrules-del {
  width: 20px;
  height: 22px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
  color: var(--descrip-text, #999);
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
}
.tagrules-del:hover {
  background: rgba(255, 90, 90, .15);
  border-color: rgba(255, 90, 90, .45);
  color: var(--error-text, #f44);
}
.tagrules-add {
  align-self: flex-start;
  margin-top: 2px;
  padding: 2px 8px;
  border: 1px dashed var(--border-color, #4e4e4e);
  border-radius: 4px;
  background: transparent;
  color: var(--input-text, #ddd);
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
}
.tagrules-add:hover { border-color: #4f8cff; color: #fff; background: rgba(79, 140, 255, .12); }
.tagrules-empty { padding: 2px 1px; color: var(--descrip-text, #999); font-size: 11px; font-style: italic; }
`;

function ensureStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = CSS;
  document.head.appendChild(style);
}

function normalizeKey(value) {
  return String(value ?? "")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function parseRules(raw) {
  let data = null;
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (trimmed) {
      try {
        data = JSON.parse(trimmed);
      } catch (error) {
        data = null;
      }
    }
  } else if (raw && typeof raw === "object") {
    data = raw;
  }
  if (Array.isArray(data)) data = { replace: data };
  if (!data || typeof data !== "object") data = {};

  const replaceRaw = data.replace ?? data.replacements ?? data.rules ?? [];
  const replaceList = Array.isArray(replaceRaw)
    ? replaceRaw
    : replaceRaw && typeof replaceRaw === "object"
      ? Object.entries(replaceRaw).map(([from, to]) => ({ from, to }))
      : [];

  const replace = [];
  for (const item of replaceList) {
    let from = "";
    let to = "";
    if (typeof item === "string") {
      const parts = item.split("=>");
      from = parts[0] ?? "";
      to = parts[1] ?? "";
    } else if (item && typeof item === "object") {
      from = item.from ?? item.find ?? "";
      to = item.to ?? item.replace ?? "";
    } else {
      continue;
    }
    from = String(from).trim();
    to = String(to).trim();
    if (from) replace.push({ from, to });
  }

  const removeRaw = data.remove ?? data.removals ?? data.delete ?? [];
  const removeList = Array.isArray(removeRaw)
    ? removeRaw
    : typeof removeRaw === "string"
      ? removeRaw.split(",")
      : [];

  const remove = [];
  for (const item of removeList) {
    const value = item && typeof item === "object" ? (item.tag ?? item.from ?? "") : item;
    for (const part of String(value ?? "").split(",")) {
      const tag = part.trim();
      if (tag) remove.push(tag);
    }
  }

  return { replace, remove };
}

function serializeRules(state) {
  return {
    version: 1,
    replace: state.replace
      .map((rule) => ({ from: String(rule.from ?? "").trim(), to: String(rule.to ?? "").trim() }))
      .filter((rule) => rule.from !== ""),
    remove: state.remove
      .flatMap((row) => String(row ?? "").split(","))
      .map((tag) => tag.trim())
      .filter((tag) => tag !== ""),
  };
}

function stopCanvasEvents(root) {
  for (const type of ["pointerdown", "pointerup", "mousedown", "mouseup", "click", "dblclick", "contextmenu", "wheel"]) {
    root.addEventListener(type, (event) => event.stopPropagation());
  }
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

function makeInput(className, placeholder, title) {
  const input = document.createElement("input");
  input.type = "text";
  input.className = className;
  input.placeholder = placeholder;
  input.title = title;
  input.spellcheck = false;
  input.autocomplete = "off";
  return input;
}

function makeDeleteButton(title) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "tagrules-del";
  button.textContent = "\u2715";
  button.title = title;
  return button;
}

function makeHead(labels, isRemove) {
  const head = document.createElement("div");
  head.className = isRemove ? "tagrules-row is-remove tagrules-head" : "tagrules-row tagrules-head";
  for (const label of labels) {
    const span = document.createElement("span");
    span.textContent = label;
    head.appendChild(span);
  }
  return head;
}

function installUI(node) {
  if (!node || node.__tagRulesUI) return;

  const rulesWidget = (node.widgets || []).find((widget) => widget && widget.name === RULES_WIDGET);
  if (!rulesWidget) {
    // Widgets exist before onNodeCreated in current frontends; retry briefly in
    // case a future frontend creates them later.
    node.__tagRulesAttempts = (node.__tagRulesAttempts || 0) + 1;
    if (node.__tagRulesAttempts <= 30) requestAnimationFrame(() => installUI(node));
    return;
  }
  node.__tagRulesAttempts = 0;

  ensureStyles();
  hideWidget(rulesWidget);

  const state = { replace: [], remove: [] };
  let changeTimer = null;
  let replaceRowRefs = [];
  let removeRowRefs = [];

  const root = document.createElement("div");
  root.className = "tagrules";
  const body = document.createElement("div");
  body.className = "tagrules-body";
  root.appendChild(body);
  stopCanvasEvents(root);

  const replaceRows = document.createElement("div");
  replaceRows.className = "tagrules-rows";
  const removeRows = document.createElement("div");
  removeRows.className = "tagrules-rows";

  const markChanged = () => {
    clearTimeout(changeTimer);
    changeTimer = setTimeout(() => {
      try {
        node.graph?.change?.();
      } catch (error) {
        /* graph is gone or the tracker is unavailable */
      }
    }, 400);
  };

  const sync = () => {
    const json = JSON.stringify(serializeRules(state));
    if (rulesWidget.value !== json) {
      rulesWidget.value = json;
      try {
        rulesWidget.callback?.(json);
      } catch (error) {
        /* widget callback is optional */
      }
    }
    markChanged();
    node.setDirtyCanvas?.(true, true);
  };

  const fit = (growOnly = false) => {
    if (!node || node.flags?.collapsed) return;
    node.__tagRulesContentHeight = Math.max(Math.ceil(body.scrollHeight), 80);
    const computed = node.computeSize();
    const width = Math.max(node.size[0], MIN_WIDTH);
    const height = growOnly
      ? Math.max(computed[1], node.size[1])
      : Math.max(computed[1], MIN_HEIGHT);
    if (Math.abs(node.size[0] - width) > 0.5 || Math.abs(node.size[1] - height) > 1) {
      node.setSize([width, height]);
    }
    node.setDirtyCanvas?.(true, true);
    app.canvas?.setDirty?.(true, true);
  };

  const refreshDuplicates = () => {
    const seen = new Set();
    for (const ref of replaceRowRefs) {
      const key = normalizeKey(ref.rule.from);
      const duplicate = key !== "" && seen.has(key);
      ref.from.classList.toggle("is-duplicate", duplicate);
      if (key !== "") seen.add(key);
    }
  };

  const makeReplaceRow = (rule, index) => {
    const row = document.createElement("div");
    row.className = "tagrules-row";

    const from = makeInput(
      "tagrules-input",
      "1girl",
      "Tag(s) to find. Commas separate several tags - all of them must be present (see match_mode).",
    );
    from.value = rule.from;
    from.addEventListener("input", () => {
      rule.from = from.value;
      refreshDuplicates();
      sync();
    });
    from.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        addReplaceRow(index + 1);
      }
    });

    const to = makeInput(
      "tagrules-input",
      "1boy",
      "What to put instead. Commas separate several tags. Leave empty to delete the found tags.",
    );
    to.value = rule.to;
    to.addEventListener("input", () => {
      rule.to = to.value;
      sync();
    });
    to.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        addReplaceRow(index + 1);
      }
    });

    const del = makeDeleteButton("Delete this rule");
    del.addEventListener("click", (event) => {
      event.preventDefault();
      state.replace.splice(index, 1);
      if (!state.replace.length) state.replace.push({ from: "", to: "" });
      renderAll();
      sync();
      fit(false);
    });

    row.append(from, to, del);
    replaceRowRefs.push({ from, rule });
    return row;
  };

  const makeRemoveRow = (value, index) => {
    const row = document.createElement("div");
    row.className = "tagrules-row is-remove";

    const input = makeInput(
      "tagrules-input",
      "censored",
      "Tag to drop. Commas separate several tags. '*' matches anything, e.g. *_background.",
    );
    input.value = value;
    input.addEventListener("input", () => {
      state.remove[index] = input.value;
      sync();
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        addRemoveRow(index + 1);
      }
    });

    const del = makeDeleteButton("Delete this tag");
    del.addEventListener("click", (event) => {
      event.preventDefault();
      state.remove.splice(index, 1);
      renderAll();
      sync();
      fit(false);
    });

    row.append(input, del);
    removeRowRefs.push({ input, index });
    return row;
  };

  const addReplaceRow = (at) => {
    const index = at ?? state.replace.length;
    state.replace.splice(index, 0, { from: "", to: "" });
    renderAll({ section: "replace", index });
    sync();
    fit(true);
  };

  const addRemoveRow = (at) => {
    const index = at ?? state.remove.length;
    state.remove.splice(index, 0, "");
    renderAll({ section: "remove", index });
    sync();
    fit(true);
  };

  const renderAll = (focus = null) => {
    replaceRowRefs = [];
    replaceRows.replaceChildren(makeHead(["Find", "Replace with", ""], false));
    if (state.replace.length) {
      state.replace.forEach((rule, index) => replaceRows.appendChild(makeReplaceRow(rule, index)));
    } else {
      const empty = document.createElement("div");
      empty.className = "tagrules-empty";
      empty.textContent = "No rules yet - press \u201c+ Add rule\u201d.";
      replaceRows.appendChild(empty);
    }

    removeRowRefs = [];
    removeRows.replaceChildren(makeHead(["Remove", ""], true));
    if (state.remove.length) {
      state.remove.forEach((value, index) => removeRows.appendChild(makeRemoveRow(value, index)));
    } else {
      const empty = document.createElement("div");
      empty.className = "tagrules-empty";
      empty.textContent = "Nothing is removed yet - press \u201c+ Add tag\u201d.";
      removeRows.appendChild(empty);
    }

    refreshDuplicates();

    if (focus) {
      const refs = focus.section === "replace" ? replaceRowRefs : removeRowRefs;
      const ref = refs[focus.index];
      const input = ref?.from ?? ref?.input;
      if (input) {
        input.focus();
        const end = input.value.length;
        input.setSelectionRange?.(end, end);
      }
    }
  };

  const makeSection = (title, hint, rows, addLabel, onAdd) => {
    const section = document.createElement("div");
    section.className = "tagrules-section";

    const caption = document.createElement("div");
    caption.className = "tagrules-caption";
    const titleEl = document.createElement("span");
    titleEl.textContent = title;
    const hintEl = document.createElement("span");
    hintEl.className = "tagrules-hint";
    hintEl.textContent = hint;
    caption.append(titleEl, hintEl);

    const add = document.createElement("button");
    add.type = "button";
    add.className = "tagrules-add";
    add.textContent = addLabel;
    add.addEventListener("click", (event) => {
      event.preventDefault();
      onAdd();
    });

    section.append(caption, rows, add);
    return section;
  };

  body.append(
    makeSection("Replace tags", "commas = several tags", replaceRows, "+ Add rule", () => addReplaceRow()),
    makeSection("Remove tags", "'*' wildcard supported", removeRows, "+ Add tag", () => addRemoveRow()),
  );

  const parsed = parseRules(rulesWidget.value);
  state.replace = parsed.replace.length ? parsed.replace : [{ from: "", to: "" }];
  state.remove = parsed.remove;
  renderAll();

  const domWidget = node.addDOMWidget("tag_rules_table", "tagrules", root, {
    serialize: false,
    hideOnZoom: false,
    getMinHeight: () => node.__tagRulesContentHeight || MIN_HEIGHT,
    getMaxHeight: () => 100000,
  });
  domWidget.serialize = false;

  node.__tagRulesUI = {
    state,
    rulesWidget,
    renderAll,
    fit,
    refreshFromWidget: () => {
      const fresh = parseRules(rulesWidget.value);
      state.replace = fresh.replace.length ? fresh.replace : [{ from: "", to: "" }];
      state.remove = fresh.remove;
      renderAll();
      // grow only: a workflow may have been saved with a taller node
      fit(true);
    },
  };

  node.setDirtyCanvas?.(true, true);
  fit(false);
  requestAnimationFrame(() => {
    fit(false);
    requestAnimationFrame(() => fit(false));
  });
}

app.registerExtension({
  name: "Gelbooru.TagRules",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== NODE_NAME) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function (...args) {
      const result = onNodeCreated?.apply(this, args);
      installUI(this);
      return result;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (...args) {
      const result = onConfigure?.apply(this, args);
      installUI(this);
      this.__tagRulesUI?.refreshFromWidget();
      return result;
    };
  },
  async nodeCreated(node) {
    if ((node?.comfyClass || node?.type) !== NODE_NAME) return;
    installUI(node);
  },
});
