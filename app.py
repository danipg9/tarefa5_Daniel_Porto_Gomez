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

# Importamos la base de datos y la lógica de negocio para desacoplar el código
from models import db, User, Food, DailyLog, Recipe, RecipeIngredient
from logic import obtener_resumen_diario

# --- CONFIGURACIÓN DE LA APLICACIÓN ---
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "tfm_seguridad_2024_key")

# DETECCIÓN DE ENTORNO: Si existe DATABASE_URL en el sistema, usamos Postgres (Nube)
# Si no, usamos el SQLite local (Desarrollo)
database_url = os.environ.get("DATABASE_URL")

if database_url:
    # Ajuste necesario: SQLAlchemy requiere 'postgresql://' pero Render suele dar 'postgres://'
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url.replace("postgres://", "postgresql://", 1)
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///nutri.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- CONFIGURACIÓN DE INTEGRIDAD PARA SQLITE ---
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Solo aplicamos PRAGMA si estamos en SQLite.
    PostgreSQL gestiona las Claves Foráneas de forma nativa y automática.
    """
    # Verificamos si la URL de la base de datos contiene 'sqlite'
    if "sqlite" in app.config["SQLALCHEMY_DATABASE_URI"]:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

db.init_app(app)

# Gestión de sesiones con Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Sesión requerida para acceder al sistema."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def validar_password(password):
    """
    Validación de robustez de contraseña mediante Regex.
    Exige complejidad para cumplir con estándares de seguridad mínimos.
    """
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
    # Redirección automática a la fecha actual al entrar en la app
    hoy_str = date.today().strftime("%Y-%m-%d")
    return redirect(url_for("index", date_str=hoy_str))

@app.route("/day/<date_str>")
@login_required
def index(date_str):
    """
    Punto de entrada principal. Gestiona la visualización del diario 
    y el cálculo de estadísticas de adherencia (rachas).
    """
    try:
        fecha_actual = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return redirect(url_for("root"))

    prev_day = (fecha_actual - timedelta(days=1)).strftime("%Y-%m-%d")
    next_day = (fecha_actual + timedelta(days=1)).strftime("%Y-%m-%d")

    # Recuperamos los registros y calculamos el resumen nutricional
    logs = DailyLog.query.filter_by(user_id=current_user.id, date=fecha_actual).all()
    resumen = obtener_resumen_diario(logs)

    # Lógica de Snapshots: Priorizamos la meta que el usuario tenía el día del registro
    if logs and logs[0].target_kcal_snapshot:
        targets = {
            "kcal": logs[0].target_kcal_snapshot, 
            "prot": logs[0].target_protein_snapshot,
            "carbs": logs[0].target_carbs_snapshot, 
            "fat": logs[0].target_fat_snapshot,
        }
    else:
        targets = {
            "kcal": current_user.target_kcal, 
            "prot": current_user.target_protein,
            "carbs": current_user.target_carbs, 
            "fat": current_user.target_fat,
        }

    from logic import obtener_estadisticas_breves
    stats_semana = obtener_estadisticas_breves(current_user.id, dias=7)
    stats_mes = obtener_estadisticas_breves(current_user.id, dias=30)

    return render_template(
        "index.html", 
        resumen=resumen, 
        targets=targets, 
        hoy=fecha_actual,
        prev_day=prev_day, 
        next_day=next_day, 
        logs=logs, 
        date=date,
        stats_semana=stats_semana,
        stats_mes=stats_mes
    )

# --- GESTIÓN DE USUARIOS ---

@app.route("/registro", methods=["GET", "POST"])
def registro():
    """Proceso de alta con validación de integridad (email/user únicos)."""
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
                    # Aplicamos hashing para nunca guardar contraseñas en texto plano
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
    """Actualización de metas diarias que afectan a los cálculos de progreso."""
    if request.method == "POST":
        current_user.target_kcal = int(request.form.get("kcal", 2000))
        current_user.target_protein = int(request.form.get("proteinas", 150))
        current_user.target_carbs = int(request.form.get("carbohidratos", 200))
        current_user.target_fat = int(request.form.get("grasas", 60))
        db.session.commit()
        flash("Objetivos actualizados correctamente.", "success")
        return redirect(url_for("root"))
    return render_template("perfil.html")

# --- CATÁLOGO (ALIMENTOS Y RECETAS) ---

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
    """
    Permite modificar los valores de un alimento existente.
    Verifica que el alimento pertenezca al usuario activo antes de editar.
    """
    f = Food.query.get_or_404(food_id)
    
    # Seguridad: si el alimento no es del usuario, redirigimos
    if f.user_id != current_user.id: 
        return redirect(url_for('mis_alimentos'))
        
    if request.method == "POST":
        f.name = request.form.get("name")
        f.kcal_100g = float(request.form.get("kcal"))
        f.prot_100g = float(request.form.get("prot"))
        f.carb_100g = float(request.form.get("carb"))
        f.fat_100g = float(request.form.get("fat"))
        
        db.session.commit()
        flash("Alimento actualizado correctamente.", "success")
        return redirect(url_for('mis_alimentos'))
        
    return render_template("form_food.html", alimento=f)

@app.route("/delete_food/<int:food_id>")
@login_required
def delete_food(food_id):
    """
    Elimina un alimento del catálogo.
    Controla el error si el alimento está referenciado en una receta (Integridad).
    """
    f = Food.query.get_or_404(food_id)
    if f.user_id == current_user.id:
        try:
            db.session.delete(f)
            db.session.commit()
            flash("Alimento eliminado.", "info")
        except Exception:
            db.session.rollback()
            flash("No se puede eliminar: el alimento está en uso en alguna receta.", "danger")
    return redirect(url_for('mis_alimentos'))

@app.route("/add_recipe", methods=["GET", "POST"])
@login_required
def add_recipe():
    """
    Gestión de creación de recetas. 
    Usa 'flush' para obtener el ID de la receta antes de insertar sus ingredientes.
    """
    if request.method == "POST":
        nueva = Recipe(name=request.form.get("name"), user_id=current_user.id)
        db.session.add(nueva)
        db.session.flush() # Sincroniza con la BD sin cerrar la transacción
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
    """
    Permite modificar una receta y sus ingredientes.
    Elimina los ingredientes anteriores y registra los nuevos para simplificar la actualización.
    """
    r = Recipe.query.get_or_404(recipe_id)
    if r.user_id != current_user.id: 
        return redirect(url_for('mis_alimentos'))
        
    if request.method == "POST":
        r.name = request.form.get("name")
        # Limpiamos ingredientes actuales para evitar duplicados o conflictos
        RecipeIngredient.query.filter_by(recipe_id=r.id).delete()
        
        f_ids = request.form.getlist("food_ids[]")
        grams = request.form.getlist("grams[]")
        
        for fid, g in zip(f_ids, grams):
            if fid and g:
                db.session.add(RecipeIngredient(recipe_id=r.id, food_id=int(fid), grams=float(g)))
        
        db.session.commit()
        flash("Receta actualizada con éxito.", "success")
        return redirect(url_for('mis_alimentos'))
        
    alimentos = Food.query.filter_by(user_id=current_user.id).all()
    return render_template("form_recipe.html", receta=r, alimentos=alimentos)

@app.route("/delete_recipe/<int:recipe_id>")
@login_required
def delete_recipe(recipe_id):
    """
    Elimina una receta del catálogo. 
    Las relaciones en RecipeIngredient se borran en cascada según el modelo.
    """
    r = Recipe.query.get_or_404(recipe_id)
    if r.user_id == current_user.id:
        db.session.delete(r)
        db.session.commit()
        flash("Receta eliminada correctamente.", "info")
    return redirect(url_for('mis_alimentos'))

# --- CARGA DE DATOS Y LIMPIEZA ---

@app.route("/cargar_basicos")
@login_required
def cargar_basicos():
    """Seed de base de datos desde un archivo JSON externo."""
    path = os.path.join(app.root_path, 'alimentos_basicos.json')
    if not os.path.exists(path):
        flash("Archivo JSON no encontrado.", "danger")
        return redirect(url_for("mis_alimentos"))
    with open(path, 'r', encoding='utf-8') as f:
        basicos = json.load(f)
    cont = 0
    for b in basicos:
        # Evitamos duplicados por nombre para el mismo usuario
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
    """
    Eliminación masiva con control de excepciones. 
    Protege alimentos que ya están siendo usados en recetas o registros diarios.
    """
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
    flash(f"Limpieza: {borrados} eliminados, {protegidos} aún en uso.", "info")
    return redirect(url_for('mis_alimentos'))

# --- DIARIO DE CONSUMO ---

@app.route("/add_log", methods=["GET", "POST"])
@login_required
def add_log():
    """
    Registro de ingesta. 
    Guarda un 'snapshot' de las metas actuales del usuario para que el historial sea inalterable.
    """
    date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    if request.method == "POST":
        item, grams = request.form.get("item_id"), float(request.form.get("grams", 0))
        f_date = datetime.strptime(request.form.get("date"), '%Y-%m-%d').date()
        
        # El prefijo del ID nos dice si es alimento base o receta compuesta
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
    """
    Elimina un registro de consumo del diario.
    Retorna al usuario a la misma fecha en la que estaba visualizando el diario.
    """
    log = DailyLog.query.get_or_404(log_id)
    if log.user_id == current_user.id:
        f_ret = log.date.strftime("%Y-%m-%d")
        db.session.delete(log)
        db.session.commit()
        flash("Registro eliminado del diario.", "info")
        return redirect(url_for('index', date_str=f_ret))
    return redirect(url_for('root'))

# Inicia la base de datos dentro del contexto de la aplicación
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    # En local usaremos el puerto 5000, en la nube el que nos asigne el sistema
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)