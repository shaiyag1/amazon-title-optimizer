import streamlit as st
import pandas as pd
import json
import boto3
import base64
from typing import Dict, List
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


class InfluencerAnalyzer:
    def __init__(self, db_adapter):
        """
        db_adapter: Your existing DBAdapter instance
        """
        self.db = db_adapter
    
    def get_influencer_stats(self, username: str) -> Dict:
        """
        Get stats for a single influencer from tweets_metrics_history
        
        Note: SQL injection protection - username is trusted input from the database
        """
        # Sanitize username - remove any single quotes
        safe_username = username.replace("'", "''")
        
        sql = f"""
        SELECT 
            MIN(author_id) as author_id,
            COUNT(*) as sample_count,
            MAX(like_count) as max_likes,
            MAX(impression_count) as max_views,
            MAX(retweet_count) as max_retweets,
            MAX(x_fetched_at) as last_sampled
        FROM twitter.tweets_metrics_history
        WHERE author_username = '{safe_username}'
        """
        
        result = self.db.query(sql)
        
        if result and len(result) > 0:
            return {
                'author_id': result[0].get('author_id', 'N/A'),
                'username': username,
                'sample_count': result[0].get('sample_count', 0),
                'max_likes': result[0].get('max_likes', 0),
                'max_views': result[0].get('max_views', 0),
                'max_retweets': result[0].get('max_retweets', 0),
                'last_sampled': result[0].get('last_sampled', 'N/A')
            }
        else:
            return {
                'author_id': 'N/A',
                'username': username,
                'sample_count': 0,
                'max_likes': 0,
                'max_views': 0,
                'max_retweets': 0,
                'last_sampled': 'Never'
            }
    
    def analyze_multiple_influencers(self, usernames: List[str]) -> pd.DataFrame:
        """
        Analyze multiple influencers and return as DataFrame
        """
        results = []
        for username in usernames:
            stats = self.get_influencer_stats(username)
            results.append(stats)
        
        return pd.DataFrame(results)
    
    def get_top_tweets_for_users(self, usernames: List[str], days_back: int = 5, top_n: int = 5) -> pd.DataFrame:
        """
        Get top N tweets for each user from the last X days
        Returns aggregated metrics per user + recent sampling stats
        """
        if not usernames:
            return pd.DataFrame()
        
        # Sanitize usernames and remove @ if present
        sanitized_usernames = []
        for username in usernames:
            username = username.strip()
            if username.startswith('@'):
                username = username[1:]
            sanitized_usernames.append(username.replace("'", "''"))  # SQL injection protection
        
        usernames_str = "', '".join(sanitized_usernames)
        
        sql = f"""
        WITH user_top_tweets AS (
            SELECT 
                tmh.author_username,
                tmh.id as tweet_id,
                tmh.author_id,
                MAX(tmh.like_count) as max_likes,
                MAX(tmh.reply_count) as max_replies,
                MAX(tmh.retweet_count) as max_retweets,
                MAX(tmh.impression_count) as max_views,
                MAX(t.x_fetched_at) as last_sampled,
                t.created_at as tweet_created_at,
                ROW_NUMBER() OVER (
                    PARTITION BY tmh.author_username 
                    ORDER BY MAX(tmh.impression_count) DESC
                ) as tweet_rank
            FROM twitter.tweets_metrics_history tmh
            LEFT JOIN twitter.tweets t ON tmh.id = t.id
            WHERE tmh.author_username IN ('{usernames_str}')
              AND t.created_at >= NOW() - INTERVAL '{days_back} days'
            GROUP BY tmh.author_username, tmh.id, tmh.author_id, t.created_at
        ),
        top_tweets AS (
            SELECT *
            FROM user_top_tweets
            WHERE tweet_rank <= {top_n}
        ),
        recent_sampling AS (
            SELECT 
                tmh.author_username,
                COUNT(DISTINCT tmh.id) as recent_sample_count,
                MAX(tmh.x_fetched_at) as last_sample_time
            FROM twitter.tweets_metrics_history tmh
            WHERE tmh.author_username IN ('{usernames_str}')
              AND tmh.x_fetched_at >= NOW() - INTERVAL '6 hours'
            GROUP BY tmh.author_username
        )
        SELECT 
            tt.author_username,
            tt.author_id,
            COUNT(*) as tweet_count,
            SUM(tt.max_views) as total_views,
            SUM(tt.max_likes) as total_likes,
            SUM(tt.max_retweets) as total_retweets,
            SUM(tt.max_replies) as total_replies,
            MAX(tt.max_views) as max_single_views,
            MAX(tt.max_likes) as max_single_likes,
            MAX(tt.max_retweets) as max_single_retweets,
            MAX(tt.max_replies) as max_single_replies,
            COALESCE(rs.recent_sample_count, 0) as recent_sample_count,
            rs.last_sample_time as last_sample_time
        FROM top_tweets tt
        LEFT JOIN recent_sampling rs ON tt.author_username = rs.author_username
        GROUP BY tt.author_username, tt.author_id, rs.recent_sample_count, rs.last_sample_time
        ORDER BY SUM(tt.max_views) DESC;
        """
        
        result = self.db.query(sql)
        
        if result and len(result) > 0:
            return pd.DataFrame(result)
        else:
            return pd.DataFrame()
    
    def get_trending_tweets(self, hours_back: int = 1, limit: int = 100) -> pd.DataFrame:
        """
        Get tweets that were sampled in the last N hours and calculate delta metrics per minute
        
        Returns tweets sorted by the time between last two samples with delta metrics
        Strategy: Find the most recent sample, then look back 2 hours from there for previous samples
        """
        sql = f"""
        WITH system_time AS (
            -- Find the most recent sample time as our system time reference
            SELECT MAX(x_fetched_at) as latest_system_sample
            FROM twitter.tweets_metrics_history
        ),
        recent_tweets AS (
            -- Get tweets that had their LATEST sample in the last N hours from system time
            SELECT 
                tmh.id as tweet_id
            FROM twitter.tweets_metrics_history tmh
            CROSS JOIN system_time st
            WHERE tmh.x_fetched_at >= st.latest_system_sample - INTERVAL '{hours_back} hours'
            GROUP BY tmh.id
        ),
        last_two_samples AS (
            -- For these tweets, get their last 2 samples from a 2-hour window
            SELECT 
                tmh.id as tweet_id,
                tmh.author_id,
                tmh.author_username,
                tmh.like_count,
                tmh.reply_count,
                tmh.retweet_count,
                tmh.impression_count as views,
                tmh.x_fetched_at,
                ROW_NUMBER() OVER (
                    PARTITION BY tmh.id 
                    ORDER BY tmh.x_fetched_at DESC
                ) as sample_rank
            FROM twitter.tweets_metrics_history tmh
            CROSS JOIN system_time st
            INNER JOIN recent_tweets rt ON tmh.id = rt.tweet_id
            WHERE tmh.x_fetched_at >= st.latest_system_sample - INTERVAL '2 hours'
        ),
        tweet_stats AS (
            SELECT 
                tweet_id,
                author_id,
                author_username,
                MAX(CASE WHEN sample_rank = 1 THEN like_count END) as latest_likes,
                MAX(CASE WHEN sample_rank = 2 THEN like_count END) as previous_likes,
                MAX(CASE WHEN sample_rank = 1 THEN reply_count END) as latest_replies,
                MAX(CASE WHEN sample_rank = 2 THEN reply_count END) as previous_replies,
                MAX(CASE WHEN sample_rank = 1 THEN retweet_count END) as latest_retweets,
                MAX(CASE WHEN sample_rank = 2 THEN retweet_count END) as previous_retweets,
                MAX(CASE WHEN sample_rank = 1 THEN views END) as latest_views,
                MAX(CASE WHEN sample_rank = 2 THEN views END) as previous_views,
                MAX(CASE WHEN sample_rank = 1 THEN x_fetched_at END) as latest_sample,
                MAX(CASE WHEN sample_rank = 2 THEN x_fetched_at END) as previous_sample
            FROM last_two_samples
            WHERE sample_rank <= 2
            GROUP BY tweet_id, author_id, author_username
            HAVING COUNT(*) = 2  -- Only tweets that have exactly 2 samples
        )
        SELECT 
            ts.tweet_id,
            ts.author_id,
            ts.author_username,
            ts.latest_likes,
            ts.previous_likes,
            ts.latest_replies,
            ts.previous_replies,
            ts.latest_retweets,
            ts.previous_retweets,
            ts.latest_views,
            ts.previous_views,
            ts.latest_sample,
            ts.previous_sample,
            EXTRACT(EPOCH FROM (ts.latest_sample - ts.previous_sample)) / 60.0 as delta_minutes,
            t.text as tweet_text,
            t.created_at as tweet_created_at
        FROM tweet_stats ts
        LEFT JOIN twitter.tweets t ON ts.tweet_id = t.id
        WHERE EXTRACT(EPOCH FROM (ts.latest_sample - ts.previous_sample)) / 60.0 > 0
          AND t.created_at >= NOW() - INTERVAL '7 days'
        LIMIT {limit};
        """
        
        result = self.db.query(sql)
        
        if result and len(result) > 0:
            # Convert to DataFrame
            df = pd.DataFrame(result)
            
            # Convert numeric columns to proper types
            numeric_cols = [
                'latest_likes', 'previous_likes', 'latest_replies', 'previous_replies',
                'latest_retweets', 'previous_retweets', 'latest_views', 'previous_views',
                'delta_minutes'
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Calculate deltas per minute
            df['delta_likes'] = (df['latest_likes'] - df['previous_likes']) / df['delta_minutes']
            df['delta_replies'] = (df['latest_replies'] - df['previous_replies']) / df['delta_minutes']
            df['delta_retweets'] = (df['latest_retweets'] - df['previous_retweets']) / df['delta_minutes']
            df['delta_views'] = (df['latest_views'] - df['previous_views']) / df['delta_minutes']
            
            # Fill NaN with 0 and round to 2 decimals
            df[['delta_likes', 'delta_replies', 'delta_retweets', 'delta_views']] = \
                df[['delta_likes', 'delta_replies', 'delta_retweets', 'delta_views']].fillna(0).round(2)
            
            return df
        else:
            return pd.DataFrame()
    
    def get_original_tweets(self, hours_back: int = 3, limit: int = 100) -> pd.DataFrame:
        """
        Get original tweets (not replies, not retweets) from the last N hours
        Original tweets are where conversation_id = id
        System time is the time of the last tweet that was fetched
        Sorted by most views, limited to top N
        """
        sql = f"""
        WITH system_time AS (
            -- Find the most recent fetch time as our system time reference
            SELECT MAX(x_fetched_at) as latest_fetch_time
            FROM twitter.tweets_metrics_history
        ),
        filtered_tweets AS (
            -- First, filter tweets efficiently by time and original tweet criteria
            SELECT 
                t.id as tweet_id,
                t.author_id,
                t.author_username,
                t.text as tweet_text,
                t.created_at
            FROM twitter.tweets t
            CROSS JOIN system_time st
            WHERE t.conversation_id = t.id  -- Original tweets only (not replies)
              AND (t.is_retweet IS FALSE OR t.is_retweet IS NULL)  -- Not retweets
              AND t.created_at >= st.latest_fetch_time - INTERVAL '{hours_back} hours'
              AND t.created_at <= st.latest_fetch_time
        ),
        tweet_metrics AS (
            -- Then, get the latest metrics only for filtered tweets
            SELECT 
                tmh.id as tweet_id,
                MAX(tmh.impression_count) as max_views,
                MAX(tmh.like_count) as max_likes,
                MAX(tmh.reply_count) as max_replies,
                MAX(tmh.retweet_count) as max_retweets,
                MAX(tmh.x_fetched_at) as last_sampled
            FROM twitter.tweets_metrics_history tmh
            INNER JOIN filtered_tweets ft ON tmh.id = ft.tweet_id
            GROUP BY tmh.id
        )
        SELECT 
            ft.tweet_id,
            ft.author_id,
            ft.author_username,
            ft.tweet_text,
            ft.created_at,
            COALESCE(tm.max_views, 0) as max_views,
            COALESCE(tm.max_likes, 0) as max_likes,
            COALESCE(tm.max_replies, 0) as max_replies,
            COALESCE(tm.max_retweets, 0) as max_retweets,
            tm.last_sampled
        FROM filtered_tweets ft
        LEFT JOIN tweet_metrics tm ON ft.tweet_id = tm.tweet_id
        ORDER BY COALESCE(tm.max_views, 0) DESC
        LIMIT {limit};
        """
        
        result = self.db.query(sql)
        
        if result and len(result) > 0:
            return pd.DataFrame(result)
        else:
            return pd.DataFrame()
    
    def get_all_tweets(self, hours_back: int = 3, limit: int = 100, political_leaning: str = None) -> pd.DataFrame:
        """
        Get all tweets from the last N hours with classification and original tweet URLs
        Classification: retweet, SelfReply, media (if media_urls is not empty), or empty
        
        Args:
            hours_back: Number of hours to look back
            limit: Maximum number of tweets to return
            political_leaning: Filter by political leaning ('left', 'center_left', 'center_right', 'right', or None/'all' for all)
        """
        # Build political leaning filter
        political_filter = ""
        if political_leaning and political_leaning.lower() != 'all':
            # Sanitize political_leaning to prevent SQL injection
            safe_leaning = political_leaning.replace("'", "''")
            political_filter = f"AND ue.political_leaning = '{safe_leaning}'"
        
        sql = f"""
        WITH system_time AS (
            SELECT MAX(x_fetched_at) as latest_fetch_time
            FROM twitter.tweets_metrics_history
        ),
        filtered_tweets AS (
            SELECT 
                t.id as tweet_id,
                t.author_id,
                t.author_username,
                t.text as tweet_text,
                t.created_at,
                t.is_retweet,
                t."calc_isSelfReply",
                t.media_urls,
                t.retweeted_tweet_id,
                t.conversation_id,
                t.reply_to_tweet_id,
                t.reply_to_user_id,
                t.urls,
                t.quoted_tweet_id,
                COALESCE(ue.political_leaning, 'Unknown') as political_leaning
            FROM twitter.tweets t
            LEFT JOIN twitter.twitter_users_enriched ue ON t.author_id::text = ue.id
            CROSS JOIN system_time st
            WHERE t.created_at >= st.latest_fetch_time - INTERVAL '{hours_back} hours'
              AND t.created_at <= st.latest_fetch_time
              {political_filter}
        ),
        tweet_metrics AS (
            SELECT 
                tmh.id as tweet_id,
                MAX(tmh.impression_count) as max_views,
                MAX(tmh.like_count) as max_likes,
                MAX(tmh.reply_count) as max_replies,
                MAX(tmh.retweet_count) as max_retweets,
                MAX(tmh.x_fetched_at) as last_sampled
            FROM twitter.tweets_metrics_history tmh
            INNER JOIN filtered_tweets ft ON tmh.id = ft.tweet_id
            GROUP BY tmh.id
        )
        SELECT 
            ft.tweet_id,
            ft.author_id,
            ft.author_username,
            ft.tweet_text,
            ft.created_at,
            COALESCE(tm.max_views, 0) as max_views,
            COALESCE(tm.max_likes, 0) as max_likes,
            COALESCE(tm.max_replies, 0) as max_replies,
            COALESCE(tm.max_retweets, 0) as max_retweets,
            tm.last_sampled,
            ft.is_retweet,
            ft."calc_isSelfReply" as calc_isSelfReply,
            ft.media_urls,
            ft.retweeted_tweet_id,
            ft.conversation_id,
            ft.reply_to_tweet_id,
            ft.reply_to_user_id,
            ft.urls,
            ft.quoted_tweet_id,
            ft.political_leaning
        FROM filtered_tweets ft
        LEFT JOIN tweet_metrics tm ON ft.tweet_id = tm.tweet_id
        ORDER BY COALESCE(tm.max_views, 0) DESC
        LIMIT {limit};
        """
        
        result = self.db.query(sql)
        
        if result and len(result) > 0:
            df = pd.DataFrame(result)
            
            # Add classification column
            def classify_tweet(row):
                classifications = []
                
                # Check if retweet (highest priority)
                if row.get('is_retweet') == True or pd.notna(row.get('retweeted_tweet_id')):
                    return 'retweet'
                
                # Check if self reply
                if row.get('calc_isSelfReply') == 'True' or str(row.get('calc_isSelfReply')).lower() == 'true':
                    return 'SelfReply'
                
                # Check if reply_to_user_id is not null - add "Reply"
                if pd.notna(row.get('reply_to_user_id')):
                    classifications.append('Reply')
                
                # Check if media (media_urls is not an empty list)
                if row.get('media_urls') is not None:
                    try:
                        # Parse JSON if it's a string
                        media = row.get('media_urls')
                        if isinstance(media, str):
                            import json
                            media = json.loads(media)
                        if isinstance(media, list) and len(media) > 0:
                            classifications.append('media')
                    except:
                        pass
                
                # Check if urls is not null - add "url"
                if row.get('urls') is not None:
                    try:
                        # Parse JSON if it's a string
                        urls = row.get('urls')
                        if isinstance(urls, str):
                            import json
                            urls = json.loads(urls)
                        # Check if it's a list/array with content or just not null
                        if isinstance(urls, list):
                            if len(urls) > 0:
                                classifications.append('url')
                        else:
                            # If it's not null but not a list, still add url
                            classifications.append('url')
                    except:
                        # If parsing fails but field is not null, still add url
                        classifications.append('url')
                
                # Check if quoted_tweet_id is not null - add "Quoted"
                if pd.notna(row.get('quoted_tweet_id')):
                    classifications.append('Quoted')
                
                # Check if tweet_text is less than 70 characters - add "Tweet"
                tweet_text = row.get('tweet_text')
                if tweet_text is not None and isinstance(tweet_text, str):
                    if len(tweet_text) < 70:
                        classifications.append('Tweet')
                
                # Return joined classifications or empty string
                return ', '.join(classifications) if classifications else ''
            
            df['classification'] = df.apply(classify_tweet, axis=1)
            
            # Add original tweet ID and URL
            def get_original_tweet_id(row):
                # For retweets, use retweeted_tweet_id
                if row.get('is_retweet') == True or pd.notna(row.get('retweeted_tweet_id')):
                    return row.get('retweeted_tweet_id')
                # For replies, use conversation_id (the original tweet in the thread)
                elif row.get('reply_to_tweet_id') is not None:
                    return row.get('conversation_id')
                # For original tweets, use their own ID
                else:
                    return row.get('tweet_id')
            
            df['original_tweet_id'] = df.apply(get_original_tweet_id, axis=1)
            
            # Generate URLs
            def generate_url(row):
                tweet_id = row.get('original_tweet_id')
                if pd.notna(tweet_id):
                    try:
                        return build_twitter_url('tweet', tweet_id=int(tweet_id))
                    except (ValueError, TypeError):
                        return ''
                return ''
            
            df['original_tweet_url'] = df.apply(generate_url, axis=1)
            
            return df
        else:
            return pd.DataFrame()
    
    def get_political_leaning_classification(self) -> pd.DataFrame:
        """
        Get classification of users by political_leaning
        Gets all unique author_id from tweets_metrics_history and joins with twitter_users_enriched
        where author_id = id, then groups by political_leaning
        """
        sql = """
        WITH unique_users AS (
            SELECT DISTINCT author_id
            FROM twitter.tweets_metrics_history
        )
        SELECT 
            COALESCE(ue.political_leaning, 'Unknown') as political_leaning,
            COUNT(*) as user_count
        FROM unique_users uu
        LEFT JOIN twitter.twitter_users_enriched ue ON uu.author_id::text = ue.id
        GROUP BY ue.political_leaning
        ORDER BY user_count DESC;
        """
        
        result = self.db.query(sql)
        
        if result and len(result) > 0:
            return pd.DataFrame(result)
        else:
            return pd.DataFrame()
    
    def get_tweets_by_political_leaning(self, hours_back: int = 12) -> pd.DataFrame:
        """
        Get count of tweets created in the last N hours, grouped by political_leaning
        Groups tweets by political_leaning category from twitter_users_enriched
        
        Args:
            hours_back: Number of hours to look back (default 12)
        
        Returns DataFrame with political_leaning and tweet_count
        """
        sql = f"""
        WITH system_time AS (
            SELECT MAX(x_fetched_at) as latest_fetch_time
            FROM twitter.tweets_metrics_history
        ),
        recent_tweets AS (
            SELECT 
                t.id as tweet_id,
                t.author_id
            FROM twitter.tweets t
            CROSS JOIN system_time st
            WHERE t.created_at >= st.latest_fetch_time - INTERVAL '{hours_back} hours'
              AND t.created_at <= st.latest_fetch_time
        )
        SELECT 
            COALESCE(ue.political_leaning, 'Unknown') as political_leaning,
            COUNT(*) as tweet_count
        FROM recent_tweets rt
        LEFT JOIN twitter.twitter_users_enriched ue ON rt.author_id::text = ue.id
        GROUP BY ue.political_leaning
        ORDER BY tweet_count DESC;
        """
        
        result = self.db.query(sql)
        
        if result and len(result) > 0:
            df = pd.DataFrame(result)
            # Convert tweet_count to numeric
            if 'tweet_count' in df.columns:
                df['tweet_count'] = pd.to_numeric(df['tweet_count'], errors='coerce')
            return df
        else:
            return pd.DataFrame()
    
    def get_influencers_for_correlation(self, hours_back: int = 3, min_views: int = 1000, political_leaning: str = None) -> pd.DataFrame:
        """
        Get influencers from top-performing tweets for cross-correlation analysis
        Gets tweets with high views, filters by political leaning, then identifies unique influencers
        
        Args:
            hours_back: Number of hours to look back
            min_views: Minimum views threshold for "super tweets" (default 1000)
            political_leaning: Filter by political leaning (None for all)
        
        Returns DataFrame with influencer metrics aggregated from their tweets
        """
        # Build political leaning filter
        political_filter = ""
        if political_leaning and political_leaning.lower() != 'all':
            safe_leaning = political_leaning.replace("'", "''")
            political_filter = f"AND ue.political_leaning = '{safe_leaning}'"
        
        sql = f"""
        WITH system_time AS (
            SELECT MAX(x_fetched_at) as latest_fetch_time
            FROM twitter.tweets_metrics_history
        ),
        super_tweets AS (
            SELECT 
                t.id as tweet_id,
                t.author_id,
                t.author_username,
                t.created_at
            FROM twitter.tweets t
            LEFT JOIN twitter.twitter_users_enriched ue ON t.author_id::text = ue.id
            CROSS JOIN system_time st
            WHERE t.created_at >= st.latest_fetch_time - INTERVAL '{hours_back} hours'
              AND t.created_at <= st.latest_fetch_time
              {political_filter}
        ),
        tweet_metrics AS (
            SELECT 
                tmh.id as tweet_id,
                tmh.author_id,
                tmh.author_username,
                MAX(tmh.impression_count) as max_views,
                MAX(tmh.like_count) as max_likes,
                MAX(tmh.reply_count) as max_replies,
                MAX(tmh.retweet_count) as max_retweets
            FROM twitter.tweets_metrics_history tmh
            INNER JOIN super_tweets st ON tmh.id = st.tweet_id
            GROUP BY tmh.id, tmh.author_id, tmh.author_username
            HAVING MAX(tmh.impression_count) >= {min_views}
        ),
        influencer_aggregates AS (
            SELECT 
                author_id,
                author_username,
                COUNT(*) as tweet_count,
                AVG(max_views) as avg_views,
                AVG(max_likes) as avg_likes,
                AVG(max_replies) as avg_replies,
                AVG(max_retweets) as avg_retweets,
                MAX(max_views) as max_views,
                MAX(max_likes) as max_likes,
                SUM(max_views) as total_views,
                SUM(max_likes) as total_likes
            FROM tweet_metrics
            GROUP BY author_id, author_username
        )
        SELECT 
            ia.*,
            COALESCE(ue.political_leaning, 'Unknown') as political_leaning
        FROM influencer_aggregates ia
        LEFT JOIN twitter.twitter_users_enriched ue ON ia.author_id::text = ue.id
        ORDER BY ia.total_views DESC;
        """
        
        result = self.db.query(sql)
        
        if result and len(result) > 0:
            df = pd.DataFrame(result)
            # Convert numeric columns
            numeric_cols = ['tweet_count', 'avg_views', 'avg_likes', 'avg_replies', 'avg_retweets', 
                          'max_views', 'max_likes', 'total_views', 'total_likes']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        else:
            return pd.DataFrame()
    
    def calculate_influencer_correlation(self, influencers_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate cross-correlation matrix between influencers based on their metrics
        Uses average metrics (views, likes, replies, retweets) to calculate correlation
        """
        if influencers_df.empty or len(influencers_df) < 2:
            return pd.DataFrame()
        
        # Select relevant metrics for correlation
        metrics_cols = ['avg_views', 'avg_likes', 'avg_replies', 'avg_retweets']
        available_cols = [col for col in metrics_cols if col in influencers_df.columns]
        
        if not available_cols:
            return pd.DataFrame()
        
        # Create a matrix where each row is an influencer and columns are metrics
        # Then calculate correlation between influencers
        metric_matrix = influencers_df[available_cols].fillna(0)
        
        # Calculate correlation matrix (correlation between influencers based on their metric profiles)
        correlation_matrix = metric_matrix.T.corr()
        
        # Add influencer identifiers
        correlation_matrix.index = influencers_df['author_username'].fillna('Unknown').tolist()
        correlation_matrix.columns = influencers_df['author_username'].fillna('Unknown').tolist()
        
        return correlation_matrix
    
    def get_hot_tweets(self, hours_back: int = 3, limit: int = 100) -> pd.DataFrame:
        """
        Get the most liked tweets created in the last K hours
        Finds tweets created within the last K hours and sorts them by likes (descending)
        
        Args:
            hours_back: Number of hours to look back (default 3)
            limit: Maximum number of tweets to return (default 100)
        
        Returns DataFrame with tweet details sorted by likes
        """
        sql = f"""
        WITH system_time AS (
            SELECT MAX(x_fetched_at) as latest_fetch_time
            FROM twitter.tweets_metrics_history
        ),
        recent_tweets AS (
            SELECT 
                t.id as tweet_id,
                t.author_id,
                t.author_username,
                t.text as tweet_text,
                t.created_at
            FROM twitter.tweets t
            CROSS JOIN system_time st
            WHERE t.created_at >= st.latest_fetch_time - INTERVAL '{hours_back} hours'
              AND t.created_at <= st.latest_fetch_time
        ),
        tweet_metrics AS (
            SELECT 
                tmh.id as tweet_id,
                MAX(tmh.like_count) as max_likes,
                MAX(tmh.impression_count) as max_views,
                MAX(tmh.reply_count) as max_replies,
                MAX(tmh.retweet_count) as max_retweets,
                MAX(tmh.x_fetched_at) as last_sampled
            FROM twitter.tweets_metrics_history tmh
            INNER JOIN recent_tweets rt ON tmh.id = rt.tweet_id
            GROUP BY tmh.id
        )
        SELECT 
            rt.tweet_id,
            rt.author_id,
            rt.author_username,
            rt.tweet_text,
            rt.created_at,
            COALESCE(tm.max_likes, 0) as max_likes,
            COALESCE(tm.max_views, 0) as max_views,
            COALESCE(tm.max_replies, 0) as max_replies,
            COALESCE(tm.max_retweets, 0) as max_retweets,
            tm.last_sampled
        FROM recent_tweets rt
        LEFT JOIN tweet_metrics tm ON rt.tweet_id = tm.tweet_id
        ORDER BY COALESCE(tm.max_likes, 0) DESC
        LIMIT {limit};
        """
        
        result = self.db.query(sql)
        
        if result and len(result) > 0:
            df = pd.DataFrame(result)
            # Convert numeric columns
            numeric_cols = ['max_likes', 'max_views', 'max_replies', 'max_retweets']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        else:
            return pd.DataFrame()
    
    def get_author_ids_by_cluster(self, political_leaning: str) -> List[str]:
        """
        Get all author_ids that belong to the selected political leaning cluster
        """
        if political_leaning is None or political_leaning.lower() == 'all':
            return []
        
        # Sanitize political_leaning
        safe_leaning = political_leaning.replace("'", "''")
        
        sql = f"""
        SELECT DISTINCT uu.author_id::text as author_id
        FROM (
            SELECT DISTINCT author_id
            FROM twitter.tweets_metrics_history
        ) uu
        LEFT JOIN twitter.twitter_users_enriched ue ON uu.author_id::text = ue.id
        WHERE COALESCE(ue.political_leaning, 'Unknown') = '{safe_leaning}';
        """
        
        result = self.db.query(sql)
        
        if result and len(result) > 0:
            author_ids = [str(row.get('author_id', '')) for row in result if row.get('author_id')]
            return author_ids
        else:
            return []
    
    def get_tweets_by_cluster_batched(self, hours_back: int = 3, political_leaning: str = None, limit: int = 100, sort_by: str = 'views', progress_callback=None) -> pd.DataFrame:
        """
        Get tweets by cluster using batched processing per author_id
        More efficient for large clusters - processes each author_id separately then combines
        
        Args:
            hours_back: Number of hours to look back
            political_leaning: Filter by political leaning (None/'all' for all)
            limit: Maximum number of tweets to return
            sort_by: Sort by 'views' or 'likes' (default 'views')
            progress_callback: Optional callback function(processed, total, message) for progress updates
        
        Returns DataFrame with all classification fields, sorted by popularity
        """
        # If no filter, use the regular method
        if political_leaning is None or political_leaning.lower() == 'all':
            return self.get_all_tweets(hours_back=hours_back, limit=limit, political_leaning=None)
        
        # Get all author_ids for this cluster
        author_ids = self.get_author_ids_by_cluster(political_leaning)
        
        if not author_ids:
            return pd.DataFrame()
        
        # Process in smaller batches of 10 author_ids at a time to avoid timeouts
        batch_size = 10
        all_tweets = []
        total_batches = (len(author_ids) + batch_size - 1) // batch_size
        
        for batch_idx in range(0, len(author_ids), batch_size):
            batch = author_ids[batch_idx:batch_idx + batch_size]
            author_ids_str = ', '.join([f"'{aid}'" for aid in batch])
            processed_count = batch_idx + len(batch)
            
            # Progress update every 10 authors
            if progress_callback:
                progress_callback(processed_count, len(author_ids), f"Processing batch {batch_idx // batch_size + 1}/{total_batches} ({len(batch)} authors)")
            
            try:
                sql = f"""
                WITH system_time AS (
                    SELECT MAX(x_fetched_at) as latest_fetch_time
                    FROM twitter.tweets_metrics_history
                ),
                filtered_tweets AS (
                    SELECT 
                        t.id as tweet_id,
                        t.author_id,
                        t.author_username,
                        t.text as tweet_text,
                        t.created_at,
                        t.is_retweet,
                        t."calc_isSelfReply",
                        t.media_urls,
                        t.retweeted_tweet_id,
                        t.conversation_id,
                        t.reply_to_tweet_id,
                        t.reply_to_user_id,
                        t.urls,
                        t.quoted_tweet_id
                    FROM twitter.tweets t
                    CROSS JOIN system_time st
                    WHERE t.author_id::text IN ({author_ids_str})
                      AND t.created_at >= st.latest_fetch_time - INTERVAL '{hours_back} hours'
                      AND t.created_at <= st.latest_fetch_time
                    LIMIT 1000
                ),
                tweet_metrics AS (
                    SELECT 
                        tmh.id as tweet_id,
                        MAX(tmh.impression_count) as max_views,
                        MAX(tmh.like_count) as max_likes,
                        MAX(tmh.reply_count) as max_replies,
                        MAX(tmh.retweet_count) as max_retweets,
                        MAX(tmh.x_fetched_at) as last_sampled
                    FROM twitter.tweets_metrics_history tmh
                    INNER JOIN filtered_tweets ft ON tmh.id = ft.tweet_id
                    GROUP BY tmh.id
                )
                SELECT 
                    ft.tweet_id,
                    ft.author_id,
                    ft.author_username,
                    ft.tweet_text,
                    ft.created_at,
                    COALESCE(tm.max_views, 0) as max_views,
                    COALESCE(tm.max_likes, 0) as max_likes,
                    COALESCE(tm.max_replies, 0) as max_replies,
                    COALESCE(tm.max_retweets, 0) as max_retweets,
                    tm.last_sampled,
                    ft.is_retweet,
                    ft."calc_isSelfReply" as calc_isSelfReply,
                    ft.media_urls,
                    ft.retweeted_tweet_id,
                    ft.conversation_id,
                    ft.reply_to_tweet_id,
                    ft.reply_to_user_id,
                    ft.urls,
                    ft.quoted_tweet_id
                FROM filtered_tweets ft
                LEFT JOIN tweet_metrics tm ON ft.tweet_id = tm.tweet_id
                ORDER BY COALESCE(tm.max_views, 0) DESC
                LIMIT 500;
                """
                
                result = self.db.query(sql)
                if result and len(result) > 0:
                    all_tweets.extend(result)
            except Exception as e:
                # Log error but continue with next batch
                if progress_callback:
                    progress_callback(processed_count, len(author_ids), f"⚠️ Error in batch {batch_idx // batch_size + 1}: {str(e)[:50]}...")
                continue  # Skip this batch and continue
        
        if not all_tweets:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(all_tweets)
        
        # Convert numeric columns
        numeric_cols = ['max_views', 'max_likes', 'max_replies', 'max_retweets']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Add classification column (same logic as get_all_tweets)
        def classify_tweet(row):
            classifications = []
            
            # Check if retweet (highest priority)
            if row.get('is_retweet') == True or pd.notna(row.get('retweeted_tweet_id')):
                return 'retweet'
            
            # Check if self reply
            if row.get('calc_isSelfReply') == 'True' or str(row.get('calc_isSelfReply')).lower() == 'true':
                return 'SelfReply'
            
            # Check if reply_to_user_id is not null - add "Reply"
            if pd.notna(row.get('reply_to_user_id')):
                classifications.append('Reply')
            
            # Check if media (media_urls is not an empty list)
            if row.get('media_urls') is not None:
                try:
                    media = row.get('media_urls')
                    if isinstance(media, str):
                        import json
                        media = json.loads(media)
                    if isinstance(media, list) and len(media) > 0:
                        classifications.append('media')
                except:
                    pass
            
            # Check if urls is not null - add "url"
            if row.get('urls') is not None:
                try:
                    urls = row.get('urls')
                    if isinstance(urls, str):
                        import json
                        urls = json.loads(urls)
                    if isinstance(urls, list):
                        if len(urls) > 0:
                            classifications.append('url')
                    else:
                        classifications.append('url')
                except:
                    classifications.append('url')
            
            # Check if quoted_tweet_id is not null - add "Quoted"
            if pd.notna(row.get('quoted_tweet_id')):
                classifications.append('Quoted')
            
            # Check if tweet_text is less than 70 characters - add "Tweet"
            tweet_text = row.get('tweet_text')
            if tweet_text is not None and isinstance(tweet_text, str):
                if len(tweet_text) < 70:
                    classifications.append('Tweet')
            
            # Return joined classifications or empty string
            return ', '.join(classifications) if classifications else ''
        
        df['classification'] = df.apply(classify_tweet, axis=1)
        
        # Add original tweet ID and URL
        def get_original_tweet_id(row):
            # For retweets, use retweeted_tweet_id
            if row.get('is_retweet') == True or pd.notna(row.get('retweeted_tweet_id')):
                return row.get('retweeted_tweet_id')
            # For replies, use conversation_id
            elif row.get('reply_to_tweet_id') is not None:
                return row.get('conversation_id')
            # For original tweets, use their own ID
            else:
                return row.get('tweet_id')
        
        df['original_tweet_id'] = df.apply(get_original_tweet_id, axis=1)
        
        # Generate URLs
        def generate_url(row):
            tweet_id = row.get('original_tweet_id')
            if pd.notna(tweet_id):
                try:
                    return build_twitter_url('tweet', tweet_id=int(tweet_id))
                except (ValueError, TypeError):
                    return ''
            return ''
        
        df['original_tweet_url'] = df.apply(generate_url, axis=1)
        
        # Sort by popularity (views or likes)
        if sort_by == 'likes':
            df = df.sort_values('max_likes', ascending=False)
        else:
            df = df.sort_values('max_views', ascending=False)
        
        # Limit results
        df = df.head(limit).reset_index(drop=True)
        
        return df
    
    def get_first_hour_engagement(self, usernames: List[str], days_back: int = 10) -> pd.DataFrame:
        """
        Get first hour engagement metrics for tweets created by specified users in the last N days
        For each tweet, finds the first 3 samples within the first hour and calculates engagement
        
        Args:
            usernames: List of usernames to analyze
            days_back: Number of days to look back (default 10)
        
        Returns DataFrame with tweet details and first hour engagement metrics
        """
        if not usernames:
            return pd.DataFrame()
        
        # Sanitize usernames and remove @ if present
        sanitized_usernames = []
        for username in usernames:
            username = username.strip()
            if username.startswith('@'):
                username = username[1:]
            sanitized_usernames.append(username.replace("'", "''"))  # SQL injection protection
        
        usernames_str = "', '".join(sanitized_usernames)
        
        sql = f"""
        WITH user_tweets AS (
            -- Get tweets created by these users in the last N days
            SELECT 
                t.id as tweet_id,
                t.author_id,
                t.author_username,
                t.text as tweet_text,
                t.created_at
            FROM twitter.tweets t
            WHERE t.author_username IN ('{usernames_str}')
              AND t.created_at >= NOW() - INTERVAL '{days_back} days'
              AND t.created_at <= NOW()
        ),
        first_hour_samples AS (
            -- Get samples within the first hour (first 3 samples per tweet)
            SELECT 
                tmh.id as tweet_id,
                tmh.author_id,
                tmh.author_username,
                tmh.like_count,
                tmh.reply_count,
                tmh.retweet_count,
                tmh.impression_count as views,
                tmh.x_fetched_at,
                ut.created_at as tweet_created_at,
                ut.tweet_text,
                ROW_NUMBER() OVER (
                    PARTITION BY tmh.id 
                    ORDER BY tmh.x_fetched_at ASC
                ) as sample_rank
            FROM twitter.tweets_metrics_history tmh
            INNER JOIN user_tweets ut ON tmh.id = ut.tweet_id
            WHERE tmh.x_fetched_at >= ut.created_at
              AND tmh.x_fetched_at <= ut.created_at + INTERVAL '1 hour'
        ),
        first_three_samples AS (
            -- Get only the first 3 samples per tweet
            SELECT *
            FROM first_hour_samples
            WHERE sample_rank <= 3
        ),
        tweet_first_hour_stats AS (
            -- Aggregate metrics: first sample, last sample, and growth during first hour
            SELECT 
                tweet_id,
                author_id,
                author_username,
                tweet_text,
                tweet_created_at,
                COUNT(*) as sample_count,
                MIN(x_fetched_at) as first_sample_time,
                MAX(x_fetched_at) as last_sample_time,
                MAX(CASE WHEN sample_rank = 1 THEN like_count END) as first_likes,
                MAX(CASE WHEN sample_rank = 1 THEN views END) as first_views,
                MAX(CASE WHEN sample_rank = 1 THEN reply_count END) as first_replies,
                MAX(CASE WHEN sample_rank = 1 THEN retweet_count END) as first_retweets,
                MAX(like_count) as max_likes_first_hour,
                MAX(views) as max_views_first_hour,
                MAX(reply_count) as max_replies_first_hour,
                MAX(retweet_count) as max_retweets_first_hour,
                MAX(like_count) - COALESCE(MAX(CASE WHEN sample_rank = 1 THEN like_count END), 0) as likes_growth_first_hour,
                MAX(views) - COALESCE(MAX(CASE WHEN sample_rank = 1 THEN views END), 0) as views_growth_first_hour,
                MAX(reply_count) - COALESCE(MAX(CASE WHEN sample_rank = 1 THEN reply_count END), 0) as replies_growth_first_hour,
                MAX(retweet_count) - COALESCE(MAX(CASE WHEN sample_rank = 1 THEN retweet_count END), 0) as retweets_growth_first_hour
            FROM first_three_samples
            GROUP BY tweet_id, author_id, author_username, tweet_text, tweet_created_at
        ),
        current_tweet_metrics AS (
            -- Get the latest/current metrics for each tweet (not just first hour)
            SELECT 
                tmh.id as tweet_id,
                MAX(tmh.like_count) as total_likes,
                MAX(tmh.impression_count) as total_views,
                MAX(tmh.reply_count) as total_replies,
                MAX(tmh.retweet_count) as total_retweets
            FROM twitter.tweets_metrics_history tmh
            INNER JOIN user_tweets ut ON tmh.id = ut.tweet_id
            GROUP BY tmh.id
        )
        SELECT 
            tfhs.author_username,
            tfhs.author_id,
            tfhs.tweet_id,
            tfhs.tweet_text,
            tfhs.tweet_created_at,
            tfhs.sample_count,
            tfhs.first_sample_time,
            tfhs.last_sample_time,
            COALESCE(tfhs.first_likes, 0) as first_likes,
            COALESCE(tfhs.first_views, 0) as first_views,
            COALESCE(tfhs.first_replies, 0) as first_replies,
            COALESCE(tfhs.first_retweets, 0) as first_retweets,
            COALESCE(tfhs.max_likes_first_hour, 0) as max_likes_first_hour,
            COALESCE(tfhs.max_views_first_hour, 0) as max_views_first_hour,
            COALESCE(tfhs.max_replies_first_hour, 0) as max_replies_first_hour,
            COALESCE(tfhs.max_retweets_first_hour, 0) as max_retweets_first_hour,
            COALESCE(tfhs.likes_growth_first_hour, 0) as likes_growth_first_hour,
            COALESCE(tfhs.views_growth_first_hour, 0) as views_growth_first_hour,
            COALESCE(tfhs.replies_growth_first_hour, 0) as replies_growth_first_hour,
            COALESCE(tfhs.retweets_growth_first_hour, 0) as retweets_growth_first_hour,
            COALESCE(ctm.total_likes, 0) as total_likes,
            COALESCE(ctm.total_views, 0) as total_views
        FROM tweet_first_hour_stats tfhs
        LEFT JOIN current_tweet_metrics ctm ON tfhs.tweet_id = ctm.tweet_id
        ORDER BY tfhs.author_username, tfhs.tweet_created_at DESC;
        """
        
        result = self.db.query(sql)
        
        if result and len(result) > 0:
            df = pd.DataFrame(result)
            
            # Convert numeric columns
            numeric_cols = [
                'sample_count', 'first_likes', 'first_views', 'first_replies', 'first_retweets',
                'max_likes_first_hour', 'max_views_first_hour', 'max_replies_first_hour', 'max_retweets_first_hour',
                'likes_growth_first_hour', 'views_growth_first_hour', 'replies_growth_first_hour', 'retweets_growth_first_hour',
                'total_likes', 'total_views'
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            return df
        else:
            return pd.DataFrame()


# Streamlit App
st.set_page_config(page_title="Influencer Analysis", layout="wide")

st.title("📊 Influencer Analysis Dashboard")
st.markdown("---")

# Add refresh button at the top
if st.button("🔄 Refresh Data"):
    st.rerun()

st.markdown("---")

# Initialize database connection
try:
    # Initialize session state for DB connection if not exists
    if 'db_adapter' not in st.session_state:
        with st.spinner("Initializing database connection..."):
            db_secret_name = 'main-rds-cluster'
            sm = SecretsManager()
            st.session_state.db_adapter = DBAdapter(sm.get_secret(db_secret_name))
    
    # Initialize analyzer
    analyzer = InfluencerAnalyzer(st.session_state.db_adapter)
    
    # Initialize session state for tweet selection
    if 'selected_trending_tweet' not in st.session_state:
        st.session_state.selected_trending_tweet = None
    
    # Sidebar for trending tweet details
    with st.sidebar:
        # Time information at the top
        st.markdown("### ⏰ Time Information")
        current_time = datetime.now()
        st.markdown(f"**Current Time:** {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if 'trending_tweets' in st.session_state and not st.session_state.trending_tweets.empty:
            # Get the latest sample time from the database
            latest_sample_time = st.session_state.trending_tweets['latest_sample'].max()
            if pd.notna(latest_sample_time):
                st.markdown(f"**Latest Sample:** {pd.to_datetime(latest_sample_time).strftime('%Y-%m-%d %H:%M:%S')}")
                # Calculate time delta
                time_delta = current_time - pd.to_datetime(latest_sample_time)
                if time_delta.total_seconds() < 3600:  # Less than 1 hour
                    delta_minutes = time_delta.total_seconds() / 60
                    st.markdown(f"**Delta:** {delta_minutes:.1f} minutes ago")
                else:
                    delta_hours = time_delta.total_seconds() / 3600
                    st.markdown(f"**Delta:** {delta_hours:.1f} hours ago")
        
        st.markdown("---")
        
        st.header("📋 Trending Tweet Details")
        if 'trending_tweets' in st.session_state and st.session_state.selected_trending_tweet is not None:
            selected_row = st.session_state.trending_tweets.iloc[st.session_state.selected_trending_tweet]
            
            st.markdown("### Tweet Information")
            st.markdown(f"**@{selected_row['author_username']}**")
            st.markdown(f"**Author ID:** `{selected_row['author_id']}`")
            st.markdown(f"**Tweet ID:** `{int(selected_row['tweet_id'])}`")
            if 'tweet_created_at' in selected_row and pd.notna(selected_row['tweet_created_at']):
                created_at = pd.to_datetime(selected_row['tweet_created_at'])
                st.markdown(f"**Created:** {created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            st.markdown("---")
            st.markdown("### Tweet Text")
            st.markdown(f"""<div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 4px solid #1f77b4; word-wrap: break-word;">
            {selected_row['tweet_text']}
            </div>""", unsafe_allow_html=True)
            st.markdown("---")
            st.markdown("### Growth Metrics")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Δ Likes/min", f"{selected_row['delta_likes']:.2f}")
                st.metric("Δ Views/min", f"{selected_row['delta_views']:.2f}")
            with col2:
                st.metric("Δ Replies/min", f"{selected_row['delta_replies']:.2f}")
                st.metric("Δ Retweets/min", f"{selected_row['delta_retweets']:.2f}")
            st.markdown("---")
            st.markdown("### Latest Counts")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Likes", f"{int(selected_row['latest_likes']):,}")
                st.metric("Views", f"{int(selected_row['latest_views']):,}")
            with col2:
                st.metric("Replies", f"{int(selected_row['latest_replies']):,}")
                st.metric("Retweets", f"{int(selected_row['latest_retweets']):,}")
            st.markdown(f"**Time Delta:** {selected_row['delta_minutes']:.1f} minutes")
            if st.button("❌ Clear Selection"):
                st.session_state.selected_trending_tweet = None
                st.rerun()
        else:
            st.info("👆 Select a tweet from the trending table to view details")
    
    # Trending Tweets Section
    st.subheader("🔥 Trending Tweets - Last Hour")
    with st.expander("📊 View Trending Tweets by Growth Rate", expanded=False):
        col_time, col_limit = st.columns(2)
        with col_time:
            hours_back = st.selectbox("Hours to look back:", [1, 2, 6, 12, 24], index=0)
        with col_limit:
            limit = st.number_input("Max tweets to show:", min_value=10, max_value=500, value=100, step=10)
        
        sort_by = st.radio(
            "Sort by delta per minute:",
            options=['delta_views', 'delta_likes', 'delta_retweets', 'delta_replies'],
            horizontal=True
        )
        
        if st.button("🔍 Get Trending Tweets", type="primary"):
            with st.spinner(f"Fetching trending tweets from last {hours_back} hours..."):
                trending_df = analyzer.get_trending_tweets(hours_back=hours_back, limit=limit)
                
                if not trending_df.empty:
                    # Handle tweet_text column
                    if 'tweet_text' not in trending_df.columns:
                        trending_df['tweet_text'] = '(No text available)'
                    else:
                        trending_df['tweet_text'] = trending_df['tweet_text'].fillna('(No text available)')
                    
                    # Sort by selected metric
                    trending_df_sorted = trending_df.sort_values(sort_by, ascending=False).reset_index(drop=True)
                    
                    # Store in session state for sidebar and persistent display
                    st.session_state.trending_tweets = trending_df_sorted
                    st.success(f"✅ Found {len(trending_df)} trending tweets with recent samples")
                else:
                    st.warning("⚠️ No trending tweets found with recent samples")
        
        # Display results from session state
        if 'trending_tweets' in st.session_state and not st.session_state.trending_tweets.empty:
            trending_df_sorted = st.session_state.trending_tweets
            
            # Display summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Avg Delta Likes/min", f"{trending_df_sorted['delta_likes'].mean():.2f}")
            with col2:
                st.metric("Avg Delta Views/min", f"{trending_df_sorted['delta_views'].mean():.2f}")
            with col3:
                st.metric("Avg Delta Replies/min", f"{trending_df_sorted['delta_replies'].mean():.2f}")
            with col4:
                st.metric("Avg Delta Retweets/min", f"{trending_df_sorted['delta_retweets'].mean():.2f}")
            
            # Display the results table
            st.markdown(f"### Top {len(trending_df_sorted)} Trending Tweets")
            
            # Create display dataframe with better column names
            display_df = trending_df_sorted[[
                'author_username', 'author_id', 'tweet_id',
                'delta_likes', 'delta_views', 'delta_replies', 'delta_retweets',
                'latest_likes', 'latest_views', 'latest_replies', 'latest_retweets',
                'delta_minutes'
            ]].copy()
            
            display_df.columns = [
                'Author', 'Author ID', 'Tweet ID',
                'Δ Likes/min', 'Δ Views/min', 'Δ Replies/min', 'Δ Retweets/min',
                'Latest Likes', 'Latest Views', 'Latest Replies', 'Latest Retweets',
                'Time Δ (min)'
            ]
            
            # Add selection support
            selected_rows = st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            
            # Handle row selection for tweet text display
            if selected_rows.selection.rows:
                selected_index = selected_rows.selection.rows[0]
                st.session_state.selected_trending_tweet = selected_index
                st.info(f"Selected Row {selected_index + 1}. Check the sidebar for tweet details!")
                # Note: on_select="rerun" already handles the rerun, so we don't need another one
            
            # Download button
            csv_trending = trending_df_sorted.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Trending Tweets as CSV",
                data=csv_trending,
                file_name=f"trending_tweets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    st.markdown("---")
    
    # Top Tweets for Users Section
    st.subheader("🏆 Top Tweets Analysis - User List")
    with st.expander("📊 Analyze Top Tweets for Multiple Users", expanded=False):
        st.markdown("Enter Twitter usernames - separate by newlines, commas, or spaces (with or without @ symbol)")
        
        # Text area for username list
        usernames_text = st.text_area(
            "Twitter Usernames",
            placeholder="Examples:\none per line: netanyahu\\namit_segal\\nDrEliDavid\\n\\nor with commas: netanyahu, amit_segal, @DrEliDavid\\n\\nor with spaces: netanyahu amit_segal DrEliDavid\\n\\n(@ symbol is optional)",
            height=150,
            help="You can separate usernames by newlines, commas, or spaces. The @ symbol is optional."
        )
        
        col_days, col_top = st.columns(2)
        with col_days:
            days_back = st.selectbox("Days to look back:", [1, 3, 5, 7, 10, 14, 30], index=2)
        with col_top:
            top_n = st.number_input("Top N tweets per user:", min_value=1, max_value=10, value=5)
        
        if st.button("🔍 Analyze Top Tweets", type="primary"):
            if usernames_text:
                # Parse usernames from text - support newlines, commas, or spaces
                usernames_list = []
                # First try splitting by newlines
                for line in usernames_text.strip().split('\n'):
                    if line.strip():
                        # If the line contains commas, split by commas
                        if ',' in line:
                            usernames_list.extend([item.strip() for item in line.split(',') if item.strip()])
                        else:
                            # If no commas, split by spaces (handles multiple spaces)
                            items = line.split()
                            if len(items) > 1:
                                usernames_list.extend(items)
                            else:
                                usernames_list.append(line.strip())
                
                # Remove duplicates while preserving order
                seen = set()
                usernames_list = [x for x in usernames_list if not (x in seen or seen.add(x))]
                
                if usernames_list:
                    with st.spinner(f"Analyzing top {top_n} tweets for {len(usernames_list)} users from last {days_back} days..."):
                        results_df = analyzer.get_top_tweets_for_users(usernames_list, days_back=days_back, top_n=top_n)
                        
                        if not results_df.empty:
                            st.success(f"✅ Found data for {len(results_df)} users")
                            
                            # Display summary metrics
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Total Views", f"{results_df['total_views'].sum():,}")
                            with col2:
                                st.metric("Total Likes", f"{results_df['total_likes'].sum():,}")
                            with col3:
                                st.metric("Total Retweets", f"{results_df['total_retweets'].sum():,}")
                            with col4:
                                st.metric("Total Replies", f"{results_df['total_replies'].sum():,}")
                            
                            # Display detailed results
                            st.markdown(f"### Top {top_n} Tweets per User (sorted by total views)")
                            
                            # Format the last_sample_time column for display
                            results_display = results_df.copy()
                            if 'last_sample_time' in results_display.columns:
                                results_display['last_sample_time'] = pd.to_datetime(results_display['last_sample_time']).apply(
                                    lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else 'Never'
                                )
                            
                            display_results = results_display[[
                                'author_username', 'author_id', 'tweet_count',
                                'total_views', 'total_likes', 'total_retweets', 'total_replies',
                                'max_single_views', 'max_single_likes', 'max_single_retweets', 'max_single_replies',
                                'recent_sample_count', 'last_sample_time'
                            ]].copy()
                            
                            display_results.columns = [
                                'Username', 'Author ID', 'Top Tweet Count',
                                'Total Views', 'Total Likes', 'Total Retweets', 'Total Replies',
                                'Max Views', 'Max Likes', 'Max Retweets', 'Max Replies',
                                'Recent Samples (6h)', 'Last Sample Time'
                            ]
                            
                            st.dataframe(
                                display_results,
                                use_container_width=True,
                                hide_index=True
                            )
                            
                            # Download button
                            csv_results = results_df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Download Results as CSV",
                                data=csv_results,
                                file_name=f"top_tweets_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                        else:
                            st.warning("⚠️ No tweets found for the specified users and date range")
                else:
                    st.error("❌ Please enter at least one username")
            else:
                st.error("❌ Please enter some usernames to analyze")
    
    st.markdown("---")
    
    # Original Tweets Section
    st.subheader("📝 Original Tweets - Recent Posts")
    with st.expander("🔥 View Original Tweets (Not Replies/Retweets)", expanded=False):
        col_hours, col_limit = st.columns(2)
        with col_hours:
            original_hours = st.selectbox("Hours to look back:", [1, 2, 3, 6, 12, 24], index=2, key="original_hours")
        with col_limit:
            original_limit = st.number_input("Max tweets to show:", min_value=10, max_value=500, value=100, step=10, key="original_limit")
        
        if st.button("🔍 Get Original Tweets", type="primary", key="btn_original"):
            with st.spinner(f"Fetching original tweets from last {original_hours} hours..."):
                original_df = analyzer.get_original_tweets(hours_back=original_hours, limit=original_limit)
                
                if not original_df.empty:
                    st.success(f"✅ Found {len(original_df)} original tweets")
                    
                    # Display summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Views", f"{original_df['max_views'].sum():,}")
                    with col2:
                        st.metric("Total Likes", f"{original_df['max_likes'].sum():,}")
                    with col3:
                        st.metric("Total Replies", f"{original_df['max_replies'].sum():,}")
                    with col4:
                        st.metric("Total Retweets", f"{original_df['max_retweets'].sum():,}")
                    
                    # Display detailed results
                    st.markdown(f"### Top {len(original_df)} Original Tweets (sorted by views)")
                    
                    # Format the created_at column for display
                    display_original = original_df.copy()
                    if 'created_at' in display_original.columns:
                        display_original['created_at'] = pd.to_datetime(display_original['created_at']).apply(
                            lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else 'N/A'
                        )
                    if 'last_sampled' in display_original.columns:
                        display_original['last_sampled'] = pd.to_datetime(display_original['last_sampled']).apply(
                            lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else 'N/A'
                        )
                    
                    # Fill NaN for tweet_text
                    if 'tweet_text' in display_original.columns:
                        display_original['tweet_text'] = display_original['tweet_text'].fillna('(No text available)')
                    
                    display_original = display_original[[
                        'author_username', 'author_id', 'tweet_id', 'tweet_text',
                        'max_views', 'max_likes', 'max_replies', 'max_retweets',
                        'created_at', 'last_sampled'
                    ]].copy()
                    
                    display_original.columns = [
                        'Username', 'Author ID', 'Tweet ID', 'Tweet Text',
                        'Views', 'Likes', 'Replies', 'Retweets',
                        'Created At', 'Last Sampled'
                    ]
                    
                    st.dataframe(
                        display_original,
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Download button
                    csv_original = original_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Original Tweets as CSV",
                        data=csv_original,
                        file_name=f"original_tweets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("⚠️ No original tweets found for the specified time range")
    
    st.markdown("---")
    
    # All Tweets Section
    st.subheader("📋 All Tweets - With Classification")
    with st.expander("🌐 View All Tweets (Retweets, Replies, Media)", expanded=False):
        col_all_hours, col_all_limit = st.columns(2)
        with col_all_hours:
            all_hours = st.selectbox("Hours to look back:", [1, 2, 3, 6, 12, 24], index=2, key="all_hours")
        with col_all_limit:
            all_limit = st.number_input("Max tweets to show:", min_value=10, max_value=500, value=100, step=10, key="all_limit")
        
        st.info("💡 All tweets will be fetched. Rows are color-coded by political leaning: 🔴 Light Red (left), 🔵 Light Blue (right), 🟢 Light Green (center/unknown)")
        
        if st.button("🔍 Get All Tweets", type="primary", key="btn_all_tweets"):
            # Always fetch all tweets (no filter)
            with st.spinner(f"Fetching all tweets from last {all_hours} hours..."):
                all_tweets_df = analyzer.get_all_tweets(hours_back=all_hours, limit=all_limit, political_leaning=None)
                
                if not all_tweets_df.empty:
                    st.success(f"✅ Found {len(all_tweets_df)} tweets")
                    
                    # Display summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Views", f"{all_tweets_df['max_views'].sum():,}")
                    with col2:
                        st.metric("Total Likes", f"{all_tweets_df['max_likes'].sum():,}")
                    with col3:
                        st.metric("Total Replies", f"{all_tweets_df['max_replies'].sum():,}")
                    with col4:
                        st.metric("Total Retweets", f"{all_tweets_df['max_retweets'].sum():,}")
                    
                    # Political leaning breakdown
                    if 'political_leaning' in all_tweets_df.columns:
                        st.markdown("### Political Leaning Breakdown")
                        leaning_counts = all_tweets_df['political_leaning'].value_counts()
                        col_leaning1, col_leaning2, col_leaning3, col_leaning4 = st.columns(4)
                        with col_leaning1:
                            st.metric("Left", leaning_counts.get('left', 0))
                        with col_leaning2:
                            st.metric("Right", leaning_counts.get('right', 0))
                        with col_leaning3:
                            center_count = leaning_counts.get('center_left', 0) + leaning_counts.get('center_right', 0)
                            st.metric("Center", center_count)
                        with col_leaning4:
                            st.metric("Unknown", leaning_counts.get('Unknown', 0))
                    
                    # Classification summary
                    st.markdown("### Classification Summary")
                    if 'classification' in all_tweets_df.columns:
                        class_counts = all_tweets_df['classification'].value_counts()
                        col_class1, col_class2, col_class3, col_class4 = st.columns(4)
                        with col_class1:
                            st.metric("Retweets", class_counts.get('retweet', 0))
                        with col_class2:
                            st.metric("Self Replies", class_counts.get('SelfReply', 0))
                        with col_class3:
                            st.metric("Media", class_counts.get('media', 0))
                        with col_class4:
                            st.metric("Others", class_counts.get('', 0))
                    
                    # Display detailed results
                    st.markdown(f"### All {len(all_tweets_df)} Tweets (sorted by views)")
                    
                    # Work with a copy before formatting dates
                    display_all = all_tweets_df.copy()
                    
                    # Calculate normalized metrics (likes and views per minute)
                    # Calculate delta minutes between created_at and last_sampled
                    if 'created_at' in display_all.columns and 'last_sampled' in display_all.columns:
                        # Convert to datetime for calculation
                        display_all['created_at_dt'] = pd.to_datetime(display_all['created_at'], errors='coerce')
                        display_all['last_sampled_dt'] = pd.to_datetime(display_all['last_sampled'], errors='coerce')
                        
                        # Calculate delta in minutes
                        display_all['delta_minutes'] = (display_all['last_sampled_dt'] - display_all['created_at_dt']).dt.total_seconds() / 60.0
                        
                        # Ensure numeric columns are numeric
                        display_all['max_likes'] = pd.to_numeric(display_all['max_likes'], errors='coerce').fillna(0)
                        display_all['max_views'] = pd.to_numeric(display_all['max_views'], errors='coerce').fillna(0)
                        display_all['delta_minutes'] = pd.to_numeric(display_all['delta_minutes'], errors='coerce')
                        
                        # Calculate normalized metrics (per minute)
                        # Avoid division by zero - if delta_minutes is 0, negative, or NaN, set to NaN (will result in 0 normalized)
                        def safe_divide(likes, views, delta):
                            if pd.isna(delta) or delta <= 0:
                                return 0.0, 0.0
                            return round(likes / delta, 2), round(views / delta, 2)
                        
                        normalized = display_all.apply(
                            lambda row: safe_divide(row['max_likes'], row['max_views'], row['delta_minutes']),
                            axis=1
                        )
                        display_all['Nlikes'] = [n[0] for n in normalized]
                        display_all['Nviews'] = [n[1] for n in normalized]
                        
                        # Clean up temporary datetime columns
                        display_all = display_all.drop(columns=['created_at_dt', 'last_sampled_dt', 'delta_minutes'], errors='ignore')
                    else:
                        # If we don't have the required columns, set normalized values to 0
                        display_all['Nlikes'] = 0.0
                        display_all['Nviews'] = 0.0
                    
                    # Format the created_at column for display
                    if 'created_at' in display_all.columns:
                        display_all['created_at'] = pd.to_datetime(display_all['created_at'], errors='coerce').apply(
                            lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else 'N/A'
                        )
                    if 'last_sampled' in display_all.columns:
                        display_all['last_sampled'] = pd.to_datetime(display_all['last_sampled'], errors='coerce').apply(
                            lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else 'N/A'
                        )
                    
                    # Fill NaN for tweet_text
                    if 'tweet_text' in display_all.columns:
                        display_all['tweet_text'] = display_all['tweet_text'].fillna('(No text available)')
                    
                    # Calculate text length
                    display_all['text_length'] = display_all['tweet_text'].apply(
                        lambda x: len(str(x)) if pd.notna(x) and isinstance(x, str) else 0
                    )
                    
                    # Select columns for display
                    display_columns = [
                        'author_username', 'author_id', 'tweet_id', 'tweet_text',
                        'classification', 'text_length', 'max_views', 'max_likes', 'Nviews', 'Nlikes', 'max_replies', 'max_retweets',
                        'created_at', 'original_tweet_url', 'political_leaning'
                    ]
                    
                    # Only include columns that exist
                    available_columns = [col for col in display_columns if col in display_all.columns]
                    display_all_filtered = display_all[available_columns].copy()
                    
                    # Store political_leaning for coloring before renaming
                    political_leaning_col = display_all_filtered['political_leaning'].copy() if 'political_leaning' in display_all_filtered.columns else None
                    
                    # Rename columns (excluding political_leaning from display)
                    display_cols_without_leaning = [col for col in display_all_filtered.columns if col != 'political_leaning']
                    display_all_filtered_display = display_all_filtered[display_cols_without_leaning].copy()
                    
                    display_all_filtered_display.columns = [
                        'Username', 'Author ID', 'Tweet ID', 'Tweet Text',
                        'Type', 'Len', 'Views', 'Likes', 'Nviews', 'Nlikes', 'Replies', 'Retweets',
                        'Created At', 'Original Tweet URL'
                    ]
                    
                    # Apply row coloring based on political_leaning
                    # Create a list of leanings in the same order as the dataframe rows
                    if political_leaning_col is not None:
                        # Reset index to ensure alignment
                        political_leaning_col_reset = political_leaning_col.reset_index(drop=True)
                        display_all_filtered_display_reset = display_all_filtered_display.reset_index(drop=True)
                        leanings_list = [str(l).lower() if pd.notna(l) else 'unknown' for l in political_leaning_col_reset]
                    else:
                        leanings_list = ['unknown'] * len(display_all_filtered_display)
                    
                    def color_rows(row):
                        """Return background color for each row based on political leaning"""
                        row_pos = row.name
                        if row_pos < len(leanings_list):
                            leaning = leanings_list[row_pos]
                        else:
                            leaning = 'unknown'
                        
                        if leaning == 'left':
                            return ['background-color: #ffcccc'] * len(row)  # Light red
                        elif leaning == 'right':
                            return ['background-color: #cce5ff'] * len(row)  # Light blue
                        else:
                            # center_left, center_right, Unknown, or any other
                            return ['background-color: #ccffcc'] * len(row)  # Light green
                    
                    # Use the reset dataframe for display
                    display_all_filtered_display = display_all_filtered_display_reset if political_leaning_col is not None else display_all_filtered_display
                    
                    # Apply styling
                    styled_df = display_all_filtered_display.style.apply(color_rows, axis=1)
                    
                    st.dataframe(
                        styled_df,
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Calculate statistics
                    # Natural tweet: Rows where Type (classification) is empty
                    natural_tweets = 0
                    short_tweets = 0
                    media_tweets = 0
                    quoted_tweets = 0
                    
                    for idx, row in all_tweets_df.iterrows():
                        classification = str(row.get('classification', '')).strip()
                        
                        # Natural tweet: classification is empty
                        if classification == '' or classification == 'nan':
                            natural_tweets += 1
                        
                        # Check if it's a short tweet (contains 'Tweet' in classification)
                        if 'Tweet' in classification:
                            short_tweets += 1
                        
                        # Check if it has media (contains 'media' in classification)
                        if 'media' in classification:
                            media_tweets += 1
                        
                        # Check if it's quoted (contains 'Quoted' in classification)
                        if 'Quoted' in classification:
                            quoted_tweets += 1
                    
                    total_tweets = len(all_tweets_df)
                    
                    # Display statistics
                    st.markdown("---")
                    st.markdown(f"**📊 Statistics:** Natural Tweet = {natural_tweets} | Short Tweet = {short_tweets} | Media Tweet = {media_tweets} | Quoted = {quoted_tweets} | Total Tweet = {total_tweets}")
                    
                    # Top 20 and Top 50 statistics by political leaning
                    if 'political_leaning' in all_tweets_df.columns and len(all_tweets_df) > 0:
                        # Helper function to calculate stats for top N
                        def calculate_top_stats(df, n):
                            top_n = df.head(n).copy()
                            
                            # Group by political leaning
                            def categorize_leaning(leaning):
                                if pd.isna(leaning) or str(leaning).lower() == 'unknown':
                                    return 'Unknown'
                                leaning_str = str(leaning).lower()
                                if leaning_str == 'left':
                                    return 'Left'
                                elif leaning_str == 'right':
                                    return 'Right'
                                elif 'center' in leaning_str:
                                    return 'Center'
                                else:
                                    return 'Unknown'
                            
                            top_n['leaning_category'] = top_n['political_leaning'].apply(categorize_leaning)
                            
                            # Ensure numeric columns are numeric
                            numeric_cols = ['max_likes', 'max_views', 'max_replies', 'max_retweets']
                            for col in numeric_cols:
                                if col in top_n.columns:
                                    top_n[col] = pd.to_numeric(top_n[col], errors='coerce').fillna(0)
                            
                            # Aggregate by category
                            stats = {}
                            for category in ['Left', 'Right', 'Center', 'Unknown']:
                                category_df = top_n[top_n['leaning_category'] == category]
                                if len(category_df) > 0:
                                    stats[category] = {
                                        'authors': category_df['author_id'].nunique(),
                                        'tweets': len(category_df),
                                        'likes': int(category_df['max_likes'].sum()),
                                        'views': int(category_df['max_views'].sum()),
                                        'replies': int(category_df['max_replies'].sum()),
                                        'retweets': int(category_df['max_retweets'].sum())
                                    }
                                else:
                                    stats[category] = {
                                        'authors': 0,
                                        'tweets': 0,
                                        'likes': 0,
                                        'views': 0,
                                        'replies': 0,
                                        'retweets': 0
                                    }
                            return stats
                        
                        # Calculate Top 20 stats
                        top20_stats = calculate_top_stats(all_tweets_df, 20)
                        
                        # Calculate Top 50 stats
                        top50_stats = calculate_top_stats(all_tweets_df, 50)
                        
                        # Helper function to format stats for one group
                        def format_group_stats(group_name, stats_data):
                            return f"{group_name}: {stats_data['authors']} authors, {stats_data['tweets']} tweets (Likes: {stats_data['likes']:,} | Views: {stats_data['views']:,} | Replies: {stats_data['replies']:,} | Retweets: {stats_data['retweets']:,})"
                        
                        # Display Top 20 statistics in compact format
                        top20_line = f"**📈 Top 20:** {format_group_stats('Left', top20_stats['Left'])} | {format_group_stats('Right', top20_stats['Right'])} | {format_group_stats('Center', top20_stats['Center'])} | {format_group_stats('Unknown', top20_stats['Unknown'])}"
                        st.markdown(top20_line)
                        
                        # Display Top 50 statistics in compact format
                        top50_line = f"**📈 Top 50:** {format_group_stats('Left', top50_stats['Left'])} | {format_group_stats('Right', top50_stats['Right'])} | {format_group_stats('Center', top50_stats['Center'])} | {format_group_stats('Unknown', top50_stats['Unknown'])}"
                        st.markdown(top50_line)
                    
                    # Download button
                    csv_all = all_tweets_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download All Tweets as CSV",
                        data=csv_all,
                        file_name=f"all_tweets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("⚠️ No tweets found for the specified time range")
    
    st.markdown("---")
    
    # First Hour Engagement Analysis Section
    st.subheader("⏱️ First Hour Engagement Analysis")
    with st.expander("📊 Analyze First Hour Engagement for User List", expanded=False):
        st.markdown("Enter Twitter usernames separated by commas to analyze their first hour engagement")
        
        # Text input for comma-separated usernames
        usernames_input = st.text_input(
            "Twitter Usernames (comma-separated):",
            placeholder="Example: netanyahu, amit_segal, DrEliDavid",
            help="Enter usernames separated by commas. The @ symbol is optional."
        )
        
        col_days, col_limit = st.columns(2)
        with col_days:
            days_back = st.selectbox("Days to look back:", [5, 7, 10, 14, 30], index=2, key="first_hour_days")
        with col_limit:
            max_tweets_per_user = st.number_input("Max tweets per user:", min_value=1, max_value=50, value=5, step=1, key="first_hour_max_tweets")
        
        col_sort_by, col_show_all = st.columns(2)
        with col_sort_by:
            sort_by_metric = st.radio(
                "Sort by (for top tweets):",
                options=['max_likes_first_hour', 'max_views_first_hour'],
                index=1,
                key="first_hour_sort_by",
                horizontal=True,
                help="Sort tweets by likes or views in first hour to find strongest tweets"
            )
        with col_show_all:
            show_all_tweets = st.checkbox("Show all tweets (ignore limit)", value=False, key="first_hour_show_all")
        
        if st.button("🔍 Analyze First Hour Engagement", type="primary", key="btn_first_hour"):
            if usernames_input:
                # Parse usernames from comma-separated input
                usernames_list = [username.strip().lstrip('@') for username in usernames_input.split(',') if username.strip()]
                
                if usernames_list:
                    with st.spinner(f"Analyzing first hour engagement for {len(usernames_list)} users from last {days_back} days..."):
                        first_hour_df = analyzer.get_first_hour_engagement(usernames_list, days_back=days_back)
                        
                        if not first_hour_df.empty:
                            # Store raw data in session state
                            st.session_state.first_hour_raw_data = first_hour_df
                            st.success(f"✅ Found {len(first_hour_df)} tweets from {first_hour_df['author_username'].nunique()} users")
                        else:
                            st.warning("⚠️ No tweets found for the specified users and date range")
        
        # Process and display stored data with filters
        if 'first_hour_raw_data' in st.session_state and not st.session_state.first_hour_raw_data.empty:
            first_hour_df_raw = st.session_state.first_hour_raw_data.copy()
            
            st.info("💡 You can adjust the filters above to change the displayed results (max tweets per user, sort by, show all)")
            
            # Apply filtering: get top N tweets per user based on sort metric
            if not show_all_tweets:
                # Sort by selected metric and get top N per user
                first_hour_df = first_hour_df_raw.sort_values(sort_by_metric, ascending=False).groupby('author_username').head(max_tweets_per_user).reset_index(drop=True)
            else:
                first_hour_df = first_hour_df_raw.copy()
            
            # Sort the final dataframe by the selected metric
            first_hour_df = first_hour_df.sort_values(sort_by_metric, ascending=False).reset_index(drop=True)
            
            if not first_hour_df.empty:
                # Show filter info
                filter_info = f"Showing top {max_tweets_per_user} tweets per user" if not show_all_tweets else "Showing all tweets"
                sort_label = "views" if sort_by_metric == 'max_views_first_hour' else "likes"
                st.success(f"📊 {filter_info} (sorted by {sort_label} in first hour) | Total: {len(first_hour_df)} tweets from {first_hour_df['author_username'].nunique()} users")
                
                # Display summary metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Tweets", len(first_hour_df))
                with col2:
                    st.metric("Total Users", first_hour_df['author_username'].nunique())
                with col3:
                    st.metric("Total Likes (1h)", f"{first_hour_df['max_likes_first_hour'].sum():,}")
                with col4:
                    st.metric("Total Views (1h)", f"{first_hour_df['max_views_first_hour'].sum():,}")
                
                # Per-user summary
                st.markdown("### Per-User Summary")
                user_summary = first_hour_df.groupby('author_username').agg({
                    'tweet_id': 'count',
                    'max_likes_first_hour': 'sum',
                    'max_views_first_hour': 'sum',
                    'max_replies_first_hour': 'sum',
                    'max_retweets_first_hour': 'sum',
                    'likes_growth_first_hour': 'sum',
                    'views_growth_first_hour': 'sum'
                }).reset_index()
                
                user_summary.columns = [
                    'Username', 'Tweet Count', 'Total Likes (1h)', 'Total Views (1h)',
                    'Total Replies (1h)', 'Total Retweets (1h)', 'Likes Growth (1h)', 'Views Growth (1h)'
                ]
                
                st.dataframe(
                    user_summary.sort_values('Total Views (1h)', ascending=False),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Display detailed results
                st.markdown(f"### Detailed Results - {len(first_hour_df)} Tweets")
                
                # Format the dataframe for display
                display_first_hour = first_hour_df.copy()
                
                # Format datetime columns
                if 'tweet_created_at' in display_first_hour.columns:
                    display_first_hour['tweet_created_at'] = pd.to_datetime(display_first_hour['tweet_created_at']).apply(
                        lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else 'N/A'
                    )
                if 'first_sample_time' in display_first_hour.columns:
                    display_first_hour['first_sample_time'] = pd.to_datetime(display_first_hour['first_sample_time']).apply(
                        lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else 'N/A'
                    )
                if 'last_sample_time' in display_first_hour.columns:
                    display_first_hour['last_sample_time'] = pd.to_datetime(display_first_hour['last_sample_time']).apply(
                        lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else 'N/A'
                    )
                
                # Fill NaN for tweet_text
                if 'tweet_text' in display_first_hour.columns:
                    display_first_hour['tweet_text'] = display_first_hour['tweet_text'].fillna('(No text available)')
                
                # Generate tweet URLs
                def generate_tweet_url(row):
                    tweet_id = row.get('tweet_id')
                    if pd.notna(tweet_id):
                        try:
                            return build_twitter_url('tweet', tweet_id=int(tweet_id))
                        except (ValueError, TypeError):
                            return ''
                    return ''
                
                display_first_hour['tweet_url'] = display_first_hour.apply(generate_tweet_url, axis=1)
                
                # Select and rename columns for display
                # Reorder: max metrics right after tweet_text, total metrics and URL at the end
                # Create a mapping of original column names to display names
                column_mapping = {
                    'author_username': 'Username',
                    'author_id': 'Author ID',
                    'tweet_id': 'Tweet ID',
                    'tweet_text': 'Tweet Text',
                    'max_likes_first_hour': 'Max Likes (1h)',
                    'max_views_first_hour': 'Max Views (1h)',
                    'max_replies_first_hour': 'Max Replies (1h)',
                    'max_retweets_first_hour': 'Max Retweets (1h)',
                    'tweet_created_at': 'Created At',
                    'sample_count': 'Samples',
                    'first_sample_time': 'First Sample',
                    'last_sample_time': 'Last Sample',
                    'first_likes': 'First Likes',
                    'first_views': 'First Views',
                    'first_replies': 'First Replies',
                    'first_retweets': 'First Retweets',
                    'likes_growth_first_hour': 'Likes Growth (1h)',
                    'views_growth_first_hour': 'Views Growth (1h)',
                    'replies_growth_first_hour': 'Replies Growth (1h)',
                    'retweets_growth_first_hour': 'Retweets Growth (1h)',
                    'total_views': 'Total Views',
                    'total_likes': 'Total Likes',
                    'tweet_url': 'Tweet URL'
                }
                
                # Define the desired column order
                desired_order = [
                    'author_username', 'author_id', 'tweet_id', 'tweet_text',
                    'max_likes_first_hour', 'max_views_first_hour', 'max_replies_first_hour', 'max_retweets_first_hour',
                    'tweet_created_at',
                    'sample_count', 'first_sample_time', 'last_sample_time',
                    'first_likes', 'first_views', 'first_replies', 'first_retweets',
                    'likes_growth_first_hour', 'views_growth_first_hour', 'replies_growth_first_hour', 'retweets_growth_first_hour',
                    'total_views', 'total_likes', 'tweet_url'
                ]
                
                # Filter to only include columns that exist and maintain order
                available_cols = [col for col in desired_order if col in display_first_hour.columns]
                display_first_hour_filtered = display_first_hour[available_cols].copy()
                
                # Rename columns using the mapping
                display_first_hour_filtered = display_first_hour_filtered.rename(columns=column_mapping)
                
                st.dataframe(
                    display_first_hour_filtered,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Download button
                csv_first_hour = first_hour_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download First Hour Engagement as CSV",
                    data=csv_first_hour,
                    file_name=f"first_hour_engagement_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    
    st.markdown("---")
    
    # Influencers Clustering Section
    st.subheader("🔀 Influencers Clustering")
    
    # Political Leaning Classification
    with st.expander("📊 View Political Leaning Classification", expanded=False):
        if st.button("🔍 Get Political Leaning Classification", type="primary", key="btn_clustering"):
            with st.spinner("Analyzing political leaning classification for all users..."):
                clustering_df = analyzer.get_political_leaning_classification()
                
                if not clustering_df.empty:
                    st.success(f"✅ Found {clustering_df['user_count'].sum():,} total users")
                    
                    # Display summary metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Users", f"{clustering_df['user_count'].sum():,}")
                    with col2:
                        known_users = clustering_df[clustering_df['political_leaning'] != 'Unknown']['user_count'].sum()
                        st.metric("Known Classification", f"{known_users:,}")
                    with col3:
                        unknown_users = clustering_df[clustering_df['political_leaning'] == 'Unknown']['user_count'].sum()
                        st.metric("Unknown Classification", f"{unknown_users:,}")
                    
                    # Display detailed results
                    st.markdown("### Classification by Political Leaning")
                    
                    # Format the dataframe for display
                    display_clustering = clustering_df.copy()
                    display_clustering.columns = ['Political Leaning', 'User Count']
                    
                    st.dataframe(
                        display_clustering,
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Download button
                    csv_clustering = clustering_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Classification as CSV",
                        data=csv_clustering,
                        file_name=f"political_leaning_classification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("⚠️ No classification data found")
        
        # Tweet counts by political leaning
        st.markdown("---")
        st.markdown("### Tweets Created in Last 12 Hours by Group")
        
        if st.button("📊 Get Tweet Counts by Political Leaning", type="primary", key="btn_tweet_counts"):
            with st.spinner("Counting tweets created in the last 12 hours by political leaning..."):
                tweets_by_leaning_df = analyzer.get_tweets_by_political_leaning(hours_back=12)
                
                if not tweets_by_leaning_df.empty:
                    # Store in session state
                    st.session_state.tweets_by_leaning = tweets_by_leaning_df
                    st.success(f"✅ Found {tweets_by_leaning_df['tweet_count'].sum():,} total tweets in the last 12 hours")
                else:
                    st.warning("⚠️ No tweets found in the last 12 hours")
        
        # Display stored results
        if 'tweets_by_leaning' in st.session_state and not st.session_state.tweets_by_leaning.empty:
            tweets_by_leaning_df = st.session_state.tweets_by_leaning
            
            # Display summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Tweets (12h)", f"{tweets_by_leaning_df['tweet_count'].sum():,}")
            with col2:
                known_tweets = tweets_by_leaning_df[tweets_by_leaning_df['political_leaning'] != 'Unknown']['tweet_count'].sum()
                st.metric("Known Classification", f"{known_tweets:,}")
            with col3:
                unknown_tweets = tweets_by_leaning_df[tweets_by_leaning_df['political_leaning'] == 'Unknown']['tweet_count'].sum()
                st.metric("Unknown Classification", f"{unknown_tweets:,}")
            
            # Display detailed results
            st.markdown("### Tweet Counts by Political Leaning")
            
            # Format the dataframe for display
            display_tweets = tweets_by_leaning_df.copy()
            display_tweets.columns = ['Political Leaning', 'Tweet Count']
            
            st.dataframe(
                display_tweets,
                use_container_width=True,
                hide_index=True
            )
            
            # Download button
            csv_tweets = tweets_by_leaning_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Tweet Counts as CSV",
                data=csv_tweets,
                file_name=f"tweets_by_political_leaning_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        # Tweets by cluster section
        st.markdown("---")
        st.markdown("### Tweets by Selected Cluster")
        
        col_cluster_hours, col_cluster_limit = st.columns(2)
        with col_cluster_hours:
            cluster_hours = st.selectbox("Hours to look back (K):", [1, 2, 3, 6, 12, 24], index=2, key="cluster_hours")
        with col_cluster_limit:
            cluster_limit = st.number_input("Max tweets to show:", min_value=10, max_value=500, value=100, step=10, key="cluster_limit")
        
        # Political leaning filter for cluster tweets
        cluster_political_leaning = st.selectbox(
            "Select Political Leaning Cluster:",
            options=['all', 'left', 'center_left', 'center_right', 'right', 'Unknown'],
            index=0,
            key="cluster_political_leaning",
            help="Filter tweets by the selected political leaning cluster"
        )
        
        # Sort by option
        cluster_sort_by = st.radio(
            "Sort by popularity:",
            options=['views', 'likes'],
            index=0,
            key="cluster_sort_by",
            horizontal=True,
            help="Sort tweets by views or likes"
        )
        
        if st.button("🔍 Get Tweets by Cluster", type="primary", key="btn_cluster_tweets"):
            # Pass 'all' as None to the method
            cluster_leaning_filter = None if cluster_political_leaning == 'all' else cluster_political_leaning
            
            # Get author count first for progress indication
            if cluster_leaning_filter:
                with st.spinner("Loading author list..."):
                    author_ids = analyzer.get_author_ids_by_cluster(cluster_leaning_filter)
                    total_authors = len(author_ids) if author_ids else 0
            else:
                total_authors = 0
            
            if cluster_leaning_filter and total_authors == 0:
                st.warning(f"⚠️ No authors found for {cluster_political_leaning} cluster")
            else:
                # Create progress bar and status container
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Progress callback function
                def update_progress(processed, total, message):
                    progress = processed / total if total > 0 else 0
                    progress_bar.progress(progress)
                    status_text.text(f"{message} - Processed {processed}/{total} authors ({progress*100:.1f}%)")
                
                try:
                    cluster_tweets_df = analyzer.get_tweets_by_cluster_batched(
                        hours_back=cluster_hours, 
                        limit=cluster_limit, 
                        political_leaning=cluster_leaning_filter,
                        sort_by=cluster_sort_by,
                        progress_callback=update_progress
                    )
                    
                    # Clear progress indicators
                    progress_bar.empty()
                    status_text.empty()
                    
                    if not cluster_tweets_df.empty:
                        # Store in session state
                        st.session_state.cluster_tweets = cluster_tweets_df
                        filter_msg = f" (filtered by {cluster_political_leaning})" if cluster_political_leaning != 'all' else ""
                        st.success(f"✅ Found {len(cluster_tweets_df)} tweets{filter_msg}")
                    else:
                        st.warning(f"⚠️ No tweets found for {cluster_political_leaning} cluster in the last {cluster_hours} hours")
                except Exception as e:
                    progress_bar.empty()
                    status_text.empty()
                    st.error(f"❌ Error processing tweets: {str(e)}")
                    st.exception(e)
        
        # Display stored cluster tweets results
        if 'cluster_tweets' in st.session_state and not st.session_state.cluster_tweets.empty:
            cluster_tweets_df = st.session_state.cluster_tweets
            
            # Display summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Views", f"{cluster_tweets_df['max_views'].sum():,}")
            with col2:
                st.metric("Total Likes", f"{cluster_tweets_df['max_likes'].sum():,}")
            with col3:
                st.metric("Total Replies", f"{cluster_tweets_df['max_replies'].sum():,}")
            with col4:
                st.metric("Total Retweets", f"{cluster_tweets_df['max_retweets'].sum():,}")
            
            # Classification summary
            st.markdown("### Classification Summary")
            if 'classification' in cluster_tweets_df.columns:
                class_counts = cluster_tweets_df['classification'].value_counts()
                col_class1, col_class2, col_class3, col_class4 = st.columns(4)
                with col_class1:
                    st.metric("Retweets", class_counts.get('retweet', 0))
                with col_class2:
                    st.metric("Self Replies", class_counts.get('SelfReply', 0))
                with col_class3:
                    st.metric("Media", class_counts.get('media', 0))
                with col_class4:
                    st.metric("Others", class_counts.get('', 0))
            
            # Display detailed results
            # Check if sort_by is stored in session state, otherwise default to 'views'
            stored_sort_by = st.session_state.get('cluster_sort_by', 'views')
            sort_label = 'views' if stored_sort_by == 'views' else 'likes'
            st.markdown(f"### All {len(cluster_tweets_df)} Tweets (sorted by {sort_label})")
            
            # Format the created_at column for display
            display_cluster = cluster_tweets_df.copy()
            if 'created_at' in display_cluster.columns:
                display_cluster['created_at'] = pd.to_datetime(display_cluster['created_at']).apply(
                    lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else 'N/A'
                )
            if 'last_sampled' in display_cluster.columns:
                display_cluster['last_sampled'] = pd.to_datetime(display_cluster['last_sampled']).apply(
                    lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else 'N/A'
                )
            
            # Fill NaN for tweet_text
            if 'tweet_text' in display_cluster.columns:
                display_cluster['tweet_text'] = display_cluster['tweet_text'].fillna('(No text available)')
            
            # Calculate text length
            display_cluster['text_length'] = display_cluster['tweet_text'].apply(
                lambda x: len(str(x)) if pd.notna(x) and isinstance(x, str) else 0
            )
            
            # Select columns for display
            display_columns = [
                'author_username', 'author_id', 'tweet_id', 'tweet_text',
                'classification', 'text_length', 'max_views', 'max_likes', 'max_replies', 'max_retweets',
                'created_at', 'original_tweet_url'
            ]
            
            # Only include columns that exist
            available_columns = [col for col in display_columns if col in display_cluster.columns]
            display_cluster_filtered = display_cluster[available_columns].copy()
            
            display_cluster_filtered.columns = [
                'Username', 'Author ID', 'Tweet ID', 'Tweet Text',
                'Type', 'Len', 'Views', 'Likes', 'Replies', 'Retweets',
                'Created At', 'Original Tweet URL'
            ]
            
            st.dataframe(
                display_cluster_filtered,
                use_container_width=True,
                hide_index=True
            )
            
            # Calculate statistics
            natural_tweets = 0
            short_tweets = 0
            media_tweets = 0
            quoted_tweets = 0
            
            for idx, row in cluster_tweets_df.iterrows():
                classification = str(row.get('classification', '')).strip()
                
                # Natural tweet: classification is empty
                if classification == '' or classification == 'nan':
                    natural_tweets += 1
                
                # Check if it's a short tweet (contains 'Tweet' in classification)
                if 'Tweet' in classification:
                    short_tweets += 1
                
                # Check if it has media (contains 'media' in classification)
                if 'media' in classification:
                    media_tweets += 1
                
                # Check if it's quoted (contains 'Quoted' in classification)
                if 'Quoted' in classification:
                    quoted_tweets += 1
            
            total_tweets = len(cluster_tweets_df)
            
            # Display statistics
            st.markdown("---")
            st.markdown(f"**📊 Statistics:** Natural Tweet = {natural_tweets} | Short Tweet = {short_tweets} | Media Tweet = {media_tweets} | Quoted = {quoted_tweets} | Total Tweet = {total_tweets}")
            
            # Download button
            csv_cluster = cluster_tweets_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Cluster Tweets as CSV",
                data=csv_cluster,
                file_name=f"cluster_tweets_{cluster_political_leaning}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    # Cross-Correlation Analysis
    with st.expander("🔗 Cross-Correlation Analysis", expanded=False):
        st.markdown("Analyze correlation between influencers based on their tweet performance metrics")
        
        col_corr_hours, col_corr_min_views = st.columns(2)
        with col_corr_hours:
            corr_hours = st.selectbox("Hours to look back:", [1, 2, 3, 6, 12, 24], index=2, key="corr_hours")
        with col_corr_min_views:
            corr_min_views = st.number_input("Min Views (Super Tweets):", min_value=100, max_value=100000, value=1000, step=100, key="corr_min_views")
        
        # Political leaning filter for correlation
        corr_political_leaning = st.selectbox(
            "Political Leaning Filter:",
            options=['all', 'left', 'center_left', 'center_right', 'right'],
            index=0,
            key="corr_political_leaning",
            help="Filter influencers by political leaning"
        )
        
        if st.button("🔍 Analyze Influencer Correlation", type="primary", key="btn_correlation"):
            # Pass 'all' as None to the method
            corr_leaning_filter = None if corr_political_leaning == 'all' else corr_political_leaning
            
            with st.spinner(f"Finding influencers from super tweets (min {corr_min_views:,} views)..."):
                influencers_df = analyzer.get_influencers_for_correlation(
                    hours_back=corr_hours,
                    min_views=corr_min_views,
                    political_leaning=corr_leaning_filter
                )
                
                if not influencers_df.empty and len(influencers_df) >= 2:
                    st.success(f"✅ Found {len(influencers_df)} influencers with {influencers_df['tweet_count'].sum():,} super tweets")
                    
                    # Store in session state
                    st.session_state.correlation_influencers = influencers_df
                    
                    # Display summary
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Influencers", len(influencers_df))
                    with col2:
                        st.metric("Total Super Tweets", int(influencers_df['tweet_count'].sum()))
                    with col3:
                        st.metric("Avg Views per Influencer", f"{influencers_df['avg_views'].mean():,.0f}")
                    with col4:
                        st.metric("Max Views", f"{influencers_df['max_views'].max():,.0f}")
                    
                    # Display influencers table
                    st.markdown("### Influencers Found")
                    display_influencers = influencers_df[[
                        'author_username', 'author_id', 'political_leaning', 'tweet_count',
                        'avg_views', 'avg_likes', 'avg_replies', 'avg_retweets',
                        'max_views', 'total_views'
                    ]].copy()
                    
                    display_influencers.columns = [
                        'Username', 'Author ID', 'Political Leaning', 'Tweet Count',
                        'Avg Views', 'Avg Likes', 'Avg Replies', 'Avg Retweets',
                        'Max Views', 'Total Views'
                    ]
                    
                    st.dataframe(
                        display_influencers,
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Calculate and display correlation matrix
                    st.markdown("### Cross-Correlation Matrix")
                    st.markdown("Correlation between influencers based on their performance metrics (avg views, likes, replies, retweets)")
                    
                    with st.spinner("Calculating correlation matrix..."):
                        correlation_matrix = analyzer.calculate_influencer_correlation(influencers_df)
                        
                        if not correlation_matrix.empty:
                            # Display correlation matrix
                            st.dataframe(
                                correlation_matrix.round(3),
                                use_container_width=True
                            )
                            
                            # Download buttons
                            col_dl1, col_dl2 = st.columns(2)
                            with col_dl1:
                                csv_influencers = influencers_df.to_csv(index=False).encode('utf-8')
                                st.download_button(
                                    label="📥 Download Influencers as CSV",
                                    data=csv_influencers,
                                    file_name=f"influencers_correlation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv"
                                )
                            with col_dl2:
                                csv_correlation = correlation_matrix.to_csv().encode('utf-8')
                                st.download_button(
                                    label="📥 Download Correlation Matrix as CSV",
                                    data=csv_correlation,
                                    file_name=f"correlation_matrix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv"
                                )
                        else:
                            st.warning("⚠️ Could not calculate correlation matrix")
                    
                elif not influencers_df.empty and len(influencers_df) < 2:
                    st.warning(f"⚠️ Found only {len(influencers_df)} influencer(s). Need at least 2 for correlation analysis.")
                else:
                    st.warning(f"⚠️ No influencers found with tweets having {corr_min_views:,}+ views in the last {corr_hours} hours")
        
        # Display stored correlation results
        if 'correlation_influencers' in st.session_state and not st.session_state.correlation_influencers.empty:
            influencers_df = st.session_state.correlation_influencers
            
            if len(influencers_df) >= 2:
                st.markdown("---")
                st.markdown("### Current Correlation Analysis Results")
                
                # Recalculate correlation if needed
                correlation_matrix = analyzer.calculate_influencer_correlation(influencers_df)
                
                if not correlation_matrix.empty:
                    st.dataframe(
                        correlation_matrix.round(3),
                        use_container_width=True
                    )
    
    st.markdown("---")
    
    # File uploader
    st.subheader("📂 Upload Influencers CSV")
    uploaded_file = st.file_uploader(
        "Upload a CSV file with influencer usernames", 
        type=['csv'],
        help="CSV should have a column with 'author_username' or 'username'"
    )
    
    if uploaded_file:
        try:
            df_influencers = pd.read_csv(uploaded_file)
            st.success(f"✅ Loaded {len(df_influencers)} influencers")
            
            # Try to find the username column
            username_col = None
            if 'author_username' in df_influencers.columns:
                username_col = 'author_username'
            elif 'username' in df_influencers.columns:
                username_col = 'username'
            else:
                st.error("❌ Please ensure your CSV has a column named 'author_username' or 'username'")
                st.stop()
            
            # Display loaded data preview
            st.subheader("📋 Loaded Influencers")
            st.dataframe(df_influencers[[username_col]].head(20), use_container_width=True)
            
            # Analysis options
            st.markdown("---")
            st.subheader("🔍 Analysis Options")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                num_to_analyze = st.slider(
                    "How many influencers to analyze?", 
                    1, 
                    len(df_influencers), 
                    min(10, len(df_influencers))
                )
            
            with col2:
                analyze_all = st.checkbox("Analyze all influencers", value=False)
            
            # Get selected usernames
            if analyze_all:
                selected_usernames = df_influencers[username_col].tolist()
            else:
                selected_usernames = df_influencers[username_col].head(num_to_analyze).tolist()
            
            # Two buttons: Analyze and Find Missing
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                analyze_clicked = st.button("🔍 Analyze Selected Influencers", type="primary")
            with col_btn2:
                find_missing_clicked = st.button("🔎 Find Influencers with No Data", type="secondary")
            
            # Analyze button
            if analyze_clicked:
                with st.spinner(f"Analyzing {len(selected_usernames)} influencers..."):
                    results = analyzer.analyze_multiple_influencers(selected_usernames)
                    
                    # Display results
                    st.markdown("---")
                    st.subheader("📈 Analysis Results")
                    
                    # Show summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Samples", f"{results['sample_count'].sum():,}")
                    with col2:
                        st.metric("Max Likes", f"{results['max_likes'].max():,}")
                    with col3:
                        st.metric("Max Views", f"{results['max_views'].max():,}")
                    with col4:
                        st.metric("Max Retweets", f"{results['max_retweets'].max():,}")
                    
                    # Display detailed results table
                    st.markdown("### Detailed Results")
                    st.dataframe(
                        results.sort_values('max_likes', ascending=False),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Download results
                    csv_results = results.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Results as CSV",
                        data=csv_results,
                        file_name=f"influencer_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
            
            # Find missing influencers button
            if find_missing_clicked:
                with st.spinner(f"Analyzing all {len(df_influencers)} influencers to find missing data..."):
                    # Analyze ALL influencers to find those with no data
                    all_results = analyzer.analyze_multiple_influencers(df_influencers[username_col].tolist())
                    
                    # Filter for sample_count = 0
                    missing_data = all_results[all_results['sample_count'] == 0].copy()
                    
                    # Display results
                    st.markdown("---")
                    st.subheader("⚠️ Influencers with No Data (sample_count = 0)")
                    
                    if len(missing_data) > 0:
                        st.warning(f"Found {len(missing_data)} influencers with no data in the database!")
                        
                        # Display the missing influencers
                        st.dataframe(
                            missing_data,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Download missing data CSV
                        csv_missing = missing_data.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download Missing Data List as CSV",
                            data=csv_missing,
                            file_name=f"influencers_no_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.success("✅ All influencers have data in the database!")
                    
        except Exception as e:
            st.error(f"Error processing file: {e}")
            st.exception(e)
    
    else:
        st.info("👆 Upload a CSV file to get started with influencer analysis")

except Exception as e:
    st.error(f"An error occurred: {e}")
    st.exception(e)

finally:
    # Cleanup
    if 'db_adapter' in st.session_state:
        pass  # Keep connection alive for session