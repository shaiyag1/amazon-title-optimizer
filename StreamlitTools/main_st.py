import streamlit as st
import pandas as pd
import pickle
import os
from pathlib import Path
from typing import Optional, Dict, Any
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# In StreamlitTools/main_st.py, add these imports:
from src.services.llm_client import LLMClient
from src.services.title_optimizer import TitleOptimizer
from src.services.data_models import ProductData
from src.services.encoding_service import EncodingService


# Configuration
CACHE_DIR = Path(".streamlit_cache")
PRODUCTS_CACHE = CACHE_DIR / "last_products.pkl"
KEYWORDS_CACHE = CACHE_DIR / "last_keywords.pkl"

project_root = Path(__file__).parent.parent  # Go up from StreamlitTools to project root
sys.path.insert(0, str(project_root))

def create_cache_dir():
    """Create cache directory if it doesn't exist"""
    CACHE_DIR.mkdir(exist_ok=True)

def save_dataframe_to_cache(df: pd.DataFrame, cache_file: Path):
    """Save DataFrame to cache file"""
    try:
        create_cache_dir()
        with open(cache_file, 'wb') as f:
            pickle.dump(df, f)
    except Exception as e:
        st.error(f"Failed to save cache: {e}")

def load_dataframe_from_cache(cache_file: Path) -> Optional[pd.DataFrame]:
    """Load DataFrame from cache file"""
    try:
        if cache_file.exists():
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        st.error(f"Failed to load cache: {e}")
    return None

@st.cache_data
def load_csv_file(uploaded_file) -> pd.DataFrame:
    """Load and cache CSV file"""
    return pd.read_csv(uploaded_file)

def display_dataframe_info(df: pd.DataFrame, title: str):
    """Display DataFrame information in a nice format"""
    st.subheader(title)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Rows", len(df))
    with col2:
        st.metric("Columns", len(df.columns))
    with col3:
        if 'product_id' in df.columns:
            unique_products = df['product_id'].nunique()
            st.metric("Unique Products", unique_products)
        else:
            st.metric("Memory Usage", f"{df.memory_usage(deep=True).sum() / 1024:.1f} KB")
    
    # Show column info
    st.write("**Columns:**")
    st.write(", ".join(df.columns.tolist()))
    
    # Show data types
    with st.expander("Data Types & Info"):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Data Types:**")
            st.dataframe(pd.DataFrame({
                'Column': df.columns,
                'Type': df.dtypes.astype(str),
                'Non-Null Count': [df[col].notna().sum() for col in df.columns]
            }))
        
        with col2:
            st.write("**Sample Values:**")
            sample_data = {}
            for col in df.columns:
                non_null_values = df[col].dropna()
                if len(non_null_values) > 0:
                    sample_data[col] = non_null_values.iloc[0]
                else:
                    sample_data[col] = "No data"
            st.json(sample_data)

def validate_csv_structure(df: pd.DataFrame, expected_columns: list, file_type: str) -> bool:
    """Validate CSV structure with detailed error messages"""
    missing_columns = [col for col in expected_columns if col not in df.columns]
    
    if missing_columns:
        st.error(f"❌ **{file_type} CSV Validation Failed**")
        st.error(f"**Missing required columns:** {', '.join(missing_columns)}")
        
        # Show detailed comparison
        with st.expander("📋 **Column Analysis**", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**✅ Required Columns:**")
                for col in expected_columns:
                    if col in df.columns:
                        st.write(f"  ✅ {col}")
                    else:
                        st.write(f"  ❌ {col} *(missing)*")
            
            with col2:
                st.write("**📁 Found Columns:**")
                for col in df.columns:
                    if col in expected_columns:
                        st.write(f"  ✅ {col}")
                    else:
                        st.write(f"  ℹ️ {col} *(extra)*")
        
        # Show sample of the data
        if len(df) > 0:
            st.write("**📊 Sample Data (first 3 rows):**")
            st.dataframe(df.head(3), use_container_width=True)
        
        return False
    
    st.success(f"✅ **{file_type} CSV structure is valid!**")
    return True

def main():
    st.set_page_config(
        page_title="CSV File Loader", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("CSV File Loader & Inspector")
    st.markdown("Load and inspect Products and Keywords CSV files")
    
    # Initialize session state
    if 'products_df' not in st.session_state:
        st.session_state.products_df = None
    if 'keywords_df' not in st.session_state:
        st.session_state.keywords_df = None
    if 'cache_loaded' not in st.session_state:
        st.session_state.cache_loaded = False
    if 'selected_product_id_for_clusters' not in st.session_state:
        st.session_state.selected_product_id_for_clusters = None
    if 'encoding_service' not in st.session_state:
        st.session_state.encoding_service = None
    if 'optimized_title' not in st.session_state:
        st.session_state.optimized_title = None
    if 'cluster_optimize_scores' not in st.session_state:
        st.session_state.cluster_optimize_scores = {}
    
    # Sidebar for file uploads
    with st.sidebar:
        st.header("File Upload")
        
        # Cache loading disabled for this phase
        # if not st.session_state.cache_loaded and st.session_state.products_df is None and st.session_state.keywords_df is None:
        #     with st.spinner("Loading cached files..."):
        #         cached_products = load_dataframe_from_cache(PRODUCTS_CACHE)
        #         cached_keywords = load_dataframe_from_cache(KEYWORDS_CACHE)
        #         
        #         if cached_products is not None:
        #             st.session_state.products_df = cached_products
        #             st.success("Loaded cached products file")
        #         
        #         if cached_keywords is not None:
        #             st.session_state.keywords_df = cached_keywords
        #             st.success("Loaded cached keywords file")
        #         
        #         # Mark cache as loaded to prevent infinite loop
        #         st.session_state.cache_loaded = True
        
        st.subheader("Upload New Files")
        
        # Show current status
        col1, col2 = st.columns(2)
        with col1:
            if st.session_state.products_df is not None:
                st.success("✅ Product Title CSV loaded")
            else:
                st.info("📁 No Product Title CSV")
        
        with col2:
            if st.session_state.keywords_df is not None:
                st.success("✅ Search Terms CSV loaded")
            else:
                st.info("📁 No Search Terms CSV")
        
        # Products CSV upload
        products_file = st.file_uploader(
            "Upload Product Title CSV", 
            type=['csv'],
            key="products_upload",
            help="CSV with columns: product_id, title, brand, description, product_type, etc."
        )
        
        if products_file is not None:
            try:
                with st.spinner("Loading products CSV..."):
                    df = load_csv_file(products_file)
                    
                    # Validate structure
                    required_columns = ['product_id', 'title']
                    if validate_csv_structure(df, required_columns, "Products"):
                        st.session_state.products_df = df
                        # save_dataframe_to_cache(df, PRODUCTS_CACHE)  # Cache disabled
                        st.success(f"Loaded {len(df)} products")
                        # st.rerun()  # Removed to prevent hiding second uploader
                    
            except Exception as e:
                st.error(f"Error loading products CSV: {e}")
        
        # Keywords CSV upload
        keywords_file = st.file_uploader(
            "Upload Search Terms Clusters CSV", 
            type=['csv'],
            key="keywords_upload",
            help="CSV with columns: select_box, parent_product_id, product_id, search_term, cluster_id"
        )
        
        if keywords_file is not None:
            try:
                with st.spinner("Loading keywords CSV..."):
                    df = load_csv_file(keywords_file)
                    
                    # Validate structure - check for essential columns only
                    required_columns = ['product_id', 'search_term', 'cluster_id']
                    if validate_csv_structure(df, required_columns, "Search Terms Clusters"):
                        st.session_state.keywords_df = df
                        
                        # save_dataframe_to_cache(df, KEYWORDS_CACHE)  # Cacheadd the selected product and show the list of the cluster 
                        st.success(f"Loaded {len(df)} keyword entries")
                        
                        # Debug info
                        st.write(f"**Debug Info:**")
                        st.write(f"- Total rows: {len(df)}")
                        st.write(f"- Columns: {list(df.columns)}")
                        
                        # Handle product_id data types properly
                        try:
                            product_ids = df['product_id'].astype(str)
                            product_ids = product_ids[product_ids != 'nan']
                            unique_products = product_ids.unique()
                            st.write(f"- Unique product IDs: {len(unique_products)}")
                            st.write(f"- Sample product IDs: {list(unique_products)[:5]}")
                        except Exception as e:
                            st.write(f"- Error processing product IDs: {e}")
                        
                        # st.rerun()  # Removed to prevent hiding second uploader
                    
            except Exception as e:
                st.error(f"Error loading keywords CSV: {e}")
        
        # Clear cache button
        st.subheader("Cache Management")
        if st.button("Clear Cached Files"):
            try:
                if PRODUCTS_CACHE.exists():
                    PRODUCTS_CACHE.unlink()
                if KEYWORDS_CACHE.exists():
                    KEYWORDS_CACHE.unlink()
                st.session_state.products_df = None
                st.session_state.keywords_df = None
                st.session_state.cache_loaded = False  # Reset cache loaded flag
                st.success("Cache cleared!")
                st.rerun()
            except Exception as e:
                st.error(f"Error clearing cache: {e}")
        
        # Encoding Service Management
        st.subheader("🔤 Encoding Service")
        
        # Debug: Show if we're in the sidebar
        st.write("🔍 Debug: In sidebar section")
        
        # Model selection
        available_models = [
            "sentence-transformers/all-MiniLM-L6-v2",
            "sentence-transformers/all-mpnet-base-v2",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        ]
        
        selected_model = st.selectbox(
            "Select Encoding Model:",
            available_models,
            help="Choose the LLM model for generating embeddings"
        )
        
        st.write(f"🔍 Debug: Selected model: {selected_model}")
        
        # Initialize encoding service
        st.write("🔍 Debug: About to show button")
        if st.button("🚀 Initialize Encoding Service"):
            st.write("🔍 Debug: Button clicked!")
            try:
                with st.spinner("Loading encoding model..."):
                    st.session_state.encoding_service = EncodingService(model_name=selected_model)
                st.success(f"✅ Encoding service initialized with {selected_model}")
            except Exception as e:
                st.error(f"❌ Failed to initialize encoding service: {e}")
                st.info("Please install: pip install sentence-transformers")
        
        # Show encoding service status
        if st.session_state.encoding_service is not None:
            st.success("✅ Encoding service ready")
            
            # Show cache stats
            cache_stats = st.session_state.encoding_service.get_cache_stats()
            st.write("**Cache Statistics:**")
            st.write(f"- Total cached embeddings: {cache_stats['total_files']}")
            st.write(f"- Product embeddings: {cache_stats['product_cache']}")
            st.write(f"- Search term embeddings: {cache_stats['search_term_cache']}")
            
            # Clear encoding cache
            if st.button("🗑️ Clear Encoding Cache"):
                st.session_state.encoding_service.clear_cache()
                st.success("Encoding cache cleared!")
                st.rerun()
        else:
            st.info("👆 Initialize encoding service to use LLM-based similarity")
    
    # Main content area
    if st.session_state.products_df is not None or st.session_state.keywords_df is not None:
        
        # File selector
        col1, col2 = st.columns(2)
        
        with col1:
            file_options = []
            if st.session_state.products_df is not None:
                file_options.append("Products")
            if st.session_state.keywords_df is not None:
                file_options.append("Keywords")
            
            selected_file = st.selectbox("Select file to inspect:", file_options)
        
        with col2:
            if selected_file:
                if selected_file == "Products" and st.session_state.products_df is not None:
                    df_to_show = st.session_state.products_df
                elif selected_file == "Keywords" and st.session_state.keywords_df is not None:
                    df_to_show = st.session_state.keywords_df
                else:
                    df_to_show = None
                
                if df_to_show is not None:
                    st.metric("Selected File", f"{selected_file} ({len(df_to_show)} rows)")
        
        # Cluster exploration section (only show if keywords data is loaded)
        if st.session_state.keywords_df is not None:
            st.subheader("🔍 Product-Specific Search Terms Cluster Explorer")
            
            # First, let user select a product to explore
            st.write("**Step 1: Select a Product to Explore**")
            
            # Get all unique products from the search terms data
            try:
                # Convert product_id to string and filter out NaN values
                product_ids = st.session_state.keywords_df['product_id'].astype(str)
                product_ids = product_ids[product_ids != 'nan']  # Remove NaN values
                available_products = sorted(product_ids.unique())
            except Exception as e:
                st.error(f"Error accessing keywords data: {e}")
                st.info("Please upload a valid Search Terms Clusters CSV file.")
                available_products = []
            
            # Create a product selector only if we have products
            if len(available_products) > 0:
                # Check if a product was selected from the Products table
                if st.session_state.selected_product_id_for_clusters is not None:
                    # Pre-select the product from session state
                    default_index = 0
                    if st.session_state.selected_product_id_for_clusters in available_products:
                        default_index = available_products.index(st.session_state.selected_product_id_for_clusters)
                    
                    selected_product_id = st.selectbox(
                        "Choose Product ID:",
                        available_products,
                        index=default_index,
                        help="Select a product to see its search terms and clusters"
                    )
                    
                    # Show info about pre-selected product
                    if st.session_state.selected_product_id_for_clusters == selected_product_id:
                        st.success(f"🎯 **Pre-selected from Products table:** {selected_product_id}")
                else:
                    selected_product_id = st.selectbox(
                        "Choose Product ID:",
                        available_products,
                        help="Select a product to see its search terms and clusters"
                    )
            else:
                st.warning("No products found in the search terms data.")
                st.info("Please upload a Search Terms Clusters CSV file with valid product_id data.")
                selected_product_id = None
            
            if selected_product_id:
                # Get product info from products data if available
                product_info = None
                if st.session_state.products_df is not None:
                    product_matches = st.session_state.products_df[
                        st.session_state.products_df['product_id'] == selected_product_id
                    ]
                    if len(product_matches) > 0:
                        product_info = product_matches.iloc[0]
                
                # Display product information
                st.write(f"**📦 Selected Product: {selected_product_id}**")
                if product_info is not None:
                    st.write(f"*Title: {product_info['title'][:100]}{'...' if len(product_info['title']) > 100 else ''}*")
                    if 'brand' in product_info and pd.notna(product_info['brand']):
                        st.write(f"*Brand: {product_info['brand']}*")
                
                # Filter search terms for this specific product
                # Convert product_id to string for comparison
                product_search_terms = st.session_state.keywords_df[
                    st.session_state.keywords_df['product_id'].astype(str) == selected_product_id
                ]
                
                if len(product_search_terms) > 0:
                    st.write(f"**Step 2: Explore Clusters for This Product**")
                    
                    # Get clusters for this product
                    product_clusters = sorted(product_search_terms['cluster_id'].unique())
                    
                    # Show cluster overview for this product
                    st.write(f"**📊 Clusters for Product {selected_product_id}:**")
                    cluster_overview = []
                    for cluster_id in product_clusters:
                        cluster_data = product_search_terms[product_search_terms['cluster_id'] == cluster_id]
                        cluster_overview.append({
                            'Cluster ID': cluster_id,
                            'Search Terms Count': len(cluster_data),
                            'Unique Search Terms': cluster_data['search_term'].nunique()
                        })
                    
                    cluster_overview_df = pd.DataFrame(cluster_overview)
                    st.dataframe(cluster_overview_df, use_container_width=True)
                    
                    # Cluster selection for this specific product
                    selected_cluster = st.selectbox(
                        f"Select Cluster to Explore (Product {selected_product_id}):",
                        product_clusters,
                        format_func=lambda x: f"Cluster {x} ({len(product_search_terms[product_search_terms['cluster_id'] == x])} search terms)"
                    )
                    
                    # Show search terms in selected cluster for this product
                    if selected_cluster is not None:
                        cluster_data = product_search_terms[product_search_terms['cluster_id'] == selected_cluster]
                        
                        st.write(f"**🔍 Search Terms in Cluster {selected_cluster} for Product {selected_product_id}:**")
                        
                        # Show cluster info
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Search Terms", len(cluster_data))
                        with col2:
                            st.metric("Unique Search Terms", cluster_data['search_term'].nunique())
                        with col3:
                            st.metric("Cluster ID", selected_cluster)
                        
                        # Show search terms list
                        search_terms_list = sorted(cluster_data['search_term'].unique())
                        
                        st.write("**Search Terms:**")
                        for i, term in enumerate(search_terms_list, 1):
                            st.write(f"{i}. {term}")
                        
                        # Show detailed view in expander
                        with st.expander("📊 Detailed View (All Data)", expanded=False):
                            detailed_display = cluster_data[['search_term', 'cluster_id']].copy()
                            detailed_display = detailed_display.sort_values('search_term')
                            detailed_display['#'] = range(1, len(detailed_display) + 1)
                            detailed_display = detailed_display[['#', 'search_term', 'cluster_id']]
                            st.dataframe(detailed_display, use_container_width=True)
                
                else:
                    st.warning(f"⚠️ No search terms found for product {selected_product_id}")
                    st.info("This product may not have any search terms in the uploaded data.")
            
            else:
                st.info("👆 Please select a product ID to explore its search terms and clusters")
        
        # Display selected file
        if selected_file and 'df_to_show' in locals() and df_to_show is not None:
            
            # File information
            display_dataframe_info(df_to_show, f"{selected_file} File Information")
            
            # Data preview
            st.subheader(f"{selected_file} Data Preview")
            
            # Simple controls - only show all columns checkbox
            show_all_cols = st.checkbox("Show all columns", value=True)
            
            # Product selection (only for Products file)
            if selected_file == "Products":
                # Create options for row selection
                row_options = list(range(len(df_to_show)))
                selected_row = st.selectbox(
                    "Select Product Row:",
                    row_options,
                    format_func=lambda x: f"Row {x}: {df_to_show.iloc[x]['title'][:40]}..." if 'title' in df_to_show.columns else f"Row {x}"
                )
            else:
                selected_row = None
            
            # Prepare data for display
            display_df = df_to_show.copy()
            
            # Remove parent_product_id column if it exists (first column)
            if 'parent_product_id' in display_df.columns:
                display_df = display_df.drop('parent_product_id', axis=1)
                st.info("ℹ️ **Note**: parent_product_id column has been hidden from the table")
            
            # Limit columns if needed
            if not show_all_cols and len(display_df.columns) > 10:
                # Show only first 10 columns if too many
                st.info(f"Showing first 10 columns out of {len(display_df.columns)} total")
                display_df = display_df.iloc[:, :10]
            
            # Display the table with vertical scrollbar (showing ~10 rows at a time)
            st.dataframe(display_df, use_container_width=True, height=400)
            
            # Add tips for navigation
            st.info("💡 **Navigation Tips:**")
            st.write("- **Vertical Scroll**: Use the scrollbar to see more products (showing ~10 rows at a time)")
            if len(display_df.columns) > 5:
                st.write("- **Horizontal Scroll**: Use the horizontal scrollbar to see all columns")
            
            # Show selected product details (only for Products file)
            if selected_file == "Products" and selected_row is not None:
                st.subheader("🎯 Selected Product Details")
                
                # Get selected product data
                selected_product = df_to_show.iloc[selected_row]
                
                # Display product information in columns
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Product ID:** {selected_product['product_id']}")
                    if 'title' in selected_product:
                        st.write(f"**Title:** {selected_product['title']}")
                with col2:
                    if 'brand' in selected_product:
                        st.write(f"**Brand:** {selected_product['brand']}")
                    if 'product_type' in selected_product:
                        st.write(f"**Type:** {selected_product['product_type']}")
                
                # Add button to set this product for cluster exploration
                st.write("---")
                if st.button(f"🔍 Use This Product for Search Terms Analysis", type="primary"):
                    st.session_state.selected_product_id_for_clusters = str(selected_product['product_id'])
                    st.success(f"✅ Product {selected_product['product_id']} is now selected for search terms analysis!")
                    st.info("Scroll down to the 'Product-Specific Search Terms Cluster Explorer' section to explore this product's search terms.")
                
                # Show full product details in an expander
                with st.expander("📋 Full Product Details", expanded=False):
                    st.json(selected_product.to_dict())
                
                # Similarity Analysis - Product-Specific Search Terms
                if st.session_state.keywords_df is not None:
                    st.subheader("🎯 Product-Specific Search Terms Analysis")
                    
                    # Filter search terms for the selected product
                    product_search_terms = st.session_state.keywords_df[
                        st.session_state.keywords_df['product_id'] == selected_product['product_id']
                    ]
                    
                    if len(product_search_terms) > 0:
                        st.write(f"**Found {len(product_search_terms)} search terms for this product**")
                        
                        # Show search terms grouped by cluster
                        clusters_for_product = sorted(product_search_terms['cluster_id'].unique())
                        
                        # Reset optimize scores when selecting a new product
                        current_product_id = selected_product['product_id']
                        if st.session_state.get('last_selected_product_id') != current_product_id:
                            st.session_state.cluster_optimize_scores = {}
                            st.session_state.optimized_title = None
                            st.session_state.last_selected_product_id = current_product_id
                        
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"**Found {len(clusters_for_product)} clusters for this product**")
                        with col2:
                            # Refresh button - always enabled, checks for optimized title when clicked
                            if st.button("🔄 Refresh Optimize Scores", key="refresh_optimize_scores"):
                                # Check if we have an optimized title for this product
                                if st.session_state.optimized_title is not None:
                                    st.success("✅ Refreshing with optimized title!")
                                    st.rerun()
                                else:
                                    st.warning("⚠️ No optimized title found. Run the optimizer first!")
                            
                            # Show status
                            if st.session_state.optimized_title is not None:
                                st.caption("✅ Has optimized title")
                            else:
                                st.caption("⚠️ No optimized title")
                        
                        # Calculate similarities for ALL clusters (one row per cluster)
                        with st.spinner("🔍 Calculating similarities for all clusters..."):
                            try:
                                # Prepare data for all clusters
                                cluster_similarities = []
                                
                                for cluster_id in clusters_for_product:
                                    # Get first search term from this cluster
                                    cluster_terms = product_search_terms[
                                        product_search_terms['cluster_id'] == cluster_id
                                    ]
                                    first_term = cluster_terms['search_term'].iloc[0]  # First term in cluster
                                    
                                    # Calculate similarity for this cluster's first term
                                    if st.session_state.encoding_service is not None:
                                        # Use LLM-based similarity
                                        similarities = st.session_state.encoding_service.calculate_similarities(
                                            selected_product['title'], 
                                            [first_term]
                                        )
                                        similarity_score = similarities[0][1]
                                        method = 'LLM Embeddings'
                                    else:
                                        # Use TF-IDF cosine similarity
                                        from sklearn.feature_extraction.text import TfidfVectorizer
                                        from sklearn.metrics.pairwise import cosine_similarity
                                        
                                        texts = [selected_product['title'], first_term]
                                        vectorizer = TfidfVectorizer(stop_words='english', lowercase=True)
                                        tfidf_matrix = vectorizer.fit_transform(texts)
                                        similarity_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
                                        method = 'TF-IDF Cosine'
                                    
                                    # Check if we have optimize score for this cluster
                                    optimize_score = st.session_state.cluster_optimize_scores.get(cluster_id, '')
                                    
                                    cluster_similarities.append({
                                        'Cluster ID': cluster_id,
                                        'First Search Term': first_term,
                                        'Similarity Score': f"{similarity_score:.3f}",
                                        'Optimize Score': optimize_score,
                                        'Method': method,
                                        'Terms Count': len(cluster_terms)
                                    })
                                
                                # Sort by similarity (descending)
                                cluster_similarities.sort(key=lambda x: float(x['Similarity Score']), reverse=True)
                                
                                # Display similarity table for all clusters
                                similarity_df = pd.DataFrame(cluster_similarities)
                                st.dataframe(similarity_df, use_container_width=True)
                                
                                # Show explanation for Optimize Score column
                                if st.session_state.optimized_title:
                                    st.info("💡 **Optimize Score**: Similarity between the optimized title and each cluster's first search term")
                                else:
                                    st.info("💡 **Optimize Score**: Will be calculated after running title optimization")
                                
                                # Show encoding service status
                                if st.session_state.encoding_service is not None:
                                    st.success("🧠 Using LLM-based semantic similarity")
                                else:
                                    st.warning("📝 Using TF-IDF cosine similarity")
                                    st.info("💡 **Want better semantic similarity?** Initialize the LLM encoding service!")
                                    
                                    # Quick initialization option
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        if st.button("🚀 Initialize LLM Encoding Service", key="quick_init"):
                                            try:
                                                with st.spinner("Loading sentence transformer model..."):
                                                    st.session_state.encoding_service = EncodingService(model_name="sentence-transformers/all-MiniLM-L6-v2")
                                                st.success("✅ LLM encoding service initialized!")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"❌ Failed to initialize: {e}")
                                    
                                    with col2:
                                        st.info("Or use the sidebar → 🔤 Encoding Service")
                                
                                # Create a selectbox for detailed view of a specific cluster
                                st.subheader("🔍 Detailed Cluster Analysis")
                                selected_cluster_for_detail = st.selectbox(
                                    "Select Cluster for Detailed Analysis:",
                                    clusters_for_product,
                                    format_func=lambda x: f"Cluster {x} ({len(product_search_terms[product_search_terms['cluster_id'] == x])} terms)"
                                )
                                
                                if selected_cluster_for_detail is not None:
                                    # Get search terms for selected cluster
                                    cluster_terms = product_search_terms[
                                        product_search_terms['cluster_id'] == selected_cluster_for_detail
                                    ]
                                    
                                    # Show search terms for this cluster
                                    st.write(f"**All Search Terms in Cluster {selected_cluster_for_detail}:**")
                                    search_terms_for_cluster = cluster_terms['search_term'].unique()
                                    search_terms_for_cluster = sorted(search_terms_for_cluster)
                                    
                                    for i, term in enumerate(search_terms_for_cluster, 1):
                                        st.write(f"{i}. {term}")
                                    
                            except Exception as e:
                                st.error(f"❌ Error calculating similarities: {e}")
                                st.write("Debug info:")
                                st.write(f"Product title: {selected_product['title']}")
                                st.write(f"Product search terms shape: {product_search_terms.shape}")
                        
                        # Show all search terms for this product in an expander
                        with st.expander("📊 All Search Terms for This Product", expanded=False):
                            all_terms_display = product_search_terms[['cluster_id', 'search_term']].copy()
                            all_terms_display = all_terms_display.sort_values(['cluster_id', 'search_term'])
                            all_terms_display['#'] = range(1, len(all_terms_display) + 1)
                            all_terms_display = all_terms_display[['#', 'cluster_id', 'search_term']]
                            st.dataframe(all_terms_display, use_container_width=True)
                    
                    else:
                        st.warning(f"⚠️ No search terms found for product {selected_product['product_id']}")
                        st.info("This product may not have any associated search terms in the uploaded data.")

                # Title Optimization Section
                if st.session_state.keywords_df is not None:
                    st.subheader("🎯 Title Optimization")
                    
                    # Initialize title optimizer if not already done
                    if 'title_optimizer' not in st.session_state:
                        try:
                            # Import required modules

                            
                            # Load environment variables
                            load_dotenv()
                            
                            # Initialize LLM client
                            api_key = os.getenv("OPENAI_API_KEY")
                            if not api_key:
                                st.error("❌ OPENAI_API_KEY not found in .env file")
                                st.info("Please create a .env file with your OpenAI API key")
                            else:
                                llm_client = LLMClient(
                                    api_key=api_key,
                                    model_name=os.getenv("LLM_MODEL_NAME", "gpt-3.5-turbo")
                                )
                                
                                # Initialize title optimizer
                                st.session_state.title_optimizer = TitleOptimizer(llm_client)
                                st.success("✅ Title optimizer initialized successfully")
                                
                        except ImportError as e:
                            st.error(f"❌ Missing dependencies: {e}")
                            st.info("Please install: pip install openai python-dotenv")
                        except Exception as e:
                            st.error(f"❌ Failed to initialize title optimizer: {e}")
                    
                    # Show search term selection for optimization
                    if 'product_search_terms' in locals() and len(product_search_terms) > 0:
                        st.write("**Select Search Term for Optimization:**")
                        
                        # Get all search terms for this product
                        all_product_terms = product_search_terms['search_term'].unique()
                        all_product_terms = sorted(all_product_terms)
                        
                        # Create a selectbox for all search terms for this product
                        selected_search_term = st.selectbox(
                            "Choose Search Term to Optimize For:",
                            all_product_terms,
                            help="Select the search term you want to optimize the title for"
                        )
                        
                        # Show optimization button
                        if st.button("🚀 Optimize Title", type="primary"):
                            if 'title_optimizer' in st.session_state:
                                try:
                                    # Prepare product data
                                    product_data = ProductData(
                                        product_id=selected_product['product_id'],
                                        current_title=selected_product['title'],
                                        brand=selected_product.get('brand'),
                                        description=selected_product.get('description'),
                                        product_type=selected_product.get('product_type'),
                                        manufacturer=selected_product.get('manufacturer'),
                                        category=selected_product.get('category'),
                                        features=selected_product.get('features', [])
                                    )
                                    
                                    # Optimize title
                                    with st.spinner("🔍 Optimizing title with AI..."):
                                        result = st.session_state.title_optimizer.optimize_title(
                                            product_data, 
                                            selected_search_term
                                        )
                                    
                                    # Store the optimized title for similarity calculation
                                    st.session_state.optimized_title = result.optimized_title
                                    
                                    # Calculate optimize scores for all clusters
                                    with st.spinner("🔄 Calculating optimize scores for all clusters..."):
                                        try:
                                            # Get all clusters for this product
                                            product_search_terms = st.session_state.keywords_df[
                                                st.session_state.keywords_df['product_id'] == selected_product['product_id']
                                            ]
                                            clusters_for_product = sorted(product_search_terms['cluster_id'].unique())
                                            
                                            # Calculate optimize scores for each cluster
                                            for cluster_id in clusters_for_product:
                                                cluster_terms = product_search_terms[
                                                    product_search_terms['cluster_id'] == cluster_id
                                                ]
                                                first_term = cluster_terms['search_term'].iloc[0]
                                                
                                                # Calculate similarity between optimized title and first term
                                                if st.session_state.encoding_service is not None:
                                                    similarities = st.session_state.encoding_service.calculate_similarities(
                                                        result.optimized_title, 
                                                        [first_term]
                                                    )
                                                    optimize_score = similarities[0][1]
                                                else:
                                                    # Use TF-IDF cosine similarity
                                                    from sklearn.feature_extraction.text import TfidfVectorizer
                                                    from sklearn.metrics.pairwise import cosine_similarity
                                                    
                                                    texts = [result.optimized_title, first_term]
                                                    vectorizer = TfidfVectorizer(stop_words='english', lowercase=True)
                                                    tfidf_matrix = vectorizer.fit_transform(texts)
                                                    optimize_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
                                                
                                                # Store the optimize score
                                                st.session_state.cluster_optimize_scores[cluster_id] = f"{optimize_score:.3f}"
                                            
                                            st.success("✅ Optimize scores calculated for all clusters!")
                                            st.info("💡 **Click '🔄 Refresh Optimize Scores' above to see the updated values in the table!**")
                                            
                                        except Exception as e:
                                            st.error(f"❌ Error calculating optimize scores: {e}")
                                    
                                    # Display results
                                    st.subheader("🎯 Optimization Results")
                                    
                                    # Side by side comparison
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.write("**Original Title:**")
                                        st.info(result.original_title)
                                    with col2:
                                        st.write("**Optimized Title:**")
                                        st.success(result.optimized_title)
                                    
                                    # Additional details
                                    st.write(f"**Confidence Score:** {result.confidence_score:.2f}")
                                    st.write(f"**Processing Time:** {result.processing_time:.2f} seconds")
                                    st.write(f"**Model Used:** {result.model_used}")
                                    
                                    # Reasoning
                                    with st.expander("🧠 Optimization Reasoning", expanded=True):
                                        st.write(result.optimization_reasoning)
                                    
                                    # Keywords used
                                    if result.keywords_used:
                                        st.write("**Keywords Incorporated:**")
                                        st.write(", ".join(result.keywords_used))
                                    
                                    # Warnings
                                    if result.warnings:
                                        st.warning("**Warnings:** " + ", ".join(result.warnings))
                                    
                                    # Save optimized title option
                                    if st.button("💾 Save Optimized Title"):
                                        st.success("Title optimization saved!")
                                        # Here you could add logic to save the optimized title
                                        
                                except Exception as e:
                                    st.error(f"❌ Error during optimization: {e}")
                                    st.info("Please check your API key and try again")
                            else:
                                st.error("❌ Title optimizer not initialized")
                    else:
                        st.info("📊 No search terms found for this product. Upload a search terms CSV file that contains data for this product.")
                else:
                    st.info("📁 Upload Search Terms Clusters CSV to see similarity analysis")
    
    else:
        # No files loaded
        st.info("👈 Upload CSV files in the sidebar to get started")
        
        st.markdown("""
        ### Expected File Formats:
        
        **Products CSV:**
        ```
        product_id,title,brand,description,product_type,manufacturer
        B12345,"LED Light Bulb 60W","Philips","Energy efficient bulb","Electronics","Philips"
        ```
        
        **Keywords CSV:**
        ```
        product_id,search_term,cluster_id
        B12345,"led flood light",1
        B12345,"outdoor lighting",1
        ```
        """)
    
    # Session state info (for debugging)
    with st.expander("Debug Info"):
        st.write("**Session State:**")
        debug_info = {
            "products_loaded": st.session_state.products_df is not None,
            "keywords_loaded": st.session_state.keywords_df is not None,
            "encoding_service_initialized": st.session_state.encoding_service is not None,
            "products_cache_exists": PRODUCTS_CACHE.exists(),
            "keywords_cache_exists": KEYWORDS_CACHE.exists()
        }
        if st.session_state.products_df is not None:
            debug_info["products_shape"] = st.session_state.products_df.shape
        if st.session_state.keywords_df is not None:
            debug_info["keywords_shape"] = st.session_state.keywords_df.shape
        if st.session_state.encoding_service is not None:
            debug_info["encoding_model"] = st.session_state.encoding_service.model_name
        
        st.json(debug_info)

if __name__ == "__main__":
    main()