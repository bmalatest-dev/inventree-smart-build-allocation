import { renderPanel as renderBasePanel } from "./smart_allocation_v029.js";

const React = globalThis.React;

function EasyLocationSelector(props) {
  const e = React.createElement;
  const cfg = props?.context || props || {};
  const url = cfg.easy_location_url;
  const [data, setData] = React.useState(null);
  const [selected, setSelected] = React.useState("");
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
        setMsg("");
      })
      .catch((err) => setMsg(String(err)))
      .finally(() => setBusy(false));
  }, [url]);

  React.useEffect(() => { load(); }, [load]);

  const save = () => {
    if (!url || !selected) {
      setMsg("Select the Default Easy Location for this run.");
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
        setMsg(`Default Easy Location saved: ${d.location?.label || "selected location"}.`);
      })
      .catch((err) => setMsg(String(err)))
      .finally(() => setBusy(false));
  };

  if (!url) return null;
  return e(
    "div",
    { style: { padding: "12px 12px 0 12px" } },
    e(
      "div",
      { style: { padding: "10px", border: "1px solid #bbb", borderRadius: "5px", marginBottom: "0" } },
      e("strong", null, "Default Easy Stock Location"),
      e("p", { style: { margin: "6px 0" } },
        "Choose the normal stock location for this Shared Allocation Group. Stock in this location or its child locations is Easy. Stock already allocated to a selected BO is also Easy regardless of location."
      ),
      e(
        "div",
        { style: { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" } },
        e(
          "select",
          {
            value: selected,
            onChange: (ev) => setSelected(ev.target.value),
            disabled: busy,
            style: { minWidth: "320px", maxWidth: "620px", padding: "6px" },
          },
          e("option", { value: "" }, "Select stock location…"),
          ...((data?.locations || []).map((x) => e("option", { key: x.pk, value: String(x.pk) }, x.label)))
        ),
        e("button", { onClick: save, disabled: busy || !selected }, busy ? "Saving…" : "Save Default Location")
      ),
      msg ? e("div", { style: { marginTop: "6px" } }, msg) : null
    )
  );
}

export function renderPanel(props) {
  if (!React?.createElement) return null;
  return React.createElement(
    React.Fragment,
    null,
    React.createElement(EasyLocationSelector, props),
    renderBasePanel(props)
  );
}
