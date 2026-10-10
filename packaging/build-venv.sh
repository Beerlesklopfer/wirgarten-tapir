#!/usr/bin/env bash
# Builds the self-contained Tapir installation (bundled CPython, venv, app code,
# compiled translations, collected static files, mjml) under $TAPIR_PREFIX.
#
# The venv contains absolute paths, so this must run at the final install path
# (/opt/tapir) - i.e. as root inside a throwaway build container, never on a
# production host. debian/rules then copies the tree into the package.
set -euo pipefail

TAPIR_PREFIX="${TAPIR_PREFIX:-/opt/tapir}"
TAPIR_PYTHON_VERSION="${TAPIR_PYTHON_VERSION:-3.14}"
TAPIR_POETRY_VERSION="${TAPIR_POETRY_VERSION:-2.5.1}"
TAPIR_MJML_VERSION="${TAPIR_MJML_VERSION:-4.14.1}"
TAPIR_VERSION="${TAPIR_VERSION:-dev}"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -f "$SRC_DIR/dist/manifest.json" ]; then
    echo "dist/manifest.json missing - run 'pnpm install && pnpm run build' first." >&2
    exit 1
fi

rm -rf "$TAPIR_PREFIX"
mkdir -p "$TAPIR_PREFIX"

export UV_PYTHON_INSTALL_DIR="$TAPIR_PREFIX/python"
export UV_PYTHON_PREFERENCE=only-managed
export UV_NO_CACHE=1

echo ">>> Python $TAPIR_PYTHON_VERSION"
uv python install "$TAPIR_PYTHON_VERSION"
uv venv --python "$TAPIR_PYTHON_VERSION" "$TAPIR_PREFIX/venv"

echo ">>> Python dependencies"
requirements="$(mktemp)"
(cd "$SRC_DIR" && uvx --python "$TAPIR_PYTHON_VERSION" --from "poetry==$TAPIR_POETRY_VERSION" --with poetry-plugin-export \
    poetry export --format requirements.txt --extras bakery --output "$requirements")
uv pip install --python "$TAPIR_PREFIX/venv/bin/python" --require-hashes -r "$requirements"
rm -f "$requirements"

echo ">>> Application"
mkdir -p "$TAPIR_PREFIX/app"
cp -a "$SRC_DIR/manage.py" "$SRC_DIR/tapir" "$SRC_DIR/dist" "$TAPIR_PREFIX/app/"
find "$TAPIR_PREFIX/app" -name __pycache__ -prune -exec rm -rf {} +

cd "$TAPIR_PREFIX/app"
"$TAPIR_PREFIX/venv/bin/python" manage.py compilemessages
"$TAPIR_PREFIX/venv/bin/python" manage.py collectstatic --noinput

# Writable state lives outside /opt, see debian/tapir.postinst
rm -rf tapir/media tapir/filepond_temp_uploads tapir/filepond_stored_uploads
ln -s /var/lib/tapir/media tapir/media
ln -s /var/lib/tapir/filepond_temp_uploads tapir/filepond_temp_uploads
ln -s /var/lib/tapir/filepond_stored_uploads tapir/filepond_stored_uploads
ln -s /var/lib/tapir/emails_from_celery emails_from_celery
ln -s /etc/tapir/tapir.env .env.local

echo ">>> mjml $TAPIR_MJML_VERSION"
npm install --no-audit --no-fund --prefix "$TAPIR_PREFIX/mjml" "mjml@$TAPIR_MJML_VERSION"

echo "TAPIR_VERSION=$TAPIR_VERSION" > "$TAPIR_PREFIX/version.env"

"$TAPIR_PREFIX/venv/bin/python" -m compileall -q -j 0 "$TAPIR_PREFIX/app" "$TAPIR_PREFIX/venv" || true

echo ">>> Done: $(du -sh "$TAPIR_PREFIX" | cut -f1) in $TAPIR_PREFIX"
