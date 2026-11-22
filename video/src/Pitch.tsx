import { loadFont as loadArchivo } from "@remotion/google-fonts/Archivo";
import { loadFont as loadPlexMono } from "@remotion/google-fonts/IBMPlexMono";
import type React from "react";
import { createContext, useContext } from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  Series,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
// Sample blanks offered in the demo (built from Docs/ by devtools/build_samples.py).
import samples from "../../web/public/samples/index.json";

const BODY = loadArchivo("normal", { weights: ["400", "600", "800"], subsets: ["latin", "latin-ext"] })
  .fontFamily;
const MONO = loadPlexMono("normal", { weights: ["400", "600"], subsets: ["latin", "latin-ext"] })
  .fontFamily;

// Brand palette: DESIGN.md and ksiega-znaku-biurokratka.pdf.
const C = {
  paper: "#f3f2f2",
  sheet: "#eae9e9",
  ink: "#201e1d",
  ink2: "#2d2b2b",
  red: "#ec3013",
  redText: "#ae1800",
  tint: "#ffe0d9",
  muted: "#605d5d",
  white: "#ffffff",
};

// Numbers on screen come from files in the repository; the source is next to each one.
const N = {
  forms: samples.forms.length, // web/public/samples/index.json
  matrixOk: 53, // research/08-macierz-formatow.md: 53 of 53 blanks processed, 0 rule errors
  outputs: 6, // outputs/README.md: forms 3, 4, 6-9 in model mode, 0 rule errors
  coverageLow: 64, // research/10-pokrycie-referencji.md: model, strict label match
  coverageHigh: 82,
  // README.md "Koszt i czas": about 0.001 USD per form on EdenAI, i.e. well under one grosz.
};

const SCENES = {
  hook: 165,
  formats: 210,
  solution: 240,
  drop: 300,
  upload: 150,
  queue: 150,
  auditor: 285,
  report: 195,
  numbers: 240,
  benefits: 255,
  trust: 210,
  cta: 210,
};
export const TOTAL = Object.values(SCENES).reduce((a, b) => a + b, 0);

// ---------- helpers ----------

const Dark = createContext(false);

const useIn = (delay = 0, damping = 200) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: { damping } });
};

const Rise: React.FC<{
  delay?: number;
  y?: number;
  x?: number;
  style?: React.CSSProperties;
  children: React.ReactNode;
}> = ({ delay = 0, y = 40, x = 0, style, children }) => {
  const p = useIn(delay);
  return (
    <div style={{ opacity: p, transform: `translate(${(1 - p) * x}px, ${(1 - p) * y}px)`, ...style }}>
      {children}
    </div>
  );
};

const Pop: React.FC<{ delay?: number; style?: React.CSSProperties; children: React.ReactNode }> = ({
  delay = 0,
  style,
  children,
}) => {
  const p = useIn(delay, 12);
  return <div style={{ transform: `scale(${p})`, opacity: Math.min(1, p * 2), ...style }}>{children}</div>;
};

const Scene: React.FC<{ bg?: "paper" | "white" | "ink" | "red"; children: React.ReactNode }> = ({
  bg = "paper",
  children,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const o = interpolate(frame, [0, 10, durationInFrames - 10, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const dark = bg === "ink" || bg === "red";
  const background = { paper: C.paper, white: C.white, ink: C.ink, red: C.redText }[bg];
  return (
    <Dark.Provider value={dark}>
      <AbsoluteFill style={{ opacity: o, color: dark ? C.paper : C.ink, background }}>
        {bg === "paper" && (
          // Quiet grid of form boxes in the background ("kratki" from the brand book).
          <AbsoluteFill
            style={{
              backgroundImage: `linear-gradient(${C.sheet} 2px, transparent 2px), linear-gradient(90deg, ${C.sheet} 2px, transparent 2px)`,
              backgroundSize: "96px 116px",
              opacity: 0.55,
            }}
          />
        )}
        {children}
      </AbsoluteFill>
    </Dark.Provider>
  );
};

const Kicker: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const dark = useContext(Dark);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        fontFamily: MONO,
        fontSize: 28,
        fontWeight: 600,
        letterSpacing: 4,
        textTransform: "uppercase",
        color: dark ? "#ff8a73" : C.redText,
      }}
    >
      <div style={{ width: 24, height: 28, border: `4px solid ${C.red}`, background: dark ? "transparent" : C.white }} />
      {children}
    </div>
  );
};

const H: React.FC<{ children: React.ReactNode; size?: number; style?: React.CSSProperties }> = ({
  children,
  size = 84,
  style,
}) => (
  <div style={{ fontSize: size, fontWeight: 800, lineHeight: 1.08, letterSpacing: "-0.02em", ...style }}>
    {children}
  </div>
);

const Em: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const dark = useContext(Dark);
  return <span style={{ color: dark ? "#ff8a73" : C.redText }}>{children}</span>;
};

const Bullet: React.FC<{ delay: number; children: React.ReactNode }> = ({ delay, children }) => {
  const dark = useContext(Dark);
  return (
    <Rise delay={delay} y={0} x={-40} style={{ display: "flex", gap: 22, alignItems: "flex-start" }}>
      <div style={{ marginTop: 12, width: 20, height: 24, border: `4px solid ${C.red}`, flexShrink: 0 }} />
      <div style={{ fontSize: 36, lineHeight: 1.3, color: dark ? "#d8d4d4" : C.muted }}>{children}</div>
    </Rise>
  );
};

/** Official logo file; dark scenes use the dark version (logo-pack/). */
const Logo: React.FC<{ w: number; delay?: number }> = ({ w, delay = 0 }) => {
  const dark = useContext(Dark);
  const p = useIn(delay, 14);
  return (
    <Img
      src={staticFile(dark ? "logo/ciemny.png" : "logo/jasny.png")}
      style={{ width: w, opacity: Math.min(1, p * 1.5), transform: `scale(${0.9 + p * 0.1})` }}
    />
  );
};

const Browser: React.FC<{
  src: string;
  w: number;
  h: number;
  scroll?: [number, number];
  zoom?: [number, number];
  origin?: string;
  delay?: number;
  style?: React.CSSProperties;
}> = ({ src, w, h, scroll = [0, 0], zoom = [1, 1], origin = "50% 0%", delay = 0, style }) => {
  const f = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const p = useIn(delay);
  const t = interpolate(f, [delay + 15, durationInFrames - 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.quad),
  });
  return (
    <div
      style={{
        width: w,
        overflow: "hidden",
        background: C.white,
        border: `3px solid ${C.ink}`,
        boxShadow: "0 30px 80px rgba(32,30,29,.25)",
        opacity: p,
        transform: `translateY(${(1 - p) * 80}px)`,
        ...style,
      }}
    >
      <div
        style={{
          height: 46,
          background: C.sheet,
          borderBottom: `3px solid ${C.ink}`,
          display: "flex",
          alignItems: "center",
          gap: 10,
          paddingLeft: 18,
        }}
      >
        {[C.red, C.ink, C.muted].map((c) => (
          <div key={c} style={{ width: 14, height: 14, background: c }} />
        ))}
        <div
          style={{
            marginLeft: 16,
            height: 28,
            width: w * 0.5,
            background: C.white,
            border: `2px solid ${C.muted}`,
            color: C.muted,
            fontFamily: MONO,
            fontSize: 16,
            lineHeight: "24px",
            paddingLeft: 12,
          }}
        >
          formularze.heckyeah.pl
        </div>
      </div>
      <div style={{ height: h, overflow: "hidden" }}>
        <Img
          src={staticFile(`zrzuty/${src}`)}
          style={{
            width: w,
            display: "block",
            transformOrigin: origin,
            transform: `translateY(${-interpolate(t, [0, 1], scroll)}px) scale(${interpolate(t, [0, 1], zoom)})`,
          }}
        />
      </div>
    </div>
  );
};

const Tag: React.FC<{ delay: number; color?: string; style?: React.CSSProperties; children: React.ReactNode }> = ({
  delay,
  color = C.ink,
  style,
  children,
}) => (
  <Pop
    delay={delay}
    style={{
      position: "absolute",
      background: color,
      color: C.white,
      fontSize: 30,
      fontWeight: 600,
      padding: "14px 26px",
      boxShadow: "0 16px 40px rgba(32,30,29,.3)",
      whiteSpace: "nowrap",
      ...style,
    }}
  >
    {children}
  </Pop>
);

const Split: React.FC<{ left: React.ReactNode; right: React.ReactNode; leftW?: number }> = ({
  left,
  right,
  leftW = 700,
}) => (
  <AbsoluteFill style={{ flexDirection: "row", alignItems: "center", padding: "0 100px", gap: 60 }}>
    <div style={{ width: leftW, flexShrink: 0, display: "flex", flexDirection: "column", gap: 28 }}>{left}</div>
    <div
      style={{
        flex: 1,
        position: "relative",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {right}
    </div>
  </AbsoluteFill>
);

const Count: React.FC<{ to: number; delay: number; suffix?: string }> = ({ to, delay, suffix = "" }) => {
  const f = useCurrentFrame();
  const v = interpolate(f, [delay, delay + 45], [0, to], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  return (
    <>
      {Math.round(v)}
      {suffix}
    </>
  );
};

// ---------- scenes ----------

/** Official logo (logo-pack/ciemny) revealed box by box: row BIURO + empty box, then row KRATKA. */
const HookLogo: React.FC<{ w: number }> = ({ w }) => {
  const f = useCurrentFrame();
  const cells = (start: number) => Math.min(6, Math.max(0, Math.floor((f - start) / 4) + 1));
  const top = cells(6);
  const bottom = cells(32);
  const h = (w * 235) / 575; // logo-pack SVG viewBox 575 x 235, two rows of six boxes
  const layer = (clip: string) => (
    <Img src={staticFile("logo/ciemny.png")} style={{ position: "absolute", inset: 0, width: w, clipPath: clip }} />
  );
  return (
    <div style={{ position: "relative", width: w, height: h }}>
      {layer(`inset(0 ${100 - (top / 6) * 100}% 50% 0)`)}
      {layer(`inset(50% ${100 - (bottom / 6) * 100}% 0 0)`)}
    </div>
  );
};

const Hook: React.FC = () => {
  return (
    <Scene bg="ink">
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", textAlign: "center", gap: 60 }}>
        <HookLogo w={620} />
        <Rise delay={62}>
          <H size={84}>
            Blankiet urzędowy <Em>→</Em> e-formularz
          </H>
        </Rise>
        <Rise delay={92} style={{ fontSize: 40, color: "#d8d4d4", maxWidth: 1400 }}>
          Plik gotowy do importu w Generatorze Formularzy COI. Bez ręcznego przepisywania.
        </Rise>
      </AbsoluteFill>
    </Scene>
  );
};

const Formats: React.FC = () => {
  const f = useCurrentFrame();
  const formats = ["PDF", "Word", "Excel", "Calc", "Skan", "Zdjęcie", "JPG", "PNG"];
  const merge = interpolate(f, [120, 165], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.cubic),
  });
  return (
    <Scene>
      <AbsoluteFill style={{ padding: "90px 110px" }}>
        <Rise>
          <Kicker>Problem</Kicker>
        </Rise>
        <Rise delay={8} style={{ marginTop: 16 }}>
          <H size={76}>
            Wnioski to PDF-y, Word, Excel i skany. <Em>Każdy trzeba ręcznie przerobić.</Em>
          </H>
        </Rise>
      </AbsoluteFill>
      {formats.map((fmt, i) => {
        const d = 30 + i * 8;
        const p = spring({ frame: f - d, fps: 30, config: { damping: 14 } });
        const col = i % 4;
        const row = Math.floor(i / 4);
        const x0 = 260 + col * 360;
        const y0 = 500 + row * 190;
        const x = x0 + (860 - x0) * merge;
        const y = y0 + (640 - y0) * merge;
        return (
          <div
            key={fmt}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: 220,
              height: 130,
              background: C.white,
              border: `4px solid ${C.ink}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: MONO,
              fontSize: 44,
              fontWeight: 600,
              transform: `scale(${p * (1 - merge * 0.4)}) rotate(${(1 - merge) * (i % 2 ? 3 : -3)}deg)`,
              opacity: Math.min(1, p * 2) * (1 - merge * 0.9),
            }}
          >
            {fmt}
          </div>
        );
      })}
      <Pop
        delay={150}
        style={{
          position: "absolute",
          left: 700,
          top: 590,
          width: 540,
          padding: "34px 40px",
          background: C.red,
          color: C.white,
          textAlign: "center",
          fontFamily: MONO,
          fontSize: 48,
          fontWeight: 600,
        }}
      >
        e-formularz COI
      </Pop>
    </Scene>
  );
};

const Solution: React.FC = () => {
  const steps = [
    { n: "1", t: "Wgraj blankiet", s: "PDF, Word, Excel, skan albo zdjęcie" },
    { n: "2", t: "Sprawdź", s: "Blankiet obok gotowego formularza, pole po polu" },
    { n: "3", t: "Pobierz", s: "Plik gotowy do importu w Generatorze Formularzy COI" },
  ];
  return (
    <Scene>
      <AbsoluteFill style={{ padding: "90px 110px" }}>
        <Rise>
          <Kicker>Rozwiązanie</Kicker>
        </Rise>
        <Rise delay={8} style={{ marginTop: 16 }}>
          <H size={80}>
            Biurokratka przygotowuje formularz. <Em>Urzędnik go zatwierdza.</Em>
          </H>
        </Rise>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 36, marginTop: 90 }}>
          {steps.map((st, i) => (
            <Pop
              key={st.t}
              delay={40 + i * 22}
              style={{ background: i === 1 ? C.tint : C.white, border: `4px solid ${C.ink}`, padding: 44 }}
            >
              <div style={{ fontFamily: MONO, fontSize: 40, fontWeight: 600, color: C.redText }}>{st.n}</div>
              <div style={{ fontSize: 56, fontWeight: 800, marginTop: 8 }}>{st.t}</div>
              <div style={{ fontSize: 32, lineHeight: 1.35, color: C.muted, marginTop: 14 }}>{st.s}</div>
            </Pop>
          ))}
        </div>
        <Rise delay={140} style={{ marginTop: 60, fontSize: 36, color: C.muted }}>
          Formularz jest przeprojektowany według standardów COI, a nie przepisany jeden do jednego.
        </Rise>
      </AbsoluteFill>
    </Scene>
  );
};

/** Mouse pointer drawn as an SVG arrow. */
const Pointer: React.FC<{ style?: React.CSSProperties }> = ({ style }) => (
  <svg width={46} height={58} viewBox="0 0 23 29" style={style} aria-label="kursor">
    <path d="M1 1 L1 23 L7 17.5 L11 27 L15 25.3 L11 16 L19 16 Z" fill={C.ink} stroke={C.white} strokeWidth={1.6} strokeLinejoin="round" />
  </svg>
);

/** Browser chrome around arbitrary content (same look as Browser). */
const Frame: React.FC<{ w: number; h: number; delay?: number; children: React.ReactNode }> = ({ w, h, delay = 0, children }) => {
  const p = useIn(delay);
  return (
    <div
      style={{
        position: "relative",
        width: w,
        background: C.white,
        border: `3px solid ${C.ink}`,
        boxShadow: "0 30px 80px rgba(32,30,29,.25)",
        opacity: p,
        transform: `translateY(${(1 - p) * 80}px)`,
      }}
    >
      <div style={{ height: 46, background: C.sheet, borderBottom: `3px solid ${C.ink}`, display: "flex", alignItems: "center", gap: 10, paddingLeft: 18 }}>
        {[C.red, C.ink, C.muted].map((c) => (
          <div key={c} style={{ width: 14, height: 14, background: c }} />
        ))}
        <div style={{ marginLeft: 16, height: 28, width: w * 0.5, background: C.white, border: `2px solid ${C.muted}`, color: C.muted, fontFamily: MONO, fontSize: 16, lineHeight: "24px", paddingLeft: 12 }}>
          formularze.heckyeah.pl
        </div>
      </div>
      <div style={{ position: "relative", height: h, overflow: "hidden" }}>{children}</div>
    </div>
  );
};

const DROP = { w: 980, h: 551 };
// Upload zone in 01-start.png, as a share of the screenshot (measured on the capture).
const ZONE = { left: 0.12, top: 0.32, width: 0.496, height: 0.406 };

const DropDemo: React.FC = () => {
  const f = useCurrentFrame();
  const { w, h } = DROP;
  const hover = interpolate(f, [82, 92, 118, 126], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const dropped = interpolate(f, [112, 126], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.quad) });
  const swap = interpolate(f, [128, 146], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const zoom = interpolate(f, [146, 290], [1.35, 1.5], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const ripple = interpolate(f, [114, 140], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Frame w={w} h={h} delay={5}>
      <Img src={staticFile("zrzuty/01-start.png")} style={{ position: "absolute", width: w, opacity: 1 - swap }} />
      <Img
        src={staticFile("zrzuty/03-analiza.png")}
        style={{ position: "absolute", width: w, opacity: swap, transformOrigin: "30% 100%", transform: `scale(${zoom})` }}
      />
      {/* Drag-over state of the zone: accent border and tint, as in web/src/workspace/Upload.module.css */}
      <div
        style={{
          position: "absolute",
          left: w * ZONE.left,
          top: h * ZONE.top,
          width: w * ZONE.width,
          height: h * ZONE.height,
          boxSizing: "border-box",
          border: `4px dashed ${C.red}`,
          background: "rgba(255,224,217,.7)",
          opacity: hover * (1 - swap),
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "center",
          paddingTop: 14,
          fontSize: 24,
          fontWeight: 700,
          color: C.redText,
        }}
      >
        Upuść, aby dodać do kolejki
      </div>
      <div
        style={{
          position: "absolute",
          left: w * (ZONE.left + ZONE.width / 2) - 60 * (1 + ripple),
          top: h * (ZONE.top + ZONE.height / 2) - 60 * (1 + ripple),
          width: 120 * (1 + ripple),
          height: 120 * (1 + ripple),
          border: `4px solid ${C.red}`,
          opacity: f >= 114 ? (1 - ripple) * (1 - swap) : 0,
        }}
      />
    </Frame>
  );
};

/** The dragged file lives outside the window frame so it can start beside it. */
const DraggedFile: React.FC = () => {
  const f = useCurrentFrame();
  const { w, h } = DROP;
  const t = interpolate(f, [30, 100], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
  const x0 = -560;
  const y0 = h + 40;
  const x1 = w * (ZONE.left + ZONE.width / 2) - 130;
  const y1 = h * (ZONE.top + ZONE.height / 2) - 60;
  const cx = x0 + (x1 - x0) * 0.35;
  const cy = y1 - 220;
  const bx = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t ** 2 * x1;
  const by = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t ** 2 * y1;
  const appear = useIn(8, 14);
  const grab = interpolate(f, [18, 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const dropped = interpolate(f, [112, 126], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.quad) });
  const pointerAway = interpolate(f, [126, 150], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  // Coordinates are relative to the screenshot area (below the 46 px bar, inside the 3 px border).
  return (
    <div style={{ position: "absolute", left: 3, top: 3 + 46 + 3, width: w, height: h, pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: bx,
          top: by,
          width: 260,
          padding: "18px 20px",
          boxSizing: "border-box",
          background: C.white,
          border: `3px solid ${C.ink}`,
          boxShadow: `0 ${10 + grab * 20}px ${30 + grab * 30}px rgba(32,30,29,${0.2 + grab * 0.15})`,
          display: "flex",
          gap: 16,
          alignItems: "center",
          opacity: Math.min(1, appear * 2) * (1 - dropped),
          transform: `rotate(${grab * -5 * (1 - dropped)}deg) scale(${(0.9 + appear * 0.1) * (1 + grab * 0.06) * (1 - dropped * 0.6)})`,
        }}
      >
        <div style={{ width: 62, height: 78, background: C.red, color: C.white, fontFamily: MONO, fontWeight: 600, fontSize: 18, display: "flex", alignItems: "flex-end", justifyContent: "center", paddingBottom: 8, boxSizing: "border-box", flexShrink: 0 }}>
          PDF
        </div>
        <div style={{ fontSize: 19, lineHeight: 1.25, fontWeight: 600 }}>
          Wniosek o zajęcie pasa drogowego.pdf
          <div style={{ fontFamily: MONO, fontWeight: 400, fontSize: 16, color: C.muted, marginTop: 4 }}>190 KB</div>
        </div>
      </div>
      <Pointer
        style={{
          position: "absolute",
          left: bx + 228 + pointerAway * 120,
          top: by + 92 + pointerAway * 60,
          opacity: Math.min(1, appear * 2) * (1 - pointerAway),
        }}
      />
    </div>
  );
};

const Drop: React.FC = () => (
  <Scene>
    <Split
      left={
        <>
          <Rise>
            <Kicker>Krok 1 · Wgraj blankiet</Kicker>
          </Rise>
          <Rise delay={8}>
            <H>
              Przeciągnij plik. <Em>Albo wybierz z dysku.</Em>
            </H>
          </Rise>
          <Bullet delay={35}>PDF, Word, Excel, skan albo zdjęcie telefonem</Bullet>
          <Bullet delay={130}>Analiza rusza od razu, postęp widać na żywo</Bullet>
          <Bullet delay={160}>Przesłany plik nie jest nigdzie zapisywany</Bullet>
        </>
      }
      right={
        <div style={{ position: "relative" }}>
          <DropDemo />
          <DraggedFile />
          <Tag delay={175} color={C.redText} style={{ right: -10, top: -40 }}>
            Analizuję plik 1 z 1
          </Tag>
        </div>
      }
    />
  </Scene>
);

const Upload: React.FC = () => (
  <Scene>
    <Split
      left={
        <>
          <Rise>
            <Kicker>Albo bez własnego pliku</Kicker>
          </Rise>
          <Rise delay={8}>
            <H>
              Przykłady z <Em>materiałów COI</Em>
            </H>
          </Rise>
          <Bullet delay={35}>{N.forms} prawdziwych wniosków z materiałów konkursu</Bullet>
          <Bullet delay={55}>Jedno kliknięcie, by zobaczyć wynik</Bullet>
        </>
      }
      right={<Browser src="02-przyklady.png" w={980} h={551} zoom={[1.05, 1.3]} origin="25% 75%" delay={10} />}
    />
  </Scene>
);

const Queue: React.FC = () => (
  <Scene>
    <Split
      left={
        <>
          <Rise>
            <Kicker>Krok 2 · Kolejka</Kicker>
          </Rise>
          <Rise delay={8}>
            <H>
              Kilka plików naraz. <Em>Postęp na żywo.</Em>
            </H>
          </Rise>
          <Bullet delay={40}>Wiele wniosków za jednym razem</Bullet>
          <Bullet delay={60}>Wynik w kilkanaście sekund</Bullet>
        </>
      }
      right={
        <>
          <Browser src="04-gotowe.png" w={980} h={551} zoom={[1.5, 1.6]} origin="35% 95%" delay={15} />
          <Tag delay={80} color={C.redText} style={{ right: 10, top: 230 }}>
            Gotowe: 69 pól
          </Tag>
        </>
      }
    />
  </Scene>
);

const Auditor: React.FC = () => (
  <Scene>
    <Split
      leftW={640}
      left={
        <>
          <Rise>
            <Kicker>Krok 3 · Weryfikacja</Kicker>
          </Rise>
          <Rise delay={8}>
            <H size={78}>
              Urzędnik jako <Em>audytor</Em>, nie przepisywacz
            </H>
          </Rise>
          <Bullet delay={45}>Blankiet obok gotowego formularza</Bullet>
          <Bullet delay={70}>Każde pole wskazuje miejsce w blankiecie, z którego powstało</Bullet>
          <Bullet delay={95}>Niepewne pola są oznaczone do sprawdzenia</Bullet>
        </>
      }
      right={
        <>
          <Browser src="06-podglad.png" w={1060} h={596} zoom={[1, 1.2]} origin="0% 35%" delay={15} />
          <Tag delay={120} color={C.red} style={{ left: 150, top: 600 }}>
            Skąd wzięło się to pole
          </Tag>
          <Tag delay={150} style={{ right: 20, top: 820 }}>
            Tak zobaczy go obywatel
          </Tag>
        </>
      }
    />
  </Scene>
);

const Report: React.FC = () => (
  <Scene>
    <Split
      left={
        <>
          <Rise>
            <Kicker>Krok 4 · Gotowe do importu</Kicker>
          </Rise>
          <Rise delay={8}>
            <H>
              Zgodne z regułami COI. <Em>Pobierasz jednym kliknięciem.</Em>
            </H>
          </Rise>
          <Bullet delay={40}>Automatyczna kontrola reguł technicznych COI</Bullet>
          <Bullet delay={60}>Propozycje nowych słowników</Bullet>
          <Bullet delay={80}>Plik do zaimportowania w Generatorze Formularzy</Bullet>
        </>
      }
      right={<Browser src="08-raport.png" w={980} h={551} zoom={[1, 1.2]} origin="0% 0%" delay={15} />}
    />
  </Scene>
);

const Numbers: React.FC = () => {
  const items = [
    { big: `${N.matrixOk} / ${N.matrixOk}`, l: "wniosków konkursowych w każdym formacie przetworzonych bez błędu" },
    { big: `${N.outputs} / ${N.outputs}`, l: "gotowych e-formularzy dla zadań konkursu" },
    { big: `${N.coverageLow}–${N.coverageHigh}%`, l: "pól zgodnych z formularzami wzorcowymi COI" },
    { big: "< 1 gr", l: "koszt sztucznej inteligencji na jeden formularz" },
  ];
  return (
    <Scene bg="ink">
      <AbsoluteFill style={{ padding: "90px 110px" }}>
        <Rise>
          <Kicker>Sprawdzone na materiałach konkursu</Kicker>
        </Rise>
        <Rise delay={8} style={{ marginTop: 16 }}>
          <H size={76}>Liczby zamiast deklaracji</H>
        </Rise>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 36, marginTop: 130 }}>
          {items.map((it, i) => (
            <Rise key={it.l} delay={25 + i * 18} style={{ borderTop: `8px solid ${i === 0 ? C.red : C.paper}`, paddingTop: 26 }}>
              <div style={{ fontSize: 100, fontWeight: 800, color: i === 0 ? "#ff8a73" : C.paper, letterSpacing: -3, lineHeight: 1.05 }}>{it.big}</div>
              <div style={{ fontSize: 30, lineHeight: 1.3, color: "#d8d4d4", marginTop: 12 }}>{it.l}</div>
            </Rise>
          ))}
        </div>
        <div style={{ position: "absolute", left: 110, bottom: 50, fontFamily: MONO, fontSize: 22, color: "#a8a3a3" }}>
          Pomiary zespołu na materiałach COI, 22.11.2026
        </div>
      </AbsoluteFill>
    </Scene>
  );
};

const Benefits: React.FC = () => {
  const cards = [
    { t: "Urzędnik", s: "Dostaje gotowy projekt formularza. Sprawdza go, zamiast przepisywać blankiet od zera." },
    { t: "COI", s: "Szybsza cyfryzacja tysięcy wzorów. Wynik trafia prosto do Generatora Formularzy." },
    { t: "Obywatel", s: "Wniosek online zamiast drukowania, wypełniania długopisem i skanowania." },
  ];
  return (
    <Scene>
      <AbsoluteFill style={{ padding: "90px 110px" }}>
        <Rise>
          <Kicker>Korzyści</Kicker>
        </Rise>
        <Rise delay={8} style={{ marginTop: 16 }}>
          <H size={80}>
            Kto na tym <Em>zyskuje</Em>
          </H>
        </Rise>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 36, marginTop: 100 }}>
          {cards.map((c, i) => (
            <Pop
              key={c.t}
              delay={40 + i * 22}
              style={{ background: C.white, border: `4px solid ${C.ink}`, borderTop: `14px solid ${i === 1 ? C.red : C.ink}`, padding: 44 }}
            >
              <div style={{ fontSize: 52, fontWeight: 800 }}>{c.t}</div>
              <div style={{ fontSize: 34, lineHeight: 1.35, color: C.muted, marginTop: 18 }}>{c.s}</div>
            </Pop>
          ))}
        </div>
      </AbsoluteFill>
    </Scene>
  );
};

const Trust: React.FC = () => (
  <Scene bg="white">
    <AbsoluteFill style={{ padding: "90px 110px" }}>
      <Rise>
        <Kicker>Zaufanie</Kicker>
      </Rise>
      <Rise delay={8} style={{ marginTop: 16 }}>
        <H size={76}>
          Bezpieczne i gotowe <Em>dla administracji</Em>
        </H>
      </Rise>
      <div style={{ display: "flex", flexDirection: "column", gap: 26, marginTop: 70, maxWidth: 1500 }}>
        <Bullet delay={35}>Przesłany wniosek nie jest nigdzie zapisywany</Bullet>
        <Bullet delay={55}>Otwarty model sztucznej inteligencji, który można uruchomić na serwerach państwa</Bullet>
        <Bullet delay={75}>Bez dostępu do sieci też działa, w uproszczonym trybie</Bullet>
        <Bullet delay={95}>Otwarte oprogramowanie, bez opłat licencyjnych</Bullet>
      </div>
    </AbsoluteFill>
  </Scene>
);

const Cta: React.FC = () => (
  <Scene bg="ink">
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", textAlign: "center" }}>
      <Logo w={760} delay={6} />
      <Pop delay={45} style={{ marginTop: 60 }}>
        <H size={96}>
          Jeden blankiet. <Em>Formularz gotowy do importu.</Em>
        </H>
      </Pop>
      <Rise delay={80} style={{ fontFamily: MONO, fontSize: 44, marginTop: 50, fontWeight: 600 }}>
        formularze.heckyeah.pl
      </Rise>
      <Rise delay={105} style={{ marginTop: 40, fontSize: 28, color: "#a8a3a3", letterSpacing: 2 }}>
        HACKNATION 2026 · ZADANIE COI „CYFRYZACJA FORMULARZY”
      </Rise>
    </AbsoluteFill>
  </Scene>
);

export const Pitch: React.FC = () => (
  <AbsoluteFill style={{ fontFamily: BODY, color: C.ink, background: C.paper }}>
    <Series>
      <Series.Sequence durationInFrames={SCENES.hook}>
        <Hook />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.formats}>
        <Formats />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.solution}>
        <Solution />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.drop}>
        <Drop />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.upload}>
        <Upload />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.queue}>
        <Queue />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.auditor}>
        <Auditor />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.report}>
        <Report />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.numbers}>
        <Numbers />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.benefits}>
        <Benefits />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.trust}>
        <Trust />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.cta}>
        <Cta />
      </Series.Sequence>
    </Series>
  </AbsoluteFill>
);
