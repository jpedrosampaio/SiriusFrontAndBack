"""Shared study-plan serialization without importing HTTP routes."""
def entry_json(row):
    return {'entry_id':str(row.id),'notebook_id':str(row.notebook_id),'date':row.date.isoformat(),'name':row.name,
        'minutes':row.minutes,'kind':row.kind,'completed':row.completed,'manual':row.manual,'fixed':row.fixed,'reason':row.reason,
        'topic_id': str(row.topic_id) if row.topic_id else None, 'topic_key': getattr(row, 'strategy_topic_key', None)}
