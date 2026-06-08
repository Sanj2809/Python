# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'smart-study-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///study_tips.db'

db = SQLAlchemy()

# --- CƠ SỞ DỮ LIỆU (MIGRATED FROM MODELS.PY) ---
class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    
    likes = db.relationship('Like', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)

class StudyTip(db.Model):
    __tablename__ = 'study_tip'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    
    likes = db.relationship('Like', backref='study_tip', lazy=True)
    comments = db.relationship('Comment', backref='study_tip', lazy=True)

class Like(db.Model):
    __tablename__ = 'like'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tip_id = db.Column(db.Integer, db.ForeignKey('study_tip.id'), nullable=False)

class Comment(db.Model):
    __tablename__ = 'comment'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tip_id = db.Column(db.Integer, db.ForeignKey('study_tip.id'), nullable=False)

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- TRANG CHỦ ---
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    if current_user.is_authenticated and current_user.username == 'admin':
        query = StudyTip.query
    else:
        query = StudyTip.query.filter_by(is_approved=True)
        
    if search:
        query = query.filter(StudyTip.title.contains(search) | StudyTip.content.contains(search))
    if category:
        query = query.filter(StudyTip.category == category)
        
    tips = query.order_by(StudyTip.date_created.desc()).paginate(page=page, per_page=4)
    return render_template('index.html', tips=tips, search=search, category=category)

# --- THÊM MẸO MỚI (CHUYỂN SANG DÙNG TIP_FORM.HTML) ---
@app.route('/tip/add', methods=['GET', 'POST'])
@login_required
def add_tip():
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        content = request.form.get('content')
        approved = True if current_user.username == 'admin' else False
        
        new_tip = StudyTip(title=title, category=category, content=content, is_approved=approved)
        db.session.add(new_tip)
        db.session.commit()
        
        if approved:
            flash('Đã đăng tải một phương pháp học tập mới thành công!', 'success')
        else:
            flash('Bài viết đã được gửi thành công! Vui lòng chờ Admin phê duyệt để hiển thị công khai.', 'warning')
        return redirect(url_for('index'))
    return render_template('tip_form.html', title="➕ Đăng Tải Phương Pháp Học Tập Mới", tip=None)

# --- DUYỆT BÀI (CHỈ ADMIN) ---
@app.route('/admin/approve/<int:tip_id>', methods=['POST'])
@login_required
def approve_tip(tip_id):
    if current_user.username != 'admin':
        flash('Bạn không có quyền thực hiện hành động này!', 'danger')
        return redirect(url_for('index'))
        
    tip = StudyTip.query.get_or_404(tip_id)
    tip.is_approved = True
    db.session.commit()
    flash(f'Đã phê duyệt công khai bài viết: {tip.title}', 'success')
    return redirect(url_for('index'))

# --- SỬA BÀI (CHUYỂN SANG DÙNG TIP_FORM.HTML) ---
@app.route('/admin/edit/<int:tip_id>', methods=['GET', 'POST'])
@login_required
def edit_tip(tip_id):
    if current_user.username != 'admin':
        flash('Bạn không có quyền chỉnh sửa bài viết!', 'danger')
        return redirect(url_for('index'))
        
    tip = StudyTip.query.get_or_404(tip_id)
    if request.method == 'POST':
        tip.title = request.form.get('title')
        tip.category = request.form.get('category')
        tip.content = request.form.get('content')
        db.session.commit()
        flash('Admin đã cập nhật bài viết thành công!', 'success')
        return redirect(url_for('index'))
            
    return render_template('tip_form.html', tip=tip, title="✏️ Chỉnh Sửa Phương Pháp Học Tập")

# --- XÓA BÀI ---
@app.route('/admin/delete/<int:tip_id>', methods=['POST'])
@login_required
def delete_tip(tip_id):
    if current_user.username != 'admin':
        flash('Chỉ Admin mới có quyền xóa bài viết!', 'danger')
        return redirect(url_for('index'))
        
    tip = StudyTip.query.get_or_404(tip_id)
    try:
        Comment.query.filter_by(tip_id=tip_id).delete()
        Like.query.filter_by(tip_id=tip_id).delete()
        db.session.delete(tip)
        db.session.commit()
        flash('Admin đã xóa bài viết thành công!', 'success')
    except Exception:
        db.session.rollback()
        flash('Có lỗi xảy ra khi xóa bài!', 'danger')
        
    return redirect(url_for('index'))

# --- TÀI KHOẢN VÀ TƯƠNG TÁC ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        
        if username.lower() == 'admin':
            flash('Không thể sử dụng tên tài khoản bảo mật này!', 'danger')
            return redirect(url_for('register'))
            
        if User.query.filter_by(username=username).first():
            flash('Tên đăng nhập này đã tồn tại!', 'danger')
            return redirect(url_for('register'))
        
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        db.session.add(User(username=username, password=hashed_pw))
        db.session.commit()
        flash('Đăng ký tài khoản Thành Viên thành công!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.username == 'admin':
                flash('Chào mừng ADMIN đã đăng nhập quản trị!', 'dark')
            else:
                flash('Chào mừng thành viên đã quay trở lại!', 'info')
            return redirect(url_for('index'))
            
        flash('Tài khoản hoặc mật khẩu không chính xác!', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Đã đăng xuất hệ thống.', 'info')
    return redirect(url_for('index'))

@app.route('/tip/<int:tip_id>/like', methods=['POST'])
@login_required
def like_tip(tip_id):
    existing_like = Like.query.filter_by(user_id=current_user.id, tip_id=tip_id).first()
    if existing_like:
        db.session.delete(existing_like)
    else:
        db.session.add(Like(user_id=current_user.id, tip_id=tip_id))
    db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/tip/<int:tip_id>/comment', methods=['POST'])
@login_required
def add_comment(tip_id):
    comment_content = request.form.get('content', '').strip()
    if comment_content:
        db.session.add(Comment(content=comment_content, user_id=current_user.id, tip_id=tip_id))
        db.session.commit()
        flash('Đã gửi ý kiến đóng góp của bạn!', 'success')
    return redirect(request.referrer or url_for('index'))

@app.route('/comment/delete/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id == current_user.id or current_user.username == 'admin':
        db.session.delete(comment)
        db.session.commit()
        flash('Đã xóa bình luận!', 'success')
    else:
        flash('Bạn không có quyền này!', 'danger')
    return redirect(request.referrer or url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            hashed_pw = generate_password_hash('admin', method='pbkdf2:sha256')
            db.session.add(User(username='admin', password=hashed_pw))
            db.session.commit()
            print(">>> ĐÃ KHỞI TẠO TÀI KHOẢN ADMIN MẶC ĐỊNH (MẬT KHẨU: admin)")
            
    app.run(debug=True)