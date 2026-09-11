"""
Kalıcı ajan terminali prototipi (Faz 11-F spike) — `claude --bg` sarmalayıcısı.

Neden ayrı modül
----------------
Mevcut köprüler (`claude_bridge`, `agy_bridge`) süreci Entropy'nin ömrüne
bağlar: uygulama kapanınca `Popen` çocuğu da ölür. `claude --bg` ise oturumu
CLI'ın kendi arka plan servisine (daemon) devreder; süreç Entropy'den bağımsız
yaşar, uygulama yeniden açıldığında `claude agents --json` ile geri bulunur.
Bu modül o yolu köprülere DOKUNMADAN prototipler: burada üretilen bilgi
11-C oturum deposuyla birleşene kadar deneysel sayılır.

Ölçülmüş CLI sözleşmesi (2026-09-10, CLI 2.1.265 — bkz. spike raporu)
---------------------------------------------------------------------
1. `--bg` ile `-p/--print` ÇAKIŞIR. CLI'ın kendi hata metni:
   "--bg and --print conflict: --print never starts the interactive session
   that `claude agents` attaches to". İstem POZİSYONEL verilir.
2. `--output-format stream-json` sessizce yutulur ve iş künyesine `intent`
   olarak sızar; `--bg` ile GÖNDERİLMEZ. Çıktı stdout'tan değil diskten okunur.
3. `--session-id` yok sayılır ("--bg manages the session id"). Kimliği CLI
   verir; uuid5 ile önden atama MÜMKÜN DEĞİL, dönen kısa kimlik saklanır.
4. İzole kip bayrakları (`--system-prompt-file`, `--strict-mcp-config`,
   `--setting-sources ""`, `--tools`, `--permission-mode`, `--add-dir`)
   kabul edilir ve işin `respawnFlags` alanına KALICI yazılır.
5. Takip mesajı: canlı bir oturuma `--bg --resume <sid> "<metin>"` KOPYA
   açar (yeni kimlik, kaydedilmiş bayraklar KAYBOLUR → izolasyon çöker,
   ölçülen bedel 44,6k jeton). Doğru sıra: `claude stop <id>` →
   `claude --bg --resume <sid> "<metin>"` **bayraksız**. CLI o zaman
   "woke session <id> with its saved options" der, kimlik ve izolasyon korunur.
6. `claude logs <id>` yapılandırılmamış bir PTY ekran dökümüdür (ANSI kaçış
   dizileri); ayrıştırmaya elverişli DEĞİL. Yapılandırılmış kaynak diskte:
   `<claude_home>/jobs/<kısa-id>/state.json` (durum, `tokens`, `output`) ve
   `timeline.jsonl` (tur başına bir satır: `at`, `state`, `detail`, `text`).
7. `claude attach <id>` gerçek bir PTY ister; TTY'siz koşuda yalnızca alternatif
   ekran kaçış dizisi basıp çıkar. Takip mesajı için attach GEREKMEZ (bkz. 5).

Modül saf ayrıştırıcı + ince süreç sarmalayıcısıdır: her komut `runner`
üzerinden koşar, testler sahte `claude` ile aynı yolu sürer.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from entropy.platform.proc import popen_kwargs

__all__ = [
    "ClaudeBgError",
    "BgAgent",
    "BgJobState",
    "TimelineEntry",
    "CommandResult",
    "claude_home",
    "jobs_dir",
    "job_dir",
    "parse_start_output",
    "parse_agents_json",
    "read_job_state",
    "read_timeline",
    "timeline_to_stream_events",
    "build_start_command",
    "build_resume_command",
    "ClaudeBgSession",
]


class ClaudeBgError(RuntimeError):
    """`claude --bg` komutu beklenen kimliği/çıktıyı vermedi."""


# ----------------------------------------------------------------------
# Diskteki iş kayıtları
# ----------------------------------------------------------------------

def claude_home() -> Path:
    """CLI'ın veri kökü. `CLAUDE_CONFIG_DIR` verilmişse o kazanır (test kancası)."""
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    if override:
        return Path(override)
    return Path.home() / ".claude"


def jobs_dir() -> Path:
    """Arka plan işlerinin kökü: `<claude_home>/jobs`."""
    return claude_home() / "jobs"


def job_dir(job_id: str) -> Path:
    """Tek bir arka plan işinin klasörü (kısa kimlikle adlandırılır)."""
    return jobs_dir() / job_id


# ----------------------------------------------------------------------
# Veri taşıyıcıları
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class BgAgent:
    """`claude agents --json` dizisindeki tek kayıt."""

    id: str = ""              # kısa kimlik; etkileşimli oturumlarda BOŞ gelir
    session_id: str = ""      # tam uuid (resume bunu ister)
    pid: Optional[int] = None
    cwd: str = ""
    kind: str = ""            # "background" | "interactive"
    name: str = ""
    state: str = ""           # "done" | "working" | ...
    status: str = ""          # "idle" | ...
    started_at: Optional[int] = None

    @property
    def is_background(self) -> bool:
        return self.kind == "background"

    @property
    def is_alive(self) -> bool:
        """Süreç hâlâ ayakta mı. Durmuş işlerde `pid` alanı hiç gelmez."""
        return self.pid is not None


@dataclass(frozen=True)
class BgJobState:
    """`jobs/<id>/state.json` özeti."""

    job_id: str = ""
    state: str = ""
    detail: str = ""
    tempo: str = ""
    tokens: int = 0
    result: str = ""
    session_id: str = ""
    resume_session_id: str = ""
    name: str = ""
    cwd: str = ""
    respawn_flags: Tuple[str, ...] = ()
    updated_at: str = ""

    @property
    def is_done(self) -> bool:
        return self.state == "done"

    @property
    def isolated(self) -> bool:
        """Kaydedilmiş bayraklar Entropy Saf Kip'i taşıyor mu.

        Kopya (fork) oturumlarında bayraklar düşer; bu bayrak düşüşü sessiz
        bir kota ve kimlik sızıntısıdır, o yüzden ayrıca ölçülür.
        """
        flags = set(self.respawn_flags)
        return "--system-prompt-file" in flags and "--strict-mcp-config" in flags


@dataclass(frozen=True)
class TimelineEntry:
    """`timeline.jsonl` satırı: bir turun kapanış özeti."""

    at: str = ""
    state: str = ""
    detail: str = ""
    text: str = ""


@dataclass
class CommandResult:
    """`runner` sözleşmesi: bir CLI çağrısının ham sonucu."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


Runner = Callable[[Sequence[str], Optional[str]], CommandResult]


def _default_runner(cmd: Sequence[str], cwd: Optional[str]) -> CommandResult:
    """Gerçek süreç koşucusu. Konsol penceresi açmaz (Windows)."""
    proc = subprocess.run(
        list(cmd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        **popen_kwargs(cwd=cwd or None),
    )
    return CommandResult(proc.returncode, proc.stdout or "", proc.stderr or "")


# ----------------------------------------------------------------------
# Ayrıştırıcılar
# ----------------------------------------------------------------------

# "backgrounded · bfabe6d4 · entropy-spike-1" (ad isteğe bağlı).
# Ayraç bilerek geniş tutulur: CLI ASCII olmayan bir orta nokta basar ve
# Windows konsol kod sayfasında bu karakter "?"/U+FFFD'ye bozulabilir —
# kimliği ayraç karakterine bağlamak kırılgan olurdu.
_STARTED_RE = re.compile(r"backgrounded[^0-9a-z]{1,4}([0-9a-f]{6,})", re.IGNORECASE)
# "... so this started a copy as d1d56346."
_COPY_RE = re.compile(r"started a copy as\s+([0-9a-f]{6,})", re.IGNORECASE)
# "note: woke session bfabe6d4 with its saved options (...)"
_WOKE_RE = re.compile(r"woke session\s+([0-9a-f]{6,})", re.IGNORECASE)


def parse_start_output(text: str) -> Dict[str, Any]:
    """
    `claude --bg` çıktısından kimliği ve KOPYA/UYANDIRMA uyarısını çıkarır.

    Dönen sözlük: `id`, `forked` (kaydedilmiş bayraklar kaybolduysa True),
    `woken` (aynı kimlik kaydedilmiş bayraklarla uyandıysa True).
    Kimlik bulunamazsa `ClaudeBgError`.
    """
    body = text or ""
    forked = bool(_COPY_RE.search(body))
    woken = bool(_WOKE_RE.search(body))
    match = _STARTED_RE.search(body)
    if match:
        return {"id": match.group(1), "forked": forked, "woken": woken}
    fallback = _COPY_RE.search(body) or _WOKE_RE.search(body)
    if fallback:
        return {"id": fallback.group(1), "forked": forked, "woken": woken}
    raise ClaudeBgError("arka plan oturum kimliği okunamadı: " + body.strip()[:400])


def parse_agents_json(text: str) -> List[BgAgent]:
    """`claude agents --json` çıktısını kayıtlara çevirir. Bozuk JSON → boş liste."""
    try:
        data = json.loads(text or "[]")
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    out: List[BgAgent] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        pid = item.get("pid")
        out.append(
            BgAgent(
                id=str(item.get("id") or ""),
                session_id=str(item.get("sessionId") or ""),
                pid=int(pid) if isinstance(pid, (int, float)) else None,
                cwd=str(item.get("cwd") or ""),
                kind=str(item.get("kind") or ""),
                name=str(item.get("name") or ""),
                state=str(item.get("state") or ""),
                status=str(item.get("status") or ""),
                started_at=item.get("startedAt") if isinstance(item.get("startedAt"), int) else None,
            )
        )
    return out


def read_job_state(job_id: str, root: Optional[Path] = None) -> Optional[BgJobState]:
    """`jobs/<id>/state.json` okur. Dosya yoksa/bozuksa None."""
    base = Path(root) if root is not None else jobs_dir()
    path = base / job_id / "state.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    output = data.get("output")
    result = ""
    if isinstance(output, dict):
        result = str(output.get("result") or "")
    flags = data.get("respawnFlags")
    tokens = data.get("tokens")
    return BgJobState(
        job_id=job_id,
        state=str(data.get("state") or ""),
        detail=str(data.get("detail") or ""),
        tempo=str(data.get("tempo") or ""),
        tokens=int(tokens) if isinstance(tokens, (int, float)) else 0,
        result=result,
        session_id=str(data.get("sessionId") or ""),
        resume_session_id=str(data.get("resumeSessionId") or data.get("sessionId") or ""),
        name=str(data.get("name") or ""),
        cwd=str(data.get("cwd") or ""),
        respawn_flags=tuple(str(f) for f in flags) if isinstance(flags, list) else (),
        updated_at=str(data.get("updatedAt") or ""),
    )


def read_timeline(
    job_id: str,
    since: int = 0,
    root: Optional[Path] = None,
) -> Tuple[List[TimelineEntry], int]:
    """
    `timeline.jsonl` dosyasını `since` BAYT imlecinden itibaren okur.

    Bayt imleci satır sayısına yeğlenir: dosya yalnızca eklenerek büyür, bu
    yüzden imleç dosya kırpılmadıkça geçerli kalır ve her yoklamada tüm
    dosyayı okumaktan kurtuluruz. Dosya küçüldüyse imleç sıfırlanır.
    """
    base = Path(root) if root is not None else jobs_dir()
    path = base / job_id / "timeline.jsonl"
    try:
        size = path.stat().st_size
    except OSError:
        return [], since
    offset = 0 if since > size else max(0, since)
    entries: List[TimelineEntry] = []
    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            raw = handle.read()
            offset = handle.tell()
    except OSError:
        return [], since
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        entries.append(
            TimelineEntry(
                at=str(data.get("at") or ""),
                state=str(data.get("state") or ""),
                detail=str(data.get("detail") or ""),
                text=str(data.get("text") or ""),
            )
        )
    return entries, offset


# ----------------------------------------------------------------------
# Sahne köprüsü: zaman çizgisi → `bus.agent_stream` yükü
# ----------------------------------------------------------------------

# İşin `state` alanı ile sahne durumu arasındaki eşleme. Sahnenin bildiği
# durumlar: thinking / working / idle / error (bkz. provider.stream_state_for).
_JOB_STATE_TO_SCENE = {
    "done": "idle",
    "idle": "idle",
    "working": "working",
    "running": "working",
    "thinking": "thinking",
    "error": "error",
    "failed": "error",
    "stopped": "idle",
}


def timeline_to_stream_events(
    entries: Sequence[TimelineEntry],
    *,
    agent: str = "",
    office: str = "",
    card_id: str = "",
    task_id: str = "",
    model: str = "",
) -> List[Dict[str, object]]:
    """
    Zaman çizgisi satırlarını sahne yüklerine çevirir (yayın YAPMAZ).

    Yükün tek üretim noktası `provider.build_agent_stream_event`'tir; burada
    yalnızca tür/durum eşlemesi yapılır. Yayını çağıran katman üstlenir, böylece
    prototip Qt sinyaline bağımlı olmaz ve testte sinyalsiz koşar.
    """
    from entropy.core.provider import build_agent_stream_event

    events: List[Dict[str, object]] = []
    for entry in entries:
        scene = _JOB_STATE_TO_SCENE.get((entry.state or "").lower(), "thinking")
        kind = "result" if scene == "idle" else ("error" if scene == "error" else "text")
        events.append(
            build_agent_stream_event(
                kind,
                entry.text or entry.detail,
                task_id=task_id,
                card_id=card_id,
                office=office,
                agent=agent,
                provider="claude",
                model=model,
                state=scene,
            )
        )
    return events


# ----------------------------------------------------------------------
# Komut kurucular
# ----------------------------------------------------------------------

def build_start_command(
    prompt: str,
    *,
    name: str = "",
    claude_path: str = "claude",
    system_prompt_file: str = "",
    tools: Optional[Sequence[str]] = None,
    add_dirs: Optional[Sequence[str]] = None,
    permission_mode: str = "acceptEdits",
    model: str = "",
    effort: str = "",
    isolated: bool = True,
) -> List[str]:
    """
    Yeni kalıcı oturumun argv'si.

    Kurallar ölçülmüştür: istem POZİSYONEL (`-p` çakışır), `--output-format`
    ve `--session-id` HİÇ verilmez (biri künyeyi kirletir, öteki yok sayılır).
    """
    if not (prompt or "").strip():
        raise ClaudeBgError("boş istemle arka plan oturumu açılamaz")
    cmd: List[str] = [claude_path, "--bg", prompt]
    if name:
        cmd += ["--name", name]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    if permission_mode:
        cmd += ["--permission-mode", permission_mode]
    if isolated:
        if system_prompt_file:
            cmd += ["--system-prompt-file", system_prompt_file]
        cmd += ["--strict-mcp-config", "--setting-sources", ""]
        if tools is not None:
            cmd += ["--tools", ",".join(tools)]
    for directory in add_dirs or ():
        cmd += ["--add-dir", str(directory)]
    return cmd


def build_resume_command(
    session_id: str,
    prompt: str,
    *,
    claude_path: str = "claude",
) -> List[str]:
    """
    Takip turu argv'si — BİLEREK bayraksız.

    Bayrak eklemek oturumu çatallar ve kaydedilmiş izolasyon bayraklarını
    düşürür (ölçüldü: aynı istem 4,2k yerine 44,6k jetona mal oldu). İş kendi
    `respawnFlags` kaydını taşıdığı için bayrak tekrarına gerek de yoktur.
    """
    if not (session_id or "").strip():
        raise ClaudeBgError("takip turu için oturum kimliği gerekir")
    return [claude_path, "--bg", "--resume", session_id, prompt]


# ----------------------------------------------------------------------
# Oturum yöneticisi
# ----------------------------------------------------------------------

@dataclass
class _Record:
    """`sessions.json` içindeki tek ajan kaydı."""

    agent: str = ""
    job_id: str = ""
    session_id: str = ""
    name: str = ""
    cwd: str = ""
    office: str = ""
    card_id: str = ""
    created_at: float = 0.0
    cursor: int = 0
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "job_id": self.job_id,
            "session_id": self.session_id,
            "name": self.name,
            "cwd": self.cwd,
            "office": self.office,
            "card_id": self.card_id,
            "created_at": self.created_at,
            "cursor": self.cursor,
            "meta": self.meta,
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "_Record":
        return cls(
            agent=str(data.get("agent") or ""),
            job_id=str(data.get("job_id") or ""),
            session_id=str(data.get("session_id") or ""),
            name=str(data.get("name") or ""),
            cwd=str(data.get("cwd") or ""),
            office=str(data.get("office") or ""),
            card_id=str(data.get("card_id") or ""),
            created_at=float(data.get("created_at") or 0.0),
            cursor=int(data.get("cursor") or 0),
            meta=data.get("meta") if isinstance(data.get("meta"), dict) else {},
        )


class ClaudeBgSession:
    """
    Ajan başına TEK kalıcı arka plan oturumu tutan ince yönetici.

    Sözleşme:
      * `start(agent, prompt, ...) -> job_id`  — ajanın oturumu yoksa açar.
      * `list() -> List[BgAgent]`              — CLI'a sorar (yaşayan ajanlar).
      * `logs(agent) -> List[TimelineEntry]`   — imleçten beri yeni turlar.
      * `send(agent, text) -> job_id`          — durdur + bayraksız uyandır.
      * `stop(agent)` / `remove(agent)`        — sonlandır / kaydı sil.

    Eşleme `<store_dir>/sessions.json` dosyasında durur; uygulama yeniden
    açıldığında `reattach()` bu kaydı canlı listeyle karşılaştırıp ölmüş
    girdileri temizler.
    """

    def __init__(
        self,
        store_dir: Path,
        *,
        claude_path: str = "claude",
        runner: Optional[Runner] = None,
        jobs_root: Optional[Path] = None,
    ) -> None:
        self.store_dir = Path(store_dir)
        self.claude_path = claude_path
        self._runner: Runner = runner or _default_runner
        self._jobs_root = Path(jobs_root) if jobs_root is not None else None
        self._records: Dict[str, _Record] = {}
        self._load()

    # -- depo ----------------------------------------------------------

    @property
    def store_path(self) -> Path:
        return self.store_dir / "sessions.json"

    def _load(self) -> None:
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        agents = data.get("agents") if isinstance(data, dict) else None
        if not isinstance(agents, dict):
            return
        for key, value in agents.items():
            if isinstance(value, dict):
                self._records[str(key)] = _Record.from_json(value)

    def _save(self) -> None:
        self.store_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "agents": {k: v.to_json() for k, v in self._records.items()},
        }
        tmp = self.store_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.store_path)

    def record(self, agent: str) -> Optional[_Record]:
        return self._records.get(agent)

    def _jobs_dir(self) -> Path:
        return self._jobs_root if self._jobs_root is not None else jobs_dir()

    # -- komutlar ------------------------------------------------------

    def _run(self, cmd: Sequence[str], cwd: Optional[str] = None) -> CommandResult:
        return self._runner(list(cmd), cwd)

    def start(
        self,
        agent: str,
        prompt: str,
        *,
        cwd: str = "",
        name: str = "",
        office: str = "",
        card_id: str = "",
        meta: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Ajan için kalıcı oturum açar ve kısa kimliği döndürür."""
        cmd = build_start_command(
            prompt,
            name=name or agent,
            claude_path=self.claude_path,
            **kwargs,
        )
        result = self._run(cmd, cwd or None)
        merged = (result.stdout or "") + "\n" + (result.stderr or "")
        if not result.ok:
            raise ClaudeBgError("arka plan oturumu açılamadı: " + merged.strip()[:400])
        parsed = parse_start_output(merged)
        job_id = str(parsed["id"])
        state = read_job_state(job_id, self._jobs_dir())
        self._records[agent] = _Record(
            agent=agent,
            job_id=job_id,
            session_id=state.resume_session_id if state else "",
            name=name or agent,
            cwd=cwd,
            office=office,
            card_id=card_id,
            created_at=time.time(),
            cursor=0,
            meta=dict(meta or {}),
        )
        self._save()
        return job_id

    def list(self) -> List[BgAgent]:
        """Canlı oturumlar (CLI'ın gerçeği). Komut düşerse boş liste."""
        result = self._run([self.claude_path, "agents", "--json"])
        if not result.ok:
            return []
        return parse_agents_json(result.stdout)

    def reattach(self) -> Dict[str, BgAgent]:
        """
        Uygulama açılışında kaydı canlı listeyle eşler; ölmüş kayıtları atar.

        Dönen sözlük: ajan adı → canlı oturum. Kayıtta olup listede olmayan
        ajanların girdisi silinir (yetim kayıt, sahnede hayalet ajan üretir).
        """
        live = {a.id: a for a in self.list() if a.id and a.is_background}
        alive: Dict[str, BgAgent] = {}
        dropped = False
        for agent, rec in list(self._records.items()):
            found = live.get(rec.job_id)
            if found is None:
                del self._records[agent]
                dropped = True
                continue
            if found.session_id and found.session_id != rec.session_id:
                rec.session_id = found.session_id
                dropped = True
            alive[agent] = found
        if dropped:
            self._save()
        return alive

    def state(self, agent: str) -> Optional[BgJobState]:
        """Ajanın işinin disk künyesi (durum, jeton, sonuç)."""
        rec = self._records.get(agent)
        if rec is None:
            return None
        return read_job_state(rec.job_id, self._jobs_dir())

    def logs(self, agent: str, since: Optional[int] = None) -> List[TimelineEntry]:
        """
        İmleçten beri biriken turları döndürür ve imleci ilerletir.

        `since` verilirse imleç yerine o kullanılır (imleç yine güncellenir).
        Kasten `claude logs` çağrılmaz: o komut ANSI ekran dökümü basar.
        """
        rec = self._records.get(agent)
        if rec is None:
            return []
        cursor = rec.cursor if since is None else int(since)
        entries, offset = read_timeline(rec.job_id, cursor, self._jobs_dir())
        if offset != rec.cursor:
            rec.cursor = offset
            self._save()
        return entries

    def stream_events(self, agent: str) -> List[Dict[str, object]]:
        """Yeni turların sahne yükleri (yayını çağıran yapar)."""
        rec = self._records.get(agent)
        if rec is None:
            return []
        return timeline_to_stream_events(
            self.logs(agent),
            agent=agent,
            office=rec.office,
            card_id=rec.card_id,
            model=str(rec.meta.get("model") or ""),
        )

    def send(self, agent: str, text: str) -> str:
        """
        Takip turu gönderir: önce `stop`, sonra BAYRAKSIZ `--bg --resume`.

        Neden durdurup uyandırıyoruz: canlı oturuma resume KOPYA açar ve
        kaydedilmiş izolasyon bayraklarını düşürür. Çatallanma yine de
        olursa (`forked`) kayıt yeni kimliğe taşınır ve çağıran `ClaudeBgError`
        yerine yeni kimliği alır — ama künye `meta["forked"]` ile işaretlenir,
        çünkü o oturum artık Entropy Saf Kip'te DEĞİLDİR.
        """
        rec = self._records.get(agent)
        if rec is None:
            raise ClaudeBgError("ajanın açık bir arka plan oturumu yok: " + agent)
        session_id = rec.session_id or rec.job_id
        self._run([self.claude_path, "stop", rec.job_id])
        result = self._run(
            build_resume_command(session_id, text, claude_path=self.claude_path),
            rec.cwd or None,
        )
        merged = (result.stdout or "") + "\n" + (result.stderr or "")
        if not result.ok:
            raise ClaudeBgError("takip turu gönderilemedi: " + merged.strip()[:400])
        parsed = parse_start_output(merged)
        new_id = str(parsed["id"])
        if new_id != rec.job_id:
            rec.job_id = new_id
            rec.cursor = 0
            state = read_job_state(new_id, self._jobs_dir())
            rec.session_id = state.resume_session_id if state else ""
        if parsed.get("forked"):
            rec.meta["forked"] = True
        self._save()
        return rec.job_id

    def stop(self, agent: str) -> bool:
        """Oturumu durdurur; konuşma diskte kalır, `send` yeniden uyandırır."""
        rec = self._records.get(agent)
        if rec is None:
            return False
        return self._run([self.claude_path, "stop", rec.job_id]).ok

    def remove(self, agent: str) -> bool:
        """Oturumu durdurup CLI kaydından siler ve eşlemeden düşürür."""
        rec = self._records.pop(agent, None)
        if rec is None:
            return False
        self._run([self.claude_path, "stop", rec.job_id])
        ok = self._run([self.claude_path, "rm", rec.job_id]).ok
        self._save()
        return ok
