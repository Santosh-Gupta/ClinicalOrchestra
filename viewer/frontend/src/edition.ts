export type ViewerEdition = "advanced" | "public";

const configuredEdition = import.meta.env.VITE_VIEWER_EDITION;

export const VIEWER_EDITION: ViewerEdition = configuredEdition === "public" ? "public" : "advanced";
export const IS_PUBLIC_EDITION = VIEWER_EDITION === "public";
