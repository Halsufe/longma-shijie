from .html_adapter import GenericHtmlAdapter


class CufeYouthAdapter(GenericHtmlAdapter):
    def __init__(self, base_url: str = "https://youth.cufe.edu.cn/"):
        super().__init__("cufe_youth", base_url)

