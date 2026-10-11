export interface Document {
  readonly id: number;
  readonly text: string;
  readonly language?: string;
  readonly extra?: Readonly<Record<string, string>>;
}
export interface RequestOptions {
  readonly signal?: AbortSignal;
}
export interface SearchOptions extends RequestOptions {
  readonly language?: string;
}
export interface AuthResult {
  readonly exp: number;
}
export interface FailedItem {
  readonly id: number;
  readonly error: string;
  readonly extensions: Readonly<Record<string, unknown>>;
}
export interface StoreResult {
  readonly received_texts: number;
  readonly pending_documents: number;
  readonly failed_documents: number;
  readonly timestamp: string;
  readonly http_status: number;
  readonly delivery_state: "accepted" | "failed";
  readonly pending_ids?: readonly number[];
  readonly failed_items?: readonly FailedItem[];
  readonly extensions: Readonly<Record<string, unknown>>;
}
export interface SearchHit {
  readonly id: number;
  readonly text: string;
  readonly score: number;
  readonly extensions: Readonly<Record<string, unknown>>;
}
export interface SearchResult {
  readonly results: readonly SearchHit[];
  readonly extensions: Readonly<Record<string, unknown>>;
}
