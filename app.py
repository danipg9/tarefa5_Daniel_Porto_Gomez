import re
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Food, DailyLog, Recipe, RecipeIngredient
from logic import obtener_resumen_diario

app = Flask(__name__)
app.config["SECRET_KEY"] = "tfm_seguridad_2024_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///nutri.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Configuración profesional de Flask-Login en español
login_manager.login_message = "Sesión requerida para acceder al sistema."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def validar_password(password):
    """
    Verifica: mín 8 caracteres, 1 mayúscula, 1 minúscula, 1 número y 1 carácter especial amplio.
    """
    if not password or len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    # Acepta: !@#$%^&*()_+-=[]{}|;':",./<>? y espacio
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/? ]", password):
        return False
    return True

@app.route("/")
@login_required
def index():
    hoy = date.today()
    logs_hoy = DailyLog.query.filter_by(user_id=current_user.id, date=hoy).all()
    resumen = obtener_resumen_diario(logs_hoy)
    return render_template("index.html", resumen=resumen, hoy=hoy)

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        acepta_politica = request.form.get("politica_privacidad")

        if not acepta_politica:
            flash("Debe aceptar la política de privacidad.", "warning")
            return render_template("registro.html", username=username, email=email)

        if password != confirm_password:
            flash("Las contraseñas no coinciden.", "danger")
            return render_template("registro.html", username=username, email=email)

        if not validar_password(password):
            flash("La contraseña no cumple los requisitos: debe tener una longitud mínima de 8 caracteres con al menos 1 letra minúscula, 1 letra mayorúscula, 1 número y 1 carácter especial.", "warning")
            return render_template("registro.html", username=username, email=email)

        try:
            user_exists = User.query.filter((User.username == username) | (User.email == email)).first()
            if user_exists:
                flash("El nombre de usuario o el correo electrónico ya están registrados.", "warning")
                return render_template("registro.html", username=username, email=email)

            hashed_pw = generate_password_hash(password, method="pbkdf2:sha256")
            nuevo_usuario = User(
                username=username,
                email=email,
                password=hashed_pw,
                fecha_aceptacion_politica=datetime.now()
            )
            db.session.add(nuevo_usuario)
            db.session.commit()
            flash("Cuenta creada correctamente. Ya puede iniciar sesión.", "success")
            return redirect(url_for("login"))
        except Exception:
            db.session.rollback()
            flash("Error interno del servidor.", "danger")
            return render_template("registro.html", username=username, email=email)

    return render_template("registro.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("index"))
        else:
            flash("Credenciales no válidas.", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    if request.method == "POST":
        current_user.target_kcal = int(request.form.get("kcal", 2000))
        current_user.target_protein = int(request.form.get("proteinas", 150))
        current_user.target_carbs = int(request.form.get("carbohidratos", 200))
        current_user.target_fat = int(request.form.get("grasas", 60))
        db.session.commit()
        flash("Objetivos actualizados.", "success")
        return redirect(url_for("index"))
    return render_template("perfil.html")

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)