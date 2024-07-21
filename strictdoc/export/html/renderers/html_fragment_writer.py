class HTMLFragmentWriter:
    @staticmethod
    def write(text_fragment: str) -> str:
        return text_fragment

    @staticmethod
    def write_anchor_link(title: str, href: str) -> str:
        return f'<a href="{href}">🔗&nbsp;{title}</a>`'
