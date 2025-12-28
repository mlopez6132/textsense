#!/bin/bash
# Cloudflare Deployment Script for TextSense

set -e

echo "🚀 TextSense Cloudflare Deployment Script"
echo "========================================"
echo ""

# Check if wrangler is installed
if ! command -v wrangler &> /dev/null; then
    echo "❌ Wrangler CLI is not installed."
    echo "Install it with: npm install -g wrangler"
    exit 1
fi

echo "✅ Wrangler CLI found"
echo ""

# Check if user is logged in
if ! wrangler whoami &> /dev/null; then
    echo "⚠️  Not logged in to Cloudflare. Logging in..."
    wrangler login
fi

echo "✅ Authenticated with Cloudflare"
echo ""

# Ask for environment
read -p "Deploy to (production/development) [production]: " env
env=${env:-production}

if [ "$env" = "development" ]; then
    DEPLOY_ENV="--env development"
    echo "📦 Deploying to development environment..."
else
    DEPLOY_ENV=""
    echo "📦 Deploying to production environment..."
fi

echo ""
echo "⚠️  Make sure you've set all required secrets:"
echo "   - HF_INFERENCE_URL"
echo "   - HF_OCR_URL"
echo "   - OPENAI_SPEECH_API_KEY"
echo "   - FLUX_API_KEY"
echo ""
read -p "Continue with deployment? (y/n) [y]: " confirm
confirm=${confirm:-y}

if [ "$confirm" != "y" ]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo "🚀 Deploying..."
wrangler deploy $DEPLOY_ENV

echo ""
echo "✅ Deployment complete!"
echo ""
echo "View logs with: wrangler tail"
echo "Test locally with: wrangler dev"





