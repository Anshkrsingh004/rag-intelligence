import { useEffect, useRef } from "react";

const GIS_SRC = "https://accounts.google.com/gsi/client";
let gisPromise: Promise<void> | null = null;

/** Load the Google Identity Services script once, shared across mounts. */
function loadGis(): Promise<void> {
  if (gisPromise) return gisPromise;
  gisPromise = new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) {
      resolve();
      return;
    }
    const s = document.createElement("script");
    s.src = GIS_SRC;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Failed to load Google sign-in"));
    document.head.appendChild(s);
  });
  return gisPromise;
}

interface Props {
  clientId: string;
  theme: "light" | "dark";
  onCredential: (credential: string) => void;
}

/**
 * Renders Google's official "Continue with Google" button. On success it hands
 * the ID token (credential) back via onCredential; the backend verifies it.
 */
export function GoogleButton({ clientId, theme, onCredential }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  // Keep the latest callback without re-initializing GIS on every render.
  const cbRef = useRef(onCredential);
  cbRef.current = onCredential;

  useEffect(() => {
    let cancelled = false;
    loadGis()
      .then(() => {
        if (cancelled || !ref.current || !window.google?.accounts?.id) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          auto_select: false, // never sign in without an explicit button click
          callback: (resp) => {
            if (resp?.credential) cbRef.current(resp.credential);
          },
        });
        ref.current.innerHTML = "";
        window.google.accounts.id.renderButton(ref.current, {
          type: "standard",
          theme: theme === "dark" ? "filled_black" : "outline",
          size: "large",
          shape: "pill",
          text: "continue_with",
          logo_alignment: "center",
          width: 300,
        });
      })
      .catch(() => {
        /* If Google's script is blocked/unavailable, the button just won't show. */
      });
    return () => {
      cancelled = true;
    };
  }, [clientId, theme]);

  return <div ref={ref} className="flex min-h-[40px] justify-center" />;
}
