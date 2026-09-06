from .html_adapter import GenericHtmlAdapter


class CufeMainAdapter(GenericHtmlAdapter):
    def __init__(self, base_url: str = "https://www.cufe.edu.cn/"):
        super().__init__("cufe_main", base_url)

