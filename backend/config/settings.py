"""
Django settings for TenderBee backend.
Supports Neon Serverless PostgreSQL with pooling, Celery, DRF, SimpleJWT, and multi-tenant isolation.
"""
import os
import sys
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent

# Ensure both backend/ and repo root are in python path
for p in (str(BASE_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Load environment variables
load_dotenv(REPO_ROOT / ".env")
load_dotenv()

# Security & Debug
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    os.environ.get("SECRET_KEY", "django-insecure-tenderbee-core-deterministic-eval-platform-key-2026"),
)
DEBUG = os.environ.get("DJANGO_DEBUG", os.environ.get("DEBUG", "True")).lower() in ("true", "1", "yes")

# Allowed Hosts: Support ALLOWED_HOSTS, DJANGO_ALLOWED_HOSTS, and Render's automatic host
raw_hosts = os.environ.get("ALLOWED_HOSTS") or os.environ.get("DJANGO_ALLOWED_HOSTS") or "*"
ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(",") if h.strip()]
render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_host and render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_host)
if "*" not in ALLOWED_HOSTS and ".onrender.com" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".onrender.com")

# Application definition
INSTALLED_APPS = [
    # Django core apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party apps
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",

    # TenderBee domain apps
    "apps.accounts.apps.AccountsConfig",
    "apps.tenders.apps.TendersConfig",
    "apps.rules.apps.RulesConfig",
    "apps.documents.apps.DocumentsConfig",
    "apps.verify.apps.VerifyConfig",
    "apps.evidence.apps.EvidenceConfig",
    "apps.audit.apps.AuditConfig",
    "apps.find.apps.FindConfig",
    "apps.prepare.apps.PrepareConfig",
]

try:
    import whitenoise  # noqa: F401
    HAS_WHITENOISE = True
except ImportError:
    HAS_WHITENOISE = False

MIDDLEWARE = [
    "apps.accounts.logging.RequestContextMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
]
if HAS_WHITENOISE:
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")
MIDDLEWARE.extend([
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.accounts.middleware.TenantContextMiddleware",
])

# Structured Logging Configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "security_context": {
            "()": "apps.accounts.logging.SecurityContextFilter",
        },
    },
    "formatters": {
        "structured": {
            "format": "[%(asctime)s] [%(levelname)s] [req:%(request_id)s] [user:%(user_id)s] [org:%(org_id)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["security_context"],
            "formatter": "structured",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("LOG_LEVEL", "INFO"),
    },
}

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database Configuration: Neon Serverless PostgreSQL with dual connections
# 1. DIRECT_URL: used for running migrations (session connection)
# 2. DATABASE_URL: used for application runtime (pooled connection)
is_migrating = any(arg in sys.argv for arg in ("migrate", "makemigrations"))
is_testing = any("test" in arg or "pytest" in arg for arg in sys.argv) or "pytest" in sys.modules
target_db_url = os.environ.get("DIRECT_URL") if is_migrating and os.environ.get("DIRECT_URL") else os.environ.get("DATABASE_URL")

# Short conn_max_age for serverless autoscaling / pooler suspension
conn_max_age = int(os.environ.get("CONN_MAX_AGE", 0))

if not is_testing and target_db_url and target_db_url.startswith("postgres") and "ep-sample" not in target_db_url:
    ssl_env = os.environ.get("DB_SSL_REQUIRE")
    if ssl_env is not None:
        db_ssl = ssl_env.lower() in ("true", "1", "yes")
    elif "sslmode=disable" in target_db_url or ("dpg-" in target_db_url and "render.com" not in target_db_url):
        # Render internal PostgreSQL private network does not use SSL
        db_ssl = False
    else:
        db_ssl = True

    DATABASES = {
        "default": dj_database_url.config(
            default=target_db_url,
            conn_max_age=conn_max_age,
            ssl_require=db_ssl,
        )
    }
else:
    # Graceful fallback to SQLite for local development and testing
    data_dir = REPO_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = data_dir / "tenderbee_dev.sqlite3"
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(sqlite_path),
        }
    }

# Custom User Model for Tenant Isolation & Organization Scoping
AUTH_USER_MODEL = "accounts.User"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images) & WhiteNoise Production Serving
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_ROOT.mkdir(parents=True, exist_ok=True)
if HAS_WHITENOISE:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# Media & Storage
MEDIA_URL = "/media/"
MEDIA_ROOT = REPO_ROOT / "data" / "media"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Password hashers: Enforce Argon2 as primary hasher
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

# Security Headers & Cookie Policies
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
CSRF_COOKIE_HTTPONLY = False  # Allows same-origin frontend / double-submit CSRF protection
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG

# Production SSL / HSTS enforcement when DEBUG is False
if not DEBUG:
    # Reverse proxy header: Render terminates SSL and forwards requests
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True").lower() in ("true", "1")
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# CORS Configuration: Restrict strictly to specified frontend origins + Vercel / Render domains
CORS_ALLOW_ALL_ORIGINS = False
raw_cors = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
CORS_ALLOWED_ORIGINS = [o.strip() for o in raw_cors.split(",") if o.strip()]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https:\/\/.*\.vercel\.app$",
    r"^https:\/\/.*\.onrender\.com$",
]

# CSRF Trusted Origins for Django 4+ (Mandatory for HTTPS POST/PUT from Vercel & Render)
raw_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in raw_csrf.split(",") if o.strip()]
for origin in CORS_ALLOWED_ORIGINS:
    if (origin.startswith("http://") or origin.startswith("https://")) and origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)
if "https://*.vercel.app" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append("https://*.vercel.app")
if "https://*.onrender.com" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append("https://*.onrender.com")

# REST Framework Configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.CookieJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/minute",
        "user": "1000/minute",
        "login": "10/minute",
        "refresh": "20/minute",
        "uploads": "30/minute",
        "external": "40/minute",
    },
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# SimpleJWT Configuration: Short-lived access token + rotating refresh token with blacklist
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.environ.get("JWT_ACCESS_MINUTES", 10))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", 7))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_USER_CLASS": "accounts.User",
}

# drf-spectacular configuration for OpenAPI generation
SPECTACULAR_SETTINGS = {
    "TITLE": "TenderBee Core API",
    "DESCRIPTION": "Deterministic Verification & Procurement Platform API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Celery Configuration
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
