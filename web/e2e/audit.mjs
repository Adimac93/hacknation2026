// Live WCAG 2.1 AA and performance probe, no third-party rule engine (axe-core is MPL-2.0).
// Usage: node e2e/audit.mjs [baseUrl]   (stack must run; uses Playwright's own Chromium)
import { chromium } from "@playwright/test";

const base = process.argv[2] ?? "http://localhost:8080";

/** Runs inside the page: returns a list of WCAG findings for the current DOM. */
function probe() {
  const out = [];
  const add = (rule, el, msg) =>
    out.push({
      rule,
      where: el
        ? `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ""}${el.className && typeof el.className === "string" ? `.${el.className.split(" ")[0]}` : ""}`
        : "",
      msg,
    });
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
  };
  if (!document.documentElement.lang) add("3.1.1", null, "html bez lang");
  if (!document.title.trim()) add("2.4.2", null, "brak title");
  const level = (h) => Number(h.getAttribute("aria-level") ?? h.tagName[1] ?? 0);
  const h1 = [...document.querySelectorAll("h1,h2,h3,h4,h5,h6,[role=heading]")].filter(
    (h) => vis(h) && level(h) === 1,
  );
  if (h1.length !== 1) add("1.3.1", null, `h1 na stronie: ${h1.length}`);
  let last = 0;
  for (const h of document.querySelectorAll("h1,h2,h3,h4,h5,h6,[role=heading]")) {
    if (!vis(h)) continue;
    const l = level(h);
    if (last && l > last + 1)
      add("1.3.1", h, `skok nagłówka h${last} -> h${l}: ${h.textContent.trim().slice(0, 40)}`);
    last = l;
  }
  for (const img of document.querySelectorAll("img"))
    if (!img.hasAttribute("alt") && img.getAttribute("role") !== "presentation")
      add("1.1.1", img, "img bez alt");
  const name = (el) =>
    (el.getAttribute("aria-label") || "").trim() ||
    (el.getAttribute("aria-labelledby") &&
      [...el.getAttribute("aria-labelledby").split(" ")]
        .map((i) => document.getElementById(i)?.textContent ?? "")
        .join("")
        .trim()) ||
    (el.labels &&
      [...el.labels]
        .map((l) => l.textContent)
        .join("")
        .trim()) ||
    el.textContent.trim() ||
    (el.getAttribute("title") || "").trim() ||
    (el.getAttribute("placeholder") || "").trim();
  for (const el of document.querySelectorAll(
    "a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=tab],[role=combobox],[role=checkbox],[role=radio]",
  )) {
    if (!vis(el) && el.type !== "file") continue;
    if (!name(el)) add("4.1.2", el, "brak nazwy dostępnej");
  }
  const ids = new Map();
  for (const el of document.querySelectorAll("[id]")) ids.set(el.id, (ids.get(el.id) ?? 0) + 1);
  for (const [id, n] of ids) if (n > 1) add("4.1.1", null, `duplikat id: ${id} x${n}`);
  // contrast
  const rgb = (c) => c.match(/[\d.]+/g).map(Number);
  const lum = ([r, g, b]) =>
    [r, g, b]
      .map((v) => (v / 255 <= 0.03928 ? v / 255 / 12.92 : ((v / 255 + 0.055) / 1.055) ** 2.4))
      .reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0);
  const bg = (el) => {
    for (let e = el; e; e = e.parentElement) {
      const c = rgb(getComputedStyle(e).backgroundColor);
      if (c.length === 3 || c[3] > 0.99) return c.slice(0, 3);
    }
    return [255, 255, 255];
  };
  const seen = new Set();
  for (const el of document.querySelectorAll("body *")) {
    if (!vis(el) || ![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
      continue;
    const s = getComputedStyle(el);
    const fg = rgb(s.color);
    const b = bg(el);
    const [l1, l2] = [lum(fg), lum(b)].sort((a, c) => c - a);
    const ratio = (l1 + 0.05) / (l2 + 0.05);
    const px = parseFloat(s.fontSize);
    const large = px >= 24 || (px >= 18.66 && Number(s.fontWeight) >= 700);
    const need = large ? 3 : 4.5;
    const key = `${s.color}|${b}|${px}`;
    if (ratio < need && !seen.has(key) && !el.closest("[disabled]")) {
      seen.add(key);
      add("1.4.3", el, `kontrast ${ratio.toFixed(2)}:1 < ${need} (${s.color} na rgb(${b}))`);
    }
  }
  // target size (2.5.8 AA is 24px; we report < 24)
  for (const el of document.querySelectorAll(
    "a[href],button,select,input:not([type=hidden]):not([type=file])",
  )) {
    if (!vis(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 24 || r.height < 24)
      add(
        "2.5.8",
        el,
        `cel ${Math.round(r.width)}x${Math.round(r.height)}px: ${name(el).slice(0, 30)}`,
      );
  }
  // text must not be justified / too small
  for (const el of document.querySelectorAll("p,li,td,span,label")) {
    if (!vis(el) || !el.textContent.trim()) continue;
    const s = getComputedStyle(el);
    if (parseFloat(s.fontSize) < 12) add("1.4.4", el, `font ${s.fontSize}`);
  }
  return out;
}

const findings = [];
const perf = [];
const browser = await chromium.launch();

async function view(label, setup, width = 1366) {
  const ctx = await browser.newContext({ viewport: { width, height: 800 } });
  const page = await ctx.newPage();
  await page.goto(base + "/");
  await setup(page);
  const f = await page.evaluate(probe);
  for (const x of f) findings.push({ view: `${label} @${width}`, ...x });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  if (overflow > 1)
    findings.push({
      view: `${label} @${width}`,
      rule: "1.4.10",
      where: "",
      msg: `poziome przewijanie +${overflow}px`,
    });
  // keyboard: every tab stop gets a visible focus indicator
  let bad = 0;
  let stops = 0;
  for (let i = 0; i < 60; i++) {
    await page.keyboard.press("Tab");
    const r = await page.evaluate(() => {
      const e = document.activeElement;
      if (!e || e === document.body) return null;
      const s = getComputedStyle(e);
      const ring =
        (s.outlineStyle !== "none" && parseFloat(s.outlineWidth) >= 2) || s.boxShadow !== "none";
      const lbl = e.type === "file" ? !!e.labels?.length : true;
      return { ring: ring || e.type === "file", tag: e.tagName + (e.id ? `#${e.id}` : ""), lbl };
    });
    if (!r) break;
    stops++;
    if (!r.ring) {
      bad++;
      findings.push({
        view: `${label} @${width}`,
        rule: "2.4.7",
        where: r.tag,
        msg: "brak widocznego fokusu",
      });
    }
  }
  await ctx.close();
  return { stops, bad };
}

const demo = async (p) => {
  await p.getByRole("button", { name: "Wczytaj dane przykładowe" }).click();
  await p.getByRole("region", { name: /^Wynik:/ }).waitFor();
};
const tab = (name) => async (p) => {
  await demo(p);
  await p
    .getByRole("region", { name: /^Wynik:/ })
    .getByRole("tab", { name })
    .click();
};
const views = [
  ["start", async () => {}],
  ["wynik: dokument i formularz", demo],
  ["wynik: JSON", tab("JSON")],
  ["wynik: raport", tab("Raport")],
  [
    "/podglad",
    async (p) => {
      await p.goto(base + "/podglad");
      await p.waitForTimeout(500);
    },
  ],
];
const keyb = {};
for (const [label, setup] of views) {
  keyb[label] = await view(label, setup, 1366);
  await view(label, setup, 320); // reflow
  await view(label, setup, 683); // 200% zoom equivalent
}

// ---- performance ----
for (const [label, path, throttle] of [
  ["start", "/", 1],
  ["start, CPU 4x", "/", 4],
  ["/podglad, CPU 4x", "/podglad", 4],
]) {
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: throttle });
  await page.addInitScript(() => {
    window.__m = { lcp: 0, cls: 0, longTasks: 0, longMs: 0 };
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) window.__m.lcp = e.startTime;
    }).observe({ type: "largest-contentful-paint", buffered: true });
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) if (!e.hadRecentInput) window.__m.cls += e.value;
    }).observe({ type: "layout-shift", buffered: true });
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        window.__m.longTasks++;
        window.__m.longMs += e.duration;
      }
    }).observe({ type: "longtask", buffered: true });
  });
  await page.goto(base + path, { waitUntil: "load" });
  await page.waitForTimeout(1500);
  const m = await page.evaluate(() => {
    const nav = performance.getEntriesByType("navigation")[0];
    const fcp = performance.getEntriesByName("first-contentful-paint")[0]?.startTime ?? 0;
    const res = performance.getEntriesByType("resource");
    return {
      ...window.__m,
      fcp,
      dcl: nav.domContentLoadedEventEnd,
      load: nav.loadEventEnd,
      requests: res.length + 1,
      kb: Math.round((res.reduce((a, r) => a + r.transferSize, 0) + nav.transferSize) / 1024),
      nodes: document.getElementsByTagName("*").length,
      heapMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null,
    };
  });
  perf.push({ label, ...m });
  await ctx.close();
}

// interaction cost: demo result with CPU 4x
{
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await page.goto(base + "/");
  const t = {};
  let t0 = Date.now();
  await page.getByRole("button", { name: "Wczytaj dane przykładowe" }).click();
  await page.getByRole("region", { name: /^Wynik:/ }).waitFor();
  t["wynik z danych przykładowych"] = Date.now() - t0;
  const r = page.getByRole("region", { name: /^Wynik:/ });
  for (const n of ["JSON", "Raport", "Dokument i formularz"]) {
    t0 = Date.now();
    await r.getByRole("tab", { name: n }).click();
    await r.getByRole("tabpanel").waitFor();
    t[`przełączenie na ${n}`] = Date.now() - t0;
  }
  await r.getByRole("tab", { name: "JSON" }).click();
  t0 = Date.now();
  await r.getByRole("button", { name: /Rozwiń wszystko/ }).click();
  await page.waitForTimeout(50);
  t["JSON: rozwiń wszystko"] = Date.now() - t0;
  perf.push({ label: "interakcje (CPU 4x), ms", ...t });
  await ctx.close();
}
await browser.close();

const byRule = {};
for (const f of findings) {
  const key = `${f.rule} ${f.msg.replace(/[\d.]+/g, "#").slice(0, 40)}`;
  byRule[key] ??= [];
  byRule[key].push(f);
}
console.log("\n=== WCAG: naruszenia (po deduplikacji) ===");
if (!findings.length) console.log("brak");
for (const [k, v] of Object.entries(byRule))
  console.log(`${v.length}x  ${k}\n     np. ${v[0].view} | ${v[0].where} | ${v[0].msg}`);
console.log("\n=== Klawiatura (liczba przystanków Tab) ===", JSON.stringify(keyb));
console.log("\n=== Wydajność ===");
for (const p of perf) console.log(JSON.stringify(p));
