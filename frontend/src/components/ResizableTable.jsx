import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

/**
 * A generic <table> wrapper that lets the user resize column widths by dragging
 * a small handle on the right edge of each <th>. Column widths are persisted
 * to localStorage under `resizable-table:<storageKey>`. Widths default to the
 * `defaultWidths` array (a parallel list, in rem).
 *
 * The component does NOT inject a fixed table-layout: when persisted widths
 * are missing, it relies on the existing CSS for fallback layout.
 */
export default function ResizableTable({
  storageKey,
  className,
  defaultWidths = [],
  columns = [],
  children,
  onColumnResize,
  getRowKey,
}) {
  const STORAGE_KEY = `resizable-table:${storageKey}`;
  const [widths, setWidths] = useState(() => loadFromStorage(STORAGE_KEY, defaultWidths));
  const dragState = useRef(null);

  useEffect(() => {
    saveToStorage(STORAGE_KEY, widths);
  }, [STORAGE_KEY, widths]);

  const beginDrag = useCallback((event, columnIndex) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startWidth = parseWidth(widths[columnIndex], defaultWidths[columnIndex], 8);
    dragState.current = { columnIndex, startX, startWidth };
    const handleMove = (ev) => {
      const state = dragState.current;
      if (!state) return;
      const delta = ev.clientX - state.startX;
      const next = Math.max(2, Math.round((state.startWidth + delta / 16) * 10) / 10);
      setWidths((prev) => {
        const arr = Array.isArray(prev) ? prev.slice() : defaultWidths.slice();
        arr[state.columnIndex] = next;
        return arr;
      });
    };
    const handleUp = () => {
      dragState.current = null;
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
  }, [widths, defaultWidths]);

  useEffect(() => {
    if (typeof onColumnResize === "function") {
      onColumnResize(widths);
    }
  }, [widths, onColumnResize]);

  return (
    <table className={className}>
      {children
        ? children({ widths, beginDrag })
        : null}
    </table>
  );
}

export function ResizableTh({
  width,
  defaultWidth,
  onBeginDrag,
  className = "",
  style,
  children,
  ...rest
}) {
  const resolved = parseWidth(width, defaultWidth, 8);
  const thStyle = { ...(style || {}), width: `${resolved}rem`, minWidth: `${resolved}rem` };
  return (
    <th className={className} style={thStyle} {...rest}>
      <span className="resizable-th-inner">{children}</span>
      <span
        role="presentation"
        className="resizable-th-handle"
        onMouseDown={(event) => onBeginDrag && onBeginDrag(event)}
        aria-hidden="true"
      />
    </th>
  );
}

export function ResizableTd({ width, defaultWidth, className = "", children, style, ...rest }) {
  const resolved = parseWidth(width, defaultWidth, 8);
  const tdStyle = { ...(style || {}), width: `${resolved}rem`, minWidth: `${resolved}rem` };
  return (
    <td className={className} style={tdStyle} {...rest}>
      {children}
    </td>
  );
}

function parseWidth(explicit, fallback, defaultRem) {
  const raw = explicit ?? fallback;
  if (raw === undefined || raw === null) return defaultRem;
  if (typeof raw === "number") return raw;
  const str = String(raw).trim();
  if (str.endsWith("rem")) return parseFloat(str) || defaultRem;
  if (str.endsWith("px")) return (parseFloat(str) || defaultRem * 16) / 16;
  const num = parseFloat(str);
  return Number.isFinite(num) ? num : defaultRem;
}

function loadFromStorage(key, defaults) {
  if (typeof window === "undefined") return defaults.slice();
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return defaults.slice();
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return defaults.slice();
    return parsed;
  } catch (err) {
    return defaults.slice();
  }
}

function saveToStorage(key, widths) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(widths));
  } catch (err) {
    /* noop (quota / private mode) */
  }
}
