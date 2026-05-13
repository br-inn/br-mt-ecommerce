"use client";

import * as React from "react";
import {
  AlertTriangle,
  Check,
  Pencil,
  Send,
  X,
} from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { MtButton, Pill, SectionCard } from "@/components/mt/primitives";
import { MtError, MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import { useProduct } from "@/lib/hooks/products/use-product";
import {
  useApproveTranslation,
  useProductTranslations,
  useUpsertTranslation,
} from "@/lib/hooks/products/use-translations";
import {
  useMarkTranslationsStale,
  useRejectTranslation,
  useRequestReviewTranslation,
} from "@/lib/hooks/products/use-translation-workflow";
import type {
  Language,
  ProductTranslationRead,
} from "@/lib/api/endpoints/products";
import {
  getProductDescription,
  getProductName,
} from "@/lib/utils/product-display";


const tSchema = z.object({
  name: z.string().min(2, "Mínimo 2 caracteres"),
  description: z.string().optional(),
});
type TFormValues = z.infer<typeof tSchema>;

type WorkflowStatus =
  | "draft"
  | "pending"
  | "pending_review"
  | "approved"
  | "stale";

function statusVisuals(status: WorkflowStatus): {
  tone: "success" | "warning" | "danger" | "neutral";
  label: string;
} {
  switch (status) {
    case "approved":
      return { tone: "success", label: "Aprobada" };
    case "pending_review":
      return { tone: "warning", label: "En revisión" };
    case "stale":
      return { tone: "danger", label: "Stale" };
    case "pending":
      return { tone: "warning", label: "Pendiente" };
    case "draft":
    default:
      return { tone: "warning", label: "Borrador" };
  }
}

function TranslationEditor({
  productId,
  lang,
  current,
  masterName,
  masterDesc,
}: {
  productId: string;
  lang: Language;
  current: ProductTranslationRead | undefined;
  masterName: string;
  masterDesc: string;
}) {
  const upsert = useUpsertTranslation(productId);
  const approve = useApproveTranslation(productId);
  const requestReview = useRequestReviewTranslation(productId);
  const reject = useRejectTranslation(productId);
  const status = (current?.status ?? "draft") as WorkflowStatus;
  const { tone, label } = statusVisuals(status);
  const isAR = lang === "ar";

  // Visibilidad de botones del workflow.
  const canRequestReview =
    !!current && (status === "draft" || status === "pending" || status === "stale");
  const canApprove = !!current && status === "pending_review";
  const canReject = !!current && status === "pending_review";
  const isStale = status === "stale";

  const [rejectOpen, setRejectOpen] = React.useState(false);
  const [rejectReason, setRejectReason] = React.useState("");

  const { register, handleSubmit, formState } = useForm<TFormValues>({
    resolver: zodResolver(tSchema),
    defaultValues: {
      name: current?.name ?? "",
      description: current?.description ?? "",
    },
  });

  const flag = isAR ? MT.success : MT.danger;
  const code = lang.toUpperCase() as "ES" | "AR";
  const langLabel = isAR ? "Árabe (UAE)" : "Español";

  return (
    <div
      className="overflow-hidden rounded-lg border bg-mt-surface"
      style={{ borderColor: MT.border }}
    >
      <div
        className="flex items-center gap-2 border-b px-3 py-2.5"
        style={{ background: MT.surface2, borderColor: MT.border }}
      >
        <span
          className="mt-mono inline-grid w-5 place-items-center rounded-[2px] border text-[9px] font-semibold leading-none text-white"
          style={{ background: flag, borderColor: MT.border, height: 14 }}
        >
          {code}
        </span>
        <span className="text-[12.5px] font-semibold" style={{ color: MT.ink }}>
          {langLabel}
        </span>
        <Pill tone={tone} dot>
          {label}
        </Pill>
        <span className="flex-1" />
        {canRequestReview ? (
          <MtButton
            size="sm"
            tone="ghost"
            icon={<Send className="size-3.5" />}
            onClick={() => requestReview.mutate(lang)}
            disabled={requestReview.isPending}
          >
            Pedir revisión
          </MtButton>
        ) : null}
        {canReject ? (
          <MtButton
            size="sm"
            tone="ghost"
            icon={<X className="size-3.5" />}
            onClick={() => setRejectOpen((v) => !v)}
            disabled={reject.isPending}
          >
            Rechazar
          </MtButton>
        ) : null}
        {canApprove ? (
          <MtButton
            size="sm"
            tone="ghost"
            icon={<Check className="size-3.5" />}
            onClick={() => approve.mutate(lang)}
            disabled={approve.isPending}
          >
            Aprobar
          </MtButton>
        ) : null}
      </div>

      {isStale ? (
        <div
          className="flex items-center gap-1.5 border-b px-3 py-1.5 text-[11.5px]"
          style={{
            background: MT.dangerSoft,
            color: MT.danger,
            borderColor: MT.border,
          }}
        >
          <AlertTriangle className="size-3" />
          Esta traducción es <strong>stale</strong>: el master EN cambió
          {(current as { staleness_reason?: string | null } | undefined)?.staleness_reason
            ? ` (${(current as { staleness_reason?: string | null }).staleness_reason})`
            : ""}.
          Edita y vuelve a pedir revisión.
        </div>
      ) : null}

      {rejectOpen && canReject ? (
        <div
          className="flex flex-col gap-2 border-b px-3 py-2.5"
          style={{ background: MT.surface3, borderColor: MT.border }}
        >
          <span className="text-[11.5px]" style={{ color: MT.ink3 }}>
            Motivo del rechazo (mínimo 3 caracteres):
          </span>
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            rows={2}
            className="w-full rounded-md border bg-transparent px-2 py-1.5 text-[12px] outline-none focus-visible:ring-2 focus-visible:ring-mt-brand"
            style={{ borderColor: MT.border, color: MT.ink }}
            placeholder="Ej: terminología incorrecta para válvulas industriales"
          />
          <div className="flex items-center justify-end gap-2">
            <MtButton
              size="sm"
              tone="ghost"
              onClick={() => {
                setRejectOpen(false);
                setRejectReason("");
              }}
            >
              Cancelar
            </MtButton>
            <MtButton
              size="sm"
              tone="primary"
              disabled={reject.isPending || rejectReason.trim().length < 3}
              onClick={() =>
                reject.mutate(
                  { lang, payload: { reason: rejectReason.trim() } },
                  {
                    onSuccess: () => {
                      setRejectOpen(false);
                      setRejectReason("");
                    },
                  },
                )
              }
            >
              {reject.isPending ? "Rechazando…" : "Confirmar rechazo"}
            </MtButton>
          </div>
        </div>
      ) : null}

      <form
        className="flex flex-col gap-3 px-3 py-3"
        onSubmit={handleSubmit((vals) =>
          upsert.mutate({
            lang,
            payload: {
              name: vals.name,
              description: vals.description ?? null,
            },
          }),
        )}
      >
        <div>
          <div
            className="mt-mono mb-1 text-[10.5px] uppercase tracking-[0.6px]"
            style={{ color: MT.ink4 }}
          >
            name_{lang} ({masterName.length} chars en máster)
          </div>
          <input
            {...register("name")}
            dir={isAR ? "rtl" : "ltr"}
            className={`w-full rounded-md border bg-transparent px-2 py-1.5 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-mt-brand focus-visible:ring-offset-1 ${
              isAR ? "mt-arabic" : ""
            }`}
            style={{ borderColor: MT.border, color: MT.ink }}
          />
          {formState.errors.name ? (
            <span className="mt-1 text-[11px]" style={{ color: MT.danger }}>
              {formState.errors.name.message}
            </span>
          ) : null}
        </div>
        <div>
          <div
            className="mt-mono mb-1 text-[10.5px] uppercase tracking-[0.6px]"
            style={{ color: MT.ink4 }}
          >
            desc_{lang}
          </div>
          <textarea
            {...register("description")}
            dir={isAR ? "rtl" : "ltr"}
            rows={4}
            className={`w-full rounded-md border bg-transparent px-2 py-1.5 text-[12px] leading-[1.5] outline-none focus-visible:ring-2 focus-visible:ring-mt-brand focus-visible:ring-offset-1 ${
              isAR ? "mt-arabic" : ""
            }`}
            style={{ borderColor: MT.border, color: MT.ink2 }}
            placeholder={masterDesc.slice(0, 80)}
          />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[11px]" style={{ color: MT.ink4 }}>
            {current?.updated_at
              ? `Editado ${new Date(current.updated_at).toLocaleString("es-ES")}`
              : "Sin guardar"}
          </span>
          <MtButton
            type="submit"
            tone="primary"
            size="sm"
            disabled={upsert.isPending || !formState.isDirty}
          >
            {upsert.isPending ? "Guardando…" : "Guardar"}
          </MtButton>
        </div>
      </form>
    </div>
  );
}

export function MtTraduccionesClient({ sku }: { sku: string }) {
  const { data: product, isLoading: loadingProduct, isError: errProduct, refetch } =
    useProduct(sku);
  const productId = product?.id;
  const { data: translations, isLoading: loadingTranslations } =
    useProductTranslations(productId);
  const markStale = useMarkTranslationsStale(productId ?? "");

  const findT = React.useCallback(
    (lang: Language): ProductTranslationRead | undefined =>
      translations?.find((t) => t.language === lang),
    [translations],
  );

  if (errProduct) {
    return (
      <div className="px-6 py-4">
        <MtError
          message="No se pudo cargar el producto."
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  return (
    <div className="px-6 py-4">
        <SectionCard
          title="Traducciones"
          subtitle={
            <>
              Master <span className="mt-mono" style={{ color: MT.ink }}>EN</span> · pivote para ES y AR · cualquier cambio en EN marca las traducciones como <em>stale</em>
            </>
          }
          actions={
            <>
              <MtButton
                size="sm"
                icon={<AlertTriangle className="size-3.5" />}
                onClick={() => markStale.mutate(undefined)}
                disabled={!productId || markStale.isPending}
              >
                {markStale.isPending ? "Marcando…" : "Marcar stale"}
              </MtButton>
            </>
          }
        >
          <span className="hidden" />
        </SectionCard>

        {loadingProduct || loadingTranslations || !product ? (
          <div className="mt-3 grid grid-cols-3 gap-3">
            <MtSkeleton width="100%" height={220} />
            <MtSkeleton width="100%" height={220} />
            <MtSkeleton width="100%" height={220} />
          </div>
        ) : (
          <div className="mt-3 grid grid-cols-3 gap-3">
            {/* Master EN — read-only */}
            <div
              className="overflow-hidden rounded-lg border bg-mt-surface"
              style={{ borderColor: MT.border }}
            >
              <div
                className="flex items-center gap-2 border-b px-3 py-2.5"
                style={{ background: MT.surface2, borderColor: MT.border }}
              >
                <span
                  className="mt-mono inline-grid w-5 place-items-center rounded-[2px] border text-[9px] font-semibold leading-none text-white"
                  style={{ background: MT.brand, borderColor: MT.border, height: 14 }}
                >
                  EN
                </span>
                <span className="text-[12.5px] font-semibold" style={{ color: MT.ink }}>
                  Inglés (master)
                </span>
                <Pill tone="success" dot>
                  Aprobada
                </Pill>
                <span className="flex-1" />
                <Pencil className="size-3 cursor-pointer" style={{ color: MT.ink4 }} />
              </div>
              <div className="flex flex-col gap-2 px-3 py-3">
                <div>
                  <div
                    className="mt-mono mb-1 text-[10.5px] uppercase tracking-[0.6px]"
                    style={{ color: MT.ink4 }}
                  >
                    name_en
                  </div>
                  <div className="text-[13px] font-medium" style={{ color: MT.ink }}>
                    {getProductName(product)}
                  </div>
                </div>
                <div>
                  <div
                    className="mt-mono mb-1 text-[10.5px] uppercase tracking-[0.6px]"
                    style={{ color: MT.ink4 }}
                  >
                    desc_en
                  </div>
                  <div className="text-[12px] leading-[1.5]" style={{ color: MT.ink2 }}>
                    {getProductDescription(product) ?? (
                      <em style={{ color: MT.ink4, fontStyle: "normal" }}>
                        — sin descripción —
                      </em>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <TranslationEditor
              productId={product.id}
              lang="es"
              current={findT("es")}
              masterName={getProductName(product)}
              masterDesc={getProductDescription(product) ?? ""}
            />
            <TranslationEditor
              productId={product.id}
              lang="ar"
              current={findT("ar")}
              masterName={getProductName(product)}
              masterDesc={getProductDescription(product) ?? ""}
            />
          </div>
        )}

        {/* Stale-on-master-change reminder banner */}
        <div
          className="mt-3 flex items-center gap-1.5 rounded-md border px-3 py-2 text-[11.5px]"
          style={{
            background: MT.warningSoft,
            color: MT.warning,
            borderColor: MT.warningBorder,
          }}
        >
          <AlertTriangle className="size-3" />
          Edición de master EN puede marcar ES/AR como <em>stale</em> — re-aprueba antes de publicar.
        </div>
    </div>
  );
}
