#!/bin/bash
# Sigil Backend Deployment Script
# Usage: ./deploy.sh [railway|render|fly|manual]

set -e

PROVIDER=${1:-manual}

echo "🚀 Deploying Sigil Backend to $PROVIDER..."

# Run tests first
echo "📋 Running tests..."
python -m pytest tests/unit/ -v --tb=short
if [ $? -ne 0 ]; then
    echo "❌ Tests failed. Aborting deployment."
    exit 1
fi

case $PROVIDER in
    railway)
        echo "🚂 Deploying to Railway..."
        if ! command -v railway &> /dev/null; then
            echo "Installing Railway CLI..."
            npm install -g @railway/cli
        fi
        railway up
        ;;
    
    render)
        echo "🎨 Deploying to Render..."
        echo "Push to GitHub and Render will auto-deploy from render.yaml"
        git push origin main
        ;;
    
    fly)
        echo "🪰 Deploying to Fly.io..."
        if ! command -v flyctl &> /dev/null; then
            echo "Installing Fly CLI..."
            curl -L https://fly.io/install.sh | sh
        fi
        flyctl deploy
        ;;
    
    manual)
        echo "📦 Building for manual deployment..."
        
        # Create dist directory
        mkdir -p dist
        
        # Copy backend files
        cp -r src dist/
        cp requirements.txt dist/
        cp .env.production.template dist/.env.template
        
        # Create start script
        cat > dist/start.sh << 'STARTSCRIPT'
#!/bin/bash
pip install -r requirements.txt
uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
STARTSCRIPT
        chmod +x dist/start.sh
        
        echo "✅ Built to ./dist/"
        echo "Upload dist/ to your server and run ./start.sh"
        ;;
    
    *)
        echo "Unknown provider: $PROVIDER"
        echo "Usage: ./deploy.sh [railway|render|fly|manual]"
        exit 1
        ;;
esac

echo "✅ Deployment complete!"
