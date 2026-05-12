/**
 * Fase 4 — Tipos extendidos para asset_links polimórficos + documentos.
 *
 * Modela el contrato HTTP de los endpoints Fase 4:
 *  - GET    /api/v1/{owner_type}/{owner_id}/asset-links
 *  - POST   /api/v1/asset-links
 *  - DELETE /api/v1/asset-links/{link_id}
 *  - GET    /api/v1/documents?type=...&language=...
 *  - GET    /api/v1/documents/{document_id}
 *  - POST   /api/v1/admin/documents
 *  - PATCH  /api/v1/admin/documents/{document_id}
 *  - DELETE /api/v1/admin/documents/{document_id}
 *
 * Source of truth backend:
 *  - mt-pricing-backend/app/schemas/asset_links.py
 *  - mt-pricing-backend/app/schemas/documents.py
 */

export type AssetLinkOwnerType =
  | "product"
  | "variant"
  | "series"
  | "family"
  | "spare_part";

export type AssetLinkRole =
  | "image_padre"
  | "banner"
  | "ficha_pdf"
  | "manual_pdf"
  | "ce_pdf"
  | "catalogo_pdf"
  | "exploded_3d"
  | "section_drawing"
  | "dimensions_drawing"
  | "video"
  | "web_image"
  | "main_image";

export interface AssetLink {
  id: string;
  asset_id: string;
  owner_type: AssetLinkOwnerType;
  owner_id: string;
  role: AssetLinkRole;
  order_index: number;
  created_at: string;
}

export interface AssetLinkWithAsset extends AssetLink {
  /** Eager-loaded ProductAsset desde el endpoint GET /{owner_type}/{owner_id}/asset-links */
  asset: import("./endpoints/products").ProductAsset;
}

export interface AssetLinkCreatePayload {
  asset_id: string;
  owner_type: AssetLinkOwnerType;
  owner_id: string;
  role: AssetLinkRole;
  order_index?: number;
}

export type DocumentType =
  | "ficha_tecnica"
  | "manual"
  | "declaracion_ce"
  | "certificado"
  | "catalogo";

export interface Document {
  id: string;
  type: DocumentType;
  code: string;
  version: string;
  language: string;
  asset_id: string;
  issued_at?: string | null;
  created_at: string;
}

export interface DocumentCreatePayload {
  type: DocumentType;
  code: string;
  version: string;
  language: string;
  asset_id: string;
  issued_at?: string | null;
}

export interface DocumentPatchPayload {
  type?: DocumentType;
  code?: string;
  version?: string;
  language?: string;
  asset_id?: string;
  issued_at?: string | null;
}

export interface DocumentListFilters {
  type?: DocumentType;
  language?: string;
}

/** Roles que renderizan como imagen visualizable. */
export const IMAGE_ROLES: ReadonlyArray<AssetLinkRole> = [
  "image_padre",
  "banner",
  "web_image",
  "main_image",
  "exploded_3d",
  "section_drawing",
  "dimensions_drawing",
];

/** Roles que renderizan como PDF descargable. */
export const PDF_ROLES: ReadonlyArray<AssetLinkRole> = [
  "ficha_pdf",
  "manual_pdf",
  "ce_pdf",
  "catalogo_pdf",
];

/** Roles que renderizan como video embed/link. */
export const VIDEO_ROLES: ReadonlyArray<AssetLinkRole> = ["video"];

export type AssetLinkRoleKind = "image" | "pdf" | "video";

export function classifyRole(role: AssetLinkRole): AssetLinkRoleKind {
  if (IMAGE_ROLES.includes(role)) return "image";
  if (PDF_ROLES.includes(role)) return "pdf";
  if (VIDEO_ROLES.includes(role)) return "video";
  return "image";
}
