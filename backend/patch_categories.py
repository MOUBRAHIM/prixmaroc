"""
Patch ia_service.py : ajoute la 6e colonne 'category' à chaque tuple du NUTRITION_PLAN
en se basant sur le rôle (1ère colonne du tuple).
"""
import re

PATH = "/app/app/services/ia_service.py"
src = open(PATH, encoding="utf-8").read()

# Mapping rôle → catégorie d'affichage
ROLE_TO_CAT = {
    "Eau minérale": "💧 Eau & Boissons",
    "Farine tendre": "🌾 Pain & Céréales",
    "Levure boulang": "🌾 Pain & Céréales",
    "Œufs frais": "🥚 Œufs",
    "Sel fin": "🧂 Épices & Condiments",
    "Huile végétale": "🫒 Huiles & Corps gras",
    "Pois chiches": "🫘 Légumineuses",
    "Lentilles": "🫘 Légumineuses",
    "Haricots blancs": "🫘 Légumineuses",
    "Fèves séchées": "🫘 Légumineuses",
    "Tomates fraîches": "🥦 Légumes frais",
    "Oignons": "🥦 Légumes frais",
    "Pommes de terre": "🥦 Légumes frais",
    "Carottes": "🥦 Légumes frais",
    "Courgettes": "🥦 Légumes frais",
    "Poivrons": "🥦 Légumes frais",
    "Aubergines": "🥦 Légumes frais",
    "Légumes verts": "🥦 Légumes frais",
    "Ail": "🧂 Épices & Condiments",
    "Herbes fraîches": "🧂 Épices & Condiments",
    "Concentré de tomates": "🧂 Épices & Condiments",
    "Harissa": "🧂 Épices & Condiments",
    "Cumin": "🧂 Épices & Condiments",
    "Paprika": "🧂 Épices & Condiments",
    "Ras el Hanout": "🧂 Épices & Condiments",
    "Gingembre": "🧂 Épices & Condiments",
    "Curcuma": "🧂 Épices & Condiments",
    "Cannelle": "🧂 Épices & Condiments",
    "Safran": "🧂 Épices & Condiments",
    "Poivre noir": "🧂 Épices & Condiments",
    "Olives beldi": "🧂 Épices & Condiments",
    "Citrons confits": "🧂 Épices & Condiments",
    "Thé vert": "🍵 Boissons chaudes & Sucre",
    "Café": "🍵 Boissons chaudes & Sucre",
    "Sucre": "🍵 Boissons chaudes & Sucre",
    "Sardines en boîte": "🐟 Poissons & Fruits de mer",
    "Sardines fraîches": "🐟 Poissons & Fruits de mer",
    "Thon en boîte": "🐟 Poissons & Fruits de mer",
    "Sole / Crevettes": "🐟 Poissons & Fruits de mer",
    "Lait": "🥛 Produits laitiers",
    "Yaourt": "🥛 Produits laitiers",
    "Fromage fondu": "🥛 Produits laitiers",
    "Beurre / Margarine": "🫒 Huiles & Corps gras",
    "Huile d'olive": "🫒 Huiles & Corps gras",
    "Couscous": "🌾 Pain & Céréales",
    "Pain de mie": "🌾 Pain & Céréales",
    "Pâtes alimentaires": "🌾 Pain & Céréales",
    "Vermicelles": "🌾 Pain & Céréales",
    "Riz": "🌾 Pain & Céréales",
    "Oranges / Agrumes": "🍊 Fruits frais",
    "Bananes": "🍊 Fruits frais",
    "Pommes": "🍊 Fruits frais",
    "Dattes medjool": "🍊 Fruits frais",
    "Miel": "🍯 Miel, Confiture & Petit-déjeuner",
    "Amlou": "🍯 Miel, Confiture & Petit-déjeuner",
    "Confiture": "🍯 Miel, Confiture & Petit-déjeuner",
    "Jus d'orange": "💧 Eau & Boissons",
    "Cuisses de poulet": "🍗 Volaille (halal)",
    "Dinde hachée": "🍗 Volaille (halal)",
    "Viande hachée": "🥩 Viande rouge (halal)",
    "Merguez bœuf": "🥩 Viande rouge (halal)",
    "Agneau halal": "🥩 Viande rouge (halal)",
}

def get_cat(role: str) -> str:
    for prefix, cat in ROLE_TO_CAT.items():
        if role.startswith(prefix):
            return cat
    return "🛒 Autres"

# Remplace chaque tuple (role, kws, qty, reason, tier,) par (role, kws, qty, reason, tier, "cat")
# Pattern: ligne se terminant par un entier (tier) suivi d'une virgule et éventuellement commentaire,
# à l'intérieur d'un tuple dont la première string est le rôle
def patch_nutrition_plan(text: str) -> str:
    lines = text.split("\n")
    out = []
    i = 0
    in_nutrition = False
    current_role = None

    while i < len(lines):
        line = lines[i]

        # Détecter début/fin du NUTRITION_PLAN
        if "NUTRITION_PLAN: list[tuple[" in line:
            in_nutrition = True
        if in_nutrition and "HYGIENE_PLAN: list[tuple[" in line:
            in_nutrition = False

        if in_nutrition:
            stripped = line.strip()
            # Capturer le rôle (première string du tuple)
            role_match = re.match(r'\(\s*$', stripped)
            if stripped == "(":
                # Prochain group de lignes = un tuple : récupérer rôle sur ligne suivante
                j = i + 1
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                if j < len(lines):
                    role_line = lines[j].strip()
                    rm = re.match(r'"([^"]+)"', role_line)
                    if rm:
                        current_role = rm.group(1)

            # Ligne : "    1," ou "    2," ou "    3," seule (le tier, dernière valeur du tuple)
            tier_match = re.match(r'^(\s+)([123]),\s*$', line)
            if tier_match and current_role and in_nutrition:
                indent = tier_match.group(1)
                tier = tier_match.group(2)
                cat = get_cat(current_role)
                # Remplacer "    N," par "    N, "catégorie","
                line = f'{indent}{tier}, "{cat}",'
                current_role = None

        out.append(line)
        i += 1

    return "\n".join(out)

patched = patch_nutrition_plan(src)

# Même chose pour HYGIENE_PLAN — toutes les entrées → "🧴 Hygiène & Entretien"
def patch_hygiene_plan(text: str) -> str:
    lines = text.split("\n")
    out = []
    in_hygiene = False
    i = 0

    while i < len(lines):
        line = lines[i]

        if "HYGIENE_PLAN: list[tuple[" in line:
            in_hygiene = True
        # Fin du bloc hygiene : la ligne "]" après la dernière entrée
        if in_hygiene and line.strip() == "]" and i > 0:
            in_hygiene = False

        if in_hygiene:
            tier_match = re.match(r'^(\s+)([123]),\s*$', line)
            if tier_match:
                indent = tier_match.group(1)
                tier = tier_match.group(2)
                line = f'{indent}{tier}, "🧴 Hygiène & Entretien",'

        out.append(line)
        i += 1

    return "\n".join(out)

patched = patch_hygiene_plan(patched)

# Mettre à jour la signature du type
patched = patched.replace(
    "NUTRITION_PLAN: list[tuple[str, list[str], float, str, int]] = [",
    "NUTRITION_PLAN: list[tuple[str, list[str], float, str, int, str]] = ["
)
patched = patched.replace(
    "HYGIENE_PLAN: list[tuple[str, list[str], float, str, int]] = [",
    "HYGIENE_PLAN: list[tuple[str, list[str], float, str, int, str]] = ["
)

open(PATH, "w", encoding="utf-8").write(patched)
print("Patch NUTRITION_PLAN OK")

# Vérifier syntaxe
import ast
ast.parse(patched)
print("Syntaxe Python OK")

# Compter les tuples patchés
count = patched.count('"🥦 Légumes frais"') + patched.count('"🌾 Pain & Céréales"') + \
        patched.count('"🐟 Poissons & Fruits de mer"') + patched.count('"🥩 Viande rouge (halal)"')
print(f"Catégories injectées (échantillon): {count} tuples")
