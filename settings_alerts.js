import { Mail, Smartphone, Bell } from 'lucide-react';

export const DEFAULT_MESSAGE_LENGTH_PROFILE = { short: 0.55, medium: 0.35, long: 0.10 };

export const ALERT_CHANNEL_DEFINITIONS = [
  { id: 'email', labelKey: 'settings.alerts.channels.email', fallbackLabel: 'E-posta', icon: Mail },
  { id: 'sms', labelKey: 'settings.alerts.channels.sms', fallbackLabel: 'SMS', icon: Smartphone },
  { id: 'push', labelKey: 'settings.alerts.channels.push', fallbackLabel: 'Push', icon: Bell }
];

export const ALERT_METRIC_DEFINITIONS = [
  {
    id: 'latency',
    labelKey: 'settings.alerts.metrics.latency.label',
    fallbackLabel: 'LLM Yanıt Süresi',
    descriptionKey: 'settings.alerts.metrics.latency.description',
    fallbackDescription: 'Son 5 dakikadaki ortalama yanıt süresi.',
    unitKey: 'settings.alerts.metrics.latency.unit',
    fallbackUnit: 'sn',
    warningDefault: 1.5,
    criticalDefault: 2.5,
    recommendedChannels: ['email', 'push']
  },
  {
    id: 'errorRate',
    labelKey: 'settings.alerts.metrics.errorRate.label',
    fallbackLabel: 'API Hata Oranı',
    descriptionKey: 'settings.alerts.metrics.errorRate.description',
    fallbackDescription: 'Başarısız istek yüzdesi.',
    unitKey: 'settings.alerts.metrics.errorRate.unit',
    fallbackUnit: '%',
    warningDefault: 3,
    criticalDefault: 6,
    recommendedChannels: ['email', 'sms']
  },
  {
    id: 'drawdown',
    labelKey: 'settings.alerts.metrics.drawdown.label',
    fallbackLabel: 'Portföy Gerilemesi',
    descriptionKey: 'settings.alerts.metrics.drawdown.description',
    fallbackDescription: 'Aktif bot portföyündeki maksimum düşüş.',
    unitKey: 'settings.alerts.metrics.drawdown.unit',
    fallbackUnit: '%',
    warningDefault: 5,
    criticalDefault: 10,
    recommendedChannels: ['sms', 'push']
  }
];

export function createAlertChannelOptions(translate) {
  const translator = translate || ((_, fallback) => fallback);
  return ALERT_CHANNEL_DEFINITIONS.map(channel => ({
    ...channel,
    label: translator(channel.labelKey, channel.fallbackLabel)
  }));
}

export function createDefaultAlertMetrics(translate, channelOptions = ALERT_CHANNEL_DEFINITIONS) {
  const translator = translate || ((_, fallback) => fallback);
  const availableChannelIds = new Set((channelOptions || []).map(channel => channel.id));

  return ALERT_METRIC_DEFINITIONS.map(metric => ({
    ...metric,
    label: translator(metric.labelKey, metric.fallbackLabel),
    description: translator(metric.descriptionKey, metric.fallbackDescription),
    unit: translator(metric.unitKey, metric.fallbackUnit),
    recommendedChannels: Array.isArray(metric.recommendedChannels)
      ? metric.recommendedChannels.filter(channel => availableChannelIds.has(channel))
      : []
  }));
}

const DEFAULT_ALERT_DESTINATIONS = {
  email: [],
  sms: [],
  push: []
};

function parseListString(value) {
  if (!value) {
    return [];
  }
  return String(value)
    .split(/\r?\n|,/)
    .map(item => item.trim())
    .filter(Boolean);
}

export function normalizeAlertPreferences(
  rawPreferences,
  baselineMetrics = ALERT_METRIC_DEFINITIONS,
  availableChannels = ALERT_CHANNEL_DEFINITIONS
) {
  const channelIds = new Set((availableChannels || []).map(channel => channel.id));

  const baseline = (baselineMetrics && baselineMetrics.length ? baselineMetrics : ALERT_METRIC_DEFINITIONS).map(metric => ({
    ...metric,
    label: metric.label ?? metric.fallbackLabel,
    description: metric.description ?? metric.fallbackDescription,
    unit: metric.unit ?? metric.fallbackUnit,
    warningDefault: metric.warningDefault,
    criticalDefault: metric.criticalDefault,
    recommendedChannels: Array.isArray(metric.recommendedChannels)
      ? [...metric.recommendedChannels]
      : [],
    warning: String(metric.warningDefault),
    critical: String(metric.criticalDefault),
    channels: Array.isArray(metric.recommendedChannels) ? [...metric.recommendedChannels] : []
  }));

  if (!Array.isArray(rawPreferences)) {
    return baseline;
  }

  return baseline.map(metric => {
    const incoming = rawPreferences.find(item => item.id === metric.id) ?? {};
    const warningValue = toNumber(incoming.warning, metric.warningDefault);
    const criticalValue = toNumber(incoming.critical, metric.criticalDefault);
    const channels = Array.isArray(incoming.channels)
      ? incoming.channels.filter(channel => channelIds.has(channel))
      : metric.recommendedChannels;
    const label =
      typeof incoming.label === 'string' && incoming.label.trim()
        ? incoming.label
        : metric.label ?? metric.fallbackLabel;
    const description =
      typeof incoming.description === 'string' && incoming.description.trim()
        ? incoming.description
        : metric.description ?? metric.fallbackDescription;
    const unit =
      typeof incoming.unit === 'string' && incoming.unit.trim()
        ? incoming.unit
        : metric.unit ?? metric.fallbackUnit;

    return {
      ...metric,
      label,
      description,
      unit,
      warning: String(warningValue),
      critical: String(criticalValue),
      channels: channels.length > 0 ? channels : [...metric.recommendedChannels]
    };
  });
}

export function normalizeAlertDestinations(rawDestinations) {
  const normalized = {
    email: [...DEFAULT_ALERT_DESTINATIONS.email],
    sms: [...DEFAULT_ALERT_DESTINATIONS.sms],
    push: [...DEFAULT_ALERT_DESTINATIONS.push]
  };

  if (!rawDestinations || typeof rawDestinations !== 'object') {
    return normalized;
  }

  Object.keys(normalized).forEach(key => {
    const value = rawDestinations[key];
    if (Array.isArray(value)) {
      normalized[key] = value.map(item => String(item).trim()).filter(Boolean);
    } else if (typeof value === 'string') {
      normalized[key] = parseListString(value);
    }
  });

  return normalized;
}

export function formatAlertDestinations(rawDestinations = DEFAULT_ALERT_DESTINATIONS) {
  const normalized = normalizeAlertDestinations(rawDestinations);
  return {
    email: normalized.email.join('\n'),
    sms: normalized.sms.join('\n'),
    push: normalized.push.join('\n')
  };
}

export function parseAlertDestinationsInput(formState) {
  return {
    email: parseListString(formState.email),
    sms: parseListString(formState.sms),
    push: parseListString(formState.push)
  };
}

export function normalizeMessageLengthProfile(rawProfile) {
  const base = { ...DEFAULT_MESSAGE_LENGTH_PROFILE };
  if (rawProfile && typeof rawProfile === 'object') {
    Object.entries(rawProfile).forEach(([key, value]) => {
      if (!(key in base)) {
        return;
      }
      const parsed = Number.parseFloat(value);
      if (Number.isFinite(parsed) && parsed >= 0) {
        base[key] = parsed;
      }
    });
  }

  const total = Object.values(base).reduce((sum, val) => sum + val, 0);
  if (total <= 0) {
    return { ...DEFAULT_MESSAGE_LENGTH_PROFILE };
  }

  const normalized = Object.fromEntries(
    Object.entries(base).map(([key, val]) => [key, val / total])
  );
  const sumNormalized = Object.values(normalized).reduce((sum, val) => sum + val, 0);
  const residue = 1 - sumNormalized;
  const keys = Object.keys(DEFAULT_MESSAGE_LENGTH_PROFILE);
  const lastKey = keys[keys.length - 1];
  normalized[lastKey] = Math.max(0, normalized[lastKey] + residue);
  return normalized;
}

export function toNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function buildThresholdSummary(metric, translate) {
  if (!metric || typeof metric !== 'object') {
    return '';
  }
  const translator = translate || ((_, fallback) => fallback);
  const warningLabel = translator('settings.alerts.summary.warningLabel', 'Uyarı');
  const criticalLabel = translator('settings.alerts.summary.criticalLabel', 'Kritik');
  const unit = metric.unit || metric.fallbackUnit || '';
  const unitSuffix = unit ? ` ${unit}` : '';
  const warningValue = metric.warning ?? metric.warningDefault ?? '';
  const criticalValue = metric.critical ?? metric.criticalDefault ?? '';
  return `${warningLabel} ${warningValue}${unitSuffix}, ${criticalLabel} ${criticalValue}${unitSuffix}`.trim();
}

export function summarizeAlertChannels(preferences, channelOptions = ALERT_CHANNEL_DEFINITIONS, translate) {
  const translator = translate || ((_, fallback) => fallback);
  const normalizedChannels = (channelOptions || []).map(channel => ({
    ...channel,
    label: channel.label ?? translator(channel.labelKey, channel.fallbackLabel)
  }));

  if (!Array.isArray(preferences)) {
    return normalizedChannels.map(channel => ({ ...channel, metrics: [] }));
  }

  return normalizedChannels.map(channel => {
    const metrics = preferences
      .filter(metric => Array.isArray(metric.channels) && metric.channels.includes(channel.id))
      .map(metric => ({
        ...metric,
        summary: buildThresholdSummary(metric, translator)
      }));
    return { ...channel, metrics };
  });
}
