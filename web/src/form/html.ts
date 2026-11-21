// Allow-list sanitiser for the HTML in `description` fields. The output may only contain
// inline data: images, so rendering a config never fetches anything from the network.

const ALLOWED_TAGS = new Set([
  "P",
  "BR",
  "STRONG",
  "B",
  "EM",
  "I",
  "U",
  "UL",
  "OL",
  "LI",
  "A",
  "SPAN",
  "IMG",
  "H3",
  "H4",
  "SMALL",
  "SUB",
  "SUP",
]);

const SAFE_HREF = /^(https?:|mailto:|tel:)/i;
const SAFE_IMG = /^data:image\/(png|jpe?g|gif|webp);base64,/i;

function cleanNode(node: Node, doc: Document): Node | null {
  if (node.nodeType === Node.TEXT_NODE) return doc.createTextNode(node.textContent ?? "");
  if (node.nodeType !== Node.ELEMENT_NODE) return null;
  const el = node as Element;
  const children = Array.from(el.childNodes)
    .map((child) => cleanNode(child, doc))
    .filter((child): child is Node => child !== null);

  if (!ALLOWED_TAGS.has(el.tagName)) {
    // Keep the text of unknown wrappers (div, font, …), drop the element itself.
    const fragment = doc.createDocumentFragment();
    for (const child of children) fragment.append(child);
    return fragment;
  }

  if (el.tagName === "IMG") {
    const src = el.getAttribute("src") ?? "";
    if (!SAFE_IMG.test(src)) return null;
    const img = doc.createElement("img");
    img.setAttribute("src", src);
    const alt = el.getAttribute("alt");
    img.setAttribute("alt", alt && alt !== "undefined" ? alt : "");
    for (const dim of ["width", "height"]) {
      const v = el.getAttribute(dim);
      if (v && /^\d+$/.test(v)) img.setAttribute(dim, v);
    }
    return img;
  }

  if (el.tagName === "A") {
    const href = (el.getAttribute("href") ?? "").trim();
    // References contain placeholder hrefs such as "klauzulą informacyjną"; show text only.
    const out = doc.createElement(SAFE_HREF.test(href) ? "a" : "span");
    if (out.tagName === "A") {
      out.setAttribute("href", href);
      out.setAttribute("target", "_blank");
      out.setAttribute("rel", "noopener noreferrer");
    }
    for (const child of children) out.append(child);
    if (out.tagName === "A" && (out.textContent ?? "").trim() !== "") {
      const note = doc.createElement("span");
      note.className = "visually-hidden";
      note.textContent = " (otwiera się w nowej karcie)";
      out.append(note);
    }
    return out;
  }

  const out = doc.createElement(el.tagName.toLowerCase());
  for (const child of children) out.append(child);
  return out;
}

/** Returns safe HTML for the body of `html`, or "" when it has no visible content. */
export function sanitizeHtml(html: string | undefined): string {
  if (!html || html.trim() === "") return "";
  const source = new DOMParser().parseFromString(html, "text/html");
  const target = document.implementation.createHTMLDocument("");
  const container = target.createElement("div");
  for (const child of Array.from(source.body.childNodes)) {
    const clean = cleanNode(child, target);
    if (clean) container.append(clean);
  }
  const hasContent =
    (container.textContent ?? "").replace(/ /g, " ").trim() !== "" ||
    container.querySelector("img") !== null;
  return hasContent ? container.innerHTML : "";
}
