/**
 * Service Worker for TradeMentor AI Push Notifications
 * Handles background push events and notification display
 */

// Cache name for offline support
const CACHE_NAME = 'tradementor-v1';

// Install event - cache critical assets
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  event.waitUntil(clients.claim());
});

// Push event - show notification
self.addEventListener('push', (event) => {
  console.log('[SW] Push received:', event);

  let data = {
    title: 'TradeMentor Alert',
    body: 'You have a new trading alert',
    icon: '/icon-192.png',
    badge: '/badge-72.png',
    tag: 'tradementor-alert',
    data: {}
  };

  // Parse push data if available
  if (event.data) {
    try {
      const payload = event.data.json();
      data = {
        title: payload.title || data.title,
        body: payload.body || data.body,
        icon: payload.icon || data.icon,
        badge: payload.badge || data.badge,
        tag: payload.tag || data.tag,
        data: payload.data || {},
        // Additional notification options
        requireInteraction: payload.severity === 'danger',
        actions: payload.actions || getDefaultActions(payload.pattern_type),
        vibrate: payload.severity === 'danger' ? [200, 100, 200, 100, 200] : [200, 100, 200]
      };
    } catch (e) {
      console.error('[SW] Error parsing push data:', e);
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: data.icon,
    badge: data.badge,
    tag: data.tag,
    data: data.data,
    requireInteraction: data.requireInteraction || false,
    actions: data.actions || [],
    vibrate: data.vibrate
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification click event
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Notification clicked:', event);

  event.notification.close();

  const action = event.action;
  const data = event.notification.data || {};

  let targetUrl = '/dashboard';

  // Handle different actions
  if (action === 'view_alert') {
    targetUrl = '/dashboard';
  } else if (action === 'take_break') {
    targetUrl = '/dashboard?cooldown=true';
  } else if (action === 'view_analysis') {
    targetUrl = '/analytics';
  } else if (data.url) {
    targetUrl = data.url;
  }

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Check if app is already open
        for (const client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            client.postMessage({
              type: 'NOTIFICATION_CLICKED',
              action: action,
              data: data
            });
            return client.focus();
          }
        }
        // Open new window if not open
        if (clients.openWindow) {
          return clients.openWindow(targetUrl);
        }
      })
  );
});

// Notification close event
self.addEventListener('notificationclose', (event) => {
  console.log('[SW] Notification closed:', event);

  // Track dismissal for analytics
  const data = event.notification.data || {};
  if (data.alert_id) {
    // Could send analytics event here
    console.log('[SW] Alert dismissed:', data.alert_id);
  }
});

// Get default actions based on pattern type
function getDefaultActions(patternType) {
  const baseActions = [
    { action: 'view_alert', title: 'View Details' }
  ];

  switch (patternType) {
    case 'revenge_trading':
    case 'overtrading':
    case 'consecutive_loss':
      return [
        ...baseActions,
        { action: 'take_break', title: 'Take a Break' }
      ];
    case 'martingale':
    case 'tilt_loss_spiral':
      return [
        ...baseActions,
        { action: 'take_break', title: 'Stop Trading' }
      ];
    default:
      return baseActions;
  }
}

// Message handler for communication with main app
self.addEventListener('message', (event) => {
  console.log('[SW] Message received:', event.data);

  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
