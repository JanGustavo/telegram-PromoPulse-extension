from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# ===========================================================================
# AUTH
# ===========================================================================


class PhoneRequest(BaseModel):
    phone_number: str = Field(
        ...,
        examples=["+5511999999999"],
        description="Número de telefone com DDI (ex: +5511999999999)",
    )


class LoginRequest(BaseModel):
    code: str = Field(
        ...,
        examples=["12345"],
        description="Código de verificação recebido via Telegram",
    )


# ===========================================================================
# GRUPOS
# ===========================================================================


class GroupItem(BaseModel):
    id: int
    title: str
    username: Optional[str] = None
    link: Optional[str] = None
    auto_filtered: bool


class GroupsResponse(BaseModel):
    groups: list[GroupItem]


class FilterPreviewItem(BaseModel):
    id: int
    title: str
    auto_filtered: bool
    blocked_by: list[str]


class FilterPreviewResponse(BaseModel):
    groups: list[FilterPreviewItem]


# ===========================================================================
# CONFIGURAÇÃO DE MONITORAMENTO
# ===========================================================================


class WatchConfigRequest(BaseModel):
    active_levels: list[str] = Field(
        default=["broad"],
        examples=[["broad"]],
        description='Níveis ativos. Valores: "broad", "mid", "specific"',
    )
    broad_categories: list[str] = Field(
        default=["celulares"],
        examples=[["celulares", "tvs"]],
        description=(
            "Categorias para o nível Amplo. "
            "Valores: celulares, tvs, audio, higiene, informatica, casa, moda, games, esportes"
        ),
    )
    mid_categories: list[str] = Field(
        default=[],
        examples=[["celulares"]],
        description="Categorias ativas no nível Marcas",
    )
    mid_brands: list[str] = Field(
        default=[],
        examples=[["Samsung", "Apple", "Xiaomi"]],
        description="Marcas específicas para o nível Marcas",
    )
    specific_models: list[str] = Field(
        default=[],
        examples=[["Galaxy S24 Ultra", "iPhone 15 Pro Max"]],
        description="Modelos exatos (suportam regex) para o nível Modelos",
    )
    broad_keywords: list[str] = Field(
        default=[],
        examples=[["air fryer", "fralda"]],
        description="Palavras-chave extras para o nível Amplo",
    )
    price_max: Optional[float] = Field(
        default=None,
        examples=[3500.0],
        description="Preço máximo em R$. Alertas acima deste valor são ignorados.",
    )
    min_score: int = Field(
        default=2,
        ge=1,
        le=6,
        examples=[2],
        description="Score mínimo de oferta exigido (1 = mais permissivo, 6 = mais restrito)",
    )
    require_offer_match: bool = Field(
        default=True,
        examples=[True],
        description="Se False, captura qualquer mensagem que bata no produto (ignora score)",
    )
    relaxed_mode: bool = Field(
        default=False,
        examples=[False],
        description="Se True, aceita qualquer mensagem com score >= 1",
    )


class WatchConfigResponse(BaseModel):
    status: str
    config: dict


# ===========================================================================
# CONTROLE DE MONITORAMENTO
# ===========================================================================


class StartWatchRequest(BaseModel):
    group_ids: list[int] = Field(
        ...,
        examples=[[-1001234567890, -1009876543210]],
        description="Lista de IDs de grupos do Telegram para monitorar",
    )


class StartWatchResponse(BaseModel):
    status: str
    groups: int
    config: dict


class StopWatchResponse(BaseModel):
    status: str


class WatchStatusResponse(BaseModel):
    active: bool
    config: dict
    alerts_count: int


# ===========================================================================
# ALERTAS
# ===========================================================================


class AlertItem(BaseModel):
    group_id: int
    group_title: str
    username: Optional[str] = None
    message: str
    message_id: int
    offer_score: Optional[int] = None
    offer_categories: Optional[list[str]] = None
    extracted_price: Optional[float] = None
    link: Optional[str] = None
    clean_title: Optional[str] = None
    image_url: Optional[str] = None
    price_drop_percentage: Optional[int] = 0


class AlertsResponse(BaseModel):
    alerts: list[AlertItem]


# ===========================================================================
# TESTE DE OFERTA
# ===========================================================================


class OfferRequest(BaseModel):
    text: str = Field(
        ...,
        examples=["iPhone 15 Pro Max 256GB por apenas R$ 4.999 frete grátis"],
        description="Texto de mensagem do grupo para testar contra os filtros ativos",
    )


class OfferTestResponse(BaseModel):
    would_alert: bool
    offer_score: int
    offer_categories: list[str]
    extracted_price: Optional[float] = None
    level_match: bool
    current_level: str


class PriceHistoryItem(BaseModel):
    price: float
    date: str


class PriceHistoryResponse(BaseModel):
    history: list[PriceHistoryItem]
