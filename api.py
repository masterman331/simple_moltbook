import logging
from flask import request, jsonify
from flask_restful import Resource, reqparse
import uuid
import hashlib
import hmac
from functools import wraps

from rich.logging import RichHandler

from models import db, Agent, Post, Comment, Community
from config import API_KEY_LENGTH
from settings import SETTINGS # Import new settings

# Set up logging with RichHandler
log = logging.getLogger("rich")

# Helper for agent authentication
def authenticate_agent(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        if not api_key:
            log.warning("Authentication failed: X-API-KEY header missing.")
            return {'message': 'X-API-KEY header missing'}, 401
        
        agent = Agent.query.filter_by(api_key=api_key).first()
        if not agent:
            log.warning("Authentication failed: Invalid API Key provided (redacted).")
            return {'message': 'Invalid API Key'}, 401
        
        request.agent = agent # Attach agent to request object
        log.info(f"Agent '{agent.name}' (ID: {agent.id}) authenticated successfully.")
        return func(*args, **kwargs)
    return wrapper

def register_api_resources(api, limiter):
    class AgentRegistration(Resource):
        @limiter.limit(SETTINGS.RATE_LIMITS.get("AgentRegistration", SETTINGS.DEFAULT_RATE_LIMIT))
        def post(self):
            if not SETTINGS.ALLOW_AGENT_REGISTRATION:
                return {'message': 'Agent registration is currently disabled.'}, 503

            parser = reqparse.RequestParser()
            parser.add_argument('name', type=str, required=True, help='Agent name is required')
            args = parser.parse_args()

            agent_name = args['name']
            log.info(f"Attempting to register agent: {agent_name}")

            if Agent.query.filter_by(name=agent_name).first():
                log.warning(f"Agent registration failed: Agent with name '{agent_name}' already exists.")
                return {'message': 'Agent with this name already exists'}, 400

            # Generate a unique API key
            api_key = str(uuid.uuid4()).replace('-', '')[:API_KEY_LENGTH] # Simple truncation for length control

            new_agent = Agent(name=agent_name, api_key=api_key)
            db.session.add(new_agent)
            db.session.commit()

            log.info(f"Agent '{agent_name}' registered successfully with ID: {new_agent.id}")
            return {
                'message': 'Agent registered successfully',
                'agent_id': new_agent.id,
                'agent_name': new_agent.name,
                'api_key': new_agent.api_key
            }, 201

    class CommunityList(Resource):
        def get(self):
            communities = Community.query.all()
            return jsonify([{'name': community.name, 'description': community.description} for community in communities])

        @authenticate_agent
        def post(self):
            parser = reqparse.RequestParser()
            parser.add_argument('name', type=str, required=True, help='Community name is required')
            parser.add_argument('description', type=str, required=False, help='Community description')
            args = parser.parse_args()

            if Community.query.filter_by(name=args['name']).first():
                return {'message': 'Community with this name already exists'}, 400

            new_community = Community(name=args['name'], description=args.get('description'))
            db.session.add(new_community)
            db.session.commit()

            return {'message': 'Community created successfully', 'name': new_community.name}, 201

    class CommunityDetail(Resource):
        def get(self, community_name):
            community = Community.query.filter_by(name=community_name).first_or_404()
            posts = Post.query.filter_by(community_id=community.id).order_by(Post.created_at.desc()).all()
            return jsonify({
                'name': community.name,
                'description': community.description,
                'posts': [{
                    'id': post.id,
                    'title': post.title,
                    'author_name': post.author.name,
                    'created_at': post.created_at.isoformat()
                } for post in posts]
            })

    class PostList(Resource):
        def get(self):
            parser = reqparse.RequestParser()
            parser.add_argument('limit', type=int, default=SETTINGS.DEFAULT_POST_LIMIT, location='args')
            parser.add_argument('offset', type=int, default=0, location='args')
            parser.add_argument('sort', type=str, default='newest', choices=('newest', 'trending', 'random'), location='args')
            parser.add_argument('community', type=str, location='args')
            args = parser.parse_args()

            limit = min(args['limit'], SETTINGS.MAX_POST_LIMIT)
            query = Post.query

            if args['community']:
                community = Community.query.filter_by(name=args['community']).first()
                if community:
                    query = query.filter_by(community_id=community.id)
                else:
                    return {'message': 'Community not found'}, 404

            if args['sort'] == 'trending':
                posts = query.order_by(Post.score.desc()).offset(args['offset']).limit(limit).all()
            elif args['sort'] == 'random':
                posts = Post.get_random(limit=limit)
            else: # newest
                posts = query.order_by(Post.created_at.desc()).offset(args['offset']).limit(limit).all()

            log.info(f"Retrieved {len(posts)} posts with limit={limit}, offset={args['offset']}, sort={args['sort']}, community={args['community']}.")
            return jsonify([{
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'author_name': post.author.name,
                'community_name': post.community.name if post.community else None,
                'created_at': post.created_at.isoformat(),
                'view_count': post.view_count,
                'upvotes': post.upvotes,
                'downvotes': post.downvotes,
                'score': post.score
            } for post in posts])

        @authenticate_agent
        @limiter.limit(SETTINGS.RATE_LIMITS.get("PostList_post", SETTINGS.DEFAULT_RATE_LIMIT))
        def post(self):
            parser = reqparse.RequestParser()
            parser.add_argument('title', type=str, required=True, help='Post title is required')
            parser.add_argument('content', type=str, required=True, help='Post content is required')
            parser.add_argument('community_name', type=str, required=False, help='Name of the community to post to')
            args = parser.parse_args()
            
            community = None
            if args['community_name']:
                community = Community.query.filter_by(name=args['community_name']).first()
                if not community:
                    return {'message': 'Community not found'}, 404

            new_post = Post(
                title=args['title'], 
                content=args['content'], 
                agent_id=request.agent.id,
                community_id=community.id if community else None
            )
            db.session.add(new_post)
            db.session.commit()
            new_post.update_score()
            db.session.commit()

            log.info(f"[bold green]New Post Created:[/bold green] '{new_post.title}' by {request.agent.name}")
            return {
                'message': 'Post created successfully',
                'post_id': new_post.id,
                'title': new_post.title,
                'author_name': request.agent.name,
                'community_name': community.name if community else None
            }, 201

    class PostDetail(Resource):
        def get(self, post_id):
            post = Post.query.get(post_id)
            if not post:
                log.warning(f"Attempted to access non-existent post with ID: {post_id}")
                return {'message': 'Post not found'}, 404
            
            post.view_count += 1
            post.update_score()
            db.session.commit()
            log.info(f"Post '{post.title}' (ID: {post_id}) view count incremented to {post.view_count}.")

            def comment_to_dict(comment):
                return {
                    'id': comment.id,
                    'content': comment.content,
                    'author_name': comment.comment_author.name,
                    'created_at': comment.created_at.isoformat(),
                    'upvotes': comment.upvotes,
                    'downvotes': comment.downvotes,
                    'parent_comment_id': comment.parent_comment_id,
                    'replies': [comment_to_dict(reply) for reply in comment.replies]
                }

            top_level_comments = [comment_to_dict(c) for c in post.comments if c.parent_comment_id is None]

            return jsonify({
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'author_name': post.author.name,
                'community_name': post.community.name if post.community else None,
                'created_at': post.created_at.isoformat(),
                'view_count': post.view_count,
                'upvotes': post.upvotes,
                'downvotes': post.downvotes,
                'score': post.score,
                'comments': top_level_comments
            })

    class TrendingPosts(Resource):
        def get(self):
            parser = reqparse.RequestParser()
            parser.add_argument('limit', type=int, default=SETTINGS.DEFAULT_POST_LIMIT, location='args')
            parser.add_argument('offset', type=int, default=0, location='args')
            args = parser.parse_args()

            limit = min(args['limit'], SETTINGS.MAX_POST_LIMIT)

            posts = Post.get_trending(limit=limit) 
            posts = posts[args['offset']:] 

            return jsonify([{
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'author_name': post.author.name,
                'community_name': post.community.name if post.community else None,
                'created_at': post.created_at.isoformat(),
                'view_count': post.view_count,
                'upvotes': post.upvotes,
                'downvotes': post.downvotes,
                'score': post.score
            } for post in posts])

    class SearchPosts(Resource):
        def get(self):
            parser = reqparse.RequestParser()
            parser.add_argument('q', type=str, required=True, help='Search query is required', location='args')
            parser.add_argument('limit', type=int, default=SETTINGS.DEFAULT_POST_LIMIT, location='args')
            parser.add_argument('offset', type=int, default=0, location='args')
            args = parser.parse_args()

            limit = min(args['limit'], SETTINGS.MAX_POST_LIMIT)

            posts = Post.search(args['q'], limit=limit) 
            posts = posts[args['offset']:] 

            return jsonify([{
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'author_name': post.author.name,
                'community_name': post.community.name if post.community else None,
                'created_at': post.created_at.isoformat(),
                'view_count': post.view_count,
                'upvotes': post.upvotes,
                'downvotes': post.downvotes,
                'score': post.score
            } for post in posts])

    class CommentList(Resource):
        @authenticate_agent
        @limiter.limit(SETTINGS.RATE_LIMITS.get("CommentList_post", SETTINGS.DEFAULT_RATE_LIMIT))
        def post(self, post_id):
            if not SETTINGS.ALLOW_COMMENTS:
                return {'message': 'Comment creation is currently disabled.'}, 503
            
            parser = reqparse.RequestParser()
            parser.add_argument('content', type=str, required=True, help='Comment content is required')
            parser.add_argument('parent_comment_id', type=int, help='ID of the parent comment if this is a reply')
            args = parser.parse_args()

            post = Post.query.get(post_id)
            if not post:
                log.warning(f"Comment creation failed: Post with ID {post_id} not found.")
                return {'message': 'Post not found'}, 404
            
            parent_comment = None
            if args['parent_comment_id']:
                parent_comment = Comment.query.get(args['parent_comment_id'])
                if not parent_comment or parent_comment.post_id != post_id:
                    log.warning(f"Comment creation failed: Parent comment with ID {args['parent_comment_id']} not found or does not belong to post {post_id}.")
                    return {'message': 'Parent comment not found or does not belong to this post'}, 400

            new_comment = Comment(
                content=args['content'], 
                agent_id=request.agent.id, 
                post_id=post.id,
                parent_comment_id=args['parent_comment_id']
            )
            db.session.add(new_comment)
            db.session.commit()
            post.update_score()
            db.session.commit()

            log.info(f"[bold blue]New Comment Added:[/bold blue] by {request.agent.name} on post '{post.title}'")
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
            if not SETTINGS.ALLOW_VOTING:
                return {'message': 'Voting is currently disabled.'}, 503
            
            parser = reqparse.RequestParser()
            parser.add_argument('type', type=str, choices=('upvote', 'downvote'), required=True, help='Vote type (upvote or downvote) is required')
            args = parser.parse_args()

            post = Post.query.get(post_id)
            if not post:
                log.warning(f"Post voting failed: Post with ID {post_id} not found.")
                return {'message': 'Post not found'}, 404
            
            if args['type'] == 'upvote':
                post.upvotes += 1
                log.info(f"Agent '{request.agent.name}' (ID: {request.agent.id}) upvoted post (ID: {post.id}). New upvote count: {post.upvotes}")
            elif args['type'] == 'downvote':
                post.downvotes += 1
                log.info(f"Agent '{request.agent.name}' (ID: {request.agent.id}) downvoted post (ID: {post.id}). New downvote count: {post.downvotes}")
            
            post.update_score()
            db.session.commit()
            return {'message': 'Post {}d successfully'.format(args["type"]), 'post_id': post.id, 'upvotes': post.upvotes, 'downvotes': post.downvotes}, 200

    class CommentVote(Resource):
        @authenticate_agent
        def post(self, comment_id):
            if not SETTINGS.ALLOW_VOTING:
                return {'message': 'Voting is currently disabled.'}, 503
            
            parser = reqparse.RequestParser()
            parser.add_argument('type', type=str, choices=('upvote', 'downvote'), required=True, help='Vote type (upvote or downvote) is required')
            args = parser.parse_args()

            comment = Comment.query.get(comment_id)
            if not comment:
                log.warning(f"Comment voting failed: Comment with ID {comment_id} not found.")
                return {'message': 'Comment not found'}, 404
            
            if args['type'] == 'upvote':
                comment.upvotes += 1
                log.info(f"Agent '{request.agent.name}' (ID: {request.agent.id}) upvoted comment (ID: {comment.id}). New upvote count: {comment.upvotes}")
            elif args['type'] == 'downvote':
                comment.downvotes += 1
                log.info(f"Agent '{request.agent.name}' (ID: {request.agent.id}) downvoted comment (ID: {comment.id}). New downvote count: {comment.downvotes}")
            
            db.session.commit()
            comment.post.update_score()
            db.session.commit()
            return {'message': 'Comment {}d successfully'.format(args["type"]), 'comment_id': comment.id, 'upvotes': comment.upvotes, 'downvotes': comment.downvotes}, 200

    api.add_resource(AgentRegistration, '/api/agents/register')
    api.add_resource(CommunityList, '/api/communities')
    api.add_resource(CommunityDetail, '/api/communities/<string:community_name>')
    api.add_resource(PostList, '/api/posts')
    api.add_resource(PostDetail, '/api/posts/<int:post_id>')
    api.add_resource(TrendingPosts, '/api/posts/trending')
    api.add_resource(SearchPosts, '/api/search')
    api.add_resource(CommentList, '/api/posts/<int:post_id>/comments')
    api.add_resource(PostVote, '/api/posts/<int:post_id>/vote')
    api.add_resource(CommentVote, '/api/comments/<int:comment_id>/vote')