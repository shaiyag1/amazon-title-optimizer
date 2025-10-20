import streamlit as st
import sys
import os
import time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the path so we can import our services
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

# Import from the src directory (one level up from StreamlitTools)
from src.services.llm_client import LLMClient
from src.services.title_optimizer import TitleOptimizer
from src.services.description_optimizer import DescriptionOptimizer
from src.services.data_models import ProductData, OptimizationResult, DescriptionOptimizationResult

def main():
    st.set_page_config(
        page_title="Simple Amazon Optimizer",
        page_icon="🚀",
        layout="wide"
    )

    st.title("🚀 Simple Amazon Content Optimizer")
    st.markdown("Optimize your Amazon product content with targeted search terms")

    # Product management section
    st.markdown("### 📦 Product Management")
    
    # Load existing products
    csv_path = os.path.join(os.path.dirname(__file__), "..", "product_content_list.csv")
    csv_path = os.path.abspath(csv_path)
    
    existing_products = []
    if os.path.exists(csv_path):
        try:
            import csv
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                existing_products = list(reader)
        except Exception as e:
            st.warning(f"Could not load existing products: {e}")
    
    # Initialize services
    if 'llm_client' not in st.session_state:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
        if not api_key:
            st.error("❌ OpenAI API key not found! Please set OPENAI_API_KEY environment variable.")
            st.stop()
        
        st.session_state.llm_client = LLMClient(api_key=api_key)
        st.session_state.title_optimizer = TitleOptimizer(st.session_state.llm_client)
        st.session_state.description_optimizer = DescriptionOptimizer(st.session_state.llm_client)

    # Default sample data
    default_title = "Wireless Bluetooth Headphones with Noise Cancellation"
    default_features = """• Active Noise Cancellation Technology
• 30-hour battery life with quick charge
• Premium sound quality with deep bass
• Comfortable over-ear design
• Built-in microphone for calls
• Foldable and portable design"""
    default_description = "Experience premium audio with these wireless Bluetooth headphones featuring active noise cancellation technology. Enjoy up to 30 hours of battery life with quick charge capability. The comfortable over-ear design provides excellent sound isolation while the built-in microphone ensures crystal clear calls. Perfect for music lovers, commuters, and professionals who demand quality audio."
    
    # Use the same default search terms across all sections (can be edited per section)
    default_common_terms = """wireless headphones
bluetooth headphones
noise cancelling headphones
over ear headphones
premium audio"""
    
    col_load, col_new = st.columns([2, 1])
    
    with col_load:
        if existing_products:
            product_options = ["Select a product to load..."] + [p['product_name'] for p in existing_products]
            selected_product = st.selectbox(
                "Load Existing Product:",
                options=product_options,
                key="product_selector"
            )
        else:
            selected_product = "No products available"
            st.info("No saved products found. Create a new one below.")
    
    with col_new:
        st.markdown("**Or create new:**")
        product_name = st.text_input(
            "Product ID / Name",
            value="118_313",
            help="Enter a product identifier, e.g., 118_313",
            key="new_product_name"
        )
        
        if st.button("🔄 Clear All Fields", help="Reset to default values"):
            st.rerun()

    # Load selected product data AFTER UI elements are created
    loaded_product = None
    if existing_products and selected_product != "Select a product to load..." and selected_product != "No products available":
        loaded_product = next((p for p in existing_products if p['product_name'] == selected_product), None)

    # Set default value based on loaded product or default
    default_product_name = loaded_product['product_name'] if loaded_product else "118_313"
    
    # Parse loaded search terms or use defaults
    loaded_terms = default_common_terms
    if loaded_product and loaded_product.get('search_term_list'):
        loaded_terms = loaded_product['search_term_list'].replace(',', '\n')

    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📝 Input Content")
        
        # Title Section with side-by-side search terms
        st.markdown("### Title")
        t_col_left, t_col_right = st.columns([2, 1])
        with t_col_left:
            title_text = st.text_area(
                "Product Title:",
                value=loaded_product['title'] if loaded_product else default_title,
                height=100,
                key="title_input"
            )
        with t_col_right:
            title_terms = st.text_area(
                "Title Search Terms\n(one per line):",
                value=loaded_terms,
                height=100,
                key="title_terms_input"
            )
        optimize_title = st.checkbox("Optimize Title", value=True, key="optimize_title_check")
        st.markdown("---")
        
        # Features Section with side-by-side search terms
        st.markdown("### Features/Bullets")
        f_col_left, f_col_right = st.columns([2, 1])
        with f_col_left:
            features_text = st.text_area(
                "Product Features:",
                value=loaded_product['bullets'] if loaded_product else default_features,
                height=200,
                key="features_input"
            )
        with f_col_right:
            features_terms = st.text_area(
                "Features Search Terms\n(one per line):",
                value=loaded_terms,
                height=200,
                key="features_terms_input"
            )
        optimize_features = st.checkbox("Optimize Features", value=True, key="optimize_features_check")
        st.markdown("---")
        
        # Description Section with side-by-side search terms
        st.markdown("### Description")
        d_col_left, d_col_right = st.columns([2, 1])
        with d_col_left:
            description_text = st.text_area(
                "Product Description:",
                value=loaded_product['description'] if loaded_product else default_description,
                height=200,
                key="description_input"
            )
        with d_col_right:
            description_terms = st.text_area(
                "Description Search Terms\n(one per line):",
                value=loaded_terms,
                height=200,
                key="description_terms_input"
            )
        optimize_description = st.checkbox("Optimize Description", value=True, key="optimize_description_check")
    
    with col2:
        st.subheader("🎯 Optimization Results")
        
        if st.button("🚀 Optimize Content", type="primary", use_container_width=True):
            if not any([optimize_title, optimize_features, optimize_description]):
                st.warning("Please select at least one component to optimize!")
            else:
                with st.spinner("Optimizing content..."):
                    try:
                        # Parse search terms
                        title_search_terms = [term.strip() for term in title_terms.split('\n') if term.strip()]
                        features_search_terms = [term.strip() for term in features_terms.split('\n') if term.strip()]
                        description_search_terms = [term.strip() for term in description_terms.split('\n') if term.strip()]
                        
                        # Create ProductData object
                        product_data = ProductData(
                            product_id="simple_optimizer",
                            current_title=title_text,
                            features=[features_text] if features_text else [],
                            description=description_text,
                            brand="Sample Brand",
                            product_type="Electronics"
                        )
                        
                        results = {}
                        
                        # Optimize Title and Features
                        if optimize_title or optimize_features:
                            st.info("🔧 Optimizing Title and Features...")
                            title_result = st.session_state.title_optimizer.optimize_title(
                                product_data=product_data,
                                target_search_terms=title_search_terms + features_search_terms,
                                feature_refinement_mode=optimize_features
                            )
                            results['title'] = title_result
                        
                        # Optimize Description
                        if optimize_description:
                            st.info("📝 Optimizing Description...")
                            description_result = st.session_state.description_optimizer.optimize_description(
                                product_data=product_data,
                                target_search_terms=description_search_terms
                            )
                            results['description'] = description_result
                        
                        # Display Results
                        st.success("✅ Optimization Complete!")
                        
                        # Title Results
                        if 'title' in results:
                            st.markdown("#### 🏷️ Optimized Title")
                            st.write(results['title'].optimized_title)
                            
                            if results['title'].refined_features:
                                st.markdown("#### ✨ Optimized Features")
                                st.write(results['title'].refined_features)
                            
                            st.markdown("#### 📊 Title Metrics")
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Confidence", f"{results['title'].confidence_score:.2f}")
                            col2.metric("Preservation", f"{results['title'].preservation_score:.1f}%")
                            col3.metric("Processing Time", f"{results['title'].processing_time:.2f}s")
                        
                        # Description Results
                        if 'description' in results:
                            st.markdown("#### 📝 Optimized Description")
                            st.write(results['description'].optimized_description)
                            
                            st.markdown("#### 📊 Description Metrics")
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Confidence", f"{results['description'].confidence_score:.2f}")
                            col2.metric("Preservation", f"{results['description'].preservation_score:.1f}%")
                            col3.metric("Processing Time", f"{results['description'].processing_time:.2f}s")
                        
                        # Reasoning
                        if 'title' in results and results['title'].optimization_reasoning:
                            st.markdown("#### 🤔 Title Optimization Reasoning")
                            st.write(results['title'].optimization_reasoning)
                        
                        if 'description' in results and results['description'].optimization_reasoning:
                            st.markdown("#### 🤔 Description Optimization Reasoning")
                            st.write(results['description'].optimization_reasoning)
                        
                        # Keywords Used
                        if 'title' in results and results['title'].keywords_used:
                            st.markdown("#### 🔑 Keywords Used (Title)")
                            st.write(", ".join(results['title'].keywords_used))
                        
                        if 'description' in results and results['description'].keywords_used:
                            st.markdown("#### 🔑 Keywords Used (Description)")
                            st.write(", ".join(results['description'].keywords_used))
                        
                    except Exception as e:
                        st.error(f"❌ Error during optimization: {str(e)}")
                        st.exception(e)

        # Export Product section
        st.markdown("---")
        if st.button("💾 Export Product", use_container_width=True):
            try:
                import csv
                csv_path = os.path.join(os.path.dirname(__file__), "..", "product_content_list.csv")
                csv_path = os.path.abspath(csv_path)

                # Build combined, deduplicated search term list preserving order
                def _split_terms(text: str):
                    return [t.strip() for t in text.split("\n") if t.strip()]

                combined_terms = []
                seen = set()
                for term in _split_terms(title_terms) + _split_terms(features_terms) + _split_terms(description_terms):
                    if term not in seen:
                        seen.add(term)
                        combined_terms.append(term)
                combined_terms_str = ",".join(combined_terms)

                # Ensure CSV exists with header
                file_exists = os.path.exists(csv_path)
                with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["product_name", "title", "bullets", "description", "search_term_list"])
                    writer.writerow([
                        product_name,
                        title_text,
                        features_text,
                        description_text,
                        combined_terms_str
                    ])
                st.success(f"✅ Exported to {csv_path}")
            except Exception as e:
                st.error(f"❌ Failed to export: {e}")

    # Sidebar with instructions
    st.sidebar.header("📖 Instructions")
    st.sidebar.markdown("""
    1. **Enter your content** in the left column
    2. **Add search terms** (one per line) for each component
    3. **Check/uncheck** which components to optimize
    4. **Click "Optimize Content"** to see results
    
    **Tips:**
    - Use specific, relevant search terms
    - Each line in search terms = one keyword
    - You can optimize any combination of components
    - Results show confidence scores and preservation metrics
    """)

if __name__ == "__main__":
    main()
