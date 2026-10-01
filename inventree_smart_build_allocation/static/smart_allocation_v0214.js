const React = globalThis.React;

function SmartAllocationPanel(props) {
  const e = React.createElement;
  const cfg = props?.context || props || {};
  const buildId = Number(cfg.build_id);
  const groupUrl = cfg.group_url;
  const previewUrl = cfg.preview_url;
  const commitUrl = cfg.commit_url;

  const [data, setData] = React.useState(null);
  const [order, setOrder] = React.useState([]);
  const [preview, setPreview] = React.useState(null);
  const [msg, setMsg] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [search, setSearch] = React.useState("");
  const [overrides, setOverrides] = React.useState({});
  const [editing, setEditing] = React.useState(null);
  const [selected, setSelected] = React.useState({});
  const [approved, setApproved] = React.useState({});
  const [commitResult, setCommitResult] = React.useState(null);
  const [pendingConfirm, setPendingConfirm] = React.useState(false);
  const [splitDraft, setSplitDraft] = React.useState({});

  const csrf = () => document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";

  const load = React.useCallback(() => {
    if (!groupUrl) {
      setMsg("Smart Allocation configuration is missing the group endpoint.");
      return;
    }

    setBusy(true);
    fetch(groupUrl, { credentials: "same-origin" })
      .then(async (r) => {
        const d = await r.json();
        if (!r.ok) throw new Error(d.error || "Load failed");
        return d;
      })
      .then((d) => {
        setData(d);
        setOrder(d.build_ids || (Number.isFinite(buildId) ? [buildId] : []));
        setMsg("");
      })
      .catch((err) => setMsg(String(err)))
      .finally(() => setBusy(false));
  }, [groupUrl, buildId]);

  React.useEffect(() => {
    load();
  }, [load]);

  const add = (id) => setOrder((s) => (s.includes(id) ? s : [...s, id]));

  const remove = (id) => {
    if (id !== buildId) setOrder((s) => s.filter((x) => x !== id));
  };

  const move = (id, delta) =>
    setOrder((s) => {
      const a = [...s];
      const i = a.indexOf(id);
      const j = i + delta;
      if (i <= 0 || j <= 0 || j >= a.length) return s;
      [a[i], a[j]] = [a[j], a[i]];
      return a;
    });

  const saveCurrentGroup = () => {
    if (!groupUrl) return Promise.reject(new Error("Shared Allocation Group URL is unavailable."));
    return fetch(groupUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf(),
      },
      body: JSON.stringify({ build_ids: order }),
    }).then(async (r) => {
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || "Save failed");
      setOrder(d.build_ids || order);
      return d;
    });
  };

  const save = () => {
    setBusy(true);
    setPreview(null);
    saveCurrentGroup()
      .then(() => setMsg("Shared Allocation Group and sequence saved."))
      .catch((err) => setMsg(String(err)))
      .finally(() => setBusy(false));
  };

  const analyze = () => {
    setBusy(true);
    setMsg("");
    setPreview(null);
    setSelected({});
    setApproved({});
    setCommitResult(null);

    saveCurrentGroup()
      .then(() =>
        fetch(previewUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
          body: JSON.stringify({ overrides }),
        })
      )
      .then(async (r) => {
        const d = await r.json();
        if (!r.ok) throw new Error(d.error || "Preview failed");
        return d;
      })
      .then((d) => {
        setPreview(d);
        const nextSelected = {};
        ["easy", "spillage", "location", "multi"].forEach((section) => {
          (d[section] || []).forEach((r) => {
            if (r.commit_key) nextSelected[r.commit_key] = true;
          });
        });
        setSelected(nextSelected);
        setApproved({});
        setCommitResult(null);
      })
      .catch((err) => setMsg(String(err)))
      .finally(() => setBusy(false));
  };

  const byId = {};
  (data?.builds || []).forEach((b) => {
    byId[b.pk] = b;
  });

  const box = {
    padding: "10px",
    border: "1px solid #bbb",
    borderRadius: "5px",
    marginBottom: "10px",
  };

  const link = (href, label) =>
    href ? e("a", { href, style: { fontWeight: 600 } }, label) : e("strong", null, label);

  const buildDisplay = (r) =>
    e("div", null,
      link(r.build_url, r.build),
      r.build_part?.label ? " — " : "",
      r.build_part?.label ? link(r.build_part.url, r.build_part.label) : null
    );

  const rerunWith = (next) => {
    setOverrides(next);
    setMsg("");
    setPreview(null);
    setSelected({});
    setApproved({});
    setBusy(true);
    fetch(previewUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({ overrides: next }),
    })
      .then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d.error || "Preview failed"); return d; })
      .then((d) => {
        setPreview(d);
        const nextSelected = {};
        ["easy", "spillage", "location", "multi"].forEach((section) => {
          (d[section] || []).forEach((r) => {
            if (r.commit_key) nextSelected[r.commit_key] = true;
          });
        });
        setSelected(nextSelected);
        setApproved({});
        setCommitResult(null);
      })
      .catch((err) => setMsg(String(err)))
      .finally(() => setBusy(false));
  };

  const chooseStock = (r, stockId) => {
    const next = { ...overrides, [r.override_key]: [{ stock_id: Number(stockId), quantity: Number(r.allocate_qty || r.bom_qty || r.required) }] };
    setEditing(null);
    rerunWith(next);
  };

  const restoreStock = (r) => {
    const next = { ...overrides };
    delete next[r.override_key];
    setEditing(null);
    rerunWith(next);
  };

  const splitEditor = (r) => {
    if (editing !== `split:${r.override_key}`) return null;
    const draft = splitDraft[r.override_key] || {};
    const total = Object.values(draft).reduce((a, b) => a + (Number(b) || 0), 0);
    const required = Number(r.allocate_qty || r.bom_qty || r.required || 0);
    return e("div", { style: { border: "1px solid #aaa", padding: "10px", marginTop: "8px" } },
      e("strong", null, "Manually Allocate Stock — multiple packages"),
      e("p", null, `Required: ${required}. Selected: ${total}. ${total > required ? `Overallocated: ${total-required}` : `Remaining: ${required-total}`}.${total > required ? " Reduce selected quantities before applying." : ""}`),
      ...(r.stock_options || []).map(x =>
        e("label", { key: x.stock_id, style: { display: "block", margin: "8px 0" } },
          `Stock #${x.stock_id}${x.batch_id ? ` • Batch: ${x.batch_id}` : ""} • ${x.location} • Available ${x.quantity}`,
          x.warnings?.length ? ` • ${x.warnings.join("; ")}` : "",
          e("input", { type: "number", min: 0, max: x.quantity, step: 1,
            disabled: busy || !x.selectable, value: draft[x.stock_id] ?? "",
            placeholder: "Qty", style: { marginLeft: "8px", width: "75px" },
            onChange: ev => setSplitDraft(prev => ({
              ...prev, [r.override_key]: { ...(prev[r.override_key] || {}), [x.stock_id]: ev.target.value }
            }))
          })
        )
      ),
      e("button", { disabled: busy || Math.abs(total-required)>0.000001 || !Object.entries(draft).some(([,q])=>Number(q)>0),
        onClick: () => {
          const rows=Object.entries(draft).filter(([,q])=>Number(q)>0).map(([sid,q])=>({stock_id:Number(sid),quantity:Number(q)}));
          setEditing(null); rerunWith({...overrides,[r.override_key]:rows});
        }
      }, "Apply Manual Allocation"),
      e("button", { disabled: busy, style: {marginLeft:"8px"}, onClick:()=>setEditing(null) }, "Cancel")
    );
  };

  const stockEditor = (r) => editing === r.override_key
    ? e("div", { style: { marginTop: "8px", padding: "8px", border: "1px solid #ccc" } },
        e("strong", null, `Select StockItem for ${r.part}`),
        ...(r.stock_options || []).map((x) =>
          e("div", { key: `${r.override_key}-${x.stock_id}`, style: { marginTop: "6px" } },
            e("button", { disabled: busy || !x.selectable, onClick: () => chooseStock(r, x.stock_id) },
              x.stock_id === r.stock_id ? "Selected" : "Use"),
            " ",
            `Stock #${x.stock_id}${x.batch_id ? ` • Batch: ${x.batch_id}` : ""} • ${x.location} • Qty ${x.quantity}`,
            x.recommended ? " • Recommended" : "",
            x.warnings?.length ? ` • ⚠ ${x.warnings.join("; ")}` : "",
            !x.selectable ? " • Not currently allocatable" : ""
          )
        ),
        e("div", { style: { marginTop: "8px" } },
          e("button", { onClick: () => setEditing(null), disabled: busy }, "Close"),
          overrides[r.override_key]
            ? e("button", { onClick: () => restoreStock(r), disabled: busy, style: { marginLeft: "6px" } }, "Restore Recommendation")
            : null
        )
      )
    : null;

  const setSectionSelected = (rows, value) => {
    const next = { ...selected };
    (rows || []).forEach((r) => {
      if (r.commit_key) next[r.commit_key] = value;
    });
    setSelected(next);
  };

  const setSectionApproved = (rows, value) => {
    const next = { ...approved };
    (rows || []).forEach((r) => {
      if (r.commit_key) next[r.commit_key] = value;
    });
    setApproved(next);
  };

  const selectedKeys = () => Object.keys(selected).filter((k) => selected[k]);

  const requestCommit = () => {
    if (!selectedKeys().length) {
      setMsg("Select at least one allocation to commit.");
      return;
    }
    setPendingConfirm(true);
  };

  const selectedPreviewRows = (keys) => {
    const wanted = new Set(keys);
    const rows = {};
    if (!preview) return rows;
    ["easy", "spillage", "location", "multi"].forEach((sectionName) => {
      (preview[sectionName] || []).forEach((row) => {
        if (row.commit_key && wanted.has(row.commit_key)) {
          rows[row.commit_key] = { section: sectionName, row };
        }
      });
    });
    return rows;
  };

  const performCommit = () => {
    const keys = selectedKeys();
    if (!keys.length) {
      setPendingConfirm(false);
      setMsg("Select at least one allocation to commit.");
      return;
    }
    setPendingConfirm(false);
    setBusy(true);
    setMsg("");
    setCommitResult(null);

    fetch(commitUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({
        selected: keys,
        approved: Object.keys(approved).filter((k) => approved[k]),
        overrides,
        selected_rows: selectedPreviewRows(keys),
      }),
    })
      .then(async (r) => {
        const d = await r.json();
        if (!r.ok) throw new Error(d.error || "Commit failed");
        return d;
      })
      .then((d) => {
        setCommitResult(d);
        setMsg(d.message || "Selected allocations committed.");
        setSelected({});
        setApproved({});
        setOverrides({});
        return fetch(previewUrl, { credentials: "same-origin" })
          .then(async (r) => { const pd = await r.json(); if (!r.ok) throw new Error(pd.error || "Committed, but preview refresh failed"); return pd; })
          .then((pd) => {
            setPreview(pd);
            const nextSelected = {};
            ["easy", "spillage", "location", "multi"].forEach((section) => {
              (pd[section] || []).forEach((row) => { if (row.commit_key) nextSelected[row.commit_key] = true; });
            });
            setSelected(nextSelected);
          });
      })
      .catch((err) => setMsg(String(err)))
      .finally(() => setBusy(false));
  };

  const section = (title, rows, kind) => {
    if (!rows?.length) return null;

    return e(
      "div",
      { style: box },
      e("strong", null, `${title} (${rows.length})`),
      ["easy", "warning"].includes(kind)
        ? e("div", { style: { margin: "7px 0" } },
            e("button", { onClick: () => setSectionSelected(rows, true), disabled: busy }, "Select All"),
            e("button", { onClick: () => setSectionSelected(rows, false), disabled: busy, style: { marginLeft: "6px" } }, "Deselect All"),
            kind === "warning"
              ? e("button", { onClick: () => setSectionApproved(rows, true), disabled: busy, style: { marginLeft: "6px" } }, "Approve All Selected Warnings")
              : null)
        : null,
      ...rows.map((r, i) =>
        e(
          "div",
          {
            key: `${kind}-${r.build || ""}-${r.part || ""}-${r.stock_id || i}-${i}`,
            style: {
              padding: "8px 0",
              borderTop: i ? "1px solid #ddd" : "none",
            },
          },
          r.commit_key && ["easy", "warning"].includes(kind)
            ? e("label", { style: { display: "block", marginBottom: "4px", fontWeight: 600 } },
                e("input", {
                  type: "checkbox",
                  checked: !!selected[r.commit_key],
                  onChange: (ev) => setSelected({ ...selected, [r.commit_key]: ev.target.checked }),
                  disabled: busy,
                }),
                " Allocate this item")
            : null,
          buildDisplay(r),
          e("div", null, "Component: ", link(r.part_url, r.part)),
          r.stock_id
            ? e(
                "div",
                null,
                `Stock #${r.stock_id}${r.batch_id ? ` • Batch: ${r.batch_id}` : ""} • ${r.location || "Unknown location"} • Allocate ${r.allocate_qty} • Spillage reserve ${r.spillage || 0}`
              )
            : null,
          r.projected_before != null
            ? e("div", null, `Projected package qty: ${r.projected_before} → ${r.projected_after}`)
            : null,
          r.manual_override ? e("div", { style: { fontWeight: 600 } }, "Manual StockItem selection") : null,
          r.stock_options
            ? e("div", { style: { marginTop: "5px" } },
                e("button", { onClick: () => setEditing(editing === r.override_key ? null : r.override_key), disabled: busy },
                  editing === r.override_key ? "Hide Stock Choices" : "Change Stock"),
                stockEditor(r),
                r.manual_override ? e("button", { disabled: busy, onClick: () => restoreStock(r), style: {marginLeft:"8px"} }, "Restore Recommendation") : null)
            : null,
          r.stock_options
            ? e("div", { style: {marginTop:"6px"} },
                e("button", { disabled:busy, onClick:()=>{
                  const existing = overrides[r.override_key] || [];
                  const draft={}; existing.forEach(x=>{draft[x.stock_id]=String(x.quantity)});
                  setSplitDraft(prev=>({...prev,[r.override_key]:draft}));
                  setEditing(`split:${r.override_key}`);
                } }, "Manually Allocate Stock / Add StockItem"),
                splitEditor(r))
            : null,
          r.stock_items
            ? e(
                "div",
                null,
                `Stock: ${r.stock_items
                  .map((x) => `#${x.stock_id}${x.batch_id ? ` [Batch: ${x.batch_id}]` : ""} (${x.qty})`)
                  .join(", ")}`
              )
            : null,
          r.options
            ? e(
                "div",
                { style: { marginTop: "5px" } },
                ...r.options.map((x) =>
                  e(
                    "div",
                    { key: `manual-${x.stock_id}` },
                    `Stock #${x.stock_id}${x.batch_id ? ` • Batch: ${x.batch_id}` : ""} • ${x.location} • Qty ${x.quantity} — ${x.reason}`
                  )
                )
              )
            : null,
          r.message ? e("div", null, r.message) : null,
          kind === "warning" && r.commit_key
            ? e(
                "label",
                { style: { display: "block", marginTop: "5px" } },
                e("input", {
                  type: "checkbox",
                  checked: !!approved[r.commit_key],
                  onChange: (ev) => setApproved({ ...approved, [r.commit_key]: ev.target.checked }),
                  disabled: busy || !selected[r.commit_key],
                }),
                " Approve exception"
              )
            : null
        )
      )
    );
  };

  return e(
    "div",
    { style: { padding: "12px" } },
    e(
      "div",
      { style: box },
      e("strong", null, "V0.2.14 — Shared Allocation Group"),
      e(
        "p",
        null,
        "Select BOs at the same physical assembly location which will run sequentially. Order matters: the projected remaining quantity of a physical package is carried forward to the next BO."
      ),
      e(
        "p",
        null,
        "Actual InvenTree allocation remains BOM quantity only; BOM + expected spillage is reserved only for package-selection planning."
      )
    ),
    busy && !data ? e("div", { style: box }, "Loading Smart Allocation…") : null,
    data
      ? e(
          "div",
          { style: box },
          e("strong", null, "Sequence"),
          ...order.map((id, i) =>
            e(
              "div",
              {
                key: id,
                style: {
                  display: "flex",
                  gap: "6px",
                  alignItems: "center",
                  padding: "5px 0",
                },
              },
              e("span", { style: { minWidth: "28px" } }, `${i + 1}.`),
              e(
                "span",
                { style: { flex: 1 } },
                byId[id]?.url ? e("a", { href: byId[id].url }, byId[id].label) : (byId[id]?.label || `BO ${id}`),
                byId[id]?.part_detail?.label ? " — " : "",
                byId[id]?.part_detail?.label ? e("a", { href: byId[id].part_detail.url }, byId[id].part_detail.label) : null,
                id === buildId ? " (current BO)" : ""
              ),
              id !== buildId
                ? e(
                    "button",
                    { onClick: () => move(id, -1), disabled: busy || i <= 1 },
                    "↑"
                  )
                : null,
              id !== buildId
                ? e(
                    "button",
                    {
                      onClick: () => move(id, 1),
                      disabled: busy || i === order.length - 1,
                    },
                    "↓"
                  )
                : null,
              id !== buildId
                ? e(
                    "button",
                    { onClick: () => remove(id), disabled: busy },
                    "Remove"
                  )
                : null
            )
          ),
          e(
            "div",
            { style: { marginTop: "10px" } },
            e("strong", null, "Related Builds — Same Parent BO"),
            data.parent_id == null
              ? e("div", { style: { marginTop: "5px" } }, "Current BO has no parent BO.")
              : (data.related_builds || []).filter((b) => !order.includes(b.pk)).length
                ? e(
                    "div",
                    { style: { marginTop: "5px" } },
                    ...(data.related_builds || [])
                      .filter((b) => !order.includes(b.pk))
                      .map((b) =>
                        e(
                          "div",
                          { key: `related-${b.pk}`, style: { margin: "4px 0" } },
                          e(
                            "button",
                            { onClick: () => add(b.pk), disabled: busy },
                            "+ Add"
                          ),
                          " ",
                          b.url ? e("a", { href: b.url }, b.label) : b.label,
                          b.part_detail?.label ? " — " : "",
                          b.part_detail?.label ? e("a", { href: b.part_detail.url }, b.part_detail.label) : null,
                          ` • Qty ${b.quantity}`
                        )
                      )
                  )
                : e("div", { style: { marginTop: "5px" } }, "No other active BOs with the same parent.")
          ),
          e(
            "div",
            { style: { marginTop: "14px" } },
            e("strong", null, "Search Other Build Orders"),
            e("input", {
              value: search,
              onChange: (ev) => setSearch(ev.target.value),
              placeholder: "Search by BO reference, title, or part…",
              style: { display: "block", width: "100%", maxWidth: "620px", margin: "6px 0", padding: "6px" },
            }),
            search.trim().length < 1
              ? e("div", null, "Enter a search term to show additional active BOs.")
              : e(
                  "div",
                  { style: { maxHeight: "220px", overflow: "auto" } },
                  ...(data.other_builds || [])
                    .filter((b) => !order.includes(b.pk))
                    .filter((b) => {
                      const q = search.trim().toLowerCase();
                      return `${b.label} ${b.part || ""}`.toLowerCase().includes(q);
                    })
                    .slice(0, 50)
                    .map((b) =>
                      e(
                        "div",
                        { key: `other-${b.pk}`, style: { margin: "4px 0" } },
                        e(
                          "button",
                          { onClick: () => add(b.pk), disabled: busy },
                          "+ Add"
                        ),
                        " ",
                        b.url ? e("a", { href: b.url }, b.label) : b.label,
                        b.part_detail?.label ? " — " : "",
                        b.part_detail?.label ? e("a", { href: b.part_detail.url }, b.part_detail.label) : null,
                        ` • Qty ${b.quantity}`
                      )
                    )
                )
          ),
          e(
            "div",
            { style: { marginTop: "10px", display: "flex", gap: "8px" } },
            e(
              "button",
              { onClick: save, disabled: busy || order.length === 0 },
              "Save Group + Sequence"
            ),
            e(
              "button",
              { onClick: analyze, disabled: busy },
              busy ? "Working…" : "Analyze / Preview"
            )
          )
        )
      : null,
    msg ? e("div", { style: box }, msg) : null,
    commitResult
      ? e(
          "div",
          { style: box },
          e("strong", null, "Commit Complete"),
          e("div", null, commitResult.message || "Allocations created."),
          e("div", null, `Selected BOM lines: ${commitResult.selected_lines || 0} • Allocation records created/updated: ${commitResult.created_count || 0} • Not selected: ${commitResult.skipped_lines || 0}`),
          ...(commitResult.created || []).map((x) =>
            e("div", { key: `created-${x.pk}-${x.stock_id}`, style: { marginTop: "4px" } }, `${x.build} • ${x.part} • Stock #${x.stock_id}${x.batch_id ? ` • Batch: ${x.batch_id}` : ""} • Qty ${x.quantity}`)
          )
        )
      : null,
    preview
      ? e(
          "div",
          null,
          e(
            "div",
            { style: box },
            e("strong", null, "Preview — select the allocations you want to commit"),
            e(
              "div",
              null,
              "Sequence: ",
              ...(preview.group || []).flatMap((x, i) => [
                i ? " → " : "",
                x.url ? e("a", { href: x.url, key: `bo-${x.pk}` }, x.label) : x.label,
                x.part?.label ? " — " : "",
                x.part?.label ? e("a", { href: x.part.url, key: `part-${x.pk}` }, x.part.label) : null,
              ])
            )
          ),
          section("Easy Allocations", preview.easy, "easy"),
          section("Spillage Warnings", preview.spillage, "warning"),
          section("Location Warnings", preview.location, "warning"),
          section("Multiple Stock Item Warnings", preview.multi, "warning"),
          section("Stock Available for Manual Decision", preview.manual, "manual"),
          section(
            "Insufficient Stock / No Automatic Allocation",
            preview.insufficient,
            "insufficient"
          ),
          e(
            "div",
            { style: box },
            e("strong", null, "Commit Selected Allocations"),
            msg ? e("div", {role:"alert", style:{border:"2px solid #b42318", padding:"10px", margin:"10px 0", fontWeight:600}}, msg) : null,
            e(
              "p",
              null,
              "Only checked allocations will be written. Warning allocations must also have their exception approved. Spillage remains planning-only; actual InvenTree allocation is the BOM quantity shown."
            ),
            e(
              "button",
              {
                onClick: requestCommit,
                disabled: busy || !commitUrl || !Object.keys(selected).some((k) => selected[k]),
              },
              busy ? "Committing…" : "Commit Selected Allocations"
            )
          ),
    pendingConfirm
      ? e(
          "div",
          { style: { ...box, border: "2px solid #888", padding: "14px" } },
          e("strong", null, "Confirm Stock Allocation"),
          e("p", null, `You are about to create stock allocations for ${selectedKeys().length} selected BOM line(s). This will write allocations to InvenTree.`),
          e("p", null, "Only BOM allocation quantities are written; planned spillage remains planning-only. Continue?"),
          e("button", { onClick: () => setPendingConfirm(false), disabled: busy }, "Cancel"),
          e("button", { onClick: performCommit, disabled: busy, style: { marginLeft: "8px", fontWeight: 600 } }, "Confirm Commit")
        )
      : null
        )
      : null
  );
}

export function renderPanel(props) {
  if (!React?.createElement) return null;
  return React.createElement(SmartAllocationPanel, props);
}
