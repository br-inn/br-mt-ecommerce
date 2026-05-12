"use client";

import * as React from "react";
import {
  Download,
  FileText,
  Image as ImageIcon,
  PlayCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils/cn";
import { useAssetLinksForOwner } from "@/lib/hooks/use-asset-links";
import {
  classifyRole,
  type AssetLinkOwnerType,
  type AssetLinkRole,
  type AssetLinkWithAsset,
} from "@/lib/api/types-assets-extended";

interface Props {
  ownerType: AssetLinkOwnerType;
  ownerId: string;
  allowedRoles?: AssetLinkRole[];
  className?: string;
}

function getAssetUrl(link: AssetLinkWithAsset): string {
  return (
    link.asset.urls?.original ??
    link.asset.original_url ??
    ""
  );
}

function getThumbUrl(link: AssetLinkWithAsset): string {
  return (
    link.asset.urls?.thumb_400 ??
    link.asset.urls?.thumb_800 ??
    link.asset.urls?.original ??
    link.asset.original_url ??
    ""
  );
}

function roleLabel(role: AssetLinkRole): string {
  // Etiqueta human-readable; mantiene snake → title case sin i18n para no
  // imponer namespaces nuevos al consumidor.
  return role
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function AssetGalleryPolymorphic({
  ownerType,
  ownerId,
  allowedRoles,
  className,
}: Props) {
  const { data, isLoading, isError, refetch } = useAssetLinksForOwner(
    ownerType,
    ownerId,
  );
  const [previewLink, setPreviewLink] = React.useState<AssetLinkWithAsset | null>(
    null,
  );

  const links = React.useMemo(() => {
    const raw = data ?? [];
    const filtered = allowedRoles
      ? raw.filter((l) => allowedRoles.includes(l.role))
      : raw;
    return [...filtered].sort((a, b) => a.order_index - b.order_index);
  }, [data, allowedRoles]);

  const groups = React.useMemo(() => {
    const map = new Map<AssetLinkRole, AssetLinkWithAsset[]>();
    for (const l of links) {
      const arr = map.get(l.role) ?? [];
      arr.push(l);
      map.set(l.role, arr);
    }
    return map;
  }, [links]);

  const roles = React.useMemo(() => Array.from(groups.keys()), [groups]);

  if (isLoading) {
    return (
      <div
        className={cn(
          "grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4",
          className,
        )}
        data-testid="asset-gallery-loading"
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="aspect-square w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div
        className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground"
        data-testid="asset-gallery-error"
      >
        <p>Error cargando assets.</p>
        <Button variant="link" onClick={() => refetch()}>
          Reintentar
        </Button>
      </div>
    );
  }

  if (links.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed p-12 text-center text-sm text-muted-foreground"
        data-testid="asset-gallery-empty"
      >
        <ImageIcon className="h-10 w-10" aria-hidden />
        <p>Sin assets vinculados.</p>
      </div>
    );
  }

  return (
    <>
      <Tabs
        defaultValue={roles[0] ?? "all"}
        className={cn("w-full", className)}
        data-testid="asset-gallery-polymorphic"
      >
        <TabsList className="flex h-auto flex-wrap gap-1">
          {roles.map((role) => (
            <TabsTrigger
              key={role}
              value={role}
              data-testid={`asset-gallery-tab-${role}`}
            >
              {roleLabel(role)}
              <Badge variant="secondary" className="ml-2">
                {groups.get(role)?.length ?? 0}
              </Badge>
            </TabsTrigger>
          ))}
        </TabsList>

        {roles.map((role) => {
          const kind = classifyRole(role);
          const items = groups.get(role) ?? [];
          return (
            <TabsContent key={role} value={role} className="mt-4">
              <RoleSection
                role={role}
                kind={kind}
                items={items}
                onPreview={(l) => setPreviewLink(l)}
              />
            </TabsContent>
          );
        })}
      </Tabs>

      <Dialog
        open={!!previewLink}
        onOpenChange={(open) => !open && setPreviewLink(null)}
      >
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {previewLink ? roleLabel(previewLink.role) : "Preview"}
            </DialogTitle>
            <DialogDescription>
              {previewLink?.asset.alt_text ?? previewLink?.asset.caption ?? ""}
            </DialogDescription>
          </DialogHeader>
          {previewLink ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={getAssetUrl(previewLink)}
              alt={previewLink.asset.alt_text ?? ""}
              className="h-auto max-h-[70vh] w-full object-contain"
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

interface SectionProps {
  role: AssetLinkRole;
  kind: "image" | "pdf" | "video";
  items: AssetLinkWithAsset[];
  onPreview: (link: AssetLinkWithAsset) => void;
}

function RoleSection({ role, kind, items, onPreview }: SectionProps) {
  if (kind === "image") {
    return (
      <ul
        className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
        data-testid={`asset-gallery-section-${role}`}
      >
        {items.map((link) => (
          <li
            key={link.id}
            className="group relative overflow-hidden rounded-lg border bg-muted"
          >
            <button
              type="button"
              onClick={() => onPreview(link)}
              className="block w-full text-left"
              aria-label={`Preview ${link.asset.alt_text ?? link.role}`}
              data-testid={`asset-thumb-${link.id}`}
            >
              <div className="relative aspect-square w-full">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={getThumbUrl(link)}
                  alt={link.asset.alt_text ?? ""}
                  className="h-full w-full object-cover transition-transform group-hover:scale-105"
                  loading="lazy"
                />
              </div>
            </button>
            <div className="flex items-center justify-between p-2 text-xs text-muted-foreground">
              <span className="truncate">
                {link.asset.alt_text ?? link.asset.caption ?? ""}
              </span>
              <span aria-hidden>#{link.order_index}</span>
            </div>
          </li>
        ))}
      </ul>
    );
  }

  if (kind === "pdf") {
    return (
      <ul
        className="flex flex-col gap-2"
        data-testid={`asset-gallery-section-${role}`}
      >
        {items.map((link) => {
          const href = getAssetUrl(link);
          return (
            <li
              key={link.id}
              className="flex items-center justify-between gap-3 rounded-lg border p-3"
            >
              <div className="flex min-w-0 items-center gap-3">
                <FileText className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    {link.asset.alt_text ?? link.asset.storage_path}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {roleLabel(link.role)}
                  </p>
                </div>
              </div>
              <Button asChild size="sm" variant="outline" disabled={!href}>
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  data-testid={`asset-download-${link.id}`}
                >
                  <Download className="mr-1 h-3 w-3" aria-hidden />
                  Download PDF
                </a>
              </Button>
            </li>
          );
        })}
      </ul>
    );
  }

  // video
  return (
    <ul
      className="grid grid-cols-1 gap-4 md:grid-cols-2"
      data-testid={`asset-gallery-section-${role}`}
    >
      {items.map((link) => {
        const href = getAssetUrl(link);
        return (
          <li
            key={link.id}
            className="overflow-hidden rounded-lg border bg-muted"
          >
            {href ? (
              <iframe
                src={href}
                title={link.asset.alt_text ?? "Video"}
                className="aspect-video w-full"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                data-testid={`asset-video-${link.id}`}
              />
            ) : (
              <div className="flex aspect-video w-full items-center justify-center text-muted-foreground">
                <PlayCircle className="h-10 w-10" aria-hidden />
              </div>
            )}
            <div className="p-2 text-xs text-muted-foreground">
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline"
              >
                {link.asset.alt_text ?? href}
              </a>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
