"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { UploadCloud } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { RbacGuard } from "@/components/auth/rbac-guard";
import {
  useRunFromFixture,
  useUploadPim,
} from "@/lib/hooks/imports-admin/use-imports-admin";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UploadSheet({ open, onOpenChange }: Props) {
  const t = useTranslations("admin.imports.upload");
  const tCommon = useTranslations("common");
  const upload = useUploadPim();
  const fixture = useRunFromFixture();

  const [file, setFile] = React.useState<File | null>(null);
  const [dragOver, setDragOver] = React.useState(false);

  const reset = () => {
    setFile(null);
    setDragOver(false);
  };

  const handleUpload = async () => {
    if (!file) return;
    try {
      await upload.mutateAsync({ file });
      toast.success(t("uploadOk"));
      reset();
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("uploadFailed"));
    }
  };

  const handleFixture = async () => {
    try {
      await fixture.mutateAsync();
      toast.success(t("fixtureOk"));
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("fixtureFailed"));
    }
  };

  return (
    <Sheet
      open={open}
      onOpenChange={(o) => {
        if (!o) reset();
        onOpenChange(o);
      }}
    >
      <SheetContent className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{t("title")}</SheetTitle>
          <SheetDescription>{t("subtitle")}</SheetDescription>
        </SheetHeader>

        <div
          className={`mt-6 flex flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed p-8 text-center transition-colors ${
            dragOver
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/30 bg-muted/20"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files?.[0];
            if (f) setFile(f);
          }}
        >
          <UploadCloud className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{t("dropHere")}</p>
          <input
            id="upload-pim"
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setFile(f);
            }}
          />
          <label htmlFor="upload-pim">
            <Button asChild type="button" variant="outline" size="sm">
              <span>{t("pickFile")}</span>
            </Button>
          </label>
          {file ? (
            <p className="mt-2 text-xs font-mono">
              {file.name} ({(file.size / 1024).toFixed(1)} KB)
            </p>
          ) : null}
        </div>

        <SheetFooter className="mt-6 flex-col gap-2 sm:flex-col sm:justify-stretch sm:space-x-0">
          <Button
            type="button"
            onClick={handleUpload}
            disabled={!file || upload.isPending}
          >
            {upload.isPending ? tCommon("loading") : t("upload")}
          </Button>
          <RbacGuard permissions={["imports:execute"]}>
            <Button
              type="button"
              variant="secondary"
              onClick={handleFixture}
              disabled={fixture.isPending}
            >
              {fixture.isPending ? tCommon("loading") : t("runFixture")}
            </Button>
          </RbacGuard>
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
          >
            {tCommon("cancel")}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
