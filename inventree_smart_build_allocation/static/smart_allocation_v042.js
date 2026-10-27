import { renderPanel as renderBasePanel } from "./smart_allocation_v041.js";

const React = globalThis.React;

function SmartAllocationV042(props) {
  const backendFingerprint = props?.context?.backend_fingerprint;

  React.useEffect(() => {
    const markerId = "smart-allocation-v042-diagnostic";

    const addDiagnosticMarker = () => {
      if (document.getElementById(markerId)) return;

      const heading = [...document.querySelectorAll("strong")].find(
        (node) => (node.textContent || "").trim() === "Shared Allocation Group"
      );
      if (!heading) return;

      const marker = document.createElement("div");
      marker.id = markerId;
      marker.style.fontSize = "12px";
      marker.style.marginTop = "4px";
      marker.style.marginBottom = "8px";
      marker.textContent = `Frontend: v0.2.42 | Backend: ${backendFingerprint || "MISSING"}`;
      heading.parentElement?.insertBefore(marker, heading.nextSibling);
    };

    addDiagnosticMarker();
    const observer = new MutationObserver(addDiagnosticMarker);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [backendFingerprint]);

  return renderBasePanel(props);
}

export function renderPanel(props) {
  if (!React?.createElement) return null;
  return React.createElement(SmartAllocationV042, props);
}
