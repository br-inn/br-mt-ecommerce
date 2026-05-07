"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import {
  useInviteUser,
  useRolesCatalog,
} from "@/lib/hooks/users-admin/use-users-admin";

const ROLE_CODES = [
  "comercial",
  "gerente_comercial",
  "ti_integracion",
  "champion",
  "backup_operator",
] as const;
type RoleCode = (typeof ROLE_CODES)[number];

const LOCALES = ["es", "en", "ar"] as const;
type Locale = (typeof LOCALES)[number];

export function InviteUserClient() {
  const t = useTranslations("admin.users.invite");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const invite = useInviteUser();
  const { data: roles } = useRolesCatalog();

  const schema = React.useMemo(
    () =>
      z.object({
        email: z.string().email(t("errors.email")),
        full_name: z.string().min(2, t("errors.fullName")).max(100),
        role_code: z.enum(ROLE_CODES),
        locale: z.enum(LOCALES),
      }),
    [t],
  );

  type Values = z.infer<typeof schema>;

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: "",
      full_name: "",
      role_code: "comercial",
      locale: "es",
    },
    mode: "onBlur",
  });

  const onSubmit = async (values: Values) => {
    try {
      const created = await invite.mutateAsync({
        email: values.email,
        full_name: values.full_name,
        role_code: values.role_code,
        locale: values.locale,
      });
      toast.success(t("success"));
      router.push(`/admin/usuarios/${created.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("errors.failed"));
    }
  };

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>{t("formTitle")}</CardTitle>
        <CardDescription>{t("formSubtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-4"
          onSubmit={form.handleSubmit(onSubmit)}
          noValidate
        >
          <div className="space-y-1.5">
            <Label htmlFor="email">{t("email")}</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              {...form.register("email")}
            />
            {form.formState.errors.email ? (
              <p className="text-xs text-destructive">
                {form.formState.errors.email.message}
              </p>
            ) : null}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="full_name">{t("fullName")}</Label>
            <Input id="full_name" {...form.register("full_name")} />
            {form.formState.errors.full_name ? (
              <p className="text-xs text-destructive">
                {form.formState.errors.full_name.message}
              </p>
            ) : null}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>{t("role")}</Label>
              <Select
                value={form.watch("role_code")}
                onValueChange={(v) =>
                  form.setValue("role_code", v as RoleCode, {
                    shouldValidate: true,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(roles ?? [])
                    .filter((r) =>
                      (ROLE_CODES as readonly string[]).includes(r.code),
                    )
                    .map((r) => (
                      <SelectItem key={r.id} value={r.code}>
                        {r.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>{t("locale")}</Label>
              <Select
                value={form.watch("locale")}
                onValueChange={(v) =>
                  form.setValue("locale", v as Locale, {
                    shouldValidate: true,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LOCALES.map((l) => (
                    <SelectItem key={l} value={l}>
                      {l.toUpperCase()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => router.push("/admin/usuarios")}
            >
              {tCommon("cancel")}
            </Button>
            <Button type="submit" disabled={invite.isPending}>
              {invite.isPending ? tCommon("loading") : t("submit")}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
