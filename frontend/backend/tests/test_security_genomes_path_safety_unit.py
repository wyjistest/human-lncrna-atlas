import pytest
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from app.mounts.genomes import GenomeFileWhitelistMiddleware


pytestmark = pytest.mark.unit


async def _ok_app(scope, receive, send):
    if scope["type"] != "http":  # pragma: no cover
        return
    await PlainTextResponse("OK")(scope, receive, send)


def test_genomes_whitelist_allows_known_extensions():
    client = TestClient(GenomeFileWhitelistMiddleware(_ok_app))

    # Root path is allowed (directory listing is handled by StaticFiles; middleware should not block it).
    assert client.get("/").status_code == 200

    # Known genome file extensions should pass the whitelist.
    assert client.get("/hg19.fa").status_code == 200
    assert client.get("/panTro5.2bit").status_code == 200
    assert client.get("/cytoBand.panTro5.txt.gz").status_code == 200
    assert client.get("/tracks/repeatmasker_human.bb").status_code == 200
    assert client.get("/hg19.fa.bgz").status_code == 200


def test_genomes_blocks_dotfiles_and_traversal_defense_in_depth():
    client = TestClient(GenomeFileWhitelistMiddleware(_ok_app))

    # Block dotfiles (even if extension would otherwise be allowed, e.g., ".env.gz").
    assert client.get("/.env.gz").status_code == 403
    assert client.get("/.hidden.fa").status_code == 403
    assert client.get("/dir/.hidden.fa").status_code == 403

    # Block traversal-like segments (StaticFiles would block too; this is an early deny).
    #
    # Note: HTTP clients may normalize "/../" away before it reaches the ASGI app,
    # so we assert the helper behavior directly.
    assert not GenomeFileWhitelistMiddleware._is_safe_static_path("/../secret.fa")
    assert not GenomeFileWhitelistMiddleware._is_safe_static_path("/dir/../secret.fa")

    # Percent-encoded traversal/dotfile bypass attempts.
    assert not GenomeFileWhitelistMiddleware._is_safe_static_path("/%2e%2e/secret.fa")
    assert not GenomeFileWhitelistMiddleware._is_safe_static_path("/dir/%2e%2e/secret.fa")
    assert not GenomeFileWhitelistMiddleware._is_safe_static_path("/%2eenv.gz")
    assert not GenomeFileWhitelistMiddleware._is_safe_static_path("/dir/%2ehidden.fa")


def test_genomes_blocks_suspicious_compressed_files():
    client = TestClient(GenomeFileWhitelistMiddleware(_ok_app))

    # Block generic ".gz" without a known inner extension (reduces accidental exposure risk).
    assert client.get("/secrets.gz").status_code == 403

    # Block compressed scripts/configs even though ".gz" is broadly used for genome assets.
    assert client.get("/script.py.gz").status_code == 403
    assert client.get("/config.yaml.gz").status_code == 403
