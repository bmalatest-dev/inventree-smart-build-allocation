import { renderPanel as renderBasePanel } from "./smart_allocation_v051.js";

const React = globalThis.React;

function rowHasAllocationCheckbox(row) {
  return Boolean(row?.querySelector(':scope > td input[type="checkbox"]'));
}

function mainRowBefore(node) {
  let row = node?.closest("tr")?.previousElementSibling || null;
  while (row) {
    if (row.dataset.v051Main === "1" || rowHasAllocationCheckbox(row)) return row;
    row = row.previousElementSibling;
  }
  return null;
}

function componentFromMainRow(row) {
  if (!row) return "";
  const table = row.closest("table");
  const headers = table
    ? [...table.querySelectorAll(":scope > thead > tr > th")].map((x) => (x.textContent || "").trim())
    : [];
  const componentIndex = headers.indexOf("Component");
  const cell = componentIndex >= 0 ? row.children[componentIndex] : null;
  if (cell) return (cell.querySelector("a")?.textContent || cell.textContent || "").trim();

  // Fallback for older table layouts: the component cell is the first cell after
  // the Build Order cell which contains a part link.
  const cells = [...row.children];
  for (const candidate of cells) {
    const link = candidate.querySelector("a");
    const text = (link?.textContent || candidate.textContent || "").trim();
    if (text && !/^BO-\d+/i.test(text)) return text;
  }
  return "";
}

function repairVariantBomMpn(root) {
  for (const table of root.querySelectorAll("table")) {
    const rows = [...table.querySelectorAll("tr")];
    for (const row of rows) {
      const first = row.children[0];
      if ((first?.textContent || "").trim() !== "BOM MPN") continue;
      const valueCell = row.children[1];
      if (!valueCell || (valueCell.textContent || "").trim() !== "—") continue;

      const main = mainRowBefore(table);
      const bom = componentFromMainRow(main);
      if (bom) valueCell.textContent = bom;
    }
  }
}

function styleAllocationCards(root) {
  for (const main of root.querySelectorAll('tr[data-v051-main="1"]')) {
    if (main.dataset.v052Card === "1") continue;
    const detail = main.nextElementSibling?.dataset.v051Detail === "1"
      ? main.nextElementSibling
      : null;

    const cells = [...main.children];
    cells.forEach((cell, index) => {
      cell.style.borderTop = "2px solid #999";
      cell.style.paddingTop = "10px";
      cell.style.paddingBottom = detail ? "8px" : "10px";
      if (index === 0) cell.style.borderLeft = "2px solid #999";
      if (index === cells.length - 1) cell.style.borderRight = "2px solid #999";
      if (!detail) cell.style.borderBottom = "2px solid #999";
    });

    if (detail) {
      const detailCell = detail.querySelector(":scope > td");
      if (detailCell) {
        detailCell.style.borderLeft = "2px solid #999";
        detailCell.style.borderRight = "2px solid #999";
        detailCell.style.borderBottom = "2px solid #999";
        detailCell.style.padding = "0 12px 12px 12px";
        detailCell.style.background = "rgba(127,127,127,.025)";
      }
    }
    main.dataset.v052Card = "1";
  }
}

function addCardSpacing(root) {
  for (const detail of root.querySelectorAll('tr[data-v051-detail="1"]')) {
    const next = detail.nextElementSibling;
    if (!next || next.dataset.v052Spacer === "1") continue;
    const table = detail.closest("table");
    const colCount = table?.querySelectorAll(":scope > thead > tr > th").length || 1;
    const spacer = document.createElement("tr");
    spacer.dataset.v052Spacer = "1";
    const td = document.createElement("td");
    td.colSpan = colCount;
    td.style.height = "10px";
    td.style.border = "0";
    td.style.padding = "0";
    spacer.appendChild(td);
    detail.after(spacer);
  }
}

function enhance(root) {
  repairVariantBomMpn(root);
  styleAllocationCards(root);
  addCardSpacing(root);
}

function SmartAllocationV052(props) {
  const host = React.useRef(null);
  React.useEffect(() => {
    const root = host.current;
    if (!root) return undefined;
    let running = false;
    const run = () => {
      if (running) return;
      running = true;
      try { enhance(root); } finally { running = false; }
    };
    run();
    const observer = new MutationObserver(run);
    observer.observe(root, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, []);
  return React.createElement("div", { ref: host }, renderBasePanel(props));
}

export function renderPanel(props) {
  if (!React?.createElement) return null;
  return React.createElement(SmartAllocationV052, props);
}
