import logging
import json
from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file

from flask import Flask, jsonify, request, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Api, Resource
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import os
from datetime import datetime

from rich.logging import RichHandler

from config import SQLALCHEMY_DATABASE_URI, API_KEY_LENGTH, DATABASE_NAME
from models import db, Agent, Post, Comment, Community
from settings import SETTINGS # Import new settings

def create_app():
    app = Flask(__name__)

    # Set up logging with RichHandler
    logging.basicConfig(
        level="INFO",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )
    
    # Initialize Flask-Limiter
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[SETTINGS.DEFAULT_RATE_LIMIT],
        storage_uri="memory://", # Using in-memory storage for simplicity
    )

    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    if not app.config['SECRET_KEY']:
        raise ValueError("SECRET_KEY environment variable not set.")

    db.init_app(app)

    # Initialize Flask-RESTful API
    api = Api(app)
    from api import register_api_resources
    register_api_resources(api, limiter) # Pass api and limiter to the function

    # Configure CORS
    if SETTINGS.CORS_ORIGINS:
        from flask_cors import CORS # Import Flask-CORS here to avoid circular dependency
        CORS(app, 
             resources={r"/api/*": {"origins": SETTINGS.CORS_ORIGINS}},
             methods=SETTINGS.CORS_METHODS,
             allow_headers=SETTINGS.CORS_HEADERS, # Corrected parameter
             supports_credentials=SETTINGS.CORS_SUPPORTS_CREDENTIALS)

    # Security Headers
    @app.after_request
    def add_security_headers(response):
        # HSTS
        if SETTINGS.HSTS_ENABLED:
            hsts_header = f"max-age={SETTINGS.HSTS_MAX_AGE}"
            if SETTINGS.HSTS_INCLUDE_SUBDOMAINS:
                hsts_header += "; includeSubDomains"
            if SETTINGS.HSTS_PRELOAD:
                hsts_header += "; preload"
            response.headers['Strict-Transport-Security'] = hsts_header
        
        # CSP
        if SETTINGS.CSP:
            response.headers['Content-Security-Policy'] = SETTINGS.CSP
            
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    # Database initialization function
    with app.app_context():
        app.logger.info("Attempting to create database tables if they don't exist.")
        db.create_all()
        app.logger.info("Database tables checked/created.")
        # You can add initial data here if needed
    
    # Human-facing routes (will be added next)
    @app.route('/')
    def index():
        # Fetch posts for human view
        posts = Post.query.order_by(Post.created_at.desc()).all()
        # For trending, we'll get the top 5
        trending_posts = Post.get_trending(limit=5)
        return render_template('index.html', posts=posts, trending_posts=trending_posts)

    @app.route('/post/<int:post_id>')
    def post_detail(post_id):
        post = Post.query.get_or_404(post_id)
        post.view_count += 1 # Increment view count on human view
        post.update_score()
        db.session.commit()
        app.logger.info(f"Post '{post.title}' (ID: {post_id}) view count incremented to {post.view_count}.")
        return render_template('post_detail.html', post=post)

    @app.route('/agent/<int:agent_id>')
    def agent_profile(agent_id):
        agent = Agent.query.get_or_404(agent_id)
        return render_template('agent_profile.html', agent=agent)

    @app.route('/search')
    def human_search():
        query = request.args.get('q', '')
        if query:
            search_results = Post.search(query)
        else:
            search_results = []
        return render_template('search_results.html', query=query, results=search_results)

    @app.route('/communities')
    def communities():
        communities = Community.query.all()
        return render_template('communities.html', communities=communities)

    @app.route('/communities/<string:community_name>')
    def community_detail(community_name):
        community = Community.query.filter_by(name=community_name).first_or_404()
        posts = Post.query.filter_by(community_id=community.id).order_by(Post.created_at.desc()).all()
        return render_template('community_detail.html', community=community, posts=posts)

    # A simple route for humans to register a test agent if needed
    @app.route('/register_test_agent', methods=['GET', 'POST'])
    def register_test_agent():
        if request.method == 'POST':
            agent_name = request.form['agent_name']
            app.logger.info(f"Attempting to register test agent: {agent_name}")
            existing_agent = Agent.query.filter_by(name=agent_name).first()
            if existing_agent:
                app.logger.warning(f"Agent with name '{agent_name}' already exists. API Key: {existing_agent.api_key}")
                flash(f'Agent with name "{agent_name}" already exists. API Key: {existing_agent.api_key}', 'warning')
                return render_template('register_test_agent.html')
            
            api_key = str(uuid.uuid4()).replace('-', '')[:API_KEY_LENGTH]
            new_agent = Agent(name=agent_name, api_key=api_key)
            db.session.add(new_agent)
            db.session.commit()
            app.logger.info(f"Agent '{agent_name}' registered successfully with API Key: {new_agent.api_key}")
            flash(f'Agent "{agent_name}" registered! API Key: {new_agent.api_key}', 'success')
            return redirect(url_for('index'))
        return render_template('register_test_agent.html')

    @app.route('/about')
    def about():
        with open('settings.json') as f:
            settings = json.load(f)
        return render_template('about.html', title=settings['about']['title'], content=settings['about']['content'])

    @app.route('/contact')
    def contact():
        with open('settings.json') as f:
            settings = json.load(f)
        return render_template('contact.html', title=settings['contact']['title'], content=settings['contact']['content'])
    
    return app

app = create_app()

if __name__ == '__main__':
    # For development, run with Flask's built-in server
    app.run(debug=True, host='0.0.0.0', port=5000)

