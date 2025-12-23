import re
import json
import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Importamos componentes locales
from models import db, User, Food, DailyLog, Recipe, RecipeIngredient
from logic import obtener_resumen_diario

app = Flask(__name__)
app.config["SECRET_KEY"] = "tfm_seguridad_2024_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///nutri.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- CONFIGURACIÓN DE SQLITE PARA FOREIGN KEYS ---
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Fuerza a SQLite a respetar las Claves Foráneas para integridad referencial."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sesión requerida para acceder al sistema."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def validar_password(password):
    """Valida requisitos de seguridad de la contraseña."""
    if not password or len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password): return False
    if not re.search(r"[a-z]", password): return False
    if not re.search(r"[0-9]", password): return False
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/? ]", password): return False
    return True

# --- DASHBOARD Y NAVEGACIÓN ---

@app.route("/")
@login_required
def root():
    hoy_str = date.today().strftime("%Y-%m-%d")
    return redirect(url_for("index", date_str=hoy_str))

@app.route("/day/<date_str>")
@login_required
def index(date_str):
    try:
        fecha_actual = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return redirect(url_for("root"))

    prev_day = (fecha_actual - timedelta(days=1)).strftime("%Y-%m-%d")
    next_day = (fecha_actual + timedelta(days=1)).strftime("%Y-%m-%d")

    logs = DailyLog.query.filter_by(user_id=current_user.id, date=fecha_actual).all()
    resumen = obtener_resumen_diario(logs)

    # Trazabilidad: Snapshot de objetivos o valores actuales
    if logs and logs[0].target_kcal_snapshot:
        targets = {
            "kcal": logs[0].target_kcal_snapshot, "prot": logs[0].target_protein_snapshot,
            "carbs": logs[0].target_carbs_snapshot, "fat": logs[0].target_fat_snapshot,
        }
    else:
        targets = {
            "kcal": current_user.target_kcal, "prot": current_user.target_protein,
            "carbs": current_user.target_carbs, "fat": current_user.target_fat,
        }

    return render_template("index.html", resumen=resumen, targets=targets, hoy=fecha_actual,
                           prev_day=prev_day, next_day=next_day, logs=logs, date=date)

# --- USUARIO Y PERFIL ---

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password")
        if password != request.form.get("confirm_password"):
            flash("Las contraseñas no coinciden.", "danger")
        elif not validar_password(password):
            flash("Contraseña no válida (8+ caracteres, Mayus, Minus, Num, Especial).", "warning")
        elif not request.form.get("politica_privacidad"):
            flash("Debe aceptar la política de privacidad.", "warning")
        else:
            try:
                if User.query.filter((User.username == username) | (User.email == email)).first():
                    flash("Usuario o email ya registrados.", "warning")
                else:
                    nuevo = User(username=username, email=email, 
                                 password=generate_password_hash(password, method="pbkdf2:sha256"),
                                 fecha_aceptacion_politica=datetime.now())
                    db.session.add(nuevo)
                    db.session.commit()
                    flash("Cuenta creada correctamente.", "success")
                    return redirect(url_for("login"))
            except Exception:
                db.session.rollback()
                flash("Error interno del servidor.", "danger")
    return render_template("registro.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form.get("username")).first()
        if user and check_password_hash(user.password, request.form.get("password")):
            login_user(user)
            return redirect(url_for("root"))
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
        flash("Objetivos actualizados correctamente.", "success")
        return redirect(url_for("root"))
    return render_template("perfil.html")

# --- CATÁLOGO UNIFICADO (ALIMENTOS Y RECETAS) ---

@app.route("/mis_alimentos")
@login_required
def mis_alimentos():
    alimentos = Food.query.filter_by(user_id=current_user.id).all()
    recetas = Recipe.query.filter_by(user_id=current_user.id).all()
    return render_template("mis_alimentos.html", alimentos=alimentos, recetas=recetas)

@app.route("/add_food", methods=["GET", "POST"])
@login_required
def add_food():
    if request.method == "POST":
        nuevo = Food(name=request.form.get("name"), kcal_100g=float(request.form.get("kcal")),
                     prot_100g=float(request.form.get("prot")), carb_100g=float(request.form.get("carb")),
                     fat_100g=float(request.form.get("fat")), user_id=current_user.id)
        db.session.add(nuevo)
        db.session.commit()
        flash(f"Alimento '{nuevo.name}' añadido.", "success")
        return redirect(url_for("mis_alimentos"))
    return render_template("form_food.html", alimento=None)

@app.route("/edit_food/<int:food_id>", methods=["GET", "POST"])
@login_required
def edit_food(food_id):
    f = Food.query.get_or_404(food_id)
    if f.user_id != current_user.id: return redirect(url_for('mis_alimentos'))
    if request.method == "POST":
        f.name, f.kcal_100g = request.form.get("name"), float(request.form.get("kcal"))
        f.prot_100g, f.carb_100g = float(request.form.get("prot")), float(request.form.get("carb"))
        f.fat_100g = float(request.form.get("fat"))
        db.session.commit()
        flash("Alimento actualizado.", "success")
        return redirect(url_for('mis_alimentos'))
    return render_template("form_food.html", alimento=f)

@app.route("/delete_food/<int:food_id>")
@login_required
def delete_food(food_id):
    f = Food.query.get_or_404(food_id)
    if f.user_id == current_user.id:
        try:
            db.session.delete(f)
            db.session.commit()
            flash("Alimento eliminado.", "info")
        except Exception:
            db.session.rollback()
            flash("No se puede eliminar: está en uso.", "danger")
    return redirect(url_for('mis_alimentos'))

@app.route("/add_recipe", methods=["GET", "POST"])
@login_required
def add_recipe():
    if request.method == "POST":
        nueva = Recipe(name=request.form.get("name"), user_id=current_user.id)
        db.session.add(nueva)
        db.session.flush()
        f_ids, grams = request.form.getlist("food_ids[]"), request.form.getlist("grams[]")
        for fid, g in zip(f_ids, grams):
            if fid and g: db.session.add(RecipeIngredient(recipe_id=nueva.id, food_id=int(fid), grams=float(g)))
        db.session.commit()
        flash("Receta creada.", "success")
        return redirect(url_for("mis_alimentos"))
    alimentos = Food.query.filter_by(user_id=current_user.id).order_by(Food.name).all()
    return render_template("form_recipe.html", receta=None, alimentos=alimentos)

@app.route("/edit_recipe/<int:recipe_id>", methods=["GET", "POST"])
@login_required
def edit_recipe(recipe_id):
    r = Recipe.query.get_or_404(recipe_id)
    if r.user_id != current_user.id: return redirect(url_for('mis_alimentos'))
    if request.method == "POST":
        r.name = request.form.get("name")
        RecipeIngredient.query.filter_by(recipe_id=r.id).delete()
        f_ids, grams = request.form.getlist("food_ids[]"), request.form.getlist("grams[]")
        for fid, g in zip(f_ids, grams):
            if fid and g: db.session.add(RecipeIngredient(recipe_id=r.id, food_id=int(fid), grams=float(g)))
        db.session.commit()
        flash("Receta actualizada.", "success")
        return redirect(url_for('mis_alimentos'))
    alimentos = Food.query.filter_by(user_id=current_user.id).all()
    return render_template("form_recipe.html", receta=r, alimentos=alimentos)

@app.route("/delete_recipe/<int:recipe_id>")
@login_required
def delete_recipe(recipe_id):
    r = Recipe.query.get_or_404(recipe_id)
    if r.user_id == current_user.id:
        db.session.delete(r)
        db.session.commit()
        flash("Receta eliminada.", "info")
    return redirect(url_for('mis_alimentos'))

# --- UTILIDADES ---

@app.route("/cargar_basicos")
@login_required
def cargar_basicos():
    path = os.path.join(app.root_path, 'alimentos_basicos.json')
    if not os.path.exists(path):
        flash("Archivo JSON no encontrado.", "danger")
        return redirect(url_for("mis_alimentos"))
    with open(path, 'r', encoding='utf-8') as f:
        basicos = json.load(f)
    cont = 0
    for b in basicos:
        if not Food.query.filter_by(name=b["name"], user_id=current_user.id).first():
            db.session.add(Food(name=b["name"], kcal_100g=b["kcal"], prot_100g=b["prot"], 
                                carb_100g=b["carb"], fat_100g=b["fat"], user_id=current_user.id))
            cont += 1
    db.session.commit()
    flash(f"Añadidos {cont} alimentos básicos.", "success")
    return redirect(url_for("mis_alimentos"))

@app.route("/limpiar_catalogo")
@login_required
def limpiar_catalogo():
    alimentos = Food.query.filter_by(user_id=current_user.id).all()
    borrados = protegidos = 0
    for f in alimentos:
        try:
            db.session.delete(f)
            db.session.commit()
            borrados += 1
        except Exception:
            db.session.rollback()
            protegidos += 1
    flash(f"Limpieza: {borrados} eliminados, {protegidos} protegidos.", "info")
    return redirect(url_for('mis_alimentos'))

# --- DIARIO DE CONSUMO ---

@app.route("/add_log", methods=["GET", "POST"])
@login_required
def add_log():
    date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    if request.method == "POST":
        item, grams = request.form.get("item_id"), float(request.form.get("grams", 0))
        f_date = datetime.strptime(request.form.get("date"), '%Y-%m-%d').date()
        if not item or grams <= 0:
            flash("Datos no válidos.", "warning")
            return redirect(url_for("add_log", date=date_str))
        tipo, rid = item.split("_")
        nuevo = DailyLog(user_id=current_user.id, grams=grams, date=f_date,
                         target_kcal_snapshot=current_user.target_kcal,
                         target_protein_snapshot=current_user.target_protein,
                         target_carbs_snapshot=current_user.target_carbs,
                         target_fat_snapshot=current_user.target_fat)
        if tipo == "food": nuevo.food_id = int(rid)
        else: nuevo.recipe_id = int(rid)
        db.session.add(nuevo)
        db.session.commit()
        flash("Consumo registrado.", "success")
        return redirect(url_for("index", date_str=f_date.strftime("%Y-%m-%d")))
    alimentos = Food.query.filter_by(user_id=current_user.id).all()
    recetas = Recipe.query.filter_by(user_id=current_user.id).all()
    return render_template("add_log.html", alimentos=alimentos, recetas=recetas, selected_date=date_str)

@app.route("/delete_log/<int:log_id>")
@login_required
def delete_log(log_id):
    log = DailyLog.query.get_or_404(log_id)
    if log.user_id == current_user.id:
        f_ret = log.date.strftime("%Y-%m-%d")
        db.session.delete(log)
        db.session.commit()
        flash("Registro eliminado.", "info")
        return redirect(url_for('index', date_str=f_ret))
    return redirect(url_for('root'))

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)