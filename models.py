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
    
    # Objetivos nutricionales (defaults)
    target_kcal = db.Column(db.Integer, default=2000)
    target_protein = db.Column(db.Integer, default=150)
    target_carbs = db.Column(db.Integer, default=200)
    target_fat = db.Column(db.Integer, default=60)

class Food(db.Model):
    """Alimentos base del catálogo."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    kcal_100g = db.Column(db.Float, nullable=False)
    prot_100g = db.Column(db.Float, nullable=False)
    carb_100g = db.Column(db.Float, nullable=False)
    fat_100g = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Recipe(db.Model):
    """Para crear 'Productos' o combinaciones como el batido."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    # Una receta tiene muchos ingredientes
    ingredients = db.relationship('RecipeIngredient', backref='recipe', cascade="all, delete-orphan")

class RecipeIngredient(db.Model):
    """La relación entre un alimento y una receta (ej: 30g de crema cacahuete en el Batido)."""
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'))
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'))
    grams = db.Column(db.Float, nullable=False)
    food = db.relationship('Food')

class DailyLog(db.Model):
    """Donde se almacena lo que comes cada día (tu resumen diario)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    
    # Podemos registrar un alimento suelto o una receta entera
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=True)
    
    grams = db.Column(db.Float, nullable=False) # Cantidad total consumida
    
    food = db.relationship('Food')
    recipe = db.relationship('Recipe')