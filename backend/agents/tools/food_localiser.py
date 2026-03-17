from langchain.tools import tool
from typing import Optional

# ── SG FOOD DATABASE (based on SG FoodID / HealthHub data) ──────────────────
# Each item has: name, sodium_mg, potassium_mg, calories, tags
SG_FOOD_DB = [
    # HAWKER / CANTEEN OPTIONS
    {"name": "Yong Tau Foo (dry, no added salt)", "sodium_mg": 320, "potassium_mg": 420, "calories": 280, "tags": ["hawker", "halal", "low_sodium", "high_potassium"]},
    {"name": "Cai Png - steamed fish + 2 veg (less gravy)", "sodium_mg": 480, "potassium_mg": 510, "calories": 420, "tags": ["hawker", "halal", "low_sodium"]},
    {"name": "Ban Mian (dry, less sauce)", "sodium_mg": 520, "potassium_mg": 380, "calories": 380, "tags": ["hawker", "low_sodium"]},
    {"name": "Sliced Fish Bee Hoon Soup (clear broth, less salt)", "sodium_mg": 490, "potassium_mg": 440, "calories": 320, "tags": ["hawker", "halal", "low_sodium"]},
    {"name": "Brown Rice with Steamed Chicken + Veg", "sodium_mg": 410, "potassium_mg": 490, "calories": 450, "tags": ["hawker", "halal", "low_sodium", "high_potassium"]},
    {"name": "Thosai with Sambar (no chutney)", "sodium_mg": 380, "potassium_mg": 360, "calories": 290, "tags": ["hawker", "vegetarian", "low_sodium"]},
    {"name": "Popiah (2 rolls, no sweet sauce)", "sodium_mg": 420, "potassium_mg": 330, "calories": 260, "tags": ["hawker", "low_sodium"]},
    {"name": "Wonton Noodle Soup (less soy sauce)", "sodium_mg": 610, "potassium_mg": 290, "calories": 360, "tags": ["hawker"]},
    {"name": "Nasi Lemak (no fried chicken, extra veg)", "sodium_mg": 580, "potassium_mg": 310, "calories": 480, "tags": ["hawker", "halal"]},
    {"name": "Mee Goreng", "sodium_mg": 980, "potassium_mg": 280, "calories": 520, "tags": ["hawker", "halal", "high_sodium"]},
    {"name": "Char Kway Teow", "sodium_mg": 1100, "potassium_mg": 220, "calories": 570, "tags": ["hawker", "high_sodium"]},
    {"name": "Chicken Rice (steamed, less sauce)", "sodium_mg": 520, "potassium_mg": 350, "calories": 480, "tags": ["hawker", "halal"]},
    # BREAKFAST OPTIONS
    {"name": "Oats with Banana", "sodium_mg": 80, "potassium_mg": 520, "calories": 280, "tags": ["home", "halal", "low_sodium", "high_potassium", "breakfast"]},
    {"name": "Wholemeal Bread with Egg (no butter)", "sodium_mg": 320, "potassium_mg": 180, "calories": 240, "tags": ["home", "halal", "breakfast"]},
    {"name": "Kaya Toast (thin spread) with Soft Boiled Eggs", "sodium_mg": 410, "potassium_mg": 140, "calories": 310, "tags": ["kopitiam", "halal", "breakfast"]},
    # DRINKS
    {"name": "Teh O Kosong (plain tea no sugar)", "sodium_mg": 5, "potassium_mg": 90, "calories": 5, "tags": ["drink", "halal", "low_sodium"]},
    {"name": "Barley Water (no sugar)", "sodium_mg": 10, "potassium_mg": 60, "calories": 30, "tags": ["drink", "halal", "low_sodium"]},
    {"name": "100Plus / Isotonic Drink", "sodium_mg": 160, "potassium_mg": 50, "calories": 130, "tags": ["drink", "high_sodium"]},
]

@tool
def food_localiser_tool(
    sodium_mg_max: str,
    potassium_mg_min: str,
    dietary_restrictions: str,
    meal_type: str,
    top_n: Optional[int] = 3
) -> str:
    """
    Given nutritional targets and dietary restrictions, returns the best
    localised Singapore food options from hawker centres and canteens.

    Args:
        sodium_mg_max: maximum sodium in mg for this meal
        potassium_mg_min: minimum potassium in mg for this meal
        dietary_restrictions: comma separated e.g. "halal" or "vegetarian" or "none"
        meal_type: "breakfast", "lunch", "dinner", or "snack"
        top_n: number of options to return (default 3)

    Returns:
        JSON string with recommended food options and their nutritional info
    """
    sodium_mg_max = int(sodium_mg_max)
    potassium_mg_min = int(potassium_mg_min)
    restrictions = [r.strip().lower() for r in dietary_restrictions.split(",")]
    results = []

    for food in SG_FOOD_DB:
        # filter by sodium
        if food["sodium_mg"] > sodium_mg_max:
            continue
        # filter by potassium
        if food["potassium_mg"] < potassium_mg_min:
            continue
        # filter by dietary restrictions
        if "halal" in restrictions and "halal" not in food["tags"] and "vegetarian" not in food["tags"]:
            continue
        if "vegetarian" in restrictions and "vegetarian" not in food["tags"]:
            continue
        # filter by meal type if specified
        if meal_type == "breakfast" and "breakfast" not in food["tags"] and "home" not in food["tags"]:
            continue

        results.append(food)

    # sort by sodium ascending (lowest sodium first)
    results.sort(key=lambda x: x["sodium_mg"])
    top_results = results[:top_n]

    if not top_results:
        return "No matching food options found. Consider home-cooked meals with minimal salt."

    output = f"Top {len(top_results)} localised food options for {meal_type}:\n"
    for i, food in enumerate(top_results, 1):
        output += (
            f"{i}. {food['name']}\n"
            f"   Sodium: {food['sodium_mg']}mg | Potassium: {food['potassium_mg']}mg | "
            f"Calories: {food['calories']}kcal\n"
        )

    return output
