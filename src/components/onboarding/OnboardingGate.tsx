/**
 * OnboardingGate — shows the OnboardingWizard once per real user account.
 * Skipped for guest mode (demo data).
 * Triggered after first successful sync (syncStatus === 'success').
 */
import { useState, useEffect } from 'react';
import { useBroker } from '@/contexts/BrokerContext';
import OnboardingWizard from './OnboardingWizard';

const ONBOARDING_DONE_KEY = 'tradementor_onboarding_done';

export default function OnboardingGate() {
  const { isConnected, isGuest, syncStatus, account } = useBroker();
  const [show, setShow] = useState(false);

  useEffect(() => {
    // Don't show for guest mode or if not connected / sync not done
    if (!isConnected || isGuest || syncStatus !== 'success' || !account?.id) return;

    // Check if this account has already completed onboarding
    const doneKey = `${ONBOARDING_DONE_KEY}_${account.id}`;
    if (localStorage.getItem(doneKey)) return;

    // Show wizard — let it appear once data is ready
    const timer = setTimeout(() => setShow(true), 600);
    return () => clearTimeout(timer);
  }, [isConnected, isGuest, syncStatus, account?.id]);

  if (!show || !account?.id) return null;

  const markDone = () => {
    localStorage.setItem(`${ONBOARDING_DONE_KEY}_${account.id}`, '1');
    setShow(false);
  };

  return (
    <OnboardingWizard
      brokerAccountId={account.id}
      onComplete={markDone}
      onSkip={markDone}
    />
  );
}
