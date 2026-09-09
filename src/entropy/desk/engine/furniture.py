"""
Mobilya manifestlerini çözer.

Manifest ağacı üç düzey grup içerebilir: `rotation` (yön), `state` (açık/kapalı),
`animation` (kare dizisi). Düzen JSON'undaki `furniture[].type` alanı bir YAPRAK
varyant kimliğidir ("DESK_FRONT", "PC_SIDE"), isteğe bağlı ":left" son ekiyle
yatay aynalanır. Bu modül tüm manifestleri tek seferde tarayıp
`varyant kimliği -> ResolvedFurniture` sözlüğü kurar.

Animasyon grupları tek varyant olarak çözülür: yaprak kimliklerinin ortak kökü
(PC_FRONT_ON_1..3 -> "PC_FRONT_ON") anahtar olur, kareler sırayla tutulur.
Böylece bir masaüstü bilgisayar 3 kareli animasyon olarak çizilebilir.

Derinlik sıralaması satır tabanlıdır: bir nesnenin alt kenarı (row + footprintH)
büyükse önde çizilir; eşitlikte sütun. Karakterler de aynı ölçütle sıraya girer,
böylece masanın arkasındaki ajan masanın ardında kalır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from PySide6.QtGui import QPixmap, QTransform

from entropy.desk.engine.assets import TILE_SIZE, AssetLibrary, library

MIRROR_SUFFIX = ":left"


@dataclass
class ResolvedFurniture:
    """Çözülmüş tek varyant: bir veya birden çok kare + ayak izi."""

    variant_id: str
    furniture_id: str
    files: List[str] = field(default_factory=list)   # varlık köküne göreli
    width: int = TILE_SIZE
    height: int = TILE_SIZE
    footprint_w: int = 1
    footprint_h: int = 1
    orientation: str = ""
    state: str = ""
    mirror_side: bool = False
    category: str = ""

    @property
    def frame_count(self) -> int:
        return len(self.files)

    @property
    def animated(self) -> bool:
        return len(self.files) > 1


@dataclass
class PlacedFurniture:
    """Düzendeki tek yerleşim: varyant + hücre + ayna."""

    uid: str
    variant: ResolvedFurniture
    col: int
    row: int
    mirrored: bool = False

    @property
    def depth(self) -> Tuple[int, int]:
        """Satır sıralı derinlik anahtarı (alt kenar, sütun)."""
        return (self.row + self.variant.footprint_h, self.col)

    def cells(self):
        for r in range(self.variant.footprint_h):
            for c in range(self.variant.footprint_w):
                yield (self.col + c, self.row + r)


def _common_root(ids: Sequence[str]) -> str:
    """PC_FRONT_ON_1..3 -> PC_FRONT_ON (son sayısal parçayı atar)."""
    if not ids:
        return ""
    first = ids[0]
    head, _, tail = first.rpartition("_")
    return head if tail.isdigit() and head else first


class FurnitureLibrary:
    """Tüm manifestleri çözüp varyant indeksini tutan kütüphane."""

    def __init__(self, lib: Optional[AssetLibrary] = None) -> None:
        self.lib = lib or library()
        self._variants: Optional[Dict[str, ResolvedFurniture]] = None
        self._pixmaps: Dict[Tuple[str, bool], QPixmap] = {}
        self._scaled: Dict[Tuple[str, bool, int], QPixmap] = {}

    # ------------------------------------------------------------ çözümleme

    def variants(self) -> Dict[str, ResolvedFurniture]:
        if self._variants is None:
            out: Dict[str, ResolvedFurniture] = {}
            for fid in self.lib.furniture_ids():
                try:
                    manifest = self.lib.furniture_manifest(fid)
                except Exception:
                    continue
                self._resolve_node(fid, manifest, manifest.get("category", ""), out)
            self._variants = out
        return self._variants

    def _resolve_node(self, fid: str, node: dict, category: str, out: Dict[str, ResolvedFurniture],
                      inherited: Optional[dict] = None) -> None:
        inherited = dict(inherited or {})
        for key in ("orientation", "state", "mirrorSide"):
            if node.get(key) is not None:
                inherited[key] = node[key]

        node_type = node.get("type", "asset")
        if node_type != "group":
            variant = self._leaf_variant(fid, node, category, inherited)
            if variant is not None:
                out[variant.variant_id] = variant
            return

        members = node.get("members") or []
        if node.get("groupType") == "animation":
            frames = sorted(
                (m for m in members if m.get("file")),
                key=lambda m: int(m.get("frame", 0)),
            )
            if frames:
                ids = [str(m.get("id", "")) for m in frames]
                base = frames[0]
                variant = ResolvedFurniture(
                    variant_id=_common_root(ids) or str(base.get("id", fid)),
                    furniture_id=fid,
                    files=[f"furniture/{fid}/{m['file']}" for m in frames],
                    width=int(base.get("width", TILE_SIZE)),
                    height=int(base.get("height", TILE_SIZE)),
                    footprint_w=int(base.get("footprintW", 1)),
                    footprint_h=int(base.get("footprintH", 1)),
                    orientation=str(inherited.get("orientation", "")),
                    state=str(inherited.get("state", node.get("state", ""))),
                    mirror_side=bool(inherited.get("mirrorSide", False)),
                    category=category,
                )
                out[variant.variant_id] = variant
            return

        for member in members:
            self._resolve_node(fid, member, category, out, inherited)

    def _leaf_variant(self, fid: str, node: dict, category: str,
                      inherited: dict) -> Optional[ResolvedFurniture]:
        variant_id = str(node.get("id") or fid)
        rel_file = node.get("file") or f"{variant_id}.png"
        rel = f"furniture/{fid}/{rel_file}"
        if not self.lib.exists(*rel.split("/")):
            return None
        return ResolvedFurniture(
            variant_id=variant_id,
            furniture_id=fid,
            files=[rel],
            width=int(node.get("width", TILE_SIZE)),
            height=int(node.get("height", TILE_SIZE)),
            footprint_w=int(node.get("footprintW", 1)),
            footprint_h=int(node.get("footprintH", 1)),
            orientation=str(inherited.get("orientation", "")),
            state=str(inherited.get("state", "")),
            mirror_side=bool(inherited.get("mirrorSide", False)),
            category=category,
        )

    # ------------------------------------------------------------ arama

    def resolve(self, type_str: str) -> Tuple[Optional[ResolvedFurniture], bool]:
        """
        Düzen tipini varyanta çevirir. Dönüş: (varyant, aynalı mı).

        Bilinmeyen tip sessizce None döner; sahne o nesneyi atlar (bozuk düzen
        tüm ofisin çizilmemesine yol açmasın).
        """
        mirrored = type_str.endswith(MIRROR_SUFFIX)
        key = type_str[: -len(MIRROR_SUFFIX)] if mirrored else type_str
        variants = self.variants()
        variant = variants.get(key)
        if variant is None:
            # "PC_FRONT" gibi durum belirtmeyen tipler: açık durumu tercih et.
            variant = variants.get(f"{key}_ON") or variants.get(f"{key}_OFF")
        return variant, mirrored

    # ------------------------------------------------------------ görseller

    def pixmap(self, variant: ResolvedFurniture, frame: int = 0,
               mirrored: bool = False) -> Optional[QPixmap]:
        if not variant.files:
            return None
        rel = variant.files[frame % len(variant.files)]
        key = (rel, mirrored)
        cached = self._pixmaps.get(key)
        if cached is None:
            pix = self.lib.pixmap(rel)
            if pix.isNull():
                return None
            if mirrored:
                pix = pix.transformed(QTransform().scale(-1, 1))
            self._pixmaps[key] = pix
            cached = pix
        return cached

    def scaled(self, variant: ResolvedFurniture, frame: int, mirrored: bool,
               zoom: int) -> Optional[QPixmap]:
        if not variant.files:
            return None
        rel = variant.files[frame % len(variant.files)]
        key = (rel, mirrored, zoom)
        hit = self._scaled.get(key)
        if hit is not None:
            return hit
        base = self.pixmap(variant, frame, mirrored)
        if base is None:
            return None
        out = AssetLibrary.scaled(base, zoom)
        self._scaled[key] = out
        return out

    def clear_scaled(self) -> None:
        self._scaled.clear()


def sort_by_depth(items: Sequence[PlacedFurniture]) -> List[PlacedFurniture]:
    """Satır sıralı derinlik: arkadakiler önce çizilir."""
    return sorted(items, key=lambda p: p.depth)
