import { useEffect, useMemo, useState } from "react";

const VALID_MODES = new Set(["cards", "table"]);

function isValidMode(mode) {
  return VALID_MODES.has(mode);
}

export function getInitialMode(storageKey, defaultMode) {
  if (typeof window === "undefined") {
    return defaultMode;
  }
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) {
      return defaultMode;
    }
    const parsed = JSON.parse(raw);
    if (isValidMode(parsed)) {
      return parsed;
    }
  } catch (error) {
    console.warn("Görünüm tercihi okunamadı:", error);
  }
  return defaultMode;
}

export function persistViewPreference(storageKey, mode) {
  if (typeof window === "undefined") {
    return;
  }
  if (!isValidMode(mode)) {
    return;
  }
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(mode));
  } catch (error) {
    console.warn("Görünüm tercihi kaydedilemedi:", error);
  }
}

export function useAdaptiveView(preferenceKey, defaultMode = "cards") {
  const storageKey = useMemo(() => `piyasa.view.${preferenceKey}`, [preferenceKey]);
  const [mode, setMode] = useState(() => getInitialMode(storageKey, defaultMode));

  useEffect(() => {
    persistViewPreference(storageKey, mode);
  }, [mode, storageKey]);

  const helpers = useMemo(
    () => ({
      set: (next) => {
        if (isValidMode(next)) {
          setMode(next);
        }
      },
      setCards: () => setMode("cards"),
      setTable: () => setMode("table"),
      toggle: () => setMode((prev) => (prev === "table" ? "cards" : "table"))
    }),
    [setMode]
  );

  return [mode, setMode, helpers];
}

export function isTableView(mode) {
  return mode === "table";
}

export function isCardView(mode) {
  return mode === "cards";
}

export { isValidMode };
