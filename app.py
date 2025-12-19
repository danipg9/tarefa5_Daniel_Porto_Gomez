from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Food, DailyLog, Recipe, RecipeIngredient
from logic import obtener_resumen_diario
from datetime import date

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev_key_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nutri.db'

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- RUTAS DE NAVEGACIÓN ---

@app.route('/')
@login_required
def index():
    # Obtenemos los logs de hoy para Daniel
    hoy = date.today()
    logs_hoy = DailyLog.query.filter_by(user_id=current_user.id, date=hoy).all()
    resumen = obtener_resumen_diario(logs_hoy)
    return render_template('index.html', resumen=resumen, hoy=hoy)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('index'))
        flash('Usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'])
        nuevo_usuario = User(
            username=request.form['username'], 
            password=hashed_pw,
            target_kcal=request.form.get('kcal', 2000),
            target_protein=request.form.get('prote', 150),
            target_carbs=request.form.get('carbs', 200),
            target_fat=request.form.get('grasas', 60)
        )
        db.session.add(nuevo_usuario)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('registro.html')

# --- INICIALIZACIÓN ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)