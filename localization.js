import { useThemePreferences } from "./components/ThemeProvider.jsx";
import { TRANSLATIONS, FALLBACK_LOCALE, translate, registerTranslations } from "./translation_core.js";

export { TRANSLATIONS, FALLBACK_LOCALE, translate, registerTranslations };

export function useTranslation() {
  const { locale, setLocale } = useThemePreferences();
  return {
    t: (key) => translate(locale, key),
    locale,
    setLocale,
    availableLocales: Object.keys(TRANSLATIONS)
  };
}
