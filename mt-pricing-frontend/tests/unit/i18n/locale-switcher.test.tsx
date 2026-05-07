import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import * as React from "react";

// Mock del Server Action y del router de Next.
const setLocaleMock = vi.fn().mockResolvedValue({ ok: true, locale: "en" });
const refreshMock = vi.fn();

vi.mock("@/app/actions/locale", () => ({
  setLocale: (next: "es" | "en") => setLocaleMock(next),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: refreshMock,
    push: vi.fn(),
    replace: vi.fn(),
  }),
}));

import { LocaleSwitcher } from "@/components/shell/locale-switcher";

const messages = {
  shell: {
    locale: "Idioma",
  },
};

function renderWithIntl(locale: "es" | "en" = "es") {
  return render(
    <NextIntlClientProvider locale={locale} messages={messages} timeZone="UTC">
      <LocaleSwitcher />
    </NextIntlClientProvider>,
  );
}

describe("LocaleSwitcher", () => {
  beforeEach(() => {
    setLocaleMock.mockClear();
    refreshMock.mockClear();
  });

  it("renderiza el trigger con el código del locale activo", () => {
    renderWithIntl("es");
    const trigger = screen.getByTestId("locale-switcher-trigger");
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveTextContent("ES");
  });

  it("muestra ambos idiomas (es, en) al abrir el dropdown", async () => {
    const user = userEvent.setup();
    renderWithIntl("es");
    await user.click(screen.getByTestId("locale-switcher-trigger"));
    expect(await screen.findByTestId("locale-switcher-item-es")).toBeInTheDocument();
    expect(screen.getByTestId("locale-switcher-item-en")).toBeInTheDocument();
  });

  it("llama a setLocale + router.refresh al elegir otro idioma", async () => {
    const user = userEvent.setup();
    renderWithIntl("es");
    await user.click(screen.getByTestId("locale-switcher-trigger"));
    const enItem = await screen.findByTestId("locale-switcher-item-en");
    await user.click(enItem);
    // setLocale es async dentro de startTransition: esperamos al microtask.
    await Promise.resolve();
    await Promise.resolve();
    expect(setLocaleMock).toHaveBeenCalledWith("en");
  });

  it("no llama a setLocale si el idioma elegido es el actual", async () => {
    const user = userEvent.setup();
    renderWithIntl("es");
    await user.click(screen.getByTestId("locale-switcher-trigger"));
    const esItem = await screen.findByTestId("locale-switcher-item-es");
    await user.click(esItem);
    expect(setLocaleMock).not.toHaveBeenCalled();
  });
});
