import { renderPanel as renderBasePanel } from "./smart_allocation_v041.js";

const React = globalThis.React;

function splitProjectedColumns(root) {
  for (const table of root.querySelectorAll("table")) {
    const headers = [...table.querySelectorAll(":scope > thead > tr > th")];
    const projectedIndex = headers.findIndex((h) => (h.textContent || "").trim() === "Projected Qty");
    if (projectedIndex < 0 || table.dataset.v050Projected === "1") continue;

    headers[projectedIndex].textContent = "Available Qty";
    const remainingHead = document.createElement("th");
    remainingHead.textContent = "Remaining Qty";
    remainingHead.style.cssText = headers[projectedIndex].style.cssText;
    headers[projectedIndex].after(remainingHead);

    for (const row of table.querySelectorAll(":scope > tbody > tr")) {
      const cells = [...row.children];
      // Detail rows span the entire allocation table and are handled separately.
      if (cells.length !== headers.length) {
        const spanning = row.querySelector("td[colspan]");
        if (spanning) spanning.colSpan = Number(spanning.colSpan || 11) + 1;
        continue;
      }
      const cell = cells[projectedIndex];
      if (!cell) continue;
      const text = (cell.textContent || "").trim();
      const parts = text.split("→").map((x) => x.trim());
      cell.textContent = parts.length === 2 ? parts[0] : "—";
      const remaining = document.createElement("td");
      remaining.textContent = parts.length === 2 ? parts[1] : "—";
      remaining.style.cssText = cell.style.cssText;
      cell.after(remaining);
    }
    table.dataset.v050Projected = "1";
  }
}

function removeChangeStock(root) {
  for (const button of root.querySelectorAll("button")) {
    const label = (button.textContent || "").trim();
    if (label === "Change Stock" || label === "Hide Stock Choices") button.remove();
    if (label === "Allocate Line") {
      button.title = "Immediately allocate this single line; no need to use Commit Selected Allocations below.";
    }
    if (label === "Approve & Allocate Line") {
      button.title = "Approve this warning and immediately allocate this single line; no need to use Commit Selected Allocations below.";
    }
  }
}

function allocationPlanTable(text) {
  const raw = text.replace(/^Allocation plan:\s*/i, "").trim();
  if (!raw) return null;
  const entries = raw.split(/\s*\|\s*/).map((entry) => {
    const bits = entry.split(/\s*•\s*/);
    const first = bits.shift() || "";
    const stockMatch = first.match(/^Stock\s+#(\d+)(?:\s+\[([^\]]+)\])?/i);
    const values = { stock: stockMatch ? `#${stockMatch[1]}` : first, batch: stockMatch?.[2] || "—", location: "—", allocate: "—", before: "—", after: "—", spill: "0" };
    for (const bit of bits) {
      if (/^Allocate\s+/i.test(bit)) values.allocate = bit.replace(/^Allocate\s+/i, "");
      else if (/^Available before\s+/i.test(bit)) values.before = bit.replace(/^Available before\s+/i, "");
      else if (/^Remaining after\s+/i.test(bit)) values.after = bit.replace(/^Remaining after\s+/i, "");
      else if (/^Spillage reserve\s+/i.test(bit)) values.spill = bit.replace(/^Spillage reserve\s+/i, "");
      else values.location = bit;
    }
    return values;
  });
  if (!entries.length) return null;

  const table = document.createElement("table");
  table.style.cssText = "width:100%;border-collapse:collapse;font-size:.92em;margin-top:5px";
  const thead = document.createElement("thead");
  const hr = document.createElement("tr");
  ["Stock", "Batch", "Location", "Available", "Allocate", "Remaining", "Spillage"].forEach((label) => {
    const th = document.createElement("th");
    th.textContent = label;
    th.style.cssText = "padding:5px 7px;border:1px solid #c7c7c7;text-align:left;background:rgba(127,127,127,.10);white-space:nowrap";
    hr.appendChild(th);
  });
  thead.appendChild(hr);
  table.appendChild(thead);
  const tbody = document.createElement("tbody");
  for (const item of entries) {
    const tr = document.createElement("tr");
    [item.stock, item.batch, item.location, item.before, item.allocate, item.after, item.spill].forEach((value, i) => {
      const td = document.createElement("td");
      td.textContent = value;
      td.style.cssText = `padding:5px 7px;border:1px solid #d7d7d7;${i >= 3 ? "text-align:right;" : ""}`;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

function compactAllocationPlans(root) {
  for (const td of root.querySelectorAll("td")) {
    const text = (td.textContent || "").trim();
    if (!text.startsWith("Allocation plan:") || td.dataset.v050Plan === "1") continue;
    const table = allocationPlanTable(text);
    if (!table) continue;
    td.textContent = "";
    const title = document.createElement("strong");
    title.textContent = "Allocation plan";
    td.append(title, table);
    td.dataset.v050Plan = "1";
  }
}

function variantComparison(root) {
  for (const td of root.querySelectorAll("td")) {
    if (td.dataset.v050Variant === "1") continue;
    const text = (td.textContent || "").trim();
    let proposed = null;
    let bom = null;
    let match = text.match(/^Variant stock proposed:\s*(.+?)\s+for BOM component\s+(.+?)\.\s*Review/i);
    if (match) {
      proposed = match[1];
      bom = match[2];
    } else {
      match = text.match(/^Variant stock is required to satisfy this BOM line:\s*(.+?)\.\s*Review/i);
      if (match) proposed = match[1];
    }
    if (!proposed) continue;

    const table = td.closest("table");
    const parentRow = td.closest("tr")?.previousElementSibling;
    if (!bom && parentRow) {
      const cells = [...parentRow.children];
      bom = (cells[2]?.querySelector("a")?.textContent || cells[2]?.textContent || "").trim();
    }
    if (!bom) bom = "—";

    const compare = document.createElement("table");
    compare.style.cssText = "border-collapse:collapse;margin:4px 0 6px 0;font-size:.92em";
    [["BOM MPN", bom], ["Proposed Variant MPN", proposed]].forEach(([label, value]) => {
      const tr = document.createElement("tr");
      const th = document.createElement("th");
      th.textContent = label;
      th.style.cssText = "padding:4px 7px;border:1px solid #d7d7d7;text-align:left;background:rgba(127,127,127,.08);white-space:nowrap";
      const valueCell = document.createElement("td");
      valueCell.textContent = value;
      valueCell.style.cssText = "padding:4px 7px;border:1px solid #d7d7d7;text-align:left";
      tr.append(th, valueCell);
      compare.appendChild(tr);
    });
    td.prepend(compare);
    td.dataset.v050Variant = "1";
  }
}

function clarifyCommitArea(root) {
  for (const strong of root.querySelectorAll("strong")) {
    if ((strong.textContent || "").trim() !== "Commit Selected Allocations") continue;
    const box = strong.parentElement;
    if (!box || box.dataset.v050Commit === "1") continue;
    const p = box.querySelector("p");
    if (p) p.textContent = "Use Allocate Line (or Approve & Allocate Line) in a row to complete that line immediately. Use the checkboxes and Commit Selected Allocations below only when you want to commit several lines together. Warning allocations require approval.";
    box.dataset.v050Commit = "1";
  }
}

function enhance(root) {
  splitProjectedColumns(root);
  removeChangeStock(root);
  compactAllocationPlans(root);
  variantComparison(root);
  clarifyCommitArea(root);
}

function SmartAllocationV050(props) {
  const host = React.useRef(null);
  React.useEffect(() => {
    const root = host.current;
    if (!root) return undefined;
    const run = () => enhance(root);
    run();
    const observer = new MutationObserver(run);
    observer.observe(root, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, []);
  return React.createElement("div", { ref: host }, renderBasePanel(props));
}

export function renderPanel(props) {
  if (!React?.createElement) return null;
  return React.createElement(SmartAllocationV050, props);
}
