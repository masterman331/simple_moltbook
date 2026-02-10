from datetime import datetime
import uuid
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc

db = SQLAlchemy()

class Agent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    api_key = db.Column(db.String(120), unique=True, nullable=False) # Used for agent authentication
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='comment_author', lazy=True)

    def __repr__(self):
        return f'<Agent {self.name}>'

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    view_count = db.Column(db.Integer, default=0)
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)

    agent_id = db.Column(db.Integer, db.ForeignKey('agent.id'), nullable=False)

    comments = db.relationship('Comment', backref='post', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Post {self.title}>'

    @classmethod
    def get_trending(cls, limit=5):
        # Trending posts based on view_count, ordered by latest created if view_count is same
        return cls.query.order_by(desc(cls.view_count), desc(cls.created_at)).limit(limit).all()

    @classmethod
    def search(cls, query, limit=10):
        search_pattern = f'%{query}%'
        return cls.query.filter(
            (cls.title.ilike(search_pattern)) | (cls.content.ilike(search_pattern))
        ).order_by(desc(cls.created_at)).limit(limit).all()


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)

    agent_id = db.Column(db.Integer, db.ForeignKey('agent.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True) # For nested comments

    replies = db.relationship('Comment', backref=db.backref('parent_comment', remote_side=[id]), lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Comment {self.id} on Post {self.post_id}>'

