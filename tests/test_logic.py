import pytest
from logic import calcular_macros_alimento, calcular_macros_receta, obtener_resumen_diario

# Mock Classes para simular los modelos de la base de datos
class MockFood:
    def __init__(self, name, kcal, prot, carb, fat):
        self.name = name
        self.kcal_100g = kcal
        self.prot_100g = prot
        self.carb_100g = carb
        self.fat_100g = fat

class MockIngredient:
    def __init__(self, food, grams):
        self.food = food
        self.grams = grams

class MockRecipe:
    def __init__(self, name, ingredients):
        self.name = name
        self.ingredients = ingredients

class MockLog:
    def __init__(self, grams, food=None, recipe=None):
        self.grams = grams
        self.food = food
        self.recipe = recipe
        self.food_id = 1 if food else None
        self.recipe_id = 1 if recipe else None

# --- PRUEBAS ---

def test_calcular_macros_alimento_proporcional():
    """Verifica que si consumo 150g, el cálculo sea 1.5 veces el valor por 100g."""
    alimento = MockFood("Pollo", 100, 20, 0, 2)
    res = calcular_macros_alimento(150, alimento)
    assert res["kcal"] == 150
    assert res["proteinas"] == 30
    assert res["carbohidratos"] == 0
    assert res["grasas"] == 3

def test_calcular_macros_receta_escalado():
    """Verifica que una receta de 200g totales, si como 100g, me de la mitad de macros."""
    ing1 = MockIngredient(MockFood("Ing1", 100, 10, 0, 0), 100) # 100kcal totales
    ing2 = MockIngredient(MockFood("Ing2", 200, 0, 10, 0), 100) # 200kcal totales
    receta = MockRecipe("Mix", [ing1, ing2]) # Total 300kcal en 200g
    
    # Comemos la mitad (100g de los 200g de la receta)
    res = calcular_macros_receta(100, receta)
    assert res["kcal"] == 150
    assert res["proteinas"] == 5
    assert res["carbohidratos"] == 5

def test_obtener_resumen_diario_vacio():
    """Verifica que si no hay logs, el resumen sea cero redondeado."""
    res = obtener_resumen_diario([])
    assert res == {"kcal": 0, "proteinas": 0, "carbohidratos": 0, "grasas": 0}