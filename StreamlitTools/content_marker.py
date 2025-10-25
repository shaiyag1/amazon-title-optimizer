import streamlit as st
import difflib

def main():
    st.set_page_config(
        page_title="Content Marker - Text Comparison Tool",
        page_icon="📝",
        layout="wide"
    )
    
    st.title("📝 Content Marker - Text Comparison Tool")
    st.markdown("Compare two versions of text and see the differences highlighted with colors.")
    
    # Sidebar for instructions
    with st.sidebar:
        st.header("How to Use")
        st.markdown("""
        1. **Enter Original Text** - Your base text
        2. **Enter Revised Text** - The modified version
        3. **Click Compare** - See the differences highlighted
        
        **Color Legend:**
        - 🔴 **Red with strikethrough** - Deleted words
        - 🟢 **Green bold** - Added words
        - ⚫ **Black** - Unchanged words
        """)
        
        st.header("Sample Data")
        if st.button("Load Sample"):
            st.session_state.original_text = """Massive Size: These enormous 6-inch dough ball stress balls are perfect for relieving stress and anxiety in those extra stressful moments. Measures 5.5 - 6" depending on the lay of the ball.
Beautiful Gift Box: This huge jumbo squishy dough ball stress toy comes beautifully packaged in an easy to wrap box gift box for super easy gifting. Perfect present for kids, adults and anyone who enjoys the finer sensory things in life. Give it as gag gifts for Christmas or an office party and enjoy the laughs!"""
            
            st.session_state.revised_text = """Massive Size: These enormous 6-inch dough ball stress balls are perfect for relieving stress and anxiety in those extra stressful moments. Measures 5.5 - 6" depending on the lay of the ball.
Beautiful Gift Box: This huge medium squishy dough ball stress toy comes beautifully packaged in an easy to wrap box gift box for super easy gifting. Perfect present for boys and girls, adults and anyone who enjoys the finer sensory things in life. Give it as gag gifts for Christmas or an office party and enjoy the laughs!"""
    
    # Initialize session state with default text
    if 'original_text' not in st.session_state:
        st.session_state.original_text = """Massive Size: These enormous 6-inch dough ball stress balls are perfect for relieving stress and anxiety in those extra stressful moments. Measures 5.5 - 6" depending on the lay of the ball.
Beautiful Gift Box: This huge jumbo squishy dough ball stress toy comes beautifully packaged in an easy to wrap box gift box for super easy gifting. Perfect present for kids, adults and anyone who enjoys the finer sensory things in life. Give it as gag gifts for Christmas or an office party and enjoy the laughs!"""
    
    if 'revised_text' not in st.session_state:
        st.session_state.revised_text = """Massive Size: These enormous 6-inch dough ball stress balls are perfect for relieving stress and anxiety in those extra stressful moments. Measures 5.5 - 6" depending on the lay of the ball.
Beautiful Gift Box: This huge medium squishy dough ball stress toy comes beautifully packaged in an easy to wrap box gift box for super easy gifting. Perfect present for boys and girls, adults and anyone who enjoys the finer sensory things in life. Give it as gag gifts for Christmas or an office party and enjoy the laughs!"""
    
    # Main content area
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 Original Text")
        original_text = st.text_area(
            "Enter your original text here:",
            value=st.session_state.original_text,
            height=300,
            key="original_input",
            help="This is your base text that will be compared against the revised version."
        )
    
    with col2:
        st.subheader("✏️ Revised Text")
        revised_text = st.text_area(
            "Enter your revised text here:",
            value=st.session_state.revised_text,
            height=300,
            key="revised_input",
            help="This is the modified version that will be compared against the original."
        )
    
    # Compare button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        compare_button = st.button("🔍 Compare Texts", type="primary", use_container_width=True)
    
    # Display results
    if compare_button and original_text.strip() and revised_text.strip():
        st.markdown("---")
        st.subheader("📊 Comparison Results")
        
        # Simple word-by-word comparison
        a_words = original_text.split()
        b_words = revised_text.split()
        diff = difflib.SequenceMatcher(None, a_words, b_words)
        
        # Create HTML for differences
        original_html = []
        revised_html = []
        
        for tag, i1, i2, j1, j2 in diff.get_opcodes():
            if tag == "equal":
                original_html.extend(a_words[i1:i2])
                revised_html.extend(b_words[j1:j2])
            elif tag == "delete":
                original_html.extend([f'<span style="background-color: #ffebee; color: #c62828; text-decoration: line-through;">{word}</span>' for word in a_words[i1:i2]])
            elif tag == "replace":
                original_html.extend([f'<span style="background-color: #ffebee; color: #c62828; text-decoration: line-through;">{word}</span>' for word in a_words[i1:i2]])
                revised_html.extend([f'<span style="background-color: #e8f5e8; color: #2e7d32; font-weight: bold;">{word}</span>' for word in b_words[j1:j2]])
            elif tag == "insert":
                revised_html.extend([f'<span style="background-color: #e8f5e8; color: #2e7d32; font-weight: bold;">{word}</span>' for word in b_words[j1:j2]])
        
        # Display side by side
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Original Text (with deletions highlighted):**")
            st.markdown(" ".join(original_html), unsafe_allow_html=True)
        
        with col2:
            st.markdown("**Revised Text (with additions highlighted):**")
            st.markdown(" ".join(revised_html), unsafe_allow_html=True)
        
        # Statistics
        st.markdown("---")
        st.subheader("📈 Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            original_words = len(original_text.split())
            st.metric("Original Word Count", original_words)
        
        with col2:
            revised_words = len(revised_text.split())
            st.metric("Revised Word Count", revised_words)
        
        with col3:
            word_diff = revised_words - original_words
            st.metric("Word Difference", f"{word_diff:+d}")
        
        with col4:
            if original_words > 0:
                change_percentage = (abs(word_diff) / original_words) * 100
                st.metric("Change Percentage", f"{change_percentage:.1f}%")
        
        # Detailed diff analysis
        st.markdown("---")
        st.subheader("🔍 Detailed Analysis")
        
        # Calculate detailed statistics
        deletions = 0
        insertions = 0
        replacements = 0
        
        for tag, i1, i2, j1, j2 in diff.get_opcodes():
            if tag == "delete":
                deletions += (i2 - i1)
            elif tag == "insert":
                insertions += (j2 - j1)
            elif tag == "replace":
                replacements += min(i2 - i1, j2 - j1)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Words Deleted", deletions)
        with col2:
            st.metric("Words Added", insertions)
        with col3:
            st.metric("Words Replaced", replacements)
        
        # Similarity score
        similarity = diff.ratio() * 100
        st.metric("Similarity Score", f"{similarity:.1f}%")
        
        # Progress bar for similarity
        st.progress(similarity / 100)
        
    elif compare_button:
        st.warning("⚠️ Please enter both original and revised text to compare.")
    
    # Footer
    st.markdown("---")
    st.markdown("**Content Marker** - A tool for comparing text versions and highlighting differences.")

if __name__ == "__main__":
    main()
    