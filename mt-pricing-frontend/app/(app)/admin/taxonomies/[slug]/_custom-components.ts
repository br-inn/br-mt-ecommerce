import type * as React from "react";

/**
 * Registry de overrides para `TaxonomyType.ui_layout.custom_component`.
 *
 * Cuando un `TaxonomyType` declara `ui_layout.custom_component = "foo"`, si
 * existe la entrada `CUSTOM_COMPONENTS["foo"]` el cliente la renderiza en
 * vez del form-builder genérico. Si la string está declarada pero no
 * registrada, el cliente muestra un warning visible y cae al form-builder
 * default (no rompe la página).
 *
 * Convención de naming: usar slugs kebab-case que reflejen el caso de uso
 * (`series-versions-tree`, `materials-with-physical-props`, etc.) — NO el
 * nombre del componente React.
 *
 * Cómo registrar:
 *   import { SeriesVersionsTree } from "./_custom/series-versions-tree";
 *   export const CUSTOM_COMPONENTS = {
 *     "series-versions-tree": SeriesVersionsTree,
 *   } satisfies Record<string, CustomTaxonomyComponent>;
 */
export type CustomTaxonomyComponent = React.ComponentType<{ typeSlug: string }>;

export const CUSTOM_COMPONENTS: Record<string, CustomTaxonomyComponent> = {};
