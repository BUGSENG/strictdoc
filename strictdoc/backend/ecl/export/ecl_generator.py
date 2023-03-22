import os
import re
from pathlib import Path
from typing import Iterator, Generator

from strictdoc.backend.sdoc.models.document import SDocDocument
from strictdoc.backend.sdoc.models.node import SDocNode, SDocNodeField
from strictdoc.backend.sdoc.models.section import SDocSection
from strictdoc.backend.sdoc.models.model import SDocElementIF
from strictdoc.core.document_iterator import DocumentCachingIterator
from strictdoc.core.traceability_index import TraceabilityIndex

def maybe_ecl_quote(s):
    if re.search(r".*[\x00-\x20#\'\"=\\,\{\}\[\]\(\):;].*", s):
        return repr(s)
    return s


class ECLGenerator:
    @staticmethod
    def export_tree(
        traceability_index: TraceabilityIndex,
        output_ecl_root: str,
    ):
        Path(output_ecl_root).mkdir(parents=True, exist_ok=True)

        if not traceability_index.document_tree:
            return

        for document in traceability_index.document_tree.document_list:
            document_out_file_name = (
                f"{document.meta.document_filename_base}.sdoc.ecl"
            )
            document_out_file = os.path.join(
                output_ecl_root, document_out_file_name
            )

            ECLGenerator._export_single_document(
                document, traceability_index, document_out_file
            )

    @staticmethod
    def _export_single_document(
        document: SDocDocument,
        traceability_index: TraceabilityIndex,
        document_out_file,
    ):
        document_iterator: DocumentCachingIterator = (
            traceability_index.get_document_iterator(document)
        )
        doc_full_path = document_iterator.document.meta.input_doc_full_path
        requirements = list(extract_requirements(document_iterator))

        with open(document_out_file, mode="w", encoding="utf-8") as ecl_file:
            if requirements:
                ecl_file.write(
                    f'-doc_begin={maybe_ecl_quote(f"Automatically extracted from {doc_full_path}")}\n\n'
                )
                fmt_requirements_list = ",\n    ".join(requirements)
                ecl_file.write(
                    f'-requirements_list+=\n    {fmt_requirements_list}\n\n'
                )
                ecl_file.write(
                    f'-doc_end\n'
                )

def enumerate_fields(node: SDocElementIF) -> Iterator[SDocNodeField]:
    if hasattr(node, "enumerate_fields"):
        return getattr(node, "enumerate_fields")()
    else:
        return iter([])

def get_node_is_requirement(node: SDocElementIF) -> bool:
    if hasattr(node, "is_requirement"):
        is_requirement_f = getattr(node, "is_requirement")
        assert callable(is_requirement_f), (
            "is_requirement is not callable on node type: "
            f"{type(node)}"
        )
        is_requirement = is_requirement_f()
        assert type(is_requirement) is bool, (
            "is_requirement did not return a boolean on node type: "
            f"{type(node)}"
        )
        return is_requirement
    return False

def extract_requirements(
    document_iterator: DocumentCachingIterator,
) -> Generator[str, None, None]:
    for node, _ in document_iterator.all_content():
        if not get_node_is_requirement(node):
            continue
        node_fields = enumerate_fields(node)
        for field in node_fields:
            if field.field_name == "UID":
                yield field.get_text_value()
