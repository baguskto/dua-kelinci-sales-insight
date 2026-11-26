"""Authentication (local accounts with argon2, Microsoft Entra ID via OIDC) and role-based access.

Roles fit the people named in the job brief:
- head_of_sales: all regions, all brands
- head_of_region: only the regions listed on the account
- brand_manager: only the brands listed on the account
- admin: all data, plus upload and settings

Scope is enforced in the data layer (analytics.Scope.apply) for the UI, the API and the chat tools.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlencode

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from dk_sales.analytics import Scope

ROLES = ("head_of_sales", "head_of_region", "brand_manager", "admin")
ROLE_LABELS = {
    "head_of_sales": "Head of Sales",
    "head_of_region": "Head of Region",
    "brand_manager": "Brand Manager",
    "admin": "Admin",
}
_hasher = PasswordHasher()
# A real hash of a random value, used to spend the same time on unknown usernames.
_DUMMY_HASH = _hasher.hash(secrets.token_hex(16))


class AuthError(Exception):
    pass


@dataclass
class User:
    username: str
    display_name: str
    roles: list[str]
    regions: list[str] = field(default_factory=list)
    brands: list[str] = field(default_factory=list)
    auth_source: str = "local"

    def has(self, role: str) -> bool:
        return role in self.roles

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles

    def can_upload(self) -> bool:
        return self.is_admin

    def can_send_telegram(self) -> bool:
        return bool(set(self.roles) & {"head_of_sales", "head_of_region", "brand_manager", "admin"})

    def scope(self) -> Scope:
        if self.has("admin") or self.has("head_of_sales"):
            return Scope(label="Semua region dan brand")
        regions = frozenset(self.regions) if self.has("head_of_region") else None
        brands = frozenset(self.brands) if self.has("brand_manager") else None
        if regions is None and brands is None:
            # A user without a usable role sees nothing rather than everything.
            return Scope(regions=frozenset(), brands=frozenset(), label="Tanpa akses data")
        parts = []
        if regions is not None:
            parts.append("Region " + ", ".join(sorted(regions)))
        if brands is not None:
            parts.append("Brand " + ", ".join(sorted(brands)))
        return Scope(regions=regions, brands=brands, label="; ".join(parts))

    def to_session(self) -> dict:
        return asdict(self)

    @classmethod
    def from_session(cls, d: dict) -> User:
        return cls(**{k: d[k] for k in ("username", "display_name", "roles", "regions", "brands", "auth_source") if k in d})


DEV_USER = User(username="lokal", display_name="Local user", roles=["admin", "head_of_sales"], auth_source="dev")


# ---------------------------------------------------------------------------
# local accounts


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def load_local_users(path: Path) -> dict[str, dict]:
    data = json.loads(Path(path).read_text())
    users = {}
    for u in data["users"]:
        bad = set(u.get("roles", [])) - set(ROLES)
        if bad:
            raise AuthError(f"peran tidak dikenal untuk {u['username']}: {sorted(bad)}")
        users[u["username"].lower()] = u
    return users


def verify_local(users: dict[str, dict], username: str, password: str) -> User:
    rec = users.get(username.strip().lower())
    try:
        _hasher.verify(rec["password_hash"] if rec else _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        raise AuthError("Nama pengguna atau kata sandi salah.") from None
    if rec is None:
        raise AuthError("Nama pengguna atau kata sandi salah.")
    return User(
        username=rec["username"],
        display_name=rec.get("display_name", rec["username"]),
        roles=list(rec["roles"]),
        regions=list(rec.get("regions", [])),
        brands=list(rec.get("brands", [])),
        auth_source="local",
    )


class LoginThrottle:
    """Lock a username for a while after repeated failures (in-memory, per process)."""

    def __init__(self, max_failures: int = 5, window_s: int = 900):
        self.max_failures = max_failures
        self.window_s = window_s
        self._fails: dict[str, list[float]] = {}

    def locked(self, key: str) -> bool:
        now = time.monotonic()
        fails = [t for t in self._fails.get(key, []) if now - t < self.window_s]
        self._fails[key] = fails
        return len(fails) >= self.max_failures

    def fail(self, key: str) -> None:
        self._fails.setdefault(key, []).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._fails.pop(key, None)


# ---------------------------------------------------------------------------
# Microsoft Entra ID (OIDC authorization code flow with PKCE)


def entra_endpoints(tenant: str) -> dict[str, str]:
    base = f"https://login.microsoftonline.com/{tenant}"
    return {
        "authorize": f"{base}/oauth2/v2.0/authorize",
        "token": f"{base}/oauth2/v2.0/token",
        "jwks": f"{base}/discovery/v2.0/keys",
        "issuer": f"{base}/v2.0",
    }


def oidc_start(settings) -> tuple[str, dict]:
    """Returns (redirect URL, values to keep in the session)."""
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = {
        "client_id": settings.oidc_client_id,
        "response_type": "code",
        "redirect_uri": settings.oidc_redirect_uri,
        "response_mode": "query",
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = entra_endpoints(settings.oidc_tenant_id)["authorize"] + "?" + urlencode(params)
    return url, {"state": state, "nonce": nonce, "verifier": verifier}


def map_entra_roles(claims: dict, role_claim: str = "roles") -> User:
    """Map Entra app roles to app roles.

    App roles defined in the Entra app registration:
      HeadOfSales, Admin, HeadOfRegion.<Region tanpa spasi>, BrandManager.<Brand tanpa spasi>
    e.g. HeadOfRegion.JawaBarat, BrandManager.KacangDuaKelinci.
    """
    from dk_sales import config

    region_by_key = {r.replace(" ", "").lower(): r for r in config.CANONICAL_REGIONS}
    roles: set[str] = set()
    regions: set[str] = set()
    brands: set[str] = set()
    for value in claims.get(role_claim, []) or []:
        name, _, arg = str(value).partition(".")
        key = name.lower()
        if key == "headofsales":
            roles.add("head_of_sales")
        elif key == "admin":
            roles.add("admin")
        elif key == "headofregion" and arg.lower() in region_by_key:
            roles.add("head_of_region")
            regions.add(region_by_key[arg.lower()])
        elif key == "brandmanager" and arg:
            roles.add("brand_manager")
            brands.add(_brand_from_key(arg))
    if not roles:
        raise AuthError("Akun ini belum diberi peran di aplikasi. Hubungi admin.")
    return User(
        username=str(claims.get("preferred_username") or claims.get("oid") or claims.get("sub")),
        display_name=str(claims.get("name") or claims.get("preferred_username") or "Pengguna"),
        roles=sorted(roles),
        regions=sorted(regions),
        brands=sorted(brands),
        auth_source="entra",
    )


KNOWN_BRANDS = ["Kacang Dua Kelinci", "Sukro", "Tos Tos", "Tic Tac", "Deka", "Pilus", "Usagi", "Roni"]


def _brand_from_key(arg: str) -> str:
    for b in KNOWN_BRANDS:
        if b.replace(" ", "").lower() == arg.lower():
            return b
    return arg


def oidc_finish(settings, params: dict, saved: dict, http_post=None, jwks_client=None) -> User:
    """Validate state, exchange the code, verify the id_token signature, issuer, audience and nonce."""
    import jwt  # optional dependency group "oidc"

    if not saved or params.get("state") != saved.get("state"):
        raise AuthError("State login tidak cocok. Ulangi login.")
    if "error" in params:
        raise AuthError("Login Microsoft dibatalkan atau ditolak.")
    ep = entra_endpoints(settings.oidc_tenant_id)
    if http_post is None:
        import httpx

        def http_post(url, data):
            return httpx.post(url, data=data, timeout=10).json()

    token = http_post(
        ep["token"],
        {
            "client_id": settings.oidc_client_id,
            "client_secret": settings.oidc_client_secret,
            "grant_type": "authorization_code",
            "code": params.get("code", ""),
            "redirect_uri": settings.oidc_redirect_uri,
            "code_verifier": saved["verifier"],
        },
    )
    id_token = token.get("id_token")
    if not id_token:
        raise AuthError("Login Microsoft gagal (tidak ada id_token).")
    jwks_client = jwks_client or jwt.PyJWKClient(ep["jwks"])
    key = jwks_client.get_signing_key_from_jwt(id_token).key
    claims = jwt.decode(id_token, key, algorithms=["RS256"], audience=settings.oidc_client_id, issuer=ep["issuer"])
    if claims.get("nonce") != saved.get("nonce"):
        raise AuthError("Nonce login tidak cocok.")
    return map_entra_roles(claims, settings.oidc_role_claim)
