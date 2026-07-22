# Job Scraper — Data Science / ML

Scrapea ofertas de empleo para roles de Data Scientist, ML Engineer y afines
desde múltiples fuentes, las normaliza a un schema único y las persiste en
SQLite con deduplicación automática.

## Fuentes

- **python-jobspy**: LinkedIn, Indeed, Glassdoor, ZipRecruiter
- **Adzuna API**: fuente complementaria

## Requisitos

- Python 3.11+
- Adzuna API credentials (opcional, pero recomendado)

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Variables de entorno

```bash
export ADZUNA_APP_ID="tu_app_id"
export ADZUNA_APP_KEY="tu_app_key"
```

## Uso

```bash
# Scrapear y guardar
python scraper.py

# Solo reportar sin escribir en DB
python scraper.py --dry-run

# Con más detalle en logs
python scraper.py --verbose
```

## Scoring semántico

Se puede puntuar las ofertas contra tu perfil personal (`profile.txt`) usando
un modelo multilingual de sentence-transformers que mide la similitud semántica
entre tu perfil y la descripción de cada oferta.

```bash
# Scrapear + puntuar ofertas nuevas (solo las no puntuadas)
python scraper.py --score

# Ajustar el umbral mínimo para el resumen (default 0.5)
python scraper.py --score --threshold 0.7

# Re-puntuar todas las ofertas (incluso las ya puntuadas)
python scraper.py --score --rescore-all
```

Los scores se persisten en la tabla `jobs` (columnas `match_score` y `scored_at`)
y son visibles desde la UI de Streamlit.

## Scraper avanzado

```bash
python scraper.py --config config.yaml     # config explícito
python scraper.py --db jobs.db             # DB explícita
```

## Configuración

Editar `config.yaml` para cambiar términos de búsqueda, ubicaciones,
cantidad de resultados por búsqueda y ruta del archivo de perfil.

## Interfaz Streamlit

Para revisar las ofertas scrapeadas con una UI interactiva:

```bash
streamlit run app.py
```

La ruta de `jobs.db` se puede configurar vía variable de entorno:

```bash
export JOBS_DB_PATH=/ruta/a/jobs.db
streamlit run app.py
```

### Filtros disponibles

- **Score mínimo** — slider para filtrar por `match_score` (las ofertas sin puntuar siempre se muestran)
- **Source** y **Location** — multiselect con valores únicos de la DB
- **Buscar en título/empresa** — texto libre, case-insensitive
- **Orden** — por score, fecha de publicación o fecha de scraping (descendente)

## Tests

```bash
pytest tests/ -v
```

## Estructura

```
.
├── app.py                # interfaz Streamlit para revisar ofertas
├── config.yaml           # términos de búsqueda y ubicaciones
├── requirements.txt
├── scraper.py            # entry point del scraper, orquesta todo
├── scoring.py            # scoring semántico con sentence-transformers
├── sources/
│   ├── jobspy_source.py
│   └── adzuna_source.py
├── ui/
│   └── data_loader.py    # carga cacheada de jobs.db a DataFrame
├── db.py                 # SQLite (insert, dedupe, query)
├── models.py             # schema normalizado (dataclass)
└── tests/
    ├── test_dedupe.py    # tests de lógica de dedupe
    └── test_scoring.py   # tests de scoring
```
