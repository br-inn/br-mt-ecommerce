"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  Plus,
  RefreshCw,
  Server,
  Shield,
  Trash2,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useApiClient } from "@/lib/hooks/use-api-client";
import { usePermissions } from "@/lib/hooks/use-permissions";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DomainHealth {
  domain: string;
  circuit_state: "closed" | "open" | "half_open" | "unknown";
  failures: number;
  failure_threshold: number;
  opened_at: number | null;
  recovery_timeout: number;
  requests_24h: number;
  errors_24h: number;
  error_rate: number;
}

interface ScraperHealthData {
  domains: DomainHealth[];
  proxy_count: number;
  rate_limit_rpm: number;
  cb_failure_threshold: number;
  cb_recovery_timeout: number;
}

interface ProxyItem {
  proxy: string;
  proxy_b64: string;
}

interface ProxyListData {
  proxies: ProxyItem[];
  total: number;
}

// ---------------------------------------------------------------------------
// API hooks
// ---------------------------------------------------------------------------

function useScraperHealth() {
  const { get } = useApiClient();
  return useQuery<ScraperHealthData>({
    queryKey: ["scraper-health"],
    queryFn: () => get("/api/v1/admin/scraper-health"),
    refetchInterval: 30_000,
  });
}

function useProxies() {
  const { get } = useApiClient();
  return useQuery<ProxyListData>({
    queryKey: ["scraper-proxies"],
    queryFn: () => get("/api/v1/admin/proxies"),
  });
}

function useAddProxy() {
  const { post } = useApiClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (proxy: string) => post("/api/v1/admin/proxies", { proxy }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scraper-proxies"] });
      qc.invalidateQueries({ queryKey: ["scraper-health"] });
    },
  });
}

function useRemoveProxy() {
  const { del } = useApiClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (proxy_b64: string) => del(`/api/v1/admin/proxies/${proxy_b64}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scraper-proxies"] });
      qc.invalidateQueries({ queryKey: ["scraper-health"] });
    },
  });
}

function useResetCircuit() {
  const { post } = useApiClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (domain: string) =>
      post(`/api/v1/admin/scraper-health/circuit/${domain}/reset`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scraper-health"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Circuit state badge
// ---------------------------------------------------------------------------

function CircuitBadge({ state }: { state: DomainHealth["circuit_state"] }) {
  if (state === "closed") {
    return (
      <Badge variant="outline" className="gap-1 border-green-500/40 text-green-700 bg-green-50">
        <CheckCircle2 className="h-3 w-3" />
        Closed
      </Badge>
    );
  }
  if (state === "open") {
    return (
      <Badge variant="destructive" className="gap-1">
        <XCircle className="h-3 w-3" />
        Open
      </Badge>
    );
  }
  if (state === "half_open") {
    return (
      <Badge variant="outline" className="gap-1 border-yellow-500/40 text-yellow-700 bg-yellow-50">
        <AlertTriangle className="h-3 w-3" />
        Half-Open
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="gap-1 text-muted-foreground">
      <Clock className="h-3 w-3" />
      Unknown
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ScraperHealthClient() {
  const t = useTranslations("admin.scraperHealth");
  const { can } = usePermissions();

  const { data: healthData, isLoading: healthLoading, refetch } = useScraperHealth();
  const { data: proxiesData, isLoading: proxiesLoading } = useProxies();
  const addProxy = useAddProxy();
  const removeProxy = useRemoveProxy();
  const resetCircuit = useResetCircuit();

  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [newProxy, setNewProxy] = useState("");

  const handleAddProxy = async () => {
    if (!newProxy.trim()) return;
    try {
      await addProxy.mutateAsync(newProxy.trim());
      toast.success(t("proxies.addSuccess"));
      setNewProxy("");
      setAddDialogOpen(false);
    } catch {
      toast.error(t("proxies.addFailed"));
    }
  };

  const handleRemoveProxy = async (proxy_b64: string) => {
    try {
      await removeProxy.mutateAsync(proxy_b64);
      toast.success(t("proxies.removeSuccess"));
    } catch {
      toast.error(t("proxies.removeFailed"));
    }
  };

  const handleResetCircuit = async (domain: string) => {
    try {
      await resetCircuit.mutateAsync(domain);
      toast.success(t("circuit.resetSuccess", { domain }));
    } catch {
      toast.error(t("circuit.resetFailed"));
    }
  };

  return (
    <div className="space-y-8">
      {/* Config summary */}
      {healthData && (
        <div className="flex flex-wrap gap-4 text-sm">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Shield className="h-4 w-4" />
            <span>
              {t("config.rateLimitRpm", { rpm: healthData.rate_limit_rpm })}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Server className="h-4 w-4" />
            <span>
              {t("config.proxyCount", { count: healthData.proxy_count })}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <AlertTriangle className="h-4 w-4" />
            <span>
              {t("config.cbThreshold", {
                threshold: healthData.cb_failure_threshold,
                timeout: healthData.cb_recovery_timeout,
              })}
            </span>
          </div>
        </div>
      )}

      {/* Domain health table */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">{t("domains.title")}</h2>
          <Button
            size="sm"
            variant="outline"
            onClick={() => refetch()}
            disabled={healthLoading}
            className="gap-1.5"
          >
            {healthLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            {t("refresh")}
          </Button>
        </div>

        {healthLoading ? (
          <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            {t("loading")}
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("domains.domain")}</TableHead>
                  <TableHead>{t("domains.circuitState")}</TableHead>
                  <TableHead className="text-right">{t("domains.failures")}</TableHead>
                  <TableHead className="text-right">{t("domains.requests24h")}</TableHead>
                  <TableHead className="text-right">{t("domains.errorRate")}</TableHead>
                  {can("admin:write") && <TableHead className="text-right">{t("domains.actions")}</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {healthData?.domains.map((domain) => (
                  <TableRow key={domain.domain}>
                    <TableCell className="font-mono text-sm">{domain.domain}</TableCell>
                    <TableCell>
                      <CircuitBadge state={domain.circuit_state} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      <span
                        className={
                          domain.failures > 0 ? "text-destructive font-medium" : "text-muted-foreground"
                        }
                      >
                        {domain.failures}/{domain.failure_threshold}
                      </span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-muted-foreground">
                      {domain.requests_24h.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      <span
                        className={
                          domain.error_rate > 0.1
                            ? "text-destructive font-medium"
                            : domain.error_rate > 0
                            ? "text-yellow-600"
                            : "text-muted-foreground"
                        }
                      >
                        {(domain.error_rate * 100).toFixed(1)}%
                      </span>
                    </TableCell>
                    {can("admin:write") && (
                      <TableCell className="text-right">
                        {domain.circuit_state !== "closed" && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleResetCircuit(domain.domain)}
                            disabled={resetCircuit.isPending}
                            className="h-7 text-xs"
                          >
                            {t("circuit.reset")}
                          </Button>
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      {/* Proxy pool */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">{t("proxies.title")}</h2>
          {can("admin:write") && (
            <Button
              size="sm"
              onClick={() => setAddDialogOpen(true)}
              className="gap-1.5"
            >
              <Plus className="h-3.5 w-3.5" />
              {t("proxies.add")}
            </Button>
          )}
        </div>

        {proxiesLoading ? (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            {t("loading")}
          </div>
        ) : !proxiesData?.proxies.length ? (
          <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
            {t("proxies.empty")}
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("proxies.proxyUrl")}</TableHead>
                  {can("admin:write") && <TableHead className="text-right">{t("proxies.actions")}</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {proxiesData?.proxies.map((item) => (
                  <TableRow key={item.proxy_b64}>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {item.proxy.replace(/:\/\/[^@]+@/, "://***@")}
                    </TableCell>
                    {can("admin:write") && (
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleRemoveProxy(item.proxy_b64)}
                          disabled={removeProxy.isPending}
                          className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          <span className="sr-only">{t("proxies.remove")}</span>
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      {/* Add proxy dialog */}
      <Dialog open={addDialogOpen} onOpenChange={(v) => !v && setAddDialogOpen(false)}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>{t("proxies.addTitle")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label htmlFor="proxy-url">{t("proxies.proxyUrl")}</Label>
            <Input
              id="proxy-url"
              value={newProxy}
              onChange={(e) => setNewProxy(e.target.value)}
              placeholder="http://user:pass@host:port"
              className="font-mono text-sm"
              onKeyDown={(e) => e.key === "Enter" && handleAddProxy()}
            />
            <p className="text-xs text-muted-foreground">{t("proxies.proxyUrlHint")}</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
              {t("cancel")}
            </Button>
            <Button
              onClick={handleAddProxy}
              disabled={!newProxy.trim() || addProxy.isPending}
            >
              {addProxy.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
              ) : null}
              {t("proxies.addConfirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
