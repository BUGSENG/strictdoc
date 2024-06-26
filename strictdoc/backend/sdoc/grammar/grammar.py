REGEX_UID = r"([A-Za-z0-9]+[A-Za-z0-9_\-]*)"
NEGATIVE_FREETEXT_END = "(?!^\\[\\/FREETEXT\\]\n)"
NEGATIVE_INLINE_LINK_START = rf"(?!\[LINK: {REGEX_UID})"
NEGATIVE_ANCHOR_START = rf"(?!^\[ANCHOR: {REGEX_UID})"

TEXT_TYPES_GRAMMAR = rf"""
TextPart[noskipws]:
  (Anchor | InlineLink | NormalString)
;

NormalString[noskipws]:
  (/(?ms){NEGATIVE_FREETEXT_END}{NEGATIVE_INLINE_LINK_START}{NEGATIVE_ANCHOR_START}./)+
;

InlineLink[noskipws]:
  '[LINK: ' value = /{REGEX_UID}/ ']'
;

Anchor[noskipws]:
  /^\[ANCHOR: /
  value = /{REGEX_UID}/ (', ' title = /\w+[\s\w+]*/)?
  /\](\Z|\n)/
;
"""

FREE_TEXT_PARSER_GRAMMAR = r"""
FreeTextContainer[noskipws]:
  parts*=TextPart
;
"""

DOCUMENT_GRAMMAR = rf"""
SDocDocument[noskipws]:
  '[DOCUMENT]' '\n'
  ('MID: ' mid = SingleLineString '\n')?
  'TITLE: ' title = SingleLineString '\n'
  (config = DocumentConfig)?
  (view = DocumentView)?
  ('\n' grammar = DocumentGrammar)?
  free_texts *= SpaceThenFreeText
  section_contents *= SectionOrRequirement
;

DocumentConfig[noskipws]:
  ('UID: ' uid = /{REGEX_UID}/ '\n')?
  ('VERSION: ' version = SingleLineString '\n')?
  ('CLASSIFICATION: ' classification = SingleLineString '\n')?
  ('REQ_PREFIX: ' requirement_prefix = SingleLineString '\n')?
  ('ROOT: ' (root = BooleanChoice) '\n')?
  ('OPTIONS:' '\n'
    ('  ENABLE_MID: ' (enable_mid = BooleanChoice) '\n')?
    ('  MARKUP: ' (markup = MarkupChoice) '\n')?
    ('  AUTO_LEVELS: ' (auto_levels = AutoLevelsChoice) '\n')?
    ('  LAYOUT: ' (layout = LayoutChoice) '\n')?
    ('  REQUIREMENT_STYLE: ' (requirement_style = RequirementStyleChoice) '\n')?
    ('  REQUIREMENT_IN_TOC: '
        (requirement_in_toc = RequirementHasTitleChoice) '\n'
    )?
    ('  DEFAULT_VIEW: ' default_view = SingleLineString '\n')?
  )?
;

DocumentView[noskipws]:
  'VIEWS:' '\n'
  views += ViewElement
;

ViewElement[noskipws]:
  '- ID: ' view_id = /{REGEX_UID}/ '\n'
  ('  NAME: ' name = SingleLineString '\n')?
  '  TAGS:' '\n'
  tags += ViewElementTags
  ('  HIDDEN_TAGS:' '\n'
  hidden_tags += ViewElementHiddenTag)?
;

ViewElementTags[noskipws]:
  '  - OBJECT_TYPE: ' object_type = SingleLineString '\n'
  '    VISIBLE_FIELDS:' '\n'
  visible_fields += ViewElementField
;

ViewElementField[noskipws]:
  '    - NAME: ' name = SingleLineString '\n'
  ('      PLACEMENT: ' placement = SingleLineString '\n')?
;

ViewElementHiddenTag[noskipws]:
  '  - ' hidden_tag = SingleLineString '\n'
;

MarkupChoice[noskipws]:
  'RST' | 'Text' | 'HTML'
;

RequirementStyleChoice[noskipws]:
  'Inline' | 'Simple' | 'Table' | 'Zebra'
;

RequirementHasTitleChoice[noskipws]:
  'True' | 'False'
;

AutoLevelsChoice[noskipws]:
  'On' | 'Off'
;

LayoutChoice[noskipws]:
  'Default' | 'Website'
;
"""

SECTION_GRAMMAR = rf"""
SDocSection[noskipws]:
  '[SECTION]'
  '\n'
  ('MID: ' mid = SingleLineString '\n')?
  ('UID: ' uid = /{REGEX_UID}/ '\n')?
  ('LEVEL: ' custom_level = SingleLineString '\n')?
  'TITLE: ' title = SingleLineString '\n'
  ('REQ_PREFIX: ' requirement_prefix = SingleLineString '\n')?
  free_texts *= SpaceThenFreeText
  section_contents *= SectionOrRequirement
  '\n'
  '[/SECTION]'
  '\n'
;

SectionOrRequirement[noskipws]:
  '\n' (SDocSection | SDocNode | SDocCompositeNode | DocumentFromFile)
;

DocumentFromFile[noskipws]:
  '[DOCUMENT_FROM_FILE]' '\n'
  'FILE: ' file = /.+$/ '\n'
;

SpaceThenRequirement[noskipws]:
  '\n' (SDocNode | SDocCompositeNode)
;

SpaceThenFreeText[noskipws]:
  '\n' (FreeText)
;

ReservedKeyword[noskipws]:
  'DOCUMENT' | 'GRAMMAR' | 'SECTION' | 'DOCUMENT_FROM_FILE' | 'FREETEXT'
;

SDocNode[noskipws]:
  '[' !SDocCompositeNodeTagName requirement_type = RequirementType ']' '\n'
  ('MID: ' mid = SingleLineString '\n')?
  fields *= SDocNodeField
  (
    'RELATIONS:' '\n'
    (relations += Reference)
  )?
;

SDocCompositeNodeTagName[noskipws]:
  'COMPOSITE_'
;

SDocNodeField[noskipws]:
  (
    field_name = FieldName ':'
    (
      ((' ' field_value = SingleLineString) '\n') |
      (' ' (field_value_multiline = MultiLineString) '\n')
    )
  )
;

SDocCompositeNode[noskipws]:
  '[COMPOSITE_' requirement_type = RequirementType ']' '\n'

  ('MID: ' mid = SingleLineString '\n')?

  fields *= SDocNodeField
  (
    'RELATIONS:' '\n'
    (relations += Reference)
  )?

  requirements *= SpaceThenRequirement

  '\n'
  '[/COMPOSITE_REQUIREMENT]' '\n'
;

RequirementStatus[noskipws]:
  'Draft' | 'Active' | 'Deleted';

FreeText[noskipws]:
  /\[FREETEXT\]\n/
  parts*=TextPart
  /\[\/FREETEXT\]\n/
;
"""
