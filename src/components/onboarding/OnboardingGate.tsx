/**
 * OnboardingGate — shows the OnboardingWizard once per real user account.
 * Skipped for guest mode. Triggered after first successful sync.
 *
 * Source of truth: backend UserProfile.onboarding_completed (persisted in DB).
 * localStorage is a fast-path cache — avoids the API call on subsequent loads.
 * If cache is missing (cleared storage, new device), we fall back to the API.
 */
import { useState, useEffect, useRef } from 'react';
import { useBroker } from '@/contexts/BrokerContext';
import OnboardingWizard from './OnboardingWizard';
import { api } from '@/lib/api';

const ONBOARDING_DONE_KEY = 'tradementor_onboarding_done';

export default function OnboardingGate() {
  const { isConnected, isGuest, syncStatus, account } = useBroker();
  const [show, setShow] = useState(false);
  const checkedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!isConnected || isGuest || syncStatus !== 'success' || !account?.id) return;

    const doneKey = `${ONBOARDING_DONE_KEY}_${account.id}`;

    // Fast path: localStorage cache says done — skip API call entirely
    if (localStorage.getItem(doneKey)) return;

    // Prevent duplicate checks if this effect fires twice (React strict mode)
    if (checkedRef.current === account.id) return;
    checkedRef.current = account.id;

    // Authoritative check: backend UserProfile.onboarding_completed
    api.get('/api/profile/')
      .then(({ data }) => {
        if (data.needs_onboarding) {
          setTimeout(() => setShow(true), 600);
        } else {
          // Backend says completed — write to localStorage so we skip the API call next time
          localStorage.setItem(doneKey, '1');
        }
      })
      .catch(() => {
        // On API error, don't block the user — silently skip
      });
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
