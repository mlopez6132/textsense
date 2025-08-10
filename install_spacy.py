#!/usr/bin/env python3
"""
Installation script for spaCy and the English model
Run this script to install spaCy and download the required model for sentence segmentation.
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"   Error: {e.stderr}")
        return False

def main():
    print("🚀 Installing spaCy and English model for sentence segmentation...")
    print("=" * 60)
    
    # Check if pip is available
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("❌ pip is not available. Please install pip first.")
        return False
    
    # Install spaCy
    if not run_command(f"{sys.executable} -m pip install spacy>=3.5.0", "Installing spaCy"):
        return False
    
    # Download the English model
    if not run_command(f"{sys.executable} -m spacy download en_core_web_sm", "Downloading English model"):
        return False
    
    # Verify installation
    print("\n🔍 Verifying installation...")
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        test_text = "This is a test sentence. This is another sentence."
        doc = nlp(test_text)
        sentences = list(doc.sents)
        if len(sentences) == 2:
            print("✅ spaCy installation verified successfully!")
            print(f"   Test: Found {len(sentences)} sentences in test text")
        else:
            print("⚠️  spaCy installed but test failed")
            return False
    except Exception as e:
        print(f"❌ spaCy verification failed: {e}")
        return False
    
    print("\n🎉 Installation completed successfully!")
    print("You can now run the AI Text Detector with sentence-level analysis.")
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n💡 If you encounter issues, try running these commands manually:")
        print("   pip install spacy>=3.5.0")
        print("   python -m spacy download en_core_web_sm")
    sys.exit(0 if success else 1) 