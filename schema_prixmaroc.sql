-- =============================================================================
-- PRIXMAROC — Schéma PostgreSQL Complet
-- Version 1.0 | Architecte : Claude AI
-- =============================================================================
-- CONVENTIONS :
--   - Clés primaires : UUID (sécurité + scalabilité horizontale)
--   - Timestamps : TIMESTAMPTZ (timezone-aware, crucial pour le Maroc GMT+1)
--   - Soft delete : colonne deleted_at (jamais de DELETE physique sur données métier)
--   - Nommage : snake_case, tables au pluriel, FK = table_id
-- =============================================================================

-- Extensions nécessaires
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- génération UUID
CREATE EXTENSION IF NOT EXISTS "postgis";         -- géolocalisation GPS
CREATE EXTENSION IF NOT EXISTS "pg_trgm";         -- recherche floue sur noms produits
CREATE EXTENSION IF NOT EXISTS "unaccent";        -- recherche sans accents (arabe/français)

-- =============================================================================
-- 1. VILLES & RÉGIONS (référentiel géographique marocain)
-- =============================================================================
-- Justification : table dédiée plutôt qu'un simple VARCHAR ville,
-- permet de lier les magasins et utilisateurs à une zone géographique
-- cohérente et d'étendre aux régions/wilayas plus tard.

CREATE TABLE villes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nom             VARCHAR(100) NOT NULL,
    nom_ar          VARCHAR(100),                    -- nom en arabe
    region          VARCHAR(100),                    -- région administrative
    wilaya          VARCHAR(100),                    -- wilaya
    latitude        DECIMAL(10, 8),
    longitude       DECIMAL(11, 8),
    population      INTEGER,
    est_active      BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE villes IS 'Référentiel des villes marocaines. Utilisé pour filtrer magasins et utilisateurs.';

-- Villes principales pré-remplies
INSERT INTO villes (nom, nom_ar, region, latitude, longitude) VALUES
('Casablanca',  'الدار البيضاء', 'Casablanca-Settat',    33.5731, -7.5898),
('Rabat',       'الرباط',        'Rabat-Salé-Kénitra',   34.0209, -6.8416),
('Marrakech',   'مراكش',         'Marrakech-Safi',        31.6295, -7.9811),
('Fès',         'فاس',           'Fès-Meknès',            34.0181, -5.0078),
('Tanger',      'طنجة',          'Tanger-Tétouan-Al Hoceïma', 35.7595, -5.8340),
('Agadir',      'أكادير',        'Souss-Massa',           30.4278, -9.5981),
('Meknès',      'مكناس',         'Fès-Meknès',            33.8935, -5.5547),
('Oujda',       'وجدة',          'Oriental',              34.6867, -1.9114),
('Kénitra',     'القنيطرة',      'Rabat-Salé-Kénitra',   34.2610, -6.5802),
('Tétouan',     'تطوان',         'Tanger-Tétouan-Al Hoceïma', 35.5785, -5.3684),
('Salé',        'سلا',           'Rabat-Salé-Kénitra',   34.0365, -6.7979),
('Béni Mellal', 'بني ملال',      'Béni Mellal-Khénifra', 32.3373, -6.3498),
('El Jadida',   'الجديدة',       'Casablanca-Settat',    33.2316, -8.5007),
('Nador',       'الناظور',       'Oriental',              35.1681, -2.9287),
('Settat',      'سطات',          'Casablanca-Settat',    33.0010, -7.6166);

-- =============================================================================
-- 2. CATÉGORIES DE PRODUITS
-- =============================================================================

CREATE TABLE categories (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nom             VARCHAR(100) NOT NULL,
    nom_ar          VARCHAR(100),
    parent_id       UUID REFERENCES categories(id),  -- hiérarchie : Alimentation > Épicerie > Huiles
    icone_url       VARCHAR(255),
    ordre_affichage INTEGER DEFAULT 0,
    est_active      BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON COLUMN categories.parent_id IS 'Permet une hiérarchie 3 niveaux max : Grande catégorie > Sous-catégorie > Famille';

INSERT INTO categories (nom, nom_ar, ordre_affichage) VALUES
('Épicerie',          'البقالة',          1),
('Fruits & Légumes',  'الخضر والفواكه',   2),
('Boucherie & Volaille', 'اللحوم والدواجن', 3),
('Poissonnerie',      'السمك',            4),
('Produits Laitiers', 'منتجات الألبان',   5),
('Boulangerie',       'المخبوزات',        6),
('Boissons',          'المشروبات',        7),
('Hygiène & Beauté',  'النظافة والجمال',  8),
('Entretien Maison',  'منتجات المنزل',    9),
('Bébé & Enfant',     'الطفل',            10),
('Surgelés',          'المجمدات',         11),
('Épices & Condiments', 'البهارات',       12);

-- =============================================================================
-- 3. PRODUITS — Table centrale de l'application
-- =============================================================================
-- Justification des champs nutritionnels : par 100g (norme internationale)
-- permettant la comparaison équitable entre produits de conditionnements différents.
-- Source principale : Open Food Facts API (open source, données Maroc disponibles)

CREATE TABLE produits (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Identification
    barcode_ean         VARCHAR(14) UNIQUE,              -- code-barres EAN-8 ou EAN-13
    nom                 VARCHAR(255) NOT NULL,
    nom_ar              VARCHAR(255),                    -- nom en arabe
    marque              VARCHAR(100),
    description         TEXT,
    
    -- Catégorisation
    categorie_id        UUID REFERENCES categories(id),
    sous_categorie      VARCHAR(100),
    
    -- Conditionnement
    contenance          DECIMAL(10, 3),                  -- quantité (ex: 1.0, 0.5, 200)
    unite               VARCHAR(20),                     -- 'g', 'kg', 'ml', 'l', 'pièce'
    conditionnement     VARCHAR(50),                     -- 'bouteille', 'sachet', 'boîte'
    
    -- Informations nutritionnelles (pour 100g ou 100ml)
    -- Source : Open Food Facts — champs standardisés
    energie_kcal        DECIMAL(8, 2),                   -- calories (kcal/100g)
    proteines_g         DECIMAL(8, 2),                   -- protéines (g/100g)
    glucides_g          DECIMAL(8, 2),                   -- glucides totaux (g/100g)
    sucres_g            DECIMAL(8, 2),                   -- dont sucres (g/100g)
    lipides_g           DECIMAL(8, 2),                   -- lipides totaux (g/100g)
    graisses_saturees_g DECIMAL(8, 2),                   -- dont saturées (g/100g)
    fibres_g            DECIMAL(8, 2),                   -- fibres (g/100g)
    sel_g               DECIMAL(8, 2),                   -- sel (g/100g)
    
    -- Scores qualité
    nutri_score         CHAR(1) CHECK (nutri_score IN ('A','B','C','D','E')),
    nova_group          INTEGER CHECK (nova_group BETWEEN 1 AND 4), -- degré de transformation
    ecoscore            CHAR(1),                          -- score environnemental
    
    -- Régimes alimentaires (flags booléens pour filtrage rapide)
    est_halal           BOOLEAN DEFAULT FALSE,
    est_bio             BOOLEAN DEFAULT FALSE,
    est_vegetarien      BOOLEAN DEFAULT FALSE,
    est_vegan           BOOLEAN DEFAULT FALSE,
    sans_gluten         BOOLEAN DEFAULT FALSE,
    sans_lactose        BOOLEAN DEFAULT FALSE,
    
    -- Médias
    photo_url           VARCHAR(500),                    -- URL photo principale (stockée sur R2)
    photo_url_small     VARCHAR(500),                    -- miniature 200x200
    photos_urls         TEXT[],                          -- galerie (tableau d'URLs)
    
    -- Métadonnées
    source              VARCHAR(50) DEFAULT 'manual',    -- 'open_food_facts', 'ocr', 'manual', 'scraper'
    off_id              VARCHAR(100),                    -- ID Open Food Facts si importé
    est_verifie         BOOLEAN DEFAULT FALSE,           -- validé par un admin
    est_actif           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ                      -- soft delete
);

COMMENT ON TABLE produits IS 'Table centrale. Un produit = un article physique identifié par son barcode. Les prix sont dans prix_magasin.';
COMMENT ON COLUMN produits.energie_kcal IS 'Toujours pour 100g/100ml, pas pour la portion — permet comparaison équitable';
COMMENT ON COLUMN produits.nutri_score IS 'A=excellent, E=à limiter. Calculé selon règles officielles Santé Publique France';

-- Index produits
CREATE INDEX idx_produits_barcode     ON produits(barcode_ean) WHERE barcode_ean IS NOT NULL;
CREATE INDEX idx_produits_categorie   ON produits(categorie_id);
CREATE INDEX idx_produits_marque      ON produits(marque);
CREATE INDEX idx_produits_actif       ON produits(est_actif) WHERE est_actif = TRUE;
CREATE INDEX idx_produits_nutri       ON produits(nutri_score);
-- Index recherche textuelle floue (gin = Generalized Inverted Index, parfait pour pg_trgm)
CREATE INDEX idx_produits_nom_trgm    ON produits USING gin(nom gin_trgm_ops);
CREATE INDEX idx_produits_nom_ar_trgm ON produits USING gin(nom_ar gin_trgm_ops);

-- Trigger mise à jour automatique de updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_produits_updated_at
    BEFORE UPDATE ON produits
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- 4. ENSEIGNES (chaînes de distribution)
-- =============================================================================

CREATE TABLE enseignes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nom             VARCHAR(100) NOT NULL UNIQUE,    -- 'Marjane', 'Carrefour', etc.
    nom_court       VARCHAR(20),                     -- 'MRJ', 'CRF', 'LBV', 'BIM', 'ATC'
    logo_url        VARCHAR(500),
    couleur_hex     VARCHAR(7),                      -- couleur brand pour l'UI
    site_web        VARCHAR(255),
    url_catalogue   VARCHAR(255),                    -- URL pour scraping catalogue
    est_scrapable   BOOLEAN DEFAULT TRUE,
    scraper_config  JSONB,                           -- config CSS selectors pour scraper
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO enseignes (nom, nom_court, couleur_hex, site_web) VALUES
('Marjane',    'MRJ', '#E31837', 'https://www.marjane.ma'),
('Carrefour',  'CRF', '#007DC5', 'https://www.carrefour.ma'),
('Label''Vie', 'LBV', '#00A650', 'https://www.labelvie.ma'),
('BIM',        'BIM', '#FF6B00', 'https://www.bim.com.tr'),
('Atacadão',   'ATC', '#CC0000', 'https://www.atacadao.ma');

-- =============================================================================
-- 5. MAGASINS — Points de vente physiques géolocalisés
-- =============================================================================
-- Justification PostGIS : permet des requêtes "magasins dans un rayon de X km"
-- avec l'index spatial GIST, beaucoup plus performant qu'un calcul haversine manuel.

CREATE TABLE magasins (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    enseigne_id     UUID NOT NULL REFERENCES enseignes(id),
    ville_id        UUID REFERENCES villes(id),
    
    -- Identification
    nom             VARCHAR(200) NOT NULL,            -- 'Marjane Hay Riad'
    adresse         TEXT,
    quartier        VARCHAR(100),
    code_postal     VARCHAR(10),
    telephone       VARCHAR(20),
    
    -- Géolocalisation (PostGIS)
    latitude        DECIMAL(10, 8) NOT NULL,
    longitude       DECIMAL(11, 8) NOT NULL,
    localisation    GEOMETRY(POINT, 4326),            -- index spatial PostGIS
    
    -- Horaires (JSONB flexible pour gérer les exceptions)
    -- Format : {"lundi": {"open": "09:00", "close": "21:00"}, "vendredi": {...}}
    horaires        JSONB,
    
    -- Caractéristiques
    superficie_m2   INTEGER,
    has_parking     BOOLEAN DEFAULT TRUE,
    has_drive       BOOLEAN DEFAULT FALSE,
    est_ouvert_24h  BOOLEAN DEFAULT FALSE,
    
    -- Statut
    est_actif       BOOLEAN DEFAULT TRUE,
    date_ouverture  DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON COLUMN magasins.localisation IS 'Type PostGIS POINT pour les requêtes spatiales ST_DWithin (recherche par rayon)';
COMMENT ON COLUMN magasins.horaires IS 'JSONB pour flexibilité : horaires Ramadan, jours fériés, exceptions saisonnières';

-- Index spatial (GIST = optimal pour les géométries PostGIS)
CREATE INDEX idx_magasins_localisation ON magasins USING GIST(localisation);
CREATE INDEX idx_magasins_enseigne     ON magasins(enseigne_id);
CREATE INDEX idx_magasins_ville        ON magasins(ville_id);
CREATE INDEX idx_magasins_actif        ON magasins(est_actif) WHERE est_actif = TRUE;

-- Trigger pour synchroniser latitude/longitude → geometry PostGIS
CREATE OR REPLACE FUNCTION sync_localisation()
RETURNS TRIGGER AS $$
BEGIN
    NEW.localisation = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_magasins_localisation
    BEFORE INSERT OR UPDATE OF latitude, longitude ON magasins
    FOR EACH ROW EXECUTE FUNCTION sync_localisation();

-- =============================================================================
-- 6. PRIX ACTUELS — Snapshot du prix en temps réel par produit/magasin
-- =============================================================================
-- Justification design : on sépare prix "actuel" (requêtes comparaison rapides)
-- et "historique" (graphiques). La jointure prix_actuel seule est très rapide.
-- Contrainte UNIQUE sur (produit_id, magasin_id) : un seul prix courant par couple.

CREATE TABLE prix_actuel (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    produit_id      UUID NOT NULL REFERENCES produits(id) ON DELETE CASCADE,
    magasin_id      UUID NOT NULL REFERENCES magasins(id) ON DELETE CASCADE,
    
    -- Prix
    prix_normal     DECIMAL(10, 2) NOT NULL,          -- prix sans promotion (MAD)
    prix_promo      DECIMAL(10, 2),                   -- prix avec promotion si active
    prix_effectif   DECIMAL(10, 2) GENERATED ALWAYS AS (
                        COALESCE(prix_promo, prix_normal)
                    ) STORED,                          -- colonne calculée automatiquement
    
    -- Unité de prix (pour comparaison au kilo/litre)
    prix_au_kg      DECIMAL(10, 2),                   -- calculé si contenance connue
    
    -- Disponibilité
    est_disponible  BOOLEAN DEFAULT TRUE,
    stock_estime    VARCHAR(20),                       -- 'disponible', 'faible', 'rupture'
    
    -- Source et fraîcheur
    source          VARCHAR(30) DEFAULT 'scraper',     -- 'scraper', 'ocr', 'admin', 'user'
    derniere_maj    TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_prix_produit_magasin UNIQUE (produit_id, magasin_id)
);

COMMENT ON TABLE prix_actuel IS 'Un seul enregistrement par (produit, magasin). Mis à jour à chaque scraping/scan. Jointure ultra-rapide pour comparaison.';
COMMENT ON COLUMN prix_actuel.prix_effectif IS 'Colonne calculée PostgreSQL : retourne prix_promo si actif, sinon prix_normal. Pas de logique dans le code.';

CREATE INDEX idx_prix_actuel_produit  ON prix_actuel(produit_id);
CREATE INDEX idx_prix_actuel_magasin  ON prix_actuel(magasin_id);
CREATE INDEX idx_prix_actuel_effectif ON prix_actuel(prix_effectif);
CREATE INDEX idx_prix_actuel_maj      ON prix_actuel(derniere_maj DESC);

-- =============================================================================
-- 7. HISTORIQUE DES PRIX — Série temporelle pour les graphiques
-- =============================================================================
-- Justification : table séparée de prix_actuel pour ne pas alourdir les
-- comparaisons en temps réel. Partitionnement par mois recommandé en production
-- (PARTITION BY RANGE sur date_enregistrement) pour les grandes volumétries.

CREATE TABLE prix_historique (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    produit_id          UUID NOT NULL REFERENCES produits(id) ON DELETE CASCADE,
    magasin_id          UUID NOT NULL REFERENCES magasins(id) ON DELETE CASCADE,
    
    prix_normal         DECIMAL(10, 2) NOT NULL,
    prix_promo          DECIMAL(10, 2),
    est_en_promo        BOOLEAN DEFAULT FALSE,
    
    source              VARCHAR(30) DEFAULT 'scraper',
    date_enregistrement TIMESTAMPTZ DEFAULT NOW()
)
-- Prêt pour partitionnement futur (décommenter en prod avec > 1M de lignes)
-- PARTITION BY RANGE (date_enregistrement)
;

COMMENT ON TABLE prix_historique IS 'Série temporelle. Chaque changement de prix génère un enregistrement. Utilisé pour les graphiques 30/90 jours.';

CREATE INDEX idx_prix_hist_produit_date ON prix_historique(produit_id, date_enregistrement DESC);
CREATE INDEX idx_prix_hist_magasin      ON prix_historique(magasin_id);
CREATE INDEX idx_prix_hist_date         ON prix_historique(date_enregistrement DESC);

-- Fonction : insérer dans historique à chaque màj du prix actuel
CREATE OR REPLACE FUNCTION archive_prix_historique()
RETURNS TRIGGER AS $$
BEGIN
    -- N'archive que si le prix a vraiment changé
    IF (OLD.prix_normal != NEW.prix_normal OR 
        OLD.prix_promo IS DISTINCT FROM NEW.prix_promo) THEN
        INSERT INTO prix_historique (produit_id, magasin_id, prix_normal, prix_promo, est_en_promo, source)
        VALUES (NEW.produit_id, NEW.magasin_id, NEW.prix_normal, NEW.prix_promo,
                NEW.prix_promo IS NOT NULL, NEW.source);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_archive_prix
    AFTER UPDATE ON prix_actuel
    FOR EACH ROW EXECUTE FUNCTION archive_prix_historique();

-- =============================================================================
-- 8. PROMOTIONS — Offres limitées dans le temps
-- =============================================================================

CREATE TABLE promotions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    produit_id      UUID NOT NULL REFERENCES produits(id) ON DELETE CASCADE,
    magasin_id      UUID REFERENCES magasins(id),      -- NULL = promo nationale enseigne
    enseigne_id     UUID REFERENCES enseignes(id),
    
    -- Prix
    prix_normal     DECIMAL(10, 2) NOT NULL,
    prix_promo      DECIMAL(10, 2) NOT NULL,
    pourcentage_reduction DECIMAL(5, 2) GENERATED ALWAYS AS (
        ROUND((1 - prix_promo / prix_normal) * 100, 2)
    ) STORED,
    
    -- Durée
    date_debut      TIMESTAMPTZ NOT NULL,
    date_fin        TIMESTAMPTZ NOT NULL,
    
    -- Informations
    titre           VARCHAR(200),                       -- 'Promo Ramadan -30%'
    description     TEXT,
    conditions      TEXT,                               -- '2 achetés = 1 offert'
    
    -- Source
    source          VARCHAR(30) DEFAULT 'scraper',      -- 'catalogue', 'scraper', 'manuel'
    image_url       VARCHAR(500),
    
    est_active      BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT chk_promo_dates CHECK (date_fin > date_debut),
    CONSTRAINT chk_promo_prix CHECK (prix_promo < prix_normal)
);

COMMENT ON COLUMN promotions.pourcentage_reduction IS 'Calculé automatiquement. Ex: (1 - 35/50) * 100 = 30.00%';

CREATE INDEX idx_promos_produit    ON promotions(produit_id);
CREATE INDEX idx_promos_magasin    ON promotions(magasin_id);
CREATE INDEX idx_promos_dates      ON promotions(date_debut, date_fin);
CREATE INDEX idx_promos_active     ON promotions(est_active, date_fin) WHERE est_active = TRUE;

-- =============================================================================
-- 9. UTILISATEURS
-- =============================================================================

CREATE TABLE utilisateurs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Authentification
    email               VARCHAR(255) UNIQUE NOT NULL,
    telephone           VARCHAR(20) UNIQUE,
    mot_de_passe_hash   VARCHAR(255),                  -- bcrypt hash
    provider_auth       VARCHAR(20) DEFAULT 'email',   -- 'email', 'google', 'apple'
    provider_id         VARCHAR(255),                  -- ID externe OAuth
    
    -- Profil public
    prenom              VARCHAR(100),
    nom                 VARCHAR(100),
    photo_profil_url    VARCHAR(500),
    
    -- Profil foyer (impact direct sur les recommandations IA)
    nombre_personnes    SMALLINT DEFAULT 4 CHECK (nombre_personnes BETWEEN 1 AND 20),
    nb_adultes          SMALLINT DEFAULT 2,
    nb_enfants          SMALLINT DEFAULT 2,
    nb_seniors          SMALLINT DEFAULT 0,
    
    -- Budget
    budget_mensuel      DECIMAL(10, 2),                -- budget total courses/mois (MAD)
    -- JSONB pour budgets par catégorie : {"épicerie": 600, "hygiène": 150, ...}
    budget_categories   JSONB DEFAULT '{}',
    objectif_economie   DECIMAL(10, 2),                -- économies cibles/mois (MAD)
    
    -- Localisation
    ville_id            UUID REFERENCES villes(id),
    quartier            VARCHAR(100),
    latitude            DECIMAL(10, 8),
    longitude           DECIMAL(11, 8),
    rayon_deplacement_km SMALLINT DEFAULT 10,          -- distance max pour magasins
    
    -- Préférences
    langue              VARCHAR(5) DEFAULT 'fr'        -- 'fr', 'ar', 'darija'
                        CHECK (langue IN ('fr', 'ar', 'darija')),
    regime_alimentaire  TEXT[] DEFAULT '{}',           -- ['halal', 'bio', 'sans_gluten']
    magasins_preferes   UUID[],                        -- IDs magasins favoris
    
    -- Notifications
    notif_promos        BOOLEAN DEFAULT TRUE,
    notif_liste_rappel  BOOLEAN DEFAULT TRUE,
    notif_economie_hebdo BOOLEAN DEFAULT TRUE,
    notif_prix_baisse   BOOLEAN DEFAULT TRUE,
    heure_notif_liste   TIME DEFAULT '09:00',
    
    -- Rôle et statut
    role                VARCHAR(20) DEFAULT 'user'     -- 'user', 'admin', 'moderator'
                        CHECK (role IN ('user', 'admin', 'moderator')),
    est_actif           BOOLEAN DEFAULT TRUE,
    email_verifie       BOOLEAN DEFAULT FALSE,
    derniere_connexion  TIMESTAMPTZ,
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ
);

COMMENT ON COLUMN utilisateurs.nombre_personnes IS 'Impacte directement les quantités suggérées dans les listes générées par IA';
COMMENT ON COLUMN utilisateurs.regime_alimentaire IS 'Array PostgreSQL : filtre automatique des produits incompatibles (ex: porc si halal)';
COMMENT ON COLUMN utilisateurs.magasins_preferes IS 'IDs des magasins habituels. Utilisés en priorité dans les suggestions d itinéraires';

CREATE INDEX idx_users_email       ON utilisateurs(email);
CREATE INDEX idx_users_telephone   ON utilisateurs(telephone) WHERE telephone IS NOT NULL;
CREATE INDEX idx_users_ville       ON utilisateurs(ville_id);
CREATE INDEX idx_users_actif       ON utilisateurs(est_actif) WHERE est_actif = TRUE;

CREATE TRIGGER trg_utilisateurs_updated_at
    BEFORE UPDATE ON utilisateurs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- 10. TICKETS DE CAISSE (OCR)
-- =============================================================================
-- Justification : on stocke TOUT — l'image originale, le texte brut OCR,
-- et les items parsés dans une table séparée. Permet le re-traitement
-- si l'algorithme OCR s'améliore.

CREATE TABLE tickets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    utilisateur_id  UUID NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
    magasin_id      UUID REFERENCES magasins(id),      -- NULL si magasin non identifié
    enseigne_id     UUID REFERENCES enseignes(id),
    
    -- Image source
    image_url       VARCHAR(500) NOT NULL,              -- URL de l'image sur R2
    image_url_thumb VARCHAR(500),
    
    -- Résultat OCR brut
    texte_ocr_brut  TEXT,                              -- sortie brute de Tesseract
    
    -- Données parsées
    date_achat      TIMESTAMPTZ,
    heure_achat     TIME,
    numero_ticket   VARCHAR(50),
    caissier        VARCHAR(100),
    
    -- Totaux du ticket
    total_ttc       DECIMAL(10, 2),
    total_ht        DECIMAL(10, 2),
    tva             DECIMAL(10, 2),
    remises_totales DECIMAL(10, 2) DEFAULT 0,
    mode_paiement   VARCHAR(30),                        -- 'espèces', 'carte', 'mixte'
    
    -- Statut de traitement OCR
    statut_ocr      VARCHAR(20) DEFAULT 'en_attente'
                    CHECK (statut_ocr IN ('en_attente', 'traitement', 'succes', 'partiel', 'echec')),
    score_confiance DECIMAL(5, 2),                     -- % de confiance OCR (0-100)
    nb_items_detectes INTEGER DEFAULT 0,
    nb_items_valides  INTEGER DEFAULT 0,
    
    -- Économies calculées à la validation
    economie_potentielle DECIMAL(10, 2),               -- si acheté dans magasin le moins cher
    
    notes           TEXT,                              -- corrections manuelles utilisateur
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE tickets IS 'Chaque scan de ticket crée un enregistrement. Image conservée pour re-traitement OCR si amélioration algo.';
COMMENT ON COLUMN tickets.score_confiance IS 'Score 0-100 de Tesseract. < 60 = demander correction manuelle à l utilisateur';

CREATE INDEX idx_tickets_user      ON tickets(utilisateur_id);
CREATE INDEX idx_tickets_magasin   ON tickets(magasin_id);
CREATE INDEX idx_tickets_date      ON tickets(date_achat DESC);
CREATE INDEX idx_tickets_statut    ON tickets(statut_ocr);

-- =============================================================================
-- 11. ITEMS DE TICKETS — Détail ligne par ligne
-- =============================================================================

CREATE TABLE ticket_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id       UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    produit_id      UUID REFERENCES produits(id),      -- NULL si produit non reconnu
    
    -- Données brutes du ticket (telles que lues)
    nom_brut        VARCHAR(255) NOT NULL,             -- 'HUILE OLIVE OLEOR 1L'
    nom_normalise   VARCHAR(255),                      -- après nettoyage
    
    -- Quantité et prix
    quantite        DECIMAL(8, 3) DEFAULT 1,
    prix_unitaire   DECIMAL(10, 2) NOT NULL,
    prix_total      DECIMAL(10, 2) NOT NULL,
    remise          DECIMAL(10, 2) DEFAULT 0,
    
    -- Match avec BDD produits
    score_matching  DECIMAL(5, 2),                     -- score similarité nom (0-100)
    est_valide      BOOLEAN DEFAULT FALSE,             -- confirmé par l'utilisateur
    est_corrige     BOOLEAN DEFAULT FALSE,             -- l'utilisateur a corrigé
    
    -- Position dans le ticket
    ordre_ligne     INTEGER,
    
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON COLUMN ticket_items.score_matching IS 'Score de similarité pg_trgm entre nom_brut et nom produit BDD. < 70 = proposer sélection manuelle';

CREATE INDEX idx_ticket_items_ticket   ON ticket_items(ticket_id);
CREATE INDEX idx_ticket_items_produit  ON ticket_items(produit_id);
CREATE INDEX idx_ticket_items_valide   ON ticket_items(est_valide);

-- =============================================================================
-- 12. LISTES D'ACHATS
-- =============================================================================
-- Justification : 3 types (hebdo/bi-mensuel/mensuel) dans une même table
-- avec un discriminant de type. Évite la duplication de schéma.

CREATE TABLE listes_achats (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    utilisateur_id  UUID NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
    
    -- Type et période
    type_liste      VARCHAR(20) NOT NULL
                    CHECK (type_liste IN ('hebdomadaire', 'bi_mensuelle', 'mensuelle', 'personnalisee')),
    nom             VARCHAR(200),                      -- 'Liste semaine du 15 jan'
    
    -- Période couverte
    date_debut      DATE,
    date_fin        DATE,
    
    -- Budget
    budget_prevu    DECIMAL(10, 2),
    budget_total_estime DECIMAL(10, 2),               -- calculé depuis les items
    
    -- Génération IA
    est_generee_ia  BOOLEAN DEFAULT FALSE,
    prompt_ia       TEXT,                              -- prompt utilisé pour la génération
    version_ia      VARCHAR(20),                       -- version du modèle Claude utilisé
    
    -- Optimisation magasin
    magasin_conseille_id UUID REFERENCES magasins(id),
    magasin_2_id    UUID REFERENCES magasins(id),      -- si split en 2 magasins
    economie_estimee DECIMAL(10, 2),                   -- économie vs prix moyen marché
    
    -- Statut
    statut          VARCHAR(20) DEFAULT 'brouillon'
                    CHECK (statut IN ('brouillon', 'active', 'en_cours', 'completee', 'archivee')),
    
    -- Partage
    code_partage    VARCHAR(20) UNIQUE,                -- code pour partager via WhatsApp
    
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_listes_user        ON listes_achats(utilisateur_id);
CREATE INDEX idx_listes_type        ON listes_achats(type_liste);
CREATE INDEX idx_listes_statut      ON listes_achats(statut);
CREATE INDEX idx_listes_partage     ON listes_achats(code_partage) WHERE code_partage IS NOT NULL;

-- =============================================================================
-- 13. ITEMS DE LISTES
-- =============================================================================

CREATE TABLE liste_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    liste_id        UUID NOT NULL REFERENCES listes_achats(id) ON DELETE CASCADE,
    produit_id      UUID REFERENCES produits(id),
    
    -- Détails item
    nom_libre       VARCHAR(255),                      -- si produit non en BDD
    quantite        DECIMAL(8, 3) DEFAULT 1,
    unite           VARCHAR(20),
    categorie_id    UUID REFERENCES categories(id),
    
    -- Prix au moment de la création (snapshot)
    -- Justification : le prix peut changer entre création et courses
    prix_snapshot   DECIMAL(10, 2),                   -- prix au moment de la génération
    magasin_id      UUID REFERENCES magasins(id),     -- magasin recommandé pour cet item
    prix_au_magasin DECIMAL(10, 2),
    
    -- Statut en mode "En courses"
    est_coche       BOOLEAN DEFAULT FALSE,
    est_prioritaire BOOLEAN DEFAULT FALSE,
    note            TEXT,
    ordre           INTEGER DEFAULT 0,                 -- ordre d'affichage
    
    -- Source (ajouté manuellement ou généré par IA)
    source          VARCHAR(20) DEFAULT 'manuel'
                    CHECK (source IN ('manuel', 'ia', 'recurrence', 'promo')),
    
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON COLUMN liste_items.prix_snapshot IS 'Prix figé au moment de la génération. Si le vrai prix change, on compare avec ce snapshot pour calculer l écart.';

CREATE INDEX idx_liste_items_liste   ON liste_items(liste_id);
CREATE INDEX idx_liste_items_produit ON liste_items(produit_id);
CREATE INDEX idx_liste_items_coche   ON liste_items(est_coche);

-- =============================================================================
-- 14. HISTORIQUE DES ÉCONOMIES
-- =============================================================================
-- Justification : calculé et stocké à la validation de chaque ticket,
-- pas recalculé en temps réel. Alimente le dashboard KPIs.

CREATE TABLE economies (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    utilisateur_id      UUID NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
    ticket_id           UUID REFERENCES tickets(id),
    liste_id            UUID REFERENCES listes_achats(id),
    
    -- Période
    date_economie       DATE NOT NULL DEFAULT CURRENT_DATE,
    semaine             INTEGER,                       -- numéro de semaine ISO
    mois                INTEGER,
    annee               INTEGER,
    
    -- Montants
    montant_paye        DECIMAL(10, 2) NOT NULL,
    montant_prix_moyen  DECIMAL(10, 2),               -- ce qu'il aurait payé au prix moyen marché
    economie_realisee   DECIMAL(10, 2) NOT NULL,      -- = montant_prix_moyen - montant_paye
    economie_potentielle DECIMAL(10, 2),              -- si avait choisi le magasin le moins cher
    
    -- Source de l'économie
    source_economie     VARCHAR(30)                   -- 'promo', 'meilleur_magasin', 'liste_ia'
                        CHECK (source_economie IN ('promo', 'meilleur_magasin', 'liste_ia', 'autres')),
    nb_articles         INTEGER DEFAULT 0,
    magasin_id          UUID REFERENCES magasins(id),
    
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE economies IS 'Un enregistrement par ticket validé. Agrégé pour le dashboard (sum par semaine/mois/année).';

CREATE INDEX idx_economies_user        ON economies(utilisateur_id);
CREATE INDEX idx_economies_date        ON economies(date_economie DESC);
CREATE INDEX idx_economies_user_mois   ON economies(utilisateur_id, annee, mois);

-- Triggers auto pour remplir semaine/mois/année
CREATE OR REPLACE FUNCTION fill_economie_periode()
RETURNS TRIGGER AS $$
BEGIN
    NEW.semaine = EXTRACT(WEEK   FROM NEW.date_economie);
    NEW.mois    = EXTRACT(MONTH  FROM NEW.date_economie);
    NEW.annee   = EXTRACT(YEAR   FROM NEW.date_economie);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_economie_periode
    BEFORE INSERT ON economies
    FOR EACH ROW EXECUTE FUNCTION fill_economie_periode();

-- =============================================================================
-- 15. NOTIFICATIONS
-- =============================================================================

CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    utilisateur_id  UUID NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
    
    type_notif      VARCHAR(30) NOT NULL
                    CHECK (type_notif IN (
                        'promo_alerte',
                        'liste_rappel',
                        'economie_hebdo',
                        'prix_baisse',
                        'ticket_traite',
                        'suggestion_magasin'
                    )),
    
    titre           VARCHAR(200) NOT NULL,
    corps           TEXT,
    
    -- Lien vers l'objet concerné (polymorphique)
    objet_type      VARCHAR(30),                       -- 'produit', 'liste', 'ticket', 'promo'
    objet_id        UUID,
    
    -- Données additionnelles pour l'affichage
    data_json       JSONB DEFAULT '{}',
    
    -- Statut
    est_lue         BOOLEAN DEFAULT FALSE,
    est_envoyee     BOOLEAN DEFAULT FALSE,
    canal           VARCHAR(20) DEFAULT 'push'         -- 'push', 'email', 'sms'
                    CHECK (canal IN ('push', 'email', 'sms', 'inapp')),
    
    date_envoi      TIMESTAMPTZ,
    date_lecture    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notifs_user       ON notifications(utilisateur_id);
CREATE INDEX idx_notifs_non_lues   ON notifications(utilisateur_id, est_lue) WHERE est_lue = FALSE;
CREATE INDEX idx_notifs_type       ON notifications(type_notif);
CREATE INDEX idx_notifs_date       ON notifications(created_at DESC);

-- =============================================================================
-- 16. PRODUITS FAVORIS (Watchlist)
-- =============================================================================

CREATE TABLE produits_favoris (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    utilisateur_id  UUID NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
    produit_id      UUID NOT NULL REFERENCES produits(id) ON DELETE CASCADE,
    alerte_prix     DECIMAL(10, 2),                    -- notifier si prix descend sous ce seuil
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_favori UNIQUE (utilisateur_id, produit_id)
);

CREATE INDEX idx_favoris_user     ON produits_favoris(utilisateur_id);
CREATE INDEX idx_favoris_alerte   ON produits_favoris(alerte_prix) WHERE alerte_prix IS NOT NULL;

-- =============================================================================
-- 17. SESSIONS (Authentification JWT)
-- =============================================================================

CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    utilisateur_id  UUID NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
    refresh_token   VARCHAR(500) UNIQUE NOT NULL,
    device_info     JSONB,                             -- {'os': 'iOS', 'version': '17.0', ...}
    fcm_token       VARCHAR(500),                      -- Firebase Cloud Messaging token
    ip_address      INET,
    expire_le       TIMESTAMPTZ NOT NULL,
    est_active      BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON COLUMN sessions.fcm_token IS 'Token Firebase pour les notifications push. 1 token par appareil.';

CREATE INDEX idx_sessions_user    ON sessions(utilisateur_id);
CREATE INDEX idx_sessions_token   ON sessions(refresh_token);
CREATE INDEX idx_sessions_expire  ON sessions(expire_le) WHERE est_active = TRUE;

-- =============================================================================
-- 18. LOGS SCRAPING (Admin)
-- =============================================================================

CREATE TABLE scraping_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    enseigne_id     UUID REFERENCES enseignes(id),
    
    statut          VARCHAR(20) DEFAULT 'en_cours'
                    CHECK (statut IN ('en_cours', 'succes', 'partiel', 'echec', 'bloque_captcha')),
    
    nb_produits_trouves   INTEGER DEFAULT 0,
    nb_prix_mis_a_jour    INTEGER DEFAULT 0,
    nb_nouveaux_produits  INTEGER DEFAULT 0,
    nb_erreurs            INTEGER DEFAULT 0,
    
    duree_secondes  INTEGER,
    message_erreur  TEXT,
    details_json    JSONB,
    
    debut_scraping  TIMESTAMPTZ DEFAULT NOW(),
    fin_scraping    TIMESTAMPTZ
);

CREATE INDEX idx_scraping_logs_enseigne ON scraping_logs(enseigne_id);
CREATE INDEX idx_scraping_logs_date     ON scraping_logs(debut_scraping DESC);
CREATE INDEX idx_scraping_logs_statut   ON scraping_logs(statut);

-- =============================================================================
-- VUE UTILITAIRE : Comparaison prix pour un produit donné
-- =============================================================================
-- Exemple d'utilisation : SELECT * FROM v_comparaison_prix WHERE produit_id = '...'

CREATE VIEW v_comparaison_prix AS
SELECT
    pa.produit_id,
    p.nom                       AS produit_nom,
    p.barcode_ean,
    p.contenance,
    p.unite,
    m.id                        AS magasin_id,
    m.nom                       AS magasin_nom,
    e.nom                       AS enseigne_nom,
    e.couleur_hex               AS enseigne_couleur,
    vi.nom                      AS ville_nom,
    pa.prix_normal,
    pa.prix_promo,
    pa.prix_effectif,
    pa.prix_au_kg,
    pa.est_disponible,
    pa.derniere_maj,
    RANK() OVER (
        PARTITION BY pa.produit_id
        ORDER BY pa.prix_effectif ASC
    )                           AS rang_prix,                -- 1 = moins cher
    ROUND(
        (pa.prix_effectif - MIN(pa.prix_effectif) OVER (PARTITION BY pa.produit_id)) /
        NULLIF(MIN(pa.prix_effectif) OVER (PARTITION BY pa.produit_id), 0) * 100, 1
    )                           AS pct_au_dessus_min         -- % au-dessus du prix le plus bas
FROM prix_actuel pa
JOIN produits  p  ON pa.produit_id  = p.id  AND p.est_actif = TRUE
JOIN magasins  m  ON pa.magasin_id  = m.id  AND m.est_actif = TRUE
JOIN enseignes e  ON m.enseigne_id  = e.id
LEFT JOIN villes vi ON m.ville_id  = vi.id
WHERE pa.est_disponible = TRUE;

COMMENT ON VIEW v_comparaison_prix IS 'Vue principale pour l écran de comparaison. Retourne tous les prix avec rang et % au-dessus du moins cher.';

-- =============================================================================
-- VUE UTILITAIRE : Dashboard KPIs utilisateur
-- =============================================================================

CREATE VIEW v_dashboard_utilisateur AS
SELECT
    u.id                                AS utilisateur_id,
    u.prenom,
    -- Économies ce mois
    COALESCE(SUM(e.economie_realisee) FILTER (
        WHERE e.mois = EXTRACT(MONTH FROM NOW())
        AND   e.annee = EXTRACT(YEAR FROM NOW())
    ), 0)                               AS economie_mois_actuel,
    -- Économies année en cours
    COALESCE(SUM(e.economie_realisee) FILTER (
        WHERE e.annee = EXTRACT(YEAR FROM NOW())
    ), 0)                               AS economie_annee,
    -- Stats tickets
    COUNT(DISTINCT t.id)                AS total_tickets_scannes,
    COUNT(DISTINCT t.id) FILTER (
        WHERE t.created_at >= NOW() - INTERVAL '30 days'
    )                                   AS tickets_30_derniers_jours,
    -- Produits suivis
    COUNT(DISTINCT pf.produit_id)       AS nb_produits_favoris,
    -- Score économe (0-100) basé sur ratio économies/dépenses
    LEAST(100, ROUND(
        COALESCE(SUM(e.economie_realisee), 0) /
        NULLIF(COALESCE(SUM(e.montant_paye), 0) + COALESCE(SUM(e.economie_realisee), 0), 0)
        * 200, 0
    ))                                  AS score_econome
FROM utilisateurs u
LEFT JOIN economies e          ON e.utilisateur_id = u.id
LEFT JOIN tickets t            ON t.utilisateur_id = u.id AND t.statut_ocr = 'succes'
LEFT JOIN produits_favoris pf  ON pf.utilisateur_id = u.id
WHERE u.est_actif = TRUE
GROUP BY u.id, u.prenom;

COMMENT ON VIEW v_dashboard_utilisateur IS 'Agrégats pour le dashboard. Requête unique pour tous les KPIs. Cache Redis recommandé (TTL 30 min).';

-- =============================================================================
-- FIN DU SCHÉMA
-- =============================================================================
-- Récapitulatif des tables :
--   1. villes              — référentiel géographique Maroc
--   2. categories          — hiérarchie produits (3 niveaux)
--   3. produits            — catalogue central (nutritionnel + médias)
--   4. enseignes           — chaînes GMS (Marjane, Carrefour, etc.)
--   5. magasins            — points de vente géolocalisés (PostGIS)
--   6. prix_actuel         — snapshot prix temps réel (unique/produit/magasin)
--   7. prix_historique     — série temporelle pour graphiques
--   8. promotions          — offres limitées dans le temps
--   9. utilisateurs        — profil complet (foyer, budget, préférences)
--  10. tickets             — scans OCR (image + résultat parsé)
--  11. ticket_items        — lignes détail de chaque ticket
--  12. listes_achats       — listes hebdo/mensuelle/personnalisée
--  13. liste_items         — produits dans les listes
--  14. economies           — historique des économies calculées
--  15. notifications       — push/email/sms
--  16. produits_favoris    — watchlist avec alerte prix
--  17. sessions            — JWT refresh tokens + FCM tokens
--  18. scraping_logs       — audit des scraping admin
-- + 2 vues : v_comparaison_prix, v_dashboard_utilisateur
