"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { authApi } from "@/lib/api/endpoints/auth";

const schema = z.object({
  full_name: z.string().min(2).max(100),
  locale: z.enum(["es", "en", "ar"]),
});

export default function AccountPage() {
  const t = useTranslations("auth.account");
  const { user, refresh, signOut, isLoading } = useAuth();
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      full_name: user?.fullName ?? "",
      locale: (user?.locale ?? "es") as "es" | "en" | "ar",
    },
  });

  useEffect(() => {
    if (user) {
      form.reset({
        full_name: user.fullName ?? "",
        locale: user.locale,
      });
    }
  }, [user, form]);

  if (isLoading) return <p>{t("loading")}</p>;
  if (!user) return null;

  const onSubmit = async (values: z.infer<typeof schema>) => {
    setSubmitting(true);
    try {
      await authApi.updateMe(values);
      await refresh();
      toast.success(t("updated"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{user.email}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("profileTitle")}</CardTitle>
          <CardDescription>{t("profileSubtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
            <div className="space-y-2">
              <Label htmlFor="full_name">{t("fullName")}</Label>
              <Input
                id="full_name"
                {...form.register("full_name")}
                disabled={submitting}
              />
              {form.formState.errors.full_name && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.full_name.message}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="locale">{t("locale")}</Label>
              <select
                id="locale"
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                {...form.register("locale")}
                disabled={submitting}
              >
                <option value="es">Español</option>
                <option value="en">English</option>
                <option value="ar">العربية</option>
              </select>
            </div>
            <Button type="submit" disabled={submitting}>
              {t("save")}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("permissionsTitle")}</CardTitle>
          <CardDescription>
            {user.role
              ? t("rolePrefix") + ` ${user.role.name} (${user.role.code})`
              : t("noRole")}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {user.permissions.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("noPermissions")}</p>
          ) : (
            user.permissions.map((p) => (
              <Badge key={p} variant="secondary">
                {p}
              </Badge>
            ))
          )}
        </CardContent>
        <CardFooter>
          <Button variant="destructive" onClick={signOut}>
            {t("signOut")}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
