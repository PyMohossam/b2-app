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
import qrcode
from PIL import Image






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
# Modified User class with new serial_number field
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    table_number = db.Column(db.String(100), nullable=False)
    people = db.Column(db.Integer, nullable=False)
    males = db.Column(db.Integer, nullable=False)
    females = db.Column(db.Integer, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    serial_number = db.Column(db.String(50), unique=True, nullable=False)
    date = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    image_filename = db.Column(db.String(255))



class UserLogin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Define relationship with User model
    user = db.relationship('User', backref=db.backref('logins', lazy=True))

class UserImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Define relationship with User model
    user = db.relationship('User', backref=db.backref('images', lazy=True))


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

@app.route('/sign_up', methods=['GET', 'POST'])
def sign_up():
    qr_code_url = None
    uploads_folder = os.path.join('static', 'uploads')
    if not os.path.exists(uploads_folder):
        os.makedirs(uploads_folder)

    if request.method == 'POST':
        try:
            name = request.form['name']
            table_number = request.form['table_number']
            people = int(request.form['people'])
            males = int(request.form['males'])
            females = int(request.form['females'])
            phone = request.form['phone']
            serial_number = request.form.get('serial_number')

            custom_date = request.form.get('custom_date')
            if not custom_date:
                custom_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                custom_date = f"{custom_date} {datetime.now().strftime('%H:%M:%S')}"

            if males + females != people:
                flash("عدد الذكور والإناث يجب أن يساوي عدد الأشخاص", 'danger')
                return render_template('sign_up.html', qr_code=None)

            if not serial_number:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                serial_number = f"{timestamp}-{phone}"

            existing_serial = User.query.filter_by(serial_number=serial_number).first()
            if existing_serial:
                flash("الرقم التسلسلي مستخدم بالفعل، يرجى استخدام رقم آخر", 'danger')
                return render_template('sign_up.html', qr_code=None)

            new_user = User(
                name=name,
                table_number=table_number,
                people=people,
                males=males,
                females=females,
                phone=phone,
                serial_number=serial_number,
                date=custom_date,
                password_hash=generate_password_hash(phone),
                image_filename=None
            )

            db.session.add(new_user)
            db.session.commit()

            if 'user_images[]' in request.files:
                uploaded_files = request.files.getlist('user_images[]')
                images_folder = os.path.join('static', 'images')
                if not os.path.exists(images_folder):
                    os.makedirs(images_folder)

                for image_file in uploaded_files:
                    if image_file and image_file.filename != '':
                        secure_image_filename = secure_filename(image_file.filename)
                        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_image_filename}"
                        image_path = os.path.join(images_folder, unique_filename)
                        image_file.save(image_path)

                        new_image = UserImage(user_id=new_user.id, filename=unique_filename)
                        db.session.add(new_image)

                if uploaded_files and uploaded_files[0].filename != '':
                    first_image_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(uploaded_files[0].filename)}"
                    new_user.image_filename = first_image_filename
                    db.session.commit()


            # To this:
            qr_data = serial_number  # Use the user's unique serial number

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)

            qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

            logo_path = os.path.join('static', 'logo', 'B2.jpg')
            if os.path.exists(logo_path):
                logo = Image.open(logo_path)
                qr_width, qr_height = qr_img.size
                logo_size = int(qr_width / 4)
                logo = logo.resize((logo_size, logo_size))
                pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
                qr_img.paste(logo, pos)

            qr_code_path = os.path.join(uploads_folder, f'qr_{serial_number}.png')
            qr_img.save(qr_code_path)

            qr_code_url = url_for('static', filename=f'uploads/qr_{serial_number}.png')

            flash("تم التسجيل بنجاح! يمكنك الآن تحميل الـ QR Code", 'success')
            return render_template('sign_up.html', qr_code=qr_code_url)

        except ValueError as e:
            flash(f"الرجاء إدخال أرقام صحيحة: {str(e)}", 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f"حدث خطأ أثناء التسجيل: {str(e)}", 'danger')

    return render_template('sign_up.html', qr_code=qr_code_url)





@app.route('/sign_in', methods=['GET', 'POST'])
def sign_in():
    if request.method == 'POST':
        # Handle both camera scan and file upload
        serial_number = None
        
        if 'qr_result' in request.form:  # Camera scan
            serial_number = request.form['qr_result'].strip()
        elif 'file' in request.files:  # File upload
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(filepath)
                serial_number = decode_qr_code(filepath)
                os.remove(filepath)  # Clean up uploaded file

        # Validate QR data
        if not serial_number or len(serial_number) < 5:
            flash("رمز QR غير صالح", 'error')
            return redirect(url_for('upload_qr'))

        # Handle login date
        try:
            login_date = request.form.get('custom_login_date')
            login_time = datetime.strptime(login_date, '%Y-%m-%d') if login_date else datetime.now()
            if login_date:
                current_time = datetime.now().time()
                login_time = login_time.replace(hour=current_time.hour, minute=current_time.minute, second=current_time.second)
        except ValueError:
            flash("تاريخ غير صحيح", 'error')
            return redirect(url_for('upload_qr'))

        # Find user
        user = User.query.filter_by(serial_number=serial_number).first()
        if not user:
            flash("مستخدم غير موجود", 'error')
            return redirect(url_for('upload_qr'))

        # Check if user has already logged in today
        # Get start and end of the selected day
        start_of_day = login_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = login_time.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Check for existing login in this day
        existing_login = UserLogin.query.filter(
            UserLogin.user_id == user.id,
            UserLogin.login_time >= start_of_day,
            UserLogin.login_time <= end_of_day
        ).first()
        
        if existing_login:
            # User has already logged in today, just show their details
            flash(f"مرحباً {user.name}! تم تسجيل دخولك سابقاً اليوم في {existing_login.login_time.strftime('%H:%M:%S')}", 'info')
        else:
            # User hasn't logged in today, record the new login
            try:
                new_login = UserLogin(user_id=user.id, login_time=login_time)
                db.session.add(new_login)
                db.session.commit()
                flash(f"مرحباً {user.name}! تم تسجيل دخولك بنجاح", 'success')
            except Exception as e:
                db.session.rollback()
                flash(f"خطأ في التسجيل: {str(e)}", 'error')
                return redirect(url_for('upload_qr'))

        # Set session data
        session.update({
            'logged_in': True,
            'user_name': user.name,
            'user_phone': user.phone
        })

        # Prepare user data for display
        user_data = {
            'id': user.id,
            'name': user.name,
            'table_number': user.table_number,
            'people': user.people,
            'males': user.males,
            'females': user.females,
            'phone': user.phone,
            'serial_number': user.serial_number,
            'image_filename': user.image_filename
        }
        user_images = UserImage.query.filter_by(user_id=user.id).all()

        return render_template('user_details.html', user=user_data, user_images=user_images)

    return render_template('upload_qr.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form['name']
            phone = request.form['phone']
            email = request.form.get('email', '')
            age = request.form.get('age', None)
            gender = request.form.get('gender', 'male')
            
            # Basic validation
            if len(name) < 3:
                flash("الاسم يجب أن يتكون من 3 أحرف على الأقل", 'danger')
                return render_template('register.html')
            
            if len(phone) < 10:
                flash("يرجى إدخال رقم هاتف صحيح", 'danger')
                return render_template('register.html')
            
            # Generate serial number
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            serial_number = f"{timestamp}-{phone}"
            
            # Create new user
            new_user = User(
                name=name,
                phone=phone,
                serial_number=serial_number,
                date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                password_hash=generate_password_hash(phone),
                # Default values for other required fields in your User model
                table_number="N/A",
                people=1,
                males=1 if gender == 'male' else 0,
                females=1 if gender == 'female' else 0,
                image_filename=None
            )
            
            # Add email and age if provided
            # These would need to be added to your User model
            if email:
                setattr(new_user, 'email', email)
            if age and age.isdigit():
                setattr(new_user, 'age', int(age))
            
            db.session.add(new_user)
            db.session.commit()
            
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(serial_number)
            qr.make(fit=True)
            
            qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
            
            # Add logo to QR code
            logo_path = os.path.join('static', 'logo', 'B2.jpg')
            if os.path.exists(logo_path):
                logo = Image.open(logo_path)
                qr_width, qr_height = qr_img.size
                logo_size = int(qr_width / 4)
                logo = logo.resize((logo_size, logo_size))
                pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
                qr_img.paste(logo, pos)
            
            # Save QR code
            uploads_folder = os.path.join('static', 'uploads')
            if not os.path.exists(uploads_folder):
                os.makedirs(uploads_folder)
                
            qr_code_path = os.path.join(uploads_folder, f'qr_{serial_number}.png')
            qr_img.save(qr_code_path)
            
            qr_code_url = url_for('static', filename=f'uploads/qr_{serial_number}.png')
            
            flash("تم التسجيل بنجاح!", 'success')
            return render_template('registration_success.html', 
                                  user=new_user, 
                                  qr_code=qr_code_url)
        
        except IntegrityError:
            db.session.rollback()
            flash("خطأ في التسجيل. قد يكون رقم الهاتف مسجل مسبقًا.", 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f"حدث خطأ أثناء التسجيل: {str(e)}", 'danger')
    
    return render_template('register.html')



@app.route('/upload_qr')
def upload_qr():
    return render_template('upload_qr.html')





def decode_qr_code(filepath):
    """
    Decode QR code from an image using OpenCV with improved detection
    """
    try:
        # Read the image
        img = cv2.imread(filepath)
        
        # Initialize QR Code detector
        qr_detector = cv2.QRCodeDetector()
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding to improve detection
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # Detect and decode
        data, bbox, straight_qrcode = qr_detector.detectAndDecode(thresh)
        
        if not data and bbox is not None:
            # Try again with the original image if thresholding didn't work
            data, bbox, straight_qrcode = qr_detector.detectAndDecode(img)
        
        if data:
            return data.strip()
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
        total_count = len(login_records)
        total_people = sum(user.people for _, user in login_records)

        
        return render_template(
            'view_logged_in_users.html', 
            login_records=login_records,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            total_count=total_count,
            total_people=total_people
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
