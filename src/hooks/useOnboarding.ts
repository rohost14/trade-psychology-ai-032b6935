import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import { useBroker } from '@/contexts/BrokerContext';

interface OnboardingStatus {
  completed: boolean;
  currentStep: number;
  totalSteps: number;
}

interface UserProfile {
  id: string;
  displayName?: string;
  experienceLevel: string;
  tradingStyle: string;
  riskTolerance: string;
  preferredInstruments: string[];
  preferredSegments: string[];
  dailyLossLimit?: number;
  dailyTradeLimit?: number;
  cooldownAfterLoss: number;
  knownWeaknesses: string[];
  pushEnabled: boolean;
  alertSensitivity: string;
  aiPersona: string;
}

export function useOnboarding() {
  const { account, isConnected } = useBroker();
  const [isLoading, setIsLoading] = useState(true);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);

  const checkOnboardingStatus = useCallback(async () => {
    if (!account?.id || !isConnected) {
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      const response = await api.get('/api/profile/');

      const { profile: profileData, needs_onboarding } = response.data;

      setProfile({
        id: profileData.id,
        displayName: profileData.display_name,
        experienceLevel: profileData.experience_level,
        tradingStyle: profileData.trading_style,
        riskTolerance: profileData.risk_tolerance,
        preferredInstruments: profileData.preferred_instruments || [],
        preferredSegments: profileData.preferred_segments || [],
        dailyLossLimit: profileData.daily_loss_limit,
        dailyTradeLimit: profileData.daily_trade_limit,
        cooldownAfterLoss: profileData.cooldown_after_loss || 15,
        knownWeaknesses: profileData.known_weaknesses || [],
        pushEnabled: profileData.push_enabled,
        alertSensitivity: profileData.alert_sensitivity,
        aiPersona: profileData.ai_persona,
      });

      setStatus({
        completed: profileData.onboarding_completed,
        currentStep: profileData.onboarding_step,
        totalSteps: 5,
      });

      // Show onboarding if not completed and connected
      setShowOnboarding(needs_onboarding);
    } catch (error) {
      console.error('Failed to check onboarding status:', error);
      // Don't show onboarding on error
      setShowOnboarding(false);
    } finally {
      setIsLoading(false);
    }
  }, [account?.id, isConnected]);

  useEffect(() => {
    checkOnboardingStatus();
  }, [checkOnboardingStatus]);

  const completeOnboarding = useCallback(() => {
    setShowOnboarding(false);
    setStatus(prev => prev ? { ...prev, completed: true } : null);
    // Refresh profile
    checkOnboardingStatus();
  }, [checkOnboardingStatus]);

  const skipOnboarding = useCallback(() => {
    setShowOnboarding(false);
    setStatus(prev => prev ? { ...prev, completed: true } : null);
  }, []);

  const reopenOnboarding = useCallback(() => {
    setShowOnboarding(true);
  }, []);

  return {
    isLoading,
    showOnboarding,
    status,
    profile,
    completeOnboarding,
    skipOnboarding,
    reopenOnboarding,
    refreshProfile: checkOnboardingStatus,
  };
}
