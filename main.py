import os
import json
import typer
from pathlib import Path
from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.table import Table
import requests

app = typer.Typer(
    help="CLI tool for food logging and calorie tracking using USDA FoodData Central API",
    epilog="Requires USDA_API_KEY environment variable or API key in ~/pa/usda"
)
console = Console()

DATA_DIR = Path.home() / ".local" / "share" / "food-cli"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "food_log.jsonl"

def get_api_key() -> str:
    """Get USDA API key from env or pa file"""
    api_key = os.getenv("USDA_API_KEY")
    if not api_key:
        key_file = Path.home() / "pa" / "usda"
        if key_file.exists():
            api_key = key_file.read_text().strip()
    if not api_key:
        console.print("[red]Error: USDA_API_KEY not found. Get one at https://fdc.nal.usda.gov/api-key-signup/[/red]")
        raise typer.Exit(1)
    return api_key

def search_food(query: str, page_size: int = 10) -> dict:
    """Search USDA FoodData Central for foods matching query"""
    api_key = get_api_key()
    url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    
    params = {
        "api_key": api_key,
        "query": query,
        "pageSize": page_size,
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def get_food_details(fdc_id: int) -> dict:
    """Get detailed nutrition info for a specific food by FDC ID"""
    api_key = get_api_key()
    url = f"https://api.nal.usda.gov/fdc/v1/food/{fdc_id}"
    
    params = {"api_key": api_key}
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def log_food(food_name: str, calories: float, protein: float, carbs: float, fat: float, serving: str):
    """Log food entry to jsonl file"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "food": food_name,
        "serving": serving,
        "calories": calories,
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
    }
    
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

@app.command()
def search(
    query: str = typer.Argument(..., help="Food to search for (e.g., 'banana' or '2 eggs')"),
    count: int = typer.Option(10, "--count", "-n", help="Number of results to show"),
):
    """
    Search for foods in USDA database.
    
    Example: food search "banana"
    Example: food search "cheddar cheese"
    """
    try:
        results = search_food(query, count)
        
        if not results.get("foods"):
            console.print("[yellow]No foods found matching your query[/yellow]")
            return
        
        table = Table(title=f"Search Results for '{query}'")
        table.add_column("ID", style="cyan")
        table.add_column("Food", style="green")
        table.add_column("Brand", style="dim")
        table.add_column("Calories", justify="right")
        
        for food in results["foods"]:
            fdc_id = str(food["fdcId"])
            name = food.get("description", "Unknown")
            brand = food.get("brandName", food.get("brandOwner", ""))
            
            # Try to find calorie info
            calories = "N/A"
            nutrients = food.get("foodNutrients", [])
            for nutrient in nutrients:
                if nutrient.get("nutrientName") == "Energy":
                    calories = str(int(nutrient.get("value", 0)))
                    break
            
            table.add_row(fdc_id, name, brand, calories)
        
        console.print(table)
        console.print("\n[dim]Use 'food log <id>' to log a food item[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def log(
    fdc_id: int = typer.Argument(..., help="FDC ID from search results"),
    servings: float = typer.Option(1.0, "--servings", "-s", help="Number of servings (default: 1.0)"),
):
    """
    Log a food item to your daily intake.
    
    Example: food log 123456 --servings 1.5
    """
    try:
        food = get_food_details(fdc_id)
        
        name = food.get("description", "Unknown food")
        serving_size = food.get("servingSize", 100)
        serving_unit = food.get("servingUnit", "g")
        
        # Extract key nutrients
        calories = protein = carbs = fat = 0.0
        
        nutrients = food.get("foodNutrients", [])
        for nutrient in nutrients:
            nutrient_name = nutrient.get("nutrient", {}).get("name", "")
            value = nutrient.get("amount", 0)
            
            if "Energy" in nutrient_name and "kcal" in nutrient.get("nutrient", {}).get("unitName", ""):
                calories = value
            elif nutrient_name == "Protein":
                protein = value
            elif nutrient_name == "Carbohydrate, by difference":
                carbs = value
            elif nutrient_name == "Total lipid (fat)":
                fat = value
        
        # Adjust for servings
        calories *= servings
        protein *= servings
        carbs *= servings
        fat *= servings
        serving_text = f"{serving_size * servings:.1f} {serving_unit}"
        
        # Log it
        log_food(name, calories, protein, carbs, fat, serving_text)
        
        # Display confirmation
        console.print(f"[green]✓[/green] Logged: [bold]{name}[/bold]")
        console.print(f"  Serving: {serving_text}")
        console.print(f"  Calories: {calories:.0f} kcal")
        console.print(f"  Protein: {protein:.1f}g | Carbs: {carbs:.1f}g | Fat: {fat:.1f}g")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def today():
    """
    Show today's logged foods and totals.
    
    Example: food today
    """
    if not LOG_FILE.exists():
        console.print("[yellow]No foods logged yet[/yellow]")
        return
    
    today_str = datetime.now().date().isoformat()
    entries = []
    
    with open(LOG_FILE, "r") as f:
        for line in f:
            entry = json.loads(line)
            if entry["timestamp"].startswith(today_str):
                entries.append(entry)
    
    if not entries:
        console.print("[yellow]No foods logged today[/yellow]")
        return
    
    # Display table
    table = Table(title=f"Today's Food Log - {today_str}")
    table.add_column("Time", style="dim")
    table.add_column("Food", style="green")
    table.add_column("Serving")
    table.add_column("Calories", justify="right")
    table.add_column("Protein", justify="right")
    table.add_column("Carbs", justify="right")
    table.add_column("Fat", justify="right")
    
    total_cals = total_protein = total_carbs = total_fat = 0.0
    
    for entry in entries:
        time = datetime.fromisoformat(entry["timestamp"]).strftime("%H:%M")
        table.add_row(
            time,
            entry["food"],
            entry["serving"],
            f"{entry['calories']:.0f}",
            f"{entry['protein_g']:.1f}g",
            f"{entry['carbs_g']:.1f}g",
            f"{entry['fat_g']:.1f}g",
        )
        total_cals += entry["calories"]
        total_protein += entry["protein_g"]
        total_carbs += entry["carbs_g"]
        total_fat += entry["fat_g"]
    
    table.add_section()
    table.add_row(
        "",
        "[bold]TOTAL[/bold]",
        "",
        f"[bold]{total_cals:.0f}[/bold]",
        f"[bold]{total_protein:.1f}g[/bold]",
        f"[bold]{total_carbs:.1f}g[/bold]",
        f"[bold]{total_fat:.1f}g[/bold]",
    )
    
    console.print(table)

@app.command()
def quick(
    query: str = typer.Argument(..., help="Food description (e.g., '2 eggs and bacon')"),
    servings: float = typer.Option(1.0, "--servings", "-s", help="Number of servings"),
):
    """
    Quick log: search and log first result in one command.
    
    Example: food quick "banana"
    Example: food quick "scrambled eggs" --servings 2
    """
    try:
        # Search for food
        results = search_food(query, 1)
        
        if not results.get("foods"):
            console.print("[yellow]No foods found matching your query[/yellow]")
            return
        
        food_result = results["foods"][0]
        fdc_id = food_result["fdcId"]
        
        console.print(f"[dim]Found: {food_result.get('description')}[/dim]")
        
        # Get full details and log
        food = get_food_details(fdc_id)
        
        name = food.get("description", "Unknown food")
        serving_size = food.get("servingSize", 100)
        serving_unit = food.get("servingUnit", "g")
        
        # Extract nutrients
        calories = protein = carbs = fat = 0.0
        
        nutrients = food.get("foodNutrients", [])
        for nutrient in nutrients:
            nutrient_name = nutrient.get("nutrient", {}).get("name", "")
            value = nutrient.get("amount", 0)
            
            if "Energy" in nutrient_name and "kcal" in nutrient.get("nutrient", {}).get("unitName", ""):
                calories = value
            elif nutrient_name == "Protein":
                protein = value
            elif nutrient_name == "Carbohydrate, by difference":
                carbs = value
            elif nutrient_name == "Total lipid (fat)":
                fat = value
        
        # Adjust for servings
        calories *= servings
        protein *= servings
        carbs *= servings
        fat *= servings
        serving_text = f"{serving_size * servings:.1f} {serving_unit}"
        
        # Log it
        log_food(name, calories, protein, carbs, fat, serving_text)
        
        # Display confirmation
        console.print(f"[green]✓[/green] Logged: [bold]{name}[/bold]")
        console.print(f"  Serving: {serving_text}")
        console.print(f"  Calories: {calories:.0f} kcal")
        console.print(f"  Protein: {protein:.1f}g | Carbs: {carbs:.1f}g | Fat: {fat:.1f}g")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
