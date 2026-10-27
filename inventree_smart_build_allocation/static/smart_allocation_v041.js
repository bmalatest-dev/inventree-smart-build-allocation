import { renderPanel as renderBasePanel } from "./smart_allocation_v032.js";

const React = globalThis.React;

function SmartAllocationV041(props) {
  React.useEffect(() => {
    const replaceLegacyHeading = () => {
      for (const node of document.querySelectorAll("strong")) {
        if ((node.textContent || "").trim() === "V0.2.28 — Shared Allocation Group") {
          node.textContent = "Shared Allocation Group";
        }
      }
    };

    replaceLegacyHeading();
    const observer = new MutationObserver(replaceLegacyHeading);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  return renderBasePanel(props);
}

export function renderPanel(props) {
  if (!React?.createElement) return null;
  return React.createElement(SmartAllocationV041, props);
}
