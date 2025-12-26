def calcular_macros_alimento(grams, food):
    """Calcula los macros proporcionales de un alimento base."""
    # Evitamos errores si el alimento no existe
    if not food:
        return {"kcal": 0, "proteinas": 0, "carbohidratos": 0, "grasas": 0}
    
    ratio = grams / 100
    return {
        "kcal": food.kcal_100g * ratio,
        "proteinas": food.prot_100g * ratio,
        "carbohidratos": food.carb_100g * ratio,
        "grasas": food.fat_100g * ratio
    }

def calcular_macros_receta(grams_consumidos, recipe):
    """
    Suma los ingredientes de una receta y escala el total 
    según la cantidad que el usuario ha ingerido.
    """
    totales_receta = {"kcal": 0, "proteinas": 0, "carbohidratos": 0, "grasas": 0}
    
    if not recipe or not recipe.ingredients:
        return totales_receta

    # 1. Calculamos el peso total real de la receta sumando sus ingredientes
    peso_total_receta = sum(ing.grams for ing in recipe.ingredients)
    
    # 2. Sumamos los macros de cada ingrediente
    for ing in recipe.ingredients:
        macros_ing = calcular_macros_alimento(ing.grams, ing.food)
        for clave in totales_receta:
            totales_receta[clave] += macros_ing[clave]
            
    # 3. Ratio: ¿Qué parte de la receta completa se ha comido el usuario?
    ratio_consumo = grams_consumidos / peso_total_receta if peso_total_receta > 0 else 0
    
    return {k: v * ratio_consumo for k, v in totales_receta.items()}

def obtener_resumen_diario(logs):
    """
    Itera sobre los consumos del día (DailyLog) y acumula los totales.
    """
    resumen = {"kcal": 0, "proteinas": 0, "carbohidratos": 0, "grasas": 0}
    
    for log in logs:
        if log.food_id and log.food:
            macros = calcular_macros_alimento(log.grams, log.food)
        elif log.recipe_id and log.recipe:
            macros = calcular_macros_receta(log.grams, log.recipe)
        else:
            continue
            
        for clave in resumen:
            resumen[clave] += macros[clave]
            
    # Retornamos los valores redondeados para una visualización limpia en el Dashboard
    return {k: round(v, 1) for k, v in resumen.items()}

def obtener_estadisticas_breves(user_id, dias=7):
    """Calcula cuántos días se ha cumplido el objetivo en un rango de tiempo."""
    from datetime import date, timedelta
    from models import DailyLog
    
    fecha_inicio = date.today() - timedelta(days=dias)
    # Obtenemos todos los logs del periodo
    logs = DailyLog.query.filter(DailyLog.user_id == user_id, DailyLog.date >= fecha_inicio).all()
    
    # Agrupamos por fecha para calcular totales diarios
    datos_diarios = {}
    for log in logs:
        if log.date not in datos_diarios:
            datos_diarios[log.date] = {
                "kcal": 0, 
                "objetivo": log.target_kcal_snapshot or 2000
            }
        
        m = log.get_macros()
        datos_diarios[log.date]["kcal"] += m["kcal"]

    cumplidos = 0
    # Un día es "éxito" si está cerca del objetivo (margen del 10%)
    for dia, info in datos_diarios.items():
        margen = info["objetivo"] * 0.1
        if abs(info["kcal"] - info["objetivo"]) <= margen:
            cumplidos += 1
            
    return {
        "total_dias_con_datos": len(datos_diarios), 
        "cumplidos": cumplidos
    }