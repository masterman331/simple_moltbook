from flask import request, jsonify
from flask_restful import Resource, reqparse
import uuid
import hashlib
import hmac
from functools import wraps

from models import db, Agent, Post, Comment
from config import API_KEY_LENGTH

# Helper for agent authentication
def authenticate_agent(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        if not api_key:
            return {'message': 'X-API-KEY header missing'}, 401
        
        agent = Agent.query.filter_by(api_key=api_key).first()
        if not agent:
            return {'message': 'Invalid API Key'}, 401
        
        request.agent = agent # Attach agent to request object
        return func(*args, **kwargs)
    return wrapper

class AgentRegistration(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str, required=True, help='Agent name is required')
        args = parser.parse_args()

        if Agent.query.filter_by(name=args['name']).first():
            return {'message': 'Agent with this name already exists'}, 400

        # Generate a unique API key
        api_key = str(uuid.uuid4()).replace('-', '')[:API_KEY_LENGTH] # Simple truncation for length control

        new_agent = Agent(name=args['name'], api_key=api_key)
        db.session.add(new_agent)
        db.session.commit()

        return {
            'message': 'Agent registered successfully',
            'agent_id': new_agent.id,
            'agent_name': new_agent.name,
            'api_key': new_agent.api_key
        }, 201

class PostList(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('limit', type=int, default=10, help='Limit the number of posts returned', location='args')
        parser.add_argument('offset', type=int, default=0, help='Offset for pagination', location='args')
        args = parser.parse_args()

        posts = Post.query.order_by(Post.created_at.desc()).offset(args['offset']).limit(args['limit']).all()
        return jsonify([{
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'author_name': post.author.name,
            'created_at': post.created_at.isoformat(),
            'view_count': post.view_count,
            'upvotes': post.upvotes,
            'downvotes': post.downvotes
        } for post in posts])

    @authenticate_agent
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('title', type=str, required=True, help='Post title is required')
        parser.add_argument('content', type=str, required=True, help='Post content is required')
        args = parser.parse_args()

        new_post = Post(title=args['title'], content=args['content'], agent_id=request.agent.id)
        db.session.add(new_post)
        db.session.commit()

        return {
            'message': 'Post created successfully',
            'post_id': new_post.id,
            'title': new_post.title,
            'author_name': request.agent.name
        }, 201

class PostDetail(Resource):
    def get(self, post_id):
        post = Post.query.get(post_id)
        if not post:
            return {'message': 'Post not found'}, 404
        
        post.view_count += 1
        db.session.commit()

        # Helper function to convert comments to a dict, including replies
        def comment_to_dict(comment):
            return {
                'id': comment.id,
                'content': comment.content,
                'author_name': comment.comment_author.name,
                'created_at': comment.created_at.isoformat(),
                'upvotes': comment.upvotes,
                'downvotes': comment.downvotes,
                'parent_comment_id': comment.parent_comment_id,
                'replies': [comment_to_dict(reply) for reply in comment.replies] # Recursive replies
            }

        # Get top-level comments (those without a parent_comment_id)
        top_level_comments = [comment_to_dict(c) for c in post.comments if c.parent_comment_id is None]


        return jsonify({
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'author_name': post.author.name,
            'created_at': post.created_at.isoformat(),
            'view_count': post.view_count,
            'upvotes': post.upvotes,
            'downvotes': post.downvotes,
            'comments': top_level_comments
        })

class TrendingPosts(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('limit', type=int, default=10, help='Limit the number of trending posts returned', location='args')
        parser.add_argument('offset', type=int, default=0, help='Offset for pagination', location='args')
        args = parser.parse_args()

        posts = Post.get_trending(limit=args['limit']) 
        posts = posts[args['offset']:] 

        return jsonify([{
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'author_name': post.author.name,
            'created_at': post.created_at.isoformat(),
            'view_count': post.view_count,
            'upvotes': post.upvotes,
            'downvotes': post.downvotes
        } for post in posts])

class SearchPosts(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('q', type=str, required=True, help='Search query is required', location='args')
        parser.add_argument('limit', type=int, default=10, help='Limit the number of search results returned', location='args')
        parser.add_argument('offset', type=int, default=0, help='Offset for pagination', location='args')
        args = parser.parse_args()

        posts = Post.search(args['q'], limit=args['limit']) 
        posts = posts[args['offset']:] 

        return jsonify([{
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'author_name': post.author.name,
            'created_at': post.created_at.isoformat(),
            'view_count': post.view_count,
            'upvotes': post.upvotes,
            'downvotes': post.downvotes
        } for post in posts])

class CommentList(Resource):
    @authenticate_agent
    def post(self, post_id):
        parser = reqparse.RequestParser()
        parser.add_argument('content', type=str, required=True, help='Comment content is required')
        parser.add_argument('parent_comment_id', type=int, help='ID of the parent comment if this is a reply')
        args = parser.parse_args()

        post = Post.query.get(post_id)
        if not post:
            return {'message': 'Post not found'}, 404
        
        parent_comment = None
        if args['parent_comment_id']:
            parent_comment = Comment.query.get(args['parent_comment_id'])
            if not parent_comment or parent_comment.post_id != post_id:
                return {'message': 'Parent comment not found or does not belong to this post'}, 400

        new_comment = Comment(
            content=args['content'], 
            agent_id=request.agent.id, 
            post_id=post.id,
            parent_comment_id=args['parent_comment_id']
        )
        db.session.add(new_comment)
        db.session.commit()

        return {
            'message': 'Comment added successfully',
            'comment_id': new_comment.id,
            'author_name': request.agent.name,
            'post_id': post.id,
            'parent_comment_id': new_comment.parent_comment_id
        }, 201

class PostVote(Resource):
    @authenticate_agent
    def post(self, post_id):
        parser = reqparse.RequestParser()
        parser.add_argument('type', type=str, choices=('upvote', 'downvote'), required=True, help='Vote type (upvote or downvote) is required')
        args = parser.parse_args()

        post = Post.query.get(post_id)
        if not post:
            return {'message': 'Post not found'}, 404
        
        if args['type'] == 'upvote':
            post.upvotes += 1
        elif args['type'] == 'downvote':
            post.downvotes += 1
        
        db.session.commit()
        return {'message': 'Post {}d successfully'.format(args["type"]), 'post_id': post.id, 'upvotes': post.upvotes, 'downvotes': post.downvotes}, 200

class CommentVote(Resource):
    @authenticate_agent
    def post(self, comment_id):
        parser = reqparse.RequestParser()
        parser.add_argument('type', type=str, choices=('upvote', 'downvote'), required=True, help='Vote type (upvote or downvote) is required')
        args = parser.parse_args()

        comment = Comment.query.get(comment_id)
        if not comment:
            return {'message': 'Comment not found'}, 404
        
        if args['type'] == 'upvote':
            comment.upvotes += 1
        elif args['type'] == 'downvote':
            comment.downvotes += 1
        
        db.session.commit()
        return {'message': 'Comment {}d successfully'.format(args["type"]), 'comment_id': comment.id, 'upvotes': comment.upvotes, 'downvotes': comment.downvotes}, 200
