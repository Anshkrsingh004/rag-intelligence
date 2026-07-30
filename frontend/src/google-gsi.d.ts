// Minimal typings for the Google Identity Services (GIS) browser library.

interface GoogleCredentialResponse {
  credential?: string;
  select_by?: string;
}

interface GoogleIdInitConfig {
  client_id: string;
  callback: (response: GoogleCredentialResponse) => void;
  auto_select?: boolean;
}

interface GoogleButtonRenderConfig {
  type?: "standard" | "icon";
  theme?: "outline" | "filled_blue" | "filled_black";
  size?: "small" | "medium" | "large";
  shape?: "rectangular" | "pill" | "circle" | "square";
  text?: "signin_with" | "signup_with" | "continue_with" | "signin";
  logo_alignment?: "left" | "center";
  width?: number;
}

interface Window {
  google?: {
    accounts: {
      id: {
        initialize: (config: GoogleIdInitConfig) => void;
        renderButton: (parent: HTMLElement, config: GoogleButtonRenderConfig) => void;
        prompt: () => void;
        cancel: () => void;
        disableAutoSelect: () => void;
      };
    };
  };
}
