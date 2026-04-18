import { Suspense, lazy } from "react";
import { isGuestMode } from "./lib/guestMode";
import { AUTH_TOKEN_KEY } from "./lib/api";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./components/ThemeProvider";
import { AlertProvider } from "./contexts/AlertContext";
import { BrokerProvider } from "./contexts/BrokerContext";
import { WebSocketProvider } from "./contexts/WebSocketContext";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AdminAuthProvider } from "./contexts/AdminAuthContext";
import Layout from "./components/Layout";

// Eagerly load Dashboard — it's the first screen after login.
// All other routes are lazy-loaded, splitting the bundle into per-route chunks.
import Dashboard from "./pages/Dashboard";
const Welcome       = lazy(() => import("./pages/Welcome"));
const Analytics     = lazy(() => import("./pages/Analytics"));
const Alerts        = lazy(() => import("./pages/Alerts"));
const BlowupShield  = lazy(() => import("./pages/BlowupShield"));
const MyPatterns    = lazy(() => import("./pages/MyPatterns"));
const Chat          = lazy(() => import("./pages/Chat"));
const Settings      = lazy(() => import("./pages/Settings"));
const PortfolioRadar  = lazy(() => import("./pages/PortfolioRadar"));
const Guardrails      = lazy(() => import("./pages/Guardrails"));
const PortfolioChat   = lazy(() => import("./pages/PortfolioChat"));
const Reports           = lazy(() => import("./pages/Reports"));
const Personalization   = lazy(() => import("./pages/Personalization"));
const Discipline        = lazy(() => import("./pages/Discipline"));
const TermsOfService = lazy(() => import("./pages/TermsOfService"));
const PrivacyPolicy  = lazy(() => import("./pages/PrivacyPolicy"));
const Maintenance   = lazy(() => import("./pages/Maintenance"));
const NotFound      = lazy(() => import("./pages/NotFound"));

// Admin panel — loaded lazily, separate auth context
const AdminLogin      = lazy(() => import("./pages/admin/AdminLogin"));
const AdminLayout     = lazy(() => import("./pages/admin/AdminLayout"));
const AdminOverview   = lazy(() => import("./pages/admin/AdminOverview"));
const AdminUsers      = lazy(() => import("./pages/admin/AdminUsers"));
const AdminUserDetail = lazy(() => import("./pages/admin/AdminUserDetail"));
const AdminSystem     = lazy(() => import("./pages/admin/AdminSystemHealth"));
const AdminInsights   = lazy(() => import("./pages/admin/AdminInsights"));
const AdminConfig     = lazy(() => import("./pages/admin/AdminConfig"));
const AdminAuditLog   = lazy(() => import("./pages/admin/AdminAuditLog"));
const AdminBroadcast  = lazy(() => import("./pages/admin/AdminBroadcast"));

const queryClient = new QueryClient();

const App = () => (
  <ErrorBoundary>
  <ThemeProvider>
    <QueryClientProvider client={queryClient}>
      <BrokerProvider>
        <WebSocketProvider>
        <AlertProvider>
          <TooltipProvider>
            <Toaster />
            <Sonner />
            <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
              <Suspense fallback={null}>
                <Routes>
                  <Route path="/" element={<Layout />}>
                    <Route
                      index
                      element={
                        <Navigate
                          to={
                            localStorage.getItem(AUTH_TOKEN_KEY) || isGuestMode()
                              ? '/dashboard'
                              : '/welcome'
                          }
                          replace
                        />
                      }
                    />
                    <Route path="dashboard" element={<Dashboard />} />
                    <Route path="analytics" element={<Analytics />} />
                    <Route path="alerts" element={<Alerts />} />
                    <Route path="blowup-shield" element={<BlowupShield />} />
                    <Route path="my-patterns" element={<MyPatterns />} />
                    <Route path="chat" element={<Chat />} />
                    <Route path="portfolio-radar" element={<PortfolioRadar />} />
                    <Route path="guardrails" element={<Guardrails />} />
                    <Route path="portfolio-chat" element={<PortfolioChat />} />
                    <Route path="reports" element={<Reports />} />
                    <Route path="personalization" element={<Personalization />} />
                    <Route path="discipline" element={<Discipline />} />
                    <Route path="settings" element={<Settings />} />
                  </Route>
                  <Route path="welcome" element={<Welcome />} />
                  <Route path="terms" element={<TermsOfService />} />
                  <Route path="privacy" element={<PrivacyPolicy />} />
                  <Route path="maintenance" element={<Maintenance />} />
                  {/* Admin panel — own ErrorBoundary so admin errors don't crash the main app */}
                  <Route path="admin" element={<ErrorBoundary><AdminAuthProvider><AdminLayout /></AdminAuthProvider></ErrorBoundary>}>
                    <Route index element={<Navigate to="/admin/overview" replace />} />
                    <Route path="overview"      element={<AdminOverview />} />
                    <Route path="users"         element={<AdminUsers />} />
                    <Route path="users/:id"     element={<AdminUserDetail />} />
                    <Route path="system"        element={<AdminSystem />} />
                    <Route path="insights"      element={<AdminInsights />} />
                    <Route path="broadcast"     element={<AdminBroadcast />} />
                    <Route path="audit-log"     element={<AdminAuditLog />} />
                    <Route path="config"        element={<AdminConfig />} />
                  </Route>
                  <Route path="admin/login" element={<ErrorBoundary><AdminAuthProvider><AdminLogin /></AdminAuthProvider></ErrorBoundary>} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </BrowserRouter>
          </TooltipProvider>
        </AlertProvider>
        </WebSocketProvider>
      </BrokerProvider>
    </QueryClientProvider>
  </ThemeProvider>
  </ErrorBoundary>
);

export default App;
