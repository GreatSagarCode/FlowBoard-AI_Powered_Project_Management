from app.ml.inference import predict_task, predict_project
from datetime import timedelta


class MLService:
    @staticmethod
    def suggest_for_project(title: str, description: str = '') -> dict:
        text = f"{title} {description}".strip()
        prediction = predict_project(text)

        from datetime import datetime
        suggested_date = (datetime.utcnow() + timedelta(days=prediction['duration_days'])).strftime('%Y-%m-%d')

        return {
            'category': prediction['category'],
            'priority': prediction['priority'],
            'duration_days': prediction['duration_days'],
            'suggested_description': prediction['suggested_description'],
            'suggested_date': suggested_date,
        }

    @staticmethod
    def suggest_for_task(title: str, description: str = '') -> dict:
        text = f"{title} {description}".strip()
        return predict_task(text)
