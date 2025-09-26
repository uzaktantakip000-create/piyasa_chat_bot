import React, { useMemo, useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Play, Pause, Wand2, Plus, Trash2, Gauge } from "lucide-react";

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

export default function Wizard({ onDone }) {
  const [simActive, setSimActive] = useState(false);
  const [scale, setScale] = useState(1.0);

  // --- BOT ---
  const [bot, setBot] = useState({
    name: "",
    token: "",
    username: "",
    is_enabled: true,
  });

  // --- CHAT ---
  const [chat, setChat] = useState({
    chat_id: "",
    title: "",
    topics: "BIST,FX,Kripto,Makro",
  });

  // --- PERSONA ---
  const [persona, setPersona] = useState({
    tone: "samimi ama profesyonel",
    risk_profile: "orta",
    watchlist: "BIST:AKBNK,XAUUSD,BTCUSDT",
    never_do: "garanti kazanç vaadi,kaynaksız kesin rakam",
    emojis: true,
    length: "kısa-orta",
    disclaimer: "yatırım tavsiyesi değildir",
  });

  // --- STANCES ---
  const [stances, setStances] = useState([
    { topic: "Bankacılık", stance_text: "Orta vadede temkinli; geri çekilmeler kademeli fırsat.", confidence: 0.7, cooldown_until: "" },
    { topic: "Kripto", stance_text: "Kısa vadede volatil; uzun vadede seçici iyimser.", confidence: 0.6, cooldown_until: "" },
  ]);

  // --- HOLDINGS ---
  const [holdings, setHoldings] = useState([
    { symbol: "BIST:AKBNK", avg_price: "63.4", size: "120", note: "uzun vade çekirdek pozisyon" },
  ]);

  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);

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
      stances: stanceBody.length ? stanceBody : undefined,
      holdings: holdingBody.length ? holdingBody : undefined,
      start_simulation: simActive,
    };
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setMessage(null);

    const payload = buildPayload();
    if (!payload.bot.name || !payload.bot.token || !payload.chat.chat_id) {
      setMessage({ type: "error", text: "Bot adı, Bot token ve Chat ID zorunludur." });
      return;
    }

    setSubmitting(true);
    try {
      const r = await apiFetch("/wizard/setup", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const data = await r.json().catch(() => ({}));
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

  // --- helpers to mutate arrays
  const addStance = () => setStances((arr) => [...arr, { topic: "", stance_text: "", confidence: "", cooldown_until: "" }]);
  const removeStance = () => setStances((arr) => (arr.length > 0 ? arr.slice(0, -1) : arr));
  const addHolding = () => setHoldings((arr) => [...arr, { symbol: "", avg_price: "", size: "", note: "" }]);
  const removeHolding = () => setHoldings((arr) => (arr.length > 0 ? arr.slice(0, -1) : arr));

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-semibold flex items-center gap-2">
          <Wand2 className="h-6 w-6 text-primary" />
          Kurulum (Wizard)
        </h2>
        <div className="flex items-center gap-2">
          <Badge variant={simActive ? "default" : "secondary"}>
            {simActive ? "Simülasyon: Aktif" : "Simülasyon: Kapalı"}
          </Badge>
          <Button onClick={toggleSimulation} variant={simActive ? "destructive" : "default"} size="sm">
            {simActive ? <><Pause className="h-4 w-4 mr-1" /> Durdur</> : <><Play className="h-4 w-4 mr-1" /> Başlat</>}
          </Button>
        </div>
      </div>

      {/* SCALE */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2"><Gauge className="h-5 w-5" /> Hız / Ölçek</CardTitle>
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
            <Button type="button" onClick={applyScale}>Uygula</Button>
          </div>
        </CardContent>
      </Card>

      {/* FORM */}
      <form onSubmit={handleSubmit}>
        <div className="grid md:grid-cols-2 gap-6">
          {/* BOT */}
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

          {/* CHAT */}
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

        {/* PERSONA */}
        <Card className="mt-6">
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

        {/* STANCES */}
        <Card className="mt-6">
          <CardHeader className="pb-3">
            <CardTitle>Tutumlar (Stances)</CardTitle>
            <CardDescription>Botun konu bazlı kanaatleri.</CardDescription>
          </CardHeader>
          <CardContent>
            {stances.map((s, idx) => (
              <div key={idx} className="grid md:grid-cols-4 gap-3 mb-4">
                <TextInput label="Konu" placeholder="Bankacılık" value={s.topic} onChange={(e) => {
                  const v = e.target.value; setStances((arr) => arr.map((x, i) => i === idx ? { ...x, topic: v } : x));
                }} />
                <TextInput label="Güven (0-1)" type="number" step="0.1" value={s.confidence} onChange={(e) => {
                  const v = e.target.value; setStances((arr) => arr.map((x, i) => i === idx ? { ...x, confidence: v } : x));
                }} />
                <TextInput label="Cooldown Bitişi" type="datetime-local" value={s.cooldown_until} onChange={(e) => {
                  const v = e.target.value; setStances((arr) => arr.map((x, i) => i === idx ? { ...x, cooldown_until: v } : x));
                }} />
                <TextArea label="Tutum Metni" rows={2} value={s.stance_text} onChange={(e) => {
                  const v = e.target.value; setStances((arr) => arr.map((x, i) => i === idx ? { ...x, stance_text: v } : x));
                }} />
              </div>
            ))}
            <RowActions onAdd={addStance} onRemove={removeStance} canRemove={stances.length > 0} />
          </CardContent>
        </Card>

        {/* HOLDINGS */}
        <Card className="mt-6">
          <CardHeader className="pb-3">
            <CardTitle>Pozisyonlar (Holdings)</CardTitle>
            <CardDescription>Hikâye amaçlı örnek pozisyonlar (opsiyonel).</CardDescription>
          </CardHeader>
          <CardContent>
            {holdings.map((h, idx) => (
              <div key={idx} className="grid md:grid-cols-4 gap-3 mb-4">
                <TextInput label="Sembol" placeholder="BIST:AKBNK" value={h.symbol} onChange={(e) => {
                  const v = e.target.value; setHoldings((arr) => arr.map((x, i) => i === idx ? { ...x, symbol: v } : x));
                }} />
                <TextInput label="Ortalama Maliyet" type="number" step="0.0001" value={h.avg_price} onChange={(e) => {
                  const v = e.target.value; setHoldings((arr) => arr.map((x, i) => i === idx ? { ...x, avg_price: v } : x));
                }} />
                <TextInput label="Adet/Lot" type="number" step="0.01" value={h.size} onChange={(e) => {
                  const v = e.target.value; setHoldings((arr) => arr.map((x, i) => i === idx ? { ...x, size: v } : x));
                }} />
                <TextInput label="Not" placeholder="uzun vade" value={h.note} onChange={(e) => {
                  const v = e.target.value; setHoldings((arr) => arr.map((x, i) => i === idx ? { ...x, note: v } : x));
                }} />
              </div>
            ))}
            <RowActions onAdd={addHolding} onRemove={removeHolding} canRemove={holdings.length > 0} />
          </CardContent>
        </Card>

        {/* SUBMIT */}
        <div className="flex items-center justify-between mt-6">
          <div>
            {message && (
              <div className={`text-sm ${message.type === "error" ? "text-red-600" : "text-green-600"}`}>
                {message.text}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button type="submit" disabled={submitting}>
              {submitting ? "Gönderiliyor…" : "Kaydet ve Kur"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
