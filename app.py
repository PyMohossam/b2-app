from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import qrcode
import os
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
import cv2
import numpy as np
from datetime import datetime, timedelta
import pdfkit
from flask import make_response






# إعداد Flask و SQLAlchemy
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Replace with a real secret key




# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///default.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}  # Allowed file extensions for upload
db = SQLAlchemy(app)

# Define the User table
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    table_number = db.Column(db.String(100), nullable=False)
    people = db.Column(db.Integer, nullable=False)
    males = db.Column(db.Integer, nullable=False)
    females = db.Column(db.Integer, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    date = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

class UserLogin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Define relationship with User model
    user = db.relationship('User', backref=db.backref('logins', lazy=True))
    


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error=error), 500


# Ensure the database is created
with app.app_context():
    db.create_all()

# Default username and password
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'admin'

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == DEFAULT_USERNAME and password == DEFAULT_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))  # Redirect to the homepage
        else:
            flash("الاسم أو كلمة المرور غير صحيحة، يرجى المحاولة مرة أخرى.", 'error')

    return render_template('login.html')

# Authentication check before access
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))  # Redirect to login if not logged in
        return f(*args, **kwargs)
    return decorated_function

# Index route (home page)
@app.route('/')
@login_required
def index():
    return render_template('index.html')




# Sign Up Route - Updated to use custom date
@app.route('/sign_up', methods=['GET', 'POST'])
def sign_up():
    qr_code_url = None  # To store the QR code URL
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form['name']
            table_number = request.form['table_number']
            people = int(request.form['people'])
            males = int(request.form['males'])
            females = int(request.form['females'])
            phone = request.form['phone']
            
            # Get custom date from form (new)
            custom_date = request.form.get('custom_date')
            # If no custom date provided, use current date
            if not custom_date:
                custom_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                # Append time to the date
                custom_date = f"{custom_date} {datetime.now().strftime('%H:%M:%S')}"
            
            # Validate gender counts
            if males + females != people:
                flash("عدد الذكور والإناث يجب أن يساوي عدد الأشخاص", 'error')
                return redirect(url_for('sign_up'))

            # Check if phone already exists
            existing_user = User.query.filter_by(phone=phone).first()
            if existing_user:
                flash("رقم الهاتف مسجل مسبقاً", 'error')
                return redirect(url_for('sign_up'))

            # Create new user with custom date
            new_user = User(
                name=name,
                table_number=table_number,
                people=people,
                males=males,
                females=females,
                phone=phone,
                date=custom_date,  # Use custom date here
                password_hash=generate_password_hash(phone)
            )

            db.session.add(new_user)
            db.session.commit()

            # Generate QR Code with phone number (or any other data)
            qr_data = phone  # Use phone number or any other data you want in QR code
            img = qrcode.make(qr_data)

            # Save QR code in static/uploads directory
            uploads_folder = os.path.join('static', 'uploads')
            if not os.path.exists(uploads_folder):
                os.makedirs(uploads_folder)

            qr_code_path = os.path.join(uploads_folder, f'qr_{phone}.png')
            img.save(qr_code_path)

            # Set qr_code_url to send the image path to the template
            qr_code_url = url_for('static', filename=f'uploads/qr_{phone}.png')

            flash("تم التسجيل بنجاح!", 'success')
            return render_template('sign_up.html', qr_code=qr_code_url)

        except ValueError:
            flash("الرجاء إدخال أرقام صحيحة", 'error')
        except Exception as e:
            db.session.rollback()
            flash(f"حدث خطأ أثناء التسجيل: {str(e)}", 'error')

    return render_template('sign_up.html', qr_code=qr_code_url)

# Sign In Route - Updated to use custom date
@app.route('/sign_in', methods=['GET', 'POST'])
def sign_in():
    if request.method == 'POST':
        # Check if the user uploaded a file
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)

        # Check if the file has an allowed extension
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # Ensure upload folder exists
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
                
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Get custom login date (new)
            custom_login_date = request.form.get('custom_login_date')
            if custom_login_date:
                try:
                    # Parse the custom date
                    login_time = datetime.strptime(custom_login_date, '%Y-%m-%d')
                    # Set time to current time
                    current_time = datetime.now().time()
                    login_time = login_time.replace(hour=current_time.hour, minute=current_time.minute, second=current_time.second)
                except ValueError:
                    flash("تنسيق التاريخ غير صحيح، يرجى استخدام YYYY-MM-DD", 'error')
                    return redirect(url_for('sign_in'))
            else:
                # Use current date and time if no custom date provided
                login_time = datetime.now()

            # Decode the QR code from the uploaded image
            user_id = decode_qr_code(filepath)
            if user_id:
                user = User.query.filter_by(phone=user_id).first()
                if user:
                    # Record login event with custom date
                    login_record = UserLogin(user_id=user.id, login_time=login_time)
                    db.session.add(login_record)
                    try:
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        flash(f"Error recording login: {str(e)}", 'error')
                    
                    session['logged_in'] = True
                    session['user_name'] = user.name  # Store user name in session
                    session['user_phone'] = user.phone  # Store user phone in session
                    flash(f"مرحباً {user.name}! تم تسجيل الدخول بنجاح.", 'success')
                    return redirect(url_for('index'))  # User logged in, redirect to home
                else:
                    flash("لم يتم العثور على المستخدم.", 'error')
                    return redirect(url_for('sign_in'))
            else:
                flash("لم يتم التعرف على الرمز في الصورة", 'error')
                return redirect(url_for('sign_in'))
        else:
            flash('Invalid file format. Only images are allowed.', 'error')
            return redirect(request.url)

    return render_template('upload_qr.html')






# Function to decode the QR code from an image
def decode_qr_code(filepath):
    """
    Decode QR code from an image using OpenCV
    """
    try:
        # Read the image
        img = cv2.imread(filepath)
        
        # Initialize QR Code detector
        qr_detector = cv2.QRCodeDetector()
        
        # Detect and decode
        data, bbox, straight_qrcode = qr_detector.detectAndDecode(img)
        
        if data:
            return data
        return None
    except Exception as e:
        print(f"Error decoding QR code: {str(e)}")
        return None

# Check if the uploaded file is an allowed image
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/view_users', methods=['GET', 'POST'])
@login_required
def view_users():
    try:
        # Default date range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Format for display in the form
        default_start = start_date.strftime('%Y-%m-%d')
        default_end = end_date.strftime('%Y-%m-%d')
        
        # If the form was submitted, get the date range from the form
        if request.method == 'POST':
            start_date_str = request.form.get('start_date', default_start)
            end_date_str = request.form.get('end_date', default_end)
            
            try:
                # Parse the dates
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                end_date = end_date.replace(hour=23, minute=59, second=59)
            except ValueError:
                flash("تنسيق التاريخ غير صحيح، يرجى استخدام YYYY-MM-DD", 'error')
                return redirect(url_for('view_users'))
        
        # Get the date strings in the format they're stored in the database
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # Use simpler LIKE filtering which is less prone to errors
        # This will filter records where the date string starts with anything between start_date and end_date
        users = User.query.filter(
            User.date >= start_date_str,
            User.date <= end_date_str + ' 23:59:59'
        ).all()
        
        if not users:
            flash("لا يوجد زوار مسجلين في هذه الفترة.", 'info')
            
        return render_template(
            'view_users.html', 
            users=users, 
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
    except Exception as e:
        flash(f"حدث خطأ أثناء جلب البيانات: {str(e)}", 'error')
        return redirect(url_for('index'))    
# Logout route
@app.route('/logout')
@login_required
def logout():
    session.pop('logged_in', None)  # Remove the logged_in flag from the session
    flash("تم تسجيل الخروج بنجاح.", 'success')
    return redirect(url_for('login'))


# Update the view_logged_in_users route to include date filtering
@app.route('/view_logged_in_users', methods=['GET', 'POST'])
@login_required
def view_logged_in_users():
    try:
        # Default date range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Format for display in the form
        default_start = start_date.strftime('%Y-%m-%d')
        default_end = end_date.strftime('%Y-%m-%d')
        
        # If the form was submitted, get the date range from the form
        if request.method == 'POST':
            start_date_str = request.form.get('start_date', default_start)
            end_date_str = request.form.get('end_date', default_end)
            
            try:
                # Parse the dates
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                # Set end_date to the end of the day
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                end_date = end_date.replace(hour=23, minute=59, second=59)
            except ValueError:
                flash("تنسيق التاريخ غير صحيح، يرجى استخدام YYYY-MM-DD", 'error')
                return redirect(url_for('view_logged_in_users'))
        
        # Get all login records with user information within the date range
        login_records = db.session.query(
            UserLogin, User
        ).join(
            User, UserLogin.user_id == User.id
        ).filter(
            UserLogin.login_time >= start_date,
            UserLogin.login_time <= end_date
        ).order_by(
            UserLogin.login_time.desc()
        ).all()
        
        return render_template(
            'view_logged_in_users.html', 
            login_records=login_records,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
    except Exception as e:
        flash(f"حدث خطأ أثناء جلب بيانات تسجيل الدخول: {str(e)}", 'error')
        return redirect(url_for('index'))
    















# You'll need to install these dependencies
# pip install pdfkit
# Also install wkhtmltopdf: https://wkhtmltopdf.org/downloads.html



# Route to generate a PDF report of users
@app.route('/print_users_report', methods=['GET'])
@login_required
def print_users_report():
    try:
        # Get date range from query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # Default to last 30 days if no dates provided
        if not start_date_str or not end_date_str:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
        
        # Parse the dates
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        end_date = end_date.replace(hour=23, minute=59, second=59)
        
        # Use the same filtering logic as in view_users
        # This is the Python-based filtering method
        all_users = User.query.all()
        users = []
        
        for user in all_users:
            try:
                user_date = datetime.strptime(user.date, '%Y-%m-%d %H:%M:%S')
                if start_date <= user_date <= end_date:
                    users.append(user)
            except ValueError:
                continue
        
        # Generate HTML for the report
        html = render_template(
            'print_users_report.html', 
            users=users, 
            start_date=start_date_str,
            end_date=end_date_str
        )
        
        # Convert HTML to PDF
        pdf = pdfkit.from_string(html, False)
        
        # Create response
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=users_report_{start_date_str}_to_{end_date_str}.pdf'
        
        return response
        
    except Exception as e:
        flash(f"حدث خطأ أثناء إنشاء التقرير: {str(e)}", 'error')
        return redirect(url_for('view_users'))

# Route to generate a PDF report of logged-in users
@app.route('/print_logins_report', methods=['GET'])
@login_required
def print_logins_report():
    try:
        # Get date range from query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # Default to last 30 days if no dates provided
        if not start_date_str or not end_date_str:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
        
        # Parse the dates
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        end_date = end_date.replace(hour=23, minute=59, second=59)
        
        # Get all login records with user information within the date range
        login_records = db.session.query(
            UserLogin, User
        ).join(
            User, UserLogin.user_id == User.id
        ).filter(
            UserLogin.login_time >= start_date,
            UserLogin.login_time <= end_date
        ).order_by(
            UserLogin.login_time.desc()
        ).all()
        
        # Generate HTML for the report
        html = render_template(
            'print_logins_report.html', 
            login_records=login_records,
            start_date=start_date_str,
            end_date=end_date_str
        )
        
        # Convert HTML to PDF
        pdf = pdfkit.from_string(html, False)
        
        # Create response
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=logins_report_{start_date_str}_to_{end_date_str}.pdf'
        
        return response
        
    except Exception as e:
        flash(f"حدث خطأ أثناء إنشاء التقرير: {str(e)}", 'error')
        return redirect(url_for('view_logged_in_users'))
    

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
