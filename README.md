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
python scraper.py                          # con defaults
python scraper.py --config config.yaml     # config explícito
python scraper.py --db jobs.db             # DB explícita
python scraper.py --dry-run                # solo reporta, no escribe
python scraper.py --verbose                # logs en DEBUG
```

## Configuración

Editar `config.yaml` para cambiar términos de búsqueda, ubicaciones y
cantidad de resultados por búsqueda.

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
