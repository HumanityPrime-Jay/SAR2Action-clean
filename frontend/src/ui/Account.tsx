import React, { useEffect, useRef, useState } from 'react';
import { type Me, deleteMyData, fetchAuthConfig, fetchMe, signInWithGoogle, signOut } from '../api/auth';
import { useLang, useT } from '../i18n';

const GSI_SRC = 'https://accounts.google.com/gsi/client';

interface GoogleId {
  initialize(opts: { client_id: string; callback: (r: { credential: string }) => void; ux_mode: 'popup' }): void;
  renderButton(el: HTMLElement, opts: Record<string, string | number>): void;
  disableAutoSelect(): void;
}
declare global {
  interface Window {
    google?: { accounts: { id: GoogleId } };
  }
}

let gsi: Promise<GoogleId> | null = null;
/** Loads Google Identity Services once. */
function loadGsi(): Promise<GoogleId> {
  gsi ??= new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = GSI_SRC;
    s.async = true;
    s.onload = () => (window.google ? resolve(window.google.accounts.id) : reject(new Error('gsi')));
    s.onerror = () => {
      gsi = null;
      reject(new Error('gsi'));
    };
    document.head.appendChild(s);
  });
  return gsi;
}

function GoogleButton({ clientId, onCredential }: { clientId: string; onCredential: (c: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const { lang } = useLang();
  const cb = useRef(onCredential);
  cb.current = onCredential;
  useEffect(() => {
    let live = true;
    loadGsi()
      .then((id) => {
        if (!live || !ref.current) return;
        id.initialize({ client_id: clientId, callback: (r) => cb.current(r.credential), ux_mode: 'popup' });
        ref.current.replaceChildren();
        id.renderButton(ref.current, { theme: 'filled_black', size: 'medium', shape: 'rectangular', text: 'signin', locale: lang === 'zh' ? 'zh-TW' : 'en' });
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [clientId, lang]);
  return <div ref={ref} className="gsi-button" />;
}

/**
 * Optional Google sign-in in the top bar. Hidden entirely when the server has sign-in off;
 * nothing else on the site depends on it.
 */
export function Account() {
  const t = useT();
  const [clientId, setClientId] = useState<string | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState(false);
  const menuRef = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    let live = true;
    fetchAuthConfig()
      .then(async (cfg) => {
        if (!live || !cfg.enabled || !cfg.google_client_id) return;
        setClientId(cfg.google_client_id);
        const user = await fetchMe();
        if (live) setMe(user);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  if (!clientId) return null;

  if (!me) {
    return (
      <div className="account">
        <GoogleButton
          clientId={clientId}
          onCredential={(c) => {
            setError(false);
            signInWithGoogle(c)
              .then(setMe)
              .catch(() => setError(true));
          }}
        />
        {error && (
          <span className="account-error" role="alert">
            {t('登入失敗', 'Sign-in failed')}
          </span>
        )}
      </div>
    );
  }

  const leave = async (remove: boolean) => {
    menuRef.current?.removeAttribute('open');
    if (remove) {
      if (!window.confirm(t('確定要刪除你的帳號和所有存下的資料嗎？無法復原。', 'Delete your account and everything saved? This cannot be undone.'))) return;
      await deleteMyData().catch(() => {});
    } else {
      await signOut().catch(() => {});
    }
    window.google?.accounts.id.disableAutoSelect();
    setMe(null);
  };

  const label = me.name || me.email;
  return (
    <details ref={menuRef} className="account account-menu">
      <summary aria-label={t(`已登入：${label}`, `Signed in as ${label}`)}>
        <span className="avatar" aria-hidden="true">
          {label.slice(0, 1).toUpperCase()}
        </span>
        <span className="who">{label}</span>
        {me.role === 'authority' && <span className="role">{t('農政', 'Authority')}</span>}
      </summary>
      <div className="account-pop">
        <p className="cap">{me.email}</p>
        <button onClick={() => leave(false)}>{t('登出', 'Sign out')}</button>
        <button className="danger" onClick={() => leave(true)}>
          {t('刪除我的資料', 'Delete my data')}
        </button>
      </div>
    </details>
  );
}
