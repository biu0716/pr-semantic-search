import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Copy, Check, Download, ArrowUpRight, ChevronRight,
  RotateCcw, FileText, Search, Zap, Pencil, Minimize2,
} from "lucide-react";

type Mode  = "generate" | "review" | "search";
type Phase = "idle" | "workflow" | "streaming" | "done";
type DeliverySection = { title: string; body: string };
type GenerateResponse = { result: string; stage1?: string | null; stage2?: string | null };
type SearchResult = { title?: string; file_name?: string; type?: string; excerpt?: string; text?: string; score?: number; rel?: number; date?: string };

/* ── typography ── */
const SANS:  React.CSSProperties = { fontFamily: "'DM Sans', sans-serif" };
const DISP:  React.CSSProperties = { fontFamily: "'Barlow Condensed', sans-serif" };
const MONO:  React.CSSProperties = { fontFamily: "'JetBrains Mono', monospace" };
const SERIF: React.CSSProperties = { fontFamily: "'Lora', Georgia, serif" };

/* ── palette ── */
const INK    = "#1C1917";
const RED    = "#C41F2E";
const AMBER  = "#B45309";
const MUTED  = "#78716C";
const BORDER = "#E0D8CE";
const PAPER  = "#FFFFFF";

const S_BG     = "#18120A";
const S_TEXT   = "#F0E6CC";
const S_DIM    = "#6B5E4E";
const S_BORDER = "rgba(240,230,204,0.07)";

/* ── data ── */
const WORKFLOW_STEPS = [
  "读取传播 brief",
  "搭建传播框架",
  "校验品牌口径",
  "整理交付文档",
];

const DELIVERY_HEADERS = ["传播主题", "传播方向（3条）", "导语", "新闻稿段落", "社媒文案（3条）", "媒体标题（5条）", "正文"];

async function apiJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = await res.text();
    try { msg = JSON.parse(msg).detail || msg; } catch {}
    throw new Error(msg || `HTTP ${res.status}`);
  }
  return res.json();
}

function briefPrefix(contentType: string, brand: string, tone: string, goal: string) {
  return [
    `内容类型：${contentType}`,
    `品牌：${brand}`,
    `语气：${tone}`,
    `目标：${goal}`,
  ].join("\n");
}

function splitTwoStage(text: string) {
  if (!text.includes("【第二步｜具体交付内容】")) return { stage1: "", stage2: text };
  const parts = text.split("【第二步｜具体交付内容】");
  return {
    stage1: parts[0].replace("【第一步｜传播策略骨架】", "").trim(),
    stage2: (parts[1] || "").trim(),
  };
}

function parseDeliverySections(text: string): DeliverySection[] {
  const sections: DeliverySection[] = [];
  let current: DeliverySection | null = null;
  const push = () => {
    if (current && current.body.trim()) sections.push({ title: current.title, body: current.body.trim() });
  };
  text.split(/\n/).forEach(raw => {
    const line = raw.trim();
    if (!line) {
      if (current) current.body += "\n";
      return;
    }
    const bracket = line.match(/^【(.+?)】$/);
    const colon = line.match(/^(.+?)：\s*(.*)$/);
    const title = bracket ? bracket[1] : (colon && DELIVERY_HEADERS.includes(colon[1]) ? colon[1] : "");
    if (title) {
      push();
      current = { title, body: colon?.[2] || "" };
      return;
    }
    if (!current) current = { title: "交付内容", body: "" };
    current.body += `${current.body ? "\n" : ""}${line}`;
  });
  push();
  return sections.length ? sections : [{ title: "交付内容", body: text.trim() }];
}

function renderParagraphs(text: string) {
  return text.split(/\n+/).map(x => x.trim()).filter(Boolean);
}

function useCopy() {
  const [k, setK] = useState<string | null>(null);
  const copy = useCallback((text: string, key: string) => {
    navigator.clipboard.writeText(text); setK(key); setTimeout(() => setK(null), 2000);
  }, []);
  return { copied: k, copy };
}

/* ── small atoms ── */

function Cursor({ color = RED }: { color?: string }) {
  return (
    <motion.span className="inline-block w-px h-[1em] ml-0.5 align-[-2px]"
      style={{ backgroundColor: color }}
      animate={{ opacity: [1, 0] }} transition={{ duration: 0.5, repeat: Infinity }} />
  );
}

function CopyBtn({ text, id, copied, copy }: {
  text: string; id: string; copied: string | null; copy: (t: string, k: string) => void;
}) {
  const done = copied === id;
  return (
    <motion.button onClick={e => { e.stopPropagation(); copy(text, id); }}
      whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.94 }}
      className="flex items-center gap-1 transition-colors px-2 py-1 border"
      style={{ borderColor: BORDER, color: done ? "#059669" : MUTED }}>
      <AnimatePresence mode="wait">
        {done
          ? <motion.span key="y" initial={{ scale: 0 }} animate={{ scale: 1 }}><Check size={10} /></motion.span>
          : <motion.span key="n" initial={{ scale: 0 }} animate={{ scale: 1 }}><Copy size={10} /></motion.span>}
      </AnimatePresence>
      <span style={{ ...MONO, fontSize: 8 }}>{done ? "已复制" : "复制"}</span>
    </motion.button>
  );
}

function ToolBtn({ icon: Icon, label, onClick }: { icon: any; label: string; onClick?: () => void }) {
  return (
    <motion.button onClick={onClick} whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.94 }}
      className="flex items-center gap-1 px-2 py-1 border transition-colors hover:border-foreground/20"
      style={{ borderColor: BORDER, color: MUTED }}>
      <Icon size={9} />
      <span style={{ ...MONO, fontSize: 8 }}>{label}</span>
    </motion.button>
  );
}

function SectionMark({ children, color }: { children: React.ReactNode; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="w-px h-3 shrink-0" style={{ backgroundColor: color || MUTED }} />
      <span className="uppercase tracking-[0.18em] text-[8px]" style={{ ...MONO, color: color || MUTED }}>
        {children}
      </span>
    </div>
  );
}

function Stamp({ label, color }: { label: string; color?: string }) {
  const c = color || RED;
  return (
    <span className="inline-flex items-center px-1.5 py-px font-bold uppercase tracking-widest text-[8px] border"
      style={{ ...MONO, borderColor: `${c}60`, color: c }}>
      {label}
    </span>
  );
}

/* ── DocSection: each briefing block ── */
function DocSection({ letter, title, color = MUTED, children, toolbar }: {
  letter: string; title: string; color?: string;
  children: React.ReactNode; toolbar?: React.ReactNode;
}) {
  return (
    <div className="border-b group/section last:border-0" style={{ borderColor: BORDER }}>
      <div className="px-8 py-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="w-[18px] h-[18px] flex items-center justify-center border text-[8px] font-bold shrink-0"
              style={{ ...MONO, borderColor: `${color}60`, color }}>
              {letter}
            </span>
            <SectionMark color={color}>{title}</SectionMark>
          </div>
          <div className="flex items-center gap-1.5 opacity-0 group-hover/section:opacity-100 transition-opacity">
            {toolbar}
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}

/* ── WorkflowPanel ── */
function WorkflowPanel({ onDone }: { onDone: () => void }) {
  const [stepsDone, setStepsDone] = useState<boolean[]>([false, false, false, false]);
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    const delays = [700, 620, 680, 560];
    let cur = 0;
    const advance = () => {
      setStepsDone(p => { const n = [...p]; n[cur] = true; return n; });
      cur++;
      setActiveStep(cur);
      if (cur < WORKFLOW_STEPS.length) setTimeout(advance, delays[cur]);
      else setTimeout(onDone, 320);
    };
    setTimeout(advance, delays[0]);
  }, [onDone]);

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.3 }}
      className="border border-border bg-white shadow-sm p-6 mb-4" style={{ borderColor: BORDER }}>
      <div className="flex items-center gap-2 mb-5">
        <motion.div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: RED }}
          animate={{ scale: [1, 1.5, 1], opacity: [1, 0.4, 1] }}
          transition={{ duration: 0.9, repeat: Infinity }} />
        <span className="text-[9px] tracking-[0.2em] uppercase" style={{ ...MONO, color: RED }}>正在处理</span>
      </div>

      {/* Vertical track */}
      <div className="relative pl-6">
        <div className="absolute left-[7px] top-2 bottom-2 w-px" style={{ backgroundColor: BORDER }}>
          <motion.div className="w-full bg-red-600 origin-top"
            style={{ backgroundColor: RED }}
            animate={{ scaleY: activeStep / WORKFLOW_STEPS.length }}
            transition={{ duration: 0.3, ease: "easeOut" }} />
        </div>

        <div className="space-y-4">
          {WORKFLOW_STEPS.map((step, i) => {
            const done   = stepsDone[i];
            const active = activeStep === i;
            return (
              <motion.div key={i} className="flex items-center gap-3"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                transition={{ delay: i * 0.06 }}>
                {/* node */}
                <div className="absolute left-[3.5px] w-[7px] h-[7px] rounded-full border flex items-center justify-center"
                  style={{ borderColor: done ? RED : active ? RED : BORDER, backgroundColor: done ? RED : "white" }}>
                  {done && <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 700 }}>
                    <Check size={4} color="white" strokeWidth={3} />
                  </motion.span>}
                </div>
                <span className="text-sm transition-colors" style={{ ...SERIF, color: done ? INK : active ? RED : MUTED }}>
                  {step}
                </span>
                {active && <motion.span style={{ ...MONO, color: RED, fontSize: 12 }} animate={{ opacity: [1, 0] }} transition={{ duration: 0.5, repeat: Infinity }}>_</motion.span>}
              </motion.div>
            );
          })}
        </div>
      </div>

      <div className="mt-5 h-px overflow-hidden" style={{ backgroundColor: BORDER }}>
        <motion.div className="h-full" style={{ backgroundColor: RED }}
          animate={{ scaleX: activeStep / WORKFLOW_STEPS.length, originX: 0 }}
          transition={{ duration: 0.3, ease: "easeOut" }} />
      </div>
    </motion.div>
  );
}

/* ── sidebar ── */
function Sidebar({ mode, switchMode }: { mode: Mode; switchMode: (m: Mode) => void }) {
  const MODES = [
    { id: "generate" as Mode, num: "01", lines: ["传播内容", "生成"],  icon: Zap      },
    { id: "review"   as Mode, num: "02", lines: ["稿件审校", "改写"],  icon: FileText },
    { id: "search"   as Mode, num: "03", lines: ["知识库",   "检索"],  icon: Search   },
  ];

  return (
    <aside className="hidden md:flex flex-col shrink-0 h-full"
      style={{ width: 196, backgroundColor: S_BG, borderRight: `1px solid ${S_BORDER}` }}>

      {/* Logo */}
      <div className="px-5 py-5 flex items-center gap-3" style={{ borderBottom: `1px solid ${S_BORDER}` }}>
        <div className="w-7 h-7 flex items-center justify-center shrink-0 text-white font-black text-[10px]"
          style={{ ...DISP, backgroundColor: RED,
            clipPath: "polygon(0 0,100% 0,100% 75%,75% 100%,0 100%)" }}>
          PR
        </div>
        <div>
          <div className="font-bold leading-none tracking-[0.18em] text-[12px] uppercase" style={{ ...DISP, color: S_TEXT }}>PR Agent</div>
          <div className="text-[8px] mt-0.5 tracking-widest" style={{ ...MONO, color: S_DIM }}>内容工作台</div>
        </div>
      </div>

      {/* Project */}
      <div className="px-5 py-4" style={{ borderBottom: `1px solid ${S_BORDER}` }}>
        <div className="text-[7px] tracking-[0.22em] uppercase mb-2" style={{ ...MONO, color: S_DIM }}>当前项目</div>
        <div className="font-semibold text-[14px] leading-tight mb-0.5" style={{ ...DISP, color: S_TEXT }}>汽车传播</div>
        <div className="text-[12px] leading-tight" style={{ ...DISP, color: `${S_TEXT}80` }}>Brief 到可用稿件</div>
        <div className="flex items-center gap-2 mt-2">
          <div className="w-1 h-1 rounded-full" style={{ backgroundColor: "#22C55E" }} />
          <span className="text-[8px]" style={{ ...MONO, color: S_DIM }}>工作台在线</span>
        </div>
      </div>

      {/* Mode nav */}
      <nav className="px-3 py-3 flex-1">
        <div className="text-[7px] tracking-[0.22em] uppercase px-2 mb-2" style={{ ...MONO, color: S_DIM }}>工作模块</div>
        <div className="relative space-y-0.5">
          {/* track */}
          <div className="absolute left-[20px] top-3 bottom-3 w-px" style={{ backgroundColor: S_BORDER }} />
          {MODES.map(m => {
            const active = mode === m.id;
            return (
              <button key={m.id} onClick={() => switchMode(m.id)}
                className="w-full text-left pl-9 pr-3 py-3 relative transition-colors"
                style={{ backgroundColor: active ? "rgba(240,230,204,0.06)" : undefined }}>
                {active && (
                  <motion.div layoutId="nav-bar" className="absolute left-0 top-0 bottom-0 w-0.5"
                    style={{ backgroundColor: RED }}
                    transition={{ type: "spring", stiffness: 500, damping: 40 }} />
                )}
                {/* node */}
                <div className="absolute left-[17px] top-1/2 -translate-y-1/2 w-[7px] h-[7px] rounded-full border transition-all"
                  style={{ borderColor: active ? RED : `${S_BORDER}`, backgroundColor: active ? RED : S_BG }} />
                <div className="text-[8px] mb-0.5" style={{ ...MONO, color: active ? RED : `${S_DIM}80` }}>{m.num}</div>
                {m.lines.map((line, li) => (
                  <div key={li} className="font-bold leading-tight transition-colors text-[15px]"
                    style={{ ...DISP, color: active ? S_TEXT : S_DIM }}>
                    {line}
                  </div>
                ))}
              </button>
            );
          })}
        </div>
      </nav>

      {/* Recent */}
      <div className="px-5 py-4" style={{ borderTop: `1px solid ${S_BORDER}` }}>
        <div className="text-[7px] tracking-[0.22em] uppercase mb-3" style={{ ...MONO, color: S_DIM }}>近期任务</div>
        {[
          { m: "generate" as Mode, t: "上市发布传播稿", d: "2h" },
          { m: "review"   as Mode, t: "媒体沟通稿审校", d: "昨天" },
          { m: "search"   as Mode, t: "技术口径检索",   d: "昨天" },
        ].map((item, i) => (
          <button key={i} onClick={() => switchMode(item.m)}
            className="w-full flex items-center justify-between py-1.5 group">
            <div className="flex items-center gap-2 min-w-0">
              <span style={{ color: S_DIM }}>·</span>
              <span className="text-[11px] truncate transition-colors group-hover:text-amber-100"
                style={{ color: S_DIM }}>{item.t}</span>
            </div>
            <span className="text-[8px] shrink-0 ml-2" style={{ ...MONO, color: `${S_DIM}60` }}>{item.d}</span>
          </button>
        ))}
      </div>

      {/* Status */}
      <div className="px-5 py-3 flex items-center justify-between" style={{ borderTop: `1px solid ${S_BORDER}` }}>
        <span className="text-[8px]" style={{ ...MONO, color: S_DIM }}>知识库 · 本地</span>
        <div className="flex items-center gap-1.5">
          <motion.span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "#22C55E" }}
            animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 2.4, repeat: Infinity }} />
          <span className="text-[8px]" style={{ ...MONO, color: S_DIM }}>已同步</span>
        </div>
      </div>
    </aside>
  );
}

/* ── generate mode ── */
function GenerateMode() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [brief, setBrief] = useState("");
  const [contentType, setContentType] = useState("新闻稿");
  const [brand, setBrand] = useState("Mercedes-Benz");
  const [tone, setTone] = useState("正式");
  const [goal, setGoal] = useState("生成");
  const [sections, setSections] = useState<DeliverySection[]>([]);
  const [stage1, setStage1] = useState("");
  const [error, setError] = useState("");
  const { copied, copy } = useCopy();

  const showDoc = phase === "done" && sections.length > 0;
  const fullText = sections.map(s => `${s.title}\n${s.body}`).join("\n\n");

  async function runGenerate() {
    if (!brief.trim()) return;
    setError("");
    setSections([]);
    setStage1("");
    setPhase("workflow");
    try {
      const query = `${briefPrefix(contentType, brand, tone, goal)}\n\n传播需求：\n${brief.trim()}`;
      const data = await apiJSON<GenerateResponse>("/api/generate", {
        query,
        top_k: 5,
        extra_terms: null,
        uploaded_text: "",
        source_name: "",
      });
      const split = splitTwoStage(data.result || "");
      const stage2 = data.stage2 || split.stage2 || data.result || "";
      setStage1(data.stage1 || split.stage1 || "");
      setSections(parseDeliverySections(stage2));
      setPhase("done");
    } catch (err) {
      setError(String((err as Error).message || err));
      setPhase("idle");
    }
  }

  return (
    <div className="h-full overflow-y-auto overflow-x-hidden" style={{ scrollbarWidth: "none" }}>
      <div className="w-full mx-auto px-4 sm:px-8 lg:px-10 py-8 lg:py-10" style={{ maxWidth: "min(960px, calc(100vw - 32px))" }}>

        {/* Section header */}
        <div className="flex items-baseline gap-4 mb-7">
          <span className="font-black leading-none select-none" style={{ ...DISP, fontSize: 56, color: BORDER, lineHeight: 1 }}>01</span>
          <div>
            <SectionMark color={RED}>传播内容生成</SectionMark>
            <p className="text-xs mt-1" style={{ color: MUTED }}>输入传播需求，生成主题、方向、标题、新闻稿与社媒文案</p>
          </div>
          {phase !== "idle" && (
            <motion.button initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              onClick={() => { setPhase("idle"); setBrief(""); setSections([]); setStage1(""); setError(""); }}
              className="ml-auto flex items-center gap-1.5 text-xs transition-colors hover:opacity-70"
              style={{ color: MUTED }}>
              <RotateCcw size={11} /><span style={MONO}>重新开始</span>
            </motion.button>
          )}
        </div>

        {/* Brief input */}
        <AnimatePresence>
          {phase === "idle" && (
            <motion.div exit={{ opacity: 0, height: 0, marginBottom: 0 }}
              transition={{ duration: 0.35, ease: [0.22,1,0.36,1] }} className="mb-5">
              <div className="w-full max-w-full overflow-hidden bg-white border shadow-sm" style={{ borderColor: BORDER }}>
                <div className="flex items-center justify-between gap-3 px-5 sm:px-7 py-4 border-b" style={{ borderColor: BORDER }}>
                  <SectionMark>BRIEF</SectionMark>
                  <div className="flex items-center gap-3">
                    <span className="hidden sm:inline text-[9px]" style={{ ...MONO, color: brief.length > 20 ? RED : MUTED }}>{brief.length} CHARS</span>
                    <span className="hidden sm:inline-flex">
                      <Stamp label="需求录入" color={RED} />
                    </span>
                  </div>
                </div>
                <div className="grid border-b" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", borderColor: BORDER }}>
                  {[
                    ["内容类型", contentType, setContentType, ["新闻稿", "社媒文案", "邀请函", "标题", "传播方向", "完整初稿"]],
                    ["品牌", brand, setBrand, ["Mercedes-Benz", "BMW", "MINI", "其他 / 待确认"]],
                    ["语气", tone, setTone, ["正式", "社媒化", "顾问感", "更像人话"]],
                    ["目标", goal, setGoal, ["生成", "改写", "统一口径"]],
                  ].map(([label, value, setter, options]) => (
                    <div key={label as string} className="px-4 sm:px-5 py-4 border-r last:border-r-0" style={{ borderColor: BORDER }}>
                      <span className="block text-[8px] uppercase tracking-widest mb-2" style={{ ...MONO, color: MUTED }}>{label as string}</span>
                      <select
                        value={value as string}
                        onChange={e => (setter as (v: string) => void)(e.target.value)}
                        className="w-full text-xs bg-transparent focus:outline-none cursor-pointer"
                        style={{ ...SANS, color: INK }}>
                        {(options as string[]).map(opt => <option key={opt}>{opt}</option>)}
                      </select>
                      </div>
                  ))}
                </div>
                <div className="flex justify-between gap-4 px-5 sm:px-7 pt-5 text-[8px] tracking-[0.18em] uppercase" style={{ ...MONO, color: MUTED }}>
                  <span>这些分类会写入 brief，不会被隐藏成默认 prompt</span>
                  <span className="hidden sm:inline">Content / Brand / Tone / Goal</span>
                </div>
                <textarea value={brief} onChange={e => setBrief(e.target.value)}
                  placeholder={"描述传播需求……\n\n例如：为梅赛德斯-奔驰全新纯电 GLC 生成上市新闻稿，重点突出产品序列进入纯电时代、豪华品牌电动化与媒体沟通切口。"}
                  className="w-full h-48 bg-transparent resize-none focus:outline-none text-[15px] leading-relaxed px-5 sm:px-7 py-5 placeholder:text-muted-foreground/30"
                  style={{ ...SERIF, color: INK }} />
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-5 sm:px-7 py-4 border-t" style={{ borderColor: BORDER }}>
                  <button className="text-xs transition-colors hover:opacity-70" style={{ color: MUTED }}
                    onClick={() => setBrief("为梅赛德斯-奔驰全新纯电 GLC 生成上市新闻稿，重点突出产品序列进入纯电时代、豪华品牌电动化与媒体沟通切口。")}>
                    填入示例 →
                  </button>
                  <motion.button onClick={runGenerate} disabled={!brief.trim()}
                    whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                    className="flex w-full sm:w-auto items-center justify-center gap-2 px-6 py-2 text-sm font-medium text-white disabled:opacity-40"
                    style={{ ...SANS, backgroundColor: RED,
                      clipPath: "polygon(0 0,calc(100% - 8px) 0,100% 8px,100% 100%,8px 100%,0 calc(100% - 8px))" }}>
                    <Zap size={13} />生成传播内容
                  </motion.button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        {error && (
          <div className="border px-5 py-4 mb-5 text-sm" style={{ borderColor: `${RED}40`, color: RED, backgroundColor: `${RED}06` }}>
            {error}
          </div>
        )}

        {/* Workflow steps */}
        <AnimatePresence>
          {phase === "workflow" && (
            <WorkflowPanel onDone={() => {}} />
          )}
        </AnimatePresence>

        {/* Output document */}
        <AnimatePresence>
          {showDoc && (
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: [0.22,1,0.36,1] }}
              className="bg-white border shadow-sm overflow-hidden" style={{ borderColor: BORDER }}>

              {/* Document header */}
              <div className="px-8 pt-5 pb-4 border-b" style={{ borderColor: BORDER }}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <SectionMark color={RED}>COMMUNICATION BRIEFING</SectionMark>
                    </div>
                    <p className="text-[9px]" style={{ ...MONO, color: MUTED }}>
                      {brand} · {contentType} · {tone} · {new Date().toLocaleDateString("zh-CN")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Stamp label="DRAFT" color={RED} />
                    <CopyBtn text={fullText} id="all" copied={copied} copy={copy} />
                  </div>
                </div>
                {/* delivery note */}
                <div className="flex items-center gap-3 mt-3 pt-3 border-t flex-wrap" style={{ borderColor: BORDER }}>
                  <span className="text-[8px]" style={{ ...MONO, color: MUTED }}>本次交付包含</span>
                  {sections.map(s => s.title).map(tag => (
                    <span key={tag} className="text-[8px] px-1.5 py-px border" style={{ ...MONO, borderColor: BORDER, color: MUTED }}>{tag}</span>
                  ))}
                </div>
              </div>

              {sections.map((section, i) => (
                <DocSection
                  key={`${section.title}-${i}`}
                  letter={"ABCDEFGHIJKLMNOPQRSTUVWXYZ"[i] || String(i + 1)}
                  title={section.title}
                  color={i % 2 === 0 ? RED : AMBER}
                  toolbar={<>
                    <CopyBtn text={`${section.title}\n${section.body}`} id={`section-${i}`} copied={copied} copy={copy} />
                    <ToolBtn icon={Pencil} label="调整" />
                  </>}>
                  <div className={/传播主题/.test(section.title) ? "py-2" : "space-y-3"}>
                    {renderParagraphs(section.body).map((p, pi) => {
                      const numbered = p.match(/^(\d+)[.、]\s*(.+)$/);
                      if (numbered) {
                        return (
                          <div key={pi} className="flex items-start gap-4 py-2.5 border-b last:border-0" style={{ borderColor: BORDER }}>
                            <span className="w-5 h-5 flex items-center justify-center border shrink-0 text-[9px] font-bold mt-px"
                              style={{ ...MONO, borderColor: `${AMBER}50`, color: AMBER }}>{numbered[1]}</span>
                            <p className="text-sm leading-relaxed flex-1" style={{ ...SERIF, color: INK }}>{numbered[2]}</p>
                          </div>
                        );
                      }
                      return (
                        <p key={pi} className={/传播主题/.test(section.title) ? "leading-snug" : "text-sm leading-relaxed"}
                          style={/传播主题/.test(section.title) ? { ...DISP, fontSize: 32, color: INK } : { ...SERIF, color: INK }}>
                          {/传播主题/.test(section.title) ? `「${p}」` : p}
                        </p>
                      );
                    })}
                  </div>
                </DocSection>
              ))}
              {stage1 && (
                <div className="px-8 py-5 border-t" style={{ borderColor: BORDER, backgroundColor: "#FDFAF6" }}>
                  <details>
                    <summary className="cursor-pointer">
                      <SectionMark color={MUTED}>STRATEGY NOTES</SectionMark>
                    </summary>
                    <div className="mt-4 space-y-3">
                      {renderParagraphs(stage1).map((p, i) => (
                        <p key={i} className="text-xs leading-relaxed" style={{ ...SERIF, color: MUTED }}>{p}</p>
                      ))}
                    </div>
                  </details>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

/* ── review mode ── */
function ReviewMode() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [text, setText] = useState("");
  const [mode, setMode] = useState("check");
  const [instruction, setInstruction] = useState("");
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const { copied, copy } = useCopy();

  async function runReview(nextMode = mode) {
    if (!text.trim()) return;
    setError("");
    setPhase("workflow");
    try {
      const data = await apiJSON<{ result: string }>("/api/refine-doc", {
        mode: nextMode,
        source_text: text.trim(),
        instruction,
        extra_terms: null,
      });
      setResult(data.result || "");
      setPhase("done");
    } catch (err) {
      setError(String((err as Error).message || err));
      setPhase("idle");
    }
  }

  return (
    <div className="h-full overflow-y-auto" style={{ scrollbarWidth: "none" }}>
      <div className="max-w-[760px] mx-auto px-12 py-10">
        <div className="flex items-baseline gap-4 mb-7">
          <span className="font-black leading-none select-none" style={{ ...DISP, fontSize: 56, color: BORDER, lineHeight: 1 }}>02</span>
          <div>
            <SectionMark color={AMBER}>稿件审校改写</SectionMark>
            <p className="text-xs mt-1" style={{ color: MUTED }}>检查品牌口径、术语规范、事实表述与传播风险</p>
          </div>
          {phase === "done" && (
            <motion.button initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              onClick={() => { setPhase("idle"); setResult(""); }}
              className="ml-auto flex items-center gap-1.5 text-xs" style={{ color: MUTED }}>
              <RotateCcw size={11} /><span style={MONO}>重新审校</span>
            </motion.button>
          )}
        </div>

        <AnimatePresence mode="wait">
          {phase === "idle" && (
            <motion.div key="idle" exit={{ opacity: 0 }}>
              <div className="bg-white border shadow-sm overflow-hidden" style={{ borderColor: BORDER }}>
                <div className="flex items-center justify-between px-6 py-3 border-b" style={{ borderColor: BORDER }}>
                  <SectionMark>MANUSCRIPT</SectionMark>
                  <div className="flex items-center gap-2">
                    <Stamp label="待审校" color={AMBER} />
                    <span className="text-[9px]" style={{ ...MONO, color: MUTED }}>{text.length} CHARS</span>
                  </div>
                </div>
                <textarea value={text} onChange={e => setText(e.target.value)}
                  placeholder="粘贴需要审校或改写的稿件……"
                  className="w-full h-36 bg-transparent resize-none focus:outline-none text-sm leading-loose px-6 py-5 placeholder:text-muted-foreground/30"
                  style={{ ...SERIF, color: INK }} />
                <div className="px-6 pb-4">
                  <input value={instruction} onChange={e => setInstruction(e.target.value)}
                    placeholder="补充要求，例如：更正式、删除夸张表述、按豪华品牌语气改写"
                    className="w-full bg-transparent border-b py-2 text-xs focus:outline-none"
                    style={{ ...SANS, borderColor: BORDER, color: INK }} />
                </div>
                <div className="flex items-center gap-3 px-6 py-4 border-t" style={{ borderColor: BORDER }}>
                  {[
                    ["check", "风险检查"],
                    ["normalize", "统一口径"],
                    ["rewrite", "PR 风格改写"],
                  ].map(([value, label]) => (
                    <button key={value} onClick={() => setMode(value)}
                      className="text-[8px] px-2 py-1 border transition-all"
                      style={{ ...MONO, borderColor: mode === value ? `${AMBER}60` : BORDER, color: mode === value ? AMBER : MUTED }}>
                      {label}
                    </button>
                  ))}
                  <motion.button onClick={() => runReview()} disabled={!text.trim()}
                    whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                    className="ml-auto flex items-center gap-2 px-5 py-2 text-sm font-medium text-white disabled:opacity-40"
                    style={{ ...SANS, backgroundColor: AMBER,
                      clipPath: "polygon(0 0,calc(100% - 8px) 0,100% 8px,100% 100%,8px 100%,0 calc(100% - 8px))" }}>
                    <FileText size={13} />开始审校
                  </motion.button>
                </div>
              </div>
            </motion.div>
          )}

          {phase === "workflow" && <WorkflowPanel onDone={() => {}} />}

          {phase === "done" && (
            <motion.div key="done" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <div className="bg-white border shadow-sm overflow-hidden" style={{ borderColor: BORDER }}>
                <div className="flex items-center justify-between px-6 py-3 border-b" style={{ borderColor: BORDER }}>
                  <SectionMark color={AMBER}>REVIEW RESULT</SectionMark>
                  <div className="flex items-center gap-2">
                    <Stamp label="IN REVIEW" color={AMBER} />
                    <CopyBtn text={result} id="review-result" copied={copied} copy={copy} />
                  </div>
                </div>
                <div className="grid" style={{ gridTemplateColumns: "1fr 264px" }}>
                  <div className="px-8 py-7 border-r space-y-4" style={{ borderColor: BORDER }}>
                    {renderParagraphs(result).map((p, i) => (
                      <p key={i} className="text-sm leading-relaxed" style={{ ...SERIF, color: INK }}>{p}</p>
                    ))}
                  </div>
                  <div className="py-6 px-5 space-y-3" style={{ backgroundColor: "#FDFAF6" }}>
                    <p className="text-[7px] tracking-[0.22em] uppercase mb-4" style={{ ...MONO, color: MUTED }}>编辑批注</p>
                    {["事实风险", "品牌口径", "PR 语气"].map((tag, i) => (
                      <div key={tag} className="border p-3" style={{ borderColor: BORDER, backgroundColor: PAPER }}>
                        <span className="text-[8px] tracking-widest uppercase" style={{ ...MONO, color: i === 0 ? RED : i === 1 ? AMBER : MUTED }}>{tag}</span>
                        <p className="text-[11px] mt-2 leading-relaxed" style={{ ...SERIF, color: MUTED }}>已由后端审校结果整理，建议人工确认后再对外使用。</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        {error && <div className="border px-5 py-4 mt-4 text-sm" style={{ borderColor: `${RED}40`, color: RED, backgroundColor: `${RED}06` }}>{error}</div>}
      </div>
    </div>
  );
}

/* ── search mode ── */
function SearchMode() {
  const [phase, setPhase]           = useState<Phase>("idle");
  const [query, setQuery]           = useState("");
  const [activeFilter, setFilter]   = useState("全部");
  const [expanded, setExpanded]     = useState<number | null>(null);
  const [results, setResults]       = useState<SearchResult[]>([]);
  const [error, setError]           = useState("");
  const { copied, copy }            = useCopy();

  const doSearch = async () => {
    if (!query.trim()) return;
    setError("");
    setPhase("workflow");
    try {
      const data = await apiJSON<{ results: SearchResult[] }>("/api/search", { query: query.trim(), k: 5 });
      setResults(data.results || []);
      setPhase("done");
    } catch (err) {
      setError(String((err as Error).message || err));
      setPhase("idle");
    }
  };

  return (
    <div className="h-full overflow-y-auto" style={{ scrollbarWidth: "none" }}>
      <div className="max-w-[720px] mx-auto px-12 py-10">

        <div className="flex items-baseline gap-4 mb-7">
          <span className="font-black leading-none select-none" style={{ ...DISP, fontSize: 56, color: BORDER, lineHeight: 1 }}>03</span>
          <div>
            <SectionMark color="#059669">知识库检索</SectionMark>
            <p className="text-xs mt-1" style={{ color: MUTED }}>从本地 PR 知识库中检索传播素材、技术说明和品牌口径</p>
          </div>
        </div>

        {/* Search bar */}
        <div className="bg-white border shadow-sm mb-5" style={{ borderColor: BORDER }}>
          <div className="flex items-center gap-3 border-b px-5 py-3" style={{ borderColor: BORDER }}>
            <input value={query} onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === "Enter" && doSearch()}
              placeholder="输入问题或关键词……"
              className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-muted-foreground/30"
              style={{ ...SERIF, color: INK }} />
            <motion.button onClick={doSearch} disabled={!query.trim()}
              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
              className="flex items-center gap-1.5 text-sm font-medium disabled:opacity-30 px-4 py-1.5 border"
              style={{ ...SANS, borderColor: `#05966940`, color: "#059669",
                clipPath: "polygon(0 0,calc(100% - 6px) 0,100% 6px,100% 100%,6px 100%,0 calc(100% - 6px))" }}>
              <Search size={13} />检索
            </motion.button>
          </div>
          <div className="flex items-center gap-1.5 px-5 py-2.5">
            {["全部","技术说明","发布会资料","品牌口径","媒体稿"].map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className="text-[8px] px-2 py-1 border transition-all"
                style={{ ...MONO, borderColor: activeFilter === f ? "#05966950" : BORDER,
                  color: activeFilter === f ? "#059669" : MUTED,
                  backgroundColor: activeFilter === f ? "#05966908" : "transparent" }}>
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Loading */}
        <AnimatePresence>
          {phase === "workflow" && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex items-center gap-3 py-4">
              <motion.div className="w-4 h-4 border-2 border-t-transparent rounded-full"
                style={{ borderColor: "#05966940", borderTopColor: "#059669" }}
                animate={{ rotate: 360 }} transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }} />
              <span className="text-sm" style={{ ...MONO, color: "#059669" }}>检索知识库…</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Quick queries */}
        {phase === "idle" && (
          <div>
            <div className="mb-3"><SectionMark>常用查询</SectionMark></div>
            <div className="bg-white border shadow-sm overflow-hidden" style={{ borderColor: BORDER }}>
              {[
                ["智能驾驶功能的官方传播表述", "高频"],
                ["纯电车型上市稿传播重点",     "高频"],
                ["车展发布会媒体沟通资料",     "近期"],
                ["品牌语气与风险词检查",       "常用"],
              ].map(([q, tag], i) => (
                <motion.button key={i} onClick={() => setQuery(q)}
                  whileHover={{ backgroundColor: "#FDFAF6" }}
                  className="w-full flex items-center justify-between gap-4 px-6 py-4 border-b last:border-0 text-left group"
                  style={{ borderColor: BORDER }}>
                  <div className="flex items-center gap-4">
                    <span className="text-[8px] w-4 text-right opacity-30 shrink-0" style={MONO}>{i + 1}</span>
                    <span className="text-sm group-hover:text-foreground transition-colors" style={{ ...SERIF, color: MUTED }}>{q}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[8px] px-1.5 py-px border" style={{ ...MONO, borderColor: BORDER, color: MUTED }}>{tag}</span>
                    <ChevronRight size={11} style={{ color: MUTED }} className="opacity-25 group-hover:opacity-60 transition-opacity" />
                  </div>
                </motion.button>
              ))}
            </div>
          </div>
        )}

        {/* Results */}
        <AnimatePresence>
          {phase === "done" && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3">
              <div className="flex items-center justify-between mb-1">
                <SectionMark color="#059669">{results.length} 条结果</SectionMark>
                <button onClick={() => { setPhase("idle"); setQuery(""); setExpanded(null); setResults([]); }}
                  className="flex items-center gap-1 text-xs" style={{ color: MUTED }}>
                  <RotateCcw size={10} /><span style={MONO}>重新检索</span>
                </button>
              </div>
              {results.map((r, i) => {
                const isOpen    = expanded === i;
                const relColor  = i === 0 ? RED : i === 1 ? AMBER : MUTED;
                const score = typeof r.rel === "number" ? r.rel : typeof r.score === "number" ? Math.round(r.score * 100) : Math.max(72, 98 - i * 7);
                const title = r.title || r.file_name || `资料 ${i + 1}`;
                const excerpt = r.excerpt || r.text || "";
                const type = r.type || "资料";
                const date = r.date || "本地";
                return (
                  <motion.div key={i}
                    initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.07 }}
                    className="bg-white border shadow-sm overflow-hidden cursor-pointer group"
                    style={{ borderColor: isOpen ? `${relColor}40` : BORDER }}
                    onClick={() => setExpanded(isOpen ? null : i)}>
                    <div className="px-6 py-5">
                      <div className="flex items-start gap-5">
                        {/* Relevance */}
                        <div className="shrink-0 text-center w-11 pt-0.5">
                          <div className="font-black leading-none" style={{ ...DISP, fontSize: 26, color: relColor }}>{score}</div>
                          <div className="text-[7px] mt-px" style={{ ...MONO, color: MUTED }}>%</div>
                          <div className="mt-2 h-px overflow-hidden" style={{ backgroundColor: BORDER }}>
                            <motion.div className="h-full" style={{ backgroundColor: relColor }}
                              initial={{ scaleX: 0, originX: 0 }}
                              animate={{ scaleX: Math.min(score, 100) / 100 }}
                              transition={{ delay: 0.1 + i * 0.07, duration: 0.6, ease: "easeOut" }} />
                          </div>
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-3 mb-2">
                            <h3 className="text-sm font-semibold leading-snug transition-colors group-hover:opacity-80"
                              style={{ color: INK }}>{title}</h3>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <span className="text-[8px] border px-1.5 py-px" style={{ ...MONO, borderColor: BORDER, color: MUTED }}>{type}</span>
                              <span className="text-[8px]" style={{ ...MONO, color: MUTED }}>{date}</span>
                            </div>
                          </div>
                          <p className="text-xs leading-relaxed" style={{ ...SERIF, color: MUTED }}>
                            {isOpen ? excerpt : excerpt.slice(0, 72) + (excerpt.length > 72 ? "…" : "")}
                          </p>
                        </div>
                      </div>
                    </div>

                    <AnimatePresence>
                      {isOpen && (
                        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22 }}
                          className="overflow-hidden border-t" style={{ borderColor: BORDER }}>
                          <div className="px-6 py-3 flex gap-3">
                            <CopyBtn text={excerpt} id={`r${i}`} copied={copied} copy={copy} />
                            <button className="flex items-center gap-1 text-[9px] transition-colors hover:opacity-70"
                              style={{ ...MONO, color: MUTED }}>
                              <ArrowUpRight size={10} />查看全文
                            </button>
                            <button className="flex items-center gap-1 text-[9px] transition-colors hover:opacity-70 ml-auto"
                              style={{ ...MONO, color: "#059669" }}>
                              引用到 brief →
                            </button>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                );
              })}
            </motion.div>
          )}
        </AnimatePresence>
        {error && <div className="border px-5 py-4 mt-4 text-sm" style={{ borderColor: `${RED}40`, color: RED, backgroundColor: `${RED}06` }}>{error}</div>}
      </div>
    </div>
  );
}

/* ── app ── */
export default function App() {
  const [mode, setMode] = useState<Mode>("generate");

  const switchMode = (m: Mode) => setMode(m);

  return (
    <div className="h-screen w-full flex overflow-hidden bg-background" style={SANS}>
      <Sidebar mode={mode} switchMode={switchMode} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <div className="flex items-center justify-between px-4 md:px-8 shrink-0 bg-white/50 backdrop-blur-sm"
          style={{ height: 42, borderBottom: `1px solid ${BORDER}` }}>
          <div className="flex items-center gap-2">
            <span className="text-[9px]" style={{ ...MONO, color: MUTED }}>PR Agent</span>
            <ChevronRight size={9} style={{ color: MUTED }} />
            <span className="text-[9px]" style={{ ...MONO, color: MUTED }}>内容工作台</span>
            <ChevronRight size={9} style={{ color: MUTED }} />
            <span className="text-[9px] font-medium" style={{ ...MONO, color: INK }}>
              {mode === "generate" ? "传播内容生成" : mode === "review" ? "稿件审校改写" : "知识库检索"}
            </span>
          </div>
          <div className="hidden sm:flex items-center gap-5">
            {[["MODE", mode.toUpperCase()], ["KB", "local"], ["VER", "beta"]].map(([k, v]) => (
              <div key={k} className="flex items-center gap-1.5">
                <span className="text-[7px] tracking-widest" style={{ ...MONO, color: MUTED }}>{k}</span>
                <span className="text-[8px]" style={{ ...MONO, color: INK }}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Workspace */}
        <div className="flex-1 overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.div key={mode}
              initial={{ opacity: 0, x: 6 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -6 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="h-full">
              {mode === "generate" && <GenerateMode />}
              {mode === "review"   && <ReviewMode />}
              {mode === "search"   && <SearchMode />}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
