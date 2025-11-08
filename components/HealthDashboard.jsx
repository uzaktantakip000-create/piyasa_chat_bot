import React, { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Server,
  Database,
  Activity,
  HardDrive,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  Zap,
  Loader2,
  Download,
  FileText,
  FileJson,
} from "lucide-react";
import { apiFetch } from "../apiClient";

/**
 * HealthDashboard - Real-time system health monitoring
 *
 * Displays:
 * - API status (uptime, version)
 * - Worker status (last message, message count)
 * - Database status (connection, stats)
 * - Redis status (optional)
 * - Disk usage
 * - System alerts
 */
export default function HealthDashboard({ refreshInterval = 10000 }) {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchHealth = async () => {
    try {
      const response = await apiFetch("/api/system/health");
      setHealth(response);
      setLastUpdate(new Date());
      setLoading(false);
    } catch (error) {
      console.error("Failed to fetch health:", error);
      setLoading(false);
    }
  };

  // Initial fetch + auto-refresh
  useEffect(() => {
    fetchHealth();

    if (autoRefresh) {
      const interval = setInterval(fetchHealth, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refreshInterval]);

  // Manual refresh
  const handleRefresh = () => {
    setLoading(true);
    fetchHealth();
  };

  // Export handlers
  const handleExportCSV = async () => {
    try {
      const response = await fetch("/api/system/health/export/csv", {
        method: "GET",
        headers: {
          "X-API-Key": localStorage.getItem("api_key") || "",
        },
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `health_metrics_${new Date().toISOString().split("T")[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error("CSV export failed:", error);
    }
  };

  const handleExportJSON = async () => {
    try {
      const response = await fetch("/api/system/health/export/json", {
        method: "GET",
        headers: {
          "X-API-Key": localStorage.getItem("api_key") || "",
        },
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `health_metrics_${new Date().toISOString().split("T")[0]}.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error("JSON export failed:", error);
    }
  };

  // Status badge component
  const StatusBadge = ({ status }) => {
    const variants = {
      running: { icon: CheckCircle, color: "bg-green-100 text-green-700 border-green-200", label: "Çalışıyor" },
      active: { icon: CheckCircle, color: "bg-green-100 text-green-700 border-green-200", label: "Aktif" },
      connected: { icon: CheckCircle, color: "bg-green-100 text-green-700 border-green-200", label: "Bağlı" },
      healthy: { icon: CheckCircle, color: "bg-green-100 text-green-700 border-green-200", label: "Sağlıklı" },
      slow: { icon: Clock, color: "bg-yellow-100 text-yellow-700 border-yellow-200", label: "Yavaş" },
      idle: { icon: Clock, color: "bg-gray-100 text-gray-700 border-gray-200", label: "Beklemede" },
      unavailable: { icon: XCircle, color: "bg-gray-100 text-gray-700 border-gray-200", label: "Kullanılamıyor" },
      not_configured: { icon: XCircle, color: "bg-gray-100 text-gray-700 border-gray-200", label: "Yapılandırılmamış" },
      error: { icon: AlertTriangle, color: "bg-red-100 text-red-700 border-red-200", label: "Hata" },
      critical: { icon: AlertTriangle, color: "bg-red-100 text-red-700 border-red-200", label: "Kritik" },
    };

    const variant = variants[status] || variants.error;
    const Icon = variant.icon;

    return (
      <Badge variant="outline" className={`flex items-center gap-1 ${variant.color}`}>
        <Icon className="h-3 w-3" />
        {variant.label}
      </Badge>
    );
  };

  // Format uptime
  const formatUptime = (seconds) => {
    if (!seconds) return "Bilinmiyor";
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return `${hours}s ${minutes}d`;
    return `${minutes} dakika`;
  };

  // Format disk space
  const formatDiskSpace = (gb) => {
    if (!gb) return "0 GB";
    return `${gb.toFixed(1)} GB`;
  };

  if (loading && !health) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!health) {
    return (
      <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20 flex items-start gap-2">
        <AlertTriangle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm text-destructive font-medium">Sistem Durumu Alınamadı</p>
          <p className="text-xs text-destructive/70 mt-1">
            Health endpoint'e erişilemiyor. Lütfen API servisini kontrol edin.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with refresh button */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Sistem Durumu</h3>
          {lastUpdate && (
            <p className="text-xs text-muted-foreground">
              Son güncelleme: {lastUpdate.toLocaleTimeString("tr-TR")}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportCSV}
            title="CSV olarak indir"
          >
            <FileText className="h-4 w-4 mr-2" />
            CSV
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportJSON}
            title="JSON olarak indir"
          >
            <FileJson className="h-4 w-4 mr-2" />
            JSON
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Yenile
          </Button>
          <Button
            variant={autoRefresh ? "default" : "outline"}
            size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}
          >
            <Zap className="h-4 w-4 mr-2" />
            {autoRefresh ? "Otomatik" : "Manuel"}
          </Button>
        </div>
      </div>

      {/* System Alerts */}
      {health.alerts && health.alerts.length > 0 && (
        <div className="space-y-2">
          {health.alerts.map((alert, idx) => (
            <div
              key={idx}
              className={`p-3 rounded-lg border flex items-start gap-2 ${
                alert.severity === "critical"
                  ? "bg-red-50 border-red-200"
                  : "bg-yellow-50 border-yellow-200"
              }`}
            >
              <AlertTriangle
                className={`h-5 w-5 flex-shrink-0 mt-0.5 ${
                  alert.severity === "critical" ? "text-red-600" : "text-yellow-600"
                }`}
              />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-xs">
                    {alert.component}
                  </Badge>
                  <span className="text-xs text-muted-foreground">{alert.severity}</span>
                </div>
                <p className="text-sm mt-1">{alert.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Status Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* API Status */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-sm">API</CardTitle>
              </div>
              <StatusBadge status={health.api?.status || "error"} />
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {health.api?.uptime_seconds !== undefined && (
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Uptime:</span>
                <span className="font-medium">{formatUptime(health.api.uptime_seconds)}</span>
              </div>
            )}
            {health.api?.python_version && (
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Python:</span>
                <span className="font-medium">{health.api.python_version}</span>
              </div>
            )}
            {health.api?.error && (
              <p className="text-xs text-destructive">{health.api.error}</p>
            )}
          </CardContent>
        </Card>

        {/* Worker Status */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-sm">Worker</CardTitle>
              </div>
              <StatusBadge status={health.worker?.status || "error"} />
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {health.worker?.messages_last_hour !== undefined && (
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Son 1 saat:</span>
                <span className="font-medium">{health.worker.messages_last_hour} mesaj</span>
              </div>
            )}
            {health.worker?.last_message_age_seconds !== undefined && (
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Son mesaj:</span>
                <span className="font-medium">
                  {Math.floor(health.worker.last_message_age_seconds / 60)} dk önce
                </span>
              </div>
            )}
            {health.worker?.error && (
              <p className="text-xs text-destructive">{health.worker.error}</p>
            )}
          </CardContent>
        </Card>

        {/* Database Status */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-sm">Database</CardTitle>
              </div>
              <StatusBadge status={health.database?.status || "error"} />
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {health.database?.type && (
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Tip:</span>
                <span className="font-medium uppercase">{health.database.type}</span>
              </div>
            )}
            {health.database?.active_bots !== undefined && (
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Aktif bot:</span>
                <span className="font-medium">{health.database.active_bots}</span>
              </div>
            )}
            {health.database?.total_messages !== undefined && (
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Mesajlar:</span>
                <span className="font-medium">{health.database.total_messages.toLocaleString()}</span>
              </div>
            )}
            {health.database?.error && (
              <p className="text-xs text-destructive">{health.database.error}</p>
            )}
          </CardContent>
        </Card>

        {/* Disk Usage */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <HardDrive className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-sm">Disk</CardTitle>
              </div>
              {health.disk?.usage_percent !== undefined && (
                <Badge
                  variant="outline"
                  className={
                    health.disk.usage_percent > 90
                      ? "bg-red-100 text-red-700 border-red-200"
                      : health.disk.usage_percent > 80
                      ? "bg-yellow-100 text-yellow-700 border-yellow-200"
                      : "bg-green-100 text-green-700 border-green-200"
                  }
                >
                  {health.disk.usage_percent.toFixed(0)}%
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {health.disk?.free_gb !== undefined && (
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Boş alan:</span>
                <span className="font-medium">{formatDiskSpace(health.disk.free_gb)}</span>
              </div>
            )}
            {health.disk?.total_gb !== undefined && (
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Toplam:</span>
                <span className="font-medium">{formatDiskSpace(health.disk.total_gb)}</span>
              </div>
            )}
            {health.disk?.error && (
              <p className="text-xs text-destructive">{health.disk.error}</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Redis Status (if configured) */}
      {health.redis && health.redis.status !== "not_configured" && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-sm">Redis Cache</CardTitle>
              </div>
              <StatusBadge status={health.redis.status} />
            </div>
          </CardHeader>
          <CardContent>
            {health.redis.available ? (
              <p className="text-xs text-muted-foreground">Cache aktif ve çalışıyor</p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Redis kullanılamıyor (opsiyonel, sistem çalışmaya devam ediyor)
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Overall Status Summary */}
      <Card className={
        health.overall_status === "critical"
          ? "border-red-200 bg-red-50/50"
          : "border-green-200 bg-green-50/50"
      }>
        <CardHeader>
          <div className="flex items-center gap-2">
            {health.overall_status === "critical" ? (
              <AlertTriangle className="h-5 w-5 text-red-600" />
            ) : (
              <CheckCircle className="h-5 w-5 text-green-600" />
            )}
            <CardTitle className="text-base">
              {health.overall_status === "critical" ? "Kritik Sorun Tespit Edildi" : "Sistem Sağlıklı"}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {health.overall_status === "critical"
              ? "Yukarıdaki kritik uyarıları kontrol edin ve gerekli aksiyonları alın."
              : "Tüm sistem bileşenleri normal çalışıyor."}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
