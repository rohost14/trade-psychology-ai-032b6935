/**
 * Push Notification Service for TradeMentor AI
 * Handles service worker registration, permission requests, and subscription management
 */

import { api } from './api';

// VAPID public key - must match backend
// Generate with: npx web-push generate-vapid-keys
const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY || '';

export interface PushSubscriptionData {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
}

export interface NotificationPayload {
  title: string;
  body: string;
  icon?: string;
  badge?: string;
  tag?: string;
  data?: Record<string, unknown>;
  severity?: 'danger' | 'caution' | 'info';
  pattern_type?: string;
  actions?: Array<{ action: string; title: string }>;
}

class PushNotificationService {
  private registration: ServiceWorkerRegistration | null = null;
  private subscription: PushSubscription | null = null;

  /**
   * Check if push notifications are supported
   */
  isSupported(): boolean {
    return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  }

  /**
   * Get current permission status
   */
  getPermissionStatus(): NotificationPermission {
    if (!this.isSupported()) return 'denied';
    return Notification.permission;
  }

  /**
   * Check if already subscribed
   */
  async isSubscribed(): Promise<boolean> {
    if (!this.isSupported()) return false;

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      return subscription !== null;
    } catch (error) {
      console.error('Error checking subscription:', error);
      return false;
    }
  }

  /**
   * Register service worker
   */
  async registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
    if (!this.isSupported()) {
      console.warn('Push notifications not supported');
      return null;
    }

    try {
      this.registration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/'
      });
      // Service Worker registered successfully
      return this.registration;
    } catch (error) {
      console.error('Service Worker registration failed:', error);
      return null;
    }
  }

  /**
   * Request notification permission
   */
  async requestPermission(): Promise<NotificationPermission> {
    if (!this.isSupported()) {
      return 'denied';
    }

    try {
      const permission = await Notification.requestPermission();
      // Permission response received
      return permission;
    } catch (error) {
      console.error('Error requesting permission:', error);
      return 'denied';
    }
  }

  /**
   * Subscribe to push notifications
   */
  async subscribe(): Promise<PushSubscriptionData | null> {
    if (!this.isSupported()) {
      console.warn('Push not supported');
      return null;
    }

    if (!VAPID_PUBLIC_KEY) {
      console.error('VAPID public key not configured');
      return null;
    }

    try {
      // Ensure service worker is registered
      const registration = await navigator.serviceWorker.ready;

      // Always unsubscribe first to force a fresh subscription with current VAPID key.
      // This prevents stale subscriptions (created with old/empty keys) from silently failing.
      const existing = await registration.pushManager.getSubscription();
      if (existing) {
        await existing.unsubscribe();
      }

      // Create new subscription with current VAPID key
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: this.urlBase64ToUint8Array(VAPID_PUBLIC_KEY).buffer as ArrayBuffer
      });

      this.subscription = subscription;

      // Convert to JSON format for backend
      const subscriptionJson = subscription.toJSON();
      return {
        endpoint: subscriptionJson.endpoint!,
        keys: {
          p256dh: subscriptionJson.keys!.p256dh!,
          auth: subscriptionJson.keys!.auth!
        }
      };
    } catch (error) {
      console.error('Error subscribing to push:', error);
      return null;
    }
  }

  /**
   * Unsubscribe from push notifications
   */
  async unsubscribe(): Promise<boolean> {
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();

      if (subscription) {
        await subscription.unsubscribe();
        this.subscription = null;
        // Unsubscribed from push notifications
        return true;
      }

      return false;
    } catch (error) {
      console.error('Error unsubscribing:', error);
      return false;
    }
  }

  /**
   * Send subscription to backend
   */
  async saveSubscription(
    subscriptionData: PushSubscriptionData,
    brokerAccountId: string
  ): Promise<boolean> {
    try {
      await api.post('/api/notifications/subscribe', {
        subscription: subscriptionData,
      });
      return true;
    } catch (error) {
      console.error('Error saving subscription:', error);
      return false;
    }
  }

  /**
   * Remove subscription from backend
   */
  async removeSubscription(brokerAccountId: string): Promise<boolean> {
    try {
      await api.post('/api/notifications/unsubscribe', {});
      return true;
    } catch (error) {
      console.error('Error removing subscription:', error);
      return false;
    }
  }

  /**
   * Full setup flow: register SW, request permission, subscribe, save to backend
   */
  async setup(brokerAccountId: string): Promise<{
    success: boolean;
    permission: NotificationPermission;
    subscribed: boolean;
  }> {
    const result = {
      success: false,
      permission: 'denied' as NotificationPermission,
      subscribed: false
    };

    if (!this.isSupported()) {
      console.warn('Push notifications not supported on this browser');
      return result;
    }

    // 1. Register service worker
    const registration = await this.registerServiceWorker();
    if (!registration) {
      return result;
    }

    // 2. Request permission
    result.permission = await this.requestPermission();
    if (result.permission !== 'granted') {
      return result;
    }

    // 3. Subscribe to push
    const subscriptionData = await this.subscribe();
    if (!subscriptionData) {
      return result;
    }

    // 4. Save to backend
    const saved = await this.saveSubscription(subscriptionData, brokerAccountId);
    if (!saved) {
      return result;
    }

    result.success = true;
    result.subscribed = true;
    return result;
  }

  /**
   * Show a local notification (for testing)
   */
  async showLocalNotification(payload: NotificationPayload): Promise<boolean> {
    if (Notification.permission !== 'granted') {
      return false;
    }

    try {
      const registration = await navigator.serviceWorker.ready;
      await registration.showNotification(payload.title, {
        body: payload.body,
        icon: payload.icon || '/icon-192.png',
        badge: payload.badge || '/badge-72.png',
        tag: payload.tag || 'local-notification',
        data: payload.data,
        requireInteraction: payload.severity === 'danger',
      } as NotificationOptions);
      return true;
    } catch (error) {
      console.error('Error showing notification:', error);
      return false;
    }
  }

  /**
   * Convert VAPID key from base64 to Uint8Array
   */
  private urlBase64ToUint8Array(base64String: string): Uint8Array {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding)
      .replace(/-/g, '+')
      .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }

    return outputArray;
  }
}

// Singleton instance
export const pushNotifications = new PushNotificationService();

// Auto-register service worker on module load (non-blocking)
if (typeof window !== 'undefined') {
  window.addEventListener('load', () => {
    pushNotifications.registerServiceWorker().catch(console.error);
  });
}
