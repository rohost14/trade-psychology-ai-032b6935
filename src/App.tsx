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
import OfflineBanner from "./components/OfflineBanner";
import { AdminAuthProvider } from "./contexts/AdminAuthContext";
import Layout from "./components/Layout";

// Eagerly load Dashboard — it's the first screen after login.
// All other routes are lazy-loaded, splitting the bundle into per-route chunks.
import Dashboard from "./pages/Dashboard";
const Welcome       = lazy(() => import("./pages/Welcome"));
const LandingLab    = lazy(() => import("./pages/_lab/LandingLab"));
const SoftPrecisionLab = lazy(() => import("./pages/_lab/SoftPrecisionLab"));
const SoftPrecisionWebLab = lazy(() => import("./pages/_lab/SoftPrecisionWebLab"));
const DesignLab     = lazy(() => import("./pages/_lab/DesignLab"));
const ImpersonateEntry = lazy(() => import("./pages/ImpersonateEntry"));
const Analytics     = lazy(() => import("./pages/Analytics"));
const Alerts        = lazy(() => import("./pages/Alerts"));
const MyRecord      = lazy(() => import("./pages/MyRecord"));
const Chat          = lazy(() => import("./pages/Chat"));
const Settings      = lazy(() => import("./pages/Settings"));
const Reports           = lazy(() => import("./pages/Reports"));
const Journal           = lazy(() => import("./pages/Journal"));
const MyRules           = lazy(() => import("./pages/MyRules"));
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
const AdminAdmins     = lazy(() => import("./pages/admin/AdminAdmins"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Fresh for 30s. Deliberately short: a trader who just closed a position and
      // opens Analytics must not read minutes-old numbers. The cost of refetching
      // often is low because the BACKEND cache answers most of them instantly and
      // is invalidated the moment a CompletedTrade lands (core/response_cache.py).
      // Meanwhile React Query serves the cached copy immediately and refreshes
      // behind it, so the user never sees a blank skeleton on back-navigation.
      staleTime: 30 * 1000,

      // Keep results in memory well past staleTime so returning to a page is
      // instant. This is what makes Dashboard -> Analytics -> Dashboard stop
      // re-rendering skeletons for data we had seconds ago.
      gcTime: 10 * 60 * 1000,

      // The axios interceptor already retries transient GETs once. React Query's
      // default is THREE more, so a genuine outage would fire six requests and
      // delay the error the user needs to see by several seconds.
      retry: false,
    },
  },
});

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
            <OfflineBanner />
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
                    <Route path="my-record" element={<MyRecord />} />

                    {/* Blowup Shield was replaced by My Record — keep the old
                        path working for anyone with it bookmarked. */}
                    <Route path="blowup-shield" element={<Navigate to="/my-record" replace />} />
                    {/* Merged into Alerts 2026-08-01. Redirect, not 404: the URL may be bookmarked. */}
                    <Route path="my-patterns" element={<Navigate to="/alerts" replace />} />
                    <Route path="chat" element={<Chat />} />
                    <Route path="reports" element={<Reports />} />
                    <Route path="journal" element={<Journal />} />
                    <Route path="my-rules" element={<MyRules />} />
                    <Route path="settings" element={<Settings />} />
                  </Route>
                  <Route path="impersonate" element={<ImpersonateEntry />} />
                  <Route path="welcome" element={<Welcome />} />
                  <Route path="landing-lab" element={<LandingLab />} />
                  <Route path="soft-lab" element={<SoftPrecisionLab />} />
                  <Route path="soft-web-lab" element={<SoftPrecisionWebLab />} />
                  <Route path="design-lab" element={<DesignLab />} />
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
                    <Route path="admins"        element={<AdminAdmins />} />
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
