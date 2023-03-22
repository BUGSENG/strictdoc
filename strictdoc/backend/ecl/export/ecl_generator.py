import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from strictdoc.backend.sdoc.models.document import SDocDocument
from strictdoc.backend.sdoc.models.node import SDocNode
from strictdoc.core.document_iterator import DocumentCachingIterator
from strictdoc.core.traceability_index import TraceabilityIndex


def maybe_ecl_quote(s):
    if re.search(r".*[\x00-\x20#\'\"=\\,\{\}\[\]\(\):;].*", s):
        return repr(s)
    return s


class ReqCoverage:
    def __init__(
        self, uid: Optional[str], tag: Optional[str], constraints: List[str]
    ):
        self.uid = uid
        self.tag = tag
        self.constraints = constraints

    def set_uid(self, uid):
        self.uid = uid

    def set_tag(self, tag):
        self.tag = tag

    def set_constraints(self, constraints):
        self.constraints = constraints

    def is_valid(self) -> bool:
        return (
            self.uid is not None
            and self.tag is not None
            and len(self.uid) > 0
            and len(self.tag) > 0
        )

    def __str__(self):
        sep = ", "
        return (
            f"\n-requirement_coverages+={{{maybe_ecl_quote(self.uid)}, "
            f"{maybe_ecl_quote(self.tag)}, "
            f"{{{sep.join(map(maybe_ecl_quote, self.constraints))}}}}}"
        )


class ReqSet:
    def __init__(self, uid: str, reqs: List[str], covs: List[str]):
        self.uid = uid
        self.reqs = reqs
        self.coverages = covs

    def set_uid(self, uid):
        self.uid = uid

    def set_requirements(self, reqs):
        self.reqs = reqs

    def set_coverages(self, covs):
        self.coverages = covs

    def __str__(self):
        sep = ",\n  "
        return (
            f"\n-requirements+={{{maybe_ecl_quote(self.uid)}, "
            f"{{\n  {sep.join(map(maybe_ecl_quote, self.reqs))}\n}}, "
            f"{{\n  {sep.join(map(maybe_ecl_quote, self.coverages))}\n}}}}"
        )


def extract_coverages(
    document_iterator: DocumentCachingIterator,
) -> Tuple[List[ReqCoverage], List[str]]:
    # Extract coverages
    coverages = set()
    coverage_tags = set()
    for node in document_iterator.all_content():
        if node.is_requirement:
            coverage = ReqCoverage("", "", "")
            constraints = set()
            for field in node.enumerate_fields():
                if field.field_name == "UID":
                    coverage.set_uid(field.get_text_value())
                elif field.field_name == "COVERAGE_TAG":
                    coverage.set_tag(field.get_text_value())
                elif field.field_name == "COVERAGE_SINGLE":
                    constraints.add("single")
                elif field.field_name == "COVERAGE_COMPLETE":
                    constraints.add("complete")
                elif field.field_name == "COVERAGE_INDEPENDENT":
                    constraints.add(
                        "independent(" + field.get_text_value() + ")"
                    )
                elif field.field_name == "COVERAGE_RELEVANT":
                    constraints.add("relevant(" + field.get_text_value() + ")")

                coverage.set_constraints(constraints)
                if coverage.is_valid():
                    coverage_tags.add(coverage.uid)
                    coverages.add(coverage)
    return coverages, coverage_tags


def extract_reqsets(
    traceability_index: TraceabilityIndex,
    document_iterator: DocumentCachingIterator,
) -> Dict[str, ReqSet]:
    # Extract requirement sets
    req_sets: Dict[str, ReqSet] = {}

    for node in document_iterator.all_content():
        # we only care about requirement that have at least one relation that refers a coverage
        if node.is_requirement:
            for uid, _ in node.get_parent_requirement_reference_uids():
                new_reqset = None
                if uid not in req_sets:
                    # new requirement set
                    new_reqset = ReqSet(uid, [], [])
                    reqset_node = traceability_index.get_linkable_node_by_uid(
                        uid
                    )
                    if not reqset_node.is_requirement:
                        raise AssertionError("Parent node is not a requirement")
                    else:
                        has_coverages = False
                        for (
                            parent,
                            _,
                        ) in traceability_index.get_parent_relations_with_role(
                            reqset_node, "Coverage"
                        ):
                            parent_req: SDocNode = parent
                            coverage_req = (
                                traceability_index.get_linkable_node_by_uid(
                                    parent_req.reserved_uid
                                )
                            )
                            new_reqset.coverages.append(
                                coverage_req.reserved_uid
                            )
                            has_coverages = True
                    if has_coverages and new_reqset is not None:
                        new_reqset.reqs.append(node.reserved_uid)
                        req_sets[uid] = new_reqset
                else:
                    req_sets[uid].reqs.append(node.reserved_uid)
    for v in req_sets.values():
        v.reqs.sort()
        v.coverages.sort()
    return req_sets


class ECLGenerator:
    @staticmethod
    def export_tree(
        traceability_index: TraceabilityIndex,
        output_ecl_root: str,
    ):
        Path(output_ecl_root).mkdir(parents=True, exist_ok=True)

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
        coverages, coverage_tags = extract_coverages(document_iterator)
        reqsets = extract_reqsets(traceability_index, document_iterator)
        with open(document_out_file, mode="w", encoding="utf-8") as ecl_file:
            ecl_file.write(
                f'-doc_begin={maybe_ecl_quote(f"Automatically extracted from {doc_full_path}")}\n'
            )
            for coverage in coverages:
                ecl_file.write(coverage.__str__())
                ecl_file.write("\n")
            for req_set in reqsets.values():
                ecl_file.write(req_set.__str__())
                ecl_file.write("\n")
            ecl_file.write("\n-doc_end\n")
