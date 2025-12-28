# Cloudflare Deployment Guide

This guide explains how to deploy your TextSense FastAPI application to Cloudflare using Cloudflare Workers for Platforms.

## Prerequisites

1. **Cloudflare Account**: Sign up at [cloudflare.com](https://cloudflare.com)
2. **Wrangler CLI**: Cloudflare's command-line tool
3. **Python 3.10+**: For local development
4. **Git**: For version control

## Option 1: Cloudflare Workers for Platforms (Recommended)

Cloudflare Workers for Platforms supports Python natively, making it ideal for FastAPI applications.

### Step 1: Install Wrangler CLI

```bash
npm install -g wrangler
# or
pip install wrangler
```

### Step 2: Authenticate with Cloudflare

```bash
wrangler login
```

This will open your browser to authenticate with Cloudflare.

### Step 3: Configure Your Project

The `wrangler.toml` file is already configured. You may need to update:
- `name`: Your worker name (currently "textsense")
- Routes: Configure in Cloudflare dashboard after deployment

**Note**: Cloudflare Workers for Platforms is currently in beta/early access. If you don't have access:
1. Request access through Cloudflare dashboard
2. Or use the alternative deployment method (see Option 2 below)

### Step 4: Set Environment Variables

Set your environment variables as secrets in Cloudflare:

```bash
# Set secrets (these are encrypted and not visible in wrangler.toml)
wrangler secret put HF_INFERENCE_URL
wrangler secret put HF_OCR_URL
wrangler secret put OPENAI_SPEECH_API_KEY
wrangler secret put OPENAI_SPEECH_TOKEN
wrangler secret put FLUX_API_KEY
wrangler secret put FLUX_TEXT_URL
wrangler secret put FLUX_IMAGE_BASE
# Optional secrets
wrangler secret put RECAPTCHA_SITE_KEY
wrangler secret put RECAPTCHA_SECRET_KEY
wrangler secret put CONTACT_EMAIL
wrangler secret put HF_API_KEY
wrangler secret put ADSENSE_PUB_ID
```

Or set them via Cloudflare Dashboard:
1. Go to Workers & Pages → Your Worker → Settings → Variables
2. Add each environment variable under "Environment Variables" or "Secrets"

### Step 5: Deploy

```bash
# Deploy to production
wrangler deploy

# Deploy to development environment
wrangler deploy --env development
```

### Step 6: Configure Custom Domain (Optional)

1. Go to Cloudflare Dashboard → Workers & Pages → Your Worker
2. Click "Triggers" → "Custom Domains"
3. Add your domain
4. Update DNS records as instructed

## Option 2: Cloudflare Pages with Functions

If Workers for Platforms is not available, you can use Cloudflare Pages with Python Functions.

### Step 1: Install Wrangler CLI

```bash
npm install -g wrangler
```

### Step 2: Authenticate

```bash
wrangler login
```

### Step 3: Deploy via Cloudflare Dashboard

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Navigate to "Workers & Pages"
3. Click "Create Application" → "Pages" → "Connect to Git"
4. Connect your GitHub/GitLab repository
5. Configure build settings:
   - **Build command**: `pip install -r requirements.txt`
   - **Build output directory**: `.` (root)
   - **Python version**: 3.10
6. Set environment variables in the dashboard
7. Deploy

### Step 4: Configure Functions

Cloudflare Pages Functions require a specific structure. You may need to adapt your FastAPI routes to work with Pages Functions format.

## Environment Variables Reference

| Variable | Description | Required | Set As Secret |
|----------|-------------|----------|---------------|
| `HF_INFERENCE_URL` | Hugging Face Space for AI detection | Yes | Yes |
| `HF_OCR_URL` | Hugging Face Space for OCR | Yes | Yes |
| `OPENAI_SPEECH_API_KEY` | OpenAI API key for TTS | Yes | Yes |
| `OPENAI_SPEECH_TOKEN` | OpenAI token | No | Yes |
| `FLUX_API_KEY` | Flux API key for image generation | Yes | Yes |
| `FLUX_TEXT_URL` | Flux text endpoint URL | No | No |
| `FLUX_IMAGE_BASE` | Flux image base URL | No | No |
| `RECAPTCHA_SITE_KEY` | reCAPTCHA site key | No | No |
| `RECAPTCHA_SECRET_KEY` | reCAPTCHA secret key | No | Yes |
| `CONTACT_EMAIL` | Contact email address | No | No |
| `HF_API_KEY` | Hugging Face API key (optional) | No | Yes |
| `ADSENSE_PUB_ID` | AdSense publisher ID | No | No |
| `TOKENIZERS_PARALLELISM` | Tokenizers parallelism | No | No |

## Deployment Commands

### Deploy to Production
```bash
wrangler deploy
```

### Deploy to Development
```bash
wrangler deploy --env development
```

### View Logs
```bash
wrangler tail
```

### Test Locally
```bash
wrangler dev
```

## Important Notes

1. **Python Runtime**: Cloudflare Workers for Platforms uses Python 3.10+. Ensure your code is compatible.

2. **File Uploads**: Cloudflare Workers have limits on request/response sizes. Large file uploads may need special handling.

3. **Execution Time**: Cloudflare Workers have execution time limits:
   - Free plan: 10ms CPU time, 50ms wall-clock time
   - Paid plans: Up to 50 seconds CPU time
   
   Your application may need optimization for long-running operations.

4. **Static Files**: Static files are served efficiently through Cloudflare's CDN. The current static file mounting should work well.

5. **Rate Limiting**: Your application has built-in rate limiting. Cloudflare also provides additional rate limiting at the edge.

6. **Caching**: Cloudflare provides edge caching. Your cache headers are already configured for optimal performance.

## Troubleshooting

### Issue: "Python runtime not available"
- Ensure you're using Cloudflare Workers for Platforms (not regular Workers)
- Check that `compatibility_flags = ["python_workers"]` is in `wrangler.toml`

### Issue: "Module not found"
- Ensure all dependencies are in `requirements.txt`
- Check that the build process installs dependencies correctly

### Issue: "Timeout errors"
- Check execution time limits
- Optimize long-running operations
- Consider using Cloudflare Queues for background tasks

### Issue: "Environment variables not found"
- Ensure variables are set as secrets (for sensitive data)
- Check variable names match exactly (case-sensitive)
- Verify environment scope (production vs development)

## Migration from Render

When migrating from Render:

1. **Export environment variables** from Render dashboard
2. **Set them in Cloudflare** using `wrangler secret put` or dashboard
3. **Update DNS** to point to Cloudflare
4. **Test thoroughly** before switching DNS
5. **Monitor logs** using `wrangler tail` or dashboard

## Cost Comparison

- **Render Free Tier**: Limited hours, spins down after inactivity
- **Cloudflare Workers Free Tier**: 100,000 requests/day, always-on
- **Cloudflare Workers Paid**: $5/month for 10M requests

Cloudflare is generally more cost-effective for high-traffic applications.

## Support

For Cloudflare-specific issues:
- [Cloudflare Workers Docs](https://developers.cloudflare.com/workers/)
- [Cloudflare Community](https://community.cloudflare.com/)
- [Wrangler CLI Docs](https://developers.cloudflare.com/workers/wrangler/)

