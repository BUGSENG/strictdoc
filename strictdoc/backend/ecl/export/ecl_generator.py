import os
import re
from pathlib import Path

from strictdoc.backend.sdoc.models.document import Document

from strictdoc.cli.cli_arg_parser import ExportCommandConfig
from strictdoc.core.traceability_index import TraceabilityIndex


def maybe_ecl_quote(s):
    if re.search(r".*[\x00-\x20#\'\"=\\,\{\}\[\]\(\):;].*", s):
        return repr(s)
    return s


class ReqCoverage:
    def __init__(self, uid, tag, constraints):
        self.uid = uid
        self.tag = tag
        self.constraints = constraints

    def set_uid(self, id):
        self.uid = id

    def set_tag(self, tag):
        self.tag = tag

    def set_constraints(self, constraints):
        self.constraints = constraints

    def __str__(self):
        sep = ", "
        return (
            f"\n-requirement_coverages+={{{maybe_ecl_quote(self.uid)}, "
            f"{maybe_ecl_quote(self.tag)}, "
            f"{{{sep.join(map(maybe_ecl_quote, self.constraints))}}}}}"
        )


class ReqSet:
    def __init__(self, uid, reqs, covs):
        self.uid = uid
        self.reqs = reqs
        self.coverages = covs

    def set_uid(self, id):
        self.uid = id

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


def visit_node(node, visited, target_set):
    visited.add(node.node_id)
    if node.is_requirement and len(node.references) > 0:
        req_uid = None
        for field in node.fields:
            if field.field_name == "UID":
                req_uid = field.field_value
        for ref in node.references:
            if ref.ref_type == "Parent" and ref.ref_uid == target_set:
                return visited, set([req_uid])
    return visited, set()


def visit_sections(sections, visited, target_set):
    visited_reqs = visited
    requirements = set()
    for node in sections:
        if node.is_section and len(node.section_contents) > 0:
            new_visited, new_reqset = visit_sections(
                node.section_contents, visited_reqs, target_set
            )
        else:
            new_visited, new_reqset = visit_node(node, visited_reqs, target_set)
        visited_reqs |= new_visited
        requirements |= new_reqset
    return visited_reqs, requirements


def extract_coverages(document):
    # Extract coverages
    coverages = []
    coverage_tags = set()
    for section in document.section_contents:
        for requirement in section.section_contents:
            if requirement.is_requirement:
                constraints = set()
                coverage = ReqCoverage("", "", "")
                for field in requirement.fields_as_parsed:
                    match field.field_name:
                        case "UID":
                            coverage.set_uid(field.field_value)
                        case "COVERAGE_TAG":
                            coverage.set_tag(field.field_value)
                        case "COVERAGE_SINGLE":
                            constraints.add("single")
                        case "COVERAGE_COMPLETE":
                            constraints.add(
                                "complete(" + field.field_value + ")"
                            )
                        case "COVERAGE_INDEPENDENT":
                            constraints.add(
                                "indipendent(" + field.field_value + ")"
                            )
                        case "COVERAGE_RELEVANT":
                            constraints.add(
                                "relevant(" + field.field_value + ")"
                            )
                coverage.set_constraints(constraints)
                if len(coverage.tag) > 0:
                    coverage_tags.add(coverage.uid)
                    coverages.append(coverage)
    return coverages, coverage_tags


def extract_reqsets(document, coverages):
    # Extract requirement sets
    req_sets = []
    for section in document.section_contents:
        for requirement in section.section_contents:
            if requirement.is_requirement and len(requirement.references) > 0:
                covs = set()
                reqset = ReqSet("", "", "")
                # Fill coverages
                for ref in requirement.references:
                    if ref.ref_type == "Parent" and ref.ref_uid in coverages:
                        covs.add(ref.ref_uid)
                if len(covs) == 0:
                    break
                reqset.set_coverages(covs)
                for field in requirement.fields_as_parsed:
                    if field.field_name == "UID":
                        reqset.set_uid(field.field_value)
                # Visit children to collect requirements
                visited = set([requirement.node_id])
                _, new_reqset = visit_sections(
                    document.section_contents, visited, reqset.uid
                )
                reqset.reqs = sorted(new_reqset)
                req_sets.append(reqset)
    return req_sets


class ECLGenerator:
    @staticmethod
    def export_tree(
        traceability_index: TraceabilityIndex,
        output_ecl_root: str,
    ):
        Path(output_ecl_root).mkdir(parents=True, exist_ok=True)

        document: Document
        for document in traceability_index.document_tree.document_list:
            document_out_file_name = (
                f"{document.meta.document_filename_base}.sdoc.ecl"
            )
            document_out_file = os.path.join(
                output_ecl_root, document_out_file_name
            )

            ECLGenerator._export_single_document(document, document_out_file)

    @staticmethod
    def _export_single_document(
        document: Document,
        document_out_file,
    ):
        coverages, coverage_tags = extract_coverages(document)
        reqsets = extract_reqsets(document, coverage_tags)
        with open(document_out_file, mode="w", encoding="utf-8") as ecl_file:
            ecl_file.write(
                f'-doc_begin={maybe_ecl_quote(f"Automatically extracted from {document.meta.input_doc_full_path}")}\n'
            )
            for coverage in coverages:
                ecl_file.write(coverage.__str__())
                ecl_file.write("\n")
            for req_set in reqsets:
                ecl_file.write(req_set.__str__())
                ecl_file.write("\n")
            ecl_file.write("\n-doc_end\n")
