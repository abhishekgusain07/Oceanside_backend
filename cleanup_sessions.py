#!/usr/bin/env python3
"""
Manual session cleanup script.

This script can be run manually or via cron to cleanup old ghost sessions.

Usage:
    python cleanup_sessions.py [--days=7] [--dry-run]

Examples:
    python cleanup_sessions.py --days=7          # Cleanup sessions older than 7 days
    python cleanup_sessions.py --days=1 --dry-run  # Preview what would be cleaned up
"""

import asyncio
import argparse
import logging
from datetime import datetime

from app.core.database import async_session
from app.services.session_service import SessionService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def cleanup_sessions(days_old: int = 7, dry_run: bool = False):
    """
    Cleanup old sessions.
    
    Args:
        days_old: Sessions older than this many days will be cleaned up
        dry_run: If True, only show what would be cleaned up without making changes
    """
    try:
        async with async_session() as db:
            service = SessionService(db)
            
            if dry_run:
                logger.info(f"🔍 DRY RUN: Checking for sessions older than {days_old} days...")
                
                # For dry run, we'd need to implement a preview method
                # For now, let's just run the actual cleanup but rollback
                await db.begin()
                cleanup_count = await service.cleanup_old_sessions(days_old)
                await db.rollback()  # Don't commit the changes
                
                logger.info(f"📊 DRY RUN RESULT: {cleanup_count} sessions would be cleaned up")
                
            else:
                logger.info(f"🧹 Cleaning up sessions older than {days_old} days...")
                cleanup_count = await service.cleanup_old_sessions(days_old)
                
                if cleanup_count > 0:
                    logger.info(f"✅ Successfully cleaned up {cleanup_count} sessions")
                else:
                    logger.info("✅ No sessions needed cleanup")
                    
            return cleanup_count
            
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {e}")
        return 0

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Cleanup old recording sessions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cleanup_sessions.py                    # Cleanup sessions older than 7 days
  python cleanup_sessions.py --days=1          # Cleanup sessions older than 1 day
  python cleanup_sessions.py --days=7 --dry-run # Preview cleanup without making changes
        """
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Cleanup sessions older than this many days (default: 7)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be cleaned up without making changes'
    )
    
    args = parser.parse_args()
    
    logger.info("🎬 Riverside Session Cleanup Tool")
    logger.info(f"📅 Target: Sessions older than {args.days} days")
    logger.info(f"🔧 Mode: {'DRY RUN' if args.dry_run else 'LIVE CLEANUP'}")
    logger.info("=" * 50)
    
    start_time = datetime.now()
    cleanup_count = await cleanup_sessions(args.days, args.dry_run)
    end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds()
    
    logger.info("=" * 50)
    logger.info(f"🏁 Cleanup completed in {duration:.2f} seconds")
    logger.info(f"📊 Sessions processed: {cleanup_count}")
    
    return cleanup_count

if __name__ == "__main__":
    asyncio.run(main()) 