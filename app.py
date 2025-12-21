import re
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
from models import db, User, Food, DailyLog, Recipe, RecipeIngredient
from logic import obtener_resumen_diario

app = Flask(__name__)
app.config["SECRET_KEY"] = "tfm_seguridad_2024_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///nutri.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Configuración de Flask-Login en español
login_manager.login_message = "Sesión requerida para acceder al sistema."
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def validar_password(password):
    """Valida requisitos de seguridad de la contraseña."""
    if not password or len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/? ]", password):
        return False
    return True


# --- RUTAS DE NAVEGACIÓN Y DASHBOARD ---


@app.route("/")
@login_required
def root():
    """Redirige a la vista del día actual."""
    hoy_str = date.today().strftime("%Y-%m-%d")
    return redirect(url_for("index", date_str=hoy_str))


@app.route("/day/<date_str>")
@login_required
def index(date_str):
    """Dashboard principal con historial y trazabilidad de objetivos."""
    try:
        fecha_actual = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return redirect(url_for("root"))

    prev_day = (fecha_actual - timedelta(days=1)).strftime("%Y-%m-%d")
    next_day = (fecha_actual + timedelta(days=1)).strftime("%Y-%m-%d")

    logs = DailyLog.query.filter_by(user_id=current_user.id, date=fecha_actual).all()
    resumen = obtener_resumen_diario(logs)

    # Lógica de trazabilidad: snapshot si hay registros, si no, objetivos actuales
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

    return render_template(
        "index.html",
        resumen=resumen,
        targets=targets,
        hoy=fecha_actual,
        prev_day=prev_day,
        next_day=next_day,
        logs=logs,
    )


# --- RUTAS DE USUARIO Y PERFIL ---


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
            flash(
                "La contraseña debe tener una longitud mínima de 8 caracteres con al menos 1 minúscula, 1 mayúscula, 1 número y 1 carácter especial.",
                "warning",
            )
            return render_template("registro.html", username=username, email=email)

        try:
            user_exists = User.query.filter(
                (User.username == username) | (User.email == email)
            ).first()
            if user_exists:
                flash(
                    "El nombre de usuario o el correo electrónico ya están registrados.",
                    "warning",
                )
                return render_template("registro.html", username=username, email=email)

            hashed_pw = generate_password_hash(password, method="pbkdf2:sha256")
            nuevo_usuario = User(
                username=username,
                email=email,
                password=hashed_pw,
                fecha_aceptacion_politica=datetime.now(),
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
            # Al loguear, redirigimos a la raíz (que lleva a hoy)
            return redirect(url_for("root"))
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
        flash("Objetivos actualizados correctamente.", "success")
        return redirect(url_for("root"))
    return render_template("perfil.html")


# --- RUTAS DE ALIMENTOS Y LOGS ---


@app.route("/add_food", methods=["GET", "POST"])
@login_required
def add_food():
    if request.method == "POST":
        nuevo_alimento = Food(
            name=request.form.get("name"),
            kcal_100g=float(request.form.get("kcal")),
            prot_100g=float(request.form.get("prot")),
            carb_100g=float(request.form.get("carb")),
            fat_100g=float(request.form.get("fat")),
            user_id=current_user.id,
        )
        db.session.add(nuevo_alimento)
        db.session.commit()
        flash(f"Alimento '{nuevo_alimento.name}' añadido correctamente.", "success")
        return redirect(url_for("mis_alimentos"))
    return render_template("add_food.html")


@app.route("/mis_alimentos")
@login_required
def mis_alimentos():
    alimentos = Food.query.filter_by(user_id=current_user.id).all()
    recetas = Recipe.query.filter_by(user_id=current_user.id).all() # Añadimos esto
    return render_template("mis_alimentos.html", alimentos=alimentos, recetas=recetas)


@app.route("/add_log", methods=["GET", "POST"])
@login_required
def add_log():
    if request.method == "POST":
        item_id_raw = request.form.get("item_id")  # Recibe ej: "food_5" o "recipe_2"
        grams = float(request.form.get("grams", 0))

        if not item_id_raw or grams <= 0:
            flash("Selección o cantidad no válida.", "warning")
            return redirect(url_for("add_log"))

        # Separamos el tipo (food/recipe) del ID real
        tipo, real_id = item_id_raw.split("_")

        nuevo_log = DailyLog(
            user_id=current_user.id,
            grams=grams,
            date=date.today(),
            target_kcal_snapshot=current_user.target_kcal,
            target_protein_snapshot=current_user.target_protein,
            target_carbs_snapshot=current_user.target_carbs,
            target_fat_snapshot=current_user.target_fat,
        )

        if tipo == "food":
            nuevo_log.food_id = int(real_id)
        else:
            nuevo_log.recipe_id = int(real_id)

        db.session.add(nuevo_log)
        db.session.commit()
        flash("Consumo registrado correctamente.", "success")
        return redirect(url_for("root"))

    # Cargamos ambos para el formulario
    alimentos = Food.query.filter_by(user_id=current_user.id).all()
    recetas = Recipe.query.filter_by(user_id=current_user.id).all()
    return render_template("add_log.html", alimentos=alimentos, recetas=recetas)


@app.route("/add_recipe", methods=["GET", "POST"])
@login_required
def add_recipe():
    if request.method == "POST":
        nombre_receta = request.form.get("name")
        food_ids = request.form.getlist("food_ids[]")
        grams_list = request.form.getlist("grams[]")

        if not nombre_receta or not food_ids:
            flash(
                "La receta debe tener un nombre y al menos un ingrediente.", "warning"
            )
            return redirect(url_for("add_recipe"))

        nueva_receta = Recipe(name=nombre_receta, user_id=current_user.id)
        db.session.add(nueva_receta)
        db.session.flush()  # Para obtener el ID de la receta antes del commit

        for f_id, g in zip(food_ids, grams_list):
            if f_id and g:
                ingrediente = RecipeIngredient(
                    recipe_id=nueva_receta.id, food_id=int(f_id), grams=float(g)
                )
                db.session.add(ingrediente)

        db.session.commit()
        flash(f"Receta '{nombre_receta}' creada correctamente.", "success")
        return redirect(url_for("root"))

    alimentos = Food.query.filter_by(user_id=current_user.id).all()
    return render_template("add_recipe.html", alimentos=alimentos)

# --- ELIMINAR DEL LOG DIARIO ---
@app.route("/delete_log/<int:log_id>")
@login_required
def delete_log(log_id):
    log = DailyLog.query.get_or_404(log_id)
    # Seguridad: solo el dueño puede borrarlo
    if log.user_id == current_user.id:
        fecha_retorno = log.date.strftime("%Y-%m-%d")
        db.session.delete(log)
        db.session.commit()
        flash("Consumo eliminado.", "info")
        return redirect(url_for('index', date_str=fecha_retorno))
    return redirect(url_for('root'))

# --- GESTIÓN DEL CATÁLOGO (ELIMINAR Y EDITAR) ---
@app.route("/delete_food/<int:food_id>")
@login_required
def delete_food(food_id):
    alimento = Food.query.get_or_404(food_id)
    if alimento.user_id == current_user.id:
        try:
            db.session.delete(alimento)
            db.session.commit()
            flash(f"Alimento '{alimento.name}' eliminado.", "info")
        except Exception:
            db.session.rollback()
            flash("No se puede eliminar: el alimento está siendo usado en logs o recetas.", "danger")
    return redirect(url_for('mis_alimentos'))

@app.route("/edit_food/<int:food_id>", methods=["GET", "POST"])
@login_required
def edit_food(food_id):
    alimento = Food.query.get_or_404(food_id)
    if alimento.user_id != current_user.id:
        return redirect(url_for('mis_alimentos'))
    
    if request.method == "POST":
        alimento.name = request.form.get("name")
        alimento.kcal_100g = float(request.form.get("kcal"))
        alimento.prot_100g = float(request.form.get("prot"))
        alimento.carb_100g = float(request.form.get("carb"))
        alimento.fat_100g = float(request.form.get("fat"))
        db.session.commit()
        flash("Alimento actualizado correctamente.", "success")
        return redirect(url_for('mis_alimentos'))
    
    return render_template("edit_food.html", food=alimento)

@app.route("/delete_recipe/<int:recipe_id>")
@login_required
def delete_recipe(recipe_id):
    receta = Recipe.query.get_or_404(recipe_id)
    if receta.user_id == current_user.id:
        try:
            # Primero borramos los ingredientes de la receta
            RecipeIngredient.query.filter_by(recipe_id=receta.id).delete()
            db.session.delete(receta)
            db.session.commit()
            flash(f"Receta '{receta.name}' eliminada correctamente.", "info")
        except Exception:
            db.session.rollback()
            flash("Error al eliminar la receta.", "danger")
    return redirect(url_for('mis_alimentos'))

@app.route("/edit_recipe/<int:recipe_id>", methods=["GET", "POST"])
@login_required
def edit_recipe(recipe_id):
    receta = Recipe.query.get_or_404(recipe_id)
    if receta.user_id != current_user.id:
        return redirect(url_for('mis_alimentos'))

    if request.method == "POST":
        receta.name = request.form.get("name")
        food_ids = request.form.getlist("food_ids[]")
        grams_list = request.form.getlist("grams[]")

        # Borramos los ingredientes actuales para reinsertar los nuevos (más simple que actualizar uno a uno)
        RecipeIngredient.query.filter_by(recipe_id=receta.id).delete()

        for f_id, g in zip(food_ids, grams_list):
            if f_id and g:
                nuevo_ing = RecipeIngredient(
                    recipe_id=receta.id,
                    food_id=int(f_id),
                    grams=float(g)
                )
                db.session.add(nuevo_ing)
        
        db.session.commit()
        flash("Receta actualizada con éxito.", "success")
        return redirect(url_for('mis_alimentos'))

    alimentos = Food.query.filter_by(user_id=current_user.id).all()
    return render_template("edit_recipe.html", receta=receta, alimentos=alimentos)

# --- INICIALIZACIÓN ---
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
