import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createAlertChannelOptions,
  createDefaultAlertMetrics,
  normalizeAlertPreferences,
  normalizeAlertDestinations,
  formatAlertDestinations,
  parseAlertDestinationsInput,
  normalizeMessageLengthProfile,
  DEFAULT_MESSAGE_LENGTH_PROFILE,
  toNumber,
  buildThresholdSummary,
  summarizeAlertChannels
} from '../../settings_alerts.js';
import { translate, registerTranslations } from '../../translation_core.js';

const noopTranslate = (_, fallback) => fallback;

test('normalizeAlertPreferences combines defaults with stored values', () => {
  const channels = createAlertChannelOptions(noopTranslate);
  const metrics = createDefaultAlertMetrics(noopTranslate, channels);
  const input = [
    {
      id: metrics[0].id,
      warning: '2.1',
      critical: '3.2',
      channels: ['email'],
      label: 'Custom label',
      description: 'Custom description',
      unit: 'ms',
    },
  ];

  const normalized = normalizeAlertPreferences(input, metrics, channels);

  assert.equal(normalized.length, metrics.length);
  const first = normalized[0];
  assert.equal(first.label, 'Custom label');
  assert.equal(first.description, 'Custom description');
  assert.equal(first.unit, 'ms');
  assert.deepEqual(first.channels, ['email']);
  assert.equal(first.warning, '2.1');
  assert.equal(first.critical, '3.2');

  const second = normalized[1];
  assert.ok(second.channels.length > 0);
});

test('normalizeAlertPreferences enforces default channels when none provided', () => {
  const channels = createAlertChannelOptions(noopTranslate);
  const metrics = createDefaultAlertMetrics(noopTranslate, channels);
  const input = [
    {
      id: metrics[1].id,
      warning: 'not-a-number',
      critical: 'invalid',
      channels: [],
    },
  ];

  const normalized = normalizeAlertPreferences(input, metrics, channels);
  const target = normalized.find(metric => metric.id === metrics[1].id);
  assert.equal(target.warning, String(metrics[1].warningDefault));
  assert.equal(target.critical, String(metrics[1].criticalDefault));
  assert.deepEqual(target.channels, metrics[1].recommendedChannels);
});

test('alert destinations format, parse, and normalize consistently', () => {
  const incoming = {
    email: ['alpha@example.com', 'beta@example.com'],
    sms: '+905331112233\n+905331112244',
    push: '',
  };

  const normalized = normalizeAlertDestinations(incoming);
  assert.deepEqual(normalized.email, ['alpha@example.com', 'beta@example.com']);
  assert.deepEqual(normalized.sms, ['+905331112233', '+905331112244']);
  assert.deepEqual(normalized.push, []);

  const formatted = formatAlertDestinations(incoming);
  const parsed = parseAlertDestinationsInput(formatted);
  assert.deepEqual(parsed, normalized);
});

test('normalizeMessageLengthProfile preserves proportions and sums to one', () => {
  const updated = normalizeMessageLengthProfile({ short: 0.7, medium: 0.1, long: 0.2 });
  const total = Object.values(updated).reduce((sum, value) => sum + value, 0);
  assert.ok(Math.abs(total - 1) < 1e-6);
  assert.equal(Object.keys(updated).length, Object.keys(DEFAULT_MESSAGE_LENGTH_PROFILE).length);
});

test('toNumber falls back when value is invalid', () => {
  assert.equal(toNumber('42', 10), 42);
  assert.equal(toNumber('invalid', 7), 7);
});

test('translate resolves localized strings with fallback', () => {
  const trValue = translate('tr', 'settings.alerts.tab');
  const enValue = translate('en', 'settings.alerts.tab');
  const fallbackValue = translate('es', 'settings.alerts.tab');

  assert.equal(trValue, 'Bildirimler');
  assert.equal(enValue, 'Notifications');
  assert.equal(fallbackValue, trValue);
});

test('registerTranslations merges dictionaries dynamically', () => {
  registerTranslations('de', { 'settings.alerts.tab': 'Benachrichtigungen' });
  assert.equal(translate('de', 'settings.alerts.tab'), 'Benachrichtigungen');
});

test('buildThresholdSummary formats warning and critical labels', () => {
  const metric = { warning: '1.2', critical: '2.4', unit: 'sn' };
  assert.equal(buildThresholdSummary(metric, noopTranslate), 'Uyarı 1.2 sn, Kritik 2.4 sn');
  assert.equal(buildThresholdSummary(null, noopTranslate), '');
});

test('summarizeAlertChannels groups metrics per channel with summaries', () => {
  const channels = createAlertChannelOptions(noopTranslate);
  const preferences = [
    { id: 'latency', channels: ['email'], warning: '1.0', critical: '2.0', unit: 'sn', label: 'Latency' },
    { id: 'errorRate', channels: ['email', 'sms'], warning: '4', critical: '6', unit: '%', label: 'Error' }
  ];

  const summaries = summarizeAlertChannels(preferences, channels, noopTranslate);
  const emailSummary = summaries.find(channel => channel.id === 'email');
  const smsSummary = summaries.find(channel => channel.id === 'sms');

  assert.equal(emailSummary.metrics.length, 2);
  assert.ok(emailSummary.metrics[0].summary.includes('Uyarı'));
  assert.equal(smsSummary.metrics.length, 1);
  assert.equal(smsSummary.metrics[0].id, 'errorRate');
});
