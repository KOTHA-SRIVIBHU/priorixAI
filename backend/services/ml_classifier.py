import os
import requests
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HF_API_TOKEN = os.getenv("HF_API_TOKEN")

# Models we'll use (free inference)
CLASSIFIER_MODEL = "facebook/bart-large-mnli"  # zero-shot classification
SUMMARIZER_MODEL = "facebook/bart-large-cnn"

def classify_with_ml(email_record: Dict[str, Any]) -> Dict[str, Any]:
    """Classify email using Hugging Face zero‑shot classification."""
    text = f"{email_record['subject']}\n{email_record['snippet']}"
    
    # Candidate labels
    candidate_labels = [
        "interview invitation",
        "deadline reminder",
        "selection notification",
        "job opportunity",
        "academic update",
        "promotion or spam"
    ]
    
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {
        "inputs": text,
        "parameters": {
            "candidate_labels": candidate_labels,
            "multi_label": False
        }
    }
    
    try:
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{CLASSIFIER_MODEL}",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        # Get the top label and score
        top_label = result['labels'][0]
        top_score = result['scores'][0]
        
        # Map to our categories
        category_map = {
            "interview invitation": "interview",
            "deadline reminder": "deadline",
            "selection notification": "selection",
            "job opportunity": "job",
            "academic update": "academic",
            "promotion or spam": "promotion"
        }
        category = category_map.get(top_label, "other")
        
        # Importance score from the model's confidence
        importance_score = top_score
        
        # Action required if score > 0.7 and category not promotion
        action_required = (importance_score > 0.7 and category != "promotion")
        
        return {
            "category": category,
            "importance_score": importance_score,
            "action_required": action_required,
            "method": "ml"
        }
    except Exception as e:
        logger.error(f"ML classification failed: {e}")
        # Fall back to rule-based (you can call your rule classifier here)
        return None

def summarize_with_ml(email_record: Dict[str, Any]) -> str:
    """Generate a summary using Hugging Face summarization."""
    text = f"Subject: {email_record['subject']}\n\n{email_record['snippet']}"
    # Truncate to 1024 tokens (max for BART)
    text = text[:1024]
    
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {
        "inputs": text,
        "parameters": {
            "max_length": 100,
            "min_length": 20,
            "do_sample": False
        }
    }
    
    try:
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{SUMMARIZER_MODEL}",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        summary = result[0]['summary_text']
        return summary
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        # Fallback to subject + snippet
        return f"{email_record['subject']} – {email_record['snippet'][:100]}..."