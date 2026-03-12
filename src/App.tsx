import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./components/ThemeProvider";
import { AlertProvider } from "./contexts/AlertContext";
import { BrokerProvider } from "./contexts/BrokerContext";
import { WebSocketProvider } from "./contexts/WebSocketContext";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Analytics from "./pages/Analytics";
import BlowupShield from "./pages/BlowupShield";
import MyPatterns from "./pages/MyPatterns";
import Chat from "./pages/Chat";
import Settings from "./pages/Settings";
import MoneySaved from "./pages/MoneySaved";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <ThemeProvider>
    <QueryClientProvider client={queryClient}>
      <BrokerProvider>
        <WebSocketProvider>
        <AlertProvider>
          <TooltipProvider>
            <Toaster />
            <Sonner />
            <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
              <Routes>
                <Route path="/" element={<Layout />}>
                  <Route index element={<Navigate to="/dashboard" replace />} />
                  <Route path="dashboard" element={<Dashboard />} />
                  <Route path="analytics" element={<Analytics />} />
                  <Route path="blowup-shield" element={<BlowupShield />} />
                  <Route path="my-patterns" element={<MyPatterns />} />
                  <Route path="chat" element={<Chat />} />
                  <Route path="money-saved" element={<MoneySaved />} />
                  <Route path="settings" element={<Settings />} />
                </Route>
                <Route path="*" element={<NotFound />} />
              </Routes>
            </BrowserRouter>
          </TooltipProvider>
        </AlertProvider>
        </WebSocketProvider>
      </BrokerProvider>
    </QueryClientProvider>
  </ThemeProvider>
);

export default App;
