"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import {
  Activity,
  Building2,
  Edit2,
  Loader2,
  Play,
  Plus,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { usePermissions } from "@/lib/hooks/use-permissions";
import {
  useCompetitorBrands,
  useCreateCompetitorBrand,
  useRunBrandScrape,
  useToggleCompetitorBrandMonitoring,
  useUpdateCompetitorBrand,
} from "@/lib/hooks/admin/use-competitor-brands";
import type { CompetitorBrandRead } from "@/lib/api/endpoints/competitor-brands";

// ---------------------------------------------------------------------------
// Form state
// ---------------------------------------------------------------------------

interface BrandFormState {
  name: string;
  amazon_search_term: string;
  amazon_dept: string;
  amazon_category_node: string;
  is_active: boolean;
  notes: string;
}

const EMPTY_FORM: BrandFormState = {
  name: "",
  amazon_search_term: "",
  amazon_dept: "industrial",
  amazon_category_node: "",
  is_active: true,
  notes: "",
};

function brandToForm(b: CompetitorBrandRead): BrandFormState {
  return {
    name: b.name,
    amazon_search_term: b.amazon_search_term ?? "",
    amazon_dept: b.amazon_dept,
    amazon_category_node: b.amazon_category_node ?? "",
    is_active: b.is_active,
    notes: b.notes ?? "",
  };
}

// ---------------------------------------------------------------------------
// Brand form dialog (create / edit)
// ---------------------------------------------------------------------------

interface BrandDialogProps {
  mode: "create" | "edit";
  initial: BrandFormState;
  open: boolean;
  onClose: () => void;
  onSave: (form: BrandFormState) => Promise<void>;
  isSaving: boolean;
}

function BrandDialog({ mode, initial, open, onClose, onSave, isSaving }: BrandDialogProps) {
  const t = useTranslations("admin.competitorBrands.form");
  const [form, setForm] = React.useState<BrandFormState>(initial);

  React.useEffect(() => {
    if (open) setForm(initial);
  }, [open, initial]);

  const set = (key: keyof BrandFormState) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSave(form);
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? t("createTitle") : t("editTitle")}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          {/* Name */}
          <div className="space-y-1.5">
            <Label htmlFor="name">{t("name")} *</Label>
            <Input
              id="name"
              value={form.name}
              onChange={set("name")}
              placeholder={t("namePlaceholder")}
              required
              disabled={isSaving}
            />
          </div>

          {/* Amazon search term */}
          <div className="space-y-1.5">
            <Label htmlFor="amazon_search_term">{t("amazonSearchTerm")}</Label>
            <Input
              id="amazon_search_term"
              value={form.amazon_search_term}
              onChange={set("amazon_search_term")}
              placeholder={t("amazonSearchTermPlaceholder")}
              disabled={isSaving}
            />
            <p className="text-xs text-muted-foreground">{t("amazonSearchTermHint")}</p>
          </div>

          {/* Dept + Category node — 2 col */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="amazon_dept">{t("amazonDept")}</Label>
              <Input
                id="amazon_dept"
                value={form.amazon_dept}
                onChange={set("amazon_dept")}
                placeholder={t("amazonDeptPlaceholder")}
                disabled={isSaving}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="amazon_category_node">{t("amazonCategoryNode")}</Label>
              <Input
                id="amazon_category_node"
                value={form.amazon_category_node}
                onChange={set("amazon_category_node")}
                placeholder={t("amazonCategoryNodePlaceholder")}
                disabled={isSaving}
              />
            </div>
          </div>

          {/* Active */}
          <div className="flex items-center gap-3">
            <Checkbox
              id="is_active"
              checked={form.is_active}
              onCheckedChange={(v) => setForm((prev) => ({ ...prev, is_active: v === true }))}
              disabled={isSaving}
            />
            <Label htmlFor="is_active" className="cursor-pointer font-normal">
              {t("isActive")}
            </Label>
          </div>

          {/* Notes */}
          <div className="space-y-1.5">
            <Label htmlFor="notes">{t("notes")}</Label>
            <Textarea
              id="notes"
              value={form.notes}
              onChange={set("notes")}
              placeholder={t("notesPlaceholder")}
              rows={2}
              disabled={isSaving}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={isSaving}>
              {t("cancel")}
            </Button>
            <Button type="submit" disabled={isSaving || !form.name.trim()}>
              {isSaving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t("saving")}
                </>
              ) : (
                t("save")
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Main client component
// ---------------------------------------------------------------------------

export function CompetitorBrandsClient() {
  const t = useTranslations("admin.competitorBrands");
  const { hasPermission } = usePermissions();
  const canWrite = hasPermission("scraper:write");

  const { data: brands = [], isLoading } = useCompetitorBrands();
  const createMutation = useCreateCompetitorBrand();
  const updateMutation = useUpdateCompetitorBrand();
  const toggleMonitoringMutation = useToggleCompetitorBrandMonitoring();
  const runMutation = useRunBrandScrape();

  // Dialog state
  const [dialogMode, setDialogMode] = React.useState<"create" | "edit" | null>(null);
  const [editTarget, setEditTarget] = React.useState<CompetitorBrandRead | null>(null);

  const isSaving = createMutation.isPending || updateMutation.isPending;

  const openCreate = () => {
    setEditTarget(null);
    setDialogMode("create");
  };

  const openEdit = (brand: CompetitorBrandRead) => {
    setEditTarget(brand);
    setDialogMode("edit");
  };

  const closeDialog = () => {
    setDialogMode(null);
    setEditTarget(null);
  };

  const handleSave = async (form: BrandFormState) => {
    const payload = {
      name: form.name.trim(),
      amazon_search_term: form.amazon_search_term.trim() || null,
      amazon_dept: form.amazon_dept.trim() || "industrial",
      amazon_category_node: form.amazon_category_node.trim() || null,
      is_active: form.is_active,
      notes: form.notes.trim() || null,
    };

    try {
      if (dialogMode === "create") {
        await createMutation.mutateAsync(payload);
        toast.success(t("form.created"));
      } else if (editTarget) {
        await updateMutation.mutateAsync({ id: editTarget.id, data: payload });
        toast.success(t("form.updated"));
      }
      closeDialog();
    } catch {
      toast.error(dialogMode === "create" ? t("form.createFailed") : t("form.updateFailed"));
    }
  };

  const handleToggleActive = async (brand: CompetitorBrandRead) => {
    try {
      await updateMutation.mutateAsync({
        id: brand.id,
        data: { is_active: !brand.is_active },
      });
    } catch {
      toast.error(t("form.updateFailed"));
    }
  };

  const handleToggleMonitoring = async (brand: CompetitorBrandRead) => {
    try {
      await toggleMonitoringMutation.mutateAsync(brand.id);
      toast.success(t("toggleMonitoringSuccess"));
    } catch {
      toast.error(t("toggleMonitoringFailed"));
    }
  };

  const handleRunAll = async () => {
    try {
      const resp = await runMutation.mutateAsync({});
      if (resp.total_brands === 0) {
        toast.info(t("noActiveBrands"));
      } else {
        toast.success(t("scrapeQueued", { count: resp.total_brands }));
      }
    } catch {
      toast.error(t("scrapeFailed"));
    }
  };

  const handleBootstrapScan = async (brandId: string) => {
    try {
      await fetch(`/api/v1/competitor-brands/${encodeURIComponent(brandId)}/bootstrap-scan`, {
        method: "POST",
      });
      toast.success("Bootstrap scan iniciado");
    } catch {
      toast.error("Error al iniciar bootstrap scan");
    }
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return t("never");
    return new Date(iso).toLocaleString("es-AE", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {brands.length} {brands.length === 1 ? t("brandSingular") : t("brandPlural")}
        </p>
        <div className="flex gap-2">
          {canWrite ? (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={handleRunAll}
                disabled={runMutation.isPending || brands.filter((b) => b.is_active).length === 0}
                className="gap-1.5"
              >
                {runMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5" />
                )}
                {runMutation.isPending ? t("runningScrape") : t("runScrape")}
              </Button>
              <Button size="sm" onClick={openCreate} className="gap-1.5">
                <Plus className="h-3.5 w-3.5" />
                {t("addBrand")}
              </Button>
            </>
          ) : null}
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-8">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("loading")}
        </div>
      ) : brands.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed py-16 text-center">
          <Building2 className="h-10 w-10 text-muted-foreground/40" />
          <div>
            <p className="text-sm font-medium">{t("empty")}</p>
            <p className="text-xs text-muted-foreground mt-1">{t("emptyHint")}</p>
          </div>
          {canWrite ? (
            <Button size="sm" onClick={openCreate} className="gap-1.5 mt-2">
              <Plus className="h-3.5 w-3.5" />
              {t("addBrand")}
            </Button>
          ) : null}
        </div>
      ) : (
        <div className="rounded-md border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">
                  {t("columns.name")}
                </th>
                <th className="hidden px-4 py-2.5 text-left font-medium text-muted-foreground md:table-cell">
                  {t("columns.dept")}
                </th>
                <th className="hidden px-4 py-2.5 text-left font-medium text-muted-foreground lg:table-cell">
                  {t("columns.categoryNode")}
                </th>
                <th className="hidden px-4 py-2.5 text-left font-medium text-muted-foreground xl:table-cell">
                  {t("columns.lastScraped")}
                </th>
                <th className="px-4 py-2.5 text-center font-medium text-muted-foreground">
                  {t("columns.active")}
                </th>
                <th className="hidden px-4 py-2.5 text-center font-medium text-muted-foreground lg:table-cell">
                  {t("columns.monitoring")}
                </th>
                <th className="hidden px-4 py-2.5 text-center font-medium text-muted-foreground md:table-cell">
                  Modo
                </th>
                {canWrite ? (
                  <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">
                    {t("columns.actions")}
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {brands.map((brand, idx) => (
                <tr
                  key={brand.id}
                  className={idx % 2 === 0 ? "bg-background" : "bg-muted/20"}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium">{brand.name}</div>
                    {brand.amazon_search_term &&
                    brand.amazon_search_term !== brand.name ? (
                      <div className="text-xs text-muted-foreground font-mono mt-0.5">
                        → {brand.amazon_search_term}
                      </div>
                    ) : null}
                  </td>
                  <td className="hidden px-4 py-3 md:table-cell">
                    <Badge variant="outline" className="font-mono text-xs">
                      {brand.amazon_dept}
                    </Badge>
                  </td>
                  <td className="hidden px-4 py-3 text-muted-foreground font-mono text-xs lg:table-cell">
                    {brand.amazon_category_node ?? "—"}
                  </td>
                  <td className="hidden px-4 py-3 text-muted-foreground text-xs xl:table-cell">
                    {formatDate(brand.last_scraped_at)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {canWrite ? (
                      <button
                        type="button"
                        onClick={() => handleToggleActive(brand)}
                        disabled={updateMutation.isPending}
                        title={
                          brand.is_active
                            ? t("actions.deactivate")
                            : t("actions.activate")
                        }
                        className="inline-flex items-center text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
                      >
                        {brand.is_active ? (
                          <ToggleRight className="h-5 w-5 text-primary" />
                        ) : (
                          <ToggleLeft className="h-5 w-5" />
                        )}
                      </button>
                    ) : (
                      <span
                        className={
                          brand.is_active ? "text-primary" : "text-muted-foreground"
                        }
                      >
                        {brand.is_active ? "✓" : "—"}
                      </span>
                    )}
                  </td>
                  {/* Monitoring badge */}
                  <td className="hidden px-4 py-3 text-center lg:table-cell">
                    {canWrite ? (
                      <button
                        type="button"
                        onClick={() => handleToggleMonitoring(brand)}
                        disabled={toggleMonitoringMutation.isPending}
                        title={t("toggleMonitoring")}
                        className="inline-flex items-center gap-1 disabled:opacity-50"
                      >
                        {brand.monitoring_active ? (
                          <Badge
                            variant="outline"
                            className="gap-1 border-blue-500/40 text-blue-700 bg-blue-50 text-xs cursor-pointer"
                          >
                            <Activity className="h-3 w-3" />
                            {t("monitoringEnabled")}
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="gap-1 text-muted-foreground text-xs cursor-pointer"
                          >
                            {t("monitoringDisabled")}
                          </Badge>
                        )}
                      </button>
                    ) : (
                      brand.monitoring_active ? (
                        <Badge
                          variant="outline"
                          className="gap-1 border-blue-500/40 text-blue-700 bg-blue-50 text-xs"
                        >
                          <Activity className="h-3 w-3" />
                          {t("monitoringEnabled")}
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">{t("monitoringDisabled")}</span>
                      )
                    )}
                  </td>
                  {/* Modo column */}
                  <td className="hidden px-4 py-3 text-center md:table-cell">
                    <div className="flex flex-col items-center gap-1.5">
                      {brand.monitoring_active ? (
                        <Badge variant="secondary">Monitoreo</Badge>
                      ) : (
                        <Badge
                          variant="outline"
                          className="border-orange-400 text-orange-600"
                        >
                          Bootstrap
                        </Badge>
                      )}
                      {canWrite && !brand.monitoring_active ? (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-6 px-2 text-xs"
                          onClick={() => handleBootstrapScan(brand.id)}
                        >
                          Bootstrap Scan
                        </Button>
                      ) : null}
                    </div>
                  </td>

                  {canWrite ? (
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => openEdit(brand)}
                        title={t("actions.edit")}
                      >
                        <Edit2 className="h-3.5 w-3.5" />
                      </Button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit dialog */}
      {dialogMode ? (
        <BrandDialog
          mode={dialogMode}
          initial={editTarget ? brandToForm(editTarget) : EMPTY_FORM}
          open={dialogMode !== null}
          onClose={closeDialog}
          onSave={handleSave}
          isSaving={isSaving}
        />
      ) : null}
    </>
  );
}
