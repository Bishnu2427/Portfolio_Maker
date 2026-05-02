from datetime import datetime
from bson import ObjectId
from app.extensions import mongo


class Portfolio:
    COLLECTION = 'portfolios'

    @staticmethod
    def create(data):
        doc = {
            'session_id': data.get('session_id'),
            'style': data.get('style', 'professional'),
            'status': 'uploading',
            'cv_text': '',
            'cv_data': {},
            'user_prompt': data.get('user_prompt', ''),
            'photo_path': data.get('photo_path', ''),
            'cv_path': data.get('cv_path', ''),
            'upload_dir': '',
            'portfolio_dir': '',
            'port': None,
            'pid': None,
            'github_url': '',
            'pages_url': '',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }
        result = mongo.db[Portfolio.COLLECTION].insert_one(doc)
        doc['_id'] = result.inserted_id
        return doc

    @staticmethod
    def get_by_id(portfolio_id):
        try:
            return mongo.db[Portfolio.COLLECTION].find_one({'_id': ObjectId(portfolio_id)})
        except Exception:
            return None

    @staticmethod
    def update(portfolio_id, data):
        data['updated_at'] = datetime.utcnow()
        try:
            mongo.db[Portfolio.COLLECTION].update_one(
                {'_id': ObjectId(portfolio_id)},
                {'$set': data}
            )
        except Exception:
            pass

    @staticmethod
    def get_by_session(session_id):
        return list(
            mongo.db[Portfolio.COLLECTION].find(
                {'session_id': session_id},
                sort=[('created_at', -1)]
            )
        )
