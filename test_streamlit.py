import streamlit as st

st.title("Test Streamlit App")
st.write("Hello World!")
st.write("If you can see this, Streamlit is working!")

# Add a simple widget
name = st.text_input("Enter your name:")
if name:
    st.write(f"Hello, {name}!")

# Add a button
if st.button("Click me!"):
    st.balloons()
    st.success("Button clicked!")
