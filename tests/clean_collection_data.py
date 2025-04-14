#!/usr/bin/env python3
import sys
import logging
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import astra_db_ops

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Check if collection name is provided
    if len(sys.argv) != 2:
        print("Usage: python clean_collection_data.py <collection_name>")
        print("Example: python clean_collection_data.py verification_attempts")
        sys.exit(1)

    collection_name = sys.argv[1]
    
    try:
        logging.info(f"Cleaning data from collection: {collection_name}")
        # Call the function without expecting a return value
        astra_db_ops.clean_collection_data(collection_name)
        logging.info(f"Successfully cleaned data from {collection_name}")
            
    except Exception as e:
        logging.error(f"Error cleaning collection data: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 