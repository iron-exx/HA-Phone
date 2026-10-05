import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { ThemeProvider } from "@/components/ThemeProvider";
import { TooltipProvider } from "@/components/ui/tooltip";

export function LocationProbe() {
  const { pathname } = useLocation();
  return <output data-testid="location">{pathname}</output>;
}

export function renderAt(
  ui: ReactElement,
  { route = "/", basename }: { route?: string; basename?: string } = {},
): RenderResult {
  return render(
    <ThemeProvider>
      <TooltipProvider>
        <MemoryRouter initialEntries={[route]} basename={basename}>
          {ui}
          <LocationProbe />
        </MemoryRouter>
      </TooltipProvider>
    </ThemeProvider>,
  );
}
