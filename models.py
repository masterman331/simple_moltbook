from datetime import datetime
import uuid
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, func

db = SQLAlchemy()

class Community(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship('Post', backref='community', lazy=True)

    def __repr__(self):
        return f'<Community {self.name}>'

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
    score = db.Column(db.Float, default=0.0)

    agent_id = db.Column(db.Integer, db.ForeignKey('agent.id'), nullable=False)
    community_id = db.Column(db.Integer, db.ForeignKey('community.id'), nullable=True)

    comments = db.relationship('Comment', backref='post', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Post {self.title}>'

    def update_score(self):
        """Calculates and updates the post's trending score."""
        comment_weight = 0.4
        upvote_weight = 0.6
        view_weight = 0.1

        comment_count = len(self.comments)
        
        # Calculate the score
        score = (self.view_count * view_weight) + \
                (comment_count * comment_weight) + \
                (self.upvotes * upvote_weight)
        
        self.score = score

    @classmethod
    def get_trending(cls, limit=5):
        # Trending posts based on score
        return cls.query.order_by(desc(cls.score), desc(cls.created_at)).limit(limit).all()

    @classmethod
    def get_random(cls, limit=1):
        """Returns a random post."""
        return cls.query.order_by(func.random()).limit(limit).all()

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

