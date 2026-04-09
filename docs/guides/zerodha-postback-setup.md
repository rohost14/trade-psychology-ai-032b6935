# Zerodha Postback Configuration

## What are Postbacks?

Postbacks are webhooks sent by Zerodha when order status changes.
This enables real-time trade processing instead of polling.

## Setup Steps

### 1. Get Your Postback URL

Production: https://yourdomain.com/api/webhooks/zerodha/postback
Development: Use Cloudflare Tunnel for testing

### 2. Configure in Zerodha Developer Dashboard

1. Go to: https://developers.kite.trade/apps
2. Click your app
3. Under "Postback URL", enter your URL
4. Save

### 3. Important Notes

- Zerodha sends webhooks for ALL order status changes
- We process COMPLETE orders immediately
- Postback URL must be publicly accessible (no localhost)
- Zerodha doesn't retry failed postbacks
- Response must be fast (<5 seconds)

## Testing Postbacks

### Local Testing (Cloudflare Tunnel)
```bash
# Start tunnel pointing to backend
cloudflared tunnel --url http://localhost:8000

# Copy the https://xxx.trycloudflare.com URL
# Add /api/webhooks/zerodha/postback to it
# Configure in Zerodha dashboard
```

### Verify Postback Works

1. Place a test order in Zerodha Kite
2. Check backend logs:
   - Should see: "Received postback from Zerodha"
   - Should see: "Postback processed: {order_id}"
3. Check database:
   - Trade should appear immediately (no manual sync needed)

## Security

- Checksum verification ensures request is from Zerodha
- Invalid checksums are rejected (403)
- Logs all postback attempts
