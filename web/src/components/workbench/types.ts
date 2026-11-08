export type SelectionSource = "viewer" | "table" | "panel";

export interface Selection {
  field: string;
  source: SelectionSource;
  nonce: number;
}
