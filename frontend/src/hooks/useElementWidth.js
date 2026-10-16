import { useEffect, useState } from "react";

/**
 * Width of an element, kept current with a ResizeObserver (charts redraw at the new size).
 * Returns a callback ref, so it also works for elements that mount after the first render.
 */
export function useElementWidth(fallback = 600) {
  const [node, setNode] = useState(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    if (!node) return undefined;
    setWidth(node.clientWidth || fallback);
    const ro = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width) || fallback));
    ro.observe(node);
    return () => ro.disconnect();
  }, [node, fallback]);
  return [setNode, width];
}
