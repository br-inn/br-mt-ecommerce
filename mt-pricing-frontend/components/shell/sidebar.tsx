"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Award,
  Boxes,
  ChevronLeft,
  ChevronRight,
  Coins,
  Database,
  FileUp,
  Flag,
  GitCompare,
  Home,
  Layers,
  LayoutGrid,
  Network,
  Receipt,
  ScrollText,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Sprout,
  Tags,
  Timer,
  Truck,
  Users,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils/cn";
import { useUIStore } from "@/lib/stores/ui-store";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { MTMark } from "@/components/mt/logo";
import { MT } from "@/components/mt/tokens";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: string | number;
  permissions?: string[];
}

const SECTION_OPS: readonly NavItem[] = [
  { href: "/dashboard", label: "Inicio", icon: Home },
  { href: "/catalogo", label: "Catálogo", icon: LayoutGrid, badge: "224" },
  { href: "/proveedores", label: "Proveedores", icon: Truck, badge: "3", permissions: ["suppliers:read"] },
  { href: "/imports", label: "Importer PIM", icon: FileUp },
  { href: "/imports/costs", label: "Importer costos", icon: FileUp, permissions: ["imports:write"] },
  { href: "/imports/materials", label: "Importer materiales", icon: FileUp, permissions: ["imports:write"] },
  { href: "/precios", label: "Precios", icon: Tags },
  { href: "/canales", label: "Canales", icon: Network, badge: "5" },
  { href: "/precios/aprobaciones", label: "Aprobaciones", icon: ShieldCheck, badge: 45 },
  { href: "/costos", label: "Cobertura costes", icon: Receipt, permissions: ["costs:read"] },
] as const;

const SECTION_QA: readonly NavItem[] = [
  { href: "/catalogo/validacion", label: "Validación", icon: GitCompare },
  { href: "/auditoria", label: "Auditoría", icon: ScrollText },
] as const;

const SECTION_SYS: readonly NavItem[] = [
  { href: "/admin/divisions", label: "Divisiones", icon: Layers, permissions: ["admin:taxonomy"] },
  { href: "/admin/series", label: "Series", icon: Sprout, permissions: ["admin:taxonomy"] },
  { href: "/admin/series-tiers", label: "Tiers", icon: Award, permissions: ["admin:taxonomy"] },
  { href: "/admin/materials", label: "Materiales", icon: Boxes, permissions: ["admin:taxonomy"] },
  { href: "/admin/divisas", label: "Divisas", icon: Coins, permissions: ["currencies:manage"] },
  { href: "/admin/fx-rates", label: "Tasas FX", icon: Coins, permissions: ["fx:read"] },
  { href: "/admin/usuarios", label: "Usuarios", icon: Users, permissions: ["users:read"] },
  { href: "/admin/jobs", label: "Jobs", icon: Timer, permissions: ["jobs:read"] },
  { href: "/admin/imports", label: "Importaciones", icon: Database, permissions: ["imports:read"] },
  { href: "/admin/flags", label: "Feature flags", icon: Flag, permissions: ["admin:read"] },
  { href: "/admin/calibrator", label: "Calibrator", icon: Sparkles, permissions: ["admin:read"] },
  { href: "/ajustes", label: "Configuración", icon: Settings },
] as const;

function NavLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const pathname = usePathname();
  const active = pathname === item.href || pathname?.startsWith(`${item.href}/`) || false;
  const Icon = item.icon;
  const node = (
    <Link
      href={item.href}
      title={collapsed ? item.label : undefined}
      className={cn(
        "relative flex items-center gap-2.5 rounded-md text-[13px]",
        collapsed ? "justify-center py-2" : "px-2.5 py-[7px]",
        active ? "font-semibold" : "font-normal",
      )}
      style={{
        color: active ? MT.brandDeep : MT.ink3,
        background: active ? MT.brandSoft : "transparent",
      }}
    >
      {active && !collapsed ? (
        <span
          className="absolute -left-2 top-1.5 bottom-1.5 w-[3px] rounded-[2px]"
          style={{ background: MT.brand }}
        />
      ) : null}
      <Icon
        className="size-[15px] shrink-0"
        style={{ color: active ? MT.brand : MT.ink3 }}
      />
      {!collapsed ? <span className="flex-1 truncate">{item.label}</span> : null}
      {!collapsed && item.badge !== undefined ? (
        <span
          className="mt-mono rounded-[4px] border px-1.5 py-px text-[11px] leading-[1.4]"
          style={{
            color: active ? MT.brandDeep : MT.ink3,
            background: active ? "white" : MT.surface,
            borderColor: active ? MT.brandBorder : MT.border,
          }}
        >
          {item.badge}
        </span>
      ) : null}
      {collapsed && item.badge !== undefined ? (
        <span
          className="absolute right-1.5 top-0.5 size-1.5 rounded-full"
          style={{ background: MT.brand }}
        />
      ) : null}
    </Link>
  );
  if (!item.permissions?.length) return node;
  return <RbacGuard permissions={item.permissions}>{node}</RbacGuard>;
}

function SectionLabel({ children, collapsed }: { children: string; collapsed: boolean }) {
  if (collapsed) {
    return (
      <div
        className="my-1 mx-1.5 border-t"
        style={{ borderColor: MT.border }}
        aria-hidden
      />
    );
  }
  return (
    <div
      className="mt-mono px-2.5 pb-1 pt-2 text-[10px] uppercase tracking-[0.6px]"
      style={{ color: MT.ink4 }}
    >
      {children}
    </div>
  );
}

export function Sidebar() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const toggle = useUIStore((s) => s.toggleSidebar);
  const collapsed = !sidebarOpen;
  const tShell = useTranslations("shell");

  return (
    <aside
      className={cn(
        "relative hidden flex-col border-r bg-mt-surface transition-[width] duration-200 ease-out md:flex",
        collapsed ? "md:w-[60px]" : "md:w-[220px]",
      )}
      style={{ borderColor: MT.border }}
      aria-label="Primary"
    >
      <div className="mt-brand-stripe h-[3px]" />

      <div
        className={cn(
          "flex items-center gap-2.5 border-b",
          collapsed ? "justify-center px-1.5 py-3" : "px-3.5 py-3",
        )}
        style={{ borderColor: MT.border }}
      >
        <MTMark size={28} />
        {!collapsed ? (
          <div className="flex min-w-0 flex-1 flex-col leading-tight">
            <span className="text-[13px] font-bold tracking-[-0.1px]" style={{ color: MT.brandDeep }}>
              MT e-Commerce
            </span>
            <span className="mt-mono text-[10.5px]" style={{ color: MT.ink4 }}>
              MDM · Pricing
            </span>
          </div>
        ) : null}
      </div>

      {/* Floating collapse toggle */}
      <button
        type="button"
        onClick={toggle}
        aria-label={tShell("toggleSidebar")}
        className="absolute -right-2.5 top-[22px] z-10 grid size-5 place-items-center rounded-full border bg-mt-surface shadow-[0_1px_2px_rgba(15,23,42,0.08)]"
        style={{ borderColor: MT.border, color: MT.ink3 }}
      >
        {collapsed ? (
          <ChevronRight className="size-[11px]" strokeWidth={2.2} />
        ) : (
          <ChevronLeft className="size-[11px]" strokeWidth={2.2} />
        )}
      </button>

      <nav className={cn("flex flex-1 flex-col gap-px", collapsed ? "px-1.5 py-2" : "p-2")}>
        <SectionLabel collapsed={collapsed}>Operación</SectionLabel>
        {SECTION_OPS.map((item) => (
          <NavLink key={item.href} item={item} collapsed={collapsed} />
        ))}

        <SectionLabel collapsed={collapsed}>Calidad</SectionLabel>
        {SECTION_QA.map((item) => (
          <NavLink key={item.href} item={item} collapsed={collapsed} />
        ))}

        <SectionLabel collapsed={collapsed}>Sistema</SectionLabel>
        {SECTION_SYS.map((item) => (
          <NavLink key={item.href} item={item} collapsed={collapsed} />
        ))}
      </nav>

      <div
        className={cn(
          "flex items-center gap-2.5 border-t",
          collapsed ? "justify-center px-2 py-2" : "px-3 py-3",
        )}
        style={{ borderColor: MT.border }}
      >
        <span
          className="grid size-7 place-items-center rounded-full text-[11px] font-semibold text-white"
          style={{
            background: `linear-gradient(135deg, ${MT.brandDeep}, ${MT.brandLight})`,
          }}
        >
          PS
        </span>
        {!collapsed ? (
          <>
            <div className="flex min-w-0 flex-1 flex-col leading-tight">
              <span className="text-[12.5px] font-medium" style={{ color: MT.ink }}>
                Pablo Sierra
              </span>
              <span className="text-[11px]" style={{ color: MT.ink3 }}>
                Comercial · Online
              </span>
            </div>
            <Search className="size-[13px]" style={{ color: MT.ink4 }} />
          </>
        ) : null}
      </div>
    </aside>
  );
}
