import { renderPanel as renderBasePanel } from "./smart_allocation_v050.js";

const React = globalThis.React;

function isMainAllocationRow(row) {
  if (!row || row.dataset.v051Main === "1") return false;
  const cells = [...row.children];
  if (cells.length < 8) return false;
  return Boolean(cells[0]?.querySelector('input[type="checkbox"]'));
}

function detailRowsAfter(row) {
  const rows = [];
  let next = row.nextElementSibling;
  while (next && !isMainAllocationRow(next)) {
    rows.push(next);
    next = next.nextElementSibling;
  }
  return rows;
}

function numericText(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return Number.isInteger(n) ? String(n) : String(Math.round(n * 1000) / 1000);
}

function totalAvailableFromPlan(detailRows) {
  for (const row of detailRows) {
    const plan = [...row.querySelectorAll("strong")].find((x) => (x.textContent || "").trim() === "Allocation plan");
    if (!plan) continue;
    const table = plan.parentElement?.querySelector("table");
    if (!table) continue;
    const headers = [...table.querySelectorAll("thead th")].map((x) => (x.textContent || "").trim());
    const idx = headers.indexOf("Available");
    if (idx < 0) continue;
    let total = 0;
    let found = false;
    for (const tr of table.querySelectorAll("tbody tr")) {
      const value = Number((tr.children[idx]?.textContent || "").trim());
      if (Number.isFinite(value)) {
        total += value;
        found = true;
      }
    }
    if (found) return total;
  }
  return null;
}

function moveDetailRowsIntoBlock(mainRow, details) {
  const table = mainRow.closest("table");
  if (!table || !details.length) return;

  const colCount = table.querySelectorAll(":scope > thead > tr > th").length || mainRow.children.length;
  const blockRow = document.createElement("tr");
  blockRow.dataset.v051Detail = "1";
  const td = document.createElement("td");
  td.colSpan = colCount;
  td.style.cssText = "padding:0 12px 14px 12px;border-left:2px solid #aaa;border-right:2px solid #aaa;border-bottom:2px solid #aaa";

  // Keep the original React-created detail rows alive, but present their contents
  // inside one visually bounded block directly beneath the BOM requirement.
  for (const detail of details) {
    const inner = document.createElement("div");
    inner.style.cssText = "margin-top:8px";
    while (detail.firstChild) {
      const child = detail.firstChild;
      if (child.nodeType === 1 && child.tagName === "TD") {
        while (child.firstChild) inner.appendChild(child.firstChild);
        child.remove();
      } else {
        inner.appendChild(child);
      }
    }
    if (inner.textContent.trim() || inner.children.length) td.appendChild(inner);
    detail.remove();
  }
  blockRow.appendChild(td);
  mainRow.after(blockRow);
}

function groupRows(root) {
  for (const table of root.querySelectorAll("table")) {
    const rows = [...table.querySelectorAll(":scope > tbody > tr")];
    for (const row of rows) {
      if (!isMainAllocationRow(row) || !row.isConnected) continue;
      const details = detailRowsAfter(row);
      const totalAvailable = totalAvailableFromPlan(details);

      row.dataset.v051Main = "1";
      row.style.cssText += ";border-left:2px solid #aaa;border-right:2px solid #aaa;border-top:2px solid #aaa";

      // v0.2.50 split Projected Qty into Available Qty / Remaining Qty. Multi-package
      // rows have no single-package projection, so show the sum of the plan instead.
      const headers = [...table.querySelectorAll(":scope > thead > tr > th")].map((x) => (x.textContent || "").trim());
      const availableIndex = headers.indexOf("Available Qty");
      if (availableIndex >= 0 && totalAvailable != null && row.children[availableIndex]) {
        row.children[availableIndex].textContent = numericText(totalAvailable);
      }

      moveDetailRowsIntoBlock(row, details);
    }
  }
}

function labelLineActions(root) {
  for (const button of root.querySelectorAll("button")) {
    const text = (button.textContent || "").trim();
    if (text === "Approve & Allocate Line") {
      button.title = "Approve and immediately commit this BOM line only.";
    } else if (text === "Allocate Line") {
      button.title = "Immediately commit this BOM line only.";
    }
  }
}

function enhance(root) {
  groupRows(root);
  labelLineActions(root);
}

function SmartAllocationV051(props) {
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
  return React.createElement(SmartAllocationV051, props);
}
