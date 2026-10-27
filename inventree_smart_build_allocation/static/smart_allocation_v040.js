import { renderPanel as renderBasePanel } from "./smart_allocation_v0228.js";

const React = globalThis.React;

function CurrentSmartAllocationPanel(props) {
  React.useEffect(() => {
    const replaceHeading = () => {
      for (const node of document.querySelectorAll("strong")) {
        if ((node.textContent || "").trim() === "V0.2.28 — Shared Allocation Group") {
          node.textContent = "Shared Allocation Group";
        }
      }
    };

    replaceHeading();
    const observer = new MutationObserver(replaceHeading);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  return renderBasePanel(props);
}

export function renderPanel(props) {
  if (!React?.createElement) return null;
  return React.createElement(CurrentSmartAllocationPanel, props);
}
