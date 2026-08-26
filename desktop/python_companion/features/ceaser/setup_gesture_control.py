#!/usr/bin/env python3
"""
Setup script for Ceaser Gesture Control
Installs dependencies and tests the system.
"""

import subprocess
import sys
import os

def install_dependencies():
    """Install gesture control dependencies."""
    print("📦 Installing gesture control dependencies...")
    
    requirements_file = "gesture_requirements.txt"
    if not os.path.exists(requirements_file):
        print(f"❌ Requirements file not found: {requirements_file}")
        return False
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", requirements_file
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Dependencies installed successfully")
            return True
        else:
            print(f"❌ Failed to install dependencies: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error installing dependencies: {e}")
        return False

def test_system():
    """Test the gesture control system."""
    print("\n🧪 Testing gesture control system...")
    
    try:
        result = subprocess.run([
            sys.executable, "test_gesture_control.py"
        ], capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print(f"Errors: {result.stderr}")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Error testing system: {e}")
        return False

def main():
    """Main setup function."""
    print("🤖 Ceaser Gesture Control Setup")
    print("=" * 40)
    
    # Install dependencies
    if not install_dependencies():
        print("❌ Setup failed: Could not install dependencies")
        return False
    
    # Test system
    if not test_system():
        print("❌ Setup failed: System test failed")
        return False
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Gesture Control is ready to use:")
    print("1. Run: python gesture_control.py")
    print("2. Use hand gestures to control your computer")
    print("3. Press ESC to exit")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
