import React, { createContext, useContext, useEffect, useState } from 'react';

export type Lang = 'zh' | 'en';

/** A string in both languages. */
export interface Text {
  zh: string;
  en: string;
}

type T = {
  (text: Text): string;
  (zh: string, en: string): string;
};

const LangContext = createContext<{ lang: Lang; setLang: (l: Lang) => void }>({ lang: 'zh', setLang: () => {} });

const STORAGE_KEY = 'sar2action.lang';

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'zh' || saved === 'en') return saved;
  } catch {
    // Storage blocked (private mode, previews): fall back to Chinese.
  }
  return 'zh';
}

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Lang>(initialLang);
  useEffect(() => {
    document.documentElement.lang = lang === 'zh' ? 'zh-Hant' : 'en';
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      // Not persisting is fine.
    }
  }, [lang]);
  return <LangContext.Provider value={{ lang, setLang }}>{children}</LangContext.Provider>;
}

export function useLang() {
  return useContext(LangContext);
}

/** `t('中文', 'English')` or `t({ zh, en })` → the string for the current language. */
export function useT(): T {
  const { lang } = useLang();
  return ((a: string | Text, b?: string) => (typeof a === 'string' ? (lang === 'zh' ? a : (b as string)) : a[lang])) as T;
}
