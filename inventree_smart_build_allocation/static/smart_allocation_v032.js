import { renderPanel as renderBasePanel } from "./smart_allocation_v0228.js";

const React = globalThis.React;

function EasyLocationSelector(props) {
  const e = React.createElement;
  const cfg = props?.context || props || {};
  const url = cfg.easy_location_url;
  const [data, setData] = React.useState(null);
  const [selected, setSelected] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [open, setOpen] = React.useState(false);
  const [msg, setMsg] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const csrf = () => document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";

  const load = React.useCallback(() => {
    if (!url) return;
    setBusy(true);
    fetch(url, { credentials: "same-origin" })
      .then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d.error || "Location load failed"); return d; })
      .then((d) => {
        setData(d);
        setSelected(d.location_id == null ? "" : String(d.location_id));
        setQuery(d.location?.label || "");
        setMsg("");
      })
      .catch((err) => setMsg(String(err)))
      .finally(() => setBusy(false));
  }, [url]);

  React.useEffect(() => { load(); }, [load]);

  const choose = (x) => {
    setSelected(String(x.pk));
    setQuery(x.label || x.name || `Location ${x.pk}`);
    setOpen(false);
    setMsg("");
  };

  const save = () => {
    if (!url || !selected) {
      setMsg("Search for and select the Default Easy Location for this run.");
      return;
    }
    setBusy(true);
    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({ location_id: Number(selected) }),
    })
      .then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d.error || "Location save failed"); return d; })
      .then((d) => {
        setData(d);
        setSelected(d.location_id == null ? "" : String(d.location_id));
        setQuery(d.location?.label || "");
        setMsg(`Default Easy Location saved: ${d.location?.label || "selected location"}.`);
      })
      .catch((err) => setMsg(String(err)))
      .finally(() => setBusy(false));
  };

  if (!url) return null;
  const q = query.trim().toLowerCase();
  const matches = (data?.locations || [])
    .filter((x) => !q || String(x.label || x.name || "").toLowerCase().includes(q))
    .slice(0, 30);

  return e(
    "div",
    { style: { padding: "12px 12px 0 12px" } },
    e(
      "div",
      { style: { padding: "10px", border: "1px solid #bbb", borderRadius: "5px" } },
      e("strong", null, "Default Easy Stock Location"),
      e("p", { style: { margin: "6px 0" } },
        "Stock in this location or its child locations is Easy. Stock already allocated to a selected BO is also Easy regardless of location."
      ),
      e("div", { style: { position: "relative", maxWidth: "620px" } },
        e("input", {
          type: "text",
          value: query,
          placeholder: "Search stock locations…",
          disabled: busy,
          onFocus: () => setOpen(true),
          onChange: (ev) => { setQuery(ev.target.value); setSelected(""); setOpen(true); },
          style: { width: "100%", padding: "7px", boxSizing: "border-box" },
        }),
        open && matches.length
          ? e("div", { style: { position: "absolute", zIndex: 20, left: 0, right: 0, maxHeight: "240px", overflowY: "auto", border: "1px solid #aaa", background: "var(--mantine-color-body, white)", boxShadow: "0 3px 10px rgba(0,0,0,.15)" } },
              ...matches.map((x) => e("button", {
                key: x.pk,
                type: "button",
                onClick: () => choose(x),
                style: { display: "block", width: "100%", textAlign: "left", padding: "8px 10px", border: 0, borderBottom: "1px solid #ddd", background: "transparent", cursor: "pointer" },
              }, x.label || x.name || `Location ${x.pk}`)))
          : null
      ),
      e("div", { style: { marginTop: "8px" } },
        e("button", { onClick: save, disabled: busy || !selected }, busy ? "Saving…" : "Save Default Location")
      ),
      msg ? e("div", { style: { marginTop: "6px" } }, msg) : null
    )
  );
}

function removeLegacyVersionLabel(node) {
  if (typeof node === "string") {
    return node.replace(/^V0\.2\.28\s+[—-]\s+Shared Allocation Group$/, "Shared Allocation Group");
  }
  if (Array.isArray(node)) return node.map(removeLegacyVersionLabel);
  if (!React?.isValidElement?.(node)) return node;
  const children = node.props?.children;
  if (children == null) return node;
  const nextChildren = React.Children.map(children, removeLegacyVersionLabel);
  return React.cloneElement(node, undefined, nextChildren);
}

export function renderPanel(props) {
  if (!React?.createElement) return null;
  return React.createElement(
    React.Fragment,
    null,
    React.createElement(EasyLocationSelector, props),
    removeLegacyVersionLabel(renderBasePanel(props))
  );
}
