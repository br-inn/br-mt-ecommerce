"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

import { createSupabaseBrowserClient } from "@/lib/supabase/client";
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
import { Separator } from "@/components/ui/separator";

type Mode = "magic-link" | "password";

const magicLinkSchema = z.object({
  email: z.string().email(),
});

const passwordSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

export default function LoginPage() {
  const t = useTranslations("auth.login");
  const tErrors = useTranslations("auth.errors");
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";
  const reason = searchParams.get("reason");

  const [mode, setMode] = useState<Mode>("magic-link");
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<z.infer<typeof passwordSchema>>({
    resolver: zodResolver(mode === "magic-link" ? magicLinkSchema : passwordSchema),
    defaultValues: { email: "", password: "" },
    mode: "onTouched",
  });

  const supabase = createSupabaseBrowserClient();

  const onSubmit = async (values: z.infer<typeof passwordSchema>) => {
    setSubmitting(true);
    try {
      if (mode === "magic-link") {
        const origin = window.location.origin;
        const { error } = await supabase.auth.signInWithOtp({
          email: values.email,
          options: {
            emailRedirectTo: `${origin}/auth/callback?next=${encodeURIComponent(next)}`,
          },
        });
        if (error) {
          toast.error(error.message);
          return;
        }
        toast.success(t("magicLinkSent"));
        return;
      }

      const { error } = await supabase.auth.signInWithPassword({
        email: values.email,
        password: values.password,
      });
      if (error) {
        if (error.status === 400) {
          toast.error(tErrors("invalidCredentials"));
        } else {
          toast.error(error.message);
        }
        return;
      }
      router.replace(next);
      router.refresh();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>{t("title")}</CardTitle>
          <CardDescription>{t("subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          {reason === "revoked" && (
            <p className="mb-4 rounded border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">
              {tErrors("sessionRevoked")}
            </p>
          )}
          <form
            className="space-y-4"
            onSubmit={form.handleSubmit(onSubmit)}
            noValidate
          >
            <div className="space-y-2">
              <Label htmlFor="email">{t("email")}</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="user@empresa.com"
                {...form.register("email")}
                aria-invalid={!!form.formState.errors.email}
                disabled={submitting}
              />
              {form.formState.errors.email && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.email.message}
                </p>
              )}
            </div>
            {mode === "password" && (
              <div className="space-y-2">
                <Label htmlFor="password">{t("password")}</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  {...form.register("password")}
                  aria-invalid={!!form.formState.errors.password}
                  disabled={submitting}
                />
                {form.formState.errors.password && (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.password.message}
                  </p>
                )}
              </div>
            )}
            <Button type="submit" className="w-full" disabled={submitting}>
              {mode === "magic-link" ? t("magicLink") : t("submit")}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex flex-col gap-2">
          <Separator />
          <Button
            type="button"
            variant="ghost"
            className="w-full"
            onClick={() =>
              setMode((m) => (m === "magic-link" ? "password" : "magic-link"))
            }
            disabled={submitting}
          >
            {mode === "magic-link" ? t("usePassword") : t("useMagicLink")}
          </Button>
          <a
            href="/reset-password"
            className="text-center text-xs text-muted-foreground hover:underline"
          >
            {t("forgot")}
          </a>
        </CardFooter>
      </Card>
    </div>
  );
}
