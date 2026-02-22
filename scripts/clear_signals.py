#!/usr/bin/env python3
"""
Administrative CLI tool to clear trading signal history.
This script provides safe, command-line only access to data reset functionality.
"""

import sys
import logging
from pathlib import Path

# Add src to path if needed to ensure imports work when run from root
sys.path.append(str(Path(__file__).parent.parent / "src"))

from wsb_agent.utils.config import load_config
from wsb_agent.storage.database import Database

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("admin.clear_signals")

def main():
    print("\n" + "="*50)
    print(" WSB AGENT: ADMINISTRATIVE SIGNAL RESET")
    print("="*50)
    
    confirm = input("\nWARNING: This will permanently delete ALL signal history.\nAre you sure you want to proceed? (y/N): ").lower()
    
    if confirm != 'y':
        print("Aborted. No data was deleted.")
        return

    try:
        config = load_config()
        db = Database(config.storage.database_path)
        
        # Verify signal count before deletion
        cursor = db.conn.execute("SELECT COUNT(*) FROM signals")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("No signals found in database. Nothing to clear.")
            return

        print(f"Clearing {count} signals...")
        db.clear_signals()
        print("SUCCESS: Signal history has been reset.")
        db.close()
        
    except Exception as e:
        logger.error(f"FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
