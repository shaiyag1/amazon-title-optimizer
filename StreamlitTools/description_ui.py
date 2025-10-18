# StreamlitTools/description_ui.py
"""
UI components for description generation
"""

import streamlit as st
import pandas as pd
import os
from typing import Optional, Dict, Any
from src.services.description_generator import DescriptionGenerator, DescriptionGenerationResult
from src.services.csv_manager import CSVManager
from src.services.data_models import ProductData

class DescriptionUI:
    """UI components for description generation"""
    
    def __init__(self, description_generator: DescriptionGenerator, csv_manager: CSVManager):
        self.description_generator = description_generator
        self.csv_manager = csv_manager
    
    def render_description_button(self, selected_product: Dict[str, Any]) -> bool:
        """Render the description generation button and return True if clicked"""
        
        # Check if product needs description
        needs_description = self._product_needs_description(selected_product)
        
        if needs_description:
            if st.button("🤖 Generate Description", type="secondary", disabled=False):
                return True
        else:
            st.button("🤖 Generate Description", type="secondary", disabled=True, 
                     help="Product already has a description")
        
        return False
    
    def show_description_generation_modal(self, 
                                        selected_product: Dict[str, Any],
                                        csv_path: str) -> None:
        """Show the description generation modal/popup"""
        
        with st.container():
            st.markdown("### 🤖 Generate Product Description")
            
            # Show product info
            st.info(f"**Product:** {selected_product['title'][:50]}...")
            
            # Debug info
            with st.expander("🔍 Debug Info", expanded=False):
                st.write(f"**Product ID:** {selected_product.get('product_id', 'N/A')}")
                st.write(f"**Current Description:** {selected_product.get('description', 'N/A')}")
                st.write(f"**CSV Path:** {csv_path}")
                st.write(f"**File Exists:** {os.path.exists(csv_path) if csv_path else 'N/A'}")
                if csv_path and os.path.exists(csv_path):
                    st.write(f"**File Size:** {os.path.getsize(csv_path)} bytes")
                    st.write(f"**Absolute Path:** {os.path.abspath(csv_path)}")
                st.write(f"**Description Generator Available:** {self.description_generator is not None}")
                st.write(f"**CSV Manager Available:** {self.csv_manager is not None}")
            
            # Check if we already have a generated description in session state
            if 'generated_description_result' not in st.session_state:
                # Generate description immediately
                with st.spinner("Generating description..."):
                    result = self._generate_description(selected_product)
                    if result and result.generated_description:
                        st.session_state.generated_description_result = result
                    else:
                        st.error("❌ Failed to generate description")
                        return
            
            # Show the generated description
            result = st.session_state.generated_description_result
            if result and result.generated_description:
                # Show generated description
                st.markdown("#### Generated Description:")
                st.text_area("Generated Description", value=result.generated_description, height=200, disabled=True, label_visibility="collapsed")
                
                # Show metadata
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Confidence", f"{result.confidence_score:.2f}")
                with col2:
                    st.metric("Keywords", len(result.keywords_used))
                with col3:
                    st.metric("Time", f"{result.processing_time:.2f}s")
                
                # Show reasoning
                with st.expander("🧠 Generation Reasoning"):
                    st.write(result.generation_reasoning)
                
                # Show keywords used
                if result.keywords_used:
                    st.write("**Keywords Used:**")
                    st.write(", ".join(result.keywords_used))
                
                # Show warnings
                if result.warnings:
                    st.warning("**Warnings:** " + ", ".join(result.warnings))
                
                # Action buttons
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("✅ Approve & Save", type="primary"):
                        if self._save_description(csv_path, selected_product['product_id'], result.generated_description):
                            st.success("✅ Description saved successfully!")
                            # Clear session state
                            if 'generated_description_result' in st.session_state:
                                del st.session_state.generated_description_result
                            st.session_state.description_generated = False
                            st.rerun()
                        else:
                            st.error("❌ Failed to save description")
                
                with col2:
                    if st.button("🔄 Regenerate"):
                        # Clear the generated result and regenerate
                        if 'generated_description_result' in st.session_state:
                            del st.session_state.generated_description_result
                        st.rerun()
                
                with col3:
                    if st.button("❌ Cancel"):
                        # Clear session state
                        if 'generated_description_result' in st.session_state:
                            del st.session_state.generated_description_result
                        st.session_state.description_generated = False
                        st.rerun()
    
    def _product_needs_description(self, product: Dict[str, Any]) -> bool:
        """Check if product needs a description"""
        description = product.get('description', '')
        return pd.isna(description) or str(description).strip() == '' or str(description).lower() in ['none', 'n/a', '']
    
    def _generate_description(self, product: Dict[str, Any]) -> Optional[DescriptionGenerationResult]:
        """Generate description for the product"""
        try:
            # Convert to ProductData
            product_data = ProductData(
                product_id=product['product_id'],
                current_title=product['title'],
                brand=product.get('brand'),
                product_type=product.get('product_type'),
                features=product.get('features'),
                category=product.get('category')
            )
            
            # Generate description
            result = self.description_generator.generate_description(product_data)
            return result
            
        except Exception as e:
            st.error(f"Error generating description: {e}")
            return None
    
    def _save_description(self, csv_path: str, product_id: str, description: str) -> bool:
        """Save the generated description to CSV"""
        try:
            # Debug info
            st.write(f"🔍 Debug: Attempting to save description to: {csv_path}")
            st.write(f"🔍 Debug: Product ID: {product_id}")
            st.write(f"🔍 Debug: Description length: {len(description)}")
            
            # Check if file exists
            import os
            if not os.path.exists(csv_path):
                st.error(f"❌ CSV file not found: {csv_path}")
                return False
            
            # Try to save
            success = self.csv_manager.update_product_description(csv_path, product_id, description)
            
            if success:
                st.success(f"✅ Description saved successfully to {csv_path}")
                # Force refresh the products data
                st.session_state.cache_loaded = False
                # Clear the cache files to force reload
                import os
                cache_files = [".streamlit_cache/last_products.pkl", ".streamlit_cache/last_keywords.pkl"]
                for cache_file in cache_files:
                    if os.path.exists(cache_file):
                        os.remove(cache_file)
                st.info("🔄 Product list will refresh automatically")
            else:
                st.error(f"❌ Failed to save description to {csv_path}")
            
            return success
            
        except Exception as e:
            st.error(f"❌ Error saving description: {e}")
            return False

