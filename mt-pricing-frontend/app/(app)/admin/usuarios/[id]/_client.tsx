"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { LogOut, Mail, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { AuditTimeline } from "@/components/domain/audit-timeline";
import {
  useAssignRole,
  useForceLogout,
  useResendInvite,
  useRevokeRole,
  useRolePermissions,
  useRolesCatalog,
  useUpdateUser,
  useUserDetail,
} from "@/lib/hooks/users-admin/use-users-admin";

interface Props {
  userId: string;
}

export function UserDetailClient({ userId }: Props) {
  const t = useTranslations("admin.users");
  const tDetail = useTranslations("admin.users.detail");
  const tCommon = useTranslations("common");

  const { data: user, isLoading, isError } = useUserDetail(userId);
  const { data: roles } = useRolesCatalog();
  const updateUser = useUpdateUser(userId);
  const assignRole = useAssignRole(userId);
  const revokeRole = useRevokeRole(userId);
  const forceLogout = useForceLogout(userId);
  const resendInvite = useResendInvite(userId);

  const { data: rolePerms } = useRolePermissions(user?.role?.id);

  const [confirmLogout, setConfirmLogout] = React.useState(false);
  const [confirmArchive, setConfirmArchive] = React.useState(false);
  const [confirmRevoke, setConfirmRevoke] = React.useState(false);
  const [newRole, setNewRole] = React.useState<string>("");

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (isError || !user) {
    return (
      <p className="text-sm text-destructive">{t("errors.loadFailed")}</p>
    );
  }

  const handleAssign = async () => {
    if (!newRole) return;
    try {
      await assignRole.mutateAsync({ role_code: newRole });
      toast.success(tDetail("roleAssigned"));
      setNewRole("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tDetail("roleAssignFailed"));
    }
  };

  const handleRevoke = async () => {
    try {
      await revokeRole.mutateAsync({});
      toast.success(tDetail("roleRevoked"));
      setConfirmRevoke(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tDetail("roleRevokeFailed"));
      setConfirmRevoke(false);
    }
  };

  const handleForceLogout = async () => {
    try {
      await forceLogout.mutateAsync({ reason: "admin force logout" });
      toast.success(tDetail("forceLogoutOk"));
      setConfirmLogout(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tDetail("forceLogoutFailed"));
      setConfirmLogout(false);
    }
  };

  const handleArchive = async () => {
    try {
      await updateUser.mutateAsync({ is_active: false });
      toast.success(tDetail("archived"));
      setConfirmArchive(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tDetail("archiveFailed"));
      setConfirmArchive(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Profile */}
      <Card>
        <CardHeader>
          <CardTitle>{tDetail("profileTitle")}</CardTitle>
          <CardDescription>{user.email}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          <Field label={tDetail("fullName")}>{user.full_name ?? "—"}</Field>
          <Field label={tDetail("locale")}>{user.locale}</Field>
          <Field label={tDetail("active")}>
            {user.is_active ? (
              <Badge>{tCommon("yes")}</Badge>
            ) : (
              <Badge variant="secondary">{tCommon("no")}</Badge>
            )}
          </Field>
          <Field label={tDetail("lastSignIn")}>
            {user.last_login_at
              ? new Date(user.last_login_at).toLocaleString()
              : "—"}
          </Field>
        </CardContent>
      </Card>

      {/* Roles asignados */}
      <Card>
        <CardHeader>
          <CardTitle>{tDetail("rolesTitle")}</CardTitle>
          <CardDescription>{tDetail("rolesSubtitle")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {user.role ? (
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-sm">
                {user.role.name}
              </Badge>
              <RbacGuard permissions={["users:assign_role"]}>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setConfirmRevoke(true)}
                >
                  <X className="h-4 w-4" /> {tDetail("revoke")}
                </Button>
              </RbacGuard>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{tDetail("noRole")}</p>
          )}
          <RbacGuard permissions={["users:assign_role"]}>
            <div className="flex items-end gap-2">
              <div className="grow space-y-1.5">
                <label className="text-xs text-muted-foreground">
                  {tDetail("assignRole")}
                </label>
                <Select value={newRole} onValueChange={setNewRole}>
                  <SelectTrigger className="w-full max-w-sm">
                    <SelectValue placeholder={tDetail("pickRole")} />
                  </SelectTrigger>
                  <SelectContent>
                    {(roles ?? [])
                      .filter((r) => r.code !== user.role?.code)
                      .map((r) => (
                        <SelectItem key={r.id} value={r.code}>
                          {r.name}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                type="button"
                onClick={handleAssign}
                disabled={!newRole || assignRole.isPending}
              >
                {assignRole.isPending ? tCommon("loading") : tDetail("assign")}
              </Button>
            </div>
          </RbacGuard>
        </CardContent>
      </Card>

      {/* Permisos efectivos */}
      <Card>
        <CardHeader>
          <CardTitle>{tDetail("permsTitle")}</CardTitle>
          <CardDescription>{tDetail("permsSubtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          {!rolePerms || rolePerms.permissions.length === 0 ? (
            <p className="text-sm text-muted-foreground">{tDetail("noPerms")}</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {rolePerms.permissions.map((p) => (
                <Badge
                  key={p.id}
                  variant="secondary"
                  className="font-mono text-[11px]"
                >
                  {p.code}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Audit timeline */}
      <RbacGuard permissions={["audit:read"]}>
        <Card>
          <CardHeader>
            <CardTitle>{tDetail("auditTitle")}</CardTitle>
            <CardDescription>{tDetail("auditSubtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            <AuditTimeline entityType="user" entityId={user.id} />
          </CardContent>
        </Card>
      </RbacGuard>

      {/* Acciones destructivas */}
      <Card>
        <CardHeader>
          <CardTitle>{tDetail("dangerTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {!user.last_login_at && (
            <RbacGuard permissions={["users:invite"]}>
              <Button
                type="button"
                variant="outline"
                disabled={resendInvite.isPending}
                onClick={async () => {
                  try {
                    await resendInvite.mutateAsync();
                    toast.success(tDetail("resendInviteOk"));
                  } catch (err) {
                    toast.error(err instanceof Error ? err.message : tDetail("resendInviteFailed"));
                  }
                }}
              >
                <Mail className="h-4 w-4" />
                {resendInvite.isPending ? tCommon("loading") : tDetail("resendInvite")}
              </Button>
            </RbacGuard>
          )}
          <RbacGuard permissions={["users:force_logout"]}>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmLogout(true)}
            >
              <LogOut className="h-4 w-4" /> {tDetail("forceLogout")}
            </Button>
          </RbacGuard>
          <RbacGuard permissions={["users:write"]}>
            <Button
              type="button"
              variant="destructive"
              onClick={() => setConfirmArchive(true)}
              disabled={!user.is_active}
            >
              {tDetail("archive")}
            </Button>
          </RbacGuard>
        </CardContent>
      </Card>

      {/* Confirms */}
      <ConfirmDialog
        open={confirmLogout}
        onOpenChange={setConfirmLogout}
        title={tDetail("confirmForceLogoutTitle")}
        description={tDetail("confirmForceLogoutDesc")}
        confirmLabel={tDetail("forceLogout")}
        destructive
        busy={forceLogout.isPending}
        onConfirm={handleForceLogout}
      />
      <ConfirmDialog
        open={confirmArchive}
        onOpenChange={setConfirmArchive}
        title={tDetail("confirmArchiveTitle")}
        description={tDetail("confirmArchiveDesc")}
        confirmLabel={tDetail("archive")}
        destructive
        busy={updateUser.isPending}
        onConfirm={handleArchive}
      />
      <ConfirmDialog
        open={confirmRevoke}
        onOpenChange={setConfirmRevoke}
        title={tDetail("confirmRevokeTitle")}
        description={tDetail("confirmRevokeDesc")}
        confirmLabel={tDetail("revoke")}
        destructive
        busy={revokeRole.isPending}
        onConfirm={handleRevoke}
      />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs uppercase text-muted-foreground">{label}</span>
      <span className="text-sm">{children}</span>
    </div>
  );
}
