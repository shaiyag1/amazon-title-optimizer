import streamlit as st
import difflib
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
from src.services.encoding_service import EncodingService

# Diff rendering helper using word-level comparison
def render_diff_html(original_text: str, revised_text: str) -> tuple[str, str]:
    """Return (original_html, revised_html) with deletions in red and additions in green."""
    a_words = (original_text or "").split()
    b_words = (revised_text or "").split()
    diff = difflib.SequenceMatcher(None, a_words, b_words)
    original_html_parts = []
    revised_html_parts = []
    for tag, i1, i2, j1, j2 in diff.get_opcodes():
        if tag == "equal":
            original_html_parts.extend(a_words[i1:i2])
            revised_html_parts.extend(b_words[j1:j2])
        elif tag == "delete":
            original_html_parts.extend([
                f'<span style="background-color: #ffebee; color: #c62828; text-decoration: line-through;">{word}</span>'
                for word in a_words[i1:i2]
            ])
        elif tag == "replace":
            original_html_parts.extend([
                f'<span style="background-color: #ffebee; color: #c62828; text-decoration: line-through;">{word}</span>'
                for word in a_words[i1:i2]
            ])
            revised_html_parts.extend([
                f'<span style="background-color: #e8f5e8; color: #2e7d32; font-weight: bold;">{word}</span>'
                for word in b_words[j1:j2]
            ])
        elif tag == "insert":
            revised_html_parts.extend([
                f'<span style="background-color: #e8f5e8; color: #2e7d32; font-weight: bold;">{word}</span>'
                for word in b_words[j1:j2]
            ])
    return (" ".join(original_html_parts), " ".join(revised_html_parts))
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
        # Initialize encoding service for similarity scoring
        try:
            st.session_state.encoding_service = EncodingService(
                model_name=os.getenv("ENCODING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            )
        except Exception as e:
            st.session_state.encoding_service = None
            st.warning(f"Embedding service unavailable: {e}. Install sentence-transformers to enable similarity.")

    # Default sample data
    default_title = "Wireless Bluetooth Headphones with Noise Cancellation"
    default_features = """• Active Noise Cancellation Technology
• 30-hour battery life with quick charge
• Premium sound quality with deep bass
• Comfortable over-ear design
• Built-in microphone for calls
• Foldable and portable design"""
    default_description = "Experience premium audio with these wireless Bluetooth headphones featuring active noise cancellation technology. Enjoy up to 30 hours of battery life with quick charge capability. The comfortable over-ear design provides excellent sound isolation while the built-in microphone ensures crystal clear calls. Perfect for music lovers, commuters, and professionals who demand quality audio."
    
    # Available search terms for selection
    available_search_terms = [
        "wireless headphones",
        "bluetooth headphones", 
        "noise cancelling headphones",
        "over ear headphones",
        "premium audio",
        "active noise cancellation",
        "30 hour battery",
        "quick charge",
        "premium sound",
        "deep bass",
        "comfortable design",
        "wireless bluetooth",
        "noise cancellation",
        "battery life",
        "crystal clear calls",
        "foldable design",
        "portable headphones",
        "music lovers",
        "commuters",
        "professionals"
    ]
    
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
    loaded_terms = available_search_terms[:5]  # Default to first 5 terms
    if loaded_product and loaded_product.get('search_term_list'):
        loaded_terms = [term.strip() for term in loaded_product['search_term_list'].split(',') if term.strip()]

    # Create dynamic search terms list (include loaded terms if they exist)
    dynamic_search_terms = list(available_search_terms)
    if loaded_product and loaded_product.get('search_term_list'):
        # Add any loaded terms that aren't already in our list
        for term in loaded_terms:
            if term not in dynamic_search_terms:
                dynamic_search_terms.append(term)

    # Search term selection section
    st.markdown("### 🔍 Search Term Selection")
    
    # Global search term selection
    selected_global_terms = st.multiselect(
        "Select Search Terms (shared across all sections):",
        options=dynamic_search_terms,
        default=loaded_terms,
        key="global_search_terms"
    )
    
    # Independent search terms checkbox
    use_independent_terms = st.checkbox(
        "Use Independent Search Terms per Section", 
        value=False,
        help="If checked, each section can have different search terms"
    )

    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Weight configuration
        st.markdown("### 📝 Input Content")
        weight_col1, weight_col2, weight_col3, weight_col4 = st.columns([1, 1, 1, 1])
        with weight_col1:
            title_weight = st.number_input("Title Weight", min_value=0.0, max_value=1.0, value=0.6, step=0.1, key="title_weight")
        with weight_col2:
            bullets_weight = st.number_input("Bullets Weight", min_value=0.0, max_value=1.0, value=0.3, step=0.1, key="bullets_weight")
        with weight_col3:
            description_weight = st.number_input("Description Weight", min_value=0.0, max_value=1.0, value=0.1, step=0.1, key="description_weight")
        with weight_col4:
            total_weight = title_weight + bullets_weight + description_weight
            st.metric("Total", f"{total_weight:.1f}", help="Should ideally equal 1.0")
        
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
            if use_independent_terms:
                title_terms = st.multiselect(
                    "Title Search Terms:",
                    options=dynamic_search_terms,
                    default=selected_global_terms,
                    key="title_terms_select"
                )
            else:
                st.markdown("**Using Global Search Terms**")
                st.write(", ".join(selected_global_terms))
                title_terms = selected_global_terms
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
            if use_independent_terms:
                features_terms = st.multiselect(
                    "Features Search Terms:",
                    options=dynamic_search_terms,
                    default=selected_global_terms,
                    key="features_terms_select"
                )
            else:
                st.markdown("**Using Global Search Terms**")
                st.write(", ".join(selected_global_terms))
                features_terms = selected_global_terms
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
            if use_independent_terms:
                description_terms = st.multiselect(
                    "Description Search Terms:",
                    options=dynamic_search_terms,
                    default=selected_global_terms,
                    key="description_terms_select"
                )
            else:
                st.markdown("**Using Global Search Terms**")
                st.write(", ".join(selected_global_terms))
                description_terms = selected_global_terms
        optimize_description = st.checkbox("Optimize Description", value=True, key="optimize_description_check")
    
    with col2:
        st.subheader("🎯 Optimization Results")
        
        if st.button("🚀 Optimize Content", type="primary", use_container_width=True):
            if not any([optimize_title, optimize_features, optimize_description]):
                st.warning("Please select at least one component to optimize!")
            else:
                with st.spinner("Optimizing content..."):
                    try:
                        # Search terms are already lists from multiselect
                        title_search_terms = title_terms if isinstance(title_terms, list) else [term.strip() for term in title_terms.split('\n') if term.strip()]
                        features_search_terms = features_terms if isinstance(features_terms, list) else [term.strip() for term in features_terms.split('\n') if term.strip()]
                        description_search_terms = description_terms if isinstance(description_terms, list) else [term.strip() for term in description_terms.split('\n') if term.strip()]
                        
                        # Create ProductData object
                        product_data = ProductData(
                            product_id="simple_optimizer",
                            current_title=title_text,
                            features=[features_text] if features_text else [],
                            description=(description_text if (description_text and description_text.strip()) else (title_text or "")),
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
                            col3.metric("Processing Time", f"{results['title'].processing_time:.2f}s")
                            # Show preservation metrics if available
                            if hasattr(results['title'], 'preservation_score') and results['title'].preservation_score:
                                col2.metric("Preservation", f"{results['title'].preservation_score:.1f}%")
                        
                        # Description Results
                        if 'description' in results:
                            st.markdown("#### 📝 Optimized Description")
                            st.write(results['description'].optimized_description)
                            
                            st.markdown("#### 📊 Description Metrics")
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Confidence", f"{results['description'].confidence_score:.2f}")
                            col3.metric("Processing Time", f"{results['description'].processing_time:.2f}s")
                            # Show preservation metrics if available
                            if hasattr(results['description'], 'preservation_score') and results['description'].preservation_score:
                                col2.metric("Preservation", f"{results['description'].preservation_score:.1f}%")
                        
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

                        # Side-by-side Original vs Optimized Content (with highlights)
                        st.markdown("---")
                        st.markdown("### 🧾 Original vs Optimized Content")
                        # Title
                        st.markdown("#### Title")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.caption("Original")
                            orig_html, _ = render_diff_html(title_text or "", (results['title'].optimized_title if 'title' in results else (title_text or "")))
                            st.markdown(orig_html, unsafe_allow_html=True)
                        with c2:
                            st.caption("Optimized")
                            _, rev_html = render_diff_html(title_text or "", (results['title'].optimized_title if 'title' in results else (title_text or "")))
                            st.markdown(rev_html, unsafe_allow_html=True)
                        
                        # Bullets/Features
                        st.markdown("#### Features/Bullets")
                        c3, c4 = st.columns(2)
                        with c3:
                            st.caption("Original")
                            optimized_features_text = None
                            if 'title' in results and getattr(results['title'], 'refined_features', None):
                                optimized_features_text = results['title'].refined_features
                            orig_feat_html, _ = render_diff_html(features_text or "", optimized_features_text if optimized_features_text is not None else (features_text or ""))
                            st.markdown(orig_feat_html, unsafe_allow_html=True)
                        with c4:
                            st.caption("Optimized")
                            _, rev_feat_html = render_diff_html(features_text or "", optimized_features_text if optimized_features_text is not None else (features_text or ""))
                            st.markdown(rev_feat_html, unsafe_allow_html=True)
                        
                        # Description
                        st.markdown("#### Description")
                        c5, c6 = st.columns(2)
                        with c5:
                            st.caption("Original")
                            orig_desc_html, _ = render_diff_html(description_text or "", (results['description'].optimized_description if 'description' in results else (description_text or "")))
                            st.markdown(orig_desc_html, unsafe_allow_html=True)
                        with c6:
                            st.caption("Optimized")
                            _, rev_desc_html = render_diff_html(description_text or "", (results['description'].optimized_description if 'description' in results else (description_text or "")))
                            st.markdown(rev_desc_html, unsafe_allow_html=True)
                        
                    except Exception as e:
                        st.error(f"❌ Error during optimization: {str(e)}")
                        st.exception(e)

        # Similarity Matrix Section (below description)
        st.markdown("---")
        st.markdown("### 📈 Similarity Matrix (Selected Terms vs Content)")
        if 'encoding_service' in st.session_state and st.session_state.encoding_service is not None:
            try:
                # Collect selected terms based on mode
                def _as_list(terms):
                    if isinstance(terms, list):
                        return terms
                    return [t.strip() for t in str(terms).split("\n") if t.strip()]

                if use_independent_terms:
                    candidate_terms = _as_list(title_terms) + _as_list(features_terms) + _as_list(description_terms)
                else:
                    candidate_terms = _as_list(selected_global_terms)

                # Deduplicate while preserving order
                seen_terms = set()
                selected_terms_unique = []
                for t in candidate_terms:
                    if t not in seen_terms:
                        seen_terms.add(t)
                        selected_terms_unique.append(t)

                if not selected_terms_unique:
                    st.info("No search terms selected.")
                else:
                    enc = st.session_state.encoding_service
                    # Prepare content texts (use current inputs)
                    title_text_for_sim = title_text or ""
                    bullets_text_for_sim = features_text or ""
                    description_text_for_sim = description_text or ""

                    # Encode contents
                    content_embeddings = enc.encode_texts_batch(
                        [title_text_for_sim, bullets_text_for_sim, description_text_for_sim],
                        cache_type="product",
                        show_progress=False
                    )
                    title_emb, bullets_emb, description_emb = content_embeddings

                    # Encode terms
                    term_embeddings = enc.encode_texts_batch(selected_terms_unique, cache_type="search_term", show_progress=False)

                    # Build rows
                    rows = []
                    for term, term_emb in zip(selected_terms_unique, term_embeddings):
                        rows.append({
                            "Search Term": term,
                            "Title": round(enc.cosine_similarity(term_emb, title_emb), 3),
                            "Bullets": round(enc.cosine_similarity(term_emb, bullets_emb), 3),
                            "Description": round(enc.cosine_similarity(term_emb, description_emb), 3)
                        })

                    # Display table
                    st.table(rows)
            except Exception as e:
                st.error(f"Failed to compute similarity matrix: {e}")
        else:
            st.info("Initialize embedding service to view similarity scores (sentence-transformers required).")

        # Optimized Similarity Matrix (uses optimized content when available)
        st.markdown("---")
        st.markdown("### 📈 Optimized Similarity Matrix (After Optimization)")
        if 'encoding_service' in st.session_state and st.session_state.encoding_service is not None:
            try:
                # Collect selected terms based on mode
                def _as_list(terms):
                    if isinstance(terms, list):
                        return terms
                    return [t.strip() for t in str(terms).split("\n") if t.strip()]

                if use_independent_terms:
                    candidate_terms = _as_list(title_terms) + _as_list(features_terms) + _as_list(description_terms)
                else:
                    candidate_terms = _as_list(selected_global_terms)

                # Deduplicate while preserving order
                seen_terms = set()
                selected_terms_unique = []
                for t in candidate_terms:
                    if t not in seen_terms:
                        seen_terms.add(t)
                        selected_terms_unique.append(t)

                if not selected_terms_unique:
                    st.info("No search terms selected.")
                else:
                    enc = st.session_state.encoding_service
                    # Prefer optimized content when present
                    optimized_title_text = results['title'].optimized_title if ('results' in locals() and isinstance(results, dict) and 'title' in results and getattr(results['title'], 'optimized_title', None)) else None
                    optimized_bullets_text = results['title'].refined_features if ('results' in locals() and isinstance(results, dict) and 'title' in results and getattr(results['title'], 'refined_features', None) is not None) else None
                    optimized_description_text = results['description'].optimized_description if ('results' in locals() and isinstance(results, dict) and 'description' in results and getattr(results['description'], 'optimized_description', None)) else None

                    title_text_for_sim = optimized_title_text or (title_text or "")
                    bullets_text_for_sim = optimized_bullets_text if optimized_bullets_text is not None else (features_text or "")
                    description_text_for_sim = optimized_description_text or (description_text or "")

                    # Encode contents
                    content_embeddings = enc.encode_texts_batch(
                        [title_text_for_sim, bullets_text_for_sim, description_text_for_sim],
                        cache_type="product",
                        show_progress=False
                    )
                    title_emb, bullets_emb, description_emb = content_embeddings

                    # Encode terms
                    term_embeddings = enc.encode_texts_batch(selected_terms_unique, cache_type="search_term", show_progress=False)

                    # Build rows
                    rows = []
                    for term, term_emb in zip(selected_terms_unique, term_embeddings):
                        rows.append({
                            "Search Term": term,
                            "Title": round(enc.cosine_similarity(term_emb, title_emb), 3),
                            "Bullets": round(enc.cosine_similarity(term_emb, bullets_emb), 3),
                            "Description": round(enc.cosine_similarity(term_emb, description_emb), 3)
                        })

                    # Display table
                    st.table(rows)
            except Exception as e:
                st.error(f"Failed to compute optimized similarity matrix: {e}")
        else:
            st.info("Initialize embedding service to view similarity scores (sentence-transformers required).")

        # Export Product section
        st.markdown("---")
        if st.button("💾 Export Product", use_container_width=True):
            try:
                import csv
                csv_path = os.path.join(os.path.dirname(__file__), "..", "product_content_list.csv")
                csv_path = os.path.abspath(csv_path)

                # Build combined, deduplicated search term list preserving order
                def _get_terms(terms):
                    if isinstance(terms, list):
                        return terms
                    else:
                        return [t.strip() for t in terms.split("\n") if t.strip()]

                combined_terms = []
                seen = set()
                for term in _get_terms(title_terms) + _get_terms(features_terms) + _get_terms(description_terms):
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
