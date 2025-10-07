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
  AlertCircle
} from "lucide-react";

import { apiFetch } from "../apiClient";

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

export default function Wizard({ onDone }) {
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
  const [autosaveStatus, setAutosaveStatus] = useState("saved");
  const autosaveTimeoutRef = useRef(null);
  const [wizardLoaded, setWizardLoaded] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);

  const wizardSteps = useMemo(
    () => [
      { id: "bot-chat", title: "Bot & Sohbet", description: "Kimlik ve bağlantı ayarlarını yapılandırın." },
      { id: "persona", title: "Persona & Duygu", description: "Üslup ve empati ayarlarını belirleyin." },
      { id: "stances", title: "Tutumlar & Pozisyonlar", description: "Opsiyonel strateji ve portföy notları." },
      { id: "summary", title: "Özet & Yayınla", description: "Kurulumu tamamlamadan önce son kontrol." }
    ],
    []
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
    setAutosaveStatus("saving");
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
    autosaveTimeoutRef.current = window.setTimeout(() => {
      setAutosaveStatus("saved");
    }, 600);
    return () => {
      if (autosaveTimeoutRef.current) {
        window.clearTimeout(autosaveTimeoutRef.current);
      }
    };
  }, [bot, chat, persona, emotion, stances, holdings, simActive, scale, currentStep, wizardLoaded]);

  const progressValue = Math.round((currentStep / Math.max(wizardSteps.length - 1, 1)) * 100);

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

  // --- helpers to mutate arrays
  const addStance = () => setStances((arr) => [...arr, { topic: "", stance_text: "", confidence: "", cooldown_until: "" }]);
  const removeStance = () => setStances((arr) => (arr.length > 0 ? arr.slice(0, -1) : arr));
  const addHolding = () => setHoldings((arr) => [...arr, { symbol: "", avg_price: "", size: "", note: "" }]);
  const removeHolding = () => setHoldings((arr) => (arr.length > 0 ? arr.slice(0, -1) : arr));

  const validateBotChatStep = () => {
    const name = bot.name.trim();
    const token = bot.token.trim();
    const chatId = chat.chat_id.trim();
    if (!name) {
      setStepError("Bot adı zorunludur.");
      return false;
    }
    if (!token) {
      setStepError("Bot token zorunludur.");
      return false;
    }
    if (!BOT_TOKEN_PATTERN.test(token)) {
      setStepError("Bot token formatı hatalı görünüyor.");
      return false;
    }
    if (!chatId) {
      setStepError("Chat ID zorunludur.");
      return false;
    }
    if (!CHAT_ID_PATTERN.test(chatId)) {
      setStepError("Chat ID formatını kontrol edin.");
      return false;
    }
    setStepError("");
    return true;
  };

  const validatePersonaStep = () => {
    if (!persona.tone.trim()) {
      setStepError("Persona üslup alanı boş bırakılamaz.");
      return false;
    }
    if (!emotion.empathy.trim()) {
      setStepError("Empati yaklaşımı tanımlanmalıdır.");
      return false;
    }
    if (!emotion.tone.trim()) {
      setStepError("Duygu tonu boş bırakılamaz.");
      return false;
    }
    setStepError("");
    return true;
  };

  const validateStancesStep = () => {
    for (const stance of stances) {
      const hasAny = stance.topic || stance.stance_text || stance.confidence !== "" || stance.cooldown_until;
      if (hasAny) {
        if (!stance.topic?.trim() || !stance.stance_text?.trim()) {
          setStepError("Her tutum için konu ve açıklama birlikte girilmelidir.");
          return false;
        }
        if (stance.confidence !== "") {
          const confidenceNumber = Number(stance.confidence);
          if (!Number.isFinite(confidenceNumber) || confidenceNumber < 0 || confidenceNumber > 1) {
            setStepError("Güven değeri 0 ile 1 arasında olmalıdır.");
            return false;
          }
        }
      }
    }
    for (const holding of holdings) {
      const hasAny = holding.symbol || holding.avg_price !== "" || holding.size !== "" || holding.note;
      if (hasAny && !holding.symbol?.trim()) {
        setStepError("Pozisyon satırları sembol ile başlamalıdır.");
        return false;
      }
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

  const autosaveLabel = autosaveStatus === "saving" ? "Taslak kaydediliyor…" : "Taslak güncel";
  const autosaveVariant = autosaveStatus === "saving" ? "secondary" : "outline";
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === wizardSteps.length - 1;

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
            <h2 className="text-2xl font-semibold">Kurulum (Wizard)</h2>
            <p className="text-sm text-muted-foreground">Adım adım botunuzu piyasaya hazırlayın.</p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <Badge variant={autosaveVariant}>{autosaveLabel}</Badge>
          <div className="flex items-center gap-2">
            <Badge variant={simActive ? "default" : "secondary"}>
              {simActive ? "Simülasyon: Aktif" : "Simülasyon: Kapalı"}
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

          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold">{wizardSteps[currentStep].title}</h3>
              <p className="text-sm text-muted-foreground">{wizardSteps[currentStep].description}</p>
            </div>
            {renderStepContent()}
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
