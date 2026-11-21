import { type KeyboardEvent, useMemo, useRef, useState } from "react";
import buttons from "../renderer/buttons.module.css";
import styles from "./JsonTree.module.css";
import {
  allContainerIds,
  defaultExpanded,
  flatten,
  highlightParts,
  IMPORTANT_KEYS,
  search,
  type TreeRow,
} from "./treeModel";

function Marked({ text, query }: { text: string; query: string }) {
  let offset = 0;
  return highlightParts(text, query).map((p) => {
    const key = offset;
    offset += p.text.length;
    return p.hit ? <mark key={key}>{p.text}</mark> : p.text;
  });
}

function Row({
  row,
  query,
  isMatch,
  tabbable,
  onActivate,
  setRef,
}: {
  row: TreeRow;
  query: string;
  isMatch: boolean;
  tabbable: boolean;
  onActivate: (id: string) => void;
  setRef: (id: string, el: HTMLDivElement | null) => void;
}) {
  const tag = row.label !== null ? IMPORTANT_KEYS[row.label] : undefined;
  const container = row.kind === "object" || row.kind === "array";
  const long = row.expandable && !container;
  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: keys are handled once on the tree (onKeyDown).
    <div
      role="treeitem"
      tabIndex={tabbable ? 0 : -1}
      aria-level={row.level}
      aria-posinset={row.posInSet}
      aria-setsize={row.setSize}
      aria-expanded={row.expandable ? row.expanded : undefined}
      data-id={row.id}
      data-match={isMatch || undefined}
      ref={(el) => setRef(row.id, el)}
      className={styles.row}
      style={{ paddingInlineStart: `calc(${row.level - 1} * var(--space-4) + var(--space-2))` }}
      onClick={() => onActivate(row.id)}
    >
      <span className={styles.twisty} aria-hidden="true">
        {row.expandable ? (row.expanded ? "▾" : "▸") : ""}
      </span>
      {row.label !== null ? (
        <>
          <span className={styles.key}>
            <Marked text={row.label} query={query} />
          </span>
          <span>: </span>
        </>
      ) : null}
      {container ? (
        // The summary is always shown: it is the one-line form of a collapsed node.
        <span>{row.summary}</span>
      ) : (
        <span className={styles.value}>
          {row.kind === "string" ? '"' : ""}
          <Marked text={row.text} query={query} />
          {row.kind === "string" ? '"' : ""}
        </span>
      )}
      {long ? <span className={styles.more}>{row.expanded ? "zwiń" : "pokaż całość"}</span> : null}
      {tag ? <span className={styles.tag}>{tag}</span> : null}
    </div>
  );
}

/**
 * WAI-ARIA tree over a flat list of rows (aria-level/posinset/setsize instead of nested
 * role=group). Chosen over nested <details> because the arrow-key/Home/End model and roving
 * tabindex are what the task asks for, and a flat list lets collapsed children stay unrendered.
 */
export function JsonTree({ value }: { value: unknown }) {
  const [expanded, setExpanded] = useState(() => defaultExpanded(value));
  const [query, setQuery] = useState("");
  const [focusId, setFocusId] = useState("");
  const refs = useRef(new Map<string, HTMLDivElement>());

  const rows = useMemo(() => flatten(value, expanded), [value, expanded]);
  const { matches } = useMemo(() => search(value, query), [value, query]);
  const tabbableId = rows.some((r) => r.id === focusId) ? focusId : (rows[0]?.id ?? "");

  const toggle = (id: string, open: boolean) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (open) next.add(id);
      else next.delete(id);
      return next;
    });

  const move = (id: string | undefined) => {
    if (id === undefined) return;
    setFocusId(id);
    refs.current.get(id)?.focus();
  };

  const onActivate = (id: string) => {
    setFocusId(id);
    const row = rows.find((r) => r.id === id);
    if (row?.expandable) toggle(id, !row.expanded);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const id = (e.target as HTMLElement).closest<HTMLElement>("[data-id]")?.dataset.id;
    const i = rows.findIndex((r) => r.id === id);
    const row = rows[i];
    if (!row) return;
    const handled = (): void => e.preventDefault();
    switch (e.key) {
      case "ArrowDown":
        handled();
        move(rows[i + 1]?.id);
        break;
      case "ArrowUp":
        handled();
        move(rows[i - 1]?.id);
        break;
      case "Home":
        handled();
        move(rows[0]?.id);
        break;
      case "End":
        handled();
        move(rows[rows.length - 1]?.id);
        break;
      case "ArrowRight":
        handled();
        if (row.expandable && !row.expanded) toggle(row.id, true);
        else if (row.expanded) move(rows[i + 1]?.parentId === row.id ? rows[i + 1]?.id : undefined);
        break;
      case "ArrowLeft":
        handled();
        if (row.expandable && row.expanded) toggle(row.id, false);
        else move(row.parentId ?? undefined);
        break;
      case "Enter":
      case " ":
        handled();
        onActivate(row.id);
        break;
    }
  };

  const onQuery = (q: string) => {
    setQuery(q);
    // Expanding the path once (instead of overriding on every render) keeps manual collapse working.
    const { reveal } = search(value, q);
    if (reveal.size) setExpanded((prev) => new Set([...prev, ...reveal]));
  };

  const status =
    query === "" ? "" : matches.size === 0 ? "Brak dopasowań." : `Dopasowań: ${matches.size}.`;

  return (
    <div className={styles.wrap}>
      <div className={styles.toolbar}>
        <label className={styles.search}>
          <span>Szukaj w JSON</span>
          <input type="search" value={query} onChange={(e) => onQuery(e.target.value)} />
        </label>
        <button
          type="button"
          className={`${buttons.secondary} ${buttons.small}`}
          onClick={() => setExpanded(allContainerIds(value))}
        >
          Rozwiń wszystko
        </button>
        <button
          type="button"
          className={`${buttons.secondary} ${buttons.small}`}
          onClick={() => setExpanded(new Set([""]))}
        >
          Zwiń wszystko
        </button>
      </div>
      <p className={styles.status} aria-live="polite">
        {status}
      </p>
      <div
        role="tree"
        aria-label="Struktura JSON formularza"
        className={styles.tree}
        onKeyDown={onKeyDown}
      >
        {rows.map((row) => (
          <Row
            key={row.id}
            row={row}
            query={query}
            isMatch={matches.has(row.id)}
            tabbable={row.id === tabbableId}
            onActivate={onActivate}
            setRef={(id, el) => {
              if (el) refs.current.set(id, el);
              else refs.current.delete(id);
            }}
          />
        ))}
      </div>
    </div>
  );
}
