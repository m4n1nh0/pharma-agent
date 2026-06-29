import { RouterProvider } from "@tanstack/react-router";
import { useAuth } from "@/auth/AuthContext";
import { router } from "@/router";

export function App() {
  const auth = useAuth();
  return <RouterProvider router={router} context={{ auth }} />;
}
