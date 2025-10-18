# src/services/csv_manager.py
"""
CSV management utilities for updating product data
"""

import pandas as pd
import logging
from typing import Optional, Dict, Any

class CSVManager:
    """Handles CSV file operations for product data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def update_product_description(self, 
                                 csv_path: str, 
                                 product_id: str, 
                                 new_description: str) -> bool:
        """Update a product's description in the CSV file"""
        try:
            # Load CSV
            df = pd.read_csv(csv_path)
            
            # Check if description column exists
            if 'description' not in df.columns:
                # Add description column if it doesn't exist
                df['description'] = ''
                self.logger.info("Added 'description' column to CSV")
            
            # Find and update the product
            mask = df['product_id'] == product_id
            if mask.any():
                df.loc[mask, 'description'] = new_description
                
                # Save back to CSV
                df.to_csv(csv_path, index=False)
                self.logger.info(f"Updated description for product {product_id}")
                return True
            else:
                self.logger.warning(f"Product {product_id} not found in CSV")
                # Debug: show available product IDs
                available_ids = df['product_id'].tolist()[:10]  # Show first 10
                self.logger.info(f"Available product IDs (first 10): {available_ids}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating CSV: {e}")
            return False
    
    def get_product_by_id(self, csv_path: str, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product data by ID from CSV"""
        try:
            df = pd.read_csv(csv_path)
            product_row = df[df['product_id'] == product_id]
            if not product_row.empty:
                return product_row.iloc[0].to_dict()
            return None
        except Exception as e:
            self.logger.error(f"Error reading product from CSV: {e}")
            return None
    
    def update_product_field(self, 
                           csv_path: str, 
                           product_id: str, 
                           field_name: str, 
                           new_value: str) -> bool:
        """Update any field for a product in the CSV file"""
        try:
            # Load CSV
            df = pd.read_csv(csv_path)
            
            # Find and update the product
            mask = df['product_id'] == product_id
            if mask.any():
                df.loc[mask, field_name] = new_value
                
                # Save back to CSV
                df.to_csv(csv_path, index=False)
                self.logger.info(f"Updated {field_name} for product {product_id}")
                return True
            else:
                self.logger.warning(f"Product {product_id} not found in CSV")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating CSV field {field_name}: {e}")
            return False

