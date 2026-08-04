"""
Import des prix depuis waffar_959_produits.csv vers PrixMaroc.

Colonnes CSV : Produit ; Prix_DH ; Enseigne ; Date_Debut ; Date_Fin

Stratégie :
  1. Cherche le produit par nom (similarité ≥ 55%) → sinon le crée
  2. Cherche le magasin par enseigne (ILIKE %enseigne%)
  3. Insère un enregistrement Price (source = MANUAL)
  4. Si Date_Debut != Date_Fin → c'est une promo (is_promo = True)

Usage (depuis le répertoire backend) :
  docker exec -i prixmaroc-backend-1 python import_waffer_prices.py
"""
from __future__ import annotations
import asyncio
import csv
import io
import re
import sys
import unicodedata
from datetime import datetime, date, timezone
from difflib import SequenceMatcher
from pathlib import Path

# ── Path vers le CSV (monté dans le container si exécuté en dehors) ───────────
CSV_PATH = Path("/app/import_waffer_prices.csv")   # copié via stdin ou volume
THRESHOLD_PRODUCT = 0.55
THRESHOLD_STORE   = 0.50


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _parse_date(s: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


async def main():
    # Import ici pour éviter les problèmes si lancé hors container
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    import os

    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://prixmaroc:prixmaroc@db:5432/prixmaroc"
    )

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from app.models.product import Product
    from app.models.category import Category
    from app.models.store import Store
    from app.models.price import Price, PriceSource

    async with async_session() as db:
        # ── Charge produits et magasins ───────────────────────────────────────
        prod_res = await db.execute(
            sa.select(Product.id, Product.name).where(Product.is_active == True)
        )
        products = prod_res.fetchall()   # [(id, name)]
        prod_norm = [(r[0], _norm(r[1])) for r in products]

        store_res = await db.execute(
            sa.select(Store.id, Store.name, Store.city).where(Store.is_active == True)
        )
        stores = store_res.fetchall()   # [(id, name, city)]

        # ── Catégorie par défaut ──────────────────────────────────────────────
        default_cat_res = await db.execute(
            sa.select(Category).where(Category.slug == "divers").limit(1)
        )
        default_cat = default_cat_res.scalar_one_or_none()
        if not default_cat:
            default_cat = Category(name="Divers", slug="divers")
            db.add(default_cat)
            await db.flush()

        # ── Lit le CSV depuis stdin ou fichier ────────────────────────────────
        if not sys.stdin.isatty():
            raw = sys.stdin.buffer.read()
        elif CSV_PATH.exists():
            raw = CSV_PATH.read_bytes()
        else:
            print("ERREUR : fournir le CSV via stdin ou copier dans /app/import_waffer_prices.csv")
            return

        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = raw.decode("latin-1")

        first_line = content.split("\n")[0]
        sep = ";" if first_line.count(";") > first_line.count(",") else ","
        reader = csv.DictReader(io.StringIO(content), delimiter=sep)

        if not reader.fieldnames:
            print("ERREUR : CSV vide ou sans en-tête")
            return

        fmap = {f.strip().lower(): f for f in reader.fieldnames}

        def _get(row: dict, *cols: str) -> str | None:
            for col in cols:
                key = fmap.get(col)
                if key:
                    v = (row.get(key) or "").strip()
                    if v:
                        return v
            return None

        inserted = updated = skipped = created_products = 0
        errors: list[str] = []
        now = datetime.now(timezone.utc)

        rows = list(reader)
        print(f"Traitement de {len(rows)} lignes…\n")

        for line_num, row in enumerate(rows, start=2):
            product_name = _get(row, "produit", "product_name", "nom")
            if not product_name:
                skipped += 1
                continue

            price_str = _get(row, "prix_dh", "prix", "price", "prix_mad")
            if not price_str:
                skipped += 1
                errors.append(f"L{line_num}: prix manquant pour «{product_name}»")
                continue

            try:
                price_val = float(price_str.replace(",", ".").replace(" ", ""))
                if price_val <= 0:
                    raise ValueError
            except ValueError:
                skipped += 1
                errors.append(f"L{line_num}: prix invalide «{price_str}» pour «{product_name}»")
                continue

            store_name = _get(row, "enseigne", "store_name", "magasin")
            date_debut_str = _get(row, "date_debut", "date debut")
            date_fin_str   = _get(row, "date_fin", "date fin")

            date_debut = _parse_date(date_debut_str) if date_debut_str else None
            date_fin   = _parse_date(date_fin_str)   if date_fin_str   else None

            # Promo si date_debut != date_fin (catalogue hebdo)
            is_promo = (
                date_debut is not None and
                date_fin is not None and
                date_debut != date_fin
            )

            # ── Résolution produit ────────────────────────────────────────────
            q = _norm(product_name)
            best_id = None
            best_score = 0.0
            for pid, pnorm in prod_norm:
                score = _sim(q, pnorm)
                if score > best_score:
                    best_score = score
                    best_id = pid

            product_id: int
            if best_score >= THRESHOLD_PRODUCT and best_id:
                product_id = best_id
            else:
                # Crée le produit
                new_prod = Product(
                    name=product_name.strip(),
                    slug=re.sub(r"[-\s]+", "-",
                         re.sub(r"[^\w\s-]", "",
                         _norm(product_name)))[:120],
                    category_id=default_cat.id,
                    is_active=True,
                )
                db.add(new_prod)
                await db.flush()
                product_id = new_prod.id
                # Met à jour le cache local
                prod_norm.append((product_id, q))
                created_products += 1

            # ── Résolution magasin ────────────────────────────────────────────
            store_id: int | None = None
            if store_name:
                sq = _norm(store_name)
                best_sid = None
                best_sscore = 0.0
                for sid, sname, scity in stores:
                    score = _sim(sq, _norm(sname))
                    if score > best_sscore:
                        best_sscore = score
                        best_sid = sid
                if best_sscore >= THRESHOLD_STORE:
                    store_id = best_sid

            if not store_id:
                skipped += 1
                errors.append(f"L{line_num}: magasin introuvable «{store_name}» pour «{product_name}»")
                continue

            # ── Prix existant pour ce produit+magasin (MANUAL) ───────────────
            existing_res = await db.execute(
                sa.select(Price).where(
                    Price.product_id == product_id,
                    Price.store_id == store_id,
                    Price.source == PriceSource.MANUAL,
                ).order_by(Price.recorded_at.desc()).limit(1)
            )
            existing = existing_res.scalar_one_or_none()

            if existing:
                existing.price = round(price_val, 2)
                existing.is_promo = is_promo
                existing.promo_price = round(price_val, 2) if is_promo else None
                existing.promo_start = date_debut if is_promo else None
                existing.promo_end   = date_fin   if is_promo else None
                existing.recorded_at = now
                updated += 1
            else:
                db.add(Price(
                    product_id=product_id,
                    store_id=store_id,
                    price=round(price_val, 2),
                    currency="MAD",
                    is_promo=is_promo,
                    promo_price=round(price_val, 2) if is_promo else None,
                    promo_start=date_debut if is_promo else None,
                    promo_end=date_fin   if is_promo else None,
                    source=PriceSource.MANUAL,
                    recorded_at=now,
                ))
                inserted += 1

        await db.commit()

        # ── Invalide cache Redis ──────────────────────────────────────────────
        try:
            from app.utils.cache import cache
            await cache.invalidate_prefix("prixmaroc:prices:")
            await cache.invalidate_prefix("prixmaroc:products:search:")
            await cache.invalidate_prefix("prixmaroc:dashboard:")
        except Exception as e:
            print(f"  ⚠ Cache non invalidé : {e}")

    await engine.dispose()

    print("═" * 50)
    print(f"  ✅ Insérés      : {inserted}")
    print(f"  🔄 Mis à jour   : {updated}")
    print(f"  🆕 Produits créés: {created_products}")
    print(f"  ⏭  Ignorés      : {skipped}")
    if errors:
        print(f"\n  ⚠ {len(errors)} erreur(s) :")
        for e in errors[:20]:
            print(f"    {e}")
        if len(errors) > 20:
            print(f"    … et {len(errors)-20} autres.")
    print("═" * 50)


if __name__ == "__main__":
    asyncio.run(main())
