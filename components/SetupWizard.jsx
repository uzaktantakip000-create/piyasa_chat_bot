import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  Loader2,
  Key,
  User,
  Sparkles,
  Server,
} from "lucide-react";
import { apiFetch } from "../apiClient";

/**
 * SetupWizard - Initial system setup wizard
 *
 * 3-step process:
 * 1. LLM Provider selection + API key
 * 2. Admin user creation
 * 3. Finish + redirect to dashboard
 */
export default function SetupWizard({ onComplete }) {
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [validating, setValidating] = useState(false);

  // Step 1: LLM Provider
  const [llmProvider, setLlmProvider] = useState("groq"); // groq as default (free)
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmModel, setLlmModel] = useState("");
  const [keyValid, setKeyValid] = useState(null);

  // Step 2: Admin User
  const [adminUsername, setAdminUsername] = useState("admin");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminPasswordConfirm, setAdminPasswordConfirm] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [enableMfa, setEnableMfa] = useState(false);

  const totalSteps = 3;
  const progress = (currentStep / totalSteps) * 100;

  // LLM Provider options
  const llmProviders = [
    {
      id: "groq",
      name: "Groq",
      description: "ÜCRETSİZ ve ÇOK HIZLI! (llama-3.3-70b-versatile)",
      defaultModel: "llama-3.3-70b-versatile",
      keyPrefix: "gsk_",
      recommended: true,
    },
    {
      id: "openai",
      name: "OpenAI",
      description: "GPT-4 modelleri (ücretli)",
      defaultModel: "gpt-4o-mini",
      keyPrefix: "sk-",
    },
    {
      id: "gemini",
      name: "Google Gemini",
      description: "Gemini modelleri (ücretsiz tier mevcut)",
      defaultModel: "gemini-pro",
      keyPrefix: "AIza",
    },
  ];

  // Set default model when provider changes
  useEffect(() => {
    const provider = llmProviders.find((p) => p.id === llmProvider);
    if (provider && !llmModel) {
      setLlmModel(provider.defaultModel);
    }
  }, [llmProvider]);

  // Validate API key format
  const validateApiKey = async () => {
    if (!llmApiKey || llmApiKey.length < 10) {
      setError("API key çok kısa");
      return false;
    }

    const provider = llmProviders.find((p) => p.id === llmProvider);
    if (provider && provider.keyPrefix && !llmApiKey.startsWith(provider.keyPrefix)) {
      setError(`${provider.name} API key'i "${provider.keyPrefix}" ile başlamalı`);
      return false;
    }

    return true;
  };

  // Password validation
  const validatePassword = () => {
    if (adminPassword.length < 12) {
      setError("Şifre en az 12 karakter olmalı");
      return false;
    }

    if (!/[A-Z]/.test(adminPassword)) {
      setError("Şifre en az 1 büyük harf içermeli");
      return false;
    }

    if (!/[a-z]/.test(adminPassword)) {
      setError("Şifre en az 1 küçük harf içermeli");
      return false;
    }

    if (!/[0-9]/.test(adminPassword)) {
      setError("Şifre en az 1 rakam içermeli");
      return false;
    }

    if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>/?]/.test(adminPassword)) {
      setError("Şifre en az 1 özel karakter içermeli");
      return false;
    }

    if (adminPassword !== adminPasswordConfirm) {
      setError("Şifreler eşleşmiyor");
      return false;
    }

    return true;
  };

  // Handle next step
  const handleNext = async () => {
    setError(null);

    if (currentStep === 1) {
      const valid = await validateApiKey();
      if (!valid) return;
      setCurrentStep(2);
    } else if (currentStep === 2) {
      if (!validatePassword()) return;
      setCurrentStep(3);
    }
  };

  // Handle previous step
  const handlePrevious = () => {
    setError(null);
    setCurrentStep(currentStep - 1);
  };

  // Handle final setup
  const handleFinish = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiFetch("/api/setup/init", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          llm_provider: llmProvider,
          llm_api_key: llmApiKey,
          llm_model: llmModel,
          admin_username: adminUsername,
          admin_password: adminPassword,
          admin_email: adminEmail,
          enable_mfa: enableMfa,
        }),
      });

      if (response.success) {
        // Reload .env variables (server side)
        // Redirect to login or dashboard
        if (onComplete) {
          onComplete(response);
        } else {
          window.location.href = "/";
        }
      } else {
        setError(response.message || "Setup başarısız oldu");
      }
    } catch (err) {
      console.error("Setup error:", err);
      setError(err.message || "Setup sırasında hata oluştu");
    } finally {
      setLoading(false);
    }
  };

  // Render step content
  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">LLM Provider Seçin</label>
              <div className="space-y-2">
                {llmProviders.map((provider) => (
                  <div
                    key={provider.id}
                    onClick={() => setLlmProvider(provider.id)}
                    className={`p-4 border rounded-lg cursor-pointer transition-all ${
                      llmProvider === provider.id
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50"
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{provider.name}</span>
                          {provider.recommended && (
                            <Badge variant="outline" className="text-xs bg-green-50 text-green-700 border-green-200">
                              Önerilen
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">{provider.description}</p>
                      </div>
                      <div
                        className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                          llmProvider === provider.id
                            ? "border-primary bg-primary"
                            : "border-border"
                        }`}
                      >
                        {llmProvider === provider.id && (
                          <div className="w-2 h-2 rounded-full bg-white" />
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                API Key
                <span className="text-muted-foreground text-xs ml-2">
                  ({llmProviders.find((p) => p.id === llmProvider)?.keyPrefix}... ile başlamalı)
                </span>
              </label>
              <div className="relative">
                <Key className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="password"
                  value={llmApiKey}
                  onChange={(e) => setLlmApiKey(e.target.value)}
                  placeholder="API key'inizi girin"
                  className="w-full pl-10 pr-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {llmProvider === "groq" && "Groq API key için: https://console.groq.com/keys"}
                {llmProvider === "openai" && "OpenAI API key için: https://platform.openai.com/api-keys"}
                {llmProvider === "gemini" && "Gemini API key için: https://aistudio.google.com/app/apikey"}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Model (İsteğe Bağlı)</label>
              <input
                type="text"
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                placeholder={llmProviders.find((p) => p.id === llmProvider)?.defaultModel}
                className="w-full px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Boş bırakırsanız varsayılan model kullanılır
              </p>
            </div>
          </div>
        );

      case 2:
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Kullanıcı Adı</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  value={adminUsername}
                  onChange={(e) => setAdminUsername(e.target.value)}
                  placeholder="admin"
                  className="w-full pl-10 pr-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Şifre (min. 12 karakter)</label>
              <input
                type="password"
                value={adminPassword}
                onChange={(e) => setAdminPassword(e.target.value)}
                placeholder="Güçlü bir şifre girin"
                className="w-full px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Büyük harf, küçük harf, rakam ve özel karakter içermeli
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Şifre Tekrar</label>
              <input
                type="password"
                value={adminPasswordConfirm}
                onChange={(e) => setAdminPasswordConfirm(e.target.value)}
                placeholder="Şifrenizi tekrar girin"
                className="w-full px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">E-posta (İsteğe Bağlı)</label>
              <input
                type="email"
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
                placeholder="admin@example.com"
                className="w-full px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="mfa"
                checked={enableMfa}
                onChange={(e) => setEnableMfa(e.target.checked)}
              />
              <label htmlFor="mfa" className="text-sm cursor-pointer">
                MFA (Multi-Factor Authentication) etkinleştir (önerilir)
              </label>
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-4">
            <div className="text-center py-8">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 mb-4">
                <CheckCircle2 className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Kurulum Hazır!</h3>
              <p className="text-muted-foreground mb-6">
                Sistem kurulumunuz tamamlanmak üzere. Aşağıdaki özeti kontrol edin.
              </p>

              <div className="bg-muted/50 rounded-lg p-4 text-left space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">LLM Provider:</span>
                  <span className="text-sm font-medium">{llmProviders.find((p) => p.id === llmProvider)?.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Model:</span>
                  <span className="text-sm font-medium">{llmModel || "Varsayılan"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Admin Kullanıcı:</span>
                  <span className="text-sm font-medium">{adminUsername}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">MFA:</span>
                  <span className="text-sm font-medium">{enableMfa ? "Etkin" : "Devre Dışı"}</span>
                </div>
              </div>

              <p className="text-xs text-muted-foreground mt-4">
                "Kurulumu Tamamla" butonuna tıkladıktan sonra sistem yapılandırılacak ve
                giriş ekranına yönlendirileceksiniz.
              </p>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted/20 p-4">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-primary/10">
              <Sparkles className="h-6 w-6 text-primary" />
            </div>
            <div>
              <CardTitle className="text-2xl">İlk Kurulum</CardTitle>
              <CardDescription>Sistemi kullanmaya başlamak için birkaç basit adım</CardDescription>
            </div>
          </div>

          {/* Progress bar */}
          <div className="mt-4">
            <div className="flex justify-between text-sm mb-2">
              <span className="text-muted-foreground">Adım {currentStep} / {totalSteps}</span>
              <span className="text-muted-foreground">%{Math.round(progress)}</span>
            </div>
            <Progress value={progress} className="h-2" />
          </div>

          {/* Step indicators */}
          <div className="flex items-center justify-between mt-4">
            {[
              { num: 1, label: "LLM Provider", icon: Server },
              { num: 2, label: "Admin User", icon: User },
              { num: 3, label: "Tamamla", icon: CheckCircle2 },
            ].map(({ num, label, icon: Icon }) => (
              <div key={num} className="flex flex-col items-center flex-1">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 ${
                    currentStep >= num
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <span className="text-xs text-center">{label}</span>
              </div>
            ))}
          </div>
        </CardHeader>

        <CardContent>
          {/* Error message */}
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 flex items-start gap-2">
              <AlertCircle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {/* Step content */}
          {renderStepContent()}

          {/* Navigation buttons */}
          <div className="flex justify-between mt-6 pt-6 border-t">
            <Button
              variant="outline"
              onClick={handlePrevious}
              disabled={currentStep === 1 || loading}
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Geri
            </Button>

            {currentStep < totalSteps ? (
              <Button onClick={handleNext} disabled={loading}>
                İleri
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            ) : (
              <Button onClick={handleFinish} disabled={loading}>
                {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Kurulumu Tamamla
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
