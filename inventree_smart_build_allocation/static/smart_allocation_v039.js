import { renderPanel as renderBasePanel } from "./smart_allocation_v0228.js";

const React = globalThis.React;

function replaceLegacyVersionLabel(node) {
  if (typeof node === "string") {
    return node.replace(/^V0\.2\.28\s+[—-]\s+Shared Allocation Group$/, "Shared Allocation Group");
  }
  if (Array.isArray(node)) return node.map(replaceLegacyVersionLabel);
  if (!React?.isValidElement?.(node)) return node;
  const children = node.props?.children;
  if (children == null) return node;
  const nextChildren = React.Children.map(children, replaceLegacyVersionLabel);
  return React.cloneElement(node, undefined, nextChildren);
}

export function renderPanel(props) {
  if (!React?.createElement) return null;
  return replaceLegacyVersionLabel(renderBasePanel(props));
}
