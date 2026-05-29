from datetime import datetime
from app.extensions import mongo


class CVSection:
    COLLECTION = 'cv_sections'

    @staticmethod
    def store(portfolio_id: str, sections: dict):
        mongo.db[CVSection.COLLECTION].delete_many({'portfolio_id': portfolio_id})
        docs = [
            {
                'portfolio_id': portfolio_id,
                'section_type': stype,
                'raw_text': data.get('raw_text', ''),
                'parsed': data.get('parsed', {}),
                'created_at': datetime.utcnow(),
            }
            for stype, data in sections.items()
        ]
        if docs:
            mongo.db[CVSection.COLLECTION].insert_many(docs)

    @staticmethod
    def get(portfolio_id: str, section_type: str) -> dict:
        return mongo.db[CVSection.COLLECTION].find_one(
            {'portfolio_id': portfolio_id, 'section_type': section_type}
        ) or {}

    @staticmethod
    def get_all(portfolio_id: str) -> list:
        return list(mongo.db[CVSection.COLLECTION].find({'portfolio_id': portfolio_id}))
