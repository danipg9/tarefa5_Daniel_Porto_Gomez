def calcular_macros_alimento(grams, food):
    """Calcula los macros de una cantidad específica de un alimento base."""
    ratio = grams / 100
    return {
        "kcal": food.kcal_100g * ratio,
        "proteinas": food.prot_100g * ratio,
        "carbohidratos": food.carb_100g * ratio,
        "grasas": food.fat_100g * ratio
    }

def calcular_macros_receta(grams_consumidos, recipe):
    """
    Calcula los macros de una receta (ej. tu batido).
    Suma los ingredientes y escala al peso que hayas tomado.
    """
    totales_receta = {"kcal": 0, "proteinas": 0, "carbohidratos": 0, "grasas": 0}
    peso_total_receta = sum(ing.grams for ing in recipe.ingredients)
    
    # 1. Sumamos los macros de todos los ingredientes de la receta
    for ing in recipe.ingredients:
        macros_ing = calcular_macros_alimento(ing.grams, ing.food)
        for clave in totales_receta:
            totales_receta[clave] += macros_ing[clave]
            
    # 2. Escalamos según cuánto del total de la receta te has tomado
    # (Si la receta pesa 500g y te tomas 250g, te llevas la mitad de macros)
    ratio_consumo = grams_consumidos / peso_total_receta if peso_total_receta > 0 else 0
    
    return {k: v * ratio_consumo for k, v in totales_receta.items()}

def obtener_resumen_diario(logs):
    """
    Procesa todos los logs de un día para darte el resumen:
    'Daniel, hoy llevas X/Y kcal...'
    """
    resumen = {"kcal": 0, "proteinas": 0, "carbohidratos": 0, "grasas": 0}
    
    for log in logs:
        if log.food_id:
            macros = calcular_macros_alimento(log.grams, log.food)
        elif log.recipe_id:
            macros = calcular_macros_receta(log.grams, log.recipe)
        else:
            continue
            
        for clave in resumen:
            resumen[clave] += macros[clave]
            
    return {k: round(v, 2) for k, v in resumen.items()}