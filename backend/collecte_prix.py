"""
collecte_prix.py — Collecte hebdomadaire des prix depuis les catalogues d'enseignes.

Pourquoi Claude et pas une expression régulière
-----------------------------------------------
La source publie un texte irrégulier. Deux lignes voisines d'un même catalogue :

    Bouilloire électrique Simpl : 129 DH
    Prix promotionnel : 24,50 DH au lieu de 27,50 DH

La première porte son nom, la seconde non — le produit se trouve deux lignes plus
haut. Une expression régulière qui cherche « <texte> : <nombre> DH » enregistre
donc « Prix promotionnel » comme nom de produit. C'est exactement l'origine des
entrées « À partir de », « Économie » et « promotionnel » trouvées en base.

Claude lit la page comme un humain : il rattache chaque prix à son produit,
distingue le prix barré du prix payé, et écarte les mentions de mise en page.
On lui demande du JSON strict, et on valide tout ce qu'il renvoie avant écriture.

Garde-fous
----------
- Le modèle ne décide jamais seul : tout prix hors bornes ou tout nom trop court
  est rejeté côté Python.
- Chaque relevé est INSÉRÉ avec sa date, jamais écrasé : l'historique alimente
  les courbes d'évolution et permet de revenir en arrière.
- Hors périmètre (électroménager, vaisselle, décoration) : filtré par le même
  classifieur que le catalogue, pour rester cohérent.

Usage :
    ANTHROPIC_API_KEY=sk-... DATABASE_URL=... python collecte_prix.py --simuler
    ANTHROPIC_API_KEY=sk-... DATABASE_URL=... python collecte_prix.py --appliquer
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import anthropic
import httpx
from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from recentre_catalogue import categorie

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

SOURCE = "https://hmizate.ma"
MODELE = "claude-haiku-4-5-20251001"

# Un prix de courses hors de ces bornes est une erreur de lecture, pas une affaire.
PRIX_MIN, PRIX_MAX = 0.5, 3000.0
NOM_MIN = 5

NAVIGATEUR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    )
}

ENSEIGNES = {
    "carrefour": "Carrefour", "marjane": "Marjane", "bim": "BIM",
    "atacadao": "Atacadão", "supeco": "Supeco", "aswak": "Aswak Assalam",
    "kazyon": "Kazyon", "label": "Label'Vie",
}

CONSIGNE = """Tu extrais les produits d'un texte de catalogue de supermarché marocain.

Réponds UNIQUEMENT par un tableau JSON, sans commentaire ni bloc de code :
[{"nom": "...", "marque": "...", "prix": 12.5, "prix_barre": 18.0, "format": "1 kg"}]

Règles :
- "prix" est le montant à payer. Si le texte dit « 24,50 DH au lieu de 27,50 DH »,
  alors prix = 24.5 et prix_barre = 27.5.
- Rattache chaque prix à son produit même s'ils sont sur des lignes différentes.
- N'invente jamais un produit. Si un prix n'a pas de produit identifiable, ignore-le.
- N'extrais JAMAIS les mentions de mise en page comme nom de produit :
  « Prix promotionnel », « À partir de », « Économie », « au lieu de », « Offre spéciale ».
- Ignore l'électroménager, la vaisselle, le textile et la décoration :
  ce catalogue ne sert qu'aux courses alimentaires, à l'hygiène et à l'entretien.
- "marque", "prix_barre" et "format" sont facultatifs : mets null si absent.
- Le nom doit être celui du produit seul, sans le prix ni la promotion.

Si le texte ne contient aucun produit exploitable, réponds []."""


@dataclass(frozen=True)
class Releve:
    nom: str
    marque: str | None
    prix: float
    prix_barre: float | None
    format: str | None
    enseigne: str
    source: str


def sans_accents(t: str) -> str:
    n = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in n if not unicodedata.combining(c))


def enseigne_de(url: str) -> str | None:
    u = sans_accents(url)
    for cle, nom in ENSEIGNES.items():
        if cle in u:
            return nom
    return None


async def catalogues_du_moment(client: httpx.AsyncClient, limite: int) -> list[str]:
    """
    Liens des catalogues en cours.

    La page d'index en liste bien plus que l'accueil. Les liens s'y écrivent
    tantôt en absolu, tantôt en relatif — les deux formes sont acceptées.
    """
    # Deux formes d'adresses cohabitent : « …-c20 » désigne une rubrique,
    # « …-n1090 » un catalogue précis. Seules les secondes portent des prix.
    catalogue = re.compile(
        r'href="(?:https?://hmizate\.ma)?(/deal/catalogue-[^"#?]*-n\d+)"'
    )
    rubrique = re.compile(
        r'href="(?:https?://hmizate\.ma)?(/deal/catalogue-[^"#?]*-c\d+)"'
    )

    vus: set[str] = set()
    sortie: list[str] = []
    rubriques: list[str] = []

    async def moissonner(url: str) -> None:
        try:
            r = await client.get(url, headers=NAVIGATEUR, timeout=45)
            r.raise_for_status()
        except Exception:
            return
        for lien in catalogue.findall(r.text):
            adresse = SOURCE + lien
            if adresse not in vus and enseigne_de(lien):
                vus.add(adresse)
                sortie.append(adresse)
        for lien in rubrique.findall(r.text):
            adresse = SOURCE + lien
            if adresse not in rubriques:
                rubriques.append(adresse)

    await moissonner(f"{SOURCE}/")
    await moissonner(f"{SOURCE}/deal/catalogues-c6")

    # Les rubriques les plus récentes d'abord : elles listent les catalogues en cours.
    for r in rubriques[:12]:
        if len(sortie) >= limite:
            break
        await moissonner(r)
        await asyncio.sleep(1)

    return sortie[:limite]


def texte_utile(html: str) -> str:
    """
    Texte de la page, réduit aux passages qui portent un prix.

    On se limite d'abord au bloc <article> : il contient tous les prix du
    catalogue, sans la colonne latérale de la boutique — dont les articles
    (compléments alimentaires, cosmétiques) seraient sinon pris pour des
    offres du catalogue. Moitié moins de texte, autant d'information.
    """
    bloc = re.search(r"(?is)<article[^>]*>(.*?)</article>", html)
    if bloc and len(bloc.group(1)) > 500:
        html = bloc.group(1)

    corps = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html)
    corps = re.sub(r"(?s)<[^>]+>", "\n", corps)
    corps = corps.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#039;", "'")

    lignes = [l.strip() for l in corps.split("\n")]
    lignes = [l for l in lignes if l]

    # On garde chaque ligne portant un prix ET ses deux voisines : le nom du
    # produit est fréquemment sur la ligne précédente.
    prix = re.compile(r"\d+([.,]\d+)?\s*(DH|Dh|dh|MAD)")
    retenues: set[int] = set()
    for i, ligne in enumerate(lignes):
        if prix.search(ligne):
            retenues.update({i - 2, i - 1, i, i + 1})
    garde = [lignes[i] for i in sorted(retenues) if 0 <= i < len(lignes)]
    return "\n".join(garde)[:14000]


async def extraire(claude: anthropic.AsyncAnthropic, texte: str) -> list[dict]:
    """Demande à Claude la liste structurée des produits."""
    reponse = await claude.messages.create(
        model=MODELE,
        max_tokens=4096,
        system=CONSIGNE,
        messages=[{"role": "user", "content": texte}],
    )
    brut = reponse.content[0].text.strip()
    brut = re.sub(r"^```(?:json)?|```$", "", brut, flags=re.MULTILINE).strip()
    try:
        donnees = json.loads(brut)
    except json.JSONDecodeError:
        return []
    return donnees if isinstance(donnees, list) else []


def valider(donnees: list[dict], enseigne: str, url: str) -> tuple[list[Releve], int]:
    """
    Filtre ce que le modèle renvoie. Rien n'entre en base sans passer ici :
    un modèle peut se tromper, la base ne doit pas en garder la trace.
    """
    gardes: list[Releve] = []
    rejets = 0
    for d in donnees:
        nom = str(d.get("nom") or "").strip()
        try:
            prix = float(d.get("prix"))
        except (TypeError, ValueError):
            rejets += 1
            continue

        if len(nom) < NOM_MIN or not (PRIX_MIN <= prix <= PRIX_MAX):
            rejets += 1
            continue
        if categorie(nom) not in ("alimentaire", "hygiene"):
            rejets += 1
            continue

        barre = d.get("prix_barre")
        try:
            barre = float(barre) if barre is not None else None
        except (TypeError, ValueError):
            barre = None
        if barre is not None and barre <= prix:
            barre = None      # un « prix barré » inférieur au prix payé est faux

        gardes.append(Releve(
            nom=nom[:200],
            marque=(str(d["marque"])[:100] if d.get("marque") else None),
            prix=round(prix, 2),
            prix_barre=round(barre, 2) if barre else None,
            format=(str(d["format"])[:50] if d.get("format") else None),
            enseigne=enseigne,
            source=url,
        ))
    return gardes, rejets


async def enregistrer(db: AsyncSession, releves: list[Releve]) -> tuple[int, int]:
    """
    Écrit les relevés. Un produit inconnu est créé ; un prix est toujours
    AJOUTÉ avec sa date, jamais écrasé — l'historique est la valeur du service.
    """
    nouveaux = ajoutes = 0
    aujourdhui = date.today()

    for r in releves:
        magasin = (await db.execute(sql(
            "SELECT id FROM stores WHERE name = :n ORDER BY id LIMIT 1"
        ), {"n": r.enseigne})).scalar()
        if magasin is None:
            continue

        produit = (await db.execute(sql(
            "SELECT id FROM products WHERE lower(name) = lower(:n) LIMIT 1"
        ), {"n": r.nom})).scalar()

        if produit is None:
            produit = (await db.execute(sql("""
                INSERT INTO products (name, brand, unit_size, slug, is_active,
                                      created_at, updated_at)
                VALUES (:n, :m, :f, :s, true, now(), now())
                RETURNING id
            """), {
                "n": r.nom, "m": r.marque, "f": r.format,
                "s": re.sub(r"[^a-z0-9]+", "-", sans_accents(r.nom)).strip("-")[:200],
            })).scalar()
            nouveaux += 1

        # Un seul relevé par produit, magasin et jour.
        deja = (await db.execute(sql("""
            SELECT 1 FROM prices
             WHERE product_id = :p AND store_id = :s AND recorded_at::date = :d
             LIMIT 1
        """), {"p": produit, "s": magasin, "d": aujourdhui})).scalar()
        if deja:
            continue

        # Convention de la table : « price » est le tarif normal, « promo_price »
        # ce que le client paie réellement. Sans prix barré, les deux se confondent.
        await db.execute(sql("""
            INSERT INTO prices (product_id, store_id, price, currency,
                                is_promo, promo_price, source, recorded_at)
            VALUES (:p, :s, :normal, 'MAD', :promo, :paye, 'scraper', now())
        """), {
            "p": produit, "s": magasin,
            "normal": r.prix_barre or r.prix,
            "promo": r.prix_barre is not None,
            "paye": r.prix if r.prix_barre else None,
        })
        ajoutes += 1

    await db.commit()
    return nouveaux, ajoutes


async def main() -> None:
    appliquer = "--appliquer" in sys.argv
    limite = 8
    for a in sys.argv:
        if a.startswith("--catalogues="):
            limite = int(a.split("=")[1])

    if not settings.ANTHROPIC_API_KEY:
        print("[STOP] ANTHROPIC_API_KEY absente — la collecte a besoin du modèle.")
        return

    claude = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    total_gardes = total_rejets = total_nouveaux = total_ajoutes = 0

    async with httpx.AsyncClient(follow_redirects=True) as web:
        catalogues = await catalogues_du_moment(web, limite)
        print(f"{len(catalogues)} catalogues en cours\n")

        async with Session() as db:
            for url in catalogues:
                enseigne = enseigne_de(url)
                try:
                    page = await web.get(url, headers=NAVIGATEUR, timeout=60)
                    page.raise_for_status()
                except Exception as e:
                    print(f"  [ERREUR] {enseigne:14} {type(e).__name__}")
                    continue

                texte = texte_utile(page.text)
                if len(texte) < 200:
                    print(f"  [VIDE]   {enseigne:14} aucun prix dans la page")
                    continue

                donnees = await extraire(claude, texte)
                gardes, rejets = valider(donnees, enseigne, url)
                total_gardes += len(gardes)
                total_rejets += rejets

                if appliquer and gardes:
                    n, a = await enregistrer(db, gardes)
                    total_nouveaux += n
                    total_ajoutes += a

                print(f"  {enseigne:14} {len(gardes):3} produits retenus · "
                      f"{rejets:3} écartés")
                for r in gardes[:3]:
                    barre = f" (au lieu de {r.prix_barre})" if r.prix_barre else ""
                    print(f"       {r.nom[:44]:46} {r.prix:>8.2f} MAD{barre}")

                await asyncio.sleep(2)      # on ne martèle pas la source

    print(f"\n[{'APPLIQUE' if appliquer else 'SIMULATION'}] "
          f"{total_gardes} relevés valides · {total_rejets} écartés")
    if appliquer:
        print(f"           {total_nouveaux} produits créés · {total_ajoutes} prix ajoutés")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
