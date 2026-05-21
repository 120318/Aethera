from __future__ import annotations

from app.schemas.exception.base import AppException

SYSTEM_ERROR_CODE = 15000
SYSTEM_ERROR_KEY = "backendErrors.system"


class SystemException(AppException):
    def __init__(self, message_key: str = SYSTEM_ERROR_KEY, *, params: dict | None = None):
        super().__init__(code=SYSTEM_ERROR_CODE, message_key=message_key, is_system_error=True, params=params)


class MediaNotFoundException(AppException):
    def __init__(self):
        super().__init__(code=10000, message_key="backendErrors.mediaNotFound")


class MediaTMDBMappingRequiredException(AppException):
    def __init__(self, data):
        super().__init__(
            code=10024,
            message_key="backendErrors.mediaTmdbMappingRequired",
            data=data,
        )


class RequestParamException(AppException):
    def __init__(self, param: str, value: str):
        super().__init__(
            code=10001,
            message_key="backendErrors.requestParamInvalid",
            params={"param": param, "value": value},
        )


class TestConnectionException(AppException):
    def __init__(self, service_name: str):
        super().__init__(
            code=10002,
            message_key="backendErrors.testConnectionFailed",
            params={"service": service_name},
        )


class ConfigurationException(AppException):
    def __init__(self, message_key: str, *, params: dict | None = None):
        super().__init__(code=10003, message_key=message_key, params=params)


class DirectoryValidationException(AppException):
    def __init__(self, message_key: str, *, params: dict | None = None):
        super().__init__(code=10004, message_key=message_key, params=params)


class ServiceTypeException(AppException):
    def __init__(self, service_type: str, supported_types: list[str] | None = None):
        super().__init__(
            code=10005,
            message_key="backendErrors.serviceTypeUnsupportedWithSupported" if supported_types else "backendErrors.serviceTypeUnsupported",
            params={"serviceType": service_type, "supportedTypes": ", ".join(str(item) for item in supported_types or [])},
        )


class SubscriptionNotFoundException(AppException):
    def __init__(self):
        super().__init__(code=10006, message_key="backendErrors.subscriptionNotFound")


class DownloadException(AppException):
    def __init__(self, message_key: str, *, params: dict | None = None):
        super().__init__(code=10007, message_key=message_key, params=params)


class TransferException(AppException):
    def __init__(self, message_key: str, *, params: dict | None = None):
        super().__init__(code=10008, message_key=message_key, params=params)


class EventConsumerExecutionException(SystemException):
    def __init__(self, consumer_name: str, message: str):
        super().__init__(
            message_key="backendErrors.eventConsumerExecutionFailed",
            params={"consumer": consumer_name, "message": message},
        )


class SubscriptionStateException(AppException):
    def __init__(self, message_key: str, *, params: dict | None = None):
        super().__init__(code=10010, message_key=message_key, params=params)


class DownloadTaskAlreadyExistsException(DownloadException):
    def __init__(self):
        AppException.__init__(self, code=10011, message_key="backendErrors.downloadTaskAlreadyExists")


class DownloadTorrentPathConflictException(DownloadException):
    def __init__(self, message_key: str = "backendErrors.downloadTorrentPathConflict", *, params: dict | None = None):
        AppException.__init__(self, code=10012, message_key=message_key, params=params)


class InvalidRequestException(AppException):
    def __init__(self, message_key: str, *, params: dict | None = None):
        super().__init__(code=10013, message_key=message_key, params=params)


class ResourceNotFoundException(AppException):
    def __init__(self, message_key: str, *, params: dict | None = None):
        super().__init__(code=10014, message_key=message_key, params=params)


class SearchMissingImdbException(AppException):
    def __init__(self):
        super().__init__(code=10015, message_key="backendErrors.searchMissingImdb")


class SearchMissingSeasonInfoException(AppException):
    def __init__(self):
        super().__init__(code=10016, message_key="backendErrors.searchMissingSeasonInfo")


class EmptyTitlesException(AppException):
    def __init__(self):
        super().__init__(code=10017, message_key="backendErrors.emptyTitles")


class InvalidCalendarRangeException(AppException):
    def __init__(self, message_key: str, *, params: dict | None = None):
        super().__init__(code=10018, message_key=message_key, params=params)


class ExternalAuthNotEnabledException(AppException):
    def __init__(self):
        super().__init__(code=10019, message_key="backendErrors.externalAuthNotEnabled")


class AuthenticationProviderDisabledException(AppException):
    def __init__(self):
        super().__init__(code=10020, message_key="backendErrors.authenticationProviderDisabled")


class InvalidCredentialsException(AppException):
    def __init__(self):
        super().__init__(code=10021, message_key="backendErrors.invalidCredentials")


class SystemAlreadyInitializedException(AppException):
    def __init__(self):
        super().__init__(code=10022, message_key="backendErrors.systemAlreadyInitialized")


class AuthenticationRequiredException(AppException):
    def __init__(self):
        super().__init__(code=401, message_key="backendErrors.authenticationRequired")


class SetupRequiredException(AppException):
    def __init__(self):
        super().__init__(code=460, message_key="backendErrors.setupRequired")


class OnboardingRequiredException(AppException):
    def __init__(self):
        super().__init__(code=461, message_key="backendErrors.onboardingRequired")


class AuthenticationException(AppException):
    def __init__(self, message_key: str = "backendErrors.authenticationFailed", *, params: dict | None = None):
        super().__init__(code=10023, message_key=message_key, params=params)
