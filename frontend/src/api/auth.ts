/** Optional Google sign-in (`/api/auth/*`, `/api/me`). The session is an HttpOnly cookie on the same origin. */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export interface AuthConfig {
  enabled: boolean;
  google_client_id: string | null;
}

export interface Me {
  email: string;
  name: string | null;
  role: 'farmer' | 'authority';
}

const json = async <T,>(resp: Response): Promise<T> => {
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json() as Promise<T>;
};

export const fetchAuthConfig = () => fetch(`${API_BASE}/api/auth/config`).then((r) => json<AuthConfig>(r));

/** The signed-in user, or null when there is no session. */
export const fetchMe = async (): Promise<Me | null> => {
  const resp = await fetch(`${API_BASE}/api/me`, { credentials: 'include' });
  return resp.status === 401 ? null : json<Me>(resp);
};

export const signInWithGoogle = (credential: string) =>
  fetch(`${API_BASE}/api/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ credential }),
  }).then((r) => json<Me>(r));

export const signOut = () => fetch(`${API_BASE}/api/auth/logout`, { method: 'POST', credentials: 'include' });

export const deleteMyData = async () => {
  const resp = await fetch(`${API_BASE}/api/me`, { method: 'DELETE', credentials: 'include' });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
};
