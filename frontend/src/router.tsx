import { Navigate, createRootRouteWithContext, createRoute, createRouter, redirect } from "@tanstack/react-router";
import { LoginPage } from "@/pages/LoginPage";
import { AppLayout } from "@/pages/AppLayout";
import { DrugAnalysisPage } from "@/pages/DrugAnalysisPage";
import { InteractionsPage } from "@/pages/InteractionsPage";
import { PrescriptionPage } from "@/pages/PrescriptionPage";
import type { AuthContextValue } from "@/auth/AuthContext";

export interface RouterContext {
  auth: AuthContextValue;
}

const rootRoute = createRootRouteWithContext<RouterContext>()();

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => <Navigate to="/drug" />,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  beforeLoad: ({ context }) => {
    if (context.auth.isAuthenticated) throw redirect({ to: "/drug" });
  },
  component: LoginPage,
});

const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app-shell",
  beforeLoad: ({ context }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: "/login" });
  },
  component: AppLayout,
});

const drugRoute = createRoute({ getParentRoute: () => appRoute, path: "/drug", component: DrugAnalysisPage });
const interactionsRoute = createRoute({ getParentRoute: () => appRoute, path: "/interactions", component: InteractionsPage });
const prescriptionRoute = createRoute({ getParentRoute: () => appRoute, path: "/prescription", component: PrescriptionPage });

const routeTree = rootRoute.addChildren([indexRoute, loginRoute, appRoute.addChildren([drugRoute, interactionsRoute, prescriptionRoute])]);

export const router = createRouter({
  routeTree,
  context: { auth: undefined as unknown as AuthContextValue },
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
