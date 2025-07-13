#!/usr/bin/env python3
"""
Simple R2 CORS Configuration Script

Run this from the backend directory:
python setup_cors_simple.py
"""

import os
import sys
from pathlib import Path

def load_env_file():
    """Load environment variables from .env file."""
    env_path = Path('.env')
    
    if env_path.exists():
        print(f"📁 Loading environment variables from: {env_path}")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value
        print(f"✅ Environment variables loaded successfully")
    else:
        print(f"⚠️ .env file not found")
        return False
    return True

def validate_r2_config():
    """Validate R2 configuration."""
    required_vars = [
        'R2_ACCESS_KEY_ID',
        'R2_SECRET_ACCESS_KEY', 
        'R2_ENDPOINT_URL',
        'R2_BUCKET_NAME'
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print(f"❌ Missing R2 environment variables: {missing}")
        return False
    
    print(f"✅ All R2 environment variables found:")
    print(f"   - Bucket: {os.getenv('R2_BUCKET_NAME')}")
    print(f"   - Endpoint: {os.getenv('R2_ENDPOINT_URL')}")
    return True

def generate_cors_command():
    """Generate the CORS configuration command using AWS CLI."""
    bucket = os.getenv('R2_BUCKET_NAME')
    endpoint = os.getenv('R2_ENDPOINT_URL')
    access_key = os.getenv('R2_ACCESS_KEY_ID')
    secret_key = os.getenv('R2_SECRET_ACCESS_KEY')
    
    cors_policy = {
        "CORSRules": [
            {
                "ID": "RiversideVideoUploads",
                "AllowedHeaders": ["*"],
                "AllowedMethods": ["PUT", "POST", "GET", "HEAD", "DELETE"],
                "AllowedOrigins": [
                    "http://localhost:3000",
                    "https://localhost:3000",
                    "http://localhost:3001", 
                    "https://localhost:3001"
                ],
                "ExposeHeaders": [
                    "ETag",
                    "x-amz-request-id",
                    "x-amz-id-2",
                    "Content-Length",
                    "Content-Type"
                ],
                "MaxAgeSeconds": 3600
            }
        ]
    }
    
    print(f"\n🔧 CORS Configuration Instructions:")
    print(f"=" * 50)
    print(f"\nOption 1: Using Python script with dependencies")
    print(f"If you have a virtual environment with boto3:")
    print(f"  python scripts/setup_r2_cors.py")
    
    print(f"\nOption 2: Manual CORS setup using AWS CLI")
    print(f"1. Install AWS CLI: brew install awscli")
    print(f"2. Configure AWS CLI for R2:")
    print(f"   aws configure --profile r2")
    print(f"   AWS Access Key ID: {access_key}")
    print(f"   AWS Secret Access Key: {secret_key}")
    print(f"   Default region name: auto")
    print(f"   Default output format: json")
    
    print(f"\n3. Create CORS policy file:")
    print(f"   cat > cors-policy.json << 'EOF'")
    import json
    print(json.dumps(cors_policy, indent=2))
    print(f"EOF")
    
    print(f"\n4. Apply CORS policy:")
    print(f"   aws s3api put-bucket-cors \\")
    print(f"     --bucket {bucket} \\")
    print(f"     --cors-configuration file://cors-policy.json \\")
    print(f"     --endpoint-url {endpoint} \\")
    print(f"     --profile r2")
    
    print(f"\n5. Verify CORS policy:")
    print(f"   aws s3api get-bucket-cors \\")
    print(f"     --bucket {bucket} \\")
    print(f"     --endpoint-url {endpoint} \\")
    print(f"     --profile r2")

def try_python_script():
    """Try to run the Python CORS script with dependencies."""
    print(f"\n🐍 Attempting to run Python CORS script...")
    
    try:
        # Try to import boto3 to see if it's available
        import boto3
        print(f"✅ boto3 is available, running full script...")
        
        # Import and run the main function from the CORS script
        sys.path.append('scripts')
        from setup_r2_cors import main
        main()
        return True
        
    except ImportError:
        print(f"❌ boto3 not available in current environment")
        return False
    except Exception as e:
        print(f"❌ Error running CORS script: {e}")
        return False

def main():
    """Main function."""
    print(f"🚀 Riverside R2 CORS Setup Helper")
    print(f"=" * 40)
    
    # Load environment variables
    if not load_env_file():
        print(f"❌ Could not load .env file")
        return
    
    # Validate R2 config
    if not validate_r2_config():
        print(f"❌ R2 configuration incomplete")
        return
    
    # Try Python script first
    if try_python_script():
        print(f"\n🎉 CORS configuration completed using Python script!")
        return
    
    # Fall back to manual instructions
    print(f"\n📋 Python dependencies not available, showing manual setup:")
    generate_cors_command()
    
    print(f"\n⚠️ After setting up CORS, test your uploads!")
    print(f"The 'Load failed' errors should disappear.")

if __name__ == "__main__":
    main()