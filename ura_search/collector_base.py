#!/usr/bin/env python3
"""collector_base.py — Núcleo determinista de URA-Search.

Descarga URLs, deduplica por SHA-256 y pHash, encola en .nervioso/ura_search/.
Sin IA. Sin modelos. Puro Python determinista.
"""

from __future__ import annotations
import argparse, asyncio, hashlib, json, logging, sqlite3, sys, time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import httpx

try:
    from PIL import Image; import imagehash; PHASH_OK = True
except ImportError: PHASH_OK = False

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
COLA_DIR = Path.home() / ".nervioso" / "ura_search" / "cola"
IMAGENES_DIR = DATA_DIR / "imagenes"
DB_PATH = DATA_DIR / "estado.db"
LOG_PATH = DATA_DIR / "collector.log"

TIMEOUT_CONNECT = 10.0; TIMEOUT_READ = 30.0; MAX_RETRIES = 3; MAX_CONTENT_MB = 50
USER_AGENT = "Mozilla/5.0 (compatible; URA-Search/1.0)"
PHASH_THRESHOLD = 10
IMAGE_MIME = {"image/jpeg","image/png","image/webp","image/gif","image/bmp","image/tiff"}
IMAGE_EXT = {".jpg",".jpeg",".png",".webp",".gif",".bmp",".tiff"}

DATA_DIR.mkdir(exist_ok=True, parents=True)
COLA_DIR.mkdir(exist_ok=True, parents=True)
IMAGENES_DIR.mkdir(exist_ok=True, parents=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)])
log = logging.getLogger("collector")

class URLStatus(str, Enum):
    PENDING="pending"; DOWNLOADED="downloaded"; DUPLICATE_EXACT="duplicate_exact"
    DUPLICATE_VISUAL="duplicate_visual"; FAILED="failed"; SKIPPED="skipped"

@dataclass
class CollectResult:
    url:str; status:URLStatus; sha256:str=""; phash:str=""; content_type:str=""
    content_size:int=0; cola_path:str=""; error:str=""; elapsed:float=0.0
    timestamp:str=field(default_factory=lambda:datetime.now(timezone.utc).isoformat())
    def is_new(self) -> bool: return self.status == URLStatus.DOWNLOADED

class EstadoDB:
    def __init__(self, db_path:Path=DB_PATH):
        self.db_path = db_path; self._init_db()
    def _connect(self):
        c = sqlite3.connect(self.db_path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=NORMAL")
        return c
    def _init_db(self):
        with self._connect() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS urls (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL, sha256 TEXT NOT NULL, phash TEXT DEFAULT '',
                    content_type TEXT DEFAULT '', content_size INTEGER DEFAULT 0,
                    status TEXT NOT NULL, categoria TEXT DEFAULT '', cola_path TEXT DEFAULT '',
                    error TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_sha256 ON urls(sha256);
                CREATE INDEX IF NOT EXISTS idx_status ON urls(status);
                CREATE TABLE IF NOT EXISTS phashes (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phash TEXT NOT NULL, url TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_phash ON phashes(phash);""")
    def sha256_exists(self, sha256:str)->bool:
        with self._connect() as c:
            return c.execute("SELECT id FROM urls WHERE sha256=?",(sha256,)).fetchone() is not None
    def url_exists(self, url:str)->bool:
        with self._connect() as c:
            r = c.execute("SELECT status FROM urls WHERE url=?",(url,)).fetchone()
            return r is not None
    def find_similar_phash(self, phash:str, threshold:int=PHASH_THRESHOLD)->Optional[str]:
        if not phash or not PHASH_OK: return None
        with self._connect() as c:
            rows = c.execute("SELECT phash,url FROM phashes").fetchall()
        try:
            h1 = imagehash.hex_to_hash(phash)
            for r in rows:
                if abs(h1 - imagehash.hex_to_hash(r["phash"])) <= threshold: return r["url"]
        except: pass
        return None
    def save_result(self, r:CollectResult, cat:str=""):
        n = datetime.now(timezone.utc).isoformat()
        with self._connect() as c:
            c.execute("""INSERT INTO urls(url,sha256,phash,content_type,content_size,status,categoria,cola_path,error,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
                sha256=excluded.sha256,phash=excluded.phash,status=excluded.status,
                cola_path=excluded.cola_path,error=excluded.error,updated_at=excluded.updated_at""",
                (r.url,r.sha256,r.phash,r.content_type,r.content_size,r.status.value,cat,r.cola_path,r.error,n,n))
            if r.phash:
                c.execute("INSERT OR IGNORE INTO phashes(phash,url,created_at) VALUES(?,?,?)",(r.phash,r.url,n))
    def get_stats(self)->dict:
        with self._connect() as c:
            t = c.execute("SELECT COUNT(*) FROM urls").fetchone()[0]
            s = c.execute("SELECT status,COUNT(*) as n FROM urls GROUP BY status").fetchall()
            ct = c.execute("SELECT categoria,COUNT(*) as n FROM urls GROUP BY categoria ORDER BY n DESC LIMIT 10").fetchall()
        return {"total":t,"by_status":{r["status"]:r["n"] for r in s},"by_categoria":{r["categoria"]:r["n"] for r in ct}}

def sha256_of(data:bytes)->str: return hashlib.sha256(data).hexdigest()
def phash_of(data:bytes)->str:
    if not PHASH_OK: return ""
    try:
        import io; return str(imagehash.phash(Image.open(io.BytesIO(data))))
    except: return ""
def is_image(url:str, ct:str)->bool:
    if ct in IMAGE_MIME: return True
    return Path(urlparse(url).path).suffix.lower() in IMAGE_EXT
def save_to_cola(url:str, content:bytes, ct:str, sha:str, cat:str, meta:dict)->Path:
    cat_dir = COLA_DIR / cat; cat_dir.mkdir(exist_ok=True, parents=True)
    ext = ".html"
    if "image" in ct: ext = "." + ct.split("/")[-1].split(";")[0]
    elif "pdf" in ct: ext = ".pdf"
    f = cat_dir / (sha[:16] + ext)
    f.write_bytes(content)
    (cat_dir / (sha[:16] + ".meta.json")).write_text(
        json.dumps({"url":url,"sha256":sha,"content_type":ct,"categoria":cat,
            "size":len(content),"timestamp":datetime.now(timezone.utc).isoformat(),**meta},
            indent=2,ensure_ascii=False), encoding="utf-8")
    return f

class Collector:
    def __init__(self, db:Optional[EstadoDB]=None):
        self.db = db or EstadoDB()
        self._client:Optional[httpx.AsyncClient] = None
    async def _get_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(connect=TIMEOUT_CONNECT,read=TIMEOUT_READ,write=10.0,pool=5.0),
                follow_redirects=True, headers={"User-Agent": USER_AGENT}, http2=True)
        return self._client
    async def close(self):
        if self._client and not self._client.is_closed: await self._client.aclose()
    async def collect(self, url:str, cat:str="general", meta:Optional[dict]=None, force:bool=False)->CollectResult:
        t0 = time.time(); meta=meta or {}
        if not force and self.db.url_exists(url):
            return CollectResult(url=url, status=URLStatus.SKIPPED, elapsed=time.time()-t0)
        content, ct, err = await self._download(url)
        if err:
            r = CollectResult(url=url, status=URLStatus.FAILED, error=err, elapsed=time.time()-t0)
            self.db.save_result(r,cat); return r
        sha = sha256_of(content)
        if not force and self.db.sha256_exists(sha):
            r = CollectResult(url=url, status=URLStatus.DUPLICATE_EXACT, sha256=sha, content_type=ct, content_size=len(content), elapsed=time.time()-t0)
            self.db.save_result(r,cat); return r
        ph = ""
        if is_image(url,ct):
            ph = phash_of(content)
            if ph:
                su = self.db.find_similar_phash(ph)
                if su and not force:
                    r = CollectResult(url=url, status=URLStatus.DUPLICATE_VISUAL, sha256=sha, phash=ph, content_type=ct, content_size=len(content), error=f"Sim:{su}", elapsed=time.time()-t0)
                    self.db.save_result(r,cat); return r
        if is_image(url,ct):
            (IMAGENES_DIR / (sha[:16] + Path(urlparse(url).path).suffix or ".jpg")).write_bytes(content)
        cp = save_to_cola(url,content,ct,sha,cat,meta)
        log.info("✅ Nuevo: %s → cola/%s/%s", url, cat, cp.name)
        r = CollectResult(url=url, status=URLStatus.DOWNLOADED, sha256=sha, phash=ph, content_type=ct, content_size=len(content), cola_path=str(cp), elapsed=time.time()-t0)
        self.db.save_result(r,cat); return r
    async def _download(self, url:str)->tuple[bytes,str,str]:
        client = await self._get_client(); last = ""
        for att in range(1, MAX_RETRIES+1):
            try:
                r = await client.get(url); r.raise_for_status()
                maxb = MAX_CONTENT_MB * 1024 * 1024
                if int(r.headers.get("content-length",0)) > maxb: return b"","","too large"
                c = r.content
                if len(c) > maxb: return b"","","too large"
                return c, r.headers.get("content-type","").split(";")[0].strip(), ""
            except httpx.HTTPStatusError as e:
                last = f"HTTP {e.response.status_code}"
                if 400 <= e.response.status_code < 500: break
            except httpx.TimeoutException: last = f"timeout ({att})"
            except httpx.ConnectError as e: last = f"conn: {e}"; break
            except Exception as e: last = str(e)
            if att < MAX_RETRIES: await asyncio.sleep(2**att)
        log.error("Falló tras %d intentos: %s", MAX_RETRIES, last); return b"","",last
    async def collect_batch(self, urls:list[dict], max_concurrent:int=10)->list[CollectResult]:
        sem = asyncio.Semaphore(max_concurrent)
        async def bound(x):
            async with sem: return await self.collect(url=x["url"], cat=x.get("categoria","general"), meta=x.get("metadata",{}))
        tasks = [bound(x) for x in urls]
        return [r for r in await asyncio.gather(*tasks, return_exceptions=True) if not isinstance(r, Exception)]

async def cmd_url(args):
    c = Collector()
    try:
        r = await c.collect(url=args.url, cat=args.categoria, force=args.force)
        print(f"\n{'='*50}\nURL: {r.url}\nEstado: {r.status.value}\nTiempo: {r.elapsed:.2f}s\n{'='*50}")
    finally: await c.close()

async def cmd_batch(args):
    f = Path(args.batch)
    if not f.exists(): log.error("No existe: %s", f); sys.exit(1)
    urls = json.loads(f.read_text())
    if isinstance(urls, dict): urls = urls.get("urls", [])
    log.info("Procesando %d URLs...", len(urls))
    c = Collector()
    try:
        rr = await c.collect_batch(urls, max_concurrent=args.workers)
    finally: await c.close()
    ok = sum(1 for r in rr if r.status==URLStatus.DOWNLOADED)
    de = sum(1 for r in rr if r.status==URLStatus.DUPLICATE_EXACT)
    dv = sum(1 for r in rr if r.status==URLStatus.DUPLICATE_VISUAL)
    fl = sum(1 for r in rr if r.status==URLStatus.FAILED)
    sk = sum(1 for r in rr if r.status==URLStatus.SKIPPED)
    print(f"\nResumen: {len(rr)} URLs — Nuevos:{ok} DupExact:{de} DupVisual:{dv} Fail:{fl} Skip:{sk}\n")

def cmd_status(args):
    s = EstadoDB().get_stats()
    print(f"\nTotal: {s['total']:,}")
    for st,n in s["by_status"].items(): print(f"  {st:20s}: {n}")
    for c,n in s["by_categoria"].items(): print(f"  {c:20s}: {n}")

def main():
    p = argparse.ArgumentParser()
    su = p.add_subparsers(dest="cmd")
    for cmd, h, f in [
        ("url","Una URL", lambda a: asyncio.run(cmd_url(a))),
        ("batch","Lote desde JSON", lambda a: asyncio.run(cmd_batch(a))),
        ("status","Estado DB", cmd_status),
    ]:
        sp = su.add_parser(cmd, help=h)
        if cmd=="url": sp.add_argument("--url",required=True); sp.add_argument("--categoria",default="general"); sp.add_argument("--force",action="store_true")
        if cmd=="batch": sp.add_argument("--batch",required=True); sp.add_argument("--workers",type=int,default=10)
        sp.set_defaults(func=f)
    a = p.parse_args()
    if hasattr(a,"func"): a.func(a)
    else: p.print_help()

if __name__ == "__main__": main()
