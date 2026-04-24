from datetime import date, datetime
from typing import Literal

from pydantic import AliasChoices, Field, model_validator

from src.api.v1.schemas.common import APIModel, PaginationResponse
from src.api.v1.schemas.product import ProductBatchItemResponse, ProductResponse


class BatchCreateRequest(APIModel):
    is_closed: bool = Field(
        default=False,
        validation_alias=AliasChoices("is_closed", "СтатусЗакрытия"),
    )
    task_description: str = Field(
        min_length=1,
        max_length=500,
        validation_alias=AliasChoices("task_description", "ПредставлениеЗаданияНаСмену"),
    )
    work_center_name: str = Field(
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("work_center_name", "РабочийЦентр"),
    )
    shift: str = Field(
        min_length=1,
        max_length=100,
        validation_alias=AliasChoices("shift", "Смена"),
    )
    team: str = Field(
        min_length=1,
        max_length=100,
        validation_alias=AliasChoices("team", "Бригада"),
    )
    batch_number: int = Field(
        gt=0,
        validation_alias=AliasChoices("batch_number", "НомерПартии"),
    )
    batch_date: date = Field(validation_alias=AliasChoices("batch_date", "ДатаПартии"))
    nomenclature: str = Field(
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("nomenclature", "Номенклатура"),
    )
    ekn_code: str = Field(
        min_length=1,
        max_length=100,
        validation_alias=AliasChoices("ekn_code", "КодЕКН"),
    )
    work_center_identifier: str = Field(
        min_length=1,
        max_length=100,
        validation_alias=AliasChoices("work_center_identifier", "ИдентификаторРЦ"),
    )
    shift_start: datetime = Field(
        validation_alias=AliasChoices("shift_start", "ДатаВремяНачалаСмены"),
    )
    shift_end: datetime = Field(
        validation_alias=AliasChoices("shift_end", "ДатаВремяОкончанияСмены"),
    )


class BatchUpdateRequest(APIModel):
    is_closed: bool | None = None
    task_description: str | None = Field(default=None, min_length=1, max_length=500)
    shift: str | None = Field(default=None, min_length=1, max_length=100)
    team: str | None = Field(default=None, min_length=1, max_length=100)
    nomenclature: str | None = Field(default=None, min_length=1, max_length=255)
    ekn_code: str | None = Field(default=None, min_length=1, max_length=100)
    shift_start: datetime | None = None
    shift_end: datetime | None = None


class BatchFilterParams(APIModel):
    is_closed: bool | None = None
    batch_number: int | None = Field(default=None, gt=0)
    batch_date: date | None = None
    work_center_id: int | None = Field(default=None, gt=0)
    work_center_identifier: str | None = None
    shift: str | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class WorkCenterResponse(APIModel):
    id: int
    identifier: str
    name: str
    created_at: datetime
    updated_at: datetime


class BatchResponse(APIModel):
    id: int
    is_closed: bool
    closed_at: datetime | None
    task_description: str
    work_center_id: int
    shift: str
    team: str
    batch_number: int
    batch_date: date
    nomenclature: str
    ekn_code: str
    shift_start: datetime
    shift_end: datetime
    created_at: datetime
    updated_at: datetime
    work_center: WorkCenterResponse
    products: list[ProductResponse]


class BatchDetailResponse(APIModel):
    id: int
    is_closed: bool
    batch_number: int
    batch_date: date
    products: list[ProductBatchItemResponse]


class BatchStatisticsResponse(APIModel):
    batch_info: dict
    production_stats: dict
    timeline: dict
    team_performance: dict


class BatchListResponse(PaginationResponse):
    items: list[BatchResponse]


class BatchAggregationRequest(APIModel):
    unique_codes: list[str] | None = Field(default=None, min_length=1)
    unique_code: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def normalize_unique_codes(self) -> "BatchAggregationRequest":
        if self.unique_codes is None and self.unique_code is None:
            raise ValueError("Either unique_codes or unique_code must be provided.")

        if self.unique_codes is None:
            self.unique_codes = [self.unique_code] if self.unique_code is not None else []

        self.unique_codes = [code.strip() for code in self.unique_codes if code.strip()]
        if not self.unique_codes:
            raise ValueError("At least one non-empty unique code must be provided.")

        return self


class BatchAsyncAggregationRequest(APIModel):
    unique_codes: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def normalize_unique_codes(self) -> "BatchAsyncAggregationRequest":
        self.unique_codes = [code.strip() for code in self.unique_codes if code.strip()]
        if not self.unique_codes:
            raise ValueError("At least one non-empty unique code must be provided.")

        return self


class BatchReportRequest(APIModel):
    format: Literal["excel"] = "excel"


class BatchExportFilters(APIModel):
    is_closed: bool | None = None
    batch_number: int | None = Field(default=None, gt=0)
    date_from: date | None = None
    date_to: date | None = None
    work_center_identifier: str | None = None
    shift: str | None = None


class BatchExportRequest(APIModel):
    format: Literal["excel", "csv"] = "excel"
    filters: BatchExportFilters = Field(default_factory=BatchExportFilters)


class AggregationError(APIModel):
    unique_code: str
    error: str


class BatchAggregationResponse(APIModel):
    batch_id: int
    total: int
    aggregated: int
    failed: int
    errors: list[AggregationError]
