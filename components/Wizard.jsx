import React, { useMemo, useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Play,
  Pause,
  Wand2,
  Plus,
  Trash2,
  Gauge,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Circle,
  Loader2,
  Clock3
} from "lucide-react";

import { apiFetch } from "../apiClient";
import { useTranslation } from "../localization";

function SectionTitle({ icon: Icon, title, desc }) {
  return (
    <div className="flex items-start gap-3 mb-3">
      <div className="p-2 rounded-lg bg-accent">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <div className="font-semibold">{title}</div>
        {desc && <div className="text-sm text-muted-foreground">{desc}</div>}
      </div>
    </div>
  );
}

function TextInput({ label, ...props }) {
  return (
    <label className="block mb-3">
      <div className="text-sm mb-1 text-muted-foreground">{label}</div>
      <input
        {...props}
        className={`w-full px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/40 ${props.className || ""}`}
      />
    </label>
  );
}

function TextArea({ label, rows = 3, ...props }) {
  return (
    <label className="block mb-3">
      <div className="text-sm mb-1 text-muted-foreground">{label}</div>
      <textarea
        rows={rows}
        {...props}
        className={`w-full px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/40 ${props.className || ""}`}
      />
    </label>
  );
}

function Checkbox({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 mb-2 cursor-pointer">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="text-sm text-muted-foreground">{label}</span>
    </label>
  );
}

function formatRelativeTime(locale, timestamp) {
  if (!timestamp) {
    return null;
  }
  const safeLocale = typeof locale === "string" && locale ? locale : "tr";
  const diffSeconds = Math.round((timestamp - Date.now()) / 1000);
  const absoluteSeconds = Math.abs(diffSeconds);
  const units = [
    { unit: "second", seconds: 1 },
    { unit: "minute", seconds: 60 },
    { unit: "hour", seconds: 60 * 60 },
    { unit: "day", seconds: 60 * 60 * 24 },
    { unit: "week", seconds: 60 * 60 * 24 * 7 },
    { unit: "month", seconds: 60 * 60 * 24 * 30 },
    { unit: "year", seconds: 60 * 60 * 24 * 365 }
  ];

  const rtf = new Intl.RelativeTimeFormat(safeLocale, { numeric: "auto" });
  for (let index = 0; index < units.length; index += 1) {
    const current = units[index];
    const next = units[index + 1];
    if (!next || absoluteSeconds < next.seconds) {
      const value = Math.round(diffSeconds / current.seconds);
      return rtf.format(value, current.unit);
    }
  }
  return null;
}

function AutosaveBadge({ status, savedAt, tf, locale }) {
  const meta = useMemo(() => {
    if (status === "saving") {
      return {
        icon: Loader2,
        className: "border-border bg-muted text-muted-foreground",
        labelKey: "wizard.autosave.saving",
        fallback: "Taslak kaydediliyor…"
      };
    }
    if (status === "saved") {
      return {
        icon: CheckCircle2,
        className: "border-emerald-200 bg-emerald-50 text-emerald-700",
        labelKey: "wizard.autosave.saved",
        fallback: "Taslak güncel"
      };
    }
    return {
      icon: Clock3,
      className: "border-border bg-muted/40 text-muted-foreground",
      labelKey: "wizard.autosave.idle",
      fallback: "Taslak hazır"
    };
  }, [status]);

  const relative = status !== "saving" ? formatRelativeTime(locale, savedAt) : null;
  const Icon = meta.icon;

  return (
    <div className="flex flex-col items-end gap-1 text-right">
      <Badge variant="outline" className={`flex items-center gap-1 text-xs ${meta.className}`}>
        <Icon className={`h-3.5 w-3.5 ${status === "saving" ? "animate-spin" : ""}`} />
        {tf(meta.labelKey, meta.fallback)}
      </Badge>
      {relative && (
        <span className="text-[11px] text-muted-foreground">
          {tf("wizard.autosave.savedHint", "Son kaydetme:")} {relative}
        </span>
      )}
    </div>
  );
}

function RowActions({ onAdd, onRemove, canRemove }) {
  return (
    <div className="flex items-center gap-2">
      <Button type="button" variant="secondary" size="sm" onClick={onAdd}>
        <Plus className="h-4 w-4 mr-1" /> Satır ekle
      </Button>
      {canRemove && (
        <Button type="button" variant="destructive" size="sm" onClick={onRemove}>
          <Trash2 className="h-4 w-4 mr-1" /> Son satırı sil
        </Button>
      )}
    </div>
  );
}

function toArray(csv) {
  if (!csv) return undefined;
  const arr = String(csv)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return arr.length ? arr : undefined;
}

function toFloatOrNull(v) {
  if (v === "" || v === null || v === undefined) return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

function parseMultiline(value) {
  if (!value) return [];
  return String(value)
    .split(/\r?\n|,/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function buildEmotionProfileDraft(emotion) {
  if (!emotion) return undefined;

  const tone = emotion.tone?.trim();
  const empathy = emotion.empathy?.trim();
  const energy = emotion.energy?.trim();
  const signatureEmoji = emotion.signatureEmoji?.trim();
  const phrases = parseMultiline(emotion.signaturePhrases);
  const anecdotes = parseMultiline(emotion.anecdotes);

  const payload = {};
  if (tone) payload.tone = tone;
  if (empathy) payload.empathy = empathy;
  if (energy) payload.energy = energy;
  if (signatureEmoji) payload.signature_emoji = signatureEmoji;
  if (phrases.length) payload.signature_phrases = phrases;
  if (anecdotes.length) payload.anecdotes = anecdotes;

  return Object.keys(payload).length ? payload : undefined;
}

const WIZARD_AUTOSAVE_KEY = "piyasa.wizard.autosave";
const BOT_TOKEN_PATTERN = /^\d{6,}:[A-Za-z0-9_-]{30,}$/;
const CHAT_ID_PATTERN = /^-?\d{6,}$/;

const INITIAL_BOT = {
  name: "",
  token: "",
  username: "",
  is_enabled: true
};

const INITIAL_CHAT = {
  chat_id: "",
  title: "",
  topics: "BIST,FX,Kripto,Makro"
};

const INITIAL_PERSONA = {
  tone: "samimi ama profesyonel",
  risk_profile: "orta",
  watchlist: "BIST:AKBNK,XAUUSD,BTCUSDT",
  never_do: "garanti kazanç vaadi,kaynaksız kesin rakam",
  emojis: true,
  length: "kısa-orta",
  disclaimer: "yatırım tavsiyesi değildir"
};

const INITIAL_EMOTION = {
  tone: "sıcak ve umutlu",
  empathy: "kullanıcının duygusunu aynala, ardından umut ver",
  energy: "orta tempo, sakin",
  signatureEmoji: "😊",
  signaturePhrases: "şahsi fikrim\nseninle aynı hissediyorum",
  anecdotes: "Geçen ayki sert dalgada planıma sadık kaldım\n2008'de paniğe kapılmadan portföyümü korudum"
};

const INITIAL_STANCES = [
  { topic: "Bankacılık", stance_text: "Orta vadede temkinli; geri çekilmeler kademeli fırsat.", confidence: 0.7, cooldown_until: "" },
  { topic: "Kripto", stance_text: "Kısa vadede volatil; uzun vadede seçici iyimser.", confidence: 0.6, cooldown_until: "" }
];

const INITIAL_HOLDINGS = [
  { symbol: "BIST:AKBNK", avg_price: "63.4", size: "120", note: "uzun vade çekirdek pozisyon" }
];

function evaluateBotChat(bot, chat) {
  const name = bot.name?.trim();
  if (!name) {
    return { ok: false, message: "Bot adı zorunludur.", severity: "error" };
  }
  const token = bot.token?.trim();
  if (!token) {
    return { ok: false, message: "Bot token zorunludur.", severity: "error" };
  }
  if (!BOT_TOKEN_PATTERN.test(token)) {
    return { ok: false, message: "Bot token formatı hatalı görünüyor.", severity: "error" };
  }
  const chatId = chat.chat_id?.trim();
  if (!chatId) {
    return { ok: false, message: "Chat ID zorunludur.", severity: "error" };
  }
  if (!CHAT_ID_PATTERN.test(chatId)) {
    return { ok: false, message: "Chat ID formatını kontrol edin.", severity: "error" };
  }

  return {
    ok: true,
    message: "Kimlik ve bağlantı adımı hazır görünüyor.",
    severity: "success",
    highlights: [
      `Bot: ${name}`,
      `Chat ID: ${chatId}`,
      token ? `Token: ${token.replace(/^(.{4}).+(.{4})$/, "$1…$2")}` : null
    ].filter(Boolean)
  };
}

function evaluatePersona(persona, emotion) {
  const tone = persona.tone?.trim();
  if (!tone) {
    return { ok: false, message: "Persona üslup alanı boş bırakılamaz.", severity: "error" };
  }
  const empathy = emotion.empathy?.trim();
  if (!empathy) {
    return { ok: false, message: "Empati yaklaşımı tanımlanmalıdır.", severity: "error" };
  }
  const emotionTone = emotion.tone?.trim();
  if (!emotionTone) {
    return { ok: false, message: "Duygu tonu boş bırakılamaz.", severity: "error" };
  }

  const personaRisk = persona.risk_profile?.trim();
  const signatureEmoji = emotion.signatureEmoji?.trim();
  const highlights = [
    `Üslup: ${tone}`,
    personaRisk ? `Risk: ${personaRisk}` : null,
    `Empati: ${empathy.slice(0, 60)}${empathy.length > 60 ? "…" : ""}`,
    signatureEmoji ? `Emoji: ${signatureEmoji}` : null
  ].filter(Boolean);

  return {
    ok: true,
    message: "Persona ve duygu profili tamam.",
    severity: "success",
    highlights
  };
}

function evaluateStances(stances, holdings) {
  for (const stance of stances) {
    const hasAny = stance.topic || stance.stance_text || stance.confidence !== "" || stance.cooldown_until;
    if (hasAny) {
      if (!stance.topic?.trim() || !stance.stance_text?.trim()) {
        return { ok: false, message: "Her tutum için konu ve açıklama birlikte girilmelidir.", severity: "error" };
      }
      if (stance.confidence !== "") {
        const confidenceNumber = Number(stance.confidence);
        if (!Number.isFinite(confidenceNumber) || confidenceNumber < 0 || confidenceNumber > 1) {
          return { ok: false, message: "Güven değeri 0 ile 1 arasında olmalıdır.", severity: "error" };
        }
      }
    }
  }

  for (const holding of holdings) {
    const hasAny = holding.symbol || holding.avg_price !== "" || holding.size !== "" || holding.note;
    if (hasAny && !holding.symbol?.trim()) {
      return { ok: false, message: "Pozisyon satırları sembol ile başlamalıdır.", severity: "error" };
    }
  }

  const stanceCount = stances.filter((stance) => stance.topic?.trim() && stance.stance_text?.trim()).length;
  const holdingCount = holdings.filter((holding) => holding.symbol?.trim()).length;

  return {
    ok: true,
    message: "Strateji notları ve pozisyonlar hazır.",
    severity: "success",
    highlights: [
      `${stanceCount} tutum kaydı`,
      `${holdingCount} portföy satırı`
    ]
  };
}

function evaluateSummary(stepResults, payload) {
  const missingSteps = Object.entries(stepResults)
    .filter(([key, result]) => key !== "summary" && !result.ok)
    .map(([key]) => key);

  if (missingSteps.length > 0) {
    return {
      ok: false,
      message: "Eksik adımlar var, özet kontrolünü tamamlayın.",
      severity: "error",
      highlights: missingSteps.map((id) => {
        switch (id) {
          case "bot-chat":
            return "Bot & Sohbet adımı eksik";
          case "persona":
            return "Persona & Duygu adımı eksik";
          case "stances":
            return "Tutumlar & Pozisyonlar adımı eksik";
          default:
            return "Eksik adım";
        }
      })
    };
  }

  const highlights = [];
  if (payload?.bot?.name) {
    highlights.push(`Bot: ${payload.bot.name}`);
  }
  if (payload?.chat?.chat_id) {
    highlights.push(`Chat: ${payload.chat.chat_id}`);
  }
  if (payload?.persona?.tone) {
    highlights.push(`Üslup: ${payload.persona.tone}`);
  }
  if (payload?.start_simulation) {
    highlights.push("Kurulumdan sonra simülasyon başlayacak");
  }

  return {
    ok: true,
    message: "Kurulum gönderilmeye hazır.",
    severity: "success",
    highlights
  };
}

export default function Wizard({ onDone }) {
  const { t, locale } = useTranslation();
  const tf = (key, fallback) => t(key) || fallback;
  const [simActive, setSimActive] = useState(false);
  const [scale, setScale] = useState(1.0);

  const [bot, setBot] = useState(() => ({ ...INITIAL_BOT }));
  const [chat, setChat] = useState(() => ({ ...INITIAL_CHAT }));
  const [persona, setPersona] = useState(() => ({ ...INITIAL_PERSONA }));
  const [emotion, setEmotion] = useState(() => ({ ...INITIAL_EMOTION }));
  const [stances, setStances] = useState(() => INITIAL_STANCES.map((stance) => ({ ...stance })));
  const [holdings, setHoldings] = useState(() => INITIAL_HOLDINGS.map((holding) => ({ ...holding })));

  const [currentStep, setCurrentStep] = useState(0);
  const [stepError, setStepError] = useState("");
  const [autosaveState, setAutosaveState] = useState({ status: "idle", savedAt: null });
  const autosaveTimeoutRef = useRef(null);
  const [wizardLoaded, setWizardLoaded] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);

  const wizardSteps = useMemo(
    () => [
      {
        id: "bot-chat",
        title: tf("wizard.steps.bot", "Bot & Sohbet"),
        description: tf("wizard.steps.bot.desc", "Kimlik ve bağlantı ayarlarını yapılandırın.")
      },
      {
        id: "persona",
        title: tf("wizard.steps.persona", "Persona & Duygu"),
        description: tf("wizard.steps.persona.desc", "Üslup ve empati ayarlarını belirleyin.")
      },
      {
        id: "stances",
        title: tf("wizard.steps.stances", "Tutumlar & Pozisyonlar"),
        description: tf("wizard.steps.stances.desc", "Opsiyonel strateji ve portföy notları.")
      },
      {
        id: "summary",
        title: tf("wizard.steps.summary", "Özet & Yayınla"),
        description: tf("wizard.steps.summary.desc", "Kurulumu tamamlamadan önce son kontrol.")
      }
    ],
    [tf]
  );

  useEffect(() => {
    setStepError("");
  }, [currentStep]);

  useEffect(() => {
    if (typeof window === "undefined") {
      setWizardLoaded(true);
      return;
    }
    try {
      const raw = window.localStorage.getItem(WIZARD_AUTOSAVE_KEY);
      if (!raw) {
        setWizardLoaded(true);
        return;
      }
      const parsed = JSON.parse(raw);
      if (parsed?.bot) {
        setBot({ ...INITIAL_BOT, ...parsed.bot });
      }
      if (parsed?.chat) {
        setChat({ ...INITIAL_CHAT, ...parsed.chat });
      }
      if (parsed?.persona) {
        setPersona({ ...INITIAL_PERSONA, ...parsed.persona });
      }
      if (parsed?.emotion) {
        setEmotion({ ...INITIAL_EMOTION, ...parsed.emotion });
      }
      if (Array.isArray(parsed?.stances)) {
        const nextStances = parsed.stances.map((stance) => ({
          topic: stance.topic ?? "",
          stance_text: stance.stance_text ?? "",
          confidence: stance.confidence ?? "",
          cooldown_until: stance.cooldown_until ?? ""
        }));
        setStances(nextStances.length ? nextStances : INITIAL_STANCES.map((stance) => ({ ...stance })));
      }
      if (Array.isArray(parsed?.holdings)) {
        const nextHoldings = parsed.holdings.map((holding) => ({
          symbol: holding.symbol ?? "",
          avg_price: holding.avg_price ?? "",
          size: holding.size ?? "",
          note: holding.note ?? ""
        }));
        setHoldings(nextHoldings.length ? nextHoldings : INITIAL_HOLDINGS.map((holding) => ({ ...holding })));
      }
      if (typeof parsed?.simActive === "boolean") {
        setSimActive(parsed.simActive);
      }
      if (typeof parsed?.scale === "number" && Number.isFinite(parsed.scale)) {
        setScale(parsed.scale);
      }
      if (typeof parsed?.currentStep === "number" && Number.isFinite(parsed.currentStep)) {
        const nextIndex = Math.min(Math.max(parsed.currentStep, 0), wizardSteps.length - 1);
        setCurrentStep(nextIndex);
      }
    } catch (error) {
      console.warn("Wizard taslak verileri yüklenemedi:", error);
    } finally {
      setWizardLoaded(true);
    }
  }, [wizardSteps.length]);

  useEffect(() => {
    if (!wizardLoaded || typeof window === "undefined") {
      return;
    }
    setAutosaveState((prev) => ({ ...prev, status: "saving" }));
    if (autosaveTimeoutRef.current) {
      window.clearTimeout(autosaveTimeoutRef.current);
    }
    try {
      const payload = {
        bot,
        chat,
        persona,
        emotion,
        stances,
        holdings,
        simActive,
        scale,
        currentStep
      };
      window.localStorage.setItem(WIZARD_AUTOSAVE_KEY, JSON.stringify(payload));
    } catch (error) {
      console.warn("Wizard taslak kaydedilemedi:", error);
    }
    const timeoutId = window.setTimeout(() => {
      setAutosaveState({ status: "saved", savedAt: Date.now() });
      autosaveTimeoutRef.current = null;
    }, 600);
    autosaveTimeoutRef.current = timeoutId;
    return () => {
      if (autosaveTimeoutRef.current) {
        window.clearTimeout(autosaveTimeoutRef.current);
        autosaveTimeoutRef.current = null;
      }
    };
  }, [bot, chat, persona, emotion, stances, holdings, simActive, scale, currentStep, wizardLoaded]);

  const progressValue = Math.round((currentStep / Math.max(wizardSteps.length - 1, 1)) * 100);

  const clearDraft = () => {
    if (typeof window === "undefined") {
      return;
    }
    const shouldReset = window.confirm(tf("wizard.confirm.clearDraft", "Taslak temizlensin mi?"));
    if (!shouldReset) {
      return;
    }
    window.localStorage.removeItem(WIZARD_AUTOSAVE_KEY);
    setBot({ ...INITIAL_BOT });
    setChat({ ...INITIAL_CHAT });
    setPersona({ ...INITIAL_PERSONA });
    setEmotion({ ...INITIAL_EMOTION });
    setStances(INITIAL_STANCES.map((stance) => ({ ...stance })));
    setHoldings(INITIAL_HOLDINGS.map((holding) => ({ ...holding })));
    setCurrentStep(0);
    setMessage(null);
    setStepError("");
    setAutosaveState({ status: "idle", savedAt: null });
  };

  async function fetchMetrics() {
    try {
      const r = await apiFetch("/metrics");
      const m = await r.json();
      setSimActive(!!m.simulation_active);
      setScale(Number(m.scale_factor || 1.0));
    } catch (err) {
      console.error(err);
    }
  }

  useEffect(() => {
    fetchMetrics();
  }, []);

  async function toggleSimulation() {
    try {
      const endpoint = simActive ? "/control/stop" : "/control/start";
      await apiFetch(endpoint, { method: "POST" });
      setSimActive(!simActive);
      setTimeout(fetchMetrics, 800);
      if (onDone) onDone();
    } catch (e) {
      console.error(e);
    }
  }

  async function applyScale() {
    try {
      await apiFetch("/control/scale", {
        method: "POST",
        body: JSON.stringify({ factor: Number(scale) || 1.0 }),
      });
      setMessage({ type: "success", text: "Ölçek güncellendi." });
      if (onDone) onDone();
    } catch (e) {
      console.error(e);
      setMessage({ type: "error", text: "Ölçek güncellenemedi." });
    }
  }

  function buildPayload() {
    const personaProfile = {
      tone: persona.tone || undefined,
      risk_profile: persona.risk_profile || undefined,
      watchlist: toArray(persona.watchlist),
      never_do: toArray(persona.never_do),
      style: {
        emojis: !!persona.emojis,
        length: persona.length || undefined,
        disclaimer: persona.disclaimer || undefined,
      },
    };
    // tüm alanlar boşsa persona gönderme
    const isPersonaEmpty =
      !personaProfile.tone &&
      !personaProfile.risk_profile &&
      !personaProfile.watchlist &&
      !personaProfile.never_do &&
      !personaProfile.style.length &&
      !personaProfile.style.disclaimer &&
      personaProfile.style.emojis === false;

    const stanceBody = stances
      .map((s) => ({
        topic: s.topic?.trim(),
        stance_text: s.stance_text?.trim(),
        confidence: s.confidence === "" ? undefined : Number(s.confidence),
        cooldown_until: s.cooldown_until || undefined,
      }))
      .filter((s) => s.topic && s.stance_text);

    const holdingBody = holdings
      .map((h) => ({
        symbol: h.symbol?.trim(),
        avg_price: toFloatOrNull(h.avg_price),
        size: toFloatOrNull(h.size),
        note: h.note?.trim() || undefined,
      }))
      .filter((h) => h.symbol);

    const emotionProfile = buildEmotionProfileDraft(emotion);

    return {
      bot: {
        name: bot.name.trim(),
        token: bot.token.trim(),
        username: bot.username.trim() || undefined,
        is_enabled: !!bot.is_enabled,
      },
      chat: {
        chat_id: chat.chat_id.trim(),
        title: chat.title.trim() || undefined,
        topics: toArray(chat.topics) || ["BIST", "FX", "Kripto", "Makro"],
      },
      persona: isPersonaEmpty ? undefined : personaProfile,
      emotion: emotionProfile,
      stances: stanceBody.length ? stanceBody : undefined,
      holdings: holdingBody.length ? holdingBody : undefined,
      start_simulation: simActive,
    };
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setMessage(null);

    if (!validateStep("summary")) {
      return;
    }

    const payload = buildPayload();

    setSubmitting(true);
    try {
      const r = await apiFetch("/wizard/setup", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await r.json().catch(() => ({}));
      setMessage({ type: "success", text: "Kurulum tamamlandı 🎉 Bot ve chat oluşturuldu." });
      if (onDone) onDone();
      setTimeout(fetchMetrics, 800);
    } catch (err) {
      console.error(err);
      setMessage({ type: "error", text: String(err.message || err) });
    } finally {
      setSubmitting(false);
    }
  }

  const summaryPayload = useMemo(
    () => buildPayload(),
    [bot, chat, persona, emotion, stances, holdings, simActive]
  );

  const stepAssessments = useMemo(() => {
    const partialResults = {
      "bot-chat": evaluateBotChat(bot, chat),
      persona: evaluatePersona(persona, emotion),
      stances: evaluateStances(stances, holdings)
    };
    const summary = evaluateSummary(partialResults, summaryPayload);
    return { ...partialResults, summary };
  }, [bot, chat, persona, emotion, stances, holdings, summaryPayload]);

  // --- helpers to mutate arrays
  const addStance = () => setStances((arr) => [...arr, { topic: "", stance_text: "", confidence: "", cooldown_until: "" }]);
  const removeStance = () => setStances((arr) => (arr.length > 0 ? arr.slice(0, -1) : arr));
  const addHolding = () => setHoldings((arr) => [...arr, { symbol: "", avg_price: "", size: "", note: "" }]);
  const removeHolding = () => setHoldings((arr) => (arr.length > 0 ? arr.slice(0, -1) : arr));

  const validateBotChatStep = () => {
    const result = stepAssessments["bot-chat"];
    if (!result?.ok) {
      setStepError(result?.message || "Bu adım eksik görünüyor.");
      return false;
    }
    setStepError("");
    return true;
  };

  const validatePersonaStep = () => {
    const result = stepAssessments.persona;
    if (!result?.ok) {
      setStepError(result?.message || "Persona ayarlarını kontrol edin.");
      return false;
    }
    setStepError("");
    return true;
  };

  const validateStancesStep = () => {
    const result = stepAssessments.stances;
    if (!result?.ok) {
      setStepError(result?.message || "Tutum ve pozisyonları kontrol edin.");
      return false;
    }
    setStepError("");
    return true;
  };

  const validateSummaryStep = () => {
    if (!validateBotChatStep()) {
      return false;
    }
    if (!validatePersonaStep()) {
      return false;
    }
    if (!validateStancesStep()) {
      return false;
    }
    return true;
  };

  const validateStep = (stepId) => {
    switch (stepId) {
      case "bot-chat":
        return validateBotChatStep();
      case "persona":
        return validatePersonaStep();
      case "stances":
        return validateStancesStep();
      case "summary":
        return validateSummaryStep();
      default:
        return true;
    }
  };

  const handleNext = () => {
    const stepId = wizardSteps[currentStep].id;
    if (!validateStep(stepId)) {
      return;
    }
    setCurrentStep((index) => Math.min(index + 1, wizardSteps.length - 1));
  };

  const handlePrev = () => {
    setCurrentStep((index) => Math.max(index - 1, 0));
  };

  const handleStepClick = (index) => {
    if (index < currentStep) {
      setCurrentStep(index);
    }
  };

  const renderBotChatStep = () => (
    <div className="grid md:grid-cols-2 gap-6">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Bot</CardTitle>
          <CardDescription>Bot token’ını BotFather’dan alırsın.</CardDescription>
        </CardHeader>
        <CardContent>
          <TextInput label="Bot Adı" placeholder="AkıllıBot" value={bot.name} onChange={(e) => setBot({ ...bot, name: e.target.value })} />
          <TextInput label="Bot Token" placeholder="123456:ABC-DEF..." value={bot.token} onChange={(e) => setBot({ ...bot, token: e.target.value })} />
          <TextInput label="Kullanıcı Adı (@...)" placeholder="@akillibot" value={bot.username} onChange={(e) => setBot({ ...bot, username: e.target.value })} />
          <Checkbox label="Bot aktif" checked={bot.is_enabled} onChange={(v) => setBot({ ...bot, is_enabled: v })} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Sohbet (Chat)</CardTitle>
          <CardDescription>Telegram grup/kanal chat_id değerini gir.</CardDescription>
        </CardHeader>
        <CardContent>
          <TextInput label="Chat ID" placeholder="-1001234567890" value={chat.chat_id} onChange={(e) => setChat({ ...chat, chat_id: e.target.value })} />
          <TextInput label="Başlık" placeholder="Piyasa Grubu" value={chat.title} onChange={(e) => setChat({ ...chat, title: e.target.value })} />
          <TextInput label="Konular (virgülle)" placeholder="BIST,FX,Kripto,Makro" value={chat.topics} onChange={(e) => setChat({ ...chat, topics: e.target.value })} />
        </CardContent>
      </Card>
    </div>
  );

  const renderPersonaStep = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Kişilik (Persona)</CardTitle>
          <CardDescription>Botun üslubu ve tercihleri.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <TextInput label="Üslup (tone)" placeholder="samimi ama profesyonel" value={persona.tone} onChange={(e) => setPersona({ ...persona, tone: e.target.value })} />
              <TextInput label="Risk Profili" placeholder="düşük / orta / yüksek" value={persona.risk_profile} onChange={(e) => setPersona({ ...persona, risk_profile: e.target.value })} />
              <TextInput label="İzleme Listesi (virgülle)" placeholder="BIST:AKBNK,XAUUSD,BTCUSDT" value={persona.watchlist} onChange={(e) => setPersona({ ...persona, watchlist: e.target.value })} />
              <TextInput label="Kaçınılacaklar (virgülle)" placeholder="garanti kazanç vaadi,..." value={persona.never_do} onChange={(e) => setPersona({ ...persona, never_do: e.target.value })} />
            </div>
            <div>
              <Checkbox label="Emoji kullan" checked={!!persona.emojis} onChange={(v) => setPersona({ ...persona, emojis: v })} />
              <TextInput label="Mesaj Uzunluğu" placeholder="kısa-orta" value={persona.length} onChange={(e) => setPersona({ ...persona, length: e.target.value })} />
              <TextInput label="Kısa Dipnot (opsiyonel)" placeholder="yatırım tavsiyesi değildir" value={persona.disclaimer} onChange={(e) => setPersona({ ...persona, disclaimer: e.target.value })} />
            </div>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Duygu Profili</CardTitle>
          <CardDescription>Empati tonu, anekdotlar ve imza ifadeler.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <TextInput label="Duygu Tonu" placeholder="sıcak ve umutlu" value={emotion.tone} onChange={(e) => setEmotion({ ...emotion, tone: e.target.value })} />
              <TextArea label="Empati Yaklaşımı" rows={2} placeholder="Kullanıcının duygusunu aynala, ardından umut ver" value={emotion.empathy} onChange={(e) => setEmotion({ ...emotion, empathy: e.target.value })} />
              <TextInput label="Tempo / Enerji" placeholder="orta tempo, sakin" value={emotion.energy} onChange={(e) => setEmotion({ ...emotion, energy: e.target.value })} />
            </div>
            <div>
              <TextInput label="İmza Emoji" placeholder="😊" value={emotion.signatureEmoji} onChange={(e) => setEmotion({ ...emotion, signatureEmoji: e.target.value })} />
              <TextArea label="İmza İfadeler" rows={3} placeholder="Her satıra bir ifade yazın" value={emotion.signaturePhrases} onChange={(e) => setEmotion({ ...emotion, signaturePhrases: e.target.value })} />
              <TextArea label="Anekdot Havuzu" rows={3} placeholder="Kısa kişisel hikâyeleri her satıra bir adet yazın" value={emotion.anecdotes} onChange={(e) => setEmotion({ ...emotion, anecdotes: e.target.value })} />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );

  const renderStancesStep = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Tutumlar (Stances)</CardTitle>
          <CardDescription>Botun konu bazlı kanaatleri.</CardDescription>
        </CardHeader>
        <CardContent>
          {stances.map((s, idx) => (
            <div key={idx} className="grid md:grid-cols-4 gap-3 mb-4">
              <TextInput label="Konu" placeholder="Bankacılık" value={s.topic} onChange={(e) => {
                const v = e.target.value;
                setStances((arr) => arr.map((x, i) => (i === idx ? { ...x, topic: v } : x)));
              }} />
              <TextInput label="Güven (0-1)" type="number" step="0.1" value={s.confidence} onChange={(e) => {
                const v = e.target.value;
                setStances((arr) => arr.map((x, i) => (i === idx ? { ...x, confidence: v } : x)));
              }} />
              <TextInput label="Cooldown Bitişi" type="datetime-local" value={s.cooldown_until} onChange={(e) => {
                const v = e.target.value;
                setStances((arr) => arr.map((x, i) => (i === idx ? { ...x, cooldown_until: v } : x)));
              }} />
              <TextArea label="Tutum Metni" rows={2} value={s.stance_text} onChange={(e) => {
                const v = e.target.value;
                setStances((arr) => arr.map((x, i) => (i === idx ? { ...x, stance_text: v } : x)));
              }} />
            </div>
          ))}
          <RowActions onAdd={addStance} onRemove={removeStance} canRemove={stances.length > 0} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Pozisyonlar (Holdings)</CardTitle>
          <CardDescription>Hikâye amaçlı örnek pozisyonlar (opsiyonel).</CardDescription>
        </CardHeader>
        <CardContent>
          {holdings.map((h, idx) => (
            <div key={idx} className="grid md:grid-cols-4 gap-3 mb-4">
              <TextInput label="Sembol" placeholder="BIST:AKBNK" value={h.symbol} onChange={(e) => {
                const v = e.target.value;
                setHoldings((arr) => arr.map((x, i) => (i === idx ? { ...x, symbol: v } : x)));
              }} />
              <TextInput label="Ortalama Maliyet" type="number" step="0.0001" value={h.avg_price} onChange={(e) => {
                const v = e.target.value;
                setHoldings((arr) => arr.map((x, i) => (i === idx ? { ...x, avg_price: v } : x)));
              }} />
              <TextInput label="Adet/Lot" type="number" step="0.01" value={h.size} onChange={(e) => {
                const v = e.target.value;
                setHoldings((arr) => arr.map((x, i) => (i === idx ? { ...x, size: v } : x)));
              }} />
              <TextInput label="Not" placeholder="uzun vade" value={h.note} onChange={(e) => {
                const v = e.target.value;
                setHoldings((arr) => arr.map((x, i) => (i === idx ? { ...x, note: v } : x)));
              }} />
            </div>
          ))}
          <RowActions onAdd={addHolding} onRemove={removeHolding} canRemove={holdings.length > 0} />
        </CardContent>
      </Card>
    </div>
  );

  const renderSummaryList = (items) => (
    <ul className="text-sm text-muted-foreground space-y-2">
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  );

  const renderSummaryStep = () => {
    const payload = summaryPayload;
    const maskedToken = payload.bot?.token ? payload.bot.token.replace(/^(.{4}).+(.{4})$/, "$1…$2") : "-";
    const personaTone = payload.persona?.tone || persona.tone || "-";
    const personaRisk = payload.persona?.risk_profile || persona.risk_profile || "-";
    const personaNeverDo = payload.persona?.never_do?.join?.(", ") ?? (persona.never_do || "-");
    const personaEmoji = (payload.persona?.style?.emojis ?? !!persona.emojis) ? "Evet" : "Hayır";
    const empathy = payload.emotion?.empathy || emotion.empathy || "-";
    const signaturePhrases = payload.emotion?.signature_phrases?.join?.(", ") ?? (emotion.signaturePhrases || "-");
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Kimlik & Bağlantı</CardTitle>
            <CardDescription>Bot ve chat ayarlarını gözden geçirin.</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-3 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Bot Adı</dt>
                <dd className="font-medium">{payload.bot?.name || "-"}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Bot Token</dt>
                <dd className="font-mono">{maskedToken}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Chat ID</dt>
                <dd>{payload.chat?.chat_id || "-"}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Başlık</dt>
                <dd>{payload.chat?.title || "-"}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Konular</dt>
                <dd>{payload.chat?.topics?.join?.(", ") || "-"}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Simülasyon</dt>
                <dd>{payload.start_simulation ? "Kurulumdan sonra başlat" : "Kapalı"}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Persona & Duygu</CardTitle>
            <CardDescription>Üslup rehberinin son kontrolü.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div><span className="text-muted-foreground">Üslup:</span> {personaTone}</div>
            <div><span className="text-muted-foreground">Risk Profili:</span> {personaRisk}</div>
            <div><span className="text-muted-foreground">Kaçınılacaklar:</span> {personaNeverDo}</div>
            <div><span className="text-muted-foreground">Emoji:</span> {personaEmoji}</div>
            <div><span className="text-muted-foreground">Empati Yaklaşımı:</span> {empathy}</div>
            <div><span className="text-muted-foreground">İmza İfadeler:</span> {signaturePhrases}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Tutumlar & Pozisyonlar</CardTitle>
            <CardDescription>Strateji ve örnek portföy notlarını gözden geçirin.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <SectionTitle icon={AlertCircle} title="Tutumlar" desc="En az konu ve metni olan satırlar listelenir." />
              {payload.stances?.length ? (
                renderSummaryList(
                  payload.stances.map((stance) => `${stance.topic}: ${stance.stance_text}${
                    stance.confidence !== undefined ? ` (güven ${stance.confidence})` : ""
                  }`)
                )
              ) : (
                <p className="text-sm text-muted-foreground">Tanımlı tutum yok.</p>
              )}
            </div>
            <div>
              <SectionTitle icon={CheckCircle2} title="Pozisyonlar" desc="Opsiyonel hikâye amaçlı pozisyonlar." />
              {payload.holdings?.length ? (
                renderSummaryList(
                  payload.holdings.map((holding) => `${holding.symbol} · ${holding.size || "-"} @ ${holding.avg_price || "-"}${
                    holding.note ? ` — ${holding.note}` : ""
                  }`)
                )
              ) : (
                <p className="text-sm text-muted-foreground">Tanımlı pozisyon yok.</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  };

  const autosaveStatus = autosaveState.status;
  const autosaveSavedAt = autosaveState.savedAt;
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === wizardSteps.length - 1;
  const currentStepId = wizardSteps[currentStep].id;
  const currentAssessment = stepAssessments[currentStepId];
  const assessmentHighlights = currentAssessment?.highlights ?? [];
  const currentAssessmentMeta = useMemo(() => {
    if (!currentAssessment) {
      return null;
    }
    if (currentAssessment.ok) {
      return {
        icon: CheckCircle2,
        className: "border-emerald-200 bg-emerald-50 text-emerald-700",
        label: tf("wizard.feedback.ready", "Adım hazır")
      };
    }
    if (currentAssessment.severity === "error") {
      return {
        icon: AlertCircle,
        className: "border-amber-200 bg-amber-50 text-amber-700",
        label: tf("wizard.feedback.review", "Kontrol gerekli")
      };
    }
    return {
      icon: Circle,
      className: "border-border bg-muted/40 text-muted-foreground",
      label: tf("wizard.feedback.pending", "Bilgi bekleniyor")
    };
  }, [currentAssessment, tf]);

  const renderStepContent = () => {
    switch (wizardSteps[currentStep].id) {
      case "bot-chat":
        return renderBotChatStep();
      case "persona":
        return renderPersonaStep();
      case "stances":
        return renderStancesStep();
      case "summary":
        return renderSummaryStep();
      default:
        return null;
    }
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Wand2 className="h-6 w-6 text-primary" />
          <div>
            <h2 className="text-2xl font-semibold">{tf("wizard.title", "Kurulum (Wizard)")}</h2>
            <p className="text-sm text-muted-foreground">
              {tf("wizard.subtitle", "Adım adım botunuzu piyasaya hazırlayın.")}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <AutosaveBadge status={autosaveStatus} savedAt={autosaveSavedAt} tf={tf} locale={locale} />
          <Button type="button" size="sm" variant="ghost" className="h-8 px-2 text-xs" onClick={clearDraft}>
            <RotateCcw className="h-3.5 w-3.5 mr-1" />
            {tf("wizard.actions.clearDraft", "Taslağı temizle")}
          </Button>
          <div className="flex items-center gap-2">
            <Badge variant={simActive ? "default" : "secondary"}>
              {simActive
                ? tf("wizard.simulation.active", "Simülasyon: Aktif")
                : tf("wizard.simulation.inactive", "Simülasyon: Kapalı")}
            </Badge>
            <Button onClick={toggleSimulation} variant={simActive ? "destructive" : "default"} size="sm">
              {simActive ? (
                <>
                  <Pause className="h-4 w-4 mr-1" /> Durdur
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 mr-1" /> Başlat
                </>
              )}
            </Button>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            <Gauge className="h-5 w-5" /> Hız / Ölçek
          </CardTitle>
          <CardDescription>Mesaj üretim hızını ayarlayın. 1.0 = varsayılan.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            <TextInput
              label="Ölçek (factor)"
              type="number"
              step="0.1"
              min="0.1"
              value={scale}
              onChange={(e) => setScale(e.target.value)}
              style={{ maxWidth: 160 }}
            />
            <Button type="button" onClick={applyScale}>
              Uygula
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-4">
          <CardTitle>Kurulum Adımları</CardTitle>
          <CardDescription>Her adımı tamamladıkça sonraki adıma geçebilirsiniz.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-3">
            <Progress value={progressValue} className="h-2" />
            <ol className="flex flex-wrap gap-2">
              {wizardSteps.map((step, index) => {
                const isActive = index === currentStep;
                const isCompleted = index < currentStep;
                return (
                  <li key={step.id}>
                    <button
                      type="button"
                      onClick={() => handleStepClick(index)}
                      disabled={!isCompleted}
                      className={`px-3 py-1 rounded-full text-sm border transition ${
                        isActive
                          ? "bg-primary text-primary-foreground border-primary"
                          : isCompleted
                          ? "bg-muted border-border hover:bg-muted/70"
                          : "border-dashed border-border text-muted-foreground cursor-not-allowed"
                      }`}
                    >
                      {step.title}
                    </button>
                  </li>
                );
              })}
            </ol>
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_260px]">
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-semibold">{wizardSteps[currentStep].title}</h3>
                <p className="text-sm text-muted-foreground">{wizardSteps[currentStep].description}</p>
              </div>
              {renderStepContent()}
            </div>
            <aside className="space-y-4">
              <Card className="border-dashed border-border">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Adım Durumları</CardTitle>
                  <CardDescription>Hangi adımların hazır olduğunu takip edin.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {wizardSteps.map((step) => {
                    const assessment = stepAssessments[step.id] ?? { ok: false };
                    const Icon = assessment.ok ? CheckCircle2 : step.id === currentStepId ? AlertCircle : Circle;
                    const iconClass = assessment.ok
                      ? "text-emerald-600"
                      : assessment.severity === "error"
                      ? "text-amber-600"
                      : "text-muted-foreground";
                    return (
                      <div key={step.id} className="flex items-start gap-3">
                        <Icon className={`h-4 w-4 mt-1 ${iconClass}`} />
                        <div>
                          <div className="text-sm font-medium">{step.title}</div>
                          <p className="text-xs text-muted-foreground">
                            {assessment.message || "Bu adım için henüz bilgi yok."}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
              <Card className="border-primary/40 bg-primary/5">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{wizardSteps[currentStep].title} Özeti</CardTitle>
                  <CardDescription>Formu doldururken önemli noktaları gözden geçirin.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {currentAssessmentMeta && (
                    <Badge variant="outline" className={`flex items-center gap-1 text-xs ${currentAssessmentMeta.className}`}>
                      <currentAssessmentMeta.icon className="h-3.5 w-3.5" />
                      {currentAssessmentMeta.label}
                    </Badge>
                  )}
                  <p className="text-sm font-medium text-primary">
                    {currentAssessment?.message || "Bu adım için ilerleme bekleniyor."}
                  </p>
                  <ul className="text-xs text-muted-foreground space-y-1">
                    {assessmentHighlights.length > 0 ? (
                      assessmentHighlights.map((highlight, index) => <li key={index}>{highlight}</li>)
                    ) : (
                      <li>Henüz öne çıkan veri yok.</li>
                    )}
                  </ul>
                </CardContent>
              </Card>
            </aside>
          </div>
        </CardContent>
        <CardContent className="border-t bg-muted/40">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="text-sm text-muted-foreground">
              {stepError && <span className="text-red-600">{stepError}</span>}
              {!stepError && wizardSteps[currentStep].id !== "summary" && (
                <span>Devam etmeden önce bu adımı kontrol edin.</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" onClick={handlePrev} disabled={isFirstStep}>
                <ArrowLeft className="h-4 w-4 mr-1" /> Geri
              </Button>
              {isLastStep ? (
                <Button type="submit" disabled={submitting}>
                  {submitting ? "Gönderiliyor…" : "Kaydet ve Kur"}
                </Button>
              ) : (
                <Button type="button" onClick={handleNext}>
                  İleri <ArrowRight className="h-4 w-4 ml-1" />
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {message && (
        <Card>
          <CardContent>
            <div className={`text-sm ${message.type === "error" ? "text-red-600" : "text-green-600"}`}>
              {message.text}
            </div>
          </CardContent>
        </Card>
      )}
    </form>
  );
}
