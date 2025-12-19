import pytest
from logic import calcular_macros_alimento

# Simulamos un objeto alimento (tipo Mock) para no necesitar la base de datos real
class MockFood:
    def __init__(self, kcal, prot, carb, fat):
        self.kcal_100g = kcal
        self.prot_100g = prot
        self.carb_100g = carb
        self.fat_100g = fat

def test_calculo_alimento_base():
    """Prueba que 200g de pavo calculan bien los macros."""
    pavo = MockFood(100, 20, 0, 2) # 100kcal, 20g prot, 0 carb, 2g grasa
    resultado = calcular_macros_alimento(200, pavo)
    
    assert resultado["kcal"] == 200
    assert resultado["proteinas"] == 40
    assert resultado["grasas"] == 4