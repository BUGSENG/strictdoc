# mypy: disable-error-code="no-untyped-def,union-attr,operator"
from typing import Dict, List, Optional, Union

from reqif.models.reqif_data_type import ReqIFDataTypeDefinitionEnumeration
from reqif.models.reqif_spec_object import ReqIFSpecObject
from reqif.models.reqif_spec_object_type import (
    ReqIFSpecObjectType,
    SpecAttributeDefinition,
)
from reqif.models.reqif_specification import ReqIFSpecification
from reqif.models.reqif_types import SpecObjectAttributeType
from reqif.reqif_bundle import ReqIFBundle

from strictdoc.backend.reqif.sdoc_reqif_fields import (
    REQIF_MAP_TO_SDOC_FIELD_MAP,
    ReqIFChapterField,
    ReqIFRequirementReservedField,
)
from strictdoc.backend.sdoc.models.document import SDocDocument
from strictdoc.backend.sdoc.models.document_config import DocumentConfig
from strictdoc.backend.sdoc.models.document_grammar import (
    DocumentGrammar,
    GrammarElement,
    create_default_relations,
)
from strictdoc.backend.sdoc.models.free_text import FreeText
from strictdoc.backend.sdoc.models.node import SDocNode, SDocNodeField
from strictdoc.backend.sdoc.models.reference import (
    ParentReqReference,
    Reference,
)
from strictdoc.backend.sdoc.models.section import SDocSection
from strictdoc.backend.sdoc.models.type_system import (
    GrammarElementFieldMultipleChoice,
    GrammarElementFieldSingleChoice,
    GrammarElementFieldString,
)
from strictdoc.helpers.string import (
    create_safe_requirement_tag_string,
    unescape,
)


class P01_ReqIFToSDocBuildContext:
    def __init__(self, *, enable_mid: bool, import_markup: Optional[str]):
        self.enable_mid: bool = enable_mid
        self.import_markup: Optional[str] = import_markup
        self.map_spec_object_type_identifier_to_grammar_node_tags: Dict[
            str, GrammarElement
        ] = {}


class P01_ReqIFToSDocConverter:
    @staticmethod
    def convert_reqif_bundle(
        reqif_bundle: ReqIFBundle,
        enable_mid: bool,
        import_markup: str,
    ) -> List[SDocDocument]:
        context = P01_ReqIFToSDocBuildContext(
            enable_mid=enable_mid, import_markup=import_markup
        )

        if (
            reqif_bundle.core_content is None
            or reqif_bundle.core_content.req_if_content is None
            or len(reqif_bundle.core_content.req_if_content.specifications) == 0
        ):
            return []

        documents: List[SDocDocument] = []
        for (
            specification
        ) in reqif_bundle.core_content.req_if_content.specifications:
            document = P01_ReqIFToSDocConverter._create_document_from_reqif_specification(
                specification=specification,
                reqif_bundle=reqif_bundle,
                context=context,
            )
            documents.append(document)
        return documents

    @staticmethod
    def is_spec_object_requirement(_):
        return True

    @staticmethod
    def is_spec_object_section(
        spec_object: ReqIFSpecObject, reqif_bundle: ReqIFBundle
    ):
        spec_object_type = reqif_bundle.lookup.get_spec_type_by_ref(
            spec_object.spec_object_type
        )
        return spec_object_type.long_name == "SECTION"

    @staticmethod
    def is_spec_object_free_text(
        spec_object: ReqIFSpecObject, reqif_bundle: ReqIFBundle
    ):
        spec_object_type = reqif_bundle.lookup.get_spec_type_by_ref(
            spec_object.spec_object_type
        )
        return spec_object_type.long_name == "FREETEXT"

    @staticmethod
    def convert_requirement_field_from_reqif(field_name: str) -> str:
        if field_name in ReqIFRequirementReservedField.SET:
            return REQIF_MAP_TO_SDOC_FIELD_MAP[field_name]
        return field_name

    @staticmethod
    def _create_document_from_reqif_specification(
        *,
        specification: ReqIFSpecification,
        reqif_bundle: ReqIFBundle,
        context: P01_ReqIFToSDocBuildContext,
    ):
        document = P01_ReqIFToSDocConverter.create_document(
            specification=specification, context=context
        )
        document.section_contents = []

        for (
            spec_object_type_
        ) in reqif_bundle.core_content.req_if_content.spec_types:
            if not isinstance(spec_object_type_, ReqIFSpecObjectType):
                continue

            grammar_element: GrammarElement = P01_ReqIFToSDocConverter.create_grammar_element_from_spec_object_type(
                spec_object_type=spec_object_type_,
                reqif_bundle=reqif_bundle,
            )
            context.map_spec_object_type_identifier_to_grammar_node_tags[
                spec_object_type_.identifier
            ] = grammar_element

        # This lookup object is used to first collect the spec object type identifiers
        # that are actually used by this document. This is needed to ensure that a
        # StrictDoc document is not created with irrelevant grammar elements that
        # actually belong to other Specifications in this ReqIF bundle.
        # Using Dict as an ordered set.
        spec_object_type_identifiers_used_by_this_document: Dict[str, None] = {}

        def node_converter_lambda(
            current_hierarchy_,
            current_section_,
        ):
            spec_object = reqif_bundle.get_spec_object_by_ref(
                current_hierarchy_.spec_object
            )
            spec_object_type_identifiers_used_by_this_document[
                spec_object.spec_object_type
            ] = None

            is_section = P01_ReqIFToSDocConverter.is_spec_object_section(
                spec_object,
                reqif_bundle=reqif_bundle,
            )

            converted_node: Union[SDocSection, SDocNode, FreeText]
            if is_section:
                converted_node = (
                    P01_ReqIFToSDocConverter.create_section_from_spec_object(
                        spec_object=spec_object,
                        context=context,
                        level=current_hierarchy_.level,
                        reqif_bundle=reqif_bundle,
                    )
                )
            elif P01_ReqIFToSDocConverter.is_spec_object_free_text(
                spec_object,
                reqif_bundle=reqif_bundle,
            ):
                converted_node = (
                    P01_ReqIFToSDocConverter.create_free_text_from_spec_object(
                        spec_object=spec_object,
                    )
                )
                if len(current_section_.free_texts) == 0:
                    current_section_.free_texts.append(converted_node)
                return converted_node, False
            else:
                converted_node = P01_ReqIFToSDocConverter.create_requirement_from_spec_object(
                    spec_object=spec_object,
                    context=context,
                    parent_section=current_section_,
                    reqif_bundle=reqif_bundle,
                    level=current_hierarchy_.level,
                )
            current_section_.section_contents.append(converted_node)

            return converted_node, is_section

        reqif_bundle.iterate_specification_hierarchy_for_conversion(
            specification,
            document,
            lambda s: s.ng_level,
            node_converter_lambda,
        )

        elements: List[GrammarElement] = []
        for (
            spec_object_type_identifier_
        ) in spec_object_type_identifiers_used_by_this_document.keys():
            spec_object_type: ReqIFSpecObjectType = (
                reqif_bundle.lookup.get_spec_type_by_ref(
                    spec_object_type_identifier_
                )
            )
            if spec_object_type.long_name in ("SECTION", "FREETEXT"):
                continue
            grammar_element = (
                context.map_spec_object_type_identifier_to_grammar_node_tags[
                    spec_object_type_identifier_
                ]
            )
            elements.append(grammar_element)
        grammar: DocumentGrammar
        if len(elements) > 0:
            grammar = DocumentGrammar(parent=document, elements=elements)
            grammar.is_default = False
        else:
            grammar = DocumentGrammar.create_default(parent=document)
        document.grammar = grammar

        return document

    @staticmethod
    def create_grammar_element_from_spec_object_type(
        *,
        spec_object_type: ReqIFSpecObjectType,
        reqif_bundle: ReqIFBundle,
    ):
        fields: List[
            Union[
                GrammarElementFieldString,
                GrammarElementFieldMultipleChoice,
                GrammarElementFieldSingleChoice,
            ]
        ] = []
        for attribute in spec_object_type.attribute_definitions:
            field_name = (
                P01_ReqIFToSDocConverter.convert_requirement_field_from_reqif(
                    attribute.long_name
                )
            )
            # Chapter name is a reserved field for sections.
            if field_name == ReqIFChapterField.CHAPTER_NAME:
                continue
            if attribute.attribute_type == SpecObjectAttributeType.STRING:
                fields.append(
                    GrammarElementFieldString(
                        parent=None,
                        title=field_name,
                        human_title=None,
                        required="False",
                    )
                )
            elif attribute.attribute_type == SpecObjectAttributeType.XHTML:
                fields.append(
                    GrammarElementFieldString(
                        parent=None,
                        title=field_name,
                        human_title=None,
                        required="False",
                    )
                )
            elif (
                attribute.attribute_type == SpecObjectAttributeType.ENUMERATION
            ):
                enum_data_type: ReqIFDataTypeDefinitionEnumeration = (
                    reqif_bundle.lookup.get_data_type_by_ref(
                        attribute.datatype_definition
                    )
                )
                options = list(map(lambda v: v.key, enum_data_type.values))
                if attribute.multi_valued is True:
                    fields.append(
                        GrammarElementFieldMultipleChoice(
                            parent=None,
                            title=field_name,
                            human_title=None,
                            options=options,
                            required="False",
                        )
                    )
                else:
                    fields.append(
                        GrammarElementFieldSingleChoice(
                            parent=None,
                            title=field_name,
                            human_title=None,
                            options=options,
                            required="False",
                        )
                    )
            elif attribute.attribute_type == SpecObjectAttributeType.DATE:
                # Recognize the DATE attributes but do nothing about them,
                # since StrictDoc has no concept of "date" for its grammar
                # fields.
                pass
            else:
                raise NotImplementedError(attribute) from None

        requirement_element = GrammarElement(
            parent=None,
            tag=create_safe_requirement_tag_string(spec_object_type.long_name),
            fields=fields,
            relations=[],
        )
        requirement_element.relations = create_default_relations(
            requirement_element
        )
        return requirement_element

    @staticmethod
    def create_document(
        *,
        specification: ReqIFSpecification,
        context: P01_ReqIFToSDocBuildContext,
    ) -> SDocDocument:
        document_config = DocumentConfig.default_config(None)
        document_config.enable_mid = (
            context.enable_mid if context.enable_mid else None
        )
        document_title = (
            specification.long_name
            if specification.long_name is not None
            else "<No title>"
        )
        document = SDocDocument(
            None, document_title, document_config, None, None, [], []
        )
        if context.enable_mid:
            document.reserved_mid = specification.identifier
        if context.import_markup is not None:
            document_config.markup = context.import_markup

        document.grammar = DocumentGrammar.create_default(document)
        return document

    @staticmethod
    def create_section_from_spec_object(
        *,
        spec_object: ReqIFSpecObject,
        context: P01_ReqIFToSDocBuildContext,
        level: int,
        reqif_bundle: ReqIFBundle,
    ) -> SDocSection:
        spec_object_type = reqif_bundle.lookup.get_spec_type_by_ref(
            spec_object.spec_object_type
        )
        attribute_map: Dict[str, SpecAttributeDefinition] = (
            spec_object_type.attribute_map
        )
        assert attribute_map is not None
        for attribute in spec_object.attributes:
            field_name_or_none: Optional[str] = attribute_map[
                attribute.definition_ref
            ].long_name
            if field_name_or_none is None:
                raise NotImplementedError
            field_name: str = field_name_or_none
            if field_name == ReqIFChapterField.CHAPTER_NAME:
                section_title = attribute.value
                break
        else:
            raise NotImplementedError(spec_object, attribute_map)

        free_texts = []
        if ReqIFChapterField.TEXT in spec_object.attribute_map:
            free_text = unescape(
                spec_object.attribute_map[ReqIFChapterField.TEXT].value
            )
            free_texts.append(
                FreeText(
                    parent=None,
                    parts=[free_text],
                )
            )
        # Sanitize the title. Titles can also come from XHTML attributes with
        # custom newlines such as:
        #             <ATTRIBUTE-VALUE-XHTML>
        #               <THE-VALUE>
        #                 Some value
        #               </THE-VALUE>
        section_title = section_title.strip().replace("\n", " ")

        section_mid = spec_object.identifier if context.enable_mid else None

        section = SDocSection(
            parent=None,
            mid=section_mid,
            uid=None,
            custom_level=None,
            title=section_title,
            requirement_prefix=None,
            free_texts=free_texts,
            section_contents=[],
        )
        section.ng_level = level
        return section

    @staticmethod
    def create_requirement_from_spec_object(
        spec_object: ReqIFSpecObject,
        context: P01_ReqIFToSDocBuildContext,
        parent_section: Union[SDocSection, SDocDocument],
        reqif_bundle: ReqIFBundle,
        level,
    ) -> SDocNode:
        fields = []
        spec_object_type = reqif_bundle.lookup.get_spec_type_by_ref(
            spec_object.spec_object_type
        )
        attribute_map: Dict[str, SpecAttributeDefinition] = (
            spec_object_type.attribute_map
        )

        foreign_key_id_or_none: Optional[str] = None
        for attribute in spec_object.attributes:
            long_name_or_none = attribute_map[
                attribute.definition_ref
            ].long_name
            if long_name_or_none is None:
                raise NotImplementedError
            field_name: str = long_name_or_none
            if attribute.attribute_type == SpecObjectAttributeType.ENUMERATION:
                sdoc_field_name = P01_ReqIFToSDocConverter.convert_requirement_field_from_reqif(
                    field_name,
                )
                enum_values_resolved = []
                for (
                    attribute_definition_
                ) in spec_object_type.attribute_definitions:
                    if (
                        attribute.definition_ref
                        == attribute_definition_.identifier
                    ):
                        datatype_definition = (
                            attribute_definition_.datatype_definition
                        )

                        datatype: ReqIFDataTypeDefinitionEnumeration = (
                            reqif_bundle.lookup.get_data_type_by_ref(
                                datatype_definition
                            )
                        )

                        enum_values_list = list(attribute.value)
                        for enum_value in enum_values_list:
                            enum_values_resolved.append(
                                datatype.values_map[enum_value].key
                            )

                        break
                else:
                    raise NotImplementedError

                enum_values = ", ".join(enum_values_resolved)
                fields.append(
                    SDocNodeField(
                        parent=None,
                        field_name=sdoc_field_name,
                        field_value=enum_values,
                        field_value_multiline=None,
                    )
                )
                continue
            assert isinstance(attribute.value, str)
            if long_name_or_none == "ReqIF.ForeignID":
                foreign_key_id_or_none = attribute.definition_ref
            attribute_value: Optional[str] = unescape(attribute.value)
            attribute_multiline_value = None
            if (
                "\n" in attribute_value
                or attribute.attribute_type == SpecObjectAttributeType.XHTML
                or field_name == ReqIFRequirementReservedField.TEXT
                or field_name == ReqIFRequirementReservedField.COMMENT_NOTES
            ):
                attribute_multiline_value = attribute_value.lstrip()
                attribute_value = None

            sdoc_field_name = (
                P01_ReqIFToSDocConverter.convert_requirement_field_from_reqif(
                    field_name,
                )
            )
            fields.append(
                SDocNodeField(
                    parent=None,
                    field_name=sdoc_field_name,
                    field_value=attribute_value,
                    field_value_multiline=attribute_multiline_value,
                )
            )

        requirement_mid = spec_object.identifier if context.enable_mid else None

        grammar_element: GrammarElement = (
            context.map_spec_object_type_identifier_to_grammar_node_tags[
                spec_object_type.identifier
            ]
        )

        requirement = SDocNode(
            parent=parent_section,
            requirement_type=grammar_element.tag,
            mid=requirement_mid,
            fields=fields,
            relations=[],
        )
        requirement.ng_level = level

        if foreign_key_id_or_none is not None:
            spec_object_parents = reqif_bundle.get_spec_object_parents(
                spec_object.identifier
            )
            parent_refs: List[Reference] = []
            for spec_object_parent in spec_object_parents:
                parent_spec_object_parent = (
                    reqif_bundle.lookup.get_spec_object_by_ref(
                        spec_object_parent
                    )
                )

                parent_refs.append(
                    ParentReqReference(
                        requirement,
                        parent_spec_object_parent.attribute_map[
                            foreign_key_id_or_none
                        ].value,
                        role=None,
                    )
                )
            if len(parent_refs) > 0:
                requirement.relations = parent_refs
        return requirement

    @staticmethod
    def create_free_text_from_spec_object(
        spec_object: ReqIFSpecObject,
    ) -> FreeText:
        free_text = unescape(
            spec_object.attribute_map[ReqIFChapterField.TEXT].value
        )
        return FreeText(
            parent=None,
            parts=[free_text],
        )
