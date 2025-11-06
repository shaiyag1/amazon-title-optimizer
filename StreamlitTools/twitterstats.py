import streamlit as st
import pandas as pd
import json
import boto3
import base64
from datetime import datetime


def build_twitter_url(url_type: str, **kwargs) -> str:
    """
    Modular function to build Twitter/X URLs
    
    Args:
        url_type: Type of URL to build - 'tweet', 'profile', 'search'
        **kwargs: Additional parameters based on url_type
            - For 'tweet': requires 'tweet_id' or ('username', 'tweet_id')
            - For 'profile': requires 'username'
            - For 'search': requires 'query'
    
    Returns:
        str: Formatted Twitter/X URL
        
    Examples:
        build_twitter_url('tweet', tweet_id='1234567890')
        build_twitter_url('tweet', username='elonmusk', tweet_id='1234567890')
        build_twitter_url('profile', username='elonmusk')
        build_twitter_url('search', query='python programming')
    """
    base_url = "https://twitter.com"
    
    if url_type == 'tweet':
        if 'tweet_id' in kwargs:
            return f"{base_url}/i/web/status/{kwargs['tweet_id']}"
        elif 'username' in kwargs and 'tweet_id' in kwargs:
            return f"{base_url}/{kwargs['username']}/status/{kwargs['tweet_id']}"
        else:
            return ""
    
    elif url_type == 'profile':
        if 'username' in kwargs:
            # Remove @ if present
            username = kwargs['username'].lstrip('@')
            return f"{base_url}/{username}"
        else:
            return ""
    
    elif url_type == 'search':
        if 'query' in kwargs:
            from urllib.parse import quote_plus
            encoded_query = quote_plus(kwargs['query'])
            return f"{base_url}/search?q={encoded_query}"
        else:
            return ""
    
    else:
        return ""

class DBAdapter:
    def __init__(self, args: dict):
        self.client = boto3.client('rds-data')
        self.args = args
    
    def query(self, sql):
        result = self.client.execute_statement(
            secretArn=self.args['secretArn'],
            resourceArn=self.args['resourceArn'],
            sql=sql,
            formatRecordsAs='JSON'
        )
        return json.loads(result['formattedRecords'])
    
    def close(self):
        self.client.close()

class SecretsManager:
    client = boto3.client(
        'secretsmanager',
        region_name='us-east-1'
    )
    
    def get_secret(self, secret_id):
        try:
            get_secret_value_response = self.client.get_secret_value(
                SecretId=secret_id
            )
        except Exception as e:
            st.error(f"Error getting secret: {e}")
            raise e
        else:
            if 'SecretString' in get_secret_value_response:
                secret = get_secret_value_response['SecretString']
                return json.loads(secret)
            else:
                decoded_binary_secret = base64.b64decode(
                    get_secret_value_response['SecretBinary']
                )
                return json.loads(decoded_binary_secret)

# Streamlit App
st.set_page_config(page_title="Top Tweets Analysis", layout="wide")

st.title("🔥 Top 3 Tweets Per Hour - Last 10 Hours")

# Add refresh button and options at the top
col_refresh, col_normalize, col_empty = st.columns([1, 2, 7])
with col_refresh:
    if st.button("🔄 Refresh Data"):
        st.rerun()
with col_normalize:
    normalize_time = st.checkbox("Normalize Time (Likes per Minute)", value=False, key="normalize_time")

st.markdown("---")

# SQL Query - Get main data
sql = """
WITH ranked_tweets AS (
    SELECT 
        DATE_TRUNC('hour', tmh.created_at) as hour,
        tmh.id,
        tmh.author_username,
        MAX(tmh.like_count) as likes,
        MAX(tmh.reply_count) as replies,
        MAX(tmh.retweet_count) as retweets,
        ROW_NUMBER() OVER (
            PARTITION BY DATE_TRUNC('hour', tmh.created_at) 
            ORDER BY MAX(tmh.like_count) DESC
        ) as rank
    FROM twitter.tweets_metrics_history tmh
    WHERE tmh.created_at >= NOW() - INTERVAL '10 hours'
    GROUP BY DATE_TRUNC('hour', tmh.created_at), tmh.id, tmh.author_username
)
SELECT 
    rt.hour,
    rt.rank,
    rt.id,
    rt.author_username,
    rt.likes,
    rt.replies,
    rt.retweets,
    t.text as tweet_text
FROM ranked_tweets rt
LEFT JOIN twitter.tweets t ON rt.id = t.id
WHERE rt.rank <= 3
ORDER BY rt.hour ASC, rt.rank ASC;
"""

# Function to get sampling times and likes for a specific tweet
def get_sampling_times_with_likes(tweet_id: int, db_adapter, max_time=None) -> tuple:
    """
    Get the sampling times and corresponding like counts for a specific tweet
    
    Args:
        tweet_id: The tweet ID
        db_adapter: Database adapter
        max_time: Optional maximum time filter (only show times up to this point)
                  Can be a string, pandas Timestamp, or other datetime object
    
    Returns:
        tuple: (list of timestamps, list of like_counts) sorted descending by time
    """
    if max_time:
        # Convert max_time to string format for PostgreSQL
        if pd.isna(max_time):
            where_clause = f"WHERE tmh.id = {tweet_id}"
        else:
            # Convert to string and format for PostgreSQL
            if isinstance(max_time, pd.Timestamp):
                max_time_str = max_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                max_time_str = str(max_time)
            where_clause = f"WHERE tmh.id = {tweet_id} AND tmh.created_at <= '{max_time_str}'"
    else:
        where_clause = f"WHERE tmh.id = {tweet_id}"
    
    sampling_sql = f"""
    SELECT DISTINCT tmh.created_at as sampling_time, tmh.like_count as likes
    FROM twitter.tweets_metrics_history tmh
    {where_clause}
    ORDER BY tmh.created_at DESC
    LIMIT 10;
    """
    try:
        result = db_adapter.query(sampling_sql)
        timestamps = [pd.to_datetime(row.get('sampling_time')) for row in result if row.get('sampling_time')]
        likes = [int(row.get('likes', 0)) for row in result if row.get('sampling_time')]
        return (timestamps, likes)
    except Exception as e:
        st.error(f"Error fetching sampling times with likes: {e}")
        return ([], [])

# Function to get sampling times for a specific tweet (legacy function for compatibility)
def get_sampling_times(tweet_id: int, db_adapter, max_time=None) -> list:
    """
    Get the sampling times for a specific tweet
    
    Args:
        tweet_id: The tweet ID
        db_adapter: Database adapter
        max_time: Optional maximum time filter (only show times up to this point)
                  Can be a string, pandas Timestamp, or other datetime object
    """
    timestamps, _ = get_sampling_times_with_likes(tweet_id, db_adapter, max_time)
    return timestamps

# Function to calculate likes per minute from last two timestamps
def calculate_likes_per_minute(tweet_id: int, db_adapter, max_time=None) -> float:
    """
    Calculate the likes per minute based on the last two sampling timestamps
    
    Args:
        tweet_id: The tweet ID
        db_adapter: Database adapter
        max_time: Optional maximum time filter
    
    Returns:
        float: Likes per minute (or 0 if unable to calculate)
    """
    timestamps, likes = get_sampling_times_with_likes(tweet_id, db_adapter, max_time)
    
    if len(timestamps) < 2 or len(likes) < 2:
        return 0.0
    
    # Calculate delta: (likes_newest - likes_oldest) / minutes_between
    delta_likes = likes[0] - likes[-1]  # Most recent - oldest
    delta_minutes = (timestamps[0] - timestamps[-1]).total_seconds() / 60.0
    
    if delta_minutes <= 0:
        return 0.0
    
    return delta_likes / delta_minutes

# Fetch data
try:
    # Initialize session state for DB connection if not exists
    if 'db_adapter' not in st.session_state:
        with st.spinner("Initializing database connection..."):
            db_secret_name = 'main-rds-cluster'
            sm = SecretsManager()
            st.session_state.db_adapter = DBAdapter(sm.get_secret(db_secret_name))
    
    with st.spinner("Fetching data from database..."):
        response = st.session_state.db_adapter.query(sql)
    
    # Convert to DataFrame
    df = pd.DataFrame(response)
    
    if df.empty:
        st.warning("No data found for the last 10 hours.")
    else:
        # Format the data
        df['hour'] = pd.to_datetime(df['hour'])
        df['hour_display'] = df['hour'].dt.strftime('%Y-%m-%d %H:%M')
        df['likes'] = df['likes'].astype(int)
        df['replies'] = df['replies'].astype(int)
        df['retweets'] = df['retweets'].astype(int)
        df['tweet_text'] = df['tweet_text'].fillna('(No text available)')
        
        # If normalize_time is enabled, recalculate ranks based on likes per minute
        if normalize_time:
            with st.spinner("Calculating likes per minute for all tweets..."):
                # Calculate likes per minute for each tweet
                df['likes_per_minute'] = df.apply(
                    lambda row: calculate_likes_per_minute(
                        int(row['id']), 
                        st.session_state.db_adapter, 
                        max_time=row['hour'] + pd.Timedelta(hours=1)
                    ),
                    axis=1
                )
                
                # Re-rank within each hour based on likes per minute
                df['rank'] = df.groupby('hour')['likes_per_minute'].rank(ascending=False, method='dense').astype(int)
                
                # Only keep top 3 ranks per hour
                df = df[df['rank'] <= 3].copy()
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Hours", df['hour'].nunique())
        with col2:
            st.metric("Total Tweets", len(df))
        with col3:
            st.metric("Total Likes", f"{df['likes'].sum():,}")
        with col4:
            st.metric("Total Retweets", f"{df['retweets'].sum():,}")
        
        st.markdown("---")
        
        # Group by hour and display
        hours = df['hour'].unique()
        
        # Initialize session state for tweet selection
        if 'selected_tweet' not in st.session_state:
            st.session_state.selected_tweet = None
        
        # Sidebar for tweet details
        with st.sidebar:
            st.header("📋 Tweet Details")
            if st.session_state.selected_tweet is not None:
                selected_row = df[df['id'] == st.session_state.selected_tweet].iloc[0]
                
                # Build URLs for the selected tweet
                tweet_url = build_twitter_url('tweet', tweet_id=int(selected_row['id']))
                profile_url = build_twitter_url('profile', username=selected_row['author_username'])
                
                st.markdown("### Tweet Information")
                st.markdown(f"**@{selected_row['author_username']}**")
                st.markdown(f"**Hour:** {pd.to_datetime(selected_row['hour']).strftime('%Y-%m-%d %H:%M')}")
                st.markdown(f"**Rank:** #{int(selected_row['rank'])}")
                st.markdown("---")
                st.markdown("### Tweet Text")
                st.markdown(f"""<div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 4px solid #1f77b4; word-wrap: break-word;">
                {selected_row['tweet_text']}
                </div>""", unsafe_allow_html=True)
                st.markdown("---")
                st.markdown("### Engagement Metrics")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("❤️ Likes", f"{int(selected_row['likes']):,}")
                with col2:
                    st.metric("💬 Replies", f"{int(selected_row['replies']):,}")
                with col3:
                    st.metric("🔄 Retweets", f"{int(selected_row['retweets']):,}")
                st.markdown("---")
                st.markdown(f"**Tweet ID:** `{int(selected_row['id'])}`")
                
                # Add clickable URL links
                st.markdown("### Links")
                st.markdown(f"[🐦 Open Tweet on X/Twitter]({tweet_url})", unsafe_allow_html=True)
                st.markdown(f"[👤 Open Profile on X/Twitter]({profile_url})", unsafe_allow_html=True)
                
                if st.button("❌ Clear Selection"):
                    st.session_state.selected_tweet = None
                    st.rerun()
            else:
                st.info("👆 Click on any tweet card or row below to view details")
        
        for hour in sorted(hours):
            hour_data = df[df['hour'] == hour].sort_values('rank')
            hour_display = pd.to_datetime(hour).strftime('%Y-%m-%d %H:%M')
            
            st.subheader(f"📅 {hour_display}")
            
            # Add expander for this hour's sampling times
            with st.expander("📊 Sampling Times for This Hour", expanded=False):
                with st.spinner("Fetching sampling times..."):
                    for _, row in hour_data.iterrows():
                        # Get sampling times up to and including this hour
                        # Note: We use hour + 1 hour to include all data within the hour window
                        end_of_hour = hour + pd.Timedelta(hours=1)
                        sampling_times = get_sampling_times(int(row['id']), st.session_state.db_adapter, max_time=end_of_hour)
                        
                        st.markdown("---")
                        st.markdown(f"**Rank {int(row['rank'])}** | **@{row['author_username']}** | ID: `{int(row['id'])}`")
                        
                        if sampling_times:
                            st.markdown("**Sampling Times:**")
                            for i, sample_time in enumerate(sampling_times, 1):
                                formatted_time = pd.to_datetime(sample_time).strftime('%Y-%m-%d %H:%M:%S')
                                st.markdown(f"  {i}. {formatted_time}")
                        else:
                            st.markdown("*No sampling times available*")
            
            # Display as clickable cards
            cols = st.columns(3)
            for idx, (_, row) in enumerate(hour_data.iterrows()):
                with cols[idx]:
                    # Check if this tweet is selected
                    is_selected = st.session_state.selected_tweet == row['id']
                    border_color = "#ff6b6b" if is_selected else "#1f77b4"
                    bg_color = "#ffe0e0" if is_selected else "#f0f2f6"
                    
                    # Create clickable card
                    with st.container():
                        tweet_url = build_twitter_url('tweet', tweet_id=int(row['id']))
                        profile_url = build_twitter_url('profile', username=row['author_username'])
                        
                        st.markdown(f"""
                        <div style="background-color: {bg_color}; padding: 15px; border-radius: 10px; border-left: 4px solid {border_color}; cursor: pointer;">
                            <h4 style="margin: 0;">{'⭐' if is_selected else '🥇'} Rank {int(row['rank'])}</h4>
                            <p style="margin: 5px 0;"><strong>@{row['author_username']}</strong></p>
                            <p style="margin: 5px 0;">❤️ {int(row['likes']):,} likes</p>
                            <p style="margin: 5px 0;">💬 {int(row['replies']):,} replies</p>
                            <p style="margin: 5px 0;">🔄 {int(row['retweets']):,} retweets</p>
                            <p style="margin: 5px 0; font-size: 0.85em; color: #666;">ID: {int(row['id'])}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Add clickable URLs below the card
                        col_url1, col_url2 = st.columns(2)
                        with col_url1:
                            st.markdown(f"[🐦 View Tweet]({tweet_url})", unsafe_allow_html=True)
                        with col_url2:
                            st.markdown(f"[👤 View Profile]({profile_url})", unsafe_allow_html=True)
                        
                        # Button to select this tweet
                        if st.button("View Text", key=f"btn_{row['id']}"):
                            st.session_state.selected_tweet = row['id']
                            st.rerun()
            
            st.markdown("---")
        
        # Show full table at the bottom with tweet text preview
        st.subheader("📊 Full Data Table")
        display_df = df[['hour_display', 'rank', 'author_username', 'likes', 'replies', 'retweets', 'tweet_text', 'id']].copy()
        display_df.columns = ['Hour', 'Rank', 'Username', 'Likes', 'Replies', 'Retweets', 'Tweet Text', 'Tweet ID']
        
        # Display DataFrame with row selection
        selected_rows = st.dataframe(
            display_df, 
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Handle row selection
        if selected_rows.selection.rows:
            selected_index = selected_rows.selection.rows[0]
            selected_tweet_id = display_df.iloc[selected_index]['Tweet ID']
            st.session_state.selected_tweet = selected_tweet_id
            st.info(f"Selected Tweet ID: {selected_tweet_id}. Check the sidebar for details!")
        
        # Also show expandable tweet text if a tweet is selected
        if st.session_state.selected_tweet is not None:
            selected_row = df[df['id'] == st.session_state.selected_tweet].iloc[0]
            with st.expander("📝 Quick View - Tweet Text", expanded=False):
                st.markdown(f"""**@{selected_row['author_username']}** • {pd.to_datetime(selected_row['hour']).strftime('%Y-%m-%d %H:%M')} • ❤️ {int(selected_row['likes']):,} 💬 {int(selected_row['replies']):,} 🔄 {int(selected_row['retweets']):,}""")
                st.markdown("---")
                st.markdown(f"""<div style="font-size: 1.1em; line-height: 1.6; padding: 15px; background-color: #f8f9fa; border-radius: 5px;">
                {selected_row['tweet_text']}
                </div>""", unsafe_allow_html=True)

except Exception as e:
    st.error(f"An error occurred: {e}")
    st.exception(e)