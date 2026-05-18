"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  Atom,
  Award,
  BarChart2,
  BarChart3,
  Boxes,
  Building2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Coins,
  Construction,
  CreditCard,
  Database,
  DatabaseZap,
  FileText,
  FileUp,
  Flag,
  GitCompare,
  Home,
  Layers,
  LayoutGrid,
  Network,
  Package,
  PiggyBank,
  Receipt,
  ScrollText,
  Search,
  Settings,
  Shield,
  ShieldCheck,
  ShoppingBag,
  SlidersHorizontal,
  Sparkles,
  Sprout,
  Tags,
  Timer,
  Truck,
  TrendingUp,
  Users,
  Warehouse,
  Zap,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils/cn";
import { useUIStore } from "@/lib/stores/ui-store";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { MTMark } from "@/components/mt/logo";
import { MT } from "@/components/mt/tokens";
import { useTaxonomyRegistry } from "@/lib/hooks/use-taxonomy-registry";
import type { TaxonomyTypeRead } from "@/lib/api/endpoints/taxonomy-registry";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: string | number;
  permissions?: string[];
}

const SECTION_HOME: readonly NavItem[] = [
  { href: "/dashboard", label: "Inicio", icon: Home },
] as const;

const SECTION_CATALOGO: readonly NavItem[] = [
  { href: "/catalogo", label: "Productos", icon: LayoutGrid },
  { href: "/catalogo/validacion", label: "Validación", icon: GitCompare },
  { href: "/fichas", label: "Fichas técnicas", icon: FileText },
] as const;

const SECTION_COMPRAS: readonly NavItem[] = [
  { href: "/proveedores", label: "Proveedores", icon: Truck, permissions: ["suppliers:read"] },
  { href: "/compras/requisiciones", label: "Requisiciones", icon: ClipboardList, permissions: ["purchases:write"] },
  { href: "/compras/pedidos", label: "Pedidos de compra", icon: Package, permissions: ["purchases:write"] },
  { href: "/compras/recepciones", label: "Recepciones", icon: Truck, permissions: ["purchases:write"] },
  { href: "/inventario", label: "Inventario", icon: Boxes, permissions: ["purchases:write"] },
] as const;

const SECTION_PRECIOS: readonly NavItem[] = [
  { href: "/precios", label: "Precios", icon: Tags },
  { href: "/costos", label: "Cobertura costes", icon: Receipt, permissions: ["costs:read"] },
  { href: "/precios/aprobaciones", label: "Aprobaciones", icon: ShieldCheck },
] as const;

const SECTION_CANALES: readonly NavItem[] = [
  { href: "/canales", label: "Canales", icon: Network },
  { href: "/canales/marketplace/amazon", label: "Amazon UAE", icon: ShoppingBag },
] as const;

const SECTION_VENTAS: readonly NavItem[] = [
  { href: "/ventas/dashboard", label: "Dashboard O2C", icon: TrendingUp, permissions: ["sales:read"] },
  { href: "/ventas/pedidos", label: "Pedidos de venta", icon: ScrollText, permissions: ["sales:read"] },
  { href: "/billing/facturas", label: "Facturas", icon: FileText, permissions: ["sales:read"] },
  { href: "/billing/dashboard", label: "Dashboard Facturación", icon: CreditCard, permissions: ["sales:read"] },
] as const;

// EP-ERP-06 — Finanzas (US-ERP-06-01..09). Rol gerente.
// Orden R2R: configuración → operación diaria → AP → costes → reporting → planificación → cierre
const SECTION_FINANZAS: readonly NavItem[] = [
  { href: "/finanzas/cuentas", label: "Plan de cuentas", icon: Layers, permissions: ["gerente"] },
  { href: "/finanzas/periodos", label: "Períodos contables", icon: Timer, permissions: ["gerente"] },
  { href: "/finanzas/asientos", label: "Universal Journal", icon: ScrollText, permissions: ["gerente"] },
  { href: "/finanzas/ap-aging", label: "AP Aging", icon: ClipboardList, permissions: ["gerente"] },
  { href: "/finanzas/pagos", label: "Payment Runs", icon: PiggyBank, permissions: ["gerente"] },
  { href: "/finanzas/costos-estandar", label: "Costos estándar", icon: Coins, permissions: ["gerente"] },
  { href: "/finanzas/pl", label: "P&L", icon: TrendingUp, permissions: ["gerente"] },
  { href: "/finanzas/balance", label: "Balance Sheet", icon: BarChart3, permissions: ["gerente"] },
  { href: "/finanzas/copa", label: "CO-PA", icon: BarChart3, permissions: ["gerente"] },
  { href: "/finanzas/presupuestos", label: "Presupuestos", icon: Receipt, permissions: ["gerente"] },
  { href: "/finanzas/cierre", label: "Cierre de período", icon: ShieldCheck, permissions: ["gerente"] },
] as const;

const SECTION_QA: readonly NavItem[] = [
  { href: "/auditoria", label: "Auditoría", icon: ScrollText },
  { href: "/admin/pim-quality", label: "Calidad PIM", icon: BarChart2, permissions: ["admin:read"] },
] as const;

// Comparator (ADR-012) — research workstream. La entrada del sidebar sólo
// aparece si el flag build-time `NEXT_PUBLIC_COMPARATOR_ENABLED=true` está
// activo. En Fase 1 la página renderiza placeholder. Cuando Fase 1.5+
// active el subsistema, el flag DB `COMPARATOR_ENABLED` controla la lógica
// runtime y este toggle de UI puede pasar a `true` en el deploy.
const COMPARATOR_SIDEBAR_ENABLED =
  process.env["NEXT_PUBLIC_COMPARATOR_ENABLED"] === "true";

const COMPARATOR_NAV_ITEM: NavItem = {
  href: "/comparator",
  label: "Comparador",
  icon: Construction,
  badge: "Investigación",
};

const COMPARATOR_POOL_NAV_ITEM: NavItem = {
  href: "/comparator/pool",
  label: "Pool scrapeado",
  icon: DatabaseZap,
  permissions: ["matches:read"],
};

const COMPARATOR_INTELLIGENCE_NAV_ITEM: NavItem = {
  href: "/comparator/intelligence",
  label: "Price Intelligence",
  icon: Zap,
  permissions: ["products:read"],
};

// SISTEMA — tres sub-secciones
// 1. Importaciones: herramientas de carga de datos
const SECTION_SYS_IMPORTACIONES: readonly NavItem[] = [
  { href: "/imports", label: "Importar PIM", icon: FileUp },
  { href: "/imports/costs", label: "Importar costos", icon: FileUp, permissions: ["imports:write"] },
  { href: "/imports/materials", label: "Importar materiales", icon: FileUp, permissions: ["imports:write"] },
  { href: "/admin/imports", label: "Historial importaciones", icon: Database, permissions: ["imports:read"] },
] as const;

// 2. Configuración: parámetros de negocio y sistema
const SECTION_SYS_CONFIG: readonly NavItem[] = [
  { href: "/admin/divisas", label: "Divisas", icon: Coins, permissions: ["currencies:manage"] },
  { href: "/admin/fx-rates", label: "Tasas FX", icon: Coins, permissions: ["fx:read"] },
  { href: "/admin/almacenes", label: "Almacenes", icon: Warehouse, permissions: ["purchases:write"] },
  { href: "/admin/approval-rules", label: "Reglas aprobación", icon: ShieldCheck, permissions: ["purchases:write"] },
  { href: "/admin/condiciones-proveedor", label: "PIR / Condiciones", icon: ClipboardList, permissions: ["purchases:write"] },
  { href: "/admin/rule-engine", label: "Motor de reglas", icon: SlidersHorizontal, permissions: ["admin:read"] },
  { href: "/admin/flags", label: "Feature flags", icon: Flag, permissions: ["admin:read"] },
  { href: "/admin/calibrator", label: "Calibrator", icon: Sparkles, permissions: ["admin:read"] },
  { href: "/ajustes", label: "Ajustes generales", icon: Settings },
] as const;

// 3. Administración: usuarios y procesos técnicos
const SECTION_SYS_ADMIN: readonly NavItem[] = [
  { href: "/admin/usuarios", label: "Usuarios", icon: Users, permissions: ["users:read"] },
  { href: "/admin/jobs", label: "Jobs", icon: Timer, permissions: ["jobs:read"] },
  { href: "/admin/scraper", label: "Scraper", icon: Search, permissions: ["products:read"] },
  { href: "/admin/competitor-brands", label: "Marcas competidoras", icon: Building2, permissions: ["admin:read"] },
] as const;

// --- Mapeo data-driven: icon string (de ui_layout.icon en backend) → componente lucide.
// Cuando el backend agrega un nuevo taxonomy_type con ui_layout.icon='foo', la entrada
// se renderiza con FALLBACK_ICON si no hay match. Para soportar el icono nuevo, basta
// con añadir la clave aquí (única adición de código frontend al crecer).
const ICON_MAP: Record<string, LucideIcon> = {
  layers: Layers,
  sprout: Sprout,
  award: Award,
  atom: Atom,
  boxes: Boxes,
  shield: Shield,
  tags: Tags,
};
const FALLBACK_ICON: LucideIcon = Tags;

function resolveLabel(t: TaxonomyTypeRead, locale: string): string {
  const labels = t.label_i18n ?? {};
  return (
    labels[locale] ??
    labels.es ??
    labels.en ??
    t.slug.charAt(0).toUpperCase() + t.slug.slice(1)
  );
}

function resolveIcon(iconKey: string | undefined): LucideIcon {
  if (!iconKey) return FALLBACK_ICON;
  return ICON_MAP[iconKey] ?? FALLBACK_ICON;
}

// Todas las taxonomías enrutan a la página genérica data-driven. Las páginas
// legacy (`/admin/divisions`, `/admin/series`, `/admin/series-tiers`,
// `/admin/materials`) quedan como rutas huérfanas accesibles vía URL directa,
// pendientes de cleanup en un PR posterior.
function resolveHref(t: TaxonomyTypeRead): string {
  return `/admin/taxonomies/${t.slug}`;
}

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
        collapsed ? "justify-center py-2.5" : "px-3 py-[7px]",
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
      className="mt-mono px-3 pb-1 pt-3 text-[10px] uppercase tracking-[0.6px]"
      style={{ color: MT.ink4 }}
    >
      {children}
    </div>
  );
}

// Skeleton placeholders mientras el registry carga — evita "flash" del sidebar
// expandiéndose cuando llegan los items.
function SidebarTaxonomySkeleton({ collapsed }: { collapsed: boolean }) {
  return (
    <>
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className={cn(
            "flex items-center gap-2.5",
            collapsed ? "justify-center py-2.5" : "px-3 py-[7px]",
          )}
        >
          <div
            className="size-[15px] shrink-0 animate-pulse rounded"
            style={{ background: MT.border }}
          />
          {!collapsed ? (
            <div
              className="h-3 flex-1 animate-pulse rounded"
              style={{ background: MT.border }}
            />
          ) : null}
        </div>
      ))}
    </>
  );
}

export function Sidebar() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const toggle = useUIStore((s) => s.toggleSidebar);
  const collapsed = !sidebarOpen;
  const tShell = useTranslations("shell");
  const locale = useLocale();

  // Data-driven taxonomy items para sección SISTEMA.
  const { data: taxonomyTypes, isLoading: taxonomyLoading } = useTaxonomyRegistry();

  const taxonomyNavItems: NavItem[] = (taxonomyTypes ?? [])
    .filter((t) => t.active)
    .sort((a, b) => a.display_order - b.display_order)
    .map((t) => ({
      href: resolveHref(t),
      label: resolveLabel(t, locale),
      icon: resolveIcon(t.ui_layout?.icon),
      permissions: ["admin:taxonomy"],
    }));

  return (
    <aside
      className={cn(
        "relative hidden flex-col border-r bg-mt-surface transition-[width] duration-200 ease-out md:flex",
        collapsed ? "md:w-[64px]" : "md:w-[248px]",
      )}
      style={{ borderColor: MT.border }}
      aria-label="Primary"
    >
      <div className="mt-brand-stripe h-[3px]" />

      <div
        className={cn(
          "flex items-center gap-2.5 border-b",
          collapsed ? "justify-center px-2 py-3.5" : "px-4 py-3.5",
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

      <nav className={cn("flex flex-1 flex-col gap-px overflow-y-auto", collapsed ? "px-2 py-3" : "px-3 py-3")}>
        {SECTION_HOME.map((item) => (
          <NavLink key={item.href} item={item} collapsed={collapsed} />
        ))}

        <SectionLabel collapsed={collapsed}>Catálogo</SectionLabel>
        {SECTION_CATALOGO.map((item) => (
          <NavLink key={item.href} item={item} collapsed={collapsed} />
        ))}

        <SectionLabel collapsed={collapsed}>Compras</SectionLabel>
        {SECTION_COMPRAS.map((item) => (
          <NavLink key={item.href} item={item} collapsed={collapsed} />
        ))}

        <SectionLabel collapsed={collapsed}>Precios</SectionLabel>
        {SECTION_PRECIOS.map((item) => (
          <NavLink key={item.href} item={item} collapsed={collapsed} />
        ))}

        <SectionLabel collapsed={collapsed}>Canales</SectionLabel>
        {SECTION_CANALES.map((item) => (
          <NavLink key={item.href} item={item} collapsed={collapsed} />
        ))}

        <RbacGuard permissions={["sales:read"]}>
          <SectionLabel collapsed={collapsed}>Ventas</SectionLabel>
          {SECTION_VENTAS.map((item) => (
            <NavLink key={item.href} item={item} collapsed={collapsed} />
          ))}
        </RbacGuard>

        <RbacGuard permissions={["gerente"]}>
          <SectionLabel collapsed={collapsed}>Finanzas</SectionLabel>
          {SECTION_FINANZAS.map((item) => (
            <NavLink key={item.href} item={item} collapsed={collapsed} />
          ))}
        </RbacGuard>

        <SectionLabel collapsed={collapsed}>Calidad</SectionLabel>
        {SECTION_QA.map((item) => (
          <NavLink key={item.href} item={item} collapsed={collapsed} />
        ))}
        {COMPARATOR_SIDEBAR_ENABLED ? (
          <NavLink
            key={COMPARATOR_NAV_ITEM.href}
            item={COMPARATOR_NAV_ITEM}
            collapsed={collapsed}
          />
        ) : null}
        <NavLink
          key={COMPARATOR_POOL_NAV_ITEM.href}
          item={COMPARATOR_POOL_NAV_ITEM}
          collapsed={collapsed}
        />
        <NavLink
          key={COMPARATOR_INTELLIGENCE_NAV_ITEM.href}
          item={COMPARATOR_INTELLIGENCE_NAV_ITEM}
          collapsed={collapsed}
        />

        <SectionLabel collapsed={collapsed}>Importaciones</SectionLabel>
        {SECTION_SYS_IMPORTACIONES.map((item) => (
          <NavLink key={item.href} item={item} collapsed={collapsed} />
        ))}

        <SectionLabel collapsed={collapsed}>Taxonomías</SectionLabel>
        {/* Data-driven desde /taxonomies/registry. Agregar una nueva dimensión =
            INSERT en taxonomy_types + reload — sin tocar código frontend. */}
        {taxonomyLoading && !taxonomyTypes ? (
          <SidebarTaxonomySkeleton collapsed={collapsed} />
        ) : (
          taxonomyNavItems.map((item) => (
            <NavLink key={`tax-${item.href}`} item={item} collapsed={collapsed} />
          ))
        )}

        <SectionLabel collapsed={collapsed}>Configuración</SectionLabel>
        {SECTION_SYS_CONFIG.map((item) => (
          <NavLink key={item.href} item={item} collapsed={collapsed} />
        ))}

        <SectionLabel collapsed={collapsed}>Administración</SectionLabel>
        {SECTION_SYS_ADMIN.map((item) => (
          <NavLink key={item.href} item={item} collapsed={collapsed} />
        ))}
      </nav>

      <div
        className={cn(
          "flex items-center gap-2.5 border-t",
          collapsed ? "justify-center px-2 py-3" : "px-4 py-3.5",
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
