from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session, Response, stream_with_context
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import os
import uuid
import threading
import queue
import json
import time
from werkzeug.utils import secure_filename
import EmailFinderUsingClaude
from models import db, User

# Detect cloud deployment (Handshake Playwright features disabled in cloud)
IS_CLOUD = bool(os.environ.get('RENDER') or os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('SPACE_ID'))

if not IS_CLOUD:
    import HandshakeDMAutomation
    import HandshakeJobApply

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here-change-in-production')

# Check if running on Hugging Face Spaces (persistent storage at /data)
if os.environ.get('SPACE_ID'):
    # HF Spaces: use /data for persistent storage
    data_dir = '/data'
    os.makedirs(data_dir, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = f'{data_dir}/uploads'
    app.config['RESUMES_FOLDER'] = f'{data_dir}/user_resumes'
    app.config['TRANSCRIPTS_FOLDER'] = f'{data_dir}/user_transcripts'
    database_url = f'sqlite:///{data_dir}/users.db'
else:
    # Local development or cloud (Render/Railway)
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['RESUMES_FOLDER'] = 'user_resumes'
    app.config['TRANSCRIPTS_FOLDER'] = 'user_transcripts'
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
    # Railway/Render PostgreSQL uses postgres:// but SQLAlchemy needs postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Create directories if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESUMES_FOLDER'], exist_ok=True)
os.makedirs(app.config['TRANSCRIPTS_FOLDER'], exist_ok=True)
os.makedirs('generated_cover_letters', exist_ok=True)

# Store progress queues for SSE
progress_queues = {}

# Store login confirmation flags for Handshake campaigns
handshake_login_confirmed = {}

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return db.session.get(User, int(user_id))

@app.context_processor
def utility_processor():
    """Add utility functions to Jinja2 templates."""
    def get_original_resume_name(user):
        """Get the original name of the current resume."""
        if not user.resume_filename:
            return ''

        resumes = user.get_resumes_list()
        for resume in resumes:
            if resume.get('stored_filename') == user.resume_filename:
                return resume.get('original_name', user.resume_filename)

        # If not found in list, extract from stored filename
        # Format: user_{id}_{original_name}.pdf
        parts = user.resume_filename.split('_', 2)
        if len(parts) >= 3:
            return parts[2]
        return user.resume_filename

    return dict(get_original_resume_name=get_original_resume_name, is_cloud=IS_CLOUD)

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
@login_required
def index():
    """Render the main dashboard form for logged-in users."""
    return render_template('dashboard.html', user=current_user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        if not username or not email or not password:
            flash('All fields are required', 'error')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))

        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return redirect(url_for('register'))

        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))

        # Create new user
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username/Email and password are required', 'error')
            return redirect(url_for('login'))

        # Try to find user by username OR email
        user = User.query.filter((User.username == username) | (User.email == username)).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username/email or password', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Handle user settings page."""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        sender_email = request.form.get('sender_email', '').strip()
        sender_password = request.form.get('sender_password', '').strip()

        # Verify current password
        if not current_password:
            flash('Current password is required to make changes', 'error')
            return redirect(url_for('settings'))

        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'error')
            return redirect(url_for('settings'))

        # Update login password if provided
        if new_password:
            if len(new_password) < 6:
                flash('New password must be at least 6 characters long', 'error')
                return redirect(url_for('settings'))

            if new_password != confirm_password:
                flash('New passwords do not match', 'error')
                return redirect(url_for('settings'))

            current_user.set_password(new_password)
            flash('Login password updated successfully', 'success')

        # Update email credentials
        if sender_email:
            current_user.sender_email = sender_email
        if sender_password:
            current_user.sender_password = sender_password

        db.session.commit()
        flash('Settings updated successfully', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', user=current_user)

@app.route('/contacts')
@login_required
def contacts():
    """Serve the contact history page with all contacted people."""
    return render_template('contacts.html', user=current_user)

@app.route('/submit', methods=['POST'])
@login_required
def submit():
    """Handle form submission and trigger the email workflow."""

    # Get form inputs
    location = request.form.get('location', '').strip()
    industry = request.form.get('industry', '').strip()
    num_emails = request.form.get('num_emails', '5').strip()
    custom_message = request.form.get('custom_message', '').strip()
    sender_email = request.form.get('sender_email', '').strip()
    sender_password = request.form.get('sender_password', '').strip()

    # Validate inputs
    if not location or not industry:
        return jsonify({'error': 'Location and industry are required'}), 400

    if not sender_email or not sender_password:
        return jsonify({'error': 'Email credentials are required'}), 400

    try:
        num_emails = int(num_emails)
        if num_emails < 1 or num_emails > 50:
            return jsonify({'error': 'Number of emails must be between 1 and 50'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid number of emails'}), 400

    # Handle resume upload (if provided) or use existing
    resume_path = None
    if 'resume' in request.files and request.files['resume'].filename != '':
        resume_file = request.files['resume']

        if not allowed_file(resume_file.filename):
            return jsonify({'error': 'Only PDF files are allowed for resume'}), 400

        # Get the original filename
        original_filename = secure_filename(resume_file.filename)

        # Generate unique filename using timestamp to avoid duplicates
        import time
        timestamp = int(time.time() * 1000)  # milliseconds
        filename = f"user_{current_user.id}_{timestamp}_{original_filename}"
        resume_path = os.path.join(app.config['RESUMES_FOLDER'], filename)
        resume_file.save(resume_path)

        # Add to user's resumes list
        current_user.add_resume(original_filename, filename)

        # Update user's resume filename in database
        current_user.resume_filename = filename
    else:
        # Use existing resume
        if current_user.resume_filename:
            resume_path = os.path.join(app.config['RESUMES_FOLDER'], current_user.resume_filename)
        else:
            return jsonify({'error': 'Please upload a resume'}), 400

    # Save user preferences to database
    current_user.location = location
    
    
    
    
    current_user.industry = industry
    current_user.num_emails = num_emails
    current_user.custom_message = custom_message
    current_user.sender_email = sender_email
    current_user.sender_password = sender_password
    db.session.commit()

    # Create a unique task ID and queue for this workflow
    task_id = str(uuid.uuid4())
    progress_queue = queue.Queue()
    progress_queues[task_id] = progress_queue

    # Capture user_id before starting thread (current_user won't be available in thread)
    user_id = current_user.id

    # Run workflow in background thread
    def run_workflow():
        try:
            # Get user from database (current_user is not available in background threads)
            with app.app_context():
                user = db.session.get(User, user_id)
                if not user:
                    progress_queue.put({
                        'message': 'Error: User not found',
                        'type': 'error',
                        'complete': True
                    })
                    return

                # Get user's email history
                user_emails_sent = set(user.get_emails_sent())
                user_domains_contacted = user.get_contacted_domains()

                # Execute the email workflow with user preferences and progress callback
                results = EmailFinderUsingClaude.main(
                    sender_email=sender_email,
                    sender_password=sender_password,
                    user_id=user_id,
                    user_emails_sent=user_emails_sent,
                    user_domains_contacted=user_domains_contacted,
                    resume_path=resume_path,
                    location=location,
                    industry=industry,
                    num_emails=num_emails,
                    custom_message=custom_message,
                    progress_callback=lambda msg, msg_type='in-progress', count=None: progress_queue.put({
                        'message': msg,
                        'type': msg_type,
                        'email_count': count
                    })
                )

                # Update user's sent email history
                emails_sent = results.get("emails_sent", [])
                contacts_data = results.get("contacts_data", [])

                if emails_sent:
                    user.add_sent_emails(emails_sent)

                # Update user's detailed contact history
                if contacts_data:
                    user.add_contact_history(contacts_data)

                db.session.commit()

                # Send final success message
                success_count = results.get("successful", 0)
                failed_count = results.get("failed", 0)
                progress_queue.put({
                    'message': f'Campaign completed! Sent {success_count} emails successfully. Failed: {failed_count}',
                    'type': 'success',
                    'email_count': success_count,
                    'complete': True
                })

        except Exception as e:
            progress_queue.put({
                'message': f'Error: {str(e)}',
                'type': 'error',
                'complete': True
            })

    thread = threading.Thread(target=run_workflow)
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': task_id})

@app.route('/progress/<task_id>')
@login_required
def progress(task_id):
    """Server-Sent Events endpoint for progress updates."""

    def generate():
        if task_id not in progress_queues:
            yield f"data: {json.dumps({'message': 'Invalid task ID', 'type': 'error', 'complete': True})}\n\n"
            return

        progress_queue = progress_queues[task_id]

        while True:
            try:
                # Wait for new progress updates with timeout
                update = progress_queue.get(timeout=30)
                yield f"data: {json.dumps(update)}\n\n"

                # If workflow is complete, clean up and exit
                if update.get('complete'):
                    del progress_queues[task_id]
                    break

            except queue.Empty:
                # Send keepalive message
                yield f"data: {json.dumps({'message': 'Processing...', 'type': 'in-progress'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'message': f'Error: {str(e)}', 'type': 'error', 'complete': True})}\n\n"
                break

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/submit_handshake', methods=['POST'])
@login_required
def submit_handshake():
    """Handle Handshake DM campaign submission."""
    if IS_CLOUD:
        return jsonify({'error': 'Handshake automation is not available in cloud deployment'}), 404

    # Get form inputs
    city = request.form.get('city', '').strip()
    num_dms = request.form.get('num_dms', '10').strip()
    custom_message = request.form.get('custom_message', '').strip()
    desired_job_field = request.form.get('desired_job_field', '').strip()
    filter_internships_only = request.form.get('filter_internships_only', 'false').lower() == 'true'

    # Convert internship filter to job_type parameter (3 = internships in Handshake)
    job_type = 3 if filter_internships_only else None

    # Validate inputs
    if not city or not desired_job_field:
        return jsonify({'error': 'City and industry/field are required'}), 400

    try:
        num_dms = int(num_dms)
        if num_dms < 1 or num_dms > 50:
            return jsonify({'error': 'Number of DMs must be between 1 and 50'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid number of DMs'}), 400

    # Get resume path (use existing resume)
    resume_path = None
    if current_user.resume_filename:
        resume_path = os.path.join(app.config['RESUMES_FOLDER'], current_user.resume_filename)
    else:
        return jsonify({'error': 'Please upload a resume first in the Email Campaign tab'}), 400

    # Save user preferences to database (no credentials stored)
    current_user.handshake_city = city
    current_user.handshake_num_dms = num_dms
    db.session.commit()

    # Create a unique task ID and queue for this workflow
    task_id = str(uuid.uuid4())
    progress_queue = queue.Queue()
    progress_queues[task_id] = progress_queue

    # Initialize login confirmation flag for this task
    handshake_login_confirmed[task_id] = False

    # Capture user_id before starting thread
    user_id = current_user.id

    # Run workflow in background thread
    def run_handshake_workflow():
        try:
            # Get user from database
            with app.app_context():
                user = db.session.get(User, user_id)
                if not user:
                    progress_queue.put({
                        'message': 'Error: User not found',
                        'type': 'error',
                        'complete': True
                    })
                    return

                # Get user's Handshake DM history
                user_companies_contacted = user.get_handshake_contacted_companies()

                # Execute the Handshake DM workflow
                results = HandshakeDMAutomation.main(
                    city=city,
                    num_dms=num_dms,
                    desired_job_field=desired_job_field,  # Now required, not optional
                    user_resume_path=resume_path,
                    custom_message=custom_message,
                    user_companies_contacted=user_companies_contacted,
                    progress_callback=lambda msg, msg_type='in-progress', count=None: progress_queue.put({
                        'message': msg,
                        'type': msg_type,
                        'dm_count': count,
                        'task_id': task_id  # Include task_id for login button
                    }),
                    login_confirmed_callback=lambda: handshake_login_confirmed.get(task_id, False),
                    job_type=job_type
                )

                # Update user's Handshake DM history
                messages_sent = results.get("messages_sent", [])

                if messages_sent:
                    user.add_handshake_dm_history(messages_sent)
                    db.session.commit()

                # Send final success message
                successful = results.get("successful_dms", 0)
                failed = results.get("failed_dms", 0)
                skipped = results.get("skipped", 0)

                progress_queue.put({
                    'message': f'Handshake campaign completed! Sent {successful} DMs. Skipped: {skipped}, Failed: {failed}',
                    'type': 'success',
                    'dm_count': successful,
                    'complete': True
                })

        except Exception as e:
            progress_queue.put({
                'message': f'Error: {str(e)}',
                'type': 'error',
                'complete': True
            })
        finally:
            # Clean up login confirmation flag
            if task_id in handshake_login_confirmed:
                del handshake_login_confirmed[task_id]

    thread = threading.Thread(target=run_handshake_workflow)
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': task_id})

@app.route('/api/handshake_applications')
@login_required
def api_handshake_applications():
    """API endpoint to get Handshake job applications history as JSON."""
    if IS_CLOUD:
        return jsonify({'error': 'Handshake automation is not available in cloud deployment'}), 404
    applications_history = current_user.get_handshake_applications_history()
    # Filter out None entries and sort by applied_date descending (most recent first)
    applications_history = [app for app in applications_history if app is not None and isinstance(app, dict)]
    applications_history.sort(key=lambda x: x.get('applied_date', ''), reverse=True)
    return jsonify(applications_history)

@app.route('/confirm_handshake_login/<task_id>', methods=['POST'])
@login_required
def confirm_handshake_login(task_id):
    """Handle Handshake login confirmation from user."""
    if IS_CLOUD:
        return jsonify({'error': 'Handshake automation is not available in cloud deployment'}), 404
    if task_id in handshake_login_confirmed:
        handshake_login_confirmed[task_id] = True
        return jsonify({'status': 'success', 'message': 'Login confirmed'})
    else:
        return jsonify({'status': 'error', 'message': 'Invalid task ID'}), 400

@app.route('/submit_job_application', methods=['POST'])
@login_required
def submit_job_application():
    """Handle Handshake job application session submission."""
    if IS_CLOUD:
        return jsonify({'error': 'Handshake automation is not available in cloud deployment'}), 404

    # Get form inputs
    industry = request.form.get('industry', '').strip()
    location = request.form.get('location', '').strip()
    role = request.form.get('role', '').strip()

    # Validate inputs
    if not location or not role:
        return jsonify({'error': 'Location and role are required'}), 400

    # Check if transcript is uploaded (REQUIRED)
    if not current_user.transcript_filename:
        return jsonify({'error': 'Transcript is required for job applications. Please upload your transcript in the Documents tab first.'}), 400

    # Get resume path (use existing resume)
    resume_path = None
    if current_user.resume_filename:
        resume_path = os.path.join(app.config['RESUMES_FOLDER'], current_user.resume_filename)
    else:
        return jsonify({'error': 'Please upload a resume first in the Email Campaign tab'}), 400

    # Create a unique task ID and queue for this workflow
    task_id = str(uuid.uuid4())
    progress_queue = queue.Queue()
    progress_queues[task_id] = progress_queue

    # Initialize login confirmation flag for this task
    handshake_login_confirmed[task_id] = False

    # Capture user_id before starting thread
    user_id = current_user.id

    # Run workflow in background thread
    def run_job_application_workflow():
        try:
            # Get user from database
            with app.app_context():
                user = db.session.get(User, user_id)
                if not user:
                    progress_queue.put({
                        'message': 'Error: User not found',
                        'type': 'error',
                        'complete': True
                    })
                    return

                # Get resume path
                resume_path = None
                if user.resume_filename:
                    resume_path = os.path.join(app.config['RESUMES_FOLDER'], user.resume_filename)

                # Execute the Handshake job application workflow
                results = HandshakeJobApply.main(
                    industry=industry,
                    location=location,
                    role=role,
                    progress_callback=lambda msg, msg_type='in-progress': progress_queue.put({
                        'message': msg,
                        'type': msg_type,
                        'task_id': task_id  # Include task_id for login button
                    }),
                    login_confirmed_callback=lambda: handshake_login_confirmed.get(task_id, False),
                    resume_path=resume_path,
                    user_id=user_id
                )

                # Send final message
                if results.get("login_successful"):
                    progress_queue.put({
                        'message': results.get("message", "Session completed successfully"),
                        'type': 'success',
                        'complete': True
                    })
                else:
                    progress_queue.put({
                        'message': results.get("message", "Session failed"),
                        'type': 'error',
                        'complete': True
                    })

        except Exception as e:
            progress_queue.put({
                'message': f'Error: {str(e)}',
                'type': 'error',
                'complete': True
            })
        finally:
            # Clean up login confirmation flag
            if task_id in handshake_login_confirmed:
                del handshake_login_confirmed[task_id]

    thread = threading.Thread(target=run_job_application_workflow)
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': task_id})

@app.route('/api/upload_resume', methods=['POST'])
@login_required
def upload_resume():
    """Handle standalone resume upload."""
    try:
        if 'resume' not in request.files:
            return jsonify({'error': 'No resume file provided'}), 400

        resume_file = request.files['resume']

        if resume_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(resume_file.filename):
            return jsonify({'error': 'Only PDF files are allowed'}), 400

        # Get the original filename
        original_filename = secure_filename(resume_file.filename)

        # Generate unique filename using timestamp to avoid duplicates
        import time
        timestamp = int(time.time() * 1000)  # milliseconds
        stored_filename = f"user_{current_user.id}_{timestamp}_{original_filename}"
        resume_path = os.path.join(app.config['RESUMES_FOLDER'], stored_filename)
        resume_file.save(resume_path)

        # Add to user's resumes list
        current_user.add_resume(original_filename, stored_filename)

        # Don't automatically set as current resume - user can choose later
        # If this is the first resume, set it as current
        if not current_user.resume_filename:
            current_user.resume_filename = stored_filename

        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Resume uploaded successfully',
            'filename': original_filename,
            'stored_filename': stored_filename
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/view_resume')
@login_required
def view_resume():
    """Get current resume information."""
    if current_user.resume_filename:
        resume_path = os.path.join(app.config['RESUMES_FOLDER'], current_user.resume_filename)
        if os.path.exists(resume_path):
            # Get file size in MB
            file_size = os.path.getsize(resume_path) / (1024 * 1024)

            # Find the original name from resumes list
            resumes = current_user.get_resumes_list()
            original_name = current_user.resume_filename
            for resume in resumes:
                if resume.get('stored_filename') == current_user.resume_filename:
                    original_name = resume.get('original_name', current_user.resume_filename)
                    break

            return jsonify({
                'status': 'success',
                'has_resume': True,
                'filename': original_name,
                'stored_filename': current_user.resume_filename,
                'file_size': f"{file_size:.2f} MB",
                'upload_date': 'N/A'  # Could track this in DB if needed
            })

    return jsonify({
        'status': 'success',
        'has_resume': False
    })

@app.route('/download_resume')
@login_required
def download_resume():
    """Download the user's current resume."""
    if not current_user.resume_filename:
        flash('No resume uploaded yet', 'error')
        return redirect(url_for('index'))

    resume_path = os.path.join(app.config['RESUMES_FOLDER'], current_user.resume_filename)

    if not os.path.exists(resume_path):
        flash('Resume file not found', 'error')
        return redirect(url_for('index'))

    from flask import send_file
    return send_file(resume_path, as_attachment=True, download_name=current_user.resume_filename)

@app.route('/api/resumes_list')
@login_required
def resumes_list():
    """Get list of all user resumes."""
    resumes = current_user.get_resumes_list()

    # Enrich with file size information
    for resume in resumes:
        resume_path = os.path.join(app.config['RESUMES_FOLDER'], resume['stored_filename'])
        if os.path.exists(resume_path):
            file_size = os.path.getsize(resume_path) / (1024 * 1024)
            resume['file_size'] = f"{file_size:.2f} MB"
            resume['exists'] = True
        else:
            resume['exists'] = False
            resume['file_size'] = 'N/A'

    return jsonify({
        'status': 'success',
        'resumes': resumes,
        'current_resume': current_user.resume_filename
    })

@app.route('/api/set_current_resume', methods=['POST'])
@login_required
def set_current_resume():
    """Set a resume as the current active resume."""
    try:
        data = request.get_json()
        stored_filename = data.get('stored_filename')

        if not stored_filename:
            return jsonify({'error': 'No resume filename provided'}), 400

        # Verify the resume exists in user's list
        resumes = current_user.get_resumes_list()
        resume_exists = any(r['stored_filename'] == stored_filename for r in resumes)

        if not resume_exists:
            return jsonify({'error': 'Resume not found'}), 404

        # Set as current resume
        current_user.resume_filename = stored_filename
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Current resume updated successfully'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_resume', methods=['POST'])
@login_required
def delete_resume():
    """Delete a specific resume."""
    try:
        data = request.get_json()
        stored_filename = data.get('stored_filename')

        if not stored_filename:
            return jsonify({'error': 'No resume filename provided'}), 400

        resume_path = os.path.join(app.config['RESUMES_FOLDER'], stored_filename)

        # Delete file if it exists
        if os.path.exists(resume_path):
            os.remove(resume_path)

        # Remove from user's resumes list
        current_user.remove_resume(stored_filename)

        # If this was the current resume, clear it
        if current_user.resume_filename == stored_filename:
            current_user.resume_filename = ''

        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Resume deleted successfully'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload_transcript', methods=['POST'])
@login_required
def upload_transcript():
    """Handle transcript upload (replaces existing transcript)."""
    try:
        if 'transcript' not in request.files:
            return jsonify({'error': 'No transcript file provided'}), 400

        transcript_file = request.files['transcript']

        if transcript_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(transcript_file.filename):
            return jsonify({'error': 'Only PDF files are allowed'}), 400

        # Get the original filename
        original_filename = secure_filename(transcript_file.filename)

        # Generate unique filename using timestamp
        import time
        timestamp = int(time.time() * 1000)  # milliseconds
        stored_filename = f"user_{current_user.id}_{timestamp}_{original_filename}"
        transcript_path = os.path.join(app.config['TRANSCRIPTS_FOLDER'], stored_filename)

        # Delete old transcript if exists
        if current_user.transcript_filename:
            old_transcript_path = os.path.join(app.config['TRANSCRIPTS_FOLDER'], current_user.transcript_filename)
            if os.path.exists(old_transcript_path):
                try:
                    os.remove(old_transcript_path)
                except:
                    pass  # Ignore if file can't be deleted

        # Save new transcript
        transcript_file.save(transcript_path)

        # Update user's transcript filename
        current_user.transcript_filename = stored_filename
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Transcript uploaded successfully',
            'filename': original_filename,
            'stored_filename': stored_filename
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/view_transcript')
@login_required
def view_transcript():
    """Get current transcript information."""
    if current_user.transcript_filename:
        transcript_path = os.path.join(app.config['TRANSCRIPTS_FOLDER'], current_user.transcript_filename)
        if os.path.exists(transcript_path):
            # Get file size in MB
            file_size = os.path.getsize(transcript_path) / (1024 * 1024)

            # Extract original name from stored filename
            # Format: user_{id}_{timestamp}_{original_name}.pdf
            parts = current_user.transcript_filename.split('_', 3)
            original_name = parts[3] if len(parts) >= 4 else current_user.transcript_filename

            return jsonify({
                'status': 'success',
                'has_transcript': True,
                'filename': original_name,
                'stored_filename': current_user.transcript_filename,
                'file_size': f"{file_size:.2f} MB"
            })

    return jsonify({
        'status': 'success',
        'has_transcript': False
    })

@app.route('/download_transcript')
@login_required
def download_transcript():
    """Download the user's current transcript."""
    if not current_user.transcript_filename:
        flash('No transcript uploaded yet', 'error')
        return redirect(url_for('index'))

    transcript_path = os.path.join(app.config['TRANSCRIPTS_FOLDER'], current_user.transcript_filename)

    if not os.path.exists(transcript_path):
        flash('Transcript file not found', 'error')
        return redirect(url_for('index'))

    from flask import send_file
    return send_file(transcript_path, as_attachment=True, download_name=current_user.transcript_filename)

@app.route('/api/delete_transcript', methods=['POST'])
@login_required
def delete_transcript():
    """Delete the user's transcript."""
    try:
        if not current_user.transcript_filename:
            return jsonify({'error': 'No transcript to delete'}), 400

        transcript_path = os.path.join(app.config['TRANSCRIPTS_FOLDER'], current_user.transcript_filename)

        # Delete file if it exists
        if os.path.exists(transcript_path):
            os.remove(transcript_path)

        # Clear transcript filename
        current_user.transcript_filename = ''
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Transcript deleted successfully'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Create database tables on import (needed for gunicorn which doesn't run __main__)
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    import sys

    print("Database tables created successfully!")

    # Get port from environment (HF Spaces uses 7860, others may set PORT)
    port = int(os.environ.get('PORT', 7860))

    # Check if running on cloud platform
    if os.environ.get('SPACE_ID'):
        # Hugging Face Spaces
        print(f"Starting application on Hugging Face Spaces (port {port})...")
        from waitress import serve
        serve(app, host='0.0.0.0', port=port)
    elif os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER'):
        # Railway or Render
        print(f"Starting application in CLOUD mode with Waitress on port {port}...")
        from waitress import serve
        serve(app, host='0.0.0.0', port=port)
    elif '--development' in sys.argv:
        # Use Flask development server with debug mode
        print("Starting application in DEVELOPMENT mode with Flask debug server...")
        print("Auto-reload enabled.")
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        # Local production mode with Waitress
        print(f"Starting application in PRODUCTION mode with Waitress on port 5000...")
        print("Press CTRL+C to quit")
        from waitress import serve
        serve(app, host='127.0.0.1', port=5000)
