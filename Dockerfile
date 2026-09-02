FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/usr/local/bin:${PATH}"

WORKDIR /app

RUN groupadd --gid 1000 django && useradd --uid 1000 --gid django --create-home django

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt && \
    python -c "import gunicorn; print(gunicorn.__version__)"

COPY --chown=django:django . ./

# Static assets are part of the immutable application image. WhiteNoise serves
# them from STATIC_ROOT in the Gunicorn process.
RUN python manage.py collectstatic --noinput

USER django

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; request = urllib.request.Request('http://127.0.0.1:8000/healthz/', headers={'X-Forwarded-Proto': 'https'}); urllib.request.urlopen(request, timeout=3)" || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--limit-request-line", "8190", "--access-logfile", "-", "--error-logfile", "-"]
