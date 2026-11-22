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
  files: samples.forms.reduce((s, f) => s + f.files.length, 0), // same file
  matrixOk: 53, // research/08-macierz-formatow.md: 53 of 53 blanks, HTTP 200, 0 lint errors
  outputs: 6, // outputs/README.md: forms 3, 4, 6-9 in model mode, 0 lint errors
  coverageLow: 64, // research/10-pokrycie-referencji.md: model, strict label match
  coverageHigh: 82,
  apiTests: 588, // uv run pytest in api/, 22.11 08:40
  webTests: 209, // npm test in web/, 22.11 09:25
  lintRules: 31, // ARCHITECTURE.md 5.7: blocking rules L001-L031
};

const SCENES = {
  hook: 165,
  formats: 210,
  pipeline: 270,
  upload: 210,
  queue: 165,
  auditor: 285,
  report: 210,
  error: 165,
  numbers: 240,
  model: 225,
  security: 195,
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

const Hook: React.FC = () => {
  const f = useCurrentFrame();
  const letters = "BIUROKRATKA".split("");
  return (
    <Scene bg="ink">
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", textAlign: "center", gap: 60 }}>
        <div style={{ display: "flex", gap: 0 }}>
          {letters.map((l, i) => {
            const p = spring({ frame: f - 5 - i * 4, fps: 30, config: { damping: 12 } });
            const red = i >= 5;
            return (
              <div
                key={`${l}${i}`}
                style={{
                  width: 104,
                  height: 126,
                  border: `5px solid ${red ? C.red : C.paper}`,
                  marginLeft: i ? -5 : 0,
                  background: red ? C.red : "transparent",
                  color: C.paper,
                  fontSize: 80,
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transform: `scale(${p})`,
                  opacity: Math.min(1, p * 2),
                }}
              >
                {l}
              </div>
            );
          })}
        </div>
        <Rise delay={60}>
          <H size={84}>
            Blankiet urzędowy <Em>→</Em> e-formularz
          </H>
        </Rise>
        <Rise delay={95} style={{ fontSize: 40, color: "#d8d4d4", maxWidth: 1400 }}>
          Plik gotowy do importu w Generatorze Formularzy COI. Bez ręcznego przepisywania.
        </Rise>
      </AbsoluteFill>
    </Scene>
  );
};

const Formats: React.FC = () => {
  const f = useCurrentFrame();
  const formats = ["PDF", "DOC", "DOCX", "ODS", "XLSX", "JPG", "JPEG", "PNG"];
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
            Urzędy publikują wnioski w ośmiu formatach. <Em>Każdy trzeba przeprojektować ręcznie.</Em>
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
        JSON dla Generatora
      </Pop>
    </Scene>
  );
};

const Pipeline: React.FC = () => {
  const steps = [
    { t: "Plik", s: "pdfplumber · Apache Tika · RapidOCR", kind: "plain" },
    { t: "Dokument", s: "tekst z układem i numerami linii", kind: "plain" },
    { t: "IR", s: "krótka lista pól: model albo reguły", kind: "model" },
    { t: "Kompilator", s: "sekcje predefiniowane COI", kind: "code" },
    { t: "Linter", s: `${N.lintRules} reguł z auto-naprawą`, kind: "code" },
  ];
  return (
    <Scene>
      <AbsoluteFill style={{ padding: "90px 110px" }}>
        <Rise>
          <Kicker>Rozwiązanie</Kicker>
        </Rise>
        <Rise delay={8} style={{ marginTop: 16 }}>
          <H size={80}>
            Kompilator formularzy, <Em>nie OCR</Em>
          </H>
        </Rise>
        <div style={{ display: "flex", alignItems: "stretch", gap: 14, marginTop: 110 }}>
          {steps.map((s, i) => (
            <div key={s.t} style={{ display: "flex", alignItems: "center", gap: 14, flex: 1 }}>
              <Pop
                delay={30 + i * 18}
                style={{
                  flex: 1,
                  height: 250,
                  padding: 28,
                  boxSizing: "border-box",
                  background: s.kind === "code" ? C.ink : s.kind === "model" ? C.tint : C.white,
                  color: s.kind === "code" ? C.paper : C.ink,
                  border: s.kind === "model" ? `4px dashed ${C.redText}` : `4px solid ${C.ink}`,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <div style={{ fontSize: 44, fontWeight: 800 }}>{s.t}</div>
                <div style={{ fontSize: 26, lineHeight: 1.3, color: s.kind === "code" ? "#d8d4d4" : C.muted }}>{s.s}</div>
              </Pop>
              {i < steps.length - 1 && (
                <Rise delay={40 + i * 18} y={0} x={-20} style={{ fontSize: 48, fontWeight: 800, color: C.red }}>
                  →
                </Rise>
              )}
            </div>
          ))}
        </div>
        <Rise delay={140} style={{ marginTop: 70 }}>
          <H size={52}>
            Model pisze tylko IR. <Em>Końcowy JSON składa i sprawdza kod.</Em>
          </H>
        </Rise>
        <Rise delay={175} style={{ marginTop: 18, fontSize: 34, color: C.muted }}>
          Awaria modelu nie psuje wyniku: usługa przechodzi na reguły, bez błędu 500.
        </Rise>
      </AbsoluteFill>
    </Scene>
  );
};

const Upload: React.FC = () => (
  <Scene>
    <Split
      left={
        <>
          <Rise>
            <Kicker>Krok 1 · Wgraj blankiet</Kicker>
          </Rise>
          <Rise delay={8}>
            <H>
              Plik z dysku <Em>albo przykład COI</Em>
            </H>
          </Rise>
          <Bullet delay={35}>8 formatów, także zdjęcia i skany</Bullet>
          <Bullet delay={55}>
            {N.forms} formularzy z materiałów COI, {N.files} plików do kliknięcia
          </Bullet>
          <Bullet delay={75}>Plik tylko w pamięci, nie zapisujemy go na serwerze</Bullet>
        </>
      }
      right={<Browser src="02-przyklady.png" w={980} h={551} zoom={[1, 1.3]} origin="25% 75%" delay={15} />}
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
          <Bullet delay={40}>Tryb wsadowy po stronie przeglądarki</Bullet>
          <Bullet delay={60}>Limit zapytań? Kolejka czeka i ponawia</Bullet>
        </>
      }
      right={
        <>
          <Browser src="04-gotowe.png" w={980} h={551} zoom={[1.5, 1.6]} origin="35% 95%" delay={15} />
          <Tag delay={80} color={C.redText} style={{ right: 10, top: 230 }}>
            Gotowe: model językowy, 69 pól
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
          <Bullet delay={45}>Tekst blankietu obok podglądu e-formularza</Bullet>
          <Bullet delay={70}>Wybór pola podświetla linie, z których powstało</Bullet>
          <Bullet delay={95}>Pewność rozpoznania; poniżej 70% prośba o sprawdzenie</Bullet>
        </>
      }
      right={
        <>
          <Browser src="06-podglad.png" w={1060} h={596} zoom={[1, 1.2]} origin="0% 35%" delay={15} />
          <Tag delay={120} color={C.red} style={{ left: 150, top: 600 }}>
            Źródło pola: linia L15
          </Tag>
          <Tag delay={150} style={{ right: 20, top: 820 }}>
            Podgląd z warunkami na żywo
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
            <Kicker>Krok 4 · Raport i JSON</Kicker>
          </Rise>
          <Rise delay={8}>
            <H>
              0 błędów lintera. <Em>JSON jednym kliknięciem.</Em>
            </H>
          </Rise>
          <Bullet delay={40}>Tryb, model, uwagi jakościowe, czasy etapów</Bullet>
          <Bullet delay={60}>Propozycje nowych słowników</Bullet>
          <Bullet delay={80}>Pobranie pliku gotowego do importu</Bullet>
        </>
      }
      right={
        <>
          <Browser src="08-raport.png" w={980} h={551} zoom={[1, 1.2]} origin="0% 0%" delay={15} />
          <Browser
            src="07-json.png"
            w={560}
            h={315}
            delay={95}
            zoom={[1.3, 1.3]}
            origin="0% 20%"
            style={{ position: "absolute", right: -20, bottom: 70 }}
          />
        </>
      }
    />
  </Scene>
);

const ErrorCase: React.FC = () => (
  <Scene>
    <Split
      left={
        <>
          <Rise>
            <Kicker>Zły plik?</Kicker>
          </Rise>
          <Rise delay={8}>
            <H>
              Jasny komunikat. <Em>Nigdy błąd 500.</Em>
            </H>
          </Rise>
          <Bullet delay={40}>Przeglądarka odrzuca zły typ od razu</Bullet>
          <Bullet delay={60}>API sprawdza sygnaturę treści: 415 jako problem+json</Bullet>
        </>
      }
      right={<Browser src="09-blad.png" w={980} h={551} zoom={[1, 1.35]} origin="50% 85%" delay={15} />}
    />
  </Scene>
);

const Numbers: React.FC = () => {
  const items = [
    { n: N.matrixOk, sfx: ` / ${N.matrixOk}`, l: "blankietów we wszystkich formatach: HTTP 200, 0 błędów lintera" },
    { n: N.outputs, sfx: ` / ${N.outputs}`, l: "wynikowych JSON-ów w trybie modelu, 0 błędów" },
    { n: N.coverageHigh, sfx: "%", pre: `${N.coverageLow}–`, l: "pól z referencji COI odtworzonych przez model" },
    { n: N.apiTests + N.webTests, sfx: "", l: `testów: ${N.apiTests} API i ${N.webTests} frontendu` },
  ];
  return (
    <Scene bg="ink">
      <AbsoluteFill style={{ padding: "90px 110px" }}>
        <Rise>
          <Kicker>Działa na materiałach COI</Kicker>
        </Rise>
        <Rise delay={8} style={{ marginTop: 16 }}>
          <H size={76}>Liczby zamiast deklaracji</H>
        </Rise>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 36, marginTop: 130 }}>
          {items.map((it, i) => {
            const d = 25 + i * 18;
            return (
              <Rise key={it.l} delay={d} style={{ borderTop: `8px solid ${i === 0 ? C.red : C.paper}`, paddingTop: 26 }}>
                <div style={{ fontSize: 104, fontWeight: 800, color: i === 0 ? "#ff8a73" : C.paper, letterSpacing: -3, lineHeight: 1.05, fontVariantNumeric: "tabular-nums" }}>
                  {it.pre ?? ""}
                  <Count to={it.n} delay={d} suffix={it.sfx} />
                </div>
                <div style={{ fontSize: 30, lineHeight: 1.3, color: "#d8d4d4", marginTop: 12 }}>{it.l}</div>
              </Rise>
            );
          })}
        </div>
        <div style={{ position: "absolute", left: 110, bottom: 50, fontFamily: MONO, fontSize: 22, color: "#a8a3a3" }}>
          Źródła: research/08, outputs/README.md, research/10, pytest i Vitest · stan 22.11.2026
        </div>
      </AbsoluteFill>
    </Scene>
  );
};

const Model: React.FC = () => {
  const cards = [
    { t: "Tryb reguł", c: "LLM_ENABLED=false", s: "Bez sieci. Zapas, gdy model nie odpowiada." },
    { t: "EdenAI, endpoint UE", c: "Qwen3.5-9B", s: "Open-weight, Apache-2.0. Ok. 0,001 USD za formularz." },
    { t: "Lokalny llama-server", c: "LLM_BASE_URL=…/v1", s: "Ten sam model na infrastrukturze COI." },
  ];
  return (
    <Scene>
      <AbsoluteFill style={{ padding: "90px 110px" }}>
        <Rise>
          <Kicker>Model wymienny</Kicker>
        </Rise>
        <Rise delay={8} style={{ marginTop: 16 }}>
          <H size={76}>
            Jedna zmienna zmienia model. <Em>Kod zostaje ten sam.</Em>
          </H>
        </Rise>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 36, marginTop: 100 }}>
          {cards.map((c, i) => (
            <Pop
              key={c.t}
              delay={40 + i * 22}
              style={{ background: C.white, border: `4px solid ${C.ink}`, borderTop: `14px solid ${i === 1 ? C.red : C.ink}`, padding: 44 }}
            >
              <div style={{ fontSize: 44, fontWeight: 800 }}>{c.t}</div>
              <div style={{ fontFamily: MONO, fontSize: 28, color: C.redText, marginTop: 14 }}>{c.c}</div>
              <div style={{ fontSize: 32, lineHeight: 1.35, color: C.muted, marginTop: 18 }}>{c.s}</div>
            </Pop>
          ))}
        </div>
        <Rise delay={140} style={{ marginTop: 60, fontSize: 34, color: C.muted }}>
          Klient zna tylko wspólną część API zgodnego z OpenAI: nic specyficznego dla dostawcy.
        </Rise>
      </AbsoluteFill>
    </Scene>
  );
};

const Security: React.FC = () => (
  <Scene bg="white">
    <AbsoluteFill style={{ padding: "90px 110px" }}>
      <Rise>
        <Kicker>Bezpieczeństwo i licencje</Kicker>
      </Rise>
      <Rise delay={8} style={{ marginTop: 16 }}>
        <H size={76}>
          Gotowe do wdrożenia <Em>w administracji</Em>
        </H>
      </Rise>
      <div style={{ display: "flex", flexDirection: "column", gap: 26, marginTop: 70, maxWidth: 1500 }}>
        <Bullet delay={35}>Plik tylko w pamięci; w logach wyłącznie skrót SHA-256 i rozmiar</Bullet>
        <Bullet delay={55}>Trzy kontenery bez uprawnień, system plików tylko do odczytu, Tika bez internetu</Bullet>
        <Bullet delay={75}>Automatyczna bramka licencji: tylko open source bez copyleftu</Bullet>
        <Bullet delay={95}>Uruchomienie jednym poleceniem: docker compose up</Bullet>
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
      <Series.Sequence durationInFrames={SCENES.pipeline}>
        <Pipeline />
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
      <Series.Sequence durationInFrames={SCENES.error}>
        <ErrorCase />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.numbers}>
        <Numbers />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.model}>
        <Model />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.security}>
        <Security />
      </Series.Sequence>
      <Series.Sequence durationInFrames={SCENES.cta}>
        <Cta />
      </Series.Sequence>
    </Series>
  </AbsoluteFill>
);
