from pydantic import BaseModel, Field


class OpenSubtitlesFile(BaseModel):
    file_id: int
    file_name: str = ""


class OpenSubtitlesUploader(BaseModel):
    name: str = ""


class OpenSubtitlesAttributes(BaseModel):
    language: str = ""
    files: list[OpenSubtitlesFile] = Field(default_factory=list)
    release: str = ""
    uploader: OpenSubtitlesUploader = Field(default_factory=OpenSubtitlesUploader)
    download_count: int = 0
    moviehash_match: bool = False
    hearing_impaired: bool = False
    machine_translated: bool = False


class OpenSubtitlesResult(BaseModel):
    id: str | int
    attributes: OpenSubtitlesAttributes


class OpenSubtitlesSearchPayload(BaseModel):
    data: list[OpenSubtitlesResult] = Field(default_factory=list)


class OpenSubtitlesDownloadPayload(BaseModel):
    link: str


class SubtitleSearchRequest(BaseModel):
    file_id: str


class SubtitleCandidate(BaseModel):
    id: str
    file_id: int
    provider: str
    language: str
    format: str
    release: str = ""
    file_name: str = ""
    uploader: str = ""
    download_count: int = 0
    match_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    hash_matched: bool = False
    hearing_impaired: bool = False
    machine_translated: bool = False


class SubtitleSearchResponse(BaseModel):
    items: list[SubtitleCandidate] = Field(default_factory=list)


class SubtitlePreviewRequest(BaseModel):
    candidate_file_id: int


class SubtitlePreviewResponse(BaseModel):
    content: str


class SubtitleInstallRequest(BaseModel):
    file_id: str
    candidate_file_id: int
    language: str
    format: str = "srt"


class SubtitleInstallResponse(BaseModel):
    path: str
    artifact_type: str


class SubtitleBatchFillResponse(BaseModel):
    processed_count: int = 0
    installed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
