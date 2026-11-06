import os

import pandas as pd
import streamlit as st
from pymongo import MongoClient


@st.cache_resource
def get_mongo_client():
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    return MongoClient(uri, serverSelectionTimeoutMS=5000)

def load_data():
    try:
        client = get_mongo_client()
        db = client[os.environ.get("MONGO_DB", "fraud_db")]
        coll = db[os.environ.get("MONGO_COLLECTION", "transactions")]
        client.admin.command('ping')
        cursor = coll.find().sort("processed_at", -1).limit(10000)
        data = list(cursor)
        if not data:
            return pd.DataFrame(), 0
        df = pd.DataFrame(data)
        total_docs = coll.estimated_document_count()
        return df, total_docs
    except Exception as e:
        st.error(f"⚠️ **MongoDB Connection Error:** {e}")
        return None, 0
