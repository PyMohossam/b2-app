from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import qrcode
import os
from sqlalchemy.exc import IntegrityError

# إعداد Flask و SQLAlchemy
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///default.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# تعريف جدول المستخدمين في قاعدة البيانات
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    table_number = db.Column(db.String(100), nullable=False)
    people = db.Column(db.Integer, nullable=False)
    males = db.Column(db.Integer, nullable=False)
    females = db.Column(db.Integer, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    date = db.Column(db.String(100), nullable=False)

# التأكد من وجود قاعدة البيانات
with app.app_context():
    db.create_all()

# صفحة التسجيل
@app.route('/sign_up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        # Check if the phone number already exists
        existing_user = User.query.filter_by(phone=request.form['phone']).first()
        if existing_user:
            return "رقم الهاتف موجود بالفعل، يرجى إدخال رقم آخر."
        
        user_data = User(
            name=request.form['name'],
            table_number=request.form['table_number'],
            people=request.form['people'],
            males=request.form['males'],
            females=request.form['females'],
            phone=request.form['phone'],
            date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        # Check that the people count matches the sum of males and females
        try:
            people = int(request.form['people'])
            males = int(request.form['males'])
            females = int(request.form['females'])
        except ValueError:
            return "الرجاء إدخال أرقام صحيحة في عدد الأشخاص والذكور والإناث."

        if people != males + females:
            return "عدد الأشخاص يجب أن يساوي مجموع الذكور والإناث."

        if not user_data.phone.isdigit() or len(user_data.phone) < 6:
            return "رقم الهاتف يجب أن يكون أرقام فقط وطوله لا يقل عن 6 أرقام."

        # Save the data to the database
        try:
            db.session.add(user_data)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()  # Rollback the session if an error occurs
            return "حدث خطأ أثناء حفظ البيانات. يرجى المحاولة مرة أخرى."

        # Generate QR/Barcode
        code_type = request.form['code_type']
        file_path = os.path.join("static/qrcodes", f"{user_data.phone}.{code_type}.png")
        
        if code_type == "qr":
            generate_qr_code(user_data.phone, file_path)
        else:
            generate_barcode(user_data.phone, file_path)

        return render_template('receipt.html', user=user_data, qr_path=file_path)

    return render_template('sign_up.html')

# توليد QR
def generate_qr_code(user_id, file_path):
    qr = qrcode.make(user_id)
    qr.save(file_path)

# توليد Barcode
def generate_barcode(user_id, file_path):
    qr = qrcode.make(user_id)  # يمكن استخدام مكتبة أخرى للـ Barcode هنا
    qr.save(file_path)

# صفحة عرض الزوار
@app.route('/view_users')
def view_users():
    users = User.query.all()  # استرجاع كل المستخدمين من قاعدة البيانات
    return render_template('view_users.html', users=users)

# الصفحة الرئيسية
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
