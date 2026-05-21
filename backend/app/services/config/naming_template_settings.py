from __future__ import annotations

from app.db.repositories.settings_sqlite_repository import SettingsSqliteRepository
from app.schemas.config import (
    AppConfig,
    MovieNamingTemplateConfig,
    NamingTemplateConfig,
    TVNamingTemplateConfig,
    Template,
)
from app.schemas.exception import ConfigurationException
from app.services.domain.library.naming_policy import combine_templates

DEFAULT_MOVIE_TEMPLATE_ID = "builtin-template-movie-default"
DEFAULT_TV_TEMPLATE_ID = "builtin-template-tv-default"


class NamingTemplateSettings:
    def __init__(self, repo: SettingsSqliteRepository) -> None:
        self._repo = repo

    def list(self) -> list[NamingTemplateConfig]:
        return self._repo.naming_templates.list()

    def replace_all(self, templates: list[NamingTemplateConfig]) -> None:
        self._repo.naming_templates.replace(templates)

    def get_template_by_id(self, template_id: str) -> Template | None:
        for template in self.list():
            if template.id == template_id:
                return Template(
                    full_template=combine_templates(template.dir_template, template.file_template),
                    dir_template=template.dir_template,
                    file_template=template.file_template,
                )
        return None

    def create(self, template: NamingTemplateConfig) -> NamingTemplateConfig:
        templates = self.list()
        if any(item.id == template.id for item in templates):
            raise ConfigurationException("backendErrors.config.templateIdExists", params={"id": template.id})
        templates = self._apply_default_flag(templates, template)
        templates.append(template)
        self.replace_all(templates)
        return template

    def update(self, template: NamingTemplateConfig) -> NamingTemplateConfig:
        templates = self.list()
        current_index = next((index for index, item in enumerate(templates) if item.id == template.id), -1)
        if current_index == -1:
            raise ConfigurationException("backendErrors.config.templateNotFound", params={"id": template.id})
        templates = self._apply_default_flag(templates, template)
        current_index = next((index for index, item in enumerate(templates) if item.id == template.id), -1)
        templates[current_index] = template
        self.replace_all(templates)
        return template

    def delete(self, template_id: str) -> None:
        templates = self.list()
        template = next((item for item in templates if item.id == template_id), None)
        if template is None:
            raise ConfigurationException("backendErrors.config.templateNotFound", params={"id": template_id})
        if template.is_default:
            raise ConfigurationException("backendErrors.config.defaultTemplateCannotDelete")
        self.replace_all([item for item in templates if item.id != template_id])

    def set_default(self, template_id: str) -> None:
        templates = self.list()
        template = next((item for item in templates if item.id == template_id), None)
        if template is None:
            raise ConfigurationException("backendErrors.config.templateNotFound", params={"id": template_id})
        self.replace_all(
            [
                item.model_copy(update={"is_default": item.id == template_id})
                if item.type == template.type
                else item
                for item in templates
            ]
        )

    def clear_default(self, template_type: str) -> None:
        self.replace_all(
            [
                item.model_copy(update={"is_default": False}) if item.type == template_type else item
                for item in self.list()
            ]
        )

    def ensure_defaults(self) -> None:
        templates = list(self.list())
        defaults: dict[str, NamingTemplateConfig] = {
            "movie": MovieNamingTemplateConfig(
                id=DEFAULT_MOVIE_TEMPLATE_ID,
                name="Default movie template",
                dir_template="{title} ({year})/{disc_package_name}",
                file_template="{title} ({year}){disc_suffix}",
                enabled=True,
                is_default=True,
            ),
            "tv": TVNamingTemplateConfig(
                id=DEFAULT_TV_TEMPLATE_ID,
                name="Default TV template",
                dir_template="{title} ({year})/Season {season:00}/{disc_package_name}",
                file_template="{title} - S{season:00}E{episode:00}{disc_suffix}",
                enabled=True,
                is_default=True,
            ),
        }
        selected_ids: dict[str, str] = {}
        for template_type in defaults:
            selected = next((item for item in templates if item.type == template_type and item.is_default), None)
            if selected is None:
                selected = next((item for item in templates if item.type == template_type), None)
            if selected is not None:
                selected_ids[template_type] = selected.id

        next_templates: list[NamingTemplateConfig] = []
        for item in templates:
            if item.type not in defaults:
                next_templates.append(item)
            elif item.id == selected_ids.get(item.type):
                next_templates.append(item.model_copy(update={"enabled": True, "is_default": True}))
            else:
                next_templates.append(item.model_copy(update={"is_default": False}))

        existing_types = {item.type for item in next_templates}
        for template_type, default in defaults.items():
            if template_type not in existing_types:
                next_templates.append(default)

        self.replace_all(next_templates)

    def resolve_default_id(self, config: AppConfig, template_type: str) -> str | None:
        for template in config.naming_templates:
            if template.type == template_type and template.is_default:
                return template.id
        return None

    def normalize_defaults(self, config: AppConfig) -> AppConfig:
        normalized = AppConfig.model_validate(config.to_plain())
        movie_default = normalized.default_movie_template_id or self.resolve_default_id(normalized, "movie")
        tv_default = normalized.default_tv_template_id or self.resolve_default_id(normalized, "tv")
        for template in normalized.naming_templates:
            if template.type == "movie":
                template.is_default = template.id == movie_default
            elif template.type == "tv":
                template.is_default = template.id == tv_default
        normalized.default_movie_template_id = movie_default
        normalized.default_tv_template_id = tv_default
        normalized.library.default_movie_template_id = movie_default
        normalized.library.default_tv_template_id = tv_default
        return normalized

    def _apply_default_flag(
        self,
        templates: list[NamingTemplateConfig],
        template: NamingTemplateConfig,
    ) -> list[NamingTemplateConfig]:
        if not template.is_default:
            return templates
        return [
            item.model_copy(update={"is_default": False})
            if item.type == template.type and item.id != template.id
            else item
            for item in templates
        ]
