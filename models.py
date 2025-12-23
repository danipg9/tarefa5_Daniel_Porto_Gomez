from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    fecha_aceptacion_politica = db.Column(db.DateTime, nullable=True)
    
    # Objetivos nutricionales actuales
    target_kcal = db.Column(db.Integer, default=2000)
    target_protein = db.Column(db.Integer, default=150)
    target_carbs = db.Column(db.Integer, default=200)
    target_fat = db.Column(db.Integer, default=60)

    # Relaciones
    foods = db.relationship('Food', backref='owner', lazy=True)
    recipes = db.relationship('Recipe', backref='owner', lazy=True)
    logs = db.relationship('DailyLog', backref='owner', lazy=True)

class Food(db.Model):
    """Alimentos base del catálogo."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    kcal_100g = db.Column(db.Float, nullable=False)
    prot_100g = db.Column(db.Float, nullable=False)
    carb_100g = db.Column(db.Float, nullable=False)
    fat_100g = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relaciones para proteger la integridad (No permiten borrar si existen hijos)
    recipe_usages = db.relationship('RecipeIngredient', backref='food', lazy=True)
    log_usages = db.relationship('DailyLog', backref='food', lazy=True)

class Recipe(db.Model):
    """Combinaciones de alimentos (ej: Batido de volumen)."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Si se borra una receta, se borran sus ingredientes automáticamente (cascade)
    ingredients = db.relationship('RecipeIngredient', backref='recipe', cascade="all, delete-orphan")
    log_usages = db.relationship('DailyLog', backref='recipe', lazy=True)

class RecipeIngredient(db.Model):
    """Relación alimento-receta con su peso específico."""
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    # Importante: food_id es ForeignKey y nullable=False para integridad
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=False)
    grams = db.Column(db.Float, nullable=False)

class DailyLog(db.Model):
    """Registro histórico de consumo y objetivos."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=True)
    grams = db.Column(db.Float, nullable=False) 
    
    # --- TRAZABILIDAD HISTÓRICA ---
    target_kcal_snapshot = db.Column(db.Integer)
    target_protein_snapshot = db.Column(db.Integer)
    target_carbs_snapshot = db.Column(db.Integer)
    target_fat_snapshot = db.Column(db.Integer)

    def get_macros(self):
        """Calcula y devuelve los macros del registro actual."""
        from logic import calcular_macros_alimento, calcular_macros_receta
        if self.food:
            return calcular_macros_alimento(self.grams, self.food)
        elif self.recipe:
            return calcular_macros_receta(self.grams, self.recipe)
        return {"kcal": 0, "proteinas": 0, "carbohidratos": 0, "grasas": 0}