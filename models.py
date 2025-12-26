from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    # Guardamos la fecha para cumplir con normativas de protección de datos
    fecha_aceptacion_politica = db.Column(db.DateTime, nullable=True)
    
    # Metas diarias del usuario; sirven de referencia para las barras de progreso
    target_kcal = db.Column(db.Integer, default=2000)
    target_protein = db.Column(db.Integer, default=150)
    target_carbs = db.Column(db.Integer, default=200)
    target_fat = db.Column(db.Integer, default=60)

    # Relaciones principales: un usuario es dueño de sus alimentos, recetas y registros
    foods = db.relationship('Food', backref='owner', lazy=True)
    recipes = db.relationship('Recipe', backref='owner', lazy=True)
    logs = db.relationship('DailyLog', backref='owner', lazy=True)

class Food(db.Model):
    """Alimentos básicos creados por el usuario o cargados del sistema."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # Valores nutricionales siempre referenciados a una base de 100g
    kcal_100g = db.Column(db.Float, nullable=False)
    prot_100g = db.Column(db.Float, nullable=False)
    carb_100g = db.Column(db.Float, nullable=False)
    fat_100g = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Bloqueamos el borrado accidental si el alimento ya forma parte de una receta o log
    recipe_usages = db.relationship('RecipeIngredient', backref='food', lazy=True)
    log_usages = db.relationship('DailyLog', backref='food', lazy=True)

class Recipe(db.Model):
    """Platos compuestos (ej: un batido) que agrupan varios alimentos."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Si borramos la receta, sus ingredientes (la relación peso-alimento) desaparecen automáticamente
    ingredients = db.relationship('RecipeIngredient', backref='recipe', cascade="all, delete-orphan")
    log_usages = db.relationship('DailyLog', backref='recipe', lazy=True)

class RecipeIngredient(db.Model):
    """Tabla intermedia que define cuántos gramos de un alimento lleva una receta."""
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=False)
    grams = db.Column(db.Float, nullable=False)

class DailyLog(db.Model):
    """Registro de lo consumido. Aquí ocurre la magia de la trazabilidad."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    
    # Puede ser un alimento suelto o una receta completa (uno de los dos será nulo)
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=True)
    grams = db.Column(db.Float, nullable=False) 
    
    # IMPORTANTE: Guardamos una snapshot de los objetivos actuales del usuario.
    # Así, si el usuario cambia su dieta mañana, el historial de hoy no se verá alterado.
    target_kcal_snapshot = db.Column(db.Integer)
    target_protein_snapshot = db.Column(db.Integer)
    target_carbs_snapshot = db.Column(db.Integer)
    target_fat_snapshot = db.Column(db.Integer)

    def get_macros(self):
        """Método de conveniencia para obtener resultados finales sin importar el tipo de entrada."""
        from logic import calcular_macros_alimento, calcular_macros_receta
        if self.food:
            return calcular_macros_alimento(self.grams, self.food)
        elif self.recipe:
            return calcular_macros_receta(self.grams, self.recipe)
        return {"kcal": 0, "proteinas": 0, "carbohidratos": 0, "grasas": 0}