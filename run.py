#!/usr/bin/env python3
"""
Startup script for the AI Text Detector web application.
Provides options to run the app in different modes.
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = ['flask', 'torch', 'transformers']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nTo install dependencies, run:")
        print("   pip install -r requirements.txt")
        return False
    
    print("✅ All required packages are installed")
    return True

def check_model():
    """Check if the AI model is available."""
    model_name = "desklib/ai-text-detector-v1.01"
    
    try:
        # Try to import transformers to check if it's available
        from transformers import AutoTokenizer, AutoConfig
        print(f"✅ Transformers library available")
        
        # Note: The model will be downloaded automatically when first used
        print(f"ℹ️  Model '{model_name}' will be downloaded automatically on first use")
        print("   (This may take a few minutes on first run)")
        return True
        
    except ImportError:
        print(f"⚠️  Transformers library not available")
        print("   Install with: pip install transformers")
        return False

def run_tests():
    """Run the test suite."""
    print("🧪 Running tests...")
    try:
        result = subprocess.run([sys.executable, 'test_app.py'], 
                              capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def run_app(host='0.0.0.0', port=5000, debug=False):
    """Run the Flask application."""
    print(f"🚀 Starting AI Text Detector on http://{host}:{port}")
    print("   Press Ctrl+C to stop the server")
    
    # Set environment variables
    os.environ['FLASK_ENV'] = 'development' if debug else 'production'
    
    try:
        from app import app
        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return False
    
    return True

def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(
        description='AI Text Detector Web Application',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                    # Run in production mode
  python run.py --debug           # Run in debug mode
  python run.py --host localhost  # Run on localhost only
  python run.py --port 8080       # Run on port 8080
  python run.py --test            # Run tests only
        """
    )
    
    parser.add_argument('--host', default='0.0.0.0',
                       help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000,
                       help='Port to bind to (default: 5000)')
    parser.add_argument('--debug', action='store_true',
                       help='Run in debug mode')
    parser.add_argument('--test', action='store_true',
                       help='Run tests only')
    parser.add_argument('--check', action='store_true',
                       help='Check dependencies and model only')
    
    args = parser.parse_args()
    
    print("🤖 AI Text Detector Web Application")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check model availability
    check_model()
    
    # Run tests if requested
    if args.test:
        if run_tests():
            print("✅ All tests passed!")
        else:
            print("❌ Some tests failed!")
            sys.exit(1)
        return
    
    # Check only mode
    if args.check:
        print("\n✅ System check completed")
        return
    
    # Run the application
    print("\n" + "=" * 40)
    success = run_app(host=args.host, port=args.port, debug=args.debug)
    
    if not success:
        sys.exit(1)

if __name__ == '__main__':
    main() 