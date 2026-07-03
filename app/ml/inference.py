import os
import joblib
from scipy.sparse import hstack
import scipy.sparse as sp

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE_DIR, 'Machine_Learning', 'models')

# Load models safely (lazy loading or global load)
task_classifier = None
priority_classifier = None
duration_predictor = None
duration_tfidf = None
le_cat = None
le_pri = None

def load_models():
    global task_classifier, priority_classifier, duration_predictor, duration_tfidf, le_cat, le_pri
    if task_classifier is None:
        try:
            task_classifier = joblib.load(os.path.join(MODELS_DIR, 'task_classifier.pkl'))
            priority_classifier = joblib.load(os.path.join(MODELS_DIR, 'priority_classifier.pkl'))
            duration_predictor = joblib.load(os.path.join(MODELS_DIR, 'duration_predictor.pkl'))
            duration_tfidf = joblib.load(os.path.join(MODELS_DIR, 'duration_tfidf.pkl'))
            le_cat = joblib.load(os.path.join(MODELS_DIR, 'label_encoder_category.pkl'))
            le_pri = joblib.load(os.path.join(MODELS_DIR, 'label_encoder_priority.pkl'))
        except Exception as e:
            print(f"Error loading models: {e}")

def predict_project(text: str) -> dict:
    load_models()
    
    if not task_classifier:
        return {
            'category': 'Task',
            'priority': 'Medium',
            'duration_days': 10,
            'suggested_description': 'Please provide more details.'
        }
        
    text_lower = text.lower()
    cat = task_classifier.predict([text_lower])[0]
    pri = priority_classifier.predict([text_lower])[0]
    
    text_tfidf = duration_tfidf.transform([text_lower])
    cat_enc = le_cat.transform([cat])[0]
    pri_enc = le_pri.transform([pri])[0]
    
    extra = sp.csr_matrix([[cat_enc, pri_enc]])
    combined = hstack([text_tfidf, extra])
    
    dur = max(10, int(round(duration_predictor.predict(combined)[0])))
    
    suggested_description = f"Project {cat} focused on {text[:60]}.\n\nThis project aims to deliver the specified requirements with a {pri} priority over an estimated {dur} days timeline. Key milestones include planning, execution, and review phases to ensure high-quality delivery."
    
    return {
        'category': cat,
        'priority': pri,
        'duration_days': dur,
        'suggested_description': suggested_description
    }

def predict_task(text: str) -> dict:
    load_models()
    
    if not task_classifier:
        # Fallback if models are not loaded
        return {
            'category': 'Task',
            'priority': 'Medium',
            'duration_days': 10,
            'suggested_description': '<p>Please provide more details.</p>'
        }
        
    text_lower = text.lower()
    
    cat = task_classifier.predict([text_lower])[0]
    pri = priority_classifier.predict([text_lower])[0]
    
    text_tfidf = duration_tfidf.transform([text_lower])
    cat_enc = le_cat.transform([cat])[0]
    pri_enc = le_pri.transform([pri])[0]
    
    extra = sp.csr_matrix([[cat_enc, pri_enc]])
    combined = hstack([text_tfidf, extra])
    
    dur = max(1, int(round(duration_predictor.predict(combined)[0])))
    
    suggested_description = (
        f"<h4>Objective</h4><p>Implement the {cat.lower()} related to: <strong>{text[:80]}...</strong></p>"
        f"<h4>Requirements</h4><ul><li>Gather detailed specifications.</li><li>Complete necessary technical or design steps.</li><li>Perform testing and QA.</li></ul>"
        f"<h4>Constraints</h4><p>Priority: {pri} | Estimated effort: {dur} days</p>"
    )
    
    return {
        'category': cat,
        'priority': pri,
        'duration_days': dur,
        'suggested_description': suggested_description
    }
