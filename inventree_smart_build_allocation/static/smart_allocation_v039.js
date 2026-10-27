import { renderPanel as renderV032Panel } from "./smart_allocation_v032.js";

// v0.2.39 deliberately uses a new static filename to make deployment/cache
// state visible. v0.2.32 already removes the legacy "V0.2.28 —" heading and
// includes the Default Easy Stock Location selector.
export function renderPanel(props) {
  return renderV032Panel(props);
}
