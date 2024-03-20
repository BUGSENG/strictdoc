from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from jinja2 import Environment

from strictdoc import __version__
from strictdoc.backend.sdoc.models.document import SDocDocument
from strictdoc.backend.sdoc.models.document_view import DocumentView
from strictdoc.core.document_tree_iterator import DocumentTreeIterator
from strictdoc.core.project_config import ProjectConfig
from strictdoc.core.traceability_index import TraceabilityIndex
from strictdoc.export.html.document_type import DocumentType
from strictdoc.export.html.html_templates import HTMLTemplates
from strictdoc.export.html.renderers.link_renderer import LinkRenderer
from strictdoc.export.html.renderers.markup_renderer import MarkupRenderer


@dataclass
class SearchScreenViewObject:
    def __init__(
        self,
        *,
        traceability_index: TraceabilityIndex,
        project_config: ProjectConfig,
        templates: HTMLTemplates,
        search_results,
        search_value,
        error,
    ):
        self.traceability_index: TraceabilityIndex = traceability_index
        self.project_config: ProjectConfig = project_config
        self.templates: HTMLTemplates = templates
        self.search_results = search_results
        self.search_value = search_value
        self.error = error

        link_renderer = LinkRenderer(
            root_path="", static_path=project_config.dir_for_sdoc_assets
        )
        markup_renderer = MarkupRenderer.create(
            "RST",
            traceability_index,
            link_renderer,
            templates,
            project_config,
            None,
        )

        self.link_renderer: LinkRenderer = link_renderer
        self.markup_renderer: MarkupRenderer = markup_renderer
        self.standalone: bool = False
        self.document_tree_iterator: DocumentTreeIterator = (
            DocumentTreeIterator(traceability_index.document_tree)
        )
        self.is_running_on_server: bool = project_config.is_running_on_server
        self.strictdoc_version = __version__
        self.current_view = DocumentView.create_default(None).views[0]
        self.document_type: DocumentType = DocumentType.document()
        self.link_document_type: DocumentType = DocumentType.document()
        self.document: Optional[SDocDocument] = None

    def render_screen(self, jinja_environment: Environment):
        template = jinja_environment.get_template("screens/search/index.jinja")
        return template.render(view_object=self)

    def is_empty_tree(self) -> bool:
        return self.document_tree_iterator.is_empty_tree()

    def iterator_files_first(self):
        yield from self.document_tree_iterator.iterator_files_first()

    def render_url(self, url: str):
        return self.link_renderer.render_url(url)

    def render_static_url_with_prefix(self, url: str) -> str:
        return self.link_renderer.render_static_url_with_prefix(url)

    def render_node_link(self, incoming_link, document, document_type):
        return self.link_renderer.render_node_link(
            incoming_link, document, document_type
        )

    def render_static_url(self, url: str):
        return self.link_renderer.render_static_url(url)

    def render_local_anchor(self, node):
        return self.link_renderer.render_local_anchor(node)

    def render_free_text(self, document_type, free_text):
        return self.markup_renderer.render_free_text(document_type, free_text)

    def date_today(self):
        return datetime.today().strftime("%Y-%m-%d")

    def get_document_by_path(self, full_path: str):
        return self.traceability_index.document_tree.get_document_by_path(
            full_path
        )
