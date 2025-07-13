#!/usr/bin/env python3
"""
R2 CORS Configuration Script for Riverside Video Upload System

This script configures CORS (Cross-Origin Resource Sharing) policy on your
Cloudflare R2 bucket to allow direct uploads from your frontend application.

IMPORTANT: Run this script BEFORE attempting video uploads.

Usage:
    python scripts/setup_r2_cors.py

Requirements:
    - R2_ACCESS_KEY_ID environment variable
    - R2_SECRET_ACCESS_KEY environment variable  
    - R2_ENDPOINT_URL environment variable
    - R2_BUCKET_NAME environment variable
"""

import boto3
import json
import os
import sys
from typing import Dict, List, Any
from pathlib import Path

# Load environment variables from .env file
def load_env_file():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / '.env'
    
    if env_path.exists():
        print(f"📁 Loading environment variables from: {env_path}")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value
        print(f"✅ Environment variables loaded successfully")
    else:
        print(f"⚠️ .env file not found at: {env_path}")
        print(f"Please make sure environment variables are set manually")

def get_cors_policy(allowed_origins: List[str] = None) -> Dict[str, Any]:
    """
    Get the CORS policy configuration for R2 bucket.
    
    Args:
        allowed_origins: List of allowed origins. Defaults to common development origins.
        
    Returns:
        Dict containing the CORS policy configuration
    """
    if allowed_origins is None:
        allowed_origins = [
            "http://localhost:3000",  # Next.js development
            "http://localhost:3001",  # Alternative port
            "https://localhost:3000", # HTTPS development
            "https://localhost:3001", # HTTPS alternative
            # Add your production domains here
            # "https://yourapp.com",
            # "https://www.yourapp.com"
        ]
    
    return {
        'CORSRules': [
            {
                'ID': 'RiversideVideoUploads',
                'AllowedHeaders': [
                    '*'  # Allow all headers for presigned URL uploads
                ],
                'AllowedMethods': [
                    'PUT',     # Required for direct chunk uploads
                    'POST',    # For multipart uploads
                    'GET',     # For downloading processed videos
                    'HEAD',    # For upload verification
                    'DELETE'   # For cleanup operations
                ],
                'AllowedOrigins': allowed_origins,
                'ExposeHeaders': [
                    'ETag',           # Required for upload verification
                    'x-amz-request-id',
                    'x-amz-id-2',
                    'Content-Length',
                    'Content-Type'
                ],
                'MaxAgeSeconds': 3600  # Cache preflight requests for 1 hour
            }
        ]
    }

def setup_r2_cors(
    bucket_name: str,
    access_key_id: str,
    secret_access_key: str,
    endpoint_url: str,
    allowed_origins: List[str] = None
) -> bool:
    """
    Configure CORS policy on R2 bucket.
    
    Args:
        bucket_name: Name of the R2 bucket
        access_key_id: R2 access key ID
        secret_access_key: R2 secret access key
        endpoint_url: R2 endpoint URL
        allowed_origins: List of allowed origins
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize R2 client
        print(f"🔧 Initializing R2 client...")
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name='auto'
        )
        
        # Test connection
        print(f"🔍 Testing R2 connection...")
        buckets = s3_client.list_buckets()
        bucket_names = [b['Name'] for b in buckets.get('Buckets', [])]
        
        if bucket_name not in bucket_names:
            print(f"❌ Error: Bucket '{bucket_name}' not found!")
            print(f"Available buckets: {bucket_names}")
            return False
        
        print(f"✅ Connected to R2. Found bucket: {bucket_name}")
        
        # Get current CORS configuration
        print(f"📋 Checking current CORS configuration...")
        try:
            current_cors = s3_client.get_bucket_cors(Bucket=bucket_name)
            print(f"📄 Current CORS policy:")
            print(json.dumps(current_cors.get('CORSRules', []), indent=2))
        except s3_client.exceptions.NoSuchCORSConfiguration:
            print(f"📄 No existing CORS configuration found.")
        except Exception as e:
            print(f"⚠️ Warning: Could not retrieve current CORS config: {e}")
        
        # Apply new CORS configuration
        print(f"🔧 Applying new CORS configuration...")
        cors_policy = get_cors_policy(allowed_origins)
        
        s3_client.put_bucket_cors(
            Bucket=bucket_name,
            CORSConfiguration=cors_policy
        )
        
        print(f"✅ CORS configuration applied successfully!")
        print(f"📄 New CORS policy:")
        print(json.dumps(cors_policy['CORSRules'], indent=2))
        
        # Verify the configuration
        print(f"🔍 Verifying CORS configuration...")
        new_cors = s3_client.get_bucket_cors(Bucket=bucket_name)
        
        if new_cors.get('CORSRules'):
            print(f"✅ CORS configuration verified successfully!")
            return True
        else:
            print(f"❌ Error: CORS configuration verification failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error configuring CORS: {e}")
        return False

def validate_environment() -> Dict[str, str]:
    """
    Validate that all required environment variables are set.
    
    Returns:
        Dict containing the environment variables
        
    Raises:
        SystemExit: If required environment variables are missing
    """
    required_vars = [
        'R2_ACCESS_KEY_ID',
        'R2_SECRET_ACCESS_KEY',
        'R2_ENDPOINT_URL',
        'R2_BUCKET_NAME'
    ]
    
    missing_vars = []
    env_vars = {}
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            env_vars[var] = value
    
    if missing_vars:
        print(f"❌ Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print(f"\nPlease set these variables in your .env file or environment.")
        print(f"Example .env file:")
        print(f"R2_ACCESS_KEY_ID=your_access_key_here")
        print(f"R2_SECRET_ACCESS_KEY=your_secret_key_here")
        print(f"R2_ENDPOINT_URL=https://your-account.r2.cloudflarestorage.com")
        print(f"R2_BUCKET_NAME=your-bucket-name")
        sys.exit(1)
    
    return env_vars

def main():
    """Main function to setup R2 CORS configuration."""
    print("🚀 Riverside R2 CORS Configuration Setup")
    print("=" * 50)
    
    # Load environment variables from .env file
    load_env_file()
    
    # Validate environment
    env_vars = validate_environment()
    
    # Get optional custom origins from command line or environment
    custom_origins = os.getenv('CORS_ALLOWED_ORIGINS')
    allowed_origins = None
    
    if custom_origins:
        allowed_origins = [origin.strip() for origin in custom_origins.split(',')]
        print(f"🌐 Using custom allowed origins: {allowed_origins}")
    else:
        print(f"🌐 Using default development origins")
    
    # Setup CORS
    success = setup_r2_cors(
        bucket_name=env_vars['R2_BUCKET_NAME'],
        access_key_id=env_vars['R2_ACCESS_KEY_ID'],
        secret_access_key=env_vars['R2_SECRET_ACCESS_KEY'],
        endpoint_url=env_vars['R2_ENDPOINT_URL'],
        allowed_origins=allowed_origins
    )
    
    if success:
        print("\n🎉 CORS configuration completed successfully!")
        print("\n📋 Next steps:")
        print("1. Your R2 bucket is now configured for direct uploads")
        print("2. Start your frontend and backend applications")
        print("3. Test video recording and upload functionality")
        print("4. Monitor the browser console for any remaining CORS errors")
        print("\n⚠️ Note: If you add new domains, re-run this script with updated origins")
    else:
        print("\n❌ CORS configuration failed!")
        print("Please check your R2 credentials and try again.")
        sys.exit(1)

if __name__ == "__main__":
    main()